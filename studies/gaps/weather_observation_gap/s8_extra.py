"""Descriptive detail of O1(b), added after the protocol (no trading rule, no variant): WHEN the stale dead-bucket
liquidity was taken relative to the observation time (seconds), and by whom. Reads tapes + markets + observations."""
import collections, gzip, json, os, statistics as st, sys
sys.path.insert(0, "/home/user/polymarket-lab/studies/gaps/weather_observation_gap")
from common import *

M = load_markets()
OBS = {}
bins = [(-10**9, 0, "before obs minute"), (0, 60, "0-60 s"), (60, 120, "60-120 s"), (120, 180, "120-180 s"), (180, 300, "180-300 s"), (300, 600, "5-10 min"), (600, 1200, "10-20 min"),
        (1200, 3900, "20-65 min"), (3900, 10**9, "> 65 min")]
agg = {per: collections.defaultdict(lambda: [0.0, 0.0, 0]) for per in ("Oct", "Nov")}
wal = {per: collections.Counter() for per in ("Oct", "Nov")}
first_take = {per: [] for per in ("Oct", "Nov")}
late_cases = []
for e in M:
    per = "Oct" if e["date"] < "2026-11-01" else "Nov"
    if e["icao"] not in OBS:
        OBS[e["icao"]] = load_obs(e["icao"], 3)
    rep = [r for r in OBS[e["icao"]] if e["day0"] <= r["t"] < e["day1"] and r["f"] is not None]
    runmax = None; dead = {}
    for k, r in enumerate(rep):
        if runmax is not None and r["f"] <= runmax:
            continue
        runmax = r["f"]
        for i, b in enumerate(e["buckets"]):
            if b["hi"] is not None and b["hi"] < runmax and i not in dead:
                dead[i] = (r, k == 0)
    for i, (r, first) in dead.items():
        p = f"{DATA}/tape/{e['buckets'][i]['cond']}.jsonl.gz"
        if not os.path.exists(p):
            continue
        ft = None
        for l in gzip.open(p, "rt"):
            tr = json.loads(l)
            mt = tr["t"] - BLOCK_LAG
            if mt < r["t"]:
                continue
            if tr["s"] == "SELL" and tr["o"] == "Yes":
                pyes = tr["p"]
            elif tr["s"] == "BUY" and tr["o"] == "No":
                pyes = 1 - tr["p"]
            else:
                continue
            if pyes < 0.02:
                continue
            d = mt - r["t"]
            if ft is None:
                ft = d
            for lo, hi, nm in bins:
                if lo <= d < hi:
                    a = agg[per][nm]; a[0] += tr["z"] * pyes; a[1] += tr["z"]; a[2] += 1
            wal[per][tr["w"]] += tr["z"] * pyes
            if d >= 600:
                late_cases.append((e["slug"], e["buckets"][i]["title"], iso(r["t"]), int(d), round(pyes, 3), tr["z"], tr["s"], tr["o"], first, e["buckets"][i]["won"]))
        if ft is not None:
            first_take[per].append(ft)
for per in ("Oct", "Nov"):
    tot = sum(v[0] for v in agg[per].values()) or 1
    print(f"\n{per}: stale dead-bucket liquidity taken after the observation minute, by seconds since the observation time (match time = block - 3 s)")
    for lo, hi, nm in bins:
        v = agg[per][nm]
        print(f"   {nm:18s} ${v[0]:9,.0f} ({100*v[0]/tot:5.1f}%)  {v[1]:10,.0f} shares  {v[2]:5d} prints")
    q = sorted(first_take[per])
    if q:
        print(f"   first stale take per bucket: n={len(q)} median {st.median(q):.0f} s, p25 {q[len(q)//4]:.0f}, p75 {q[3*len(q)//4]:.0f}, p90 {q[int(.9*len(q))]:.0f}")
    print("   top takers:", [(w[:10], round(v)) for w, v in wal[per].most_common(6)], "of total", round(sum(wal[per].values())))
print("\nprints >= 10 minutes after the observation time (slug, bucket, obs, seconds after, YES price, shares, side, outcome, first-report-of-day, bucket won):", len(late_cases))
late_cases.sort(key=lambda x: -x[4] * x[5])
for c in late_cases[:40]:
    print("  ", c)
json.dump(late_cases, open(DATA + "/late_stale_prints.json", "w"))
