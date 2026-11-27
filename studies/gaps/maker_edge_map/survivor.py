"""Attack (survivorship): markets with endDate in the window and volumeNum >= 1000 that are NOT closed yet."""
import json, collections, sys
sys.path.insert(0, "/home/user/polymarket-lab/studies/gaps/maker_edge_map")
from pmlab import gamma
rows = []
for m in gamma.iter_markets(closed="false", end_date_min="2026-11-20T00:00:00Z", end_date_max="2026-11-27T00:00:00Z", include_tag="true", volume_num_min=1000):
    rows.append({"conditionId": m.get("conditionId"), "slug": m.get("slug"), "endDate": m.get("endDate"), "family0": gamma.family(m),
                 "tags": [t.get("slug") for t in (m.get("tags") or [])], "outcomePrices": m.get("outcomePrices"), "uma": m.get("umaResolutionStatus"), "vol": m.get("volumeNum")})
json.dump(rows, open("/home/user/polymarket-lab/data/gaps_maker_edge/open_in_window.json", "w"))
print(len(rows), collections.Counter(r["family0"] for r in rows).most_common())
