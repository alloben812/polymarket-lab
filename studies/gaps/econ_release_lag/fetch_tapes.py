"""Step 3: whole-market tapes, newest first, stop after crossing T - 2 h (protocol 3.3). Sequential, cached."""
import gzip, json, os, sys, time
from pmlab import dataapi

D = "/home/user/polymarket-lab/data/gaps_econ"
os.makedirs(f"{D}/tapes", exist_ok=True)
mk = json.load(open(f"{D}/markets.json"))["markets"]
only = sys.argv[1] if len(sys.argv) > 1 else None
CAP = 600_000
t0 = time.time(); tot = 0
for i, m in enumerate(sorted(mk, key=lambda m: m["vol"])):
    if only and m["release"] != only:
        continue
    path = f"{D}/tapes/{m['cond']}.json.gz"
    if os.path.exists(path):
        continue
    stop_ts = m["T"] - 7203
    rows, crossed, n, status = [], False, 0, "complete"
    for r in dataapi.iter_trades(condition=m["cond"]):
        rows.append([r["timestamp"], r["side"], r.get("outcome_index"), r.get("outcome"), float(r["price"]), float(r["size"]), r.get("proxy_wallet")])
        n += 1
        if r["timestamp"] < stop_ts:
            crossed = True
        if crossed and n % 1000 == 0:
            status = "stopped after crossing T-2h"; break
        if n >= CAP:
            status = "cap"; break
    tmp = path + ".tmp"
    with gzip.open(tmp, "wt") as f:
        json.dump({"cond": m["cond"], "status": status, "crossed": crossed, "n": n, "rows": rows}, f)
    os.replace(tmp, path)
    tot += n
    print(f"{i:3d} {m['release']:<18} vol={m['vol']:>12.0f} n={n:>7d} {status} {m['slug'][:50]}", flush=True)
print("rows", tot, "seconds", round(time.time() - t0))
