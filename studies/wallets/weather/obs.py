"""Step 2: station observations (Iowa Mesonet ASOS archive, routine reports only) for every station/day in out/markets.json.
Writes out/obs.json: station -> list of [epoch, temp_tenths_C_or_None, has_T_group].  Run with python3 -I (downloaded data)."""
import json, re, sys, time, urllib.request, datetime as dt, collections
M = json.load(open("out/markets.json"))
stations = collections.Counter()
for m in M.values():
    mm = re.search(r"ids=(\w+)", m.get("src") or "")
    if mm and "temperature" in (m.get("slug") or ""):
        stations[mm.group(1)] += 1
print(len(stations), "stations", flush=True)
TG = re.compile(r"\sT([01])(\d{3})([01])(\d{3})(\s|$)")
BODY = re.compile(r"\s(M?\d{2})/(M?\d{2})?\s")
out = {}
for st in stations:
    iem = st[1:] if (st.startswith("K") and len(st) == 4) else st
    url = ("https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=%s&data=tmpc&data=metar&year1=2026&month1=11&day1=11"
           "&year2=2026&month2=11&day2=29&tz=Etc/UTC&format=onlycomma&latlon=no&report_type=3" % iem)
    for attempt in range(4):
        try:
            txt = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "research-script"}), timeout=60).read().decode("utf-8", "replace")
            break
        except Exception as e:
            txt = ""; time.sleep(3 + 3 * attempt)
    rows = []
    for line in txt.splitlines()[1:]:
        p = line.split(",", 3)
        if len(p) < 4: continue
        try: ts = int(dt.datetime.strptime(p[1], "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc).timestamp())
        except ValueError: continue
        raw = " " + p[3] + " "
        t = TG.search(raw)
        if t: val, has = (-1 if t.group(1) == "1" else 1) * int(t.group(2)), True
        else:
            b = BODY.search(raw.split(" RMK")[0] + " ")
            if b: val, has = int(b.group(1).replace("M", "-")) * 10, False
            else: val, has = None, False
        rows.append([ts, val, has])
    out[st] = rows
    print(st, len(rows), sum(1 for r in rows if r[2]), flush=True)
    time.sleep(1.0)
json.dump(out, open("out/obs.json", "w"))
