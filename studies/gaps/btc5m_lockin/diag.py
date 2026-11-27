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

# ---------------------------------------------------------------- 3. what the winning trades of the exclusion-ON runs look like
from common import model_at, meta  # noqa: E402
from pmlab import updown  # noqa: E402

E99 = summ["E99"]


def signal_age(t0: int, t: int, fav_up: bool, floor: float, max_age: int = 60) -> int:
    """Seconds (before model time t) for which the same side already had f >= floor and |EA - K| >= E99."""
    n = 0
    for s in range(t - 1, t - 1 - max_age, -1):
        f, ea, k = model_at(px, s, t0)
        ff = f if fav_up else 1 - f
        if not (ff >= floor and abs(ea - k) >= E99):
            break
        n += 1
    return n


def q5(x):
    return np.round(np.percentile(x, [0, 10, 25, 50, 75, 90, 100]), 3).tolist()


say("\n== Anatomy of the trades in the exclusion-ON runs (percentiles are min/10/25/50/75/90/max) ==")
for v, floor, D in [(summ["judged"], float(summ["judged"].split("_f")[1].split("_")[0]), 1), ("L60_f0.97_m0.02_D1_excl", 0.97, 1), ("L60_f0.97_m0.02_D2_excl", 0.97, 2)]:
    e = tr[tr.variant == v].copy()
    if e.empty:
        continue
    e["t1"] = e.t0 + 300
    e["left"] = e.t1 - e.m
    e["tm"] = e.m - D - 1
    e["age"] = [signal_age(int(a), int(b), bool(c), floor) for a, b, c in zip(e.t0, e.tm, e.b_up)]
    e["mv3"] = [(px.price(int(t)) - px.price(int(t) - 3)) * (1 if u else -1) for t, u in zip(e.tm, e.b_up)]
    e["mv10"] = [(px.price(int(t)) - px.price(int(t) - 10)) * (1 if u else -1) for t, u in zip(e.tm, e.b_up)]
    say(f"\n{v}: trades {len(e)}, markets {e.t0.nunique()}, shares {e['size'].sum():.0f}, wins {int(e.win.sum())}")
    say("  seconds left at the print:", q5(e.left))
    say("  price paid:", q5(e.bq), " model f:", q5(e.f))
    say("  |EA - K| USD:", q5(e.dist), f" trades with dist < E99_tune ({summ['E99_tune']:.2f}): {int((e.dist < summ['E99_tune']).sum())}")
    say("  signal age, s (how long the rule condition already held on Binance before the model time):", q5(e.age))
    say(f"  share of shares with signal age <=1 s: {e.loc[e.age <= 1, 'size'].sum() / e['size'].sum():.2f}; <=3 s: {e.loc[e.age <= 3, 'size'].sum() / e['size'].sum():.2f}; >=10 s: {e.loc[e.age >= 10, 'size'].sum() / e['size'].sum():.2f}")
    say("  Binance move in favoured direction over the 3 s before model time, USD:", q5(e.mv3), " over 10 s:", q5(e.mv10))
    g = e.groupby("t0").agg(n=("size", "count"), sh=("size", "sum"), first=("m", "min"), last=("m", "max"), secs=("m", "nunique"), net=("net", "sum"),
                            age_first=("age", "first"), q=("bq", "mean"))
    say("  per market: trades", q5(g.n), " shares", q5(g.sh), " distinct seconds with fills", q5(g.secs), " span s", q5(g["last"] - g["first"]))
    say("  per market: signal age at the first fill", q5(g.age_first), " net USD", q5(g.net))
    say(f"  markets filled to the 500-share cap: {int((g.sh >= 499.99).sum())}; markets with fills in >= 5 distinct seconds: {int((g.secs >= 5).sum())}")
    say(f"  markets where the first fill came when the signal was >= 5 s old: {int((g.age_first >= 5).sum())} of {len(g)}")
    by_day = e.assign(day=((e.t0 - 1795219200) // 86400 + 21)).groupby("day").agg(markets=("t0", "nunique"), shares=("size", "sum"), net=("net", "sum"))
    say("  by day (Nov):", by_day.round(1).to_dict("index"))
    # who took these prints in reality
    key = set(zip(e.t0, e.seq))
    wal = {}
    for t0 in e.t0.unique():
        rows = updown.tape(meta(int(t0))["condition"])
        for seq, r in enumerate(rows):
            if (t0, seq) in key:
                wal[r["w"]] = wal.get(r["w"], 0.0) + r["z"]
    tot = sum(wal.values())
    top = sorted(wal.values(), reverse=True)
    say(f"  real takers behind these prints: {len(wal)} wallets; top 1 / 3 / 10 took {top[0]/tot:.2f} / {sum(top[:3])/tot:.2f} / {sum(top[:10])/tot:.2f} of the printed size")
    side = e.assign(s=[1 if x else 0 for x in e.b_up]).groupby("t0").s.first()
    say(f"  markets by side bought: Up {int(side.sum())}, Down {int((1 - side).sum())}")
(OUT / "diag.txt").write_text("\n".join(lines) + "\n")
