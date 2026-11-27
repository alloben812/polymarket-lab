"""Cross-check (not in the rules): Iowa Mesonet routine/special classification and values vs the official source
(aviationweather.gov JSON, last ~400 reports per station) + receipt lags. Saves data/gaps_weather_obs/awc/<ICAO>.json"""
import json, os, sys, time, urllib.request, statistics as st, datetime as dt
sys.path.insert(0, "/home/user/polymarket-lab/studies/gaps/weather_observation_gap")
from common import *
os.makedirs(DATA + "/awc", exist_ok=True)
ST = ["KLGA", "KATL", "KMIA", "KORD", "KDAL", "KAUS", "KHOU", "KDEN", "KLAX", "KSFO", "KSEA"]
tot = {"awc_metar": 0, "in_iem3": 0, "in_iem4": 0, "missing": 0, "value_diff": 0, "awc_speci": 0, "speci_in_iem3": 0}
lags = []; offhour = []
for s in ST:
    p = f"{DATA}/awc/{s}.json"
    if not os.path.exists(p):
        url = f"https://aviationweather.gov/api/data/metar?ids={s}&format=json&hours=360"
        d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "research-script"}), timeout=60))
        json.dump(d, open(p, "w")); time.sleep(3)
    d = json.load(open(p))
    i3 = {r["t"]: r for r in load_obs(s, 3)}; i4 = {r["t"]: r for r in load_obs(s, 4)}
    tmax = max(i3)  # archive end
    lg = []
    for r in d:
        t = r["obsTime"]
        if t > tmax:
            continue
        rt = dt.datetime.fromisoformat(r["receiptTime"].replace("Z", "+00:00")).timestamp()
        c10, _ = parse_value(r["rawOb"])
        if r.get("metarType") == "SPECI":
            tot["awc_speci"] += 1; tot["speci_in_iem3"] += int(t in i3); continue
        tot["awc_metar"] += 1; lg.append(rt - t)
        mm = dt.datetime.fromtimestamp(t, UTC).minute
        if not 45 <= mm <= 59:
            offhour.append((s, iso(t), int(rt - t), "iem3" if t in i3 else "iem4" if t in i4 else "absent", r["rawOb"][:70]))
        if t in i3:
            tot["in_iem3"] += 1
            if i3[t]["c10"] != c10:
                tot["value_diff"] += 1; print("VALUE DIFF", s, iso(t), r["rawOb"], "|", i3[t]["raw"])
        elif t in i4:
            tot["in_iem4"] += 1
        else:
            tot["missing"] += 1; print("MISSING in IEM", s, iso(t), r["rawOb"][:80])
    lags += lg
    q = sorted(lg)
    print(s, "AWC rows", len(d), "span", iso(min(r["obsTime"] for r in d)), "->", iso(max(r["obsTime"] for r in d)),
          "routine receipt lag s: median %.0f p90 %.0f max %.0f; share <= 300 s: %.3f" % (st.median(q), q[int(.9 * len(q))], q[-1], sum(x <= 300 for x in q) / len(q)))
print(tot)
q = sorted(lags)
print("all routine: n=%d median %.0f p90 %.0f p99 %.0f max %.0f share<=300s %.4f" % (len(q), st.median(q), q[int(.9*len(q))], q[int(.99*len(q))], q[-1], sum(x <= 300 for x in q)/len(q)))
print("off-hour reports labelled METAR at the official source:", len(offhour))
for o in offhour: print("  ", o)
