"""Pre-game makers: closing-line value, price just before the fill, and discount to the DraftKings close (ESPN pickcenter).
usage: python3 deep2.py <name> [max_markets]"""
import sys, collections, random, json, time
from concurrent.futures import ThreadPoolExecutor
import lib
from pmlab import dataapi, stats, http

name = sys.argv[1]; MAXM = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
DAYS = {"forecastication4": 14, "0x99f0d31f": 14, "0x9f15613e": 14}
F = [r for r in lib.fills(name, DAYS[name]) if r["side"] == "BUY" and r["role"] == "M"]
M = lib.meta([r["condition_id"] for r in F]); R = lib.resol([r["condition_id"] for r in F])
now = int(time.time())
def gs(c):
    m = M.get(c) or {}
    return lib.ts(m.get("gameStartTime") or m.get("eventStartTime"))
F = [r for r in F if gs(r["condition_id"]) and r["timestamp"] < gs(r["condition_id"]) - 300]
conds = sorted(set(r["condition_id"] for r in F)); random.Random(7).shuffle(conds); keep = set(conds[:MAXM])
F = [r for r in F if r["condition_id"] in keep]
bytok = collections.defaultdict(list)
for r in F: bytok[r["token_id"]].append(r)
def series(tok):
    rs = bytok[tok]; c = rs[0]["condition_id"]; t0 = min(r["timestamp"] for r in rs) - 1200; t1 = gs(c) + 300
    b = 60 if t0 > now - 6.5 * 86400 else 300
    try:
        return tok, sorted((p["timestamp"], float(p["price"])) for p in dataapi.prices_history(tok, t0, t1, b))
    except Exception as e:
        return tok, []
with ThreadPoolExecutor(6) as ex: S = dict(ex.map(series, list(bytok)))
def at(tok, t):
    s = S.get(tok) or []; v = None
    for ts_, p in s:
        if ts_ <= t: v = p
        else: break
    return v
def final(r):
    rv = R.get(r["condition_id"])
    if not rv or not rv.get("resolved"): return None
    return float((rv.get("final") or {}).get(r["outcome"]) or 0.0)
rows = []
for r in F:
    c = r["condition_id"]; g = gs(c)
    rows.append({**r, "gs": g, "close": at(r["token_id"], g - 60), "before": at(r["token_id"], r["timestamp"] - 180),
                 "after": at(r["token_id"], min(r["timestamp"] + 900, g - 60)), "final": final(r), "type": (M[c].get("sportsMarketType") or "?"),
                 "sport": r["slug"].split("-")[0]})
def agg(sel, f, label):
    per = collections.defaultdict(lambda: [0.0, 0.0]); n = 0
    for r in rows:
        if not sel(r): continue
        v = f(r)
        if v is None: continue
        per[r["event_slug"]][0] += v * r["size"]; per[r["event_slug"]][1] += r["size"]; n += 1
    if len(per) < 4: print(f"   {label:52s} n={n} events={len(per)} (too few)"); return
    e, se = stats.ratio_cluster([v[0] for v in per.values()], [v[1] for v in per.values()])[:2]
    print(f"   {label:52s} fills={n:5d} events={len(per):4d}  {100*e:+6.2f} c/sh  se {100*se:5.2f}  t {e/se if se else 0:+5.2f}")
print(f"\n===== {name}: pre-game maker buys (>=5 min before start): {len(rows)} fills, {len(bytok)} tokens, {len(set(r['event_slug'] for r in rows))} events")
A = lambda r: True
agg(A, lambda r: None if r["close"] is None else r["close"] - r["price"], "CLV: price 1 min before start - fill price")
agg(A, lambda r: None if r["before"] is None else r["price"] - r["before"], "fill price - price 3 min BEFORE the fill")
agg(A, lambda r: None if r["after"] is None else r["after"] - r["price"], "price 15 min after the fill - fill price")
agg(A, lambda r: None if r["final"] is None else r["final"] - r["price"], "final - fill price (realised edge)")
agg(A, lambda r: None if (r["final"] is None or r["close"] is None) else r["final"] - r["close"], "final - close (luck after the close)")
for k in ("moneyline", "spreads", "totals"):
    agg(lambda r: r["type"] == k, lambda r: None if r["close"] is None else r["close"] - r["price"], f"CLV {k}")
