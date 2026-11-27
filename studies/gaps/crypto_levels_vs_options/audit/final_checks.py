import json, math, random
import numpy as np, pandas as pd
from pathlib import Path
from statistics import NormalDist
N = NormalDist().cdf
D = Path("/home/user/polymarket-lab/data/gaps_levels"); YEAR = 365 * 86400.0
# 1. the 150-entry protocol sample, re-drawn from my own entry list
uni = [u for u in json.load(open(D / "universe.json")) if u["grp"] == "euro"]; mi = {u["cond"]: i for i, u in enumerate(uni)}
E = pd.read_parquet("my_entries.parquet"); E["m"] = E.cond.map(mi)
pool = E.drop_duplicates(["m", "t", "side"]).sort_values(["m", "t", "side"]).reset_index(drop=True)
pick = sorted(random.Random(20261127).sample(range(len(pool)), 150)); S = pool.iloc[pick]
print("150-sample: confirmed", int(S.conf_w0.sum()), "full size", int((S.size_w0 >= S.shares - 1e-9).sum()), "| by band:", S.assign(b=pd.cut(S.tau_h, [2, 12, 48, 169], right=False)).groupby("b", observed=True).conf_w0.agg(["size", "mean"]).round(2).to_dict("index"))
print("all distinct: confirmed", int(pool.conf_w0.sum()), "of", len(pool), "| with prints after the entry-price bucket (t+300,t+900]:", int(pool.conf_w300.sum()), "| (t+300,t+600]:", int(pool.conf_w300s.sum()))
tv = pool[(pool.tau_h >= 48)]
print("48h-7d distinct entries:", len(tv), "confirmed w0", int(tv.conf_w0.sum()), "w300", int(tv.conf_w300.sum()), "w300s", int(tv.conf_w300s.sum()))
# 2. Deribit (c): forward basis. Recompute model with S lowered by the Binance-USD basis; IV by call/put
T = pd.read_parquet(D / "deribit_c.parquet"); Sp = pd.read_parquet(D / "deribit_c_spreads.parquet")
dv = np.load(D / "dvol_BTC.npy"); de = dv[:, 0].astype("int64") + 3600
def sig_at(t):
    j = np.searchsorted(de, t, side="right") - 1; return dv[j, 1] / 100
def pab(S, K, sig, tau):
    v = sig * sig * tau / YEAR; return N((math.log(S / K) - v / 2) / math.sqrt(v))
def bc(S, K, sig, ty):
    v = sig * math.sqrt(ty); d1 = (math.log(S / K) + v * v / 2) / v; return S * N(d1) - K * N(d1 - v)
def iv(price, S, K, ty, call):
    if not call: price = price + S - K
    if price <= max(S - K, 0) + 1e-9 or price >= S: return float("nan")
    lo, hi = 0.01, 5.0
    for _ in range(50):
        mid = (lo + hi) / 2
        if bc(S, K, mid, ty) < price: lo = mid
        else: hi = mid
    return (lo + hi) / 2
T["tau"] = T.exp - T.t
A = T[(np.abs(np.log(T.K / T.S)) <= 0.015) & (T.tau >= 2 * 3600) & (T.tau <= 24 * 3600)].copy(); A["sig"] = [sig_at(t) for t in A.t]
for basis in (0, 51, 73):
    A["iv"] = [iv(r.px_btc * r.S, r.S - basis, r.K, r.tau / YEAR, r.cp == "C") for r in A.itertuples()]
    X = A.dropna(subset=["iv"]); r = X.iv / X.sig
    print(f"basis ${basis}: ATM IV/DVOL median all {r.median():.3f} (n {len(X)}); calls {r[X.cp=='C'].median():.3f} (n {(X.cp=='C').sum()}); puts {r[X.cp=='P'].median():.3f} (n {(X.cp=='P').sum()})")
Sp["sig"] = [sig_at(int(t)) for t in Sp.t]; Sp["mb"] = pd.cut(Sp.pa, [0, 0.1, 0.3, 0.7, 0.9, 1.0000001], labels=["0-0.1", "0.1-0.3", "0.3-0.7", "0.7-0.9", "0.9-1"], right=False)
for basis in (0, 51, 73):
    pa = np.array([pab(r.S - basis, r.Km, r.sig, r.tau_h * 3600) for r in Sp.itertuples()])
    d = pd.Series(pa - Sp.dig.values); print(f"basis ${basis}: model - option digital by model bucket:", d.groupby(Sp.mb.values, observed=True).mean().round(3).to_dict(), "| overall", round(d.mean(), 4), "| check vs analyst pa max diff" if basis == 0 else "", round(float(np.abs(pa - Sp.pa.values).max()), 6) if basis == 0 else "")
# clustered se of the 0.3-0.7 bucket difference by expiry
x = Sp[Sp.mb == "0.3-0.7"].assign(d=lambda z: z.pa - z.dig).groupby("exp_code").d.mean(); print("0.3-0.7 bucket, per-expiry mean differences:", x.round(3).to_dict(), "mean", round(x.mean(), 3), "se", round(x.std(ddof=1) / math.sqrt(len(x)), 3))
# 3. BTC path around the report entries
k = np.load(D / "BTCUSDT_1m.npy"); c = dict(zip(k[:, 0].astype("int64").tolist(), k[:, 4].tolist()))
import calendar, time
for dstr in ("2026-11-09", "2026-11-12", "2026-11-13", "2026-11-15", "2026-11-16", "2026-11-17", "2026-11-20", "2026-11-23", "2026-11-26"):
    t = calendar.timegm(time.strptime(dstr + " 17:00", "%Y-%m-%d %H:%M")); print(dstr, "17:00 UTC BTC", c[t - 60], end=" | ")
print()
