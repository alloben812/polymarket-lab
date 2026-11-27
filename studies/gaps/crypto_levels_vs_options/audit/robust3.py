import json, gzip, math, glob, time
import numpy as np, pandas as pd
from pathlib import Path
D = Path("/home/user/polymarket-lab/data/gaps_levels")
E = pd.read_parquet("my_entries.parquet"); E["stake"] = 20.0
B = pd.read_parquet("placebo.parquet"); B["ret"] = B.pnl / 20
def rc(num, den):
    n = len(num); ds = den.sum(); r = num.sum() / ds
    res = num - r * den; se = math.sqrt(n / (n - 1) * (res ** 2).sum()) / ds
    return r, se, r / se
tv = E[(E.g == 0.05) & (E.band == "48h-7d") & E.conf_w0].copy()
print("== excess of the signal over blind same-side buying (48h-7d band, same tape rule) ==")
bm = B.groupby(["cond", "side"]).ret.mean().rename("r_mkt"); bc = B.groupby(["cluster", "side"]).ret.mean().rename("r_clu"); bp = B.groupby(["period", "side"]).ret.mean().rename("r_per")
tv = tv.join(bm, on=["cond", "side"]).join(bc, on=["cluster", "side"]).join(bp, on=["period", "side"])
for per in ("tune", "report"):
    X = tv[tv.period == per]
    for col, lab in (("r_mkt", "same market+side, random confirmable time"), ("r_clu", "same date ladder+side"), ("r_per", "same period+side")):
        Y = X.dropna(subset=[col]); ex = Y.pnl - 20 * Y[col]
        c = pd.DataFrame({"c": Y.cluster, "e": ex}).groupby("c").e.sum(); m = c.mean(); se = c.std(ddof=1) / math.sqrt(len(c))
        print(f"{per}: benchmark = blind {lab}: n {len(Y)} signal pnl {Y.pnl.sum():+.1f} benchmark pnl {20*Y[col].sum():+.1f} excess {ex.sum():+.1f} (t {m/se:+.2f}, {len(c)} clusters)")
# side-neutral blind portfolio
for per in ("tune", "report"):
    X = B[(B.period == per)]; print(per, "blind both sides, all confirmable entries: n", len(X), "ret on stake %.3f" % (X.pnl.sum() / X.stake.sum()), "| NO share of signal entries: %.2f" % (tv[tv.period == per].side == "NO").mean())
# L1 / L2 reproduction from my own hourly panel
H = pd.read_parquet("my_hourly.parquet"); A = H[(H.pf >= 0.05) & (H.pf <= 0.95)]
print("\n== L1 (my panel) == market-hours all", len(H), "active", len(A), "mean gap %.4f sd %.4f mean abs %.4f share>=0.05 %.3f" % (A.gap.mean(), A.gap.std(), A.gap.abs().mean(), (A.gap.abs() >= 0.05).mean()))
for lab, lo, hi in (("<2h", 0, 2), ("2-12h", 2, 12), ("12-48h", 12, 48), (">=48h", 48, 1e9)):
    X = A[(A.tau / 3600 >= lo) & (A.tau / 3600 < hi)]; print(f"  {lab}: n {len(X)} mean {X.gap.mean():+.4f} sd {X.gap.std():.3f} mean abs {X.gap.abs().mean():.3f} share>=0.05 {(X.gap.abs() >= 0.05).mean():.2f}")
Hi = H.set_index(["cond", "t"]).gap
for lag in (1, 4, 12):
    nxt = Hi.reindex(list(zip(A.cond, A.t + lag * 3600))).values; ok = ~np.isnan(nxt)
    big = ok & (A.gap.abs().values >= 0.05)
    print(f"  L2 lag {lag}h: autocorr {np.corrcoef(A.gap.values[ok], nxt[ok])[0,1]:.3f} ; decay slope for |gap|>=0.05: {(A.gap.values[big]*nxt[big]).sum()/(A.gap.values[big]**2).sum():.3f}")
# what creates the big gaps: age of the market
A2 = A.assign(age_h=168 - A.tau / 3600); big = A2[A2.gap.abs() >= 0.05]
print("  share of |gap|>=0.05 market-hours in the first 24 h of a market's life: %.2f ; in first 72 h: %.2f" % ((big.age_h < 24).mean(), (big.age_h < 72).mean()))
# bucket label vs spot (1-minute series saved by live2.py)
print("\n== label alignment of prices-history against Binance 1m (three near-the-money report markets) ==")
k = np.load(D / "BTCUSDT_1m.npy"); close_at = dict(zip((k[:, 0].astype("int64") + 60).tolist(), k[:, 4].tolist()))  # close known at candle end
for f in sorted(glob.glob("align_*.json")):
    d = json.load(open(f)); p1 = {int(a): b for a, b in d["p1"].items()}; ts_ = sorted(p1)
    dp = np.array([p1[t] - p1[t - 60] for t in ts_ if t - 60 in p1]); tt = [t for t in ts_ if t - 60 in p1]
    out = {}
    for sh in (-120, -60, 0, 60, 120):
        ds = np.array([math.log(close_at[t + sh] / close_at[t + sh - 60]) if (t + sh in close_at and t + sh - 60 in close_at) else np.nan for t in tt]); ok = ~np.isnan(ds)
        out[sh] = round(float(np.corrcoef(dp[ok], ds[ok])[0, 1]), 3)
    print(f, "corr of 1-min price change ending at label t with Binance return ending at t+shift:", out, "| n", len(dp), "| share of minutes with a price change:", round(float((dp != 0).mean()), 2))
