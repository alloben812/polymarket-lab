"""Compact markdown tables for results.md, built only from out/*.csv."""
import pandas as pd

from analyze import md_table
from common import OUT

F = {}
m1 = pd.read_csv(OUT / "m1.csv")
t = pd.DataFrame({
    "series": m1.series, "markets (all traded)": m1.mkts_with_trade, "fills": m1.fills,
    "taker $ / day (mean)": m1.usd_per_day_mean.round(0), "taker $ / day (median day)": m1.usd_per_day_median.round(0),
    "taker $ total": m1.taker_usd_total.round(0), "median $ / market": m1.usd_per_market_median.round(0),
    "fills / market": m1.fills_per_market_in_window.round(0), "seconds with a fill": (100 * m1.seconds_with_fill_share).round(1).astype(str) + "%",
    "median fill $": m1.fill_usd_median.round(2), "fills < 5 sh": (100 * m1.fills_lt5sh_share).round(0).astype(int).astype(str) + "%",
    "taker wallets": m1.wallets, "top-5 share": (100 * m1.top5_usd_share).round(0).astype(int).astype(str) + "%"})
F["m1"] = md_table(t)

m2 = pd.read_csv(OUT / "m2.csv")
p = m2[m2.cut == "period"]
F["m2_period"] = md_table(p[["series", "cell", "fills", "markets", "shares", "usd", "gross_c", "fee_c", "net_c", "se_c", "t", "net_pct", "net_usd"]]
                          .rename(columns={"cell": "period", "usd": "taker $", "gross_c": "gross c/sh", "fee_c": "fee c/sh", "net_c": "net c/sh", "se_c": "se", "net_pct": "net % turnover", "net_usd": "net $"})
                          .round({"shares": 0, "taker $": 0, "net $": 0}))
for cut, key in (("time", "m2_time"), ("price(eq.buy)", "m2_price"), ("side", "m2_side")):
    d = m2[m2.cut == cut]
    wide = d.assign(v=d.net_c.map(lambda x: f"{x:+.2f}") + " (" + d.t.map(lambda x: f"{x:+.1f}") + ")").pivot(index="cell", columns="series", values="v")
    wide = wide.reindex(index=list(dict.fromkeys(d.cell)), columns=list(dict.fromkeys(d.series))).reset_index().rename(columns={"cell": cut})
    F[key] = md_table(wide)
    g = d.assign(v=d.gross_c.map(lambda x: f"{x:+.2f}")).pivot(index="cell", columns="series", values="v")
    g = g.reindex(index=list(dict.fromkeys(d.cell)), columns=list(dict.fromkeys(d.series))).reset_index().rename(columns={"cell": cut})
    F[key + "_gross"] = md_table(g)
s = pd.read_csv(OUT / "m2s.csv")
F["m2s"] = md_table(s[["series", "mid_fills", "mid_markets", "mid_mean_q", "mid_win", "mid_se"]].rename(
    columns={"mid_fills": "fills at q 0.45-0.55", "mid_markets": "markets", "mid_mean_q": "mean price", "mid_win": "win rate", "mid_se": "se"}))

m3 = pd.read_csv(OUT / "m3.csv")
F["m3"] = md_table(m3.rename(columns={"pairs_lag0": "second pairs", "peak_lag": "peak lag s", "peak_corr": "peak corr", "mean_lag_pos": "mean lag s (positive part)",
                                      "half_lag": "50% lag s", "peak_lo90": "peak 5%", "peak_hi90": "peak 95%"}))
c = pd.read_csv(OUT / "m3_curves.csv")
F["m3_curve"] = md_table(c)
b = pd.read_csv(OUT / "m3b.csv")
F["m3b"] = md_table(b.rename(columns={"obs": "trade seconds", "best_lag": "best lag s", "rms_best": "RMS at best", "rms_lag0": "RMS lag 0", "rms_lag3": "RMS lag 3",
                                      "rms_lag10": "RMS lag 10", "rms_lag30": "RMS lag 30", "best_lo90": "best 5%", "best_hi90": "best 95%"}))
F["m3_day"] = md_table(pd.read_csv(OUT / "extra_m3_by_day.csv"))

