"""Step 1b: event/market table for the universe (no outcomes). Writes data/gaps_weather_fc/markets.csv."""
import csv, gzip, json, re, sys, datetime as dt, collections
sys.path.insert(0, "/home/user/polymarket-lab/studies/gaps/weather_forecast_gap")
import common as C

E = json.load(gzip.open(f"{C.DATA}/events_raw.json.gz"))
out = []
stat = collections.Counter()
for e in E:
    ps = C.parse_slug(e["slug"])
    if not ps or ps[0] not in C.CITY_TZ:
        continue
    city, d = ps
    if not (C.UNIVERSE[0] <= d <= C.UNIVERSE[1]):
        continue
    mk = e["markets"]
    src = mk[0]["resolutionSource"] or ""
    m = re.search(r"ids=(\w{4})", src) or re.search(r"site=(\w{4})", src)
    if not m:
        stat["no station"] += 1
        continue
    station = m.group(1).upper()
    era = "metar" if "aviationweather" in src else "wxgov"
    tz = C.CITY_TZ[city]
    assert C.STATION_TZ[station] == tz, (city, station)
    te = C.t_end(tz, d)
    est = mk[0].get("eventStartTime")
    if est:
        est_ts = int(dt.datetime.fromisoformat(est.replace("Z", "+00:00")).timestamp())
        if est_ts != C.t_start(tz, d):
            stat["eventStartTime != local midnight"] += 1
    if len(mk) != 11:
        stat["not 11 buckets"] += 1
    stat[(era, station)] += 1
    created = min(int(dt.datetime.fromisoformat(x["startDate"].replace("Z", "+00:00")).timestamp()) for x in mk if x.get("startDate"))
    for x in mk:
        lo, hi = C.parse_bucket(x["groupItemTitle"])
        tok = json.loads(x["clobTokenIds"]); oc = json.loads(x["outcomes"])
        assert oc == ["Yes", "No"], oc
        out.append(dict(city=city, date=d.isoformat(), station=station, era=era, t_end=te, created=created, event=e["slug"],
                        condition=x["conditionId"], bucket=x["groupItemTitle"], lo=lo, hi=hi, yes_token=tok[0], no_token=tok[1],
                        volume=x.get("volumeNum"), fee_type=x.get("feeType")))
out.sort(key=lambda r: (r["date"], r["city"], r["lo"]))
with open(f"{C.DATA}/markets.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
ev = {(r["city"], r["date"]) for r in out}
print("markets", len(out), "city-days", len(ev))
for k, v in sorted(stat.items(), key=str): print(" ", k, v)
# bucket continuity check
by = collections.defaultdict(list)
for r in out: by[(r["city"], r["date"])].append((r["lo"], r["hi"]))
bad = 0
for k, L in by.items():
    L.sort()
    ok = L[0][0] < -1000 and L[-1][1] > 1000 and all(L[i][1] + 1 == L[i + 1][0] for i in range(len(L) - 1))
    bad += not ok
print("events with non-contiguous buckets", bad)
lead = sorted((r["t_end"] - r["created"]) / 3600 for r in out)
print("creation lead h before T_end: min %.1f p5 %.1f med %.1f max %.1f" % (lead[0], lead[len(lead)//20], lead[len(lead)//2], lead[-1]))
