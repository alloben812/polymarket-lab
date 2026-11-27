"""Whole-history persistence: realised edge per month / type, errors clustered by event. usage: deep_full.py <name> <start YYYY-MM-DD>"""
import sys, collections, json, gzip, os, time, datetime as dt
import lib
from pmlab import wallet as W, stats
name, start = sys.argv[1], sys.argv[2]
p = f"{lib.HERE}/fills/{name}_full.json.gz"
if os.path.exists(p): F = json.load(gzip.open(p, "rt"))
else:
    s = int(dt.datetime.fromisoformat(start).replace(tzinfo=dt.timezone.utc).timestamp())
    F, tr = W.fetch_fills(lib.WALLETS[name], s, int(time.time()), None)
    for r in F: r["size"] = float(r["size"]); r["price"] = float(r["price"])
    json.dump(F, gzip.open(p, "wt"))
M = lib.meta([r["condition_id"] for r in F]); R = lib.resol([r["condition_id"] for r in F])
def fin(r):
    rv = R.get(r["condition_id"])
    if not rv or not rv.get("resolved"): return None
    return float((rv.get("final") or {}).get(r["outcome"]) or 0.0)
def gs(c): m = M.get(c) or {}; return lib.ts(m.get("gameStartTime") or m.get("eventStartTime"))
def tab(title, keyfn, rows):
    agg = collections.defaultdict(lambda: collections.defaultdict(lambda: [0.0, 0.0])); n = collections.Counter(); usd = collections.Counter()
    for r in rows:
        f = fin(r)
        if f is None: continue
        sg = 1 if r["side"] == "BUY" else -1
        v = sg * (f - r["price"]) - (0.05 * r["price"] * (1 - r["price"]) if r["role"] == "T" else 0)
        k = keyfn(r); a = agg[k][r["event_slug"]]; a[0] += v * r["size"]; a[1] += r["size"]; n[k] += 1; usd[k] += r["size"] * r["price"]
    print(f"-- {title}")
    for k in sorted(agg, key=lambda k: str(k)):
        per = agg[k]
        if len(per) < 4: continue
        e, se, t = stats.ratio_cluster([v[0] for v in per.values()], [v[1] for v in per.values()])
        print(f"   {str(k):34s} fills {n[k]:6d} events {len(per):5d} ${usd[k]:>11,.0f}  net ${sum(v[0] for v in per.values()):>9,.0f}  {100*e:+6.2f} c/sh  t {t:+5.2f}")
print(f"\n===== {name}: {len(F)} fills since {start}, {len(set(r['condition_id'] for r in F))} markets, {len(set(r['event_slug'] for r in F))} events; maker share of $ {sum(r['size']*r['price'] for r in F if r['role']=='M')/sum(r['size']*r['price'] for r in F):.3f}; sells {sum(1 for r in F if r['side']=='SELL')}")
B = [r for r in F if r["side"] == "BUY"]
tab("all buys", lambda r: "all", B)
tab("by month", lambda r: dt.datetime.fromtimestamp(r["timestamp"], dt.timezone.utc).strftime("%Y-%m"), B)
tab("by market type (top)", lambda r: (M.get(r["condition_id"]) or {}).get("sportsMarketType") if (M.get(r["condition_id"]) or {}).get("sportsMarketType") in ("moneyline", "spreads", "totals", "child_moneyline", "first_half_totals", "first_half_spreads") else "other", B)
tab("by sport (top 10 by fills)", lambda r: r["slug"].split("-")[0] if r["slug"].split("-")[0] in [k for k, _ in collections.Counter(x["slug"].split("-")[0] for x in B).most_common(10)] else "other", B)
tab("by fill price", lambda r: ("a <0.15" if r["price"] < .15 else "b 0.15-0.40" if r["price"] < .4 else "c 0.40-0.60" if r["price"] < .6 else "d 0.60-0.85" if r["price"] < .85 else "e >=0.85"), B)
def rel(r):
    g = gs(r["condition_id"])
    if not g: return "?"
    d = r["timestamp"] - g
    return "a >6h before" if d < -21600 else "b 1-6h before" if d < -3600 else "c <1h before" if d < 0 else "d 0-1h after start" if d < 3600 else "e 1-3h after" if d < 10800 else "f >3h after"
tab("by time relative to game start", rel, B)
tab("Over vs Under vs team", lambda r: r["outcome"] if r["outcome"] in ("Over", "Under", "Yes", "No") else "team/player", B)
