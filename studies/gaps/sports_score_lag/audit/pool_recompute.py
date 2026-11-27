"""Audit: recompute the stale-pool headline (soccer, from first +3c print; $ bought at <= halfway, by seconds after
the first move; wallets >= 4 s). Independent code. Also checks the own-goal direction and fee scale."""
import statistics, sys, bisect
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from recompute import games, tape, conv, sl, fav
from collections import defaultdict
tot = 0; b = defaultdict(float); w4 = set(); wall = set(); nem = 0; ngm = set(); big = defaultdict(float)
own = []
for g in games:
    if g["sport"] != "soccer": continue
    tp = {k: tape(m["cid"]) for k, m in g["markets"].items()}
    ev = g["events"]
    for i, e in enumerate(ev):
        te = e["t"]
        if i and te - ev[i - 1]["t"] < 180: continue
        for k, m in g["markets"].items():
            tok = fav(g, k, e); c = conv(tp[k], tok); ts = [x[0] for x in c]
            pre = sl(c, ts, te - 120, te - 10)
            if not pre: continue
            pp = statistics.median(x[1] for x in pre)
            if not .05 <= pp <= .95: continue
            post = sl(c, ts, te + 120, te + 300)
            if not post: continue
            J = statistics.median(x[1] for x in post) - pp
            tm = next((x[0] for x in sl(c, ts, te - 30, te + 300) if x[1] >= pp + .03), None)
            if tm is None or J < .05: continue
            nem += 1; ngm.add(g["event"])
            half = pp + J / 2
            if "Own Goal" in e["text"] and k != "draw":
                own.append((g["event"], k, round(pp, 3), round(statistics.median(x[1] for x in post), 3)))
            for x in sl(c, ts, tm, te + 300):
                if x[2] and x[1] <= half:
                    usd = x[4] * x[1]; dt = x[0] - tm
                    tot += usd; wall.add(x[5])
                    b["0-1" if dt <= 1 else "2-3" if dt <= 3 else "4+"] += usd
                    if dt >= 4: w4.add(x[5])
print(f"soccer event-markets {nem} in {len(ngm)} games; stale $ {tot:,.0f}; 0-1s {b['0-1']:,.0f} ({b['0-1']/tot:.0%}); 2-3s {b['2-3']:,.0f}; >=4s {b['4+']:,.0f}; wallets all {len(wall)}, >=4s {len(w4)}")
print("own goals (market favoured-token pre -> post, expect rise):", own)
