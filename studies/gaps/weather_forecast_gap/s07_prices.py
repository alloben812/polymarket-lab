"""Step 6a: prices-history of the YES token of every bucket, from T_end-72h to T_end+2h, 300 s buckets (1800 s fallback).
Appends to data/gaps_weather_fc/prices.jsonl.gz  {c, res, pts:[[t,p],...]} ; resumable."""
import csv, gzip, json, os, sys
sys.path.insert(0, "/home/user/polymarket-lab")
sys.path.insert(0, "/home/user/polymarket-lab/studies/gaps/weather_forecast_gap")
import common as C
from pmlab import dataapi

PATH = f"{C.DATA}/prices.jsonl.gz"
done = set()
if os.path.exists(PATH):
    with gzip.open(PATH, "rt") as f:
        for line in f:
            try:
                done.add(json.loads(line)["c"])
            except ValueError:
                pass
rows = list(csv.DictReader(open(f"{C.DATA}/markets.csv")))
only = set(sys.argv[1].split(",")) if len(sys.argv) > 1 else None
n = 0
with gzip.open(PATH, "at") as f:
    for r in rows:
        if r["condition"] in done or (only and r["city"] not in only):
            continue
        te = int(r["t_end"])
        a, b = te - 72 * 3600, te + 2 * 3600
        res = 300
        try:
            pts = dataapi.prices_history(r["yes_token"], a, b, 300)
            if not pts:
                res = 1800
                pts = dataapi.prices_history(r["yes_token"], a, b, 1800)
        except Exception as e:  # noqa: BLE001
            print("ERR", r["condition"], repr(e)[:200], flush=True)
            continue
        f.write(json.dumps({"c": r["condition"], "res": res, "pts": [[p["timestamp"], p["price"]] for p in pts]}) + "\n")
        n += 1
        if n % 500 == 0:
            print(n, r["date"], r["city"], flush=True)
print("fetched", n)
