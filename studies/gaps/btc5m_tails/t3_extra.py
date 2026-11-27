"""Post-hoc attack checks on the T3 Vega7 result (descriptive, no rule, nothing tuned). Usage: python3 t3_extra.py [full]
Reads the unit tables written by t3.py (pooled cell) and Vega7's fills. Writes out/<tag>/t3_extra.md."""
import json
import sys

import numpy as np
import pandas as pd

from common import DATA, END, MONTHS, OUT, START, add_money, binom_tail, month_of, tail_band, time_band

tag = sys.argv[1] if len(sys.argv) > 1 else "full"
lines = []


def say(s=""):
    print(s)
    lines.append(s)


fills = json.loads((DATA / "vega7_fills.json").read_text())
mk = pd.read_parquet(DATA / f"markets_{tag}.parquet")
meta = {int(r.t0): bool(r.up_won) for r in mk.itertuples()}
meta.update({int(k): bool(v["up_won"]) for k, v in json.loads((DATA / "vega7_meta.json").read_text()).items()})
rows = []
for f in fills:
    t0 = int(f["slug"].rsplit("-", 1)[1])
    if not (START <= t0 < END) or t0 not in meta:
        continue
    s = 1 if f["outcome"] == "Up" else 0
    rows.append({"t0": t0, "bt": int(f["timestamp"]), "e": int(f["timestamp"]) - 3 - t0, "side": s, "p": round(float(f["price"]), 6), "z": float(f["size"]),
                 "hit": (s == 1) == meta[t0]})
v = add_money(pd.DataFrame(rows))
v["tb"] = time_band(v.e.to_numpy())
v["band"] = tail_band(v.p.to_numpy())
v["month"] = month_of(v.t0.to_numpy())

say("## T3 attack checks (post-hoc, descriptive)\n")
say("Exact one-sided binomial: Vega7's (market, outcome) units that won vs the equal-weight break-even of its own units (price + fee).\n")
say("| cell | period | units | hits | break-even | expected hits | exact p (P[X >= hits]) | net $ | net $ without best 3 markets |")
say("|---|---|---|---|---|---|---|---|---|")
cells = [("<=0.05 x 225-285", (v.p <= 0.05) & (v.e >= 225) & (v.e < 285)),
         ("<=0.015 x 75-45", (v.band == "<=0.015") & (v.tb == "75-45")),
         ("<=0.015 x 45-15", (v.band == "<=0.015") & (v.tb == "45-15")),
         ("all its fills", np.ones(len(v), bool))]
for name, m in cells:
    for period in MONTHS + ["All"]:
        d = v[m] if period == "All" else v[m & (v.month == period)]
        if not len(d):
            continue
        u = d.groupby(["t0", "side"]).agg(hit=("hit", "first"), z=("z", "sum"), stake=("stake", "sum"), fee=("fee", "sum"))
        be = float(((u.stake + u.fee) / u.z).mean())
        n, k = len(u), int(u.hit.sum())
        g = d.groupby("t0").net.sum().sort_values(ascending=False)
        say(f"| {name} | {period} | {n} | {k} | {100 * be:.2f}% | {n * be:.1f} | {binom_tail(k, n, be):.2e} | {g.sum():+,.0f} | {g.sum() - g.head(3).sum():+,.0f} |")

# Vega7 activity over time: is it still doing the same thing in the reporting month?
say("\nVega7 BTC 5m fills per day by month: " + ", ".join(f"{m} {len(v[v.month == m]) / d:.1f}" for m, d in zip(MONTHS, (30, 31, 26))))
say("Share of Vega7 dollars at <= 0.05 and seconds 225-285 by month: " + ", ".join(
    f"{m} {100 * v[(v.month == m) & (v.p <= 0.05) & (v.e >= 225) & (v.e < 285)].stake.sum() / v[v.month == m].stake.sum():.0f}%" for m in MONTHS))
say("Median Vega7 fill: %.0f shares, $%.2f; 90th percentile $%.2f" % (v.z.median(), v.stake.median(), v.stake.quantile(0.9)))
(OUT / tag / "t3_extra.md").write_text("\n".join(lines) + "\n")
