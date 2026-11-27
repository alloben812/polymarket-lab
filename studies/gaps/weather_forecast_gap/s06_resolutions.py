"""Step 5a: actual winners. Writes data/gaps_weather_fc/winners.csv (condition, yes_final, resolved)."""
import csv, sys
sys.path.insert(0, "/home/user/polymarket-lab")
sys.path.insert(0, "/home/user/polymarket-lab/studies/gaps/weather_forecast_gap")
import common as C
from pmlab import dataapi

conds = [r["condition"] for r in csv.DictReader(open(f"{C.DATA}/markets.csv"))]
if len(sys.argv) > 1:
    conds = conds[: int(sys.argv[1])]
out = []
for i in range(0, len(conds), 500):
    res = dataapi.resolutions(conds[i:i + 500])
    for c in conds[i:i + 500]:
        r = res.get(c)
        out.append((c, "" if not r else r["final"].get("Yes"), "" if not r else int(r["resolved"])))
    print(i + 500, flush=True)
with open(f"{C.DATA}/winners.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["condition", "yes_final", "resolved"]); w.writerows(out)
