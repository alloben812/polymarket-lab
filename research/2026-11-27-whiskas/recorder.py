#!/usr/bin/env python3
"""REST recorder for the live BTC 5-minute Up/Down market on Polymarket.

Polls POST /books (~4 Hz) for the current window's two outcome tokens and appends one JSON line per poll:
  {"lt": local_recv_time, "rt": request_roundtrip_s, "t0": window_start, "ts": server_book_ts_ms,
   "ub": [[price,size]...top N Up bids], "ua": [[price,size]...top N Up asks], "db": ..., "da": ...}
Read-only, public endpoints only. No orders are ever sent.
"""
import json, sys, time, threading, argparse
import requests

CLOB = "https://clob.polymarket.com"; GAMMA = "https://gamma-api.polymarket.com"
CA = "/root/.ccr/ca-bundle.crt"

def top(levels, n, reverse):
    lv = sorted(((float(x["price"]), float(x["size"])) for x in levels), key=lambda x: x[0], reverse=reverse)
    return [[p, s] for p, s in lv[:n]]

def tokens_for(sess, t0, slug_prefix):
    for _ in range(6):
        try:
            r = sess.get(f"{GAMMA}/markets", params={"slug": f"{slug_prefix}-{t0}"}, timeout=10)
            d = r.json()
            if d:
                ids = json.loads(d[0]["clobTokenIds"]); outs = json.loads(d[0]["outcomes"])
                m = dict(zip(outs, ids))
                return m["Up"], m["Down"], d[0]["conditionId"]
        except Exception as e:
            sys.stderr.write(f"gamma err {e}\n")
        time.sleep(1)
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True); ap.add_argument("--minutes", type=float, default=40)
    ap.add_argument("--hz", type=float, default=4.0); ap.add_argument("--depth", type=int, default=6)
    ap.add_argument("--slug", default="btc-updown-5m")
    a = ap.parse_args()
    sess = requests.Session(); sess.verify = CA; sess.headers.update({"User-Agent": "Mozilla/5.0"})
    cache = {}; lock = threading.Lock()
    def ensure(t0):
        with lock:
            if t0 in cache: return cache[t0]
        v = tokens_for(requests.Session() if False else sess, t0, a.slug)
        with lock: cache[t0] = v
        return v
    end = time.time() + a.minutes * 60; period = 1.0 / a.hz; n = 0; errs = 0
    meta = open(a.out + ".meta", "a")
    with open(a.out, "a", buffering=1) as f:
        nxt = time.time()
        while time.time() < end:
            now = time.time(); t0 = int(now // 300 * 300)
            tk = ensure(t0)
            if (now - t0) > 270 and (t0 + 300) not in cache:   # pre-fetch the next window's tokens
                threading.Thread(target=ensure, args=(t0 + 300,), daemon=True).start()
            if tk:
                up, dn, cond = tk
                if n == 0 or t0 != last_t0:
                    meta.write(json.dumps({"t0": t0, "up": up, "down": dn, "condition": cond}) + "\n"); meta.flush()
                last_t0 = t0
                try:
                    s = time.time()
                    r = sess.post(f"{CLOB}/books", json=[{"token_id": up}, {"token_id": dn}], timeout=5)
                    e = time.time(); bs = r.json()
                    by = {b["asset_id"]: b for b in bs}
                    bu, bd = by.get(up), by.get(dn)
                    if bu and bd:
                        f.write(json.dumps({"lt": round(e, 3), "rt": round(e - s, 3), "t0": t0, "ts": int(bu["timestamp"]),
                                            "ub": top(bu["bids"], a.depth, True), "ua": top(bu["asks"], a.depth, False),
                                            "db": top(bd["bids"], a.depth, True), "da": top(bd["asks"], a.depth, False),
                                            "ltp": bu.get("last_trade_price"), "tick": bu.get("tick_size")}) + "\n")
                        n += 1
                except Exception as ex:
                    errs += 1
                    if errs % 20 == 1: sys.stderr.write(f"poll err {ex}\n")
            nxt += period
            sl = nxt - time.time()
            if sl > 0: time.sleep(sl)
            else: nxt = time.time()
    print(f"done: {n} snapshots, {errs} errors")

if __name__ == "__main__":
    main()
