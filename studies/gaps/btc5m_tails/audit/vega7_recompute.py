"""Audit: Vega7 net after fees and its hit rate in the <=1.5c cells vs the baseline, from raw fills + raw meta + extract.py output.
Usage: python3 vega7_recompute.py TAILS.parquet"""
import json, os, sys, math
import numpy as np, pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from t2_recompute import ratio_t, FEECHG, OCT1, NOV1
D = "/home/user/polymarket-lab/data"
f = pd.DataFrame(json.load(open(f"{D}/gaps_btc5m_tails/vega7_fills.json")))
f["t0"] = f.slug.str.rsplit("-", n=1).str[1].astype(int)
f = f[(f.t0 >= 1788220800) & (f.t0 < 1795737600) & (f.side == "BUY")]
up = {}
for t0 in f.t0.unique():
    p = f"{D}/updown_meta/btc/5m/{t0}.json"   # raw cache, not the study's vega7_meta.json
    m = json.load(open(p)) if os.path.exists(p) else None
    if m and m.get("up_won") is not None:
        up[t0] = bool(m["up_won"])
print("fills", len(f), "windows", f.t0.nunique(), "with raw meta", len(up))
f = f[f.t0.isin(up)].copy()
f["won"] = [(o == "Up") == up[t] for o, t in zip(f.outcome, f.t0)]
f["e"] = f.timestamp - 3 - f.t0
f["stk"] = f["size"] * f.price
f["fee"] = f["size"] * np.where(f.timestamp >= FEECHG, 0.05, 0.07) * f.price * (1 - f.price)
f["net"] = f["size"] * f.won - f.stk - f.fee
g = f.groupby("t0").agg(net=("net", "sum"), stk=("stk", "sum"), sh=("size", "sum"))
R, lo, hi, t = ratio_t(g.net, g.sh)
print(f"Vega7 all: markets {len(g)} stake {g.stk.sum():.0f} net {g.net.sum():+.0f} net/share {100*R:+.2f}c t {t:+.2f}")
f["month"] = np.where(f.t0 < OCT1, "Sep", np.where(f.t0 < NOV1, "Oct", "Nov"))
print(f.groupby("month").net.sum().round(0).to_dict())
gs = g.sort_values("net")
print("without best 10 markets:", round(gs.net.iloc[:-10].sum()), " best 10 sum", round(gs.net.iloc[-10:].sum()))
# the 1.5c cells
tl = pd.read_parquet(sys.argv[1])
def wilson(k, n, z=1.96):
    p = k / n; c = (p + z*z/(2*n)) / (1 + z*z/n); h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / (1 + z*z/n); return c-h, c+h
for name, lo_e, hi_e, plo, phi in (("<=1.5c 75-45", 225, 255, 0, 0.015), ("<=1.5c 45-15", 255, 285, 0, 0.015), ("<=5c 225-285", 225, 285, 0, 0.05)):
    b = tl[(tl.e >= lo_e) & (tl.e < hi_e) & (tl.p > plo) & (tl.p <= phi)].groupby(["t0", "o"]).won.first()
    v = f[(f.e >= lo_e) & (f.e < hi_e) & (f.price > plo) & (f.price <= phi + 1e-9)].groupby(["t0", "outcome"]).won.first()
    vg = v[[t % 1200 == 0 for t, _ in v.index]]
    p1, p2 = v.mean(), b.mean(); pp = (v.sum() + b.sum()) / (len(v) + len(b))
    z = (p1 - p2) / math.sqrt(pp * (1 - pp) * (1/len(v) + 1/len(b)))
    print(f"{name}: Vega7 {int(v.sum())}/{len(v)} = {100*p1:.2f}% {tuple(round(100*x,2) for x in wilson(v.sum(), len(v)))}; grid-only {int(vg.sum())}/{len(vg)}; "
          f"baseline {int(b.sum())}/{len(b)} = {100*p2:.2f}% ; z {z:+.1f}")
