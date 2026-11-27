"""T2: the published rule as stated. Buy every buyable print priced <= 0.02 (A) or <= 0.05 (B) with 225 <= e < 285,
up to 25 dollars of stake per market. Protocol 2.4. Usage: python3 t2.py [full|slice]"""
import sys

import numpy as np
import pandas as pd

from common import DATA, MONTHS, OUT, fee_rate, month_of
from pmlab import stats

tag = sys.argv[1] if len(sys.argv) > 1 else "full"
out = OUT / tag
out.mkdir(parents=True, exist_ok=True)
df = pd.read_parquet(DATA / f"prints_{tag}.parquet")
mk = pd.read_parquet(DATA / f"markets_{tag}.parquet")
empty = mk.rows == 0
short = mk.volume.notna() & (mk.volume > 0) & (mk.tape_shares / mk.volume.where(mk.volume > 0) < 0.9)
valid = mk[~empty & ~short]
df = df[df.t0.isin(set(valid.t0))]
BUDGET = 25.0
DAYS = {"Sep": 30, "Oct": 31, "Nov": 26, "All": 87}
n_grid = {m: int((month_of(valid.t0.to_numpy()) == m).sum()) for m in MONTHS}
n_grid["All"] = len(valid)

lines = []


def say(s=""):
    print(s)
    lines.append(s)


def run(cap: float) -> pd.DataFrame:
    d = df[(df.e >= 225) & (df.e < 285) & (df.p <= cap)].copy()  # df is in tape order inside each market
    d["stake_full"] = d.z * d.p
    before = d.groupby("t0").stake_full.cumsum() - d.stake_full
    d["stk"] = np.clip(BUDGET - before, 0.0, d.stake_full)
    d = d[d.stk > 1e-9].copy()
    d["sh"] = d.stk / d.p
    d["fee"] = d.sh * fee_rate(d.bt.to_numpy()) * d.p * (1 - d.p)
    d["net"] = d.sh * d.hit - d.stk - d.fee
    d["month"] = month_of(d.t0.to_numpy())
    return d


rows = []
tickets = {}
for name, cap in (("A (<=0.02)", 0.02), ("B (<=0.05)", 0.05)):
    d = run(cap)
    tickets[name] = d
    for period in MONTHS + ["All"]:
        dp = d if period == "All" else d[d.month == period]
        g = dp.groupby("t0").agg(net=("net", "sum"), stake=("stk", "sum"), sh=("sh", "sum"), hit=("hit", "max"), fee=("fee", "sum"))
        ros, se, t = stats.ratio_cluster(g.net.tolist(), g.stake.tolist())
        m, mse, mt = stats.mean_se(g.net.tolist())
        lo, hi = stats.bootstrap_sum_ci(g.net.tolist())
        full = int((g.stake >= BUDGET - 1e-6).sum())
        rows.append({"variant": name, "period": period, "grid_markets": n_grid[period], "tickets": len(dp), "markets": len(g), "stake": g.stake.sum(),
                     "avg_price": g.stake.sum() / g.sh.sum(), "hit_tickets": int(dp.hit.sum()), "hit_markets": int(g.hit.sum()),
                     "hit_rate_mkt": g.hit.mean(), "fees": g.fee.sum(), "ros": ros, "ros_se": se, "t": t, "net": g.net.sum(), "net_per_mkt": m, "t_mean": mt,
                     "boot_lo": lo, "boot_hi": hi, "budget_filled": full, "median_stake": g.stake.median(),
                     "usd_per_day_all_windows": g.net.sum() / DAYS[period] * 4})
res = pd.DataFrame(rows)
res.to_csv(out / "t2.csv", index=False)
for name, d in tickets.items():
    d.to_parquet(DATA / f"t2_tickets_{tag}_{name[0]}.parquet", index=False)

say("## T2. The published rule (budget $25 of stake per market, seconds 225-285)\n")
say("| variant | period | grid mkts | mkts traded | tickets | stake $ | avg price | hit mkts (hit tickets) | fees $ | return on stake | t (clustered) | net $ | bootstrap 95% of net $ | net $/traded mkt (t) | budget filled | $ per day, all windows |")
say("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for r in res.itertuples():
    say(f"| {r.variant} | {r.period} | {r.grid_markets:,} | {r.markets:,} | {r.tickets:,} | {r.stake:,.0f} | {r.avg_price:.4f} | {r.hit_markets} ({r.hit_tickets}) | {r.fees:,.0f} | "
        f"{100 * r.ros:+.1f}% | {r.t:+.2f} | {r.net:+,.0f} | [{r.boot_lo:+,.0f}, {r.boot_hi:+,.0f}] | {r.net_per_mkt:+.2f} ({r.t_mean:+.2f}) | {r.budget_filled:,} | {r.usd_per_day_all_windows:+,.0f} |")
say("\nPer-market stake: median $%.2f (A), $%.2f (B)." % (res[(res.variant.str[0] == "A") & (res.period == "All")].median_stake.iloc[0],
                                                       res[(res.variant.str[0] == "B") & (res.period == "All")].median_stake.iloc[0]))
# largest winners: how concentrated is the result
for name, d in tickets.items():
    g = d.groupby("t0").net.sum().sort_values(ascending=False)
    say(f"{name}: top 5 markets by net $: " + ", ".join(f"{v:,.0f}" for v in g.head(5)) + f"; winners {int((g > 0).sum())}, losers {int((g <= 0).sum())}")
(out / "t2.md").write_text("\n".join(lines) + "\n")
