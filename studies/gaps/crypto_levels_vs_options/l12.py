"""L1 (gap by cell, calibration) and L2 (persistence). Usage: l12.py euro|ot"""
import sys, math
import numpy as np, pandas as pd
from common import *
from pmlab.stats import ratio_cluster, mean_se
grp = sys.argv[1]
P = pd.read_parquet(DATA / f"panel_{grp}.parquet"); meta = pd.read_parquet(DATA / f"meta_{grp}.parquet")
P = P.dropna(subset=["S", "sig_a"]).merge(meta[["m", "yes_won", "cluster", "period", "asset", "freq"]], on="m")
P["y"] = P.yes_won.astype(float)
H = P[P.t % 3600 == 0].copy()
MB = [0, 0.1, 0.3, 0.7, 0.9, 1.0000001]; ML = ["0-0.1", "0.1-0.3", "0.3-0.7", "0.7-0.9", "0.9-1"]
TB = [0, 2 * 3600, 12 * 3600, 48 * 3600, 1e12]; TL = ["<2h", "2-12h", "12-48h", ">=48h"]
H["tb"] = pd.cut(H.tau, TB, labels=TL, right=False)
print(f"== group {grp}: markets {H.m.nunique()}, clusters {H.cluster.nunique()}, market-hours {len(H)}")

def clus(df, col):
    g = df.groupby("cluster")
    r, se, t = ratio_cluster(list(g[col].sum()), list(g[col].count()))
    return r, se, t

def enc(df, pcol):
    # (y - pm) = beta * (model - pm), cluster-robust
    x = (df[pcol] - df.pm).values; e = (df.y - df.pm).values
    sxx = (x * x).sum()
    if sxx == 0: return float("nan"), float("nan")
    b = (x * e).sum() / sxx
    u = pd.Series(x * (e - b * x)).groupby(df.cluster.values).sum().values
    n = len(u)
    se = math.sqrt(n / (n - 1) * (u * u).sum()) / sxx if n > 1 else float("nan")
    return b, se

def l1(H, pcol, label):
    H = H.dropna(subset=[pcol]).copy()
    H["gap"] = H.pm - H[pcol]; H["mb"] = pd.cut(H[pcol], MB, labels=ML, right=False)
    H["e_mod"] = H.y - H[pcol]; H["e_mkt"] = H.y - H.pm
    print(f"\n--- L1 [{label}] gap = market - model; cells model-prob x time-to-resolution")
    print("moneyness | tau | mkt-hrs | mkts | clus | mean gap | median | sd | IQR | mean|gap| | outcome | model | market | out-model (se) | out-market (se)")
    for mb in ML:
        for tb in TL:
            c = H[(H.mb == mb) & (H.tb == tb)]
            if len(c) == 0: continue
            g = c.gap
            em = clus(c, "e_mod"); ek = clus(c, "e_mkt")
            print(f"{mb} | {tb} | {len(c)} | {c.m.nunique()} | {c.cluster.nunique()} | {g.mean():+.4f} | {g.median():+.4f} | {g.std():.4f} | {g.quantile(.75)-g.quantile(.25):.4f} | {g.abs().mean():.4f} | {c.y.mean():.3f} | {c[pcol].mean():.3f} | {c.pm.mean():.3f} | {em[0]:+.4f} ({em[1]:.4f}) | {ek[0]:+.4f} ({ek[1]:.4f})")
    print("by time band: | tau | mkt-hrs | mean gap | sd gap | mean|gap| | share |gap|>=0.05 | Brier model | Brier market | diff (se, t; clustered) | beta enc (se)")
    for tb in TL + ["all"]:
        for act in ("all", "active(model .05-.95)"):
            c = H if tb == "all" else H[H.tb == tb]
            if act != "all": c = c[(c[pcol] >= .05) & (c[pcol] <= .95)]
            if len(c) == 0: continue
            c = c.assign(bd=(c.y - c[pcol]) ** 2 - (c.y - c.pm) ** 2)
            d = clus(c, "bd"); b = enc(c, pcol)
            print(f"{tb} | {act} | {len(c)} | {c.gap.mean():+.4f} | {c.gap.std():.4f} | {c.gap.abs().mean():.4f} | {(c.gap.abs()>=.05).mean():.3f} | {((c.y-c[pcol])**2).mean():.4f} | {((c.y-c.pm)**2).mean():.4f} | {d[0]:+.5f} ({d[1]:.5f}, t={d[2]:+.2f}) | {b[0]:+.3f} ({b[1]:.3f})")
    for per in ("tune", "report"):
        c = H[(H.period == per) & (H[pcol] >= .05) & (H[pcol] <= .95)]
        c = c.assign(bd=(c.y - c[pcol]) ** 2 - (c.y - c.pm) ** 2); d = clus(c, "bd"); b = enc(c, pcol)
        print(f"period {per} active: n {len(c)} mean gap {c.gap.mean():+.4f} sd {c.gap.std():.4f} mean|gap| {c.gap.abs().mean():.4f} share>=.05 {(c.gap.abs()>=.05).mean():.3f} Brier model {((c.y-c[pcol])**2).mean():.4f} market {((c.y-c.pm)**2).mean():.4f} diff {d[0]:+.5f} (t={d[2]:+.2f}) beta {b[0]:+.3f} ({b[1]:.3f})")
    for a in sorted(H.asset.unique()):
        c = H[(H.asset == a) & (H[pcol] >= .05) & (H[pcol] <= .95)]
        print(f"asset {a} active: n {len(c)} mean gap {c.gap.mean():+.4f} sd {c.gap.std():.4f} mean|gap| {c.gap.abs().mean():.4f}")

