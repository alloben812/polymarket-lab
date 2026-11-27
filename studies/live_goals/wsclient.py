"""Minimal RFC 6455 WebSocket client (standard library only), through the HTTPS proxy when one is set.

Adapted from pilot/conn_check.py (the handshake that worked from this sandbox on 2026-11-27).
Text frames only; handles ping/pong control frames and fragmented messages.
"""
from __future__ import annotations

import base64
import hashlib
import os
import socket
import ssl
import struct
import urllib.parse

UA = "Mozilla/5.0 (polymarket-lab research)"


def _open_tcp(host: str, port: int, timeout: float) -> socket.socket:
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if proxy:
        p = urllib.parse.urlparse(proxy)
        s = socket.create_connection((p.hostname, p.port or 8080), timeout=timeout)
        hdr = "CONNECT %s:%d HTTP/1.1\r\nHost: %s:%d\r\n" % (host, port, host, port)
        if p.username:
            cred = base64.b64encode(("%s:%s" % (urllib.parse.unquote(p.username),
                                                urllib.parse.unquote(p.password or ""))).encode()).decode()
            hdr += "Proxy-Authorization: Basic %s\r\n" % cred
        s.sendall((hdr + "\r\n").encode())
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


class WS:
    def __init__(self, url: str, timeout: float = 15.0, origin: str = "https://polymarket.com"):
        u = urllib.parse.urlparse(url)
        self.host, self.path = u.hostname, (u.path or "/") + (("?" + u.query) if u.query else "")
        raw = _open_tcp(self.host, u.port or 443, timeout)
        ctx = ssl.create_default_context()
        ca = "/root/.ccr/ca-bundle.crt"
        if os.path.exists(ca) and (os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")):
            ctx.load_verify_locations(ca)
        self.sock = ctx.wrap_socket(raw, server_hostname=self.host)
        key = base64.b64encode(os.urandom(16)).decode()
        req = ("GET %s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
               "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\nUser-Agent: %s\r\n"
               "Origin: %s\r\n\r\n") % (self.path, self.host, key, UA, origin)
        self.sock.sendall(req.encode())
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = self.sock.recv(4096)
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
        self.buf = rest
        self.frag = b""

    def _recv_exact(self, n: int) -> bytes:
        while len(self.buf) < n:
            chunk = self.sock.recv(max(65536, n - len(self.buf)))
            if not chunk:
                raise ConnectionError("socket closed")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def _parse(self):
        b = self.buf
        if len(b) < 2:
            return None
        b1, b2 = b[0], b[1]
        n = b2 & 0x7F
        i = 2
        if n == 126:
            if len(b) < 4:
                return None
            n = struct.unpack("!H", b[2:4])[0]
            i = 4
        elif n == 127:
            if len(b) < 10:
                return None
            n = struct.unpack("!Q", b[2:10])[0]
            i = 10
        mask = None
        if b2 & 0x80:
            if len(b) < i + 4:
                return None
            mask = b[i:i + 4]
            i += 4
        if len(b) < i + n:
            return None
        data = b[i:i + n]
        self.buf = b[i + n:]
        return b1, b1 & 0x0F, mask, data

    def send(self, payload, opcode: int = 0x1) -> None:
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
        self.sock.sendall(header + mask + masked)

    def settimeout(self, t: float) -> None:
        self.sock.settimeout(t)

    def recv(self):
        """Return a complete text message (str), or None for a control frame handled here.

        Raises socket.timeout when nothing arrives within the socket timeout, ConnectionError on close.
        """
        while True:
            fr = self._parse()
            if fr is not None:
                break
            chunk = self.sock.recv(262144)  # may raise socket.timeout; the buffer stays intact
            if not chunk:
                raise ConnectionError("socket closed")
            self.buf += chunk
        b1, opcode, mask, data = fr
        if mask:
            data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        if opcode == 0x9:
            self.send(data, 0xA)
            return None
        if opcode == 0xA:
            return None
        if opcode == 0x8:
            raise ConnectionError("server closed: %r" % data[:60])
        if opcode in (0x1, 0x2, 0x0):
            self.frag += data
            if not (b1 & 0x80):
                return None
            text, self.frag = self.frag.decode("utf-8", "replace"), b""
            return text
        return None

    def close(self) -> None:
        try:
            self.send(struct.pack("!H", 1000), 0x8)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass
