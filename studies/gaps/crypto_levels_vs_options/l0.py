"""L0 sanity on the first 3 tune resolution dates (27-29 Oct)."""
import numpy as np, pandas as pd
from common import *
from pmlab import fees
P = pd.read_parquet(DATA / "panel_euro.parquet"); meta = pd.read_parquet(DATA / "meta_euro.parquet")
sl = meta[(meta.date <= "2026-10-29") & (meta.freq == "daily")]
print("slice markets", len(sl), "dates", sorted(sl.date.unique()))
mins = {"BTC": Minute("BTCUSDT"), "ETH": Minute("ETHUSDT")}
# 1. official outcome vs Binance candle: candle opening at T-60 (closes at T) and candle opening at T (closes T+59)
ok_a = ok_b = 0; rows = []
for _, u in sl.iterrows():
    M = mins[u.asset]; i = (u["T"] - M.t0) // 60
    ca, cb = M.close[i - 1], M.close[i]
    a, b = (ca > u.K) == u.yes_won, (cb > u.K) == u.yes_won
    ok_a += a; ok_b += b
    if not (a and b): rows.append((u.slug, u.K, ca, cb, u.yes_won))
print("outcome reproduced: candle opening 11:59 ->", ok_a, "/", len(sl), "; candle opening 12:00 ->", ok_b, "/", len(sl)); print(rows)
Q = P.merge(sl[["m", "K", "T", "start", "yes_won", "asset", "date"]], on="m")
print("timestamps inside [start-600, T):", bool(((Q.t >= Q.start - 600) & (Q.t < Q["T"])).all()), "; first bucket lag after start (s) median", (Q.groupby("m").t.min() - sl.set_index("m").start).median(),
      "; last bucket before T (s) median", (sl.set_index("m")["T"] - Q.groupby("m").t.max()).median())
last = Q.sort_values("t").groupby("m").tail(1)
print("last bucket: model>0.5 agrees with outcome", ((last.pa > 0.5) == last.yes_won).mean(), " market>0.5 agrees", ((last.pm > 0.5) == last.yes_won).mean())
h = Q[Q.t % 3600 == 0]
near = h[(h.pm >= 0.45) & (h.pm <= 0.55)]
print("market price 0.45-0.55: n market-hours", len(near), "markets", near.m.nunique(), "YES rate", near.yes_won.mean())
nearm = h[(h.pa >= 0.45) & (h.pa <= 0.55)]
print("model 0.45-0.55: n", len(nearm), "markets", nearm.m.nunique(), "YES rate", nearm.yes_won.mean())
print("gap (pm - pa) overall in slice: mean %.4f median %.4f sd %.4f; with model in [.05,.95]: mean %.4f sd %.4f n %d" % (
    (h.pm - h.pa).mean(), (h.pm - h.pa).median(), (h.pm - h.pa).std(), (h[(h.pa > .05) & (h.pa < .95)].pm - h[(h.pa > .05) & (h.pa < .95)].pa).mean(),
    (h[(h.pa > .05) & (h.pa < .95)].pm - h[(h.pa > .05) & (h.pa < .95)].pa).std(), ((h.pa > .05) & (h.pa < .95)).sum()))
print("sigma: DVOL mean %.3f, RV24 mean %.3f" % (h.sig_a.mean(), h.sig_b.mean()))
for p in (0.5, 0.9, 0.05):
    sh = 20 / p; print("fee check p=%.2f shares %.2f fee %.5f toolkit %.5f" % (p, sh, sh * 0.01 * p * (1 - p), fees.taker_fee(sh, p, 0.01)))
# lead-lag on 5-minute changes, near the money
Q = Q.sort_values(["m", "t"])
g = Q.groupby("m")
Q["dpm"] = g.pm.diff(); Q["dt"] = g.t.diff()
for lag in (-2, -1, 0, 1, 2):
    Q["dpa_l"] = g.pa.diff().groupby(Q.m).shift(lag)
    x = Q[(Q.dt == 300) & (Q.pa > 0.15) & (Q.pa < 0.85) & Q.dpa_l.notna()]
    print("lag %+d buckets: corr(d pm[t], d model[t%+d]) = %.3f  n=%d" % (lag, -lag, np.corrcoef(x.dpm, x.dpa_l)[0, 1], len(x)))
