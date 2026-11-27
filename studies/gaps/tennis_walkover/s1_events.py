"""Step 1: walk closed gamma tennis events and save compact metadata (events + markets)."""
import gzip, json, sys
from pathlib import Path
from pmlab import gamma

OUT = Path("/home/user/polymarket-lab/data/gaps_tennis_wo")
OUT.mkdir(parents=True, exist_ok=True)

MKEYS = ["slug", "question", "conditionId", "outcomes", "outcomePrices", "clobTokenIds", "endDate", "gameStartTime",
         "closedTime", "umaResolutionStatus", "sportsMarketType", "volumeNum", "startDate", "line", "secondsDelay",
         "customLiveness", "groupItemTitle", "feeSchedule", "description", "umaEndDate", "createdAt"]
EKEYS = ["id", "slug", "title", "startDate", "endDate", "startTime", "eventDate", "closedTime", "finishedTimestamp",
         "seriesSlug", "score", "period", "gameId", "volume", "eventMetadata", "resolutionSource", "createdAt"]


def main():
    n = nm = 0
    path = OUT / "events.jsonl.gz"
    with gzip.open(path, "wt") as f:
        for ev in gamma.iter_events(closed="true", tag_slug="tennis", limit=50, end_date_min="2026-08-20T00:00:00Z"):
            e = {k: ev.get(k) for k in EKEYS}
            e["tags"] = [t.get("slug") for t in ev.get("tags") or []]
            e["teams"] = [t.get("name") for t in ev.get("teams") or []]
            ms = []
            for m in ev.get("markets") or []:
                mm = {k: m.get(k) for k in MKEYS}
                ms.append(mm)
            for mm in ms:  # rule text is kept for the moneyline only (side markets are read separately)
                if mm.get("sportsMarketType") != "moneyline":
                    mm["description"] = None
            e["markets"] = ms
            f.write(json.dumps(e) + "\n")
            n += 1
            nm += len(ms)
            if n % 500 == 0:
                print(n, nm, e["slug"], e["endDate"], flush=True)
    print("done", n, nm)


if __name__ == "__main__":
    main()
