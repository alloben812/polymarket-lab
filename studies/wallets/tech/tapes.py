"""Fetch and cache whole-market tapes for the resolved 'debut' and month-end ranking markets the accounts traded."""
import pickle, os, sys, collections
from concurrent.futures import ThreadPoolExecutor
from common import *
TD = f"{DATA}/tapes"; os.makedirs(TD, exist_ok=True)
def tape(cond):
    fp = f"{TD}/{cond}.pkl"
    if os.path.exists(fp): return pickle.load(open(fp, "rb"))
    rows = [(int(r["timestamp"]), float(r["price"]), float(r["size"]), r["outcome"], r["side"], (r.get("proxy_wallet") or r.get("user") or r.get("wallet") or "")) for r in dataapi.iter_trades(condition=cond, max_rows=40000)]
    rows.sort(); pickle.dump(rows, open(fp, "wb")); return rows
def wanted():
    want = collections.OrderedDict()
    for name in ACC:
        ms = [m for m in load(name)["_markets"] if m["tech"] and m["sub"] in ("arena", "hle") and m["resolved"] and m.get("closed_at")]
        ms.sort(key=lambda m: -m["turnover"])
        for m in ms[:150 if name != "0xAee8611B" else 80]: want[m["condition"]] = 1
    return list(want)
if __name__ == "__main__":
    w = wanted(); sys.stderr.write(f"{len(w)} tapes\n")
    with ThreadPoolExecutor(4) as ex: n = sum(len(t) for t in ex.map(tape, w))
    print(len(w), "markets", n, "rows")
