"""Step 1: discover BTC/ETH price-level events closed in the study window (metadata only).
Uses tag slugs multi-strikes (above ladders) and hit-price (one-touch); limit=50 because gamma /events/keyset
refuses limit>50 without gzip (pmlab.gamma.iter_events default is 100 -> HTTP 406)."""
import json, gzip, sys
from pmlab import gamma
from pmlab.http import ROOT
OUT = ROOT / "data" / "gaps_levels"
def main():
    evs = {}
    for tag in ("multi-strikes", "hit-price"):
        n = 0
        for ev in gamma.iter_events(limit=50, closed="true", tag_slug=tag, end_date_min="2026-10-20T00:00:00Z", end_date_max="2026-12-05T00:00:00Z"):
            n += 1
            evs[ev["id"]] = ev
        print(tag, n, len(evs), file=sys.stderr)
    with gzip.open(OUT / "events_raw.json.gz", "wt") as f:
        json.dump(list(evs.values()), f)
main()
