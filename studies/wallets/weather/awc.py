"""Fetch the official resolution source (aviationweather.gov METAR API, JSON) for every station: gives receiptTime and half-hourly/SPECI flags.
Merges routine reports into out/obs2.json (station -> [ts, tenths_C, hasT]) and out/receipt.json (station -> {ts: receipt_epoch}).  python3 -I awc.py"""
import json, re, time, urllib.request, datetime as dt, os
OBS = json.load(open("out/obs.json")); os.makedirs("out/awc", exist_ok=True)
TG = re.compile(r"\sT([01])(\d{3})([01])(\d{3})(\s|$)"); BODY = re.compile(r"\s(M?\d{2})/(M?\d{2})?\s")
ep = lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
out, rec, stats = {}, {}, []
for st, rows in OBS.items():
    fn = f"out/awc/{st}.json"
    if not os.path.exists(fn):
        for a in range(4):
            try:
                raw = urllib.request.urlopen(urllib.request.Request(f"https://aviationweather.gov/api/data/metar?ids={st}&format=json&hours=400", headers={"User-Agent": "research-script"}), timeout=60).read()
                open(fn, "wb").write(raw); break
            except Exception as e:
                time.sleep(4)
        time.sleep(0.7)
    try: d = json.load(open(fn))
    except Exception: d = []
    have = {r[0]: r for r in rows}; rc = {}; added = 0; lags = []; speci = 0
    for x in d:
        ts = int(ep(x["reportTime"])); raw = " " + (x.get("rawOb") or "") + " "
        if x.get("metarType") == "SPECI" or raw.strip().startswith("SPECI"):
            speci += 1; have.pop(ts, None) if False else None
            continue
        t = TG.search(raw)
        if t: val, has = (-1 if t.group(1) == "1" else 1) * int(t.group(2)), True
        else:
            b = BODY.search(raw.split(" RMK")[0] + " ")
            val, has = (int(b.group(1).replace("M", "-")) * 10, False) if b else (None, False)
        if x.get("receiptTime"):
            rc[ts] = ep(x["receiptTime"]); lags.append(rc[ts] - ts)
        if ts not in have: added += 1
        have[ts] = [ts, val, has]          # the resolution source wins over the archive
    out[st] = sorted(have.values()); rec[st] = rc
    lags.sort()
    stats.append((st, len(rows), len(d), added, speci, min(rc) if rc else 0, lags[len(lags)//2] if lags else -1, lags[len(lags)//10] if lags else -1, lags[9*len(lags)//10] if lags else -1))
json.dump(out, open("out/obs2.json", "w")); json.dump(rec, open("out/receipt.json", "w"))
print("station iem_rows awc_rows added speci first_awc  receipt-minus-reportTime s: median p10 p90")
for s in stats: print(s[0], s[1], s[2], s[3], s[4], dt.datetime.fromtimestamp(s[5], dt.timezone.utc).strftime("%m-%d") if s[5] else "-", round(s[6]), round(s[7]), round(s[8]))
