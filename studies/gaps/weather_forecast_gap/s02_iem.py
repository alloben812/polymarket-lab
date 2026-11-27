"""Steps 2-3: Iowa Mesonet downloads, cached under data/gaps_weather_fc/iem/. Sequential, >= 6 s between requests.
 obs_<ICAO>.csv            routine METARs (report_type=3, raw text) 2026-08-01 .. 2026-11-27
 mos_<ICAO>_<MODEL>_<YYYYMM>.csv   MOS archive rows for runs in that month
Run with python3 -I (downloaded data)."""
import os, sys, time, urllib.request

OUT = "/home/user/polymarket-lab/data/gaps_weather_fc/iem"
os.makedirs(OUT, exist_ok=True)
STATIONS = ["KLGA", "KORD", "KATL", "KAUS", "KDAL", "KDEN", "KBKF", "KHOU", "KLAX", "KMIA", "KSFO", "KSEA"]
MODELS = ["NBS", "GFS", "NBE", "MEX", "NAM"]
MONTHS = [("2026-08-01", "2026-09-01"), ("2026-09-01", "2026-10-01"), ("2026-10-01", "2026-11-01"), ("2026-11-01", "2026-11-28")]
last = [0.0]


def fetch(url, path, min_bytes=200):
    if os.path.exists(path) and os.path.getsize(path) >= min_bytes:
        return "cached"
    for attempt in range(6):
        wait = last[0] + 6.5 - time.time()
        if wait > 0:
            time.sleep(wait)
        last[0] = time.time()
        try:
            body = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "research-script"}), timeout=180).read()
        except Exception as e:  # noqa: BLE001
            print("  retry", attempt, repr(e)[:120], flush=True)
            time.sleep(20 * (attempt + 1))
            continue
        if b"Too many requests" in body[:200] or b"slow down" in body[:200]:
            print("  throttled, sleeping", flush=True)
            time.sleep(60 * (attempt + 1))
            continue
        with open(path + ".tmp", "wb") as f:
            f.write(body)
        os.replace(path + ".tmp", path)
        return f"{len(body)} bytes"
    return "FAILED"


for st in STATIONS:
    iem = st[1:]
    url = ("https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=%s&data=tmpc&data=metar&year1=2026&month1=8&day1=1"
           "&year2=2026&month2=11&day2=28&tz=Etc/UTC&format=onlycomma&latlon=no&report_type=3" % iem)
    print("obs", st, fetch(url, f"{OUT}/obs_{st}.csv"), flush=True)
for m in MODELS:
    for st in STATIONS:
        for a, b in MONTHS:
            url = f"https://mesonet.agron.iastate.edu/cgi-bin/request/mos.py?station={st}&model={m}&sts={a}T00:00Z&ets={b}T00:00Z&format=csv"
            print("mos", m, st, a, fetch(url, f"{OUT}/mos_{st}_{m}_{a[:7].replace('-', '')}.csv", min_bytes=1), flush=True)
print("done")
