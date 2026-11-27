"""Audit, independent of the study's code: read raw cached meta + tapes directly, write every tail print (price <= 0.10)
of every grid market to a parquet. Lag is a parameter so the block-delay sensitivity can be rerun.
Usage: python3 extract.py OUT.parquet [lag]"""
import gzip, json, os, sys
from multiprocessing import Pool
import pandas as pd

ROOT = "/home/user/polymarket-lab/data"
START, END = 1788220800, 1795737600
LAG = int(sys.argv[2]) if len(sys.argv) > 2 else 3

def one(t0):
    p = f"{ROOT}/updown_meta/btc/5m/{t0}.json"
    if not os.path.exists(p):
        return ("nometa", t0, [], None)
    m = json.load(open(p))
    if m.get("up_won") is None or not m.get("condition"):
        return ("unres", t0, [], None)
    tp = f"{ROOT}/tape/{m['condition']}.jsonl.gz"
    if not os.path.exists(tp):
        return ("notape", t0, [], None)
    out, n, sh = [], 0, 0.0
    with gzip.open(tp, "rt") as f:
        for i, line in enumerate(f):
            r = json.loads(line); n += 1; sh += float(r["z"])
            if r["s"] == "BUY":
                o, px = r["o"], float(r["p"])
            else:
                o, px = ("Down" if r["o"] == "Up" else "Up"), 1.0 - float(r["p"])
            px = round(px, 6); z = float(r["z"])
            if not (z > 0 and 0 < px <= 0.10):
                continue
            won = (o == "Up") == bool(m["up_won"])
            out.append((t0, i, int(r["t"]), int(r["t"]) - LAG - t0, o, px, z, r["s"], won))
    if n == 0:
        return ("empty", t0, [], None)
    return ("ok", t0, out, (t0, n, sh, m.get("volume"), bool(m["up_won"])))

if __name__ == "__main__":
    grid = list(range(START, END, 1200))
    with Pool(4) as pool:
        res = pool.map(one, grid, chunksize=50)
    from collections import Counter
    print(len(grid), Counter(r[0] for r in res))
    rows = [x for r in res for x in r[2]]
    df = pd.DataFrame(rows, columns=["t0", "i", "bt", "e", "o", "p", "z", "s", "won"])
    df.to_parquet(sys.argv[1], index=False)
    mk = pd.DataFrame([r[3] for r in res if r[3]], columns=["t0", "rows", "shares", "volume", "up_won"])
    mk.to_parquet(sys.argv[1].replace(".parquet", "_markets.parquet"), index=False)
    print("tail prints", len(df), "markets", len(mk))
