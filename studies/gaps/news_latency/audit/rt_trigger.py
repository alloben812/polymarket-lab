"""Auditor: the zero-money real-time trigger that results.md proposes as the next step, run on the cached tapes of the
321 screened markets. Trigger: a print (notional >= $5) whose YES price is >= 0.10 away from the last print of the
previous 30 minutes; side = direction; buy at offer prints <= 0.90 from trigger + 3 s for 60 s, $20 cap; hold to
settlement; one trigger per market per 30 min. Only volumeNum >= 50K markets (all are). Usage: python3 -I rt_trigger.py"""
import bisect, json, sys, datetime as dt
from collections import defaultdict
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import recompute as R
mk = R.load_markets()
res = json.load(open(R.STUDY / "out" / "resolutions.json"))
cids = sorted({c["c"] for c in json.load(open(R.STUDY / "out" / "candidates.json"))})
trig = []
for cid in cids:
    tp = R.tape(cid); m = mk[cid]
    if not tp: continue
    r_ = res.get(cid) or {}; o = R.jl(m["outcomes"]); fin = r_.get("final") or {}
    sy = float(fin[o[0]]) if r_.get("resolved") and fin.get(o[0]) is not None else None
    try: my = float(R.jl(m["outcomePrices"])[0])
    except Exception: my = None
    py = sy if sy is not None else my
    if py is None: continue
    lastt = -10**12
    for k in range(1, len(tp)):
        r, pr = tp[k], tp[k - 1]
        t = r["t"]
        if t < R.W0 or t >= R.W1 or t - lastt < 1800 or pr["t"] < t - 1800 or r["z"] * r["p"] < 5: continue
        dy = R.yes_price(r) - R.yes_price(pr)
        if abs(dy) < 0.10: continue
        up = dy > 0; lastt = t
        trig.append({"c": cid, "fidx": 0 if up else 1, "tb": t, "t0": t - 3, "rate": R.rate_of(m), "cat": R.cat_of(m),
                     "payoff": py if up else 1 - py, "event": ((m.get("events") or [{}])[0] or {}).get("slug") or cid})
R.clusters(trig)
for half, f in (("first", lambda t: t["t0"] < R.SPLIT), ("second", lambda t: t["t0"] >= R.SPLIT)):
    for cat in ("all", "non-elections"):
        s = [t for t in trig if f(t) and (cat == "all" or t["cat"] != "elections")]
        out = R.summarize(s, 3, budget=20, window=60)
        print("proposed RT trigger", half, cat, out)
s2 = [t for t in trig if t["t0"] >= R.SPLIT]
print("second-half days 43, triggers/day", round(len(s2) / 43, 1), "fills/day", round(sum(R.rule(t, 3, budget=20, window=60)["sh"] > 0 for t in s2) / 43, 1))
