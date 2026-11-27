"""Auditor's attacks on the news_latency headline (own code; uses only recompute.py from this folder).
Usage: python3 -I attacks.py"""
import datetime as dt, json, math, statistics, sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import recompute as R

mk, res, js, conf = R.main()
SPLIT = R.SPLIT
sec = lambda j: j["t0"] >= SPLIT
out = {}


def line(name, s):
    out[name] = s
    print(f"{name:70s} n={s['n']:4d} mk={s['mk']:4d} units={s['units']:4d} fill={s['fill']:4d} spent={s['spent']:6d} "
          f"net={s['net']:+6d} t_cl={s['t_cl']} t_day={s['t_day']}" + (f" ci={s.get('ci')}" if 'ci' in s else ""))


main2 = [j for j in conf if j["status"] == "main" and j["label"] == "unscheduled" and sec(j)]

# 1. resolved-only and payoff distribution
print("payoffs main2", Counter(round(j["payoff"], 2) if not j["resolved"] else j["payoff"] for j in main2))
print("unresolved in main2", sum(not j["resolved"] for j in main2))
for d in (30, 120):
    line(f"main2 resolved only d={d}", R.summarize([j for j in main2 if j["resolved"]], d))

# 2. drop best day / best 10 markets
for d in (30, 120):
    per = [(j, R.rule(j, d)["net"]) for j in main2]
    byday = defaultdict(float)
    bym = defaultdict(float)
    for j, n in per:
        byday[dt.datetime.utcfromtimestamp(j["t0"]).date()] += n
        bym[j["c"]] += n
    bd = max(byday, key=byday.get)
    top10 = set(sorted(bym, key=bym.get, reverse=True)[:10])
    line(f"main2 without best day {bd} d={d}", R.summarize([j for j in main2 if dt.datetime.utcfromtimestamp(j['t0']).date() != bd], d))
    line(f"main2 without 10 best markets d={d}", R.summarize([j for j in main2 if j["c"] not in top10], d))

# 3. honest sample: all tape-timed jumps (no +10 min confirmation, no 2 h hold), clustered by event within 30 min
allj = [dict(j) for j in js if j["payoff"] is not None]
R.clusters(allj)
for half, f in (("second", sec), ("whole", lambda j: True)):
    for d in (30, 120):
        for b in (200, 20):
            s = R.summarize([j for j in allj if f(j)], d, budget=b)
            if b == 200 and half == "second":
                s["ci"] = R.boot([j for j in allj if f(j)], d, budget=b)
            line(f"ALL tape-timed {half} d={d} ${b}", s)
unc = [j for j in allj if j["status"] in ("unconf", "artef")]
for d in (30, 120):
    line(f"not-confirmed only, second, d={d} $200", R.summarize([j for j in unc if sec(j)], d))
# honest sample restricted to the categories the headline used, excluding elections (empty-book artefacts)
for d in (30, 120):
    line(f"ALL tape-timed, non-election, second d={d} $20", R.summarize([j for j in allj if sec(j) and j['cat'] != 'elections'], d, budget=20))

# 4. one-shot fill: only the first offer print at/after t0+d (within 5 s), size <= that print
for d in (30, 120):
    for samp, nm in ((main2, "main2"), ([j for j in allj if sec(j)], "ALL second")):
        line(f"{nm} ONE-SHOT first print d={d} $200", R.summarize(samp, d, mode="first"))

# 5. delay measured from when a follower can SEE the first print via the public tape (block time + ~2 s indexing)
for d in (30, 120):
    line(f"main2 d={d}+5 s (seen on tape, not at match)", R.summarize(main2, d + 5))

# 6. real-time trigger on the cached tapes of the 321 screened markets (auditor's own, post-hoc; 1 variant x 2 delays)
#    trigger: a print whose YES price differs by >= 0.15 from the last print 60 s..30 min earlier, notional >= $20;
#    favoured side = direction of the move; one trigger per market per 2 h; buy at offer prints <= 0.90 from
#    trigger + d for 10 min, $20 cap, hold. Window 1 Sep - 25 Nov. Triggers within 2 h of a screened candidate are
#    reported separately (they are the hindsight-selected ones).
cand_times = defaultdict(list)
for c in json.load(open(R.STUDY / "out" / "candidates.json")):
    cand_times[c["c"]].append(c["T_pre"])
trig = []
for cid in sorted({c for c in cand_times}):
    tp = R.tape(cid)
    m = mk[cid]
    if tp is None:
        continue
    r_ = res.get(cid) or {}
    o = R.jl(m["outcomes"])
    fin = r_.get("final") or {}
    sy = float(fin[o[0]]) if r_.get("resolved") and fin.get(o[0]) is not None else None
    try:
        my = float(R.jl(m["outcomePrices"])[0])
    except Exception:
        my = None
    py = sy if sy is not None else my
    if py is None:
        continue
    ts = [r["t"] for r in tp]
    import bisect
    lastt = -10**12
    for k, r in enumerate(tp):
        t = r["t"]
        if t < R.W0 or t >= R.W1 or t - lastt < 7200:
            continue
        if r["z"] * r["p"] < 20:
            continue
        kk = bisect.bisect_right(ts, t - 60) - 1
        if kk < 0 or tp[kk]["t"] < t - 1800:
            continue
        dy = R.yes_price(r) - R.yes_price(tp[kk])
        if abs(dy) < 0.15:
            continue
        up = dy > 0
        lastt = t
        near = any(abs(t - 3 - tc) <= 7200 for tc in cand_times[cid])
        trig.append({"c": cid, "fidx": 0 if up else 1, "tb": t, "t0": t - 3, "rate": R.rate_of(m), "cat": R.cat_of(m),
                     "payoff": py if up else 1 - py, "resolved": sy is not None, "near": near,
                     "event": ((m.get("events") or [{}])[0] or {}).get("slug") or cid})
R.clusters(trig)
print("triggers", len(trig), "near candidates", sum(t["near"] for t in trig), "second half", sum(sec(t) for t in trig))
for nm, f in (("all", lambda t: True), ("away from screened jumps", lambda t: not t["near"]), ("near screened jumps", lambda t: t["near"])):
    for d in (30, 120):
        line(f"RT trigger {nm}, second, d={d} $20", R.summarize([t for t in trig if f(t) and sec(t)], d, budget=20))
for d in (30, 120):
    line(f"RT trigger away, first half, d={d} $20", R.summarize([t for t in trig if not t["near"] and not sec(t)], d, budget=20))
    line(f"RT trigger away, non-elections, second, d={d} $20", R.summarize([t for t in trig if not t["near"] and sec(t) and t['cat'] != 'elections'], d, budget=20))

# 7. weekends in the reporting period
we = [j for j in main2 if dt.datetime.utcfromtimestamp(j["t0"]).weekday() >= 5]
for d in (30, 120):
    line(f"main2 weekend only d={d}", R.summarize(we, d))
we_all = [j for j in allj if sec(j) and dt.datetime.utcfromtimestamp(j["t0"]).weekday() >= 5]
for d in (30,):
    line(f"ALL tape-timed weekend second d={d} $20", R.summarize(we_all, d, budget=20))
wt = [t for t in trig if sec(t) and not t["near"] and dt.datetime.utcfromtimestamp(t["t0"]).weekday() >= 5]
line("RT trigger away, weekend, second, d=30 $20", R.summarize(wt, 30, budget=20))

json.dump(out, open(HERE / "attacks.json", "w"), indent=1, default=str)
