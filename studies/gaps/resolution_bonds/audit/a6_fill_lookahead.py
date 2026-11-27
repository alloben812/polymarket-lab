"""Audit a6: (1) is the 5-minute bucket at t a snapshot at t (no look-ahead)? compare with tape prices of the
favourite token just before and just after t; (2) depth at the first-print price: other takers' dollars at <= that
price in the 30 s after it; (3) was the first print part of a sweep (same second, several prices)?"""
import gzip, json, pickle, statistics as st
from pathlib import Path
D = Path("/home/user/polymarket-lab/data/gaps_resolution_bonds"); OUT = Path(__file__).resolve().parent
E = [e for e in pickle.load(open(OUT / "a1_entries.pkl", "rb")) if e["fam"] == "crypto"]
pre, post, post2, late = [], [], [], []
depth, sweep, n1 = [], 0, 0
for e in E:
    d = json.load(gzip.open(D / "tapes" / f"{e['cid']}.json.gz", "rt"))
    # implied price of the favourite token from every row (complement rows mirrored)
    rows = sorted((r[0], r[3] if r[2] == e["tok"] else 1 - r[3], r) for r in d["rows"])
    def med(a, b):
        v = [p for t, p, _ in rows if a <= t < b]
        return st.median(v) if v else None
    # all windows must have prints for a like-for-like comparison
    w = [med(e["t"] - 60, e["t"]), med(e["t"], e["t"] + 60), med(e["t"] + 60, e["t"] + 180), med(e["t"] + 240, e["t"] + 300)]
    if all(x is not None for x in w):
        pre.append(abs(w[0] - e["p"])); post.append(abs(w[1] - e["p"])); post2.append(abs(w[2] - e["p"])); late.append(abs(w[3] - e["p"]))
    buys = sorted((r[0], r[3], r[4], r[5]) for r in d["rows"] if r[1] == "BUY" and r[2] == e["tok"])
    f = next(((t, p, s, wl) for t, p, s, wl in buys if t >= e["t"] + 10 and t <= e["closed"] and 0.95 - 1e-9 <= p < 0.98 - 1e-9), None)
    if not f: continue
    n1 += 1
    t0, p0, s0, w0 = f
    same_sec = {p for t, p, s, wl in buys if t == t0 and wl == w0}
    sweep += len(same_sec) > 1
    other = sum(p * s for t, p, s, wl in buys if t0 < t <= t0 + 30 and p <= p0 + 1e-9 and wl != w0)
    depth.append(other)
print(f"bucket vs tape, |median implied price - bucket| (markets with prints in all four windows: {len(pre)}):")
print(f"  [t-60,t) {st.median(pre):.4f}   [t,t+60) {st.median(post):.4f}   [t+60,t+180) {st.median(post2):.4f}   [t+240,t+300) {st.median(late):.4f}")
depth.sort()
print(f"first prints {n1}; part of a multi-price sweep by the same wallet in the same second: {sweep}")
print(f"other takers' USD at <= first-print price within 30 s after it: median {depth[len(depth)//2]:.1f}, share with >= 10 USD {sum(x>=10 for x in depth)/len(depth):.2f}, share zero {sum(x==0 for x in depth)/len(depth):.2f}")
