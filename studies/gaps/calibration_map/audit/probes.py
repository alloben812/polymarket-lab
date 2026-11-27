import collections, json, math, re, gzip
from recompute import *
rows = run()
# 1. updown families: where does the used price sit relative to window start?
for fam, dur in (("updown-15m", 900), ("updown-1h", 3600), ("updown-4h", 14400)):
    print("==", fam)
    for H in HZ:
        rs = [r for r in rows if r["fam"] == fam and r["H"] == H]
        if not rs: continue
        # price time = anchor - H - tdiff ; window start = anchor - dur
        rel = sorted((r["anchor"] - H - r["tdiff"]) - (r["anchor"] - dur) for r in rs)
        inwin = sum(1 for x in rel if x > 0) / len(rs)
        bk = collections.Counter(min(int((r["pf"]-0.5)*10),4) for r in rs)
        print(H, "n", len(rs), "share of used prices inside window", round(inwin, 3), "median s rel to start", rel[len(rel)//2],
              "mean pf", round(sum(r["pf"] for r in rs)/len(rs), 3), "share pf<0.6", round(sum(1 for r in rs if r["pf"]<0.6)/len(rs),3))
