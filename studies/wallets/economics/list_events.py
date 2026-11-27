"""List closed economics-tagged events that ended Sep-Nov 2026 (candidates for release-time tape analysis)."""
import json, sys
sys.path.insert(0, "/home/user/polymarket-lab")
from pmlab import gamma
seen = {}
for tag in ("economics", "economy", "fed", "inflation", "macro-indicators", "fed-rates"):
    try:
        for e in gamma.iter_events(max_pages=40, limit=50, closed="true", tag_slug=tag, end_date_min="2026-09-01T00:00:00Z", end_date_max="2026-11-27T00:00:00Z"):
            seen[e["slug"]] = e
    except Exception as ex:
        print("ERR", tag, ex, file=sys.stderr)
rows = sorted(seen.values(), key=lambda e: -(float(e.get("volume") or 0)))
out = []
for e in rows:
    ms = e.get("markets") or []
    out.append({"slug": e["slug"], "title": e.get("title"), "end": e.get("endDate"), "volume": float(e.get("volume") or 0), "n": len(ms),
                "markets": [{"slug": m.get("slug"), "cond": m.get("conditionId"), "q": m.get("question"), "end": m.get("endDate"), "closed": m.get("closedTime"), "vol": float(m.get("volumeNum") or m.get("volume") or 0), "prices": m.get("outcomePrices"), "tokens": m.get("clobTokenIds"), "uma_end": m.get("umaEndDate")} for m in ms]})
json.dump(out, open("events_sep_nov.json", "w"))
print(len(out), "events")
for e in out[:70]:
    print(f"{e['volume']:12.0f} n={e['n']:3d} end={str(e['end'])[:16]} {e['slug'][:70]}")
