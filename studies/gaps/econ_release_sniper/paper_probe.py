"""Forward PAPER test (read-only, public GETs only, no orders, no keys).

Run on the machine whose latency you want to know (ideally the AWS eu-west-1 box), started ~2 minutes before T:
  python3 -I paper_probe.py --T "2026-12-04 13:30:00" --event november-unemployment-rate-2026 \
      --src "https://www.bls.gov/news.release/empsit.nr0.htm" --out /path/probe_empsit.jsonl
What it does:
  1. From T-10 s to T+30 s polls each --src URL every --every seconds (default 0.25) with a cache-busting query
     string and records local receive time, HTTP status, length and a hash of the body: the first change after T
     is OUR detection time (the number is in the page from then on; parse it offline from the saved body).
  2. From T-30 s to T+60 s polls the CLOB books of every open market of --event once per second (POST /books).
  3. Writes one JSON line per observation. Afterwards: compare our detection time with the first stale print on
     the tape (data-api trades?condition=..., block time - 3 s) using measure.py-style code.
Request volume: ~4 req/s per source for 40 s (~160) and 1 req/s to the CLOB for 90 s. Keep to one or two sources.
Never point it at the BLS API (25 requests/day without a key, 500 with a v2 key).
"""
import argparse, calendar, hashlib, json, random, threading, time, urllib.request

UA = "Mozilla/5.0 (research; release-timing paper test)"


def now():
    return time.time()


def get(url, data=None, timeout=5):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, "Accept": "*/*",
                                                          **({"Content-Type": "application/json"} if data else {})})
    t0 = now()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(); code = r.status
            hdr = {k.lower(): v for k, v in r.headers.items() if k.lower() in ("age", "last-modified", "etag", "cf-cache-status", "x-cache")}
    except urllib.error.HTTPError as e:
        body, code, hdr = b"", e.code, {}
    except Exception as e:  # noqa
        body, code, hdr = b"", str(e)[:60], {}
    return t0, now(), code, body, hdr


def poll_source(url, T, every, out, lock, save_dir):
    last = None
    while now() < T + 30:
        if now() < T - 10:
            time.sleep(0.05); continue
        u = url + ("&" if "?" in url else "?") + "_=%d" % random.randrange(10**9)
        t0, t1, code, body, hdr = get(u)
        h = hashlib.sha1(body).hexdigest()[:12]
        rec = {"k": "src", "url": url, "sent": round(t0 - T, 3), "recv": round(t1 - T, 3), "code": code, "len": len(body), "h": h, "hdr": hdr}
        if h != last and body:
            rec["changed"] = True
            if save_dir:
                open(f"{save_dir}/body_{h}.html", "wb").write(body)
        last = h
        with lock:
            out.write(json.dumps(rec) + "\n"); out.flush()
        time.sleep(max(0.0, every - (now() - t0)))


def poll_books(event, T, out, lock):
    es = json.loads(get("https://gamma-api.polymarket.com/events?slug=" + event)[3] or b"[]")
    toks = []
    for m in (es[0]["markets"] if es else []):
        if not m.get("closed"):
            for i, t in enumerate(json.loads(m.get("clobTokenIds") or "[]")):
                toks.append({"token_id": t})
    while now() < T + 60:
        if now() < T - 30:
            time.sleep(0.2); continue
        t0 = now()
        for k in range(0, len(toks), 20):
            _, t1, code, body, _ = get("https://clob.polymarket.com/books", json.dumps(toks[k:k + 20]).encode())
            try:
                books = json.loads(body)
            except Exception:
                books = []
            for b in books:
                asks = sorted((float(a["price"]), float(a["size"])) for a in b.get("asks", []))[:5]
                bids = sorted(((float(a["price"]), float(a["size"])) for a in b.get("bids", [])), reverse=True)[:5]
                with lock:
                    out.write(json.dumps({"k": "book", "t": round(t1 - T, 3), "tok": b["asset_id"][-10:], "ts": b.get("timestamp"),
                                          "asks": asks, "bids": bids}) + "\n")
        time.sleep(max(0.0, 1.0 - (now() - t0)))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--T", required=True, help="scheduled UTC time 'YYYY-MM-DD HH:MM:SS'")
    ap.add_argument("--event", required=True)
    ap.add_argument("--src", action="append", default=[])
    ap.add_argument("--every", type=float, default=0.25)
    ap.add_argument("--out", required=True)
    ap.add_argument("--save-dir", default="")
    a = ap.parse_args()
    T = calendar.timegm(time.strptime(a.T, "%Y-%m-%d %H:%M:%S"))
    lock = threading.Lock()
    with open(a.out, "a") as out:
        th = [threading.Thread(target=poll_source, args=(u, T, a.every, out, lock, a.save_dir)) for u in a.src]
        th.append(threading.Thread(target=poll_books, args=(a.event, T, out, lock)))
        for t in th:
            t.start()
        for t in th:
            t.join()
