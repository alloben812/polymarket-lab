#!/usr/bin/env python3
"""Polymarket connection check. Standard library only, no account, no key.

What it does (all public, read-only):
  1. Official geoblock check: GET https://polymarket.com/api/geoblock
     (docs: https://docs.polymarket.com/api-reference/geoblock.md, read 2026-11-27).
     Prints `blocked` and `country`; the IP address is masked and never written anywhere.
  2. Latency of 10 requests to the public CLOB REST endpoint GET /book?token_id=...
     (docs: https://docs.polymarket.com/market-data/prices-order-books.md).
  3. WebSocket handshake to the public market channel
     wss://ws-subscriptions-clob.polymarket.com/ws/market and a 15-second message count
     (docs: https://docs.polymarket.com/api-reference/wss/market.md). Implemented with the
     standard library (RFC 6455 client, text frames only).

Exit codes: 0 all fine; 2 geoblock says blocked; 3 REST unreachable (geoblock or CLOB);
4 REST fine but the WebSocket failed.

Runs on python3 >= 3.8 (macOS system python included).
"""
import base64
import hashlib
import json
import os
import socket
import ssl
import statistics
import struct
import sys
import time
import urllib.parse
import urllib.request

GEOBLOCK_URL = "https://polymarket.com/api/geoblock"
GAMMA_MARKETS = "https://gamma-api.polymarket.com/markets"
CLOB_BOOK = "https://clob.polymarket.com/book"
WS_HOST = "ws-subscriptions-clob.polymarket.com"
WS_PATH = "/ws/market"
UA = "pm-pilot-conn-check/1.0"
TIMEOUT = 15
WS_SECONDS = 15


def http_get_json(url, timeout=TIMEOUT):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as r:
        return json.loads(r.read().decode("utf-8"))


def mask_ip(ip):
    if not ip:
        return "?"
    if ":" in ip:
        return ip.split(":")[0] + ":****"
    parts = ip.split(".")
    if len(parts) == 4:
        return parts[0] + ".*.*.*"
    return "****"


def geoblock():
    print("[1] Geoblock check (official endpoint %s)" % GEOBLOCK_URL)
    try:
        geo = http_get_json(GEOBLOCK_URL)
    except Exception as e:  # noqa: BLE001
        print("    UNREACHABLE: %s" % type(e).__name__)
        return None
    blocked = geo.get("blocked")
    print("    blocked = %s" % blocked)
    print("    country = %s" % geo.get("country"))
    print("    ip      = %s (masked)" % mask_ip(geo.get("ip")))
    return bool(blocked)


def pick_token():
    """A liquid open market from the public Gamma API (top 24h volume)."""
    q = urllib.parse.urlencode({"closed": "false", "active": "true", "order": "volume24hr",
                                "ascending": "false", "limit": "5"})
    rows = http_get_json(GAMMA_MARKETS + "?" + q)
    for m in rows:
        ids = m.get("clobTokenIds")
        if isinstance(ids, str):
            ids = json.loads(ids)
        if ids and m.get("enableOrderBook", True):
            return m, ids
    raise RuntimeError("no open market with an order book found")


def clob_latency():
    print("[2] Public CLOB REST latency (10 x GET %s)" % CLOB_BOOK)
    try:
        market, ids = pick_token()
    except Exception as e:  # noqa: BLE001
        print("    UNREACHABLE (gamma market list): %s" % type(e).__name__)
        return None, None
    token = ids[0]
    print("    market : %s" % (market.get("question") or market.get("slug")))
    print("    slug   : %s" % market.get("slug"))
    outs = market.get("outcomes")
    if isinstance(outs, str):
        try:
            outs = json.loads(outs)
        except ValueError:
            outs = None
    for i, t in enumerate(ids):
        name = outs[i] if outs and i < len(outs) else "#%d" % i
        print("    token  : %s = %s" % (name, t))
    url = CLOB_BOOK + "?" + urllib.parse.urlencode({"token_id": token})
    times = []
    book = None
    errors = 0
    for _ in range(10):
        t0 = time.perf_counter()
        try:
            book = http_get_json(url)
            times.append((time.perf_counter() - t0) * 1000.0)
        except Exception as e:  # noqa: BLE001
            errors += 1
            last = type(e).__name__
        time.sleep(0.2)
    if not times:
        print("    UNREACHABLE: all 10 requests failed (%s)" % last)
        return None, token
    print("    ok %d/10   min %.0f ms   median %.0f ms   max %.0f ms"
          % (len(times), min(times), statistics.median(times), max(times)))
    if book:
        bids = book.get("bids") or []
        asks = book.get("asks") or []
        # The CLOB returns bids ascending and asks descending (NOTES.md); take max/min to be safe.
        bb = max((float(b["price"]) for b in bids), default=None)
        ba = min((float(a["price"]) for a in asks), default=None)
        print("    best bid %s / best ask %s   tick %s   min_order_size %s"
              % (bb, ba, book.get("tick_size"), book.get("min_order_size")))
    return (errors == 0), token


# ---------------- minimal WebSocket client (RFC 6455) ----------------

def _open_tcp(host, port, timeout):
    """Direct TCP, or an HTTP CONNECT tunnel when HTTPS_PROXY is set (no proxy on a normal Mac)."""
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if proxy:
        p = urllib.parse.urlparse(proxy)
        s = socket.create_connection((p.hostname, p.port or 8080), timeout=timeout)
        s.sendall(("CONNECT %s:%d HTTP/1.1\r\nHost: %s:%d\r\n\r\n" % (host, port, host, port)).encode())
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = s.recv(4096)
            if not chunk:
                break
            resp += chunk
        status = resp.split(b"\r\n", 1)[0].decode("latin-1", "replace")
        if " 200" not in status:
            s.close()
            raise ConnectionError("proxy CONNECT refused: %s" % status)
        return s
    return socket.create_connection((host, port), timeout=timeout)


def _recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("socket closed")
        buf += chunk
    return buf


def _send_frame(sock, opcode, payload):
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    header = bytes([0x80 | opcode])
    n = len(payload)
    if n < 126:
        header += bytes([0x80 | n])
    elif n < 65536:
        header += bytes([0x80 | 126]) + struct.pack("!H", n)
    else:
        header += bytes([0x80 | 127]) + struct.pack("!Q", n)
    mask = os.urandom(4)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    sock.sendall(header + mask + masked)


def _recv_frame(sock):
    b1, b2 = _recv_exact(sock, 2)
    opcode = b1 & 0x0F
    n = b2 & 0x7F
    if n == 126:
        n = struct.unpack("!H", _recv_exact(sock, 2))[0]
    elif n == 127:
        n = struct.unpack("!Q", _recv_exact(sock, 8))[0]
    mask = _recv_exact(sock, 4) if b2 & 0x80 else None
    data = _recv_exact(sock, n) if n else b""
    if mask:
        data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    return opcode, data, bool(b1 & 0x80)


def ws_check(token):
    print("[3] WebSocket market channel wss://%s%s (%d s)" % (WS_HOST, WS_PATH, WS_SECONDS))
    if not token:
        print("    skipped: no token id (REST step failed)")
        return False
    try:
        raw = _open_tcp(WS_HOST, 443, TIMEOUT)
        sock = ssl.create_default_context().wrap_socket(raw, server_hostname=WS_HOST)
        key = base64.b64encode(os.urandom(16)).decode()
        req = ("GET %s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
               "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\nUser-Agent: %s\r\n"
               "Origin: https://polymarket.com\r\n\r\n") % (WS_PATH, WS_HOST, key, UA)
        t0 = time.perf_counter()
        sock.sendall(req.encode())
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = sock.recv(4096)
            if not chunk:
                raise ConnectionError("closed during handshake")
            resp += chunk
        head, rest = resp.split(b"\r\n\r\n", 1)
        status = head.split(b"\r\n", 1)[0].decode("latin-1", "replace")
        if " 101" not in status:
            raise ConnectionError("handshake refused: %s" % status)
        expect = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11")
                                               .encode()).digest()).decode()
        if expect.lower() not in head.decode("latin-1").lower():
            raise ConnectionError("bad Sec-WebSocket-Accept")
        print("    handshake ok in %.0f ms" % ((time.perf_counter() - t0) * 1000.0))
        if rest:
            raise ConnectionError("unexpected bytes after handshake")
        _send_frame(sock, 0x1, json.dumps({"assets_ids": [token], "type": "market"}))
        sock.settimeout(1.0)
        msgs = 0
        events = {}
        end = time.time() + WS_SECONDS
        next_ping = time.time() + 10
        frag = b""
        while time.time() < end:
            if time.time() >= next_ping:
                _send_frame(sock, 0x1, "PING")  # docs: client sends PING every 10 s
                next_ping = time.time() + 10
            try:
                op, data, fin = _recv_frame(sock)
            except socket.timeout:
                continue
            if op == 0x9:
                _send_frame(sock, 0xA, data)
                continue
            if op == 0x8:
                print("    server closed the connection")
                break
            if op in (0x1, 0x0):
                frag += data
                if not fin:
                    continue
                text, frag = frag.decode("utf-8", "replace"), b""
                if text.strip() == "PONG":
                    continue
                msgs += 1
                try:
                    obj = json.loads(text)
                    for o in (obj if isinstance(obj, list) else [obj]):
                        et = o.get("event_type", "?") if isinstance(o, dict) else "?"
                        events[et] = events.get(et, 0) + 1
                except ValueError:
                    events["non-json"] = events.get("non-json", 0) + 1
        try:
            _send_frame(sock, 0x8, struct.pack("!H", 1000))
            sock.close()
        except OSError:
            pass
        print("    messages in %d s: %d   by type: %s" % (WS_SECONDS, msgs, events or "-"))
        return msgs > 0
    except Exception as e:  # noqa: BLE001
        print("    FAILED: %s: %s" % (type(e).__name__, str(e)[:160]))
        return False


def main():
    print("Polymarket connection check  %s UTC" % time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()))
    blocked = geoblock()
    rest_ok, token = clob_latency()
    ws_ok = ws_check(token)
    print()
    if blocked is None or rest_ok is None:
        print("RESULT: UNREACHABLE (exit 3)")
        return 3
    if blocked:
        print("RESULT: BLOCKED - orders from this IP will be rejected (exit 2)")
        return 2
    if not ws_ok:
        print("RESULT: REST ok, not blocked, WebSocket FAILED (exit 4)")
        return 4
    print("RESULT: OK - not blocked, REST and WebSocket reachable (exit 0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
