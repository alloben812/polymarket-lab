"""m4: size and timing of the stale-quote pool in BTC 5m up/down (cached tapes, 278 markets, 21-26 Nov 2026).

A taker print is a "stale take" when, at its match time m = block time - 3 s, the Binance-based model value of the
bought outcome (pmlab.fair.fair_up, toolkit defaults) exceeds the price paid by at least the taker fee + 2 cents.
For each stale take: model edge $, realised P&L $ (official outcome, fee 0.05), and the "age": how many whole
seconds before m the same price was already stale by the same test (0 = it became stale in the same second).
Concentration: share of realised stale-take profit by taker wallet (short id on the cached tape).
Caveats: 1 s Binance closes; block time has 1-2 s jitter (median lag 2.09 s, NOTES); the model is the toolkit
model with its known ~4.5 s lateness; this is a descriptive estimate, not a rule.
Run: python3 -I m4_crypto_pool.py  (from this folder; needs the repo on sys.path)
"""
import collections, json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import pandas as pd  # noqa: E402
from pmlab import fair, px as pxmod  # noqa: E402

RATE, THR = 0.05, 0.02
OUT = Path(__file__).resolve().parent / "out"
mk = pd.read_parquet(ROOT / "data/gaps_btc5m_lockin/full/markets.parquet").set_index("t0")
px = pxmod.Px.load("BTCUSDT", ["2026-11-20", "2026-11-21", "2026-11-22", "2026-11-23", "2026-11-24", "2026-11-25",
                               "2026-11-26", "2026-11-27"], fetch=False)
fee = lambda q: RATE * q * (1 - q)
files = sorted((ROOT / "data/tape_btc5m_nov").glob("btc-updown-5m-*.jsonl"))
tot = collections.Counter()
age_b = collections.defaultdict(lambda: [0.0, 0.0, 0.0])  # bucket -> [dollars, model edge $, realised $]
wal = collections.Counter()
phase_b = collections.defaultdict(lambda: [0.0, 0.0, 0.0])
nmk = 0
for f in files:
    t0 = int(f.stem.split("-")[-1])
    if t0 not in mk.index or not bool(mk.loc[t0, "usable"]):
        continue
    up_won = bool(mk.loc[t0, "up_won"])
    nmk += 1
    cache = {}

    def fu(t):
        if t not in cache:
            cache[t] = fair.fair_up(px, t, t0)
        return cache[t]

    for line in open(f):
        r = json.loads(line)
        m = r["t"] - 3
        if m < t0 or m >= t0 + 300:
            continue
        o_up = r["o"] == "Up"
        if r["s"] == "BUY":
            b_up, q = o_up, r["p"]
        else:  # taker sold outcome o at p == bought the other outcome at 1 - p
            b_up, q = (not o_up), 1 - r["p"]
        z = r["z"]
        tot["dollars"] += z * q
        tot["prints"] += 1
        f_up = fu(m)
        if f_up != f_up:
            continue
        val = f_up if b_up else 1 - f_up
        thr = fee(q) + THR
        if val - q < thr:
            continue
        age = 0
        while age < 60:
            g = fu(m - age - 1)
            if g != g or ((g if b_up else 1 - g) - q) < thr or m - age - 1 < t0:
                break
            age += 1
        pay = 1.0 if (b_up == up_won) else 0.0
        real = z * (pay - q - fee(q))
        edge = z * (val - q - fee(q))
        tot["stale_dollars"] += z * q
        tot["stale_edge"] += edge
        tot["stale_real"] += real
        tot["stale_prints"] += 1
        b = "0 s" if age == 0 else "1-2 s" if age <= 2 else "3-10 s" if age <= 10 else ">10 s"
        for i, v in enumerate((z * q, edge, real)):
            age_b[b][i] += v
        ph = "first 240 s" if m < t0 + 240 else "last 60 s"
        for i, v in enumerate((z * q, edge, real)):
            phase_b[ph][i] += v
        wal[r["w"]] += real

days = 6.0
lines = [f"markets {nmk} (of 1,728 BTC 5m windows 21-26 Nov; tapes cached for these only); per-day figures scale"
         f" by 288 windows/day: factor {288/ (nmk/days):.2f}",
         f"all taker prints {tot['prints']:,}  dollars {tot['dollars']:,.0f}",
         f"stale takes (model value - price >= fee + {THR}): prints {tot['stale_prints']:,}  dollars {tot['stale_dollars']:,.0f}"
         f"  model edge after fee {tot['stale_edge']:,.0f}  realised after fee {tot['stale_real']:,.0f}"]
sc = 288 / (nmk / days)
lines.append(f"per day, all BTC 5m windows (scaled): stale dollars {tot['stale_dollars']/days*sc:,.0f}  model edge "
             f"{tot['stale_edge']/days*sc:,.0f}  realised {tot['stale_real']/days*sc:,.0f}")
lines.append("age of the stale quote when taken | dollars | model edge $ | realised $ | share of realised")
for b in ["0 s", "1-2 s", "3-10 s", ">10 s"]:
    d, e, rr = age_b[b]
    lines.append(f"{b} | {d:,.0f} | {e:,.0f} | {rr:,.0f} | {rr/max(tot['stale_real'],1e-9):.2f}")
for b, (d, e, rr) in phase_b.items():
    lines.append(f"phase {b} | {d:,.0f} | {e:,.0f} | {rr:,.0f}")
tw = sorted(wal.items(), key=lambda x: -x[1])
pos = sum(v for _, v in tw if v > 0)
lines.append(f"taker wallets with a stale take {len(tw)}; positive-sum {pos:,.0f}; top1/top3/top10 share of positive "
             f"{tw[0][1]/pos:.2f} / {sum(v for _,v in tw[:3])/pos:.2f} / {sum(v for _,v in tw[:10])/pos:.2f}")
lines.append("top 10: " + ", ".join(f"{w} {v:,.0f}" for w, v in tw[:10]))
open(OUT / "m4_crypto_pool.txt", "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
