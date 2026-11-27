"""T1 (tail prints <= 0.10 by price band x seconds-left band) and T4 (favourite prints >= 0.95, mirror bands).

Usage: python3 t1_t4.py [full|slice]. Writes out/<tag>/t1_*.csv, t4_*.csv and t1_t4.md. Rules: protocol.md 2.1-2.3, 2.6, 2.7.
"""
import sys

import numpy as np
import pandas as pd

from common import DATA, FAV_BANDS, MONTHS, OUT, TAIL_BANDS, TIME_BANDS, add_money, cell_stats, fav_band, month_of, tail_band, time_band

tag = sys.argv[1] if len(sys.argv) > 1 else "full"
out = OUT / tag
out.mkdir(parents=True, exist_ok=True)
df = pd.read_parquet(DATA / f"prints_{tag}.parquet")
mk = pd.read_parquet(DATA / f"markets_{tag}.parquet")

lines = []


def say(s=""):
    print(s)
    lines.append(s)


# ---- universe (protocol 2.1)
empty = mk.rows == 0
short = mk.volume.notna() & (mk.volume > 0) & (mk.tape_shares / mk.volume.where(mk.volume > 0) < 0.9)
valid = mk[~empty & ~short]
say(f"markets downloaded {len(mk)}, empty tape {int(empty.sum())}, tape under 90% of gamma volume {int(short.sum())}, used {len(valid)}")
vm = month_of(valid.t0.to_numpy())
say("used by month: " + ", ".join(f"{m} {int((vm == m).sum())}" for m in MONTHS))
df = df[df.t0.isin(set(valid.t0))].copy()
df["tb"] = time_band(df.e.to_numpy())
say(f"prints {len(df)}, before the window opens (excluded) {int((df.tb == 'pre').sum())}")
df = df[df.tb != "pre"]
df["month"] = month_of(df.t0.to_numpy())


def table(d: pd.DataFrame, band_col: str, bands, label: str) -> pd.DataFrame:
    rows = []
    for period in MONTHS + ["All"]:
        dp = d if period == "All" else d[d.month == period]
        for b, _, _ in bands:
            for tb in TIME_BANDS:
                c = dp[(dp[band_col] == b) & (dp.tb == tb)]
                rows.append({"table": label, "period": period, "price": b, "left": tb, **cell_stats(c)})
    return pd.DataFrame(rows)