for lo, hi in ((0, .15), (.15, .4), (.4, .6), (.6, .85), (.85, 1)):
    agg(lambda r: lo <= r["price"] < hi, lambda r: None if r["close"] is None else r["close"] - r["price"], f"CLV fill price {lo}-{hi}")
for lo, hi, lab in ((300, 3600, "5-60 min before"), (3600, 6 * 3600, "1-6 h before"), (6 * 3600, 9e9, ">6 h before")):
    agg(lambda r: lo <= r["gs"] - r["timestamp"] < hi, lambda r: None if r["close"] is None else r["close"] - r["price"], f"CLV placed {lab}")
half = sorted(r["timestamp"] for r in rows)[len(rows) // 2]
agg(lambda r: r["timestamp"] < half, lambda r: None if r["close"] is None else r["close"] - r["price"], "CLV first half of window")
agg(lambda r: r["timestamp"] >= half, lambda r: None if r["close"] is None else r["close"] - r["price"], "CLV second half of window")
pos = sum(1 for r in rows if r["close"] is not None and r["close"] > r["price"] + 1e-9); neg = sum(1 for r in rows if r["close"] is not None and r["close"] < r["price"] - 1e-9)
print(f"   fills with close > fill: {pos}, close < fill: {neg}, equal/unknown: {len(rows)-pos-neg}")

# ---- DraftKings close (ESPN pickcenter) for nba / nfl / cfb / cbb
def prob(o):
    o = float(o); return -o / (-o + 100) if o < 0 else 100 / (o + 100)
def devig(a, b):
    pa, pb = prob(a), prob(b); return pa / (pa + pb)
def norm(s): return "".join(ch for ch in (s or "").lower() if ch.isalnum())
boards = {}
def board(lg, d):
    if (lg, d) not in boards:
        extra = {"groups": 50} if lg == "cbb" else ({"groups": 80} if lg == "cfb" else {})
        try: boards[(lg, d)] = http.get_json(f"{lib.ESPN}/{lib.LEAGUES[lg]}/scoreboard", {"dates": d, "limit": 500, **extra}, cache=True).get("events", [])
        except Exception: boards[(lg, d)] = []
    return boards[(lg, d)]
import datetime as dt
ev_rows = collections.defaultdict(list)
for r in rows:
    if r["sport"] in ("nba", "nfl", "cfb", "cbb") and r["type"] in ("moneyline", "spreads", "totals"): ev_rows[r["event_slug"]].append(r)
def match(es):
    rs = ev_rows[es]; lg = rs[0]["sport"]; g = rs[0]["gs"]; parts = es.split("-")
    ab = (parts[1], parts[2])
    for off in (0, -1):
        d = (dt.datetime.fromtimestamp(g, dt.timezone.utc) + dt.timedelta(days=off)).strftime("%Y%m%d")
        for e in board(lg, d):
            if abs((lib.ts(e.get("date")) or 0) - g) > 5400: continue
            comp = e["competitions"][0]["competitors"]; abbr = {norm(c["team"].get("abbreviation")) for c in comp}
            names = set()
            for c in comp:
                for k in ("name", "shortDisplayName", "displayName", "location", "abbreviation"): names.add(norm(c["team"].get(k)))
            outs = {norm(r["outcome"]) for r in rs if r["type"] != "totals"}
            if (norm(ab[0]) in abbr and norm(ab[1]) in abbr) or (outs and outs <= names):
                return es, e["id"], lg
    return es, None, lg
with ThreadPoolExecutor(4) as ex: matched = list(ex.map(match, list(ev_rows)))
def summ(x):
    es, eid, lg = x
    if not eid: return es, None
    try: return es, http.get_json(f"{lib.ESPN}/{lib.LEAGUES[lg]}/summary", {"event": eid}, cache=True)
    except Exception: return es, None
with ThreadPoolExecutor(4) as ex: SUM = dict(ex.map(summ, matched))
out = []
for es, s in SUM.items():
    if not s: continue
    pc = [p for p in (s.get("pickcenter") or []) if p.get("awayTeamOdds") and p.get("homeTeamOdds")]
    if not pc: continue
    p = pc[0]; comp = s["header"]["competitions"][0]["competitors"]
    tn = {}
    for c in comp:
        t = c["team"]; tn[c["homeAway"]] = {norm(t.get(k)) for k in ("name", "shortDisplayName", "displayName", "location", "abbreviation", "nickname")}
    for r in ev_rows[es]:
        m = M[r["condition_id"]]; fair = None; o = norm(r["outcome"])
        try:
            if r["type"] == "moneyline":
                a, h = p["awayTeamOdds"].get("moneyLine"), p["homeTeamOdds"].get("moneyLine")
                if a is None or h is None: continue
                side = "away" if o in tn["away"] else ("home" if o in tn["home"] else None)
                if side: fair = devig(a, h) if side == "away" else devig(h, a)
            elif r["type"] == "totals":
                if m.get("line") is None or p.get("overUnder") is None or abs(float(m["line"]) - float(p["overUnder"])) > 1e-6: continue
                fair = devig(p["overOdds"], p["underOdds"]) if o == "over" else devig(p["underOdds"], p["overOdds"])
            elif r["type"] == "spreads":
                if m.get("line") is None or p.get("spread") is None or abs(abs(float(m["line"])) - abs(float(p["spread"]))) > 1e-6: continue
                fav = "away" if p["awayTeamOdds"].get("favorite") else "home"; dog = "home" if fav == "away" else "away"
                outs = [norm(x) for x in json.loads(m["outcomes"])]
                if outs[0] not in tn[fav]: continue   # the market's first outcome is the team giving points
                fo, do = p[fav + "TeamOdds"].get("spreadOdds"), p[dog + "TeamOdds"].get("spreadOdds")
                if fo is None or do is None: continue
                fair = devig(fo, do) if o in tn[fav] else (devig(do, fo) if o in tn[dog] else None)
        except Exception: continue
        if fair is not None: out.append({**r, "fair": fair})
print(f"-- DraftKings close matched: events {sum(1 for x in matched if x[1])}/{len(matched)}, fills with a same-line DK price: {len(out)}")
def agg2(sel, f, label):
    per = collections.defaultdict(lambda: [0.0, 0.0]); n = 0
    for r in out:
        if not sel(r): continue
        v = f(r)
        if v is None: continue
        per[r["event_slug"]][0] += v * r["size"]; per[r["event_slug"]][1] += r["size"]; n += 1
    if len(per) < 4: print(f"   {label:52s} n={n} (too few)"); return
    e, se = stats.ratio_cluster([v[0] for v in per.values()], [v[1] for v in per.values()])[:2]
    print(f"   {label:52s} fills={n:5d} events={len(per):4d}  {100*e:+6.2f} c/sh  se {100*se:5.2f}  t {e/se if se else 0:+5.2f}")
agg2(A, lambda r: r["fair"] - r["price"], "DK de-vigged close - fill price (all)")
agg2(A, lambda r: None if r["close"] is None else r["fair"] - r["close"], "DK de-vigged close - Polymarket close (sanity)")
for k in ("moneyline", "spreads", "totals"): agg2(lambda r: r["type"] == k, lambda r: r["fair"] - r["price"], f"DK close - fill, {k}")
for sp in ("nba", "nfl", "cfb", "cbb"): agg2(lambda r: r["sport"] == sp, lambda r: r["fair"] - r["price"], f"DK close - fill, {sp}")
below = sum(1 for r in out if r["price"] < r["fair"] - 0.005); above = sum(1 for r in out if r["price"] > r["fair"] + 0.005)
print(f"   fills priced >0.5c below DK fair: {below}; >0.5c above: {above}; within 0.5c: {len(out)-below-above}")
agg2(A, lambda r: None if r["final"] is None else r["final"] - r["fair"], "final - DK fair (should be ~0)")
json.dump([{k: r.get(k) for k in ("slug", "outcome", "price", "size", "timestamp", "gs", "close", "before", "after", "final", "type", "sport", "fair")} for r in rows], open(f"{lib.HERE}/out/{name}_deep2.json", "w"))
json.dump([{k: r.get(k) for k in ("slug", "outcome", "price", "size", "timestamp", "gs", "close", "final", "type", "sport", "fair")} for r in out], open(f"{lib.HERE}/out/{name}_deep2_dk.json", "w"))
