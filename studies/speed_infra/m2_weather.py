"""m2: when does a new METAR first appear on the free official sources, relative to its observation time?

Polls aviationweather.gov METAR API (the resolution source of Polymarket daily-high markets) and
api.weather.gov latest observations for the 11 US stations every INTERVAL seconds and logs the first time each
new report is seen. Output: out/m2_weather.jsonl (one row per first sighting). Public data, no keys.
Run: python3 -I m2_weather.py <duration_s> <interval_s>
"""
import json, os, sys, time, urllib.request, datetime as dt

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "pm-research/0.1 (public data study)", "Accept": "application/geo+json"}
ST = ["KATL", "KAUS", "KORD", "KDAL", "KDEN", "KHOU", "KLAX", "KMIA", "KLGA", "KSFO", "KSEA"]


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read(), dict(r.headers)


def main():
    dur, iv = float(sys.argv[1]), float(sys.argv[2])
    seen = set()
    path = os.path.join(OUT, "m2_weather.jsonl")
    end = time.time() + dur
    first = True
    with open(path, "a") as f:
        while time.time() < end:
            nxt = time.time() + iv
            # 1) aviationweather.gov, all stations in one call
            try:
                t0 = time.time()
                body, hdr = get("https://aviationweather.gov/api/data/metar?ids=" + ",".join(ST) + "&format=json&hours=2")
                t1 = time.time()
                for m in json.loads(body):
                    key = ("awc", m["icaoId"], m.get("obsTime"), m.get("rawOb", "")[:40])
                    if key in seen:
                        continue
                    seen.add(key)
                    f.write(json.dumps({"src": "awc", "st": m["icaoId"], "obs": m.get("obsTime"),
                                        "receipt": m.get("receiptTime"), "seen": t1, "boot": first,
                                        "type": m.get("metarType"), "raw": m.get("rawOb", "")[:90]}) + "\n")
            except Exception as ex:
                f.write(json.dumps({"src": "awc", "err": repr(ex)[:200], "seen": time.time()}) + "\n")
            # 2) api.weather.gov latest observation, one station per call (rotate to stay polite)
            for st in ST:
                try:
                    body, hdr = get(f"https://api.weather.gov/stations/{st}/observations/latest")
                    t1 = time.time()
                    p = json.loads(body)["properties"]
                    key = ("nws", st, p.get("timestamp"))
                    if key in seen:
                        continue
                    seen.add(key)
                    f.write(json.dumps({"src": "nws", "st": st, "obs": p.get("timestamp"), "seen": t1, "boot": first,
                                        "raw": (p.get("rawMessage") or "")[:90]}) + "\n")
                except Exception as ex:
                    f.write(json.dumps({"src": "nws", "st": st, "err": repr(ex)[:200], "seen": time.time()}) + "\n")
            f.flush()
            first = False
            time.sleep(max(0, nxt - time.time()))


if __name__ == "__main__":
    main()
