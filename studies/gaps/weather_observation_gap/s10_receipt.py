"""Post-hoc, descriptive (added after the protocol; no trading rule, no variant).
For kill reports that have an official aviationweather.gov receiptTime in the cached AWC JSON (about Nov 12-24),
split the stale dead-bucket profit taken by all takers (taker SELL Yes at >= 0.02 / BUY No at <= 0.98, profit =
shares * YES price, before fee) by match time relative to the OFFICIAL receipt time, instead of obs + 300 s.
Also: size of the stale prints taken before the receipt (what a faster feed would have had to compete for)."""
import collections, datetime as dt, gzip, json, os, statistics as st, sys
sys.path.insert(0, "/home/user/polymarket-lab/studies/gaps/weather_observation_gap")
from common import *

M = load_markets()
REC = {}
for f in os.listdir(DATA + "/awc"):
    for r in json.load(open(f"{DATA}/awc/{f}")):
        if r.get("metarType") == "SPECI":
            continue
        REC[(r["icaoId"], r["obsTime"])] = dt.datetime.fromisoformat(r["receiptTime"].replace("Z", "+00:00")).timestamp()
OBS = {}
bins = [(-10**9, -60, "> 60 s before receipt"), (-60, -10, "60-10 s before"), (-10, 0, "10-0 s before"), (0, 10, "0-10 s after receipt"),
        (10, 30, "10-30 s after"), (30, 120, "30-120 s after"), (120, 600, "2-10 min after"), (600, 10**9, "> 10 min after")]
agg = collections.defaultdict(lambda: [0.0, 0.0, 0])
lags, prints_pre, kills, kills_with = [], [], 0, 0
wk = collections.defaultdict(lambda: [0.0, set()])
for e in M:
    if e["icao"] not in OBS:
        OBS[e["icao"]] = load_obs(e["icao"], 3)
    rep = [r for r in OBS[e["icao"]] if e["day0"] <= r["t"] < e["day1"] and r["f"] is not None]
    runmax = None; dead = {}
    for r in rep:
        if runmax is not None and r["f"] <= runmax:
            continue
        runmax = r["f"]
        for i, b in enumerate(e["buckets"]):
            if b["hi"] is not None and b["hi"] < runmax and i not in dead:
                dead[i] = r
    for i, r in dead.items():
        rc = REC.get((e["icao"], r["t"]))
        if rc is None:
            continue
        kills += 1; lags.append(rc - r["t"])
        p = f"{DATA}/tape/{e['buckets'][i]['cond']}.jsonl.gz"
        if not os.path.exists(p):
            continue
        anyp = False
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
            anyp = True
            d = mt - rc
            for lo, hi, nm in bins:
                if lo <= d < hi:
                    a = agg[nm]; a[0] += tr["z"] * pyes; a[1] += tr["z"]; a[2] += 1
            if d < 0:
                prints_pre.append((tr["z"], tr["z"] * pyes, pyes))
            wkd = "weekend" if dt.date.fromisoformat(e["date"]).weekday() >= 5 else "weekday"
            wk[wkd][0] += tr["z"] * pyes; wk[wkd][1].add(e["date"])
        kills_with += anyp
q = sorted(lags)
print(f"kill reports (newly dead buckets) with an official receipt time: {kills}; with any stale print: {kills_with}")
print(f"receipt lag after observation time for these: median {st.median(q):.0f} s, p10 {q[len(q)//10]:.0f}, p90 {q[int(.9*len(q))]:.0f}")
tot = sum(v[0] for v in agg.values()) or 1
for lo, hi, nm in bins:
    v = agg[nm]
    print(f"   {nm:24s} ${v[0]:8,.0f} ({100*v[0]/tot:5.1f}%)  {v[1]:9,.0f} shares  {v[2]:4d} prints")
if prints_pre:
    z = sorted(x[0] for x in prints_pre); u = sorted(x[1] for x in prints_pre); pp = sorted(x[2] for x in prints_pre)
    print(f"stale prints before receipt: n={len(z)}, shares median {st.median(z):.0f} p90 {z[int(.9*len(z))]:.0f}; profit per print median ${st.median(u):.2f} p90 ${u[int(.9*len(u))]:.2f}; YES price median {st.median(pp):.3f}")
for k, v in wk.items():
    print(f"{k}: stale profit ${v[0]:,.0f} over {len(v[1])} observation dates with receipt data")
