"""Step 1: universe. Closed gamma weather events ending 2026-09-19 .. 2026-11-27, keep daily highest-temperature events.
Writes data/gaps_weather_fc/events_raw.json.gz (all highest-temperature events, trimmed fields)."""
import gzip, json, sys
sys.path.insert(0, "/home/user/polymarket-lab")
from pmlab import gamma

OUT = "/home/user/polymarket-lab/data/gaps_weather_fc/events_raw.json.gz"
keep = []
n = 0
for ev in gamma.iter_events(closed="true", tag_slug="weather", limit=50,
                            end_date_min="2026-09-18T00:00:00Z", end_date_max="2026-11-27T00:00:00Z"):
    n += 1
    slug = ev.get("slug") or ""
    if not slug.startswith("highest-temperature-in-"):
        continue
    mk = []
    for m in ev.get("markets") or []:
        mk.append({k: m.get(k) for k in ("conditionId", "slug", "question", "groupItemTitle", "groupItemThreshold", "endDate",
                                         "eventStartTime", "startDate", "closedTime", "resolutionSource", "volumeNum",
                                         "clobTokenIds", "outcomes", "outcomePrices", "feeSchedule", "feeType",
                                         "orderPriceMinTickSize", "orderMinSize", "negRisk", "description", "umaResolutionStatus")})
    keep.append({"slug": slug, "title": ev.get("title"), "endDate": ev.get("endDate"), "startDate": ev.get("startDate"),
                 "eventStartTime": ev.get("startTime") or ev.get("eventStartTime"), "seriesSlug": ev.get("seriesSlug"),
                 "resolutionSource": ev.get("resolutionSource"), "description": ev.get("description"),
                 "volume": ev.get("volume"), "negRisk": ev.get("negRisk"), "markets": mk})
    if len(keep) % 200 == 0:
        print(n, len(keep), slug, flush=True)
with gzip.open(OUT, "wt") as f:
    json.dump(keep, f)
print("events seen", n, "kept", len(keep))
