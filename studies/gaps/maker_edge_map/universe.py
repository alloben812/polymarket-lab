"""Walk gamma (one process per day: argv[1]) for every closed market with volumeNum >= 1000 with endDate in [2026-11-20, 2026-11-27) UTC and keep a compact row per market.
Availability only: no trade or outcome statistics are computed here."""
import gzip, json, sys, time
from pmlab import gamma
DAY = int(sys.argv[1])
OUT = f"/home/user/polymarket-lab/data/gaps_maker_edge/universe_{DAY}.jsonl.gz"
KEEP = ["conditionId", "slug", "question", "endDate", "closedTime", "outcomePrices", "outcomes", "volumeNum",
        "feeType", "feeSchedule", "negRisk", "orderPriceMinTickSize", "orderMinSize", "secondsDelay", "gameStartTime",
        "sportsMarketType", "umaResolutionStatus", "createdAt", "startDate"]
n = 0
t0 = time.time()
with gzip.open(OUT + ".tmp", "wt") as f:
    for day in [DAY]:
        lo = f"2026-11-{day:02d}T00:00:00Z"; hi = f"2026-11-{day+1:02d}T00:00:00Z"
        for m in gamma.iter_markets(closed="true", end_date_min=lo, end_date_max=hi, include_tag="true", volume_num_min=1000):
            r = {k: m.get(k) for k in KEEP}
            r["tags"] = [t.get("slug") for t in (m.get("tags") or [])]
            r["family0"] = gamma.family(m)
            ev = m.get("events") or []
            r["event_slug"] = ev[0].get("slug") if ev else None
            f.write(json.dumps(r) + "\n"); n += 1
        print(day, n, round(time.time() - t0), flush=True)
import os; os.replace(OUT + ".tmp", OUT)
print("done", n)
