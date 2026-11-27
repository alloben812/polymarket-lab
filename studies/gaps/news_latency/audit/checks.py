"""Auditor's data and fee checks (own code). Usage: python3 -I checks.py"""
import json, glob, gzip, sys, datetime as dt
from collections import Counter
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import recompute as R
mk, res, js, conf = R.main()
main2 = [j for j in conf if j["status"] == "main" and j["label"] == "unscheduled" and j["t0"] >= R.SPLIT]
# tape completeness and duplicates
metas = [json.load(open(p)) for p in glob.glob(str(R.DATA / "tapes" / "*.meta.json"))]
print("tape metas", len(metas), "reached_stop false", sum(not m["reached_stop"] for m in metas), "rows>=600000", sum(m["rows"] >= 600000 for m in metas))
dup = tot = 0
for c in {j["c"] for j in main2}:
    tp = R.tape(c)
    keys = Counter((r["t"], r["s"], r["i"], r["z"], r["p"], r["w"], r["x"]) for r in tp)
    dup += sum(v - 1 for v in keys.values()); tot += len(tp)
print("main2 markets tape rows", tot, "exact duplicate rows", dup)
# fee rates used
print("fee rates main2", Counter((j["cat"], j["rate"]) for j in main2))
# hand fee check: 3 fills with non-zero rate
n = 0
for j in main2:
    if j["rate"] == 0: continue
    tp = R.tape(j["c"])
    for r in tp:
        if r["t"] < j["tb"] + 30: continue
        p = R.offer_F(r, j["fidx"])
        if p is None or p > 0.9: continue
        q = min(r["z"], 200 / p)
        print("fee check", j["q"][:50], "rate", j["rate"], "p", round(p, 4), "q", round(q, 2), "fee", round(j["rate"] * p * (1 - p) * q, 4), "dt", r["t"] - j["tb"], "payoff", j["payoff"])
        n += 1
        break
    if n >= 3: break
# top contributors at d=30
per = sorted(((R.rule(j, 30)["net"], j["q"][:60], dt.datetime.utcfromtimestamp(j["t0"]).strftime('%m-%d %a %H:%M'), j["cl"]) for j in main2), reverse=True)
for x in per[:8]: print("top", round(x[0]), x[1:])
for x in per[-5:]: print("bottom", round(x[0]), x[1:])
# avg entry vs win rate on fills
