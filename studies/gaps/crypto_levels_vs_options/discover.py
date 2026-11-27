"""Step 1: discover BTC/ETH price-level events closed in the study window (metadata only)."""
import json, gzip, sys
from pmlab import gamma
from pmlab.http import get_json, ROOT
OUT = ROOT / "data" / "gaps_levels"
def main():
    evs = {}
    for tag in ("crypto-prices", "crypto"):
        n = 0
        for ev in gamma.iter_events(limit=50, closed="true", tag_slug=tag, end_date_min="2026-10-26T00:00:00Z", end_date_max="2026-11-28T00:00:00Z"):
            n += 1
            evs[ev["id"]] = ev
        print(tag, n, len(evs), file=sys.stderr)
    with gzip.open(OUT / "events_raw.json.gz", "wt") as f:
        json.dump(list(evs.values()), f)
main()
