"""L4 fill realism. Usage: l4.py euro pa sample|all"""
import sys, json, gzip, random, bisect
import numpy as np, pandas as pd
from common import *
from pmlab import dataapi
from pmlab.stats import wilson
import l3
LAG = 3
(DATA / "tape").mkdir(exist_ok=True)

def tape(cond):
    p = DATA / "tape" / f"{cond}.json.gz"
    if p.exists():
        return json.load(gzip.open(p, "rt"))
    rows = [(r["timestamp"], r["side"], r["outcome"], float(r["size"]), float(r["price"])) for r in dataapi.iter_trades(condition=cond)]
    rows.sort()
    with gzip.open(p, "wt") as f: json.dump(rows, f)
    return rows

def check(e, rows):
    """rows sorted by block time. Returns (confirmed, size_ok, n_prints_in_window, best_buyable_price)."""
    side = "Yes" if e.side == "YES" else "No"
    lo, hi = e.t + LAG, e.t + 600 + LAG  # match time in (t, t+600]  <=> block time in (t+3, t+603]
    ts_ = [r[0] for r in rows]
    i, j = bisect.bisect_right(ts_, lo), bisect.bisect_right(ts_, hi)
    size = 0.0; best = None; n = 0
    for bt, s, o, z, p in rows[i:j]:
        n += 1
        if s == "BUY" and o == side: bp = p
        elif s == "SELL" and o != side: bp = 1 - p
        else: continue
        best = bp if best is None else min(best, bp)
        if bp <= e.pe + 1e-9: size += z
    return size > 0, size >= e.shares, n, best

if __name__ == "__main__":
    grp, pcol, mode = sys.argv[1], sys.argv[2], sys.argv[3]
    E = pd.read_parquet(DATA / f"entries_{grp}_{pcol}.parquet")
    pool = E.drop_duplicates(["m", "t", "side"]).sort_values(["m", "t", "side"]).reset_index(drop=True)
    print(f"pool of distinct entries: {len(pool)} in {pool.m.nunique()} markets")
    rng = random.Random(20261127)
    pick = sorted(rng.sample(range(len(pool)), min(150, len(pool))))
    S = pool.iloc[pick].copy() if mode == "sample" else pool.copy()
    res = []
    for k, (_, e) in enumerate(S.iterrows()):
        rows = tape(e.cond)
        res.append(check(e, rows))
        if k % 100 == 0: print("..", k, file=sys.stderr)
    S["conf"] = [r[0] for r in res]; S["size_ok"] = [r[1] for r in res]; S["nprints"] = [r[2] for r in res]; S["best"] = [r[3] for r in res]
    S.to_parquet(DATA / f"l4_{grp}_{pcol}_{mode}.parquet")
    n = len(S); k = int(S.conf.sum()); lo, hi = wilson(k, n)
    print(f"[{mode}] checked {n} entries: confirmed {k} = {k/n:.3f} (Wilson 95% {lo:.3f}-{hi:.3f}); with size >= entry shares {int(S.size_ok.sum())} = {S.size_ok.mean():.3f}; any print at all in the 10 min: {(S.nprints>0).mean():.3f}")
    S["tb"] = pd.cut(S.tau_h, [2, 12, 48, 169], labels=["2-12h", "12-48h", "48h-7d"], right=False)
    print(S.groupby("tb", observed=True).agg(n=("conf", "size"), confirmed=("conf", "mean"), size_ok=("size_ok", "mean"), any_print=("nprints", lambda x: (x > 0).mean()), mean_abs_gap=("gap", lambda x: x.abs().mean())).round(3).to_string())
    S["hrs_since_open"] = 168 - S.tau_h
    print("confirmed share by |gap| bucket:"); S["gb"] = pd.cut(S.gap.abs(), [0.05, 0.08, 0.12, 0.2, 1.0], right=False)
    print(S.groupby("gb", observed=True).agg(n=("conf", "size"), confirmed=("conf", "mean")).round(3).to_string())
    key = S.set_index(["m", "t", "side"]).conf
    EE = E.join(key, on=["m", "t", "side"], how="inner")
    print("by variant (entries of that variant that were checked):")
    print(EE.groupby(["period", "g", "band"], observed=True).agg(checked=("conf", "size"), confirmed=("conf", "mean")).round(3).to_string())
    l3.table(EE[EE.conf], f"L3 on tape-confirmed entries only [{mode}]")
    l3.table(EE[~EE.conf], f"(for contrast) L3 on NOT confirmed entries [{mode}]")
