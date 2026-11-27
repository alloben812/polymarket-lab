"""Slice sanity checks (protocol B11 step 2). Usage: python3 sanity.py eth-5m_day1"""
import sys

import numpy as np
import pandas as pd

from common import BIG
from pmlab import fees, stats

tag = sys.argv[1]
mk = pd.read_parquet(BIG / f"{tag}_markets.parquet")
f = pd.read_parquet(BIG / f"{tag}_fills.parquet")
g = np.load(BIG / f"{tag}_grid.npz")
dur = int(mk.t1.iloc[0] - mk.t0.iloc[0])
print(tag, "markets", len(mk), "found", int(mk.found.sum()), "resolved", int(mk.resolved.sum()), "fills", len(f))
print("fee rates:", mk.fee_rate_meta.value_counts(dropna=False).to_dict(), "twap_lookback:", mk.twap_lookback.value_counts(dropna=False).to_dict())
print("up_won share:", round(mk.up_won.astype(float).mean(), 3), " official check (final>=ptb)==up_won:",
      round(((mk.final >= mk.ptb) == mk.up_won.astype(bool)).mean(), 4))
rel = (f.m - f.t0) / dur
print("match time relative to window (quantiles 0,1,5,25,50,75,95,99,100 %):", np.round(np.quantile(rel, [0, .01, .05, .25, .5, .75, .95, .99, 1]), 3))
print("share pre / in / post:", round((rel < 0).mean(), 3), round(((rel >= 0) & (rel < 1)).mean(), 3), round((rel >= 1).mean(), 3))
print("BUY share:", round(f.buy.mean(), 3), " median size:", round(f.z.median(), 2), " median price:", round(f.p.median(), 3))
mid = f[(f.q >= 0.45) & (f.q <= 0.55)]
per = mid.groupby("t0").apply(lambda d: pd.Series({"w": (d.won_eq * d.z).sum(), "z": d.z.sum()}), include_groups=False)
r, se, t = stats.ratio_cluster(per.w.tolist(), per.z.tolist())
print(f"equivalent buys with q in [0.45,0.55]: n={len(mid)} markets={len(per)} share-weighted win rate={r:.4f} se={se:.4f}; mean q={np.average(mid.q, weights=mid.z):.4f}")
f["bucket"] = np.floor(f.q * 10).clip(0, 9) / 10
cal = f.groupby("bucket").apply(lambda d: pd.Series({"fills": len(d), "mean_q": np.average(d.q, weights=d.z), "win": np.average(d.won_eq, weights=d.z)}), include_groups=False)
print(cal.round(4).to_string())
# fee formula on a hand slice
s = f.head(5)
for _, x in s.iterrows():
    print("fee check", round(x.z, 4), round(x.p, 4), x.rate, "formula", round(x.z * x.rate * x.p * (1 - x.p), 6), "toolkit", fees.taker_fee(x.z, x.p, x.rate))
# gross identity: BUY outcome - p ; equivalent-buy form must agree
alt = f.won_eq - f.q
print("max |gross - (won_eq - q)|:", float(np.abs(alt - f.gross).max()))
# fair value sanity: last grid value vs outcome, mid-window Brier
G, T0 = g["G"], g["t0"]
uw = mk.set_index("t0").up_won.astype(float).reindex(T0).to_numpy()
print("G NaN:", int(np.isnan(G).sum()), " G at t1-1 agrees with outcome:", round(((G[:, -1] >= 0.5) == (uw == 1)).mean(), 4),
      " Brier G mid:", round(np.nanmean((G[:, dur // 2] - uw) ** 2), 4), " mean G at t0:", round(np.nanmean(G[:, 0]), 3))
U = g["U"]
print("U defined share at mid:", round(np.isfinite(U[:, dur // 2]).mean(), 3), " Brier U mid:", round(np.nanmean((U[:, dur // 2] - uw) ** 2), 4),
      " corr(U, G) at mid:", round(np.corrcoef(U[:, dur // 2][np.isfinite(U[:, dur // 2])], G[:, dur // 2][np.isfinite(U[:, dur // 2])])[0, 1], 3))
print("fup_d0 defined share (in-window prints):", round(f.fup_d0[(rel >= 0) & (rel < 1)].notna().mean(), 4))
