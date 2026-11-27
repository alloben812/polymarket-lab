"""Step 1: list closed markets by endDate day, keep the protocol universe (rules 1-2), slim rows to disk."""
import sys
import time
from datetime import datetime, timedelta, timezone

from pmlab import gamma
from common import DATA, T_CLOSED_MAX, T_CLOSED_MIN, read_jsonl, ts, write_jsonl

DAYS_DIR = DATA / "listing_days"
DAYS_DIR.mkdir(exist_ok=True)
START = datetime(2026, 9, 29, tzinfo=timezone.utc)
END = datetime(2026, 12, 9, tzinfo=timezone.utc)


def slim(m: dict) -> dict:
    ev = (m.get("events") or [{}])[0]
    return {
        "slug": m.get("slug"), "conditionId": m.get("conditionId"), "question": m.get("question"),
        "endDate": m.get("endDate"), "closedTime": m.get("closedTime"), "volumeNum": m.get("volumeNum"),
        "outcomes": gamma.jfield(m.get("outcomes")), "clobTokenIds": gamma.jfield(m.get("clobTokenIds")),
        "outcomePrices": gamma.jfield(m.get("outcomePrices")), "feeSchedule": m.get("feeSchedule"),
        "feeType": m.get("feeType"), "feesEnabled": m.get("feesEnabled"), "gameStartTime": m.get("gameStartTime"),
        "eventStartTime": m.get("eventStartTime"), "negRisk": m.get("negRisk"), "customLiveness": m.get("customLiveness"),
        "umaResolutionStatus": m.get("umaResolutionStatus"), "sportsMarketType": m.get("sportsMarketType"),
        "secondsDelay": m.get("secondsDelay"), "startDate": m.get("startDate"), "tags": gamma.tag_slugs(m),
        "family": gamma.family(m), "event_slug": ev.get("slug"), "description": m.get("description"),
        "resolutionSource": m.get("resolutionSource"),
    }


def main():
    d = START
    stats = []
    while d < END:
        path = DAYS_DIR / f"{d:%Y-%m-%d}.jsonl.gz"
        if not path.exists():
            lo = d.strftime("%Y-%m-%dT%H:%M:%SZ")
            hi = (d + timedelta(days=1) - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
            t0 = time.time()
            n_all = n_updown = n_notbin = n_window = 0
            keep = []
            for m in gamma.iter_markets(closed="true", end_date_min=lo, end_date_max=hi, volume_num_min=10000, include_tag="true"):
                n_all += 1
                if "-updown-" in (m.get("slug") or ""):
                    n_updown += 1
                    continue
                ct = ts(m.get("closedTime"))
                if ct is None or not (T_CLOSED_MIN <= ct < T_CLOSED_MAX):
                    n_window += 1
                    continue
                s = slim(m)
                if not (isinstance(s["outcomes"], list) and len(s["outcomes"]) == 2 and isinstance(s["clobTokenIds"], list)
                        and len(s["clobTokenIds"]) == 2 and s["endDate"] and (s["volumeNum"] or 0) >= 10000):
                    n_notbin += 1
                    continue
                keep.append(s)
            rows = [{"_meta": {"day": f"{d:%Y-%m-%d}", "listed": n_all, "updown": n_updown, "closed_outside": n_window, "not_binary_or_bad": n_notbin}}] + keep
            write_jsonl(path, rows)
            print(f"{d:%Y-%m-%d} listed {n_all} updown {n_updown} closed_outside {n_window} bad {n_notbin} kept {len(keep)} in {time.time()-t0:.1f}s", flush=True)
        d += timedelta(days=1)
    # merge
    seen, uni, meta = set(), [], []
    for p in sorted(DAYS_DIR.glob("*.jsonl.gz")):
        for r in read_jsonl(p):
            if "_meta" in r:
                meta.append(r["_meta"])
                continue
            if r["conditionId"] in seen:
                continue
            seen.add(r["conditionId"])
            uni.append(r)
    write_jsonl(DATA / "universe.jsonl.gz", uni)
    tot = {k: sum(m[k] for m in meta) for k in ("listed", "updown", "closed_outside", "not_binary_or_bad")}
    print("TOTAL", tot, "universe", len(uni))


if __name__ == "__main__":
    main()
