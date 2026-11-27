"""Step 7: tables for results.md from the outputs of s4_sim.py and s5_live.py (no new variant).
- variant table, both periods, 95% intervals clustered by event (city x target date)
- the 200-dollar account, both fill models, both periods, intervals over events and over days
- the "today's rates" scenario of protocol 4.10 (reward rescaled, fills unchanged, 1-dollar rule re-applied)
Run: python3 s7_report.py [tag]   (tag "" = full run, "_slice" = one-day check) -> out/report{tag}.md, out/report{tag}.json
"""
import json, sys
import numpy as np, pandas as pd
from pmlab.stats import mean_se

TAG = sys.argv[1] if len(sys.argv) > 1 else ""
OUT = "/home/user/polymarket-lab/data/gaps_weather_rewards"
RES = "/home/user/polymarket-lab/studies/gaps/weather_rewards_quoting/out"
V = pd.read_csv(f"{RES}/variants{TAG}.csv")
A = json.load(open(f"{RES}/account{TAG}.json"))
live = json.load(open(f"{RES}/live.json"))
octc = json.load(open(f"{RES}/october_comp{TAG}.json"))
L = []
rep = {}


def f(x, d=2):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:,.{d}f}"


L.append("## Variants (per market-day; 95% interval = net +- 1.96 se, se clustered by event)\n")
L.append("| variant | period | market-days | markets | events | reward $/md | settlement $/md | net $/md | 95% CI | t | net per $ of capital-day | fills | settle c/share | markout 5/30/120 min c/share |")
L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for r in V.itertuples():
    if r.period == "all":
        continue
    L.append(f"| {r.variant} | {r.period} | {r.market_days} | {r.markets} | {r.events} | {f(r.reward_per_md)} | {f(r.pnl_per_md)} | {f(r.net_per_md)} | "
             f"[{f(r.net_per_md - 1.96 * r.se)}, {f(r.net_per_md + 1.96 * r.se)}] | {f(r.t)} | {f(r.net_per_capday, 3)} | {r.fills} | "
             f"{f(100 * r.settle_ps)} | {f(100 * r.m5_ps)} / {f(100 * r.m30_ps)} / {f(100 * r.m120_ps)} |")
L.append("")
L.append("Reward totals and the 1-dollar rule (all 10 days): ")
for r in V[V.period == "all"].itertuples():
    L.append(f"- {r.variant}: reward before the rule ${r.reward_raw_total:,.0f}, after ${r.reward_total:,.0f} (removed ${r.reward_raw_total - r.reward_total:,.0f}); "
             f"one-maker sensitivity ${r.reward_one_maker_total:,.0f}; settlement ${r.pnl_total:,.0f}; net ${r.net_total:,.0f}; capital-days {r.capital_days:,.0f}; "
             f"reward per $ capital-day {r.reward_per_capday:.3f}")
L.append("")

