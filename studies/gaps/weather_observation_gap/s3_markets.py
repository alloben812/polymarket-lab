"""Step 3a: market table for the universe + official resolutions. Writes data/gaps_weather_obs/markets.json:
list of events {slug, city, icao, date, regime, closed_ts, day0, day1, buckets:[{title, lo, hi, cond, yes, no, vol, won}]}"""
import gzip, json, sys, datetime as dt, collections
sys.path.insert(0, "/home/user/polymarket-lab")
sys.path.insert(0, "/home/user/polymarket-lab/studies/gaps/weather_observation_gap")
from pmlab import gamma, dataapi
from common import *

evs = [json.loads(l) for l in gzip.open(DATA + "/events_raw.jsonl.gz", "rt")]
W0 = dt.datetime(2026, 10, 1, tzinfo=UTC).timestamp(); W1 = dt.datetime(2026, 11, 26, tzinfo=UTC).timestamp()
out, dropped = [], collections.Counter()
stations_seen = collections.defaultdict(set)
for e in evs:
    m = SLUG.match(e["slug"])
    city = m.group(1)
    if city not in CITY:
        continue
    date = dt.date(int(m.group(4)), MONTHS[m.group(2)], int(m.group(3)))
    ct = e.get("closedTime")
    if not ct:
        dropped["no closedTime"] += 1; continue
    cts = dt.datetime.fromisoformat(ct.replace("Z", "+00:00").replace(" ", "T").replace("+00", "+00:00") if "+00:00" not in ct and ct.endswith("+00") else ct.replace("Z", "+00:00")).timestamp()
    if not (W0 <= cts < W1):
        dropped["outside window"] += 1; continue
    desc = e["description"]
    regime = "new" if "routine (METAR) observation" in desc else ("old" if "wrh/timeseries" in desc else "other")
    st = re.findall(r"\(([A-Z]{4})\)", desc) + re.findall(r"site=(\w{4})", desc) + re.findall(r"ids=(\w{4})", desc)
    for s in st:
        stations_seen[city].add(s.upper())
    d0, d1 = local_day_bounds(city, date)
    bks = []
    for mk in e["markets"]:
        lo, hi = parse_bucket(mk["groupItemTitle"])
        toks = gamma.jfield(mk["clobTokenIds"]); outs = gamma.jfield(mk["outcomes"])
        assert outs == ["Yes", "No"], outs
        bks.append({"title": mk["groupItemTitle"], "lo": lo, "hi": hi, "cond": mk["conditionId"], "yes": toks[0], "no": toks[1],
                    "vol": mk.get("volumeNum"), "fee_field": (mk.get("feeSchedule") or {}).get("rate"), "est": mk.get("eventStartTime")})
    bks.sort(key=lambda b: (-10**9 if b["lo"] is None else b["lo"]))
    icao = sorted({x.upper() for x in st})
    assert len(icao) == 1, (e["slug"], icao)
    out.append({"slug": e["slug"], "city": city, "icao": icao[0], "date": date.isoformat(), "regime": regime, "closed_ts": int(cts),
                "day0": d0, "day1": d1, "buckets": bks})
print("events in window", len(out), dict(dropped))
print({c: sorted(s) for c, s in stations_seen.items()})
# check eventStartTime == local midnight where present
bad = [(e["slug"], b["est"], e["day0"]) for e in out for b in e["buckets"][:1] if b["est"] and int(dt.datetime.fromisoformat(b["est"].replace("Z", "+00:00")).timestamp()) != e["day0"]]
print("eventStartTime != local midnight:", len(bad), bad[:5])
conds = [b["cond"] for e in out for b in e["buckets"]]
res = dataapi.resolutions(conds)
keep = []
for e in out:
    ok = True
    for b in e["buckets"]:
        r = res.get(b["cond"])
        if not r or not r["resolved"] or r["final"].get("Yes") not in (0, 1, 0.0, 1.0):
            ok = False; break
        b["won"] = int(r["final"]["Yes"])
        assert r["tokens"]["Yes"] == b["yes"] and r["tokens"]["No"] == b["no"]
    if ok and sum(b["won"] for b in e["buckets"]) == 1:
        keep.append(e)
    else:
        dropped["not cleanly resolved: " + e["slug"]] += 1
print("kept", len(keep), dict(dropped))
cnt = collections.Counter(e["city"] for e in keep)
print(cnt)
print(collections.Counter((e["regime"]) for e in keep), min(e["date"] for e in keep), max(e["date"] for e in keep))
json.dump(keep, open(DATA + "/markets.json", "w"))
