"""Step 7a: whole-market tapes (cached by pmlab.updown.tape under data/tape/). Markets are taken in this order:
argument 'slice' -> nyc + chicago, first 10 dates of November, all 11 buckets (sanity slice);
argument 'model' -> every bucket whose model probability reaches 0.11 at some slot/version (the only ones that can
                    ever satisfy gap >= 0.08 with price >= 0.03);
argument 'all'   -> every bucket."""
import csv, sys, collections
sys.path.insert(0, "/home/user/polymarket-lab")
sys.path.insert(0, "/home/user/polymarket-lab/studies/gaps/weather_forecast_gap")
import common as C
from pmlab import updown

mode = sys.argv[1]
rows = list(csv.DictReader(open(f"{C.DATA}/markets.csv")))
if mode == "slice":
    want = [r for r in rows if r["city"] in ("nyc", "chicago") and "2026-11-01" <= r["date"] <= "2026-11-10"]
elif mode == "model":
    mx = collections.defaultdict(float)
    for r in csv.DictReader(open(f"{C.DATA}/model_probs.csv")):
        mx[r["condition"]] = max(mx[r["condition"]], float(r["prob"]))
    want = [r for r in rows if mx.get(r["condition"], 0.0) >= 0.11]
else:
    want = rows
print("markets to fetch", len(want), flush=True)
n = tot = 0
for r in want:
    try:
        t = updown.tape(r["condition"])
    except Exception as e:  # noqa: BLE001
        print("ERR", r["condition"], repr(e)[:200], flush=True)
        continue
    n += 1; tot += len(t)
    if n % 250 == 0:
        print(n, r["date"], r["city"], "rows so far", tot, flush=True)
print("done", n, "tapes", tot, "rows")
