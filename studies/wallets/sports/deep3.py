"""In-play makers: markouts after the fill, pair (both outcomes) accounting, NBA scoring-play alignment.
usage: python3 deep3.py <name> <days>"""
import sys, collections, json, time, statistics as st
from concurrent.futures import ThreadPoolExecutor
import lib
from pmlab import dataapi, stats

name, days = sys.argv[1], float(sys.argv[2])
ALL = lib.fills(name, days)
M = lib.meta([r["condition_id"] for r in ALL]); R = lib.resol([r["condition_id"] for r in ALL])
now = int(time.time())
def gs(c):
    m = M.get(c) or {}; return lib.ts(m.get("gameStartTime") or m.get("eventStartTime"))
def final(r):
    rv = R.get(r["condition_id"])
    if not rv or not rv.get("resolved"): return None
    return float((rv.get("final") or {}).get(r["outcome"]) or 0.0)
def clus(rows, f, label):
    per = collections.defaultdict(lambda: [0.0, 0.0]); n = 0
    for r in rows:
        v = f(r)
        if v is None: continue
        per[r["event_slug"]][0] += v * r["size"]; per[r["event_slug"]][1] += r["size"]; n += 1
    if len(per) < 4: print(f"   {label:56s} n={n} (too few)"); return
    e, se, t = stats.ratio_cluster([v[0] for v in per.values()], [v[1] for v in per.values()])
    print(f"   {label:56s} fills={n:6d} events={len(per):4d}  {100*e:+6.2f} c/sh  se {100*se:5.2f}  t {t:+5.2f}")

print(f"\n===== {name}: {len(ALL)} fills in {days} days")
# ---------- pair accounting (whole window, resolved markets)
pm = collections.defaultdict(lambda: collections.defaultdict(lambda: [0.0, 0.0, None]))
for r in ALL:
    if r["side"] != "BUY": continue
    a = pm[r["condition_id"]][r["outcome"]]; a[0] += r["size"]; a[1] += r["size"] * r["price"]
    a[2] = r["timestamp"] if a[2] is None else min(a[2], r["timestamp"])
tot = pair = resid = 0.0; nboth = 0; costs = []; gaps = []; msh = ush = 0.0; pe = collections.defaultdict(float); re_ = collections.defaultdict(float)
for c, d in pm.items():
    rv = R.get(c)
    if not rv or not rv.get("resolved"): continue
    fin = rv.get("final") or {}
    pnl = sum(v[0] * float(fin.get(o) or 0) - v[1] for o, v in d.items())
    ev = (M.get(c) or {}).get("slug") or c
    if len(d) == 2:
        (o1, v1), (o2, v2) = d.items(); m_ = min(v1[0], v2[0]); cost = v1[1] / v1[0] + v2[1] / v2[0]
        pp = m_ * (1 - cost); nboth += 1; costs.append(cost); gaps.append(abs(v1[2] - v2[2])); msh += m_; ush += abs(v1[0] - v2[0])
    else:
        pp = 0.0; ush += sum(v[0] for v in d.values())
    tot += pnl; pair += pp; resid += pnl - pp
print(f"-- pair accounting (resolved markets, buys only): markets {len(pm)}, with both outcomes bought {nboth}")
if costs:
    print(f"   matched shares {msh:,.0f}, unmatched shares {ush:,.0f}; pair cost median {st.median(costs):.4f}, share of pairs under 1.00: {sum(1 for c in costs if c < 1)/len(costs):.2f}; median gap between first buys of the two legs {st.median(gaps)/60:.1f} min")
print(f"   total buy PnL {tot:,.0f} = locked pair profit {pair:,.0f} + one-sided inventory result {resid:,.0f}")

# ---------- markouts (fills of the last 6.5 days, 1-minute prices)
REC = [r for r in ALL if r["timestamp"] > now - 6.5 * 86400 and r["side"] == "BUY" and gs(r["condition_id"])]
bytok = collections.defaultdict(list)
for r in REC: bytok[r["token_id"]].append(r)
def series(tok):
    rs = bytok[tok]; t0 = min(r["timestamp"] for r in rs) - 900; t1 = max(r["timestamp"] for r in rs) + 2000
    try: return tok, sorted((p["timestamp"], float(p["price"])) for p in dataapi.prices_history(tok, t0, t1, 60))
    except Exception: return tok, []
with ThreadPoolExecutor(6) as ex: S = dict(ex.map(series, list(bytok)))
import bisect
K = {t: [x[0] for x in s] for t, s in S.items()}
def at(tok, t):
    k = K.get(tok) or []; i = bisect.bisect_right(k, t) - 1
    return S[tok][i][1] if i >= 0 else None
