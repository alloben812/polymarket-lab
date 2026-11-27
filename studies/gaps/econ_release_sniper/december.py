"""Part 3 metadata: open release-decided Polymarket events ending 2026-11-28..2027-01-20 under economics tags,
plus closed events ending 2026-11-25..27 (fresh-data check) and a text search for jobless claims / retail sales.
Output: data/gaps_econ_sniper/open_events.json.gz, out/december_events.json (small)."""
import gzip, json, sys, re
from pmlab import gamma, http

TAGS = ["economics", "economy", "fed", "fed-rates", "inflation", "jobs", "macro-indicators", "gdp", "cpi",
        "unemployment", "central-banks", "interest-rates", "jobs-report", "ecb", "fomc"]
seen = {}
for closed, lo, hi in (("false", "2026-11-28T00:00:00Z", "2027-01-20T23:59:59Z"),
                       ("true", "2026-11-25T00:00:00Z", "2026-11-27T23:59:59Z")):
    for tag in TAGS:
        try:
            for e in gamma.iter_events(max_pages=40, limit=50, closed=closed, tag_slug=tag, end_date_min=lo, end_date_max=hi):
                e["_closed_query"] = closed
                seen.setdefault(e["slug"], e)
        except Exception as ex:
            print("ERR", tag, str(ex)[:150], file=sys.stderr)
    print(closed, len(seen), file=sys.stderr)
search = {}
for q in ("jobless claims", "initial claims", "retail sales", "nonfarm payrolls", "unemployment rate", "CPI", "PCE",
          "GDP growth", "Fed decision", "ISM", "PPI", "JOLTS"):
    try:
        r = http.get_json("https://gamma-api.polymarket.com/public-search", {"q": q, "limit_per_type": 20, "events_status": "active"})
        search[q] = [e.get("slug") for e in (r.get("events") or [])]
    except Exception as ex:
        search[q] = "ERR " + str(ex)[:100]
json.dump(list(seen.values()), gzip.open("/home/user/polymarket-lab/data/gaps_econ_sniper/open_events.json.gz", "wt"))
small = []
for e in seen.values():
    ms = e.get("markets") or []
    vol = sum(float(m.get("volumeNum") or 0) for m in ms)
    small.append({"slug": e["slug"], "title": e.get("title"), "end": e.get("endDate"), "closed_q": e["_closed_query"],
                  "n_markets": len(ms), "vol_shares": round(vol), "liq": e.get("liquidity"),
                  "fee": (ms[0].get("feeSchedule") if ms else None), "feeType": (ms[0].get("feeType") if ms else None)})
small.sort(key=lambda x: x["end"] or "")
json.dump({"events": small, "search": search}, open("/home/user/polymarket-lab/studies/gaps/econ_release_sniper/out/december_events.json", "w"), indent=0)
print(len(small))
