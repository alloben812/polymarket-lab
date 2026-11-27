"""dashattacker: in-play soccer totals. What is bought, at which match minute and game state, relative to goals
(ESPN wall clock and the tape's own price jump), and what the price did next."""
import sys, collections, json, time, bisect, statistics as st, datetime as dt
from concurrent.futures import ThreadPoolExecutor
import lib
from pmlab import dataapi, stats, http

name = sys.argv[1] if len(sys.argv) > 1 else "dashattacker"
ALL = [r for r in lib.fills(name, 14) if r["side"] == "BUY"]
M = lib.meta([r["condition_id"] for r in ALL]); R = lib.resol([r["condition_id"] for r in ALL])
now = int(time.time())
def gs(c): m = M.get(c) or {}; return lib.ts(m.get("gameStartTime") or m.get("eventStartTime"))
def final(r):
    rv = R.get(r["condition_id"])
    if not rv or not rv.get("resolved"): return None
    return float((rv.get("final") or {}).get(r["outcome"]) or 0.0)
def clus(rows, f, label, fee=False):
    per = collections.defaultdict(lambda: [0.0, 0.0]); n = 0
    for r in rows:
        v = f(r)
        if v is None: continue
        if fee and r["role"] == "T": v -= 0.05 * r["price"] * (1 - r["price"])
        per[r["event_slug"]][0] += v * r["size"]; per[r["event_slug"]][1] += r["size"]; n += 1
    if len(per) < 4: print(f"   {label:58s} n={n} (too few)"); return
    e, se, t = stats.ratio_cluster([v[0] for v in per.values()], [v[1] for v in per.values()])
    print(f"   {label:58s} fills={n:5d} events={len(per):4d} ${sum(r['size']*r['price'] for r in rows if f(r) is not None):>10,.0f}  {100*e:+6.2f} c/sh  se {100*se:5.2f}  t {t:+5.2f}")
for r in ALL:
    m = M[r["condition_id"]]; r["rel"] = r["timestamp"] - gs(r["condition_id"]); r["fin"] = final(r)
    r["type"] = m.get("sportsMarketType"); r["line"] = m.get("line")
    # match minute: 0-45 first half, 15 min break (+ ~3 min stoppage), then second half
    mn = r["rel"] / 60.0
    r["minute"] = mn if mn <= 48 else (45 if mn < 63 else 45 + (mn - 63))
tot = [r for r in ALL if r["type"] in ("totals", "first_half_totals") and r["rel"] >= 0]
print(f"===== {name}: {len(ALL)} buys; in-play totals buys {len(tot)}")
print("-- outcome bought x role (final - fill, after taker fee)")
for ty in ("totals", "first_half_totals"):
    for o in ("Over", "Under"):
        for role in ("T", "M"):
            clus([r for r in tot if r["type"] == ty and r["outcome"] == o and r["role"] == role], lambda r: None if r["fin"] is None else r["fin"] - r["price"], f"{ty} {o} {role}", fee=True)
print("-- by approximate match minute (full-time totals, taker)")
for lo, hi in ((0, 15), (15, 30), (30, 45.01), (45.01, 60), (60, 75), (75, 90), (90, 200)):
    clus([r for r in tot if r["type"] == "totals" and r["role"] == "T" and lo <= r["minute"] < hi], lambda r: None if r["fin"] is None else r["fin"] - r["price"], f"minute {lo}-{hi}", fee=True)
print("-- by fill price (all in-play totals, taker)")
for lo, hi in ((0, .5), (.5, .7), (.7, .85), (.85, .95), (.95, 1.01)):
    clus([r for r in tot if r["role"] == "T" and lo <= r["price"] < hi], lambda r: None if r["fin"] is None else r["fin"] - r["price"], f"price {lo}-{hi}", fee=True)
