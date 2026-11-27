"""Step 1: event universe from gamma (protocol, Data 2). Writes data/gaps_negrisk/universe.json (slim events).
usage: python3 -I u1_universe.py
"""
import json, os, time, requests

OUT = "/home/user/polymarket-lab/data/gaps_negrisk"
G = "https://gamma-api.polymarket.com/events"
KEEP_M = ["conditionId", "clobTokenIds", "question", "groupItemTitle", "negRisk", "negRiskOther", "closed",
          "closedTime", "feeSchedule", "feeType", "orderMinSize", "orderPriceMinTickSize", "outcomes", "slug",
          "endDate", "active", "umaResolutionStatus", "outcomePrices"]
S = requests.Session(); S.headers["Accept-Encoding"] = "gzip"


def get(params, tries=5):
    import hashlib
    cf = f"{OUT}/gamma_cache/" + hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest() + ".json"
    if os.path.exists(cf):
        return json.load(open(cf))
    os.makedirs(os.path.dirname(cf), exist_ok=True)
    for a in range(tries):
        try:
            r = S.get(G, params=params, timeout=120)
            if r.status_code == 200:
                rows = [slim(e) for e in r.json()]
                json.dump(rows, open(cf, "w"))
                return rows
            print("http", r.status_code, r.text[:200], flush=True)
        except Exception as e:
            print("err", e, flush=True)
        time.sleep(3 + 5 * a)
    raise SystemExit("gamma failed")


def slim(e):
    tags = [t.get("slug") for t in (e.get("tags") or [])]
    return {"id": e["id"], "slug": e.get("slug"), "title": e.get("title"), "negRisk": e.get("negRisk"),
            "negRiskAugmented": e.get("negRiskAugmented"), "closed": e.get("closed"), "endDate": e.get("endDate"),
            "volume": e.get("volume"), "tags": tags,
            "markets": [{k: m.get(k) for k in KEEP_M} for m in (e.get("markets") or [])]}


def walk(base, n_max, page=50):
    out = []
    for off in range(0, n_max, page):
        rows = get({**base, "limit": page, "offset": off})
        out += rows
        if len(rows) < page:
            break
        time.sleep(0.4)
    return out


def main():
    ev = {}
    rng = {"end_date_min": "2026-11-21T00:00:00Z", "end_date_max": "2026-11-27T12:00:00Z"}
    parts = {
        "open_top": walk({"closed": "false", "order": "volume24hr", "ascending": "false"}, 500),
        "closed_top": walk({"closed": "true", "order": "volume", "ascending": "false", **rng}, 500),
        "weather": walk({"closed": "true", "tag_slug": "weather", **rng}, 3000),
        "ms_closed": walk({"closed": "true", "tag_slug": "multi-strikes", **rng}, 1000),
        "ms_open": walk({"closed": "false", "tag_slug": "multi-strikes"}, 1000),
    }
    for k, v in parts.items():
        print(k, len(v), "negRisk", sum(1 for e in v if e["negRisk"]), flush=True)
        for e in v:
            cur = ev.setdefault(e["id"], e)
            cur["src"] = sorted(set(cur.get("src", [])) | {k})
    json.dump(list(ev.values()), open(f"{OUT}/universe.json", "w"))
    print("events", len(ev), "markets", sum(len(e["markets"]) for e in ev.values()))


if __name__ == "__main__":
    main()
