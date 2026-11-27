"""Step 2b: recomputed daily maxima from routine METARs. Writes data/gaps_weather_fc/obs_max.csv
(station, date, n_reports, n_tgroup, max_f, max_tenths_c, hour_of_max_local). Run with python3 -I."""
import csv, datetime as dt, re, sys, collections
sys.path.insert(0, "/home/user/polymarket-lab/studies/gaps/weather_forecast_gap")
from zoneinfo import ZoneInfo
import common as C

TG = re.compile(r"\sT([01])(\d{3})([01])(\d{3})(\s|$)")
BODY = re.compile(r"\s(M?\d{2})/(M?\d{2})?\s")
rows_out = []
for st, tz in C.STATION_TZ.items():
    z = ZoneInfo(tz)
    days = collections.defaultdict(list)
    n_spec = 0
    with open(f"{C.DATA}/iem/obs_{st}.csv", newline="", encoding="utf-8", errors="replace") as f:
        for r in csv.DictReader(f):
            raw = " " + (r.get("metar") or "") + " "
            if raw.strip().startswith("SPECI"):
                n_spec += 1
                continue
            try:
                t = dt.datetime.strptime(r["valid"], "%Y-%m-%d %H:%M").replace(tzinfo=C.UTC)
            except (ValueError, KeyError):
                continue
            g = TG.search(raw)
            if g:
                val, has = (-1 if g.group(1) == "1" else 1) * int(g.group(2)), 1
            else:
                b = BODY.search(raw.split(" RMK")[0] + " ")
                if not b:
                    continue
                val, has = int(b.group(1).replace("M", "-")) * 10, 0
            loc = t.astimezone(z)
            days[loc.date()].append((val, has, loc.hour))
    for d in sorted(days):
        L = days[d]
        mx = max(L)
        rows_out.append((st, d.isoformat(), len(L), sum(x[1] for x in L), C.c10_to_f(mx[0]), mx[0], max(x[2] for x in L if x[0] == mx[0])))
    print(st, "days", len(days), "speci-labelled rows skipped", n_spec, "median reports/day", sorted(len(v) for v in days.values())[len(days)//2])
with open(f"{C.DATA}/obs_max.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["station", "date", "n_reports", "n_tgroup", "max_f", "max_tenths_c", "hour_of_max_local"]); w.writerows(rows_out)
print("rows", len(rows_out))
