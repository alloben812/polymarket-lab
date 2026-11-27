"""Markdown tables for results.md from out/*.csv (no new computation)."""
import pandas as pd

from common import OUT

d = pd.read_csv(OUT / "descriptive.csv")
v = pd.read_csv(OUT / "variants.csv")
c = pd.read_csv(OUT / "calibration.csv")
L = []


def f(x, n=2):
    return "-" if pd.isna(x) else f"{x:.{n}f}"


L.append("### T1. Taker BUY prints with match time in the last 60 s (m < t1), all 1,728 markets\n")
L.append("| price bucket | prints | markets | shares | avg price | win rate (share-w.) | fee c/sh | net c/sh | se | t (by market) | net c/sh tune (t) | net c/sh report (t) |")
L.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
a = d[d["sample"] == "all, m<t1"].set_index("bucket")
tu = d[d["sample"] == "tune, m<t1"].set_index("bucket")
rp = d[d["sample"] == "report, m<t1"].set_index("bucket")
for b in a.index:
    r = a.loc[b]
    L.append(f"| {b} | {int(r.prints):,} | {int(r.markets)} | {r.shares:,.0f} | {r.avg_price:.3f} | {r.win_share_w:.3f} | {r.fee_c:.3f} | {r.net_c:+.2f} | {r.se_c:.2f} | {r.t:+.2f} | "
             f"{tu.loc[b].net_c:+.2f} ({tu.loc[b].t:+.1f}) | {rp.loc[b].net_c:+.2f} ({rp.loc[b].t:+.1f}) |")
L.append("")
for per, title in (("tune", "T3. Rule family, tuning period (21-24 Nov, 1,152 markets, 4 days)"), ("report", "T4. Rule family, reporting period (25-26 Nov, 576 markets, 2 days)")):
    L.append(f"### {title}\n")
    L.append("| L | floor | margin | D | excl. | trades | markets | shares | avg price | win (trades) [Wilson] | win (markets) [Wilson] | lost mkts (of them proxy miss) | net c/sh | se | t | net $ | $/day |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in v[v.period == per].itertuples():
        if r.trades == 0:
            L.append(f"| {r.L} | {r.floor} | {r.margin} | {r.D} | {'on' if r.excl else 'off'} | 0 | 0 | 0 | - | - | - | - | - | - | - | 0 | 0 |")
            continue
        L.append(f"| {r.L} | {r.floor} | {r.margin} | {r.D} | {'on' if r.excl else 'off'} | {int(r.trades)} | {int(r.markets)} | {r.shares:,.0f} | {r.avg_price:.3f} | "
                 f"{r.win:.3f} [{r.wil_lo:.3f}, {r.wil_hi:.3f}] | {r.mkt_win:.3f} [{r.mkt_lo:.3f}, {r.mkt_hi:.3f}] | {int(r.lost_mkts)} ({int(r.lost_mkts_proxy_miss)}) | "
                 f"{r.net_c:+.2f} | {f(r.se_c)} | {f(r.t, 1)} | {r.net_usd:+.0f} | {r.usd_day:+.0f} |")
    L.append("")
L.append("### T5. Model calibration per market (favoured side at a fixed model time; no prices involved)\n")
L.append("| model time | period | floor | excl. | markets (share of all) | favoured side won | Wilson 95% | losses |")
L.append("|---|---|---|---|---|---|---|---|")
for r in c.itertuples():
    L.append(f"| {r.model_time} | {r.period} | {r.floor} | {'on' if r.excl else 'off'} | {int(r.markets)} ({r.share_of_markets:.2f}) | {r.win:.4f} | [{r.wilson_lo:.4f}, {r.wilson_hi:.4f}] | {int(r.losses)} |")
(OUT / "tables.md").write_text("\n".join(L) + "\n")
print("\n".join(L[:14]))
