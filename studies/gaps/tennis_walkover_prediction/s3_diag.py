"""Step 3 (diagnostics, no new trading variant): where the class A walkovers went, and the outcome-free bound
premium = q x mean(0.5 - p) versus the mean taker fee, per feature and price band."""
from __future__ import annotations

import collections
import json

import s2_analyse as S

ROWS = S.ROWS
A = [r for r in ROWS if r["cls"] == "A"]
c = collections.Counter()
for r in A:
    if not r["tape"]:
        c["no tape (never traded)"] += 1
    elif r["elig"]:
        c["eligible (underdog print 0.05-0.45 in T-6h..T-1h)"] += 1
    elif r.get("n_prints_before_T", 0) == 0:
        c["tape but no print before scheduled start"] += 1
    else:
        c["prints before start, none 0.05-0.45 in window"] += 1
print("Class A moneylines (830):", dict(c))

# when did the book move, for A with a hindsight t_first from the finished study
ev = {e["slug"]: e for e in json.load(open("/home/user/polymarket-lab/studies/gaps/tennis_walkover/out/events_A.json"))}
k = next(iter(ev.values()))
print("events_A keys:", list(k.keys())[:30])


def bound(rs, label):
    W = sum(r["w"] for r in rs)
    if not W:
        return
    q = sum(r["w"] * r["wo"] for r in rs) / W
    d = sum(r["w"] * (0.5 - r["p"]) for r in rs) / W
    prem = sum(r["w"] * (0.5 - r["p"]) for r in rs if r["wo"]) / W
    f = sum(r["w"] * S.fee(r["p"]) for r in rs) / W
    need = f / d if d else float("nan")
    print(f"{label:30s} n={len(rs):4d} wo={sum(r['wo'] for r in rs):3d} q={q*100:4.1f}% premium {prem*100:+.2f}c fee {f*100:.2f}c "
          f"premium-fee {100*(prem-f):+.2f}c | q needed {need*100:.1f}% (lift {need/0.0200:.1f}x)")


print("\nOutcome-free bound (assumes underdogs are otherwise fairly priced):")
for part in ("early", "late", "all"):
    rs = [r for r in S.EL if part == "all" or r["part"] == part]
    bound(rs, f"V0 {part}")
for lo, hi in ((0.05, 0.15), (0.15, 0.30), (0.30, 0.4501)):
    bound([r for r in S.EL if lo <= r["p"] < hi], f"band {lo:.2f}-{hi:.2f}")
for f in S.FEATS:
    for part in ("early", "late"):
        bound([r for r in S.EL if r["F"][f] and r["part"] == part], f"{f} {part}")