# ---------------------------------------------------------------- account
L.append(f"## 200-dollar account (k = {A['account_k']}, protection = {A['account_protection']}, class filter = {A['class_filter']})\n")
L.append("| period | fill model | $/day | 95% CI (events) | t events | t days | %/day on $200 | reward $/day | settlement $/day | markets | market-days | events | fills | pairs (shares) | worst day | best day | 1-$ rule removed |")
L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
rep["account"] = []
for a in A["accounts"]:
    lab = ("first5" if a["label"].startswith("first5") else "last5") + a["fill_model"] + TAG
    rw = pd.read_csv(f"{OUT}/acct_rw_{lab}.csv")
    F = pd.read_csv(f"{OUT}/acct_fills_{lab}.csv")
    ev = rw.groupby("event").reward.sum().to_frame().join(F.groupby("event").pnl.sum() if len(F) else None, how="outer").fillna(0.0)
    ev["net"] = ev.reward + ev.pnl
    n_days = a["days"]
    # event-clustered interval for the total, expressed per day
    tot = ev.net.sum(); se_tot = ev.net.std(ddof=1) * np.sqrt(len(ev)) if len(ev) > 1 else float("nan")
    lo, hi = (tot - 1.96 * se_tot) / n_days, (tot + 1.96 * se_tot) / n_days
    L.append(f"| {a['label']} | {a['fill_model']} | {f(a['usd_per_day'])} | [{f(lo)}, {f(hi)}] | {f(a['t_events'])} | {f(a['t_days'])} | {f(a['pct_per_day'])} | "
             f"{f(a['reward_per_day'])} | {f(a['pnl_per_day'])} | {a['markets']} | {a['market_days']} | {a['events']} | {a['fills']} | {f(a['pairs_completed_shares'], 0)} | "
             f"{f(a['worst_day'])} | {f(a['best_day'])} | {f(a['reward_removed_by_1usd_rule'])} |")
    # today's-rates scenario
    live_med = live["rate_quantiles"]["0.5"]
    octm = A["october_median_rate_quoted"]
    fac = live_med / octm if octm else float("nan")
    rw["raw_s"] = rw.raw * fac
    rw["rew_s"] = np.where(rw.raw_s >= 1.0, rw.raw_s, 0.0)
    days = [d["date"] for d in a["daily"]]
    dd = pd.DataFrame({"date": days}).set_index("date")
    dd["rew"] = rw.groupby("date").rew_s.sum().reindex(days).fillna(0.0)
    dd["pnl"] = (F.groupby("date").pnl.sum() if len(F) else pd.Series(dtype=float)).reindex(days).fillna(0.0)
    dd["net"] = dd.rew + dd.pnl
    evs = rw.groupby("event").rew_s.sum().to_frame().join(F.groupby("event").pnl.sum() if len(F) else None, how="outer").fillna(0.0)
    evs["net"] = evs.rew_s + evs.pnl
    _, _, t_s = mean_se(evs.net.tolist())
    rep["account"].append(dict(label=a["label"], model=a["fill_model"], usd_day=a["usd_per_day"], ci_events=[lo, hi], t_events=a["t_events"],
                               scenario_factor=fac, scenario_usd_day=float(dd.net.mean()), scenario_reward_day=float(dd.rew.mean()), scenario_t_events=t_s,
                               top3_event_share_of_pnl=float(ev.pnl.sort_values().head(3).sum()) if len(ev) else None,
                               daily=a["daily"]))
L.append("")
L.append("Daily rows (reporting period):\n")
for a in A["accounts"]:
    if not a["label"].startswith("last5"):
        continue
    L.append(f"- model {a['fill_model']}: " + "; ".join(f"{d['date']} net {d['net']:+.2f} (reward {d['reward']:.2f}, settlement {d['pnl']:+.2f}, fills {d['fills']})" for d in a["daily"]))
L.append("")
L.append("## Today's-rates scenario (protocol 4.10)\n")
for r in rep["account"]:
    L.append(f"- {r['label']}, model {r['model']}: factor {r['scenario_factor']:.3f} -> ${r['scenario_usd_day']:,.2f}/day "
             f"(reward ${r['scenario_reward_day']:,.2f}/day; t events {f(r['scenario_t_events'])}); October-rate result ${r['usd_day']:,.2f}/day")
L.append(f"\nLive (2026-11-27): rewarded highest-temperature markets {live['rewarded_highest_temperature']}, median rate ${live['rate_quantiles']['0.5']}/day, "
         f"sum ${live['rate_sum_per_day']:,.0f}/day, rate >= 50: {live['rate_ge_50']}; October median rate over quoted minutes ${A['october_median_rate_quoted']:.1f}. "
         f"Median conservative competitor score in band: live k=0 {live['live_books_summary_k0']['median_comp']:.0f} (n = {live['live_books_summary_k0']['n']} books), "
         f"October k=0 {octc['october_median_comp_valid_scored']['k0']:.0f} (all scored in-universe minutes).")
open(f"{RES}/report{TAG}.md", "w").write("\n".join(L) + "\n")
json.dump(rep, open(f"{RES}/report{TAG}.json", "w"), indent=1, default=float)
print("\n".join(L))
