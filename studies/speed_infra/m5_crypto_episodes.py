"""m5: the stale-quote pool in BTC 5m up/down measured on the book's own repricing (no model).

All prints are converted to the Up price (buy Up p -> p; buy Down p -> 1-p; sell Up p -> p; sell Down p -> 1-p).
Per market, a "jump" starts at block-second T when the Up price of a print differs by >= JUMP from the last print
at least 2 s earlier, and the median Up price over (T+10 .. T+20] confirms the move (same direction, >= JUMP/2 from
the pre-jump price). After a jump starts, a taker print in [T, T+30] is a "stale take" if it bought in the jump's
direction at a price at least fee + 1 cent better than the confirmed reference (median of T+10..T+20; resolution
payoff if the window ended). Profit = shares x (reference - price) - fee (0.05). Buckets by seconds after T:
same second (0), 1-2 s, 3-10 s, 11-30 s. Wallet concentration on stale-take profit.
Block time has 1-2 s jitter: "same second" and "1-2 s" are not separable precisely; read them together.
Run: python3 -I m5_crypto_episodes.py
"""
import collections, json, statistics, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import pandas as pd  # noqa: E402

RATE, JUMP, MARGIN = 0.05, 0.05, 0.01
OUT = Path(__file__).resolve().parent / "out"
mk = pd.read_parquet(ROOT / "data/gaps_btc5m_lockin/full/markets.parquet").set_index("t0")
fee = lambda q: RATE * q * (1 - q)
files = sorted((ROOT / "data/tape_btc5m_nov").glob("btc-updown-5m-*.jsonl"))
B = ["0 s", "1-2 s", "3-10 s", "11-30 s"]
buck = {b: [0.0, 0.0, 0] for b in B}  # dollars, profit, prints
net = {b: [0.0, 0.0] for b in B}  # all takes in the jump direction: dollars, net markout
wal = collections.Counter()
first_wal = collections.Counter()
njump, nmk, tot_dollars = 0, 0, 0.0
for f in files:
    t0 = int(f.stem.split("-")[-1])
    if t0 not in mk.index or not bool(mk.loc[t0, "usable"]):
        continue
    up_won = bool(mk.loc[t0, "up_won"])
    nmk += 1
    rows = []
    for line in open(f):
        r = json.loads(line)
        if not (t0 <= r["t"] - 3 < t0 + 300):
            continue
        up = r["o"] == "Up"
        upp = r["p"] if up else 1 - r["p"]
        buy_up = (r["s"] == "BUY") == up  # taker direction in Up terms
        q = r["p"] if r["s"] == "BUY" else 1 - r["p"]  # price paid for the outcome it effectively bought
        rows.append((r["t"], upp, buy_up, q, r["z"], r["w"]))
        tot_dollars += r["z"] * q
    rows.sort(key=lambda x: x[0])
    ts = [x[0] for x in rows]
    used_until = -1
    i = 0
    import bisect
    while i < len(rows):
        T = rows[i][0]
        if T <= used_until:
            i += 1
            continue
        j = bisect.bisect_right(ts, T - 2) - 1
        if j < 0:
            i += 1
            continue
        pre = rows[j][1]
        d = rows[i][1] - pre
        if abs(d) < JUMP:
            i += 1
            continue
        a, b = bisect.bisect_right(ts, T + 10), bisect.bisect_right(ts, T + 20)
        if T + 20 - 3 >= t0 + 300 or a == b:
            ref = 1.0 if up_won else 0.0
        else:
            ref = statistics.median(x[1] for x in rows[a:b])
        if (ref - pre) * d <= 0 or abs(ref - pre) < JUMP / 2:
            i += 1
            continue
        njump += 1
        up_dir = d > 0
        k = i
        first = None
        while k < len(rows) and rows[k][0] <= T + 30:
            t, upp, buy_up, q, z, w = rows[k]
            if buy_up == up_dir:
                a2, b2 = bisect.bisect_right(ts, t + 10), bisect.bisect_right(ts, t + 20)
                fref = (1.0 if up_won else 0.0) if (t + 20 - 3 >= t0 + 300 or a2 == b2) else statistics.median(x[1] for x in rows[a2:b2])
                val = fref if up_dir else 1 - fref
                nb = "0 s" if t == T else "1-2 s" if t - T <= 2 else "3-10 s" if t - T <= 10 else "11-30 s"
                net[nb][0] += z * q
                net[nb][1] += z * (val - q - fee(q))
                if val - q >= fee(q) + MARGIN:
                    dt = t - T
                    bb = "0 s" if dt == 0 else "1-2 s" if dt <= 2 else "3-10 s" if dt <= 10 else "11-30 s"
                    p = z * (val - q - fee(q))
                    buck[bb][0] += z * q
                    buck[bb][1] += p
                    buck[bb][2] += 1
                    wal[w] += p
                    if first is None:
                        first = w
            k += 1
        if first:
            first_wal[first] += 1
        used_until = T + 30
        i = k

days = 6.0
sc = 288 / (nmk / days)
P = sum(v[1] for v in buck.values())
D = sum(v[0] for v in buck.values())
L = [f"markets {nmk} BTC 5m (21-26 Nov 2026 cached tapes); all taker dollars {tot_dollars:,.0f}; confirmed jumps "
     f"(>= {JUMP} Up-price) {njump} ({njump/nmk:.1f} per market)",
     f"stale takes after jumps: dollars {D:,.0f}, profit after 0.05 fee {P:,.0f}; per day scaled to 288 windows: "
     f"dollars {D/days*sc:,.0f}, profit {P/days*sc:,.0f}",
     "stale takes only (forward markout >= fee + 1c): seconds after the first jump print | dollars | profit $ | prints | share"]
for b in B:
    L.append(f"{b} | {buck[b][0]:,.0f} | {buck[b][1]:,.0f} | {buck[b][2]} | {buck[b][1]/P:.2f}")
L.append("ALL takes in the jump direction (winners and losers), forward markout t+10..t+20 s: bucket | dollars | net $")
for b in B:
    L.append(f"{b} | {net[b][0]:,.0f} | {net[b][1]:,.0f}")
tw = sorted(wal.items(), key=lambda x: -x[1])
pos = sum(v for _, v in tw if v > 0)
L.append(f"wallets with a stale take {len(tw)}; top1/top3/top10 share of profit {tw[0][1]/pos:.2f} / "
         f"{sum(v for _, v in tw[:3])/pos:.2f} / {sum(v for _, v in tw[:10])/pos:.2f}")
L.append("top 10 by profit: " + ", ".join(f"{w} {v:,.0f}" for w, v in tw[:10]))
L.append(f"distinct first takers {len(first_wal)}; most frequent: " + ", ".join(f"{w} {c}" for w, c in first_wal.most_common(5)))
open(OUT / "m5_crypto_episodes.txt", "w").write("\n".join(L) + "\n")
print("\n".join(L))