px = pd.read_csv(OUT / "proxy.csv")
F["proxy"] = md_table(pd.DataFrame({
    "series": px.series, "windows": px.n, "mean bp": px.mean_bp.round(2), "sd bp": px.sd_bp.round(2), "mean abs bp": px.mean_abs_bp.round(2),
    "p1": px.p1.round(2), "p5": px.p5.round(2), "p25": px.p25.round(2), "p50": px.p50.round(2), "p75": px.p75.round(2), "p95": px.p95.round(2), "p99": px.p99.round(2),
    "proxy wrong": px.wrong, "wrong %": (100 * px.wrong_share).round(2), "Wilson 95%": (100 * px.wrong_lo).round(1).astype(str) + "-" + (100 * px.wrong_hi).round(1).astype(str),
    "official move in misses, median / max bp": px.missed_move_bp_median.round(2).astype(str) + " / " + px.missed_move_bp_max.round(2).astype(str),
    "median official move bp": px.official_move_bp_median.round(1), "windows with move < 2 bp": (100 * px.share_move_lt_2bp).round(1).astype(str) + "%"}))
dg = pd.read_csv(OUT / "diag.csv")
F["diag"] = md_table(dg.rename(columns={"brier_model": "Brier model", "brier_tape": "Brier last trade", "corr_model_tape": "corr", "mean_abs_diff": "mean abs diff"}))
cal = pd.read_csv(OUT / "cal.csv")
w = cal.assign(v=cal.up_freq.map(lambda x: f"{x:.3f}") + " (" + cal.n.astype(str) + ")").pivot(index="b", columns="series", values="v")
w = w.reindex(index=list(dict.fromkeys(cal.b)), columns=list(dict.fromkeys(cal.series))).reset_index().rename(columns={"b": "model bucket"})
F["cal"] = md_table(w)

r = pd.read_csv(OUT / "rules.csv")


def side_by_side(d, extra_cols):
    tu, re = d[d.period == "tune"].set_index(["series", "variant"]), d[d.period == "report"].set_index(["series", "variant"])
    out = pd.DataFrame(index=tu.index)
    for lab, x in (("tune", tu), ("report", re)):
        out[f"{lab} trades"] = x.trades
        out[f"{lab} mkts"] = x.markets
        for col, nm in extra_cols:
            out[f"{lab} {nm}"] = x[col]
        out[f"{lab} net c/sh"] = x.net_c.round(2)
        out[f"{lab} t"] = x.t.round(2)
        out[f"{lab} % turn"] = x.net_pct.round(2)
        out[f"{lab} $/day"] = x.usd_per_day.round(0)
    return out.reset_index()


F["m4"] = md_table(side_by_side(r[r.family == "M4"], []))
m5 = r[r.family == "M5"].copy()
m5["win"] = (100 * m5.win_rate).round(0).map(lambda v: "-" if v != v else f"{v:.0f}%") + " [" + (100 * m5.win_lo).round(0).map(lambda v: "-" if v != v else f"{v:.0f}") + "-" + \
    (100 * m5.win_hi).round(0).map(lambda v: "-" if v != v else f"{v:.0f}") + "] n=" + m5.positions.fillna(0).astype(int).astype(str)
F["m5"] = md_table(side_by_side(m5, [("win", "win rate [Wilson] positions")]))
F["m4info"] = md_table(pd.read_csv(OUT / "m4info.csv"))
F["m5info"] = md_table(pd.read_csv(OUT / "m5info.csv"))
sel = pd.read_csv(OUT / "selected.csv")
F["selected"] = md_table(sel.rename(columns={"selected": "variant", "eligible_variants": "eligible", "tune_markets": "tune mkts", "tune_trades": "tune trades", "tune_net_c": "tune net c/sh",
                                             "tune_t": "tune t", "tune_usd_day": "tune $/day", "rep_markets": "report mkts", "rep_trades": "report trades", "rep_net_c": "report net c/sh",
                                             "rep_se_c": "se", "rep_t": "report t", "rep_net_pct": "report % turn", "rep_usd_day": "report $/day", "rep_win": "report win rate"}))
F["sel_day"] = md_table(pd.read_csv(OUT / "extra_selected_by_day.csv"))
F["sel_pool"] = md_table(pd.read_csv(OUT / "extra_selected_pooled.csv"))
# D-gradient: mean net c/sh by delay, per series and period (average over the three thresholds, share-weighted)
m4 = r[r.family == "M4"]
gd = m4.assign(net=m4.net_c * m4.shares).groupby(["series", "period", "D"], sort=False)[["net", "shares"]].sum()
gd["c"] = gd.net / gd.shares
gw = gd.c.unstack("D").round(2).reset_index()
gw.columns = [str(x) if not isinstance(x, str) else x for x in gw.columns]
gw = gw.rename(columns={"0.0": "D=0", "1.0": "D=1", "2.0": "D=2", "5.0": "D=5"})
F["dgrad"] = md_table(gw)
for k, v in F.items():
    (OUT / f"frag_{k}.md").write_text(v + "\n")
print(F["m1"]); print(F["m2_period"]); print(F["m2_time"]); print(F["m2_price"]); print(F["dgrad"]); print(F["proxy"]); print(F["m5"][:1500])