l1(H, "pa", "vol a = DVOL"); l1(H, "pb", "vol b = realised 24h")
print("\nvol levels on hourly obs: DVOL mean %.3f, RV24h mean %.3f, median ratio RV/DVOL %.3f" % (H.sig_a.mean(), H.sig_b.mean(), (H.sig_b / H.sig_a).median()))

# ---- L2
print("\n--- L2 persistence (vol a)")
H["gap"] = H.pm - H.pa
H = H.sort_values(["m", "t"])
key = H.set_index(["m", "t"])
def pair(lag):
    a = H[["m", "t", "gap", "pa", "pm"]].copy(); b = H[["m", "t", "gap", "pa", "pm"]].copy()
    b["t"] = b.t - lag * 3600
    return a.merge(b, on=["m", "t"], suffixes=("", "_f"))
mm = H[(H.pa >= .05) & (H.pa <= .95)].groupby("m").gap.mean()
for lag in (1, 4, 12):
    x = pair(lag); x = x[(x.pa >= .05) & (x.pa <= .95)]
    r = np.corrcoef(x.gap, x.gap_f)[0, 1]
    d = x.assign(g0=x.gap - x.m.map(mm), g1=x.gap_f - x.m.map(mm))
    r2 = np.corrcoef(d.g0, d.g1)[0, 1]
    print(f"autocorr lag {lag}h: raw {r:.3f}, within-market-demeaned {r2:.3f}, pairs {len(x)}")
sl = {}
for lag in (1, 2, 3, 4, 6, 8, 12, 24):
    x = pair(lag); x = x[(x.pa >= .05) & (x.pa <= .95) & (x.gap.abs() >= .05)]
    b = (x.gap * x.gap_f).sum() / (x.gap ** 2).sum(); sl[lag] = b
    print(f"decay slope lag {lag}h (|gap|>=0.05, active): b={b:.3f} pairs {len(x)} markets {x.m.nunique()}")
for lag in (1, 4):
    b = sl[lag]
    print(f"half-life from {lag}h slope: {lag*math.log(.5)/math.log(b):.1f} h" if 0 < b < 1 else f"half-life from {lag}h slope: undefined (b={b:.3f})")
first = [l for l in sorted(sl) if sl[l] < .5]; print("first lag with slope < 0.5:", first[0] if first else ">24h")
x = pair(4); x = x[(x.pa >= .05) & (x.pa <= .95) & (x.gap.abs() >= .05)]
s2 = (x.gap ** 2).sum()
print("who moves over next 4h: slope d(market) on gap = %.3f ; slope d(model) on gap = %.3f (pairs %d)" % ((x.gap * (x.pm_f - x.pm)).sum() / s2, (x.gap * (x.pa_f - x.pa)).sum() / s2, len(x)))
