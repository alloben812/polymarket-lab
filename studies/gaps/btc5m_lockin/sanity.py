"""Step 2: sanity checks on the first 48 windows (protocol, 'Sanity checks')."""
import sys

import numpy as np

from common import all_windows, fee, load_px, meta, model_at
from pmlab import stats, updown

N = int(sys.argv[1]) if len(sys.argv) > 1 else 48
px = load_px()
print("px range", px.t_min, px.t_max, "nan share", float(np.mean(~px.ok)))
wins = all_windows()[:N]
n_rows = in_win = after = before = 0
near_w = near_n = 0
near_mk = {}
agree = tot = 0
cal = {}
late_hist = {}
for t0 in wins:
    m = meta(t0)
    if not m:
        print("no meta", t0)
        continue
    t1 = t0 + 300
    rows = updown.tape(m["condition"])
    assert all(rows[i]["t"] <= rows[i + 1]["t"] for i in range(len(rows) - 1))
    for r in rows:
        n_rows += 1
        if r["t"] < t0:
            before += 1
        elif r["t"] <= t1 + 10:
            in_win += 1
        else:
            after += 1
        d = r["t"] - t1
        if d >= -5:
            late_hist[min(d, 30)] = late_hist.get(min(d, 30), 0) + 1
        if r["s"] == "BUY" and t0 <= r["t"] - 3 < t1 and 0.45 <= r["p"] <= 0.55:
            w = (r["o"] == "Up") == m["up_won"]
            near_n += 1
            near_w += w
            a = near_mk.setdefault(t0, [0.0, 0.0])
            a[0] += r["z"] * (w - r["p"] - fee(r["p"]))
            a[1] += r["z"]
    k, a1 = px.twap(t0, 60), px.twap(t1, 60)
    tot += 1
    agree += (a1 >= k) == m["up_won"]
    off = (m["final_price"] >= m["price_to_beat"]) == m["up_won"]
    if not off:
        print("official prices disagree with up_won", t0, m["price_to_beat"], m["final_price"], m["up_won"])
    f, ea, kk = model_at(px, t1 - 30, t0)
    b = min(int(f * 10), 9)
    c = cal.setdefault(b, [0, 0, 0.0])
    c[0] += 1
    c[1] += m["up_won"]
    c[2] += f
print(f"markets {tot}, tape rows {n_rows}: before t0 {before} ({before/n_rows:.1%}), in [t0,t1+10] {in_win} ({in_win/n_rows:.1%}), after t1+10 {after} ({after/n_rows:.1%})")
print("rows by block time minus t1 (>=30 pooled):", dict(sorted(late_hist.items())))
print(f"BUY prints 0.45-0.55 inside the window: n={near_n}, win rate {near_w/near_n:.3f}, Wilson {stats.wilson(near_w, near_n)}")
r, se, t = stats.ratio_cluster([v[0] for v in near_mk.values()], [v[1] for v in near_mk.values()])
print(f"  net per share after fee {r*100:.2f}c (se {se*100:.2f}, t {t:.2f}), markets {len(near_mk)}")
print("fee at 0.50:", fee(0.5), " at 0.97:", fee(0.97))
print(f"Binance proxy agrees with official outcome: {agree}/{tot} = {agree/tot:.3f}")
print("calibration at t1-30 (bucket: n, realised up, mean f):")
for b in sorted(cal):
    n, u, s = cal[b]
    print(f"  {b/10:.1f}-{(b+1)/10:.1f}: n={n} up={u/n:.2f} f={s/n:.2f}")
