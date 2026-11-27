"""Step 2: Iowa Mesonet ASOS archive, raw METAR text, routine (3) and special (4) reports per station. Cached raw CSV."""
import os, sys, time, urllib.request
OUT = "/home/user/polymarket-lab/data/gaps_weather_obs/iem"
os.makedirs(OUT, exist_ok=True)
ST = ["BKF", "LGA", "ATL", "MIA", "ORD", "DAL", "AUS", "HOU", "DEN", "LAX", "SFO", "SEA"]
for st in ST:
    for rt in (3, 4):
        path = f"{OUT}/{st}_{rt}.csv"
        if os.path.exists(path) and os.path.getsize(path) > 200:
            continue
        url = ("https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=%s&data=metar&year1=2026&month1=9&day1=29"
               "&year2=2026&month2=11&day2=28&tz=Etc/UTC&format=onlycomma&latlon=no&report_type=%d" % (st, rt))
        for attempt in range(8):
            try:
                txt = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "research-script"}), timeout=120).read().decode("utf-8", "replace")
            except Exception as e:
                txt = "ERR %s" % e
            if txt.startswith("station,"):
                break
            print(st, rt, "retry", attempt, txt[:60].strip(), flush=True)
            time.sleep(20 + 20 * attempt)
        else:
            print("FAILED", st, rt); continue
        open(path, "w").write(txt)
        print(st, rt, len(txt.splitlines()) - 1, flush=True)
        time.sleep(8)