half = sorted(r["timestamp"] for r in tot)[len(tot) // 2]
clus([r for r in tot if r["role"] == "T" and r["timestamp"] < half], lambda r: None if r["fin"] is None else r["fin"] - r["price"], "taker, first half of the window", fee=True)
clus([r for r in tot if r["role"] == "T" and r["timestamp"] >= half], lambda r: None if r["fin"] is None else r["fin"] - r["price"], "taker, second half of the window", fee=True)
# ---- markouts (1-minute prices, last 6.5 days)
REC = [r for r in tot if r["timestamp"] > now - 6.5 * 86400]
bytok = collections.defaultdict(list)
for r in REC: bytok[r["token_id"]].append(r)
def series(tok):
    rs = bytok[tok]
    try: return tok, sorted((p["timestamp"], float(p["price"])) for p in dataapi.prices_history(tok, min(x["timestamp"] for x in rs) - 900, max(x["timestamp"] for x in rs) + 2000, 60))
    except Exception: return tok, []
with ThreadPoolExecutor(6) as ex: S = dict(ex.map(series, list(bytok)))
K = {t: [x[0] for x in s] for t, s in S.items()}
def at(tok, t):
    k = K.get(tok) or []; i = bisect.bisect_right(k, t) - 1
    return S[tok][i][1] if i >= 0 else None
for r in REC:
    for lab, d in (("b3", -180), ("b10", -600), ("a1", 90), ("a5", 300), ("a15", 900)): r[lab] = at(r["token_id"], r["timestamp"] + d)
for role in ("T", "M"):
    rows = [r for r in REC if r["role"] == role]
    print(f"-- markouts role {role} ({len(rows)} fills, last 6.5 days)")
    clus(rows, lambda r: None if r["b10"] is None else r["price"] - r["b10"], "fill - price 10 min before")
    clus(rows, lambda r: None if r["b3"] is None else r["price"] - r["b3"], "fill - price 3 min before")
    clus(rows, lambda r: None if r["a1"] is None else r["a1"] - r["price"], "price +90 s - fill")
    clus(rows, lambda r: None if r["a5"] is None else r["a5"] - r["price"], "price +5 min - fill")
    clus(rows, lambda r: None if r["a15"] is None else r["a15"] - r["price"], "price +15 min - fill")
    clus(rows, lambda r: None if r["fin"] is None else r["fin"] - r["price"], "final - fill (before fee)")
    for o in ("Over", "Under"):
        clus([r for r in rows if r["outcome"] == o], lambda r: None if r["a5"] is None else r["a5"] - r["price"], f"  +5 min, {o}")
        clus([r for r in rows if r["outcome"] == o], lambda r: None if r["b3"] is None else r["price"] - r["b3"], f"  fill - 3 min before, {o}")
# ---- goals: ESPN wall clock vs tape jump vs fills, big leagues
LG = {"ucl": "soccer/uefa.champions", "epl": "soccer/eng.1", "lal": "soccer/esp.1", "bun": "soccer/ger.1", "sea": "soccer/ita.1", "fl1": "soccer/fra.1",
      "uel": "soccer/uefa.europa", "elc": "soccer/eng.2", "es2": "soccer/esp.2", "bl2": "soccer/ger.2", "unl": "soccer/uefa.nations"}
lib.LEAGUES.update(LG)
evs = collections.defaultdict(list)
for r in tot:
    if r["type"] == "totals" and r["slug"].split("-")[0] in LG: evs[r["event_slug"]].append(r)
def match(es):
    rs = evs[es]; g = gs(rs[0]["condition_id"]); parts = es.split("-"); lg = parts[0]; best = None
    for off in (0, -1):
        d = (dt.datetime.fromtimestamp(g, dt.timezone.utc) + dt.timedelta(days=off)).strftime("%Y%m%d")
        for e in lib.board2(lg, d):
            if abs((lib.ts(e.get("date")) or 0) - g) > 900: continue
            ab = {lib.norm(c["team"].get("abbreviation")) for c in e["competitions"][0]["competitors"]}
            k = len(ab & {lib.norm(parts[1]), lib.norm(parts[2])})
            if k and (best is None or k > best[0]): best = (k, e["id"])
    return es, (best[1] if best else None)
with ThreadPoolExecutor(4) as ex: MT = dict(ex.map(match, list(evs)))
def goals(es):
    eid = MT.get(es)
    if not eid: return es, None
    try: s = http.get_json(f"{lib.ESPN}/{LG[es.split('-')[0]]}/summary", {"event": eid}, cache=True)
    except Exception: return es, None
    g = []
    for c in (s.get("commentary") or []):
        p = c.get("play") or {}
        if ((p.get("type") or {}).get("type") or "").startswith("goal") or (p.get("scoringPlay") and "Goal" in (p.get("text") or "")):
            w = lib.ts(p.get("wallclock"))
            if w: g.append(w)
    if not g:
        for p in (s.get("keyEvents") or []):
            if p.get("scoringPlay") and lib.ts(p.get("wallclock")): g.append(lib.ts(p.get("wallclock")))
    return es, sorted(set(g))
with ThreadPoolExecutor(4) as ex: G = dict(ex.map(goals, list(evs)))
ok = {es: g for es, g in G.items() if g is not None}
print(f"-- ESPN goals: events matched {sum(1 for v in MT.values() if v)}/{len(evs)}, with goal wall clocks {sum(1 for g in ok.values() if g)}")
bins = [(-600, -60), (-60, 0), (0, 15), (15, 45), (45, 120), (120, 300), (300, 900)]
cnt = collections.Counter(); usd = collections.Counter(); state = collections.defaultdict(lambda: [0, 0.0, 0.0, 0.0])
for es, g in ok.items():
    for r in evs[es]:
        tm = r["timestamp"] - 3
        for lo, hi in bins:
            if any(lo <= tm - x < hi for x in g): cnt[(r["role"], r["outcome"], f"{lo:+d}..{hi:+d}s from a goal")] += 1; usd[(r["role"], r["outcome"], f"{lo:+d}..{hi:+d}s from a goal")] += r["size"] * r["price"]
        cnt[(r["role"], r["outcome"], "all")] += 1; usd[(r["role"], r["outcome"], "all")] += r["size"] * r["price"]
        if r["line"] is not None and r["fin"] is not None:
            need = float(r["line"]) + 0.5 - sum(1 for x in g if x <= tm)   # goals still needed for Over
            k = (r["outcome"], f"Over needs {int(need) if need < 4 else '4+'} more", "min<60" if r["minute"] < 60 else ("60-75" if r["minute"] < 75 else "75+"))
            a = state[k]; a[0] += 1; a[1] += r["size"] * r["price"]; a[2] += r["size"]; a[3] += r["size"] * (r["fin"] - r["price"] - (0.05 * r["price"] * (1 - r["price"]) if r["role"] == "T" else 0))
print("-- fills by time from an ESPN goal wall clock (per-second rate = fills / window length)")
for k in sorted(cnt):
    w = k[2]
    if w == "all": print(f"   {k}: fills {cnt[k]}, ${usd[k]:,.0f}"); continue
    lo, hi = [int(x) for x in w.split("s")[0].split("..")]
    print(f"   {k}: fills {cnt[k]:4d}  ${usd[k]:>9,.0f}  per second {cnt[k]/(hi-lo):.3f}")
print("-- game state at the fill (ESPN goals so far vs the line): fills, $, avg price, net c/sh after fee")
for k in sorted(state):
    a = state[k]
    if a[0] >= 15: print(f"   {str(k):48s} fills {a[0]:4d}  ${a[1]:>9,.0f}  avg px {a[1]/a[2]:.3f}  net {100*a[3]/a[2]:+6.2f} c/sh")
json.dump({"goals": ok, "match": MT}, open(f"{lib.HERE}/out/{name}_deep4_goals.json", "w"))
json.dump([{k: r.get(k) for k in ("slug", "event_slug", "condition_id", "token_id", "outcome", "role", "price", "size", "timestamp", "rel", "minute", "line", "type", "fin", "b3", "a1", "a5")} for r in tot], open(f"{lib.HERE}/out/{name}_deep4.json", "w"))
