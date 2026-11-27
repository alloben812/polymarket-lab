"""Post-hoc context for results.md (not a variant, no rule, nothing tuned): size of the whole pie in the T2 cell and
concentration of the T2 result. Reads the outputs of build.py and t2.py. Usage: python3 capacity.py [full|slice]"""
import sys

import numpy as np
import pandas as pd

from common import DATA, MONTHS, OUT, add_money, month_of
from pmlab import stats

tag = sys.argv[1] if len(sys.argv) > 1 else "full"
df = pd.read_parquet(DATA / f"prints_{tag}.parquet")
mk = pd.read_parquet(DATA / f"markets_{tag}.parquet")
empty = mk.rows == 0
short = mk.volume.notna() & (mk.volume > 0) & (mk.tape_shares / mk.volume.where(mk.volume > 0) < 0.9)
valid = mk[~empty & ~short]
df = df[df.t0.isin(set(valid.t0))]
DAYS = {"Sep": 30, "Oct": 31, "Nov": 26, "All": 87}
lines = []


def say(s=""):
    print(s)
    lines.append(s)


say("## Capacity context (post-hoc, descriptive)\n")
say("Whole pie = every buyable print in the T2 cell taken in full by somebody (all real takers together), scaled x4 to all windows.\n")
say("| cap | period | markets with a print | prints | shares | stake $ | net $ after fee | net c/share (t) | stake $/day | net $/day | median print shares | median print $ |")
say("|---|---|---|---|---|---|---|---|---|---|---|---|")
for cap in (0.02, 0.05):
    d = add_money(df[(df.e >= 225) & (df.e < 285) & (df.p <= cap)])
    d["month"] = month_of(d.t0.to_numpy())
    for period in MONTHS + ["All"]:
        dp = d if period == "All" else d[d.month == period]
        g = dp.groupby("t0").agg(net=("net", "sum"), z=("z", "sum"))
        r, se, t = stats.ratio_cluster(g.net.tolist(), g.z.tolist())
        say(f"| <= {cap} | {period} | {len(g):,} | {len(dp):,} | {dp.z.sum():,.0f} | {dp.stake.sum():,.0f} | {dp.net.sum():+,.0f} | {100 * r:+.3f} ({t:+.1f}) | "
            f"{dp.stake.sum() / DAYS[period] * 4:,.0f} | {dp.net.sum() / DAYS[period] * 4:+,.0f} | {dp.z.median():.0f} | {dp.stake.median():.2f} |")

for v in ("A", "B"):
    p = DATA / f"t2_tickets_{tag}_{v}.parquet"
    if not p.exists():
        continue
    t = pd.read_parquet(p)
    g = t.groupby("t0").agg(net=("net", "sum"), stk=("stk", "sum"), hit=("hit", "max")).sort_values("net", ascending=False)
    tot = g.net.sum()
    say(f"\nT2 variant {v}: traded markets {len(g):,}, hit markets {int(g.hit.sum())}, net ${tot:+,.0f}; without the best 1 / 3 / 10 markets: "
        f"${tot - g.net.head(1).sum():+,.0f} / ${tot - g.net.head(3).sum():+,.0f} / ${tot - g.net.head(10).sum():+,.0f}. "
        f"Average loss in a losing market ${g[g.net <= 0].net.mean():.2f}, average gain in a hit market ${g[g.hit].net.mean():,.2f}.")
    # break-even hit rate of the rule at its own prices and the realised one
    be = float(((t.stk + t.fee).sum()) / t.sh.sum())
    say(f"  share-weighted break-even win probability {100 * be:.2f}% vs realised share-weighted hit {100 * (t.sh * t.hit).sum() / t.sh.sum():.2f}% "
        f"({t.sh.sum():,.0f} shares).")
    for period in MONTHS:
        gp = g[month_of(g.index.to_numpy()) == period]
        say(f"  {period}: markets {len(gp):,}, hit markets {int(gp.hit.sum())}, net ${gp.net.sum():+,.0f}, without best 3 ${gp.net.sum() - gp.net.head(3).sum():+,.0f}")

(OUT / tag / "capacity.md").write_text("\n".join(lines) + "\n")
