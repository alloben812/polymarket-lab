"""Step 1 (metadata only, no outcomes used): closed gamma events that ended 2026-08-28..2026-11-27 under economics-like tags.
Saves raw event objects (with markets and rules text) to data/gaps_econ/events_raw.json.gz."""
import gzip, json, sys
from pmlab import gamma
TAGS = ["economics", "economy", "fed", "fed-rates", "inflation", "jobs", "macro-indicators", "gdp", "cpi", "unemployment",
        "central-banks", "interest-rates", "jobs-report", "ecb", "business", "finance", "economic-policy", "jerome-powell", "fomc"]
seen = {}
per = {}
for tag in TAGS:
    n = 0
    try:
        for e in gamma.iter_events(max_pages=200, limit=50, closed="true", tag_slug=tag,
                                   end_date_min="2026-08-28T00:00:00Z", end_date_max="2026-11-27T23:59:59Z"):
            seen.setdefault(e["slug"], e)
            seen[e["slug"]].setdefault("_found_by", [])
            if tag not in seen[e["slug"]]["_found_by"]:
                seen[e["slug"]]["_found_by"].append(tag)
            n += 1
    except Exception as ex:  # noqa
        print("ERR", tag, str(ex)[:200], file=sys.stderr)
    per[tag] = n
    print(tag, n, "total", len(seen), file=sys.stderr)
with gzip.open("/home/user/polymarket-lab/data/gaps_econ/events_raw.json.gz", "wt") as f:
    json.dump(list(seen.values()), f)
print(per)