for r in REC:
    r["rel"] = r["timestamp"] - gs(r["condition_id"]); r["fin"] = final(r)
    for lab, d in (("b3", -180), ("a1", 90), ("a5", 300), ("a15", 900)): r[lab] = at(r["token_id"], r["timestamp"] + d)
for role in ("M", "T"):
    for lab, sel in (("in-play (after start)", lambda r: r["rel"] >= 0), ("pre-game", lambda r: r["rel"] < 0)):
        rows = [r for r in REC if r["role"] == role and sel(r)]
        if len(rows) < 30: continue
        print(f"-- markouts, role {role}, {lab}: {len(rows)} fills, ${sum(r['size']*r['price'] for r in rows):,.0f}")
        clus(rows, lambda r: None if r["b3"] is None else r["price"] - r["b3"], "fill price - price 3 min before")
        clus(rows, lambda r: None if r["a1"] is None else r["a1"] - r["price"], "price +90 s - fill")
        clus(rows, lambda r: None if r["a5"] is None else r["a5"] - r["price"], "price +5 min - fill")
        clus(rows, lambda r: None if r["a15"] is None else r["a15"] - r["price"], "price +15 min - fill")
        clus(rows, lambda r: None if r["fin"] is None else r["fin"] - r["price"], "final - fill")
        for lo, hi in ((0, .1), (.1, .35), (.35, .65), (.65, .9), (.9, 1.01)):
            clus([r for r in rows if lo <= r["price"] < hi], lambda r: None if r["a5"] is None else r["a5"] - r["price"], f"  +5 min markout, fill price {lo}-{hi}")
        sp = collections.Counter(r["slug"].split("-")[0] for r in rows).most_common(5)
        for s_, _ in sp:
            clus([r for r in rows if r["slug"].startswith(s_ + "-")], lambda r: None if r["a5"] is None else r["a5"] - r["price"], f"  +5 min markout, {s_}")

# ---------- NBA: maker fills vs ESPN scoring plays (wall clock); match time = block time - 3 s
nba = [r for r in ALL if r["slug"].startswith("nba-") and r["side"] == "BUY" and (M[r["condition_id"]].get("sportsMarketType") == "moneyline") and gs(r["condition_id"]) and r["timestamp"] >= gs(r["condition_id"])]
evs = collections.defaultdict(list)
for r in nba: evs[r["event_slug"]].append(r)
hit = collections.Counter(); n_ev = 0
for es, rs in evs.items():
    g = gs(rs[0]["condition_id"]); outs = json.loads(M[rs[0]["condition_id"]]["outcomes"])
    eid = lib.espn_match(es, g, outs)
    if not eid: continue
    plays, s = lib.espn_plays("nba", eid)
    comp = s["header"]["competitions"][0]["competitors"]; side = {}
    for c in comp:
        for k in ("name", "shortDisplayName", "displayName", "location", "abbreviation"): side[lib.norm(c["team"].get(k))] = c["homeAway"]
    sc = []; pa = ph = 0
    for p in plays:
        if p["scoring"] and p["away"] is not None:
            who = "away" if p["away"] > pa else "home"; sc.append((p["t"], who))
        if p["away"] is not None: pa, ph = p["away"], p["home"]
    if not sc: continue
    n_ev += 1; end = plays[-1]["t"]
    for r in rs:
        mine = side.get(lib.norm(r["outcome"]))
        if not mine: continue
        tm = r["timestamp"] - 3
        if tm > end: hit[(r["role"], "after final play")] += 1; continue
        for lab, lo, hi in (("test [-20,0]s", -20, 0), ("placebo [-80,-60]s", -80, -60)):
            opp = sum(1 for t, w in sc if lo <= t - tm <= hi and w != mine); own = sum(1 for t, w in sc if lo <= t - tm <= hi and w == mine)
            hit[(r["role"], lab, "opp scored" if opp and not own else ("own scored" if own and not opp else ("both" if own else "none")))] += 1
print(f"-- NBA moneyline in-play buys vs ESPN scoring plays: {len(nba)} fills, {n_ev}/{len(evs)} games matched")
for k in sorted(hit): print("   ", k, hit[k])
json.dump([{k: r.get(k) for k in ("slug", "outcome", "role", "price", "size", "timestamp", "rel", "b3", "a1", "a5", "a15", "fin")} for r in REC], open(f"{lib.HERE}/out/{name}_deep3.json", "w"))
