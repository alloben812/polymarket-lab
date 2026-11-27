"""Audit: T1 <=1.5c cells (hit, equal-weight break-even, exact binomial) and a hand check of T2 tickets.
Usage: python3 cells_and_handcheck.py TAILS.parquet"""
import sys, math
import numpy as np, pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from t2_recompute import rule, df, FEECHG
def bcdf(k, n, p):
    return sum(math.exp(math.lgamma(n+1)-math.lgamma(i+1)-math.lgamma(n-i+1)+i*math.log(p)+(n-i)*math.log(1-p)) for i in range(k+1))
df = df.copy(); df["fee"] = df.z * np.where(df.bt >= FEECHG, .05, .07) * df.p * (1 - df.p)
for name, a, b in (("75-45", 225, 255), ("45-15", 255, 285), ("15-0", 285, 300)):
    x = df[(df.e >= a) & (df.e < b) & (df.p <= 0.015)]
    u = x.groupby(["t0", "o"]).agg(won=("won", "first"), z=("z", "sum"), st=("p", lambda s: 0), fee=("fee", "sum"))
    u["stake"] = (x.z * x.p).groupby([x.t0, x.o]).sum()
    be = ((u.stake + u.fee) / u.z).mean(); k, n = int(u.won.sum()), len(u)
    print(f"<=1.5c {name}: {k}/{n} won = {100*k/n:.2f}%, break-even {100*be:.2f}%, exact P(X<={k}) = {bcdf(k, n, be):.2e}")
d = rule(df.drop(columns="fee"), 0.02)
w = d[d.won].groupby("t0").net.sum().sort_values().index[-1]
x = d[d.t0 == w].head(3)
for r in x.itertuples():
    rate = 0.05 if r.bt >= FEECHG else 0.07
    sh = r.stk / r.p; fee = sh * rate * r.p * (1 - r.p)
    print(f"t0 {r.t0} bt {r.bt} e {r.e} {r.o} p {r.p} print {r.z:.2f} sh, stake {r.stk:.4f} -> shares {sh:.2f}, fee {rate}*{r.p}*{1-r.p:.4f}*{sh:.2f} = {fee:.4f} (code {r.fee:.4f}), won {r.won}, net {sh*r.won - r.stk - fee:+.4f} (code {r.net:+.4f})")
g = d.groupby("t0").agg(net=("net", "sum"), won=("won", "max"))
print(f"mean net per losing market {g[~g.won].net.mean():.2f}, per winning market {g[g.won].net.mean():.2f}")
