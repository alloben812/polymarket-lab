"""Post-hoc timing check, stage B (diagnostic, not a rule variant): real match times of tape prints on 21-22 Nov.

1. Block-time lag: tape rows matched one-to-one to WebSocket trade events (same outcome token, side, size, price).
2. For the prints the exclusion-ON runs traded: was the rule condition already true on Binance at the real match
   time minus d seconds (d = 0, 1, 2), i.e. could a trader who saw Binance first have sent that order?
"""
import json
import subprocess
import sys

import numpy as np
import pandas as pd

from common import DATA, EXTRACT, OUT, load_px, meta, model_at
from pmlab import updown

lines = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    lines.append(s)


mk = pd.read_parquet(EXTRACT / "markets.parquet")
cond_file = DATA / "conditions.json"
json.dump(list(mk.condition), open(cond_file, "w"))
ws_path = DATA / "ws_trades_btc5m.parquet"
if not ws_path.exists():
    subprocess.run([sys.executable, "-I", str(OUT.parent / "ws_extract.py"), str(DATA / "ithiria_trades"), str(cond_file), str(ws_path)], check=True)
ws = pd.read_parquet(ws_path)
say(f"WS trade events for our BTC 5m markets: {len(ws)} rows, {ws.market.nunique()} markets")
px = load_px()
summ = json.load(open(OUT / "summary.json"))
E99 = summ["E99"]
tr = pd.read_parquet(EXTRACT / "trades_all_variants.parquet")
t0_of = dict(zip(mk.condition, mk.t0))

match_rows = []  # (t0, seq, bt, ev_ts)
cover = []
for cond, g in ws.groupby("market"):
    t0 = int(t0_of[cond])
    m = meta(t0)
    tok = {v: k for k, v in m["tokens"].items()}
    g = g.assign(o=g.asset_id.map(tok))
    rows = updown.tape(cond)
    t1 = t0 + 300
    # index WS events by (outcome, side, size rounded, price rounded)
    idx = {}
    for o, s, z, p, ev in zip(g.o, g.side, g["size"], g.price, g.ev_ts):
        idx.setdefault((o, s, round(z, 3), round(p, 3)), []).append(ev)
    tape_idx = {}
    for seq, r in enumerate(rows):
        tape_idx.setdefault((r["o"], r["s"], round(r["z"], 3), round(r["p"], 3)), []).append(seq)
    n_in = n_match = 0
    for seq, r in enumerate(rows):
        if not (t0 <= r["t"] <= t1 + 10):
            continue
        n_in += 1
        key = (r["o"], r["s"], round(r["z"], 3), round(r["p"], 3))
        evs = idx.get(key, [])
        cands = [ev for ev in evs if r["t"] - 20 <= ev / 1000 <= r["t"] + 1]
        # one-to-one only: exactly one WS event and exactly one tape row with this key near this time
        twins = [s2 for s2 in tape_idx[key] if abs(rows[s2]["t"] - r["t"]) <= 20]
        if len(cands) == 1 and len(twins) == 1:
            n_match += 1
            match_rows.append((t0, seq, r["t"], cands[0], r["t"] - t1))
    cover.append((t0, n_in, n_match, len(g)))
mt = pd.DataFrame(match_rows, columns=["t0", "seq", "bt", "ev_ts", "bt_rel_end"])
cv = pd.DataFrame(cover, columns=["t0", "tape_rows", "matched", "ws_rows"])
mt["lag"] = mt.bt - mt.ev_ts / 1000.0
say(f"markets with WS coverage: {len(cv)}; tape rows in window {int(cv.tape_rows.sum())}, WS events {int(cv.ws_rows.sum())}, one-to-one matched {len(mt)} ({len(mt) / cv.tape_rows.sum():.1%})")
pc = [1, 5, 25, 50, 75, 95, 99]
say("block time minus exchange match time, seconds, percentiles", pc, ":", np.round(np.percentile(mt.lag, pc), 2).tolist(), f"mean {mt.lag.mean():.2f}")
say("  share with lag > 3 s: %.3f; > 4 s: %.3f; > 5 s: %.3f; > 6 s: %.3f; < 2 s: %.3f" % (tuple((mt.lag > x).mean() for x in (3, 4, 5, 6)) + ((mt.lag < 2).mean(),)))
late = mt[(mt.bt_rel_end >= -57)]  # last minute of the window
say("  last 60 s only:", np.round(np.percentile(late.lag, pc), 2).tolist(), f"n {len(late)}")

say("\n== Traded prints of the exclusion-ON runs with a real match time ==")
for v, floor, margin in [(summ["judged"], float(summ["judged"].split("_f")[1].split("_")[0]), 0.02), ("L60_f0.97_m0.02_D1_excl", 0.97, 0.02),
                         ("L60_f0.97_m0.02_D2_excl", 0.97, 0.02)]:
    e = tr[tr.variant == v].merge(mt[["t0", "seq", "ev_ts", "lag"]], on=["t0", "seq"], how="inner")
    allv = tr[(tr.variant == v) & tr.t0.isin(cv.t0)]
    if e.empty:
        say(v, "no matched prints")
        continue
    say(f"\n{v}: traded prints in WS-covered markets {len(allv)} ({allv.t0.nunique()} markets), with a one-to-one real match time {len(e)} ({e.t0.nunique()} markets, {e['size'].sum():.0f} shares)")
    say("  lag of these prints, s (min/10/25/50/75/90/max):", np.round(np.percentile(e.lag, [0, 10, 25, 50, 75, 90, 100]), 2).tolist())
    say("  real match time minus assumed match time m, s:", np.round(np.percentile(e.ev_ts / 1000 - e.m, [0, 10, 25, 50, 75, 90, 100]), 2).tolist())
    for d in (0, 1, 2, 3):
        ok = []
        for t0, ev, up, q in zip(e.t0, e.ev_ts, e.b_up, e.bq):
            tm = int(ev // 1000) - 1 - d  # last kline fully closed by (real match time - d)
            f, ea, k = model_at(px, tm, int(t0))
            ff = f if up else 1 - f
            ok.append(bool(ff >= floor and q <= ff - margin + 1e-9 and abs(ea - k) >= E99))
        ok = np.array(ok)
        g = e.assign(ok=ok)
        say(f"  rule condition true on Binance data closed by (real match time - {d} s): {ok.mean():.2f} of prints, {g.loc[g.ok, 'size'].sum() / g['size'].sum():.2f} of shares, "
            f"markets with at least one such print {g[g.ok].t0.nunique()} of {g.t0.nunique()}; net of those prints {g.loc[g.ok, 'net'].sum():.1f} USD of {g.net.sum():.1f}")
(OUT / "ws_timing.txt").write_text("\n".join(lines) + "\n")