def fmt(t: pd.DataFrame, period: str) -> list[str]:
    o = ["| price | s left | prints | mkts | shares | dollars | hit mkts | hit rate [Wilson 95%] | break-even | z binom (exact 1-sided p) | sh-w hit | avg price | net c/share | t | return on stake | t(RoS) |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in t[t.period == period].itertuples():
        if r.prints == 0:
            o.append(f"| {r.price} | {r.left} | 0 | | | | | | | | | | | | | |")
            continue
        o.append(f"| {r.price} | {r.left} | {int(r.prints):,} | {int(r.markets):,} | {r.shares:,.0f} | {r.dollars:,.0f} | {int(r.hits)}/{int(r.units)} | "
                 f"{100 * r.hit_rate:.2f}% [{100 * r.wil_lo:.2f}, {100 * r.wil_hi:.2f}] | {100 * r.breakeven:.2f}% | {r.z_binom:+.1f} (p {r.p_binom:.3f}) | {100 * r.sw_hit:.2f}% | "
                 f"{r.avg_price:.4f} | {100 * r.net_ps:+.3f} | {r.t:+.1f} | {100 * r.ros:+.1f}% | {r.ros_t:+.1f} |")
    return o


def survivors(t: pd.DataFrame, thr: float) -> list[str]:
    o = []
    al = t[t.period == "All"]
    for r in al.itertuples():
        if r.prints == 0 or not np.isfinite(r.t):
            continue
        ms = t[(t.price == r.price) & (t.left == r.left) & (t.period != "All")]
        signs = [np.sign(x) for x in ms.net_ps if np.isfinite(x)]
        same = len(signs) == 3 and len(set(signs)) == 1
        flag = " (fewer than 10 hit markets: t unreliable)" if r.hits < 10 else ""
        if abs(r.t) >= 2.0:
            o.append(f"- {r.price} x {r.left}: net {100 * r.net_ps:+.3f} c/share, t {r.t:+.1f}, hit markets {int(r.hits)}/{int(r.units)} vs break-even {100 * r.breakeven:.2f}% (binomial z {r.z_binom:+.1f}, exact one-sided p {r.p_binom:.4f}), monthly signs "
                     f"{'/'.join('+' if s > 0 else '-' for s in signs)} -> {'SURVIVES' if abs(r.t) >= thr and same else 'does not survive'} at |t| >= {thr}{flag}")
    return o or ["- no cell with |t| >= 2"]


# ---- T1
tail = add_money(df[df.p <= 0.10])
tail["band"] = tail_band(tail.p.to_numpy())
t1 = table(tail, "band", TAIL_BANDS, "T1 all buyable prints")
t1b = table(tail[tail.src == 1], "band", TAIL_BANDS, "T1 source B (taker bought the tail)")
t1.to_csv(out / "t1_cells.csv", index=False)
t1b.to_csv(out / "t1_cells_srcB.csv", index=False)
say("\n## T1. Buyable tail prints (price <= 0.10), all sources\n")
for period in ["All"] + MONTHS:
    say(f"\n### T1 {period}\n")
    for s in fmt(t1, period):
        say(s)
say("\n### T1 pooled, source B only (a taker really bought the tail)\n")
for s in fmt(t1b, "All"):
    say(s)
say("\n### T1 cells with pooled |t| >= 2 and the correction (24 cells, threshold 3.1)\n")
for s in survivors(t1, 3.1):
    say(s)

# totals of the tail tape by source, as context for the earlier 'takers lose below 0.10' number
say("\n### Tail prints inside the window, totals by source (pooled)\n")
inside = tail[tail.tb != "after"]
for name, d in (("all", inside), ("source B (taker bought tail)", inside[inside.src == 1]), ("source S (taker sold favourite)", inside[inside.src == 0])):
    c = cell_stats(d)
    say(f"- {name}: prints {c['prints']:,}, markets {c['markets']:,}, dollars {c['dollars']:,.0f}, avg price {c['avg_price']:.4f}, sh-w hit {100 * c['sw_hit']:.2f}%, "
        f"net {100 * c['net_ps']:+.3f} c/share (t {c['t']:+.1f}), return on stake {100 * c['ros']:+.1f}% (t {c['ros_t']:+.1f}), net ${c['net_dollars']:,.0f}")

# ---- T4
fav = add_money(df[df.p >= 0.95])
fav["band"] = fav_band(fav.p.to_numpy())
t4 = table(fav, "band", FAV_BANDS, "T4 favourite prints")
t4.to_csv(out / "t4_cells.csv", index=False)
say("\n## T4. Buyable favourite prints (price >= 0.95), mirror bands\n")
for period in ["All"] + MONTHS:
    say(f"\n### T4 {period}\n")
    for s in fmt(t4, period):
        say(s)
say("\n### T4 cells with pooled |t| >= 2 and the correction (18 cells, threshold 3.1; 3.25 with T1)\n")
for s in survivors(t4, 3.1):
    say(s)

say("\n### Mirror: tail cell vs favourite cell (pooled)\n")
say("| tail band / fav band | s left | tail hit (sh-w) | tail avg price | tail net c/sh (t) | fav LOSS rate (sh-w) | 1 - fav avg price | fav net c/sh (t) | agree? |")
say("|---|---|---|---|---|---|---|---|---|")
for (tb_name, _, _), (fb_name, _, _) in zip(TAIL_BANDS[:3], FAV_BANDS):
    for tb in TIME_BANDS:
        a = t1[(t1.period == "All") & (t1.price == tb_name) & (t1.left == tb)].iloc[0]
        b = t4[(t4.period == "All") & (t4.price == fb_name) & (t4.left == tb)].iloc[0]
        if a.prints == 0 or b.prints == 0:
            say(f"| {tb_name} / {fb_name} | {tb} | n/a | | | | | | |")
            continue
        if a.net_ps > 0 and b.net_ps < 0:
            verdict = "yes: tail cheap, favourite dear"
        elif a.net_ps < 0 and b.net_ps > 0:
            verdict = "yes: tail dear, favourite cheap"
        elif a.net_ps < 0 and b.net_ps < 0:
            verdict = "both lose (true value inside the spread)"
        else:
            verdict = "NO: both win"
        say(f"| {tb_name} / {fb_name} | {tb} | {100 * a.sw_hit:.2f}% | {a.avg_price:.4f} | {100 * a.net_ps:+.3f} ({a.t:+.1f}) | {100 * (1 - b.sw_hit):.2f}% | "
            f"{1 - b.avg_price:.4f} | {100 * b.net_ps:+.3f} ({b.t:+.1f}) | {verdict} |")

(out / "t1_t4.md").write_text("\n".join(lines) + "\n")
