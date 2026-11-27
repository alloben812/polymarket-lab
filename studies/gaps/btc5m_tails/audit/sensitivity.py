"""Audit sensitivity: can a different, equally simple sizing hide a positive effect? (audit-only variants, counted in audit.md)
V1 first qualifying print per market, 5 shares (the minimum order) capped by print size.
V2 first qualifying print per market, $1 of stake capped by print size.
V3 every qualifying print, 5 shares each capped by print size, no budget (ticket-level equal weight).
Usage: python3 sensitivity.py TAILS.parquet [MARKETS.parquet]"""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from t2_recompute import ratio_t, FEECHG, OCT1, NOV1

df = pd.read_parquet(sys.argv[1]).sort_values(["t0", "i"])
df["month"] = np.where(df.t0 < OCT1, "Sep", np.where(df.t0 < NOV1, "Oct", "Nov"))

def money(d, sh):
    d = d.copy(); d["sh"] = sh; d["stk"] = d.sh * d.p
    d["fee"] = d.sh * np.where(d.bt >= FEECHG, 0.05, 0.07) * d.p * (1 - d.p)
    d["net"] = d.sh * d.won - d.stk - d.fee
    return d

def rep(d, label):
    for per in ["Sep", "Oct", "Nov", "All"]:
        x = d if per == "All" else d[d.month == per]
        g = x.groupby("t0").agg(net=("net", "sum"), stk=("stk", "sum"), won=("won", "max"), p=("p", "mean"))
        R, lo, hi, t = ratio_t(g.net, g.stk)
        print(f"{label:22s} {per:4s} mkts {len(g):5d} won {int(g.won.sum()):4d} ({100*g.won.mean():.2f}% vs avg px {100*g.p.mean():.2f}c) stake {g.stk.sum():8.1f} net {g.net.sum():+8.1f} RoS {100*R:+6.1f}% t {t:+.2f}")

for cap in (0.02, 0.05):
    q = df[(df.e >= 225) & (df.e < 285) & (df.p <= cap)]
    first = q.groupby("t0").head(1)
    rep(money(first, np.minimum(first.z, 5.0)), f"V1 first,5sh <={cap}")
    rep(money(first, np.minimum(first.z, 1.0 / first.p)), f"V2 first,$1 <={cap}")
    rep(money(q, np.minimum(q.z, 5.0)), f"V3 every,5sh <={cap}")
    # source split of the T2 rule
    for s in ("BUY", "SELL"):
        qs = q[q.s == s]
        f2 = qs.groupby("t0").head(1)
        rep(money(f2, np.minimum(f2.z, 5.0)), f"V1 src={s} <={cap}")
