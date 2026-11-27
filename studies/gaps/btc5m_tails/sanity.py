"""Step 3: plumbing checks on a slice. Uses only prints priced 0.10-0.90 for anything that involves outcomes."""
import sys

import numpy as np
import pandas as pd

from common import DATA, add_money, fee_rate, month_of
from pmlab import fees, stats

tag = sys.argv[1] if len(sys.argv) > 1 else "slice"
df = pd.read_parquet(DATA / f"prints_{tag}.parquet")
mk = pd.read_parquet(DATA / f"markets_{tag}.parquet")
print("markets", len(mk), "empty tapes", int((mk.rows == 0).sum()), "prints", len(df), "bad rows", int(mk.bad_rows.sum()))
print("months", dict(zip(*np.unique(month_of(mk.t0), return_counts=True))))
print("up_won share", round(mk.up_won.mean(), 3))

# 1. fee formula
assert abs(fees.fee_per_share(0.5, 0.07) - 0.0175) < 1e-12 and abs(fees.fee_per_share(0.01, 0.07) - 0.000693) < 1e-12
assert fees.btc_updown_rate(1795219139) == 0.07 and fees.btc_updown_rate(1795219140) == 0.05
assert (fee_rate(np.array([1795219139, 1795219140])) == np.array([0.07, 0.05])).all()
print("fee per share at 0.01 / 0.05 / 0.50 (rate 0.07):", [round(fees.fee_per_share(p, 0.07), 6) for p in (0.01, 0.05, 0.5)])

# 2. timing of prints
e = df.e.to_numpy()
qs = np.quantile(e, [0.001, 0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99, 0.999])
print("e quantiles (s into window):", [int(x) for x in qs])
print("share of prints: before window %.3f, inside %.3f, after end %.3f" % ((e < 0).mean(), ((e >= 0) & (e < 300)).mean(), (e >= 300).mean()))
print("share of dollars: before %.3f, inside %.3f, after %.3f" % tuple((df.z * df.p)[m].sum() / (df.z * df.p).sum() for m in (e < 0, (e >= 0) & (e < 300), e >= 300)))
print("last tape row rel. to t0: median %d, max %d; first: median %d" % (mk.last_rel.median(), mk.last_rel.max(), mk.first_rel.median()))

# 3. tape shares vs gamma volume
v = mk[mk.volume.notna() & (mk.volume > 0)]
ratio = v.tape_shares / v.volume
print("tape shares / gamma volume: n %d, median %.4f, p1 %.4f, p5 %.4f, p99 %.4f, below 0.9: %d; volume missing: %d" % (
    len(v), ratio.median(), ratio.quantile(0.01), ratio.quantile(0.05), ratio.quantile(0.99), int((ratio < 0.9).sum()), int(mk.volume.isna().sum())))

# 4. calibration of buyable prints between 0.10 and 0.90 (inside the window only)
d = add_money(df[(df.e >= 0) & (df.e < 300) & (df.p > 0.10) & (df.p < 0.90)])
print("\nprice band   prints  markets  sw_hit  avg_p  mkt_hit [wilson]      net/share(t)")
for lo, hi in [(0.10, 0.20), (0.20, 0.30), (0.30, 0.45), (0.45, 0.55), (0.55, 0.70), (0.70, 0.80), (0.80, 0.90)]:
    c = d[(d.p > lo) & (d.p <= hi)]
    u = c.groupby(["t0", "side"]).hit.first()
    w = stats.wilson(int(u.sum()), len(u))
    g = c.groupby("t0").agg(net=("net", "sum"), z=("z", "sum"))
    r, se, t = stats.ratio_cluster(g.net.tolist(), g.z.tolist())
    print("%.2f-%.2f  %7d  %6d  %.3f   %.3f  %.3f [%.3f,%.3f]  %+.4f (%.1f)" % (lo, hi, len(c), c.t0.nunique(), (c.z * c.hit).sum() / c.z.sum(), c.stake.sum() / c.z.sum(), u.mean(), w[0], w[1], r, t))

# 5. source mix and Up/Down symmetry
print("\nsource B share of prints %.3f; Up share of prints %.3f" % (df.src.mean(), df.side.mean()))
