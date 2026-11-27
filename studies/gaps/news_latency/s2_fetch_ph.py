"""Step 2a: cache prices-history of the YES token for every universe market (1800 s, 300 s, 60 s where served)."""
import gzip, json, sys, time
from pmlab import dataapi
from common import *

CH = 15 * 86400

def fetch(tok, a, b, bucket):
    rows = []
    t = a
    while t < b:
        e = min(t + CH, b)
        for r in dataapi.prices_history(tok, t, e, bucket):
            if r.get("resolution_seconds"):
                rows.append((r["timestamp"], r["price"]))
        t = e
    return sorted(set(rows))

def main():
    u = universe()
    u.sort(key=lambda m: m["conditionId"])
    t_start = time.time()
    for i, m in enumerate(u):
        path = PH / f"{m['conditionId']}.json.gz"
        if path.exists():
            continue
        yes = tokens(m)[0]
        start = parse_time(m.get("startDate") or m.get("createdAt")) or FETCH0
        end = parse_time(m.get("closedTime")) if m.get("closed") else FETCH1
        a, b = max(FETCH0, start - 3600), min(FETCH1, (end or FETCH1) + 3 * 3600)
        out = {"c": m["conditionId"], "a": a, "b": b, "p1800": [], "p300": [], "p60": []}
        try:
            # 1800 s: 31 Aug .. 27 Sep 02:00 (2 calls); 300 s: 27 Sep .. 26 Nov 00:00 (4 calls);
            # 60 s: 20 Nov .. 26 Nov 12:00 (1 call, one page) - also gives the 2-hour point for the last jumps.
            if a < ERA300 + 7200:
                out["p1800"] = fetch(yes, a, min(b, ERA300 + 7200), 1800)
            if b > ERA300:
                out["p300"] = fetch(yes, max(a, ERA300), min(b, W1), 300)
            if b > S60:
                out["p60"] = fetch(yes, max(a, S60), min(b, W1 + 12 * 3600), 60)
        except Exception as e:  # noqa: BLE001
            print("ERR", m["slug"], str(e)[:200], file=sys.stderr, flush=True)
            continue
        tmp = path.with_suffix(".tmp")
        with gzip.open(tmp, "wt") as f:
            json.dump(out, f)
        tmp.replace(path)
        if i % 100 == 0:
            print(i, len(u), round(time.time() - t_start), file=sys.stderr, flush=True)
    print("done")

if __name__ == "__main__":
    main()
