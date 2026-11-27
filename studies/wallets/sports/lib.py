"""Helpers for the sports wallet study: cached fills, market metadata, tapes, ESPN play-by-play."""
import gzip, json, os, time, datetime as dt, collections, re
from pmlab import wallet as W, dataapi, gamma, http

HERE = os.path.dirname(os.path.abspath(__file__))
NOW = 1795795200  # 2026-11-28 00:00 UTC upper bound; fills simply stop at "now"

WALLETS = {
    "forecastication4": "0x885ffdf360e5b0b6e6acb963fb3f8ba2344c8ed9",
    "soforth": "0x72638c8d939fd0205925025b1183d8db4a360851",
    "0x9f15613e": "0x9f15613ebf1f36d4bc679e1211d1fc567cf9bdb3",
    "0x66e7ce01": "0x66e7ce01c6831b8a2503d09edd6167152ee68bcd",
    "0xd9e0aaca": "0xd9e0aaca471f489be338fd0f91a26e8669a805f2",
    "dashattacker": "0x8191c793fd7edbadf0fae651f55c1da3b638da72",
    "0x99f0d31f": "0x99f0d31fdced5b3a0e5ee2867730a6644a6c9495",
}

def ts(v):
    return W._ts(v)

def iso(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%m-%d %H:%M:%S") if t else "-"

def fills(name, days, max_fills=60000):
    p = f"{HERE}/fills/{name}_{days}d.json.gz"
    if os.path.exists(p):
        return json.load(gzip.open(p, "rt"))
    end = int(time.time()); start = end - int(days * 86400)
    f, trunc = W.fetch_fills(WALLETS[name], start, end, max_fills)
    for r in f:
        r["size"] = float(r["size"]); r["price"] = float(r["price"])
    json.dump(f, gzip.open(p, "wt"))
    print(name, "fills", len(f), "truncated", trunc)
    return f

def meta(conds):
    conds = sorted(set(conds))
    return gamma.markets_by_condition(conds, cache=True)

def resol(conds):
    return dataapi.resolutions(sorted(set(conds)), cache=True)

def tape(cond):
    p = f"{HERE}/fills/tape_{cond[:14]}.json.gz"
    if os.path.exists(p):
        return json.load(gzip.open(p, "rt"))
    keep = ("side", "token_id", "size", "price", "timestamp", "outcome", "proxy_wallet", "transaction_hash")
    rows = [{k: r.get(k) for k in keep} for r in dataapi.iter_trades(condition=cond)]
    for r in rows:
        r["size"] = float(r["size"]); r["price"] = float(r["price"])
    rows.sort(key=lambda r: r["timestamp"])
    json.dump(rows, gzip.open(p, "wt"))
    return rows

ESPN = "https://site.api.espn.com/apis/site/v2/sports"
LEAGUES = {"nba": "basketball/nba", "nfl": "football/nfl", "nhl": "hockey/nhl", "cfb": "football/college-football",
           "cbb": "basketball/mens-college-basketball", "epl": "soccer/eng.1", "mlb": "baseball/mlb",
           "ucl": "soccer/uefa.champions", "lal": "soccer/esp.1", "bun": "soccer/ger.1", "sea": "soccer/ita.1",
           "fl1": "soccer/fra.1", "uel": "soccer/uefa.europa"}

def espn_board(lg, yyyymmdd):
    return http.get_json(f"{ESPN}/{LEAGUES[lg]}/scoreboard", {"dates": yyyymmdd, "limit": 400}, cache=True).get("events", [])

def espn_plays(lg, eid):
    s = http.get_json(f"{ESPN}/{LEAGUES[lg]}/summary", {"event": eid}, cache=True)
    out = []
    for p in s.get("plays", []) or []:
        w = ts(p.get("wallclock"))
        if w:
            out.append({"t": w, "text": p.get("text"), "scoring": bool(p.get("scoringPlay")), "away": p.get("awayScore"),
                        "home": p.get("homeScore"), "period": (p.get("period") or {}).get("number"),
                        "clock": (p.get("clock") or {}).get("displayValue"), "type": (p.get("type") or {}).get("text")})
    return out, s
