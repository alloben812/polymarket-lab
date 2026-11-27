"""Diagnostics added AFTER the protocol (not trading rules, no new variants). See results.md, 'Post-hoc diagnostics'.

1. Time alignment of the Binance proxy with the official average: proxy error when the Binance 60 s TWAP is ended
   s seconds earlier/later (same shift at both ends of the window), tuning and reporting periods.
2. Where the losses of the runs come from (uses out/variants.csv and the trade file written by analyze.py).
"""
import json

import numpy as np
import pandas as pd

from common import EXTRACT, OUT, SPLIT, load_px

px = load_px()
mk = pd.read_parquet(EXTRACT / "markets.parquet").dropna(subset=["ptb", "final"])
lines = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    lines.append(s)


say("== Proxy error vs shift s of the Binance TWAP end (px.twap(t + s, 60)), USD ==")
say("shift | all: sd, p99|err|, proxy-miss rate | tune sd | report sd")
up = mk.up_won.astype(bool).values
for s in range(-10, 3):
    k = np.array([px.twap(t0 + s, 60) for t0 in mk.t0])
    a = np.array([px.twap(t0 + 300 + s, 60) for t0 in mk.t0])
    e = (a - mk.final.values) - (k - mk.ptb.values)
    tu = mk.t0.values < SPLIT
    miss = np.mean((a >= k) != up)
    say(f"{s:+3d} | {e.std():6.2f} {np.percentile(np.abs(e), 99):6.2f} {miss:.4f} | {e[tu].std():6.2f} | {e[~tu].std():6.2f}")

tr = pd.read_parquet(EXTRACT / "trades_all_variants.parquet")
summ = json.load(open(OUT / "summary.json"))
say("\n== Losing markets per run: when was the bet placed and how far was the Binance average from the strike ==")
for v in [summ["judged"], summ["judged"].replace("_excl", "_all")]:
    e = tr[tr.variant == v].copy()
    e["t1"] = e.t0 + 300
    e["left"] = e.t1 - e.m
    e["period"] = np.where(e.t0 < SPLIT, "tune", "report")
    lost = e[e.win == 0]
    say(f"\n{v}: trades {len(e)}, losing trades {len(lost)}, losing markets {lost.t0.nunique()}")
    g = lost.groupby(["period", "t0"]).agg(trades=("size", "count"), shares=("size", "sum"), net=("net", "sum"), q=("bq", "mean"), f=("f", "mean"),
                                           dist=("dist", "mean"), left=("left", "mean"), proxy_miss=("proxy_miss", "first"))
    with pd.option_context("display.width", 200, "display.max_rows", 200, "display.float_format", "{:.3f}".format):
        say(g.to_string())
(OUT / "diag.txt").write_text("\n".join(lines) + "\n")
