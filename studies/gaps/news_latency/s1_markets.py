"""Step 1: enumerate every gamma market with volumeNum >= 50,000 and endDate >= 2026-06-01 (closed and open),
keep a trimmed record. The keyset endpoint ignores tag_slug (checked 2026-11-27), so tags are filtered client-side
in common.py."""
import json, gzip, sys
from pmlab import gamma
from common import DATA

KEEP = ["id", "slug", "question", "conditionId", "volumeNum", "endDate", "closedTime", "startDate", "createdAt", "closed",
        "feeSchedule", "feeType", "feesEnabled", "outcomes", "outcomePrices", "clobTokenIds", "negRisk", "umaResolutionStatus",
        "description", "resolutionSource", "groupItemTitle", "automaticallyResolved", "umaEndDate", "customLiveness"]

def main():
    out = DATA / "markets_all.jsonl.gz"
    n = 0
    with gzip.open(out.with_suffix(".tmp"), "wt") as f:
        for closed in ("true", "false"):
            for m in gamma.iter_markets(closed=closed, volume_num_min=50000, end_date_min="2026-06-01T00:00:00Z", include_tag="true"):
                r = {k: m.get(k) for k in KEEP}
                r["tags"] = gamma.tag_slugs(m)
                r["family"] = gamma.family(m)
                r["events"] = [{"slug": e.get("slug"), "title": e.get("title"), "id": e.get("id")} for e in (m.get("events") or [])]
                f.write(json.dumps(r) + "\n")
                n += 1
                if n % 5000 == 0:
                    print(n, file=sys.stderr, flush=True)
    out.with_suffix(".tmp").replace(out)
    print("markets", n)

if __name__ == "__main__":
    main()
