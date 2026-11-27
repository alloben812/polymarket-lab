"""Step 6a, continuation of s07_prices.py with the same request and the same output (added when the study was resumed:
the sequential run was stopped after 1,547 of 8,107 markets and left a truncated gzip, repaired by keeping the 1,547
complete lines). Same window (T_end-72h .. T_end+2h), same 300 s request with 1800 s fallback, 6 worker threads
(pmlab.http throttles per host). Appends to data/gaps_weather_fc/prices.jsonl.gz; resumable."""
import csv, gzip, json, os, sys, threading
from concurrent.futures import ThreadPoolExecutor
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
rows = [r for r in csv.DictReader(open(f"{C.DATA}/markets.csv")) if r["condition"] not in done]
# most recent dates first, so that a stop leaves the reporting period complete
rows.sort(key=lambda r: r["date"], reverse=True)
print("to fetch", len(rows), flush=True)
lock = threading.Lock()
out = gzip.open(PATH, "at")
n = [0]


def job(r):
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
        return
    line = json.dumps({"c": r["condition"], "res": res, "pts": [[p["timestamp"], p["price"]] for p in pts]}) + "\n"
    with lock:
        out.write(line)
        n[0] += 1
        if n[0] % 250 == 0:
            out.flush()
            print(n[0], r["date"], r["city"], flush=True)


with ThreadPoolExecutor(6) as ex:
    list(ex.map(job, rows))
out.close()
print("fetched", n[0], flush=True)
