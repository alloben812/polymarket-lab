"""Step 2b: routine METAR observation times (Iowa Mesonet ASOS archive, report_type=3) for the stations of the study,
2026-09-30 .. 2026-10-13. Output: data/gaps_weather_rewards/iem/<ICAO>.csv and routine_times.json (ICAO -> [epoch]).
Run: python3 -I s2b_metar_times.py"""
import csv, datetime as dt, io, json, os, time, urllib.request
OUT = "/home/user/polymarket-lab/data/gaps_weather_rewards"
os.makedirs(OUT + "/iem", exist_ok=True)
meta = json.load(open(OUT + "/meta.json"))
stations = sorted({v["station"] for v in meta.values() if v["station"]})
res = {}
for st in stations:
    path = f"{OUT}/iem/{st}.csv"
    if not (os.path.exists(path) and os.path.getsize(path) > 200):
        iem = st[1:] if st.startswith("K") else st
        url = ("https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=%s&data=metar&year1=2026&month1=9&day1=30"
               "&year2=2026&month2=10&day2=14&tz=Etc/UTC&format=onlycomma&latlon=no&report_type=3" % iem)
        txt = ""
        for attempt in range(6):
            try:
                txt = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "research-script"}), timeout=120).read().decode("utf-8", "replace")
            except Exception as e:
                txt = "ERR %s" % e
            if txt.startswith("station,"):
                break
            print(st, "retry", attempt, txt[:60].strip(), flush=True)
            time.sleep(15 + 15 * attempt)
        if txt.startswith("station,"):
            open(path, "w").write(txt)
        time.sleep(6)
    ts = []
    if os.path.exists(path):
        rd = csv.reader(open(path)); next(rd)
        for p in rd:
            try:
                ts.append(int(dt.datetime.strptime(p[1], "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc).timestamp()))
            except Exception:
                pass
    res[st] = sorted(set(ts))
    mins = sorted({(t // 60) % 60 for t in res[st]})
    print(st, len(res[st]), "reports; minutes of the hour:", mins[:12], flush=True)
json.dump(res, open(OUT + "/routine_times.json", "w"))
