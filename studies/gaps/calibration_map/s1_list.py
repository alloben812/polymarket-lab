"""Step 1: list closed markets by endDate day (protocol: Universe 1), slim rows to disk."""
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from pmlab import gamma
from common import DATA, write_jsonl

DIR = DATA / "listing"
DIR.mkdir(exist_ok=True)
START = datetime(2026, 8, 25, tzinfo=timezone.utc)
END = datetime(2026, 12, 4, tzinfo=timezone.utc)


def slim(m):
    ev = (m.get("events") or [{}])[0]
    fs = m.get("feeSchedule") or {}
    return {"slug": m.get("slug"), "cid": m.get("conditionId"), "endDate": m.get("endDate"),
            "closedTime": m.get("closedTime"), "startDate": m.get("startDate"), "gameStartTime": m.get("gameStartTime"),
            "eventStartTime": m.get("eventStartTime"), "vol": m.get("volumeNum"),
            "outcomes": gamma.jfield(m.get("outcomes")), "tokens": gamma.jfield(m.get("clobTokenIds")),
            "op": gamma.jfield(m.get("outcomePrices")), "sportsMarketType": m.get("sportsMarketType"),
            "tags": gamma.tag_slugs(m), "family": gamma.family(m), "event": ev.get("slug"), "negRisk": m.get("negRisk"),
            "feeRate": fs.get("rate"), "uma": m.get("umaResolutionStatus")}


def one(d):
    path = DIR / f"{d:%Y-%m-%d}.jsonl.gz"
    if path.exists():
        return d, -1
    lo = d.strftime("%Y-%m-%dT%H:%M:%SZ")
    hi = (d + timedelta(days=1) - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for attempt in range(3):
        try:
            rows = [slim(m) for m in gamma.iter_markets(closed="true", end_date_min=lo, end_date_max=hi,
                                                         volume_num_min=500, include_tag="true")]
            write_jsonl(path, rows)
            return d, len(rows)
        except Exception as e:  # noqa
            print("retry", d, e, flush=True)
            time.sleep(5)
    return d, None


def main():
    days = []
    d = START
    while d < END:
        days.append(d)
        d += timedelta(days=1)
    t0 = time.time()
    with ThreadPoolExecutor(4) as ex:
        for d, n in ex.map(one, days):
            print(f"{d:%Y-%m-%d} {n} {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
