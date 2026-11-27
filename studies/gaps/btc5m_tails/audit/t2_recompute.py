"""Audit recomputation of T2 from extract.py output (own code; no study functions).
Usage: python3 t2_recompute.py TAILS.parquet"""
import sys
import numpy as np, pandas as pd

OCT1, NOV1, FEECHG = 1790812800, 1793491200, 1795219140
df = pd.read_parquet(sys.argv[1]).sort_values(["t0", "i"])
df["month"] = np.where(df.t0 < OCT1, "Sep", np.where(df.t0 < NOV1, "Oct", "Nov"))

def ratio_t(net, stake):
    net, stake = np.asarray(net, float), np.asarray(stake, float)
    n = len(net); R = net.sum() / stake.sum()
    se = np.sqrt(((net - R * stake) ** 2).sum() * n / (n - 1)) / stake.sum()
    return R, R - 1.96 * se, R + 1.96 * se, R / se

def rule(d, cap, budget=25.0, rate_override=None):
    d = d[(d.e >= 225) & (d.e < 285) & (d.p <= cap)].copy()
    full = d.z * d.p
    used = full.groupby(d.t0).cumsum() - full
    d["stk"] = np.minimum(np.maximum(budget - used, 0), full)
    d = d[d.stk > 1e-9].copy()
    d["sh"] = d.stk / d.p
    rate = np.where(d.bt >= FEECHG, 0.05, 0.07) if rate_override is None else rate_override
    d["fee"] = d.sh * rate * d.p * (1 - d.p)
    d["net"] = d.sh * d.won - d.stk - d.fee
    return d

def report(d, label):
    out = []
    for per in ["Sep", "Oct", "Nov", "Sep+Oct", "All"]:
        x = d if per == "All" else d[d.month.isin(per.split("+"))]
        g = x.groupby("t0").agg(net=("net", "sum"), stk=("stk", "sum"), won=("won", "max"), fee=("fee", "sum"))
        R, lo, hi, t = ratio_t(g.net, g.stk)
        out.append(f"{label} {per:8s} mkts {len(g):5d} tickets {len(x):6d} stake {g.stk.sum():9.0f} won_mkts {int(g.won.sum()):4d} "
                   f"fees {g.fee.sum():7.0f} net {g.net.sum():+9.0f} RoS {100*R:+6.1f}% [{100*lo:+.0f},{100*hi:+.0f}] t {t:+.2f}")
    return out

if __name__ == "__main__":
    for name, cap in (("A", 0.02), ("B", 0.05)):
        d = rule(df, cap)
        print("\n".join(report(d, name)))
        g = d.groupby("t0").net.sum().sort_values()
        print(f"{name}: without best 3 markets net {g.iloc[:-3].sum():+.0f}; without best 10 {g.iloc[:-10].sum():+.0f}; top5 {g.iloc[-5:].round(0).tolist()}")
        gross = d.groupby("t0").agg(net=("net","sum"), fee=("fee","sum"), stk=("stk","sum"))
        R, lo, hi, t = ratio_t(gross.net + gross.fee, gross.stk)
        print(f"{name}: BEFORE fees RoS {100*R:+.1f}% t {t:+.2f}")
        # by day clusters
        d["day"] = (d.t0 // 86400)
        gd = d.groupby("day").agg(net=("net","sum"), stk=("stk","sum"))
        R, lo, hi, t = ratio_t(gd.net, gd.stk)
        print(f"{name}: clustered by DAY ({len(gd)} days) RoS {100*R:+.1f}% t {t:+.2f}; best day {gd.net.max():+.0f}; without best day net {gd.net.sum()-gd.net.max():+.0f}")
