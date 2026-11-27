"""Screen tech-board candidates: share of the last 30 days' turnover that is in tech-tagged markets (gamma tags)."""
import json, sys, time, collections
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, "/home/user/polymarket-lab")
from pmlab import dataapi, gamma
TECH = {"tech", "ai", "big-tech", "openai", "technology", "artificial-intelligence", "spacex", "apple", "tesla", "nvidia", "elon-musk-ai", "gpt", "chatgpt"}
L = json.load(open("leaders.json"))
now = int(time.time())
def ok(r):
    if "error" in r: return False
    ms = [v for _, v in r["months"][-3:]]
    pos = sum(1 for v in ms if v > 0)
    return (r["mkts"] >= 150 or r["fills"] >= 1500) and r["kept_all"] > 0 and (pos >= 2 if len(ms) >= 3 else pos == len(ms)) and (r["rebates_all"] / r["kept_all"] < 0.4)
cands = [r for r in L if ok(r)]
sys.stderr.write(f"{len(cands)} candidates of {len(L)}\n")
def scr(r):
    try:
        fills = list(dataapi.iter_trades(user=r["wallet"], start=now - 30 * 86400, end=now, taker_only=False, max_rows=4000))
    except Exception as e:
        return r, 0, 0, 0, 0, 0, 0, [], str(e)[:60]
    tot = 0.0; bycond = collections.Counter(); ev = {}
    for f in fills:
        u = float(f["size"]) * float(f["price"]); tot += u; bycond[f["condition_id"]] += u; ev[f["condition_id"]] = f.get("event_slug") or f.get("slug")
    top = [c for c, _ in bycond.most_common(80)]
    meta = gamma.markets_by_condition(top)
    tech = 0.0; cov = 0.0; tev = collections.Counter(); ntech = 0
    for c in top:
        m = meta.get(c)
        if not m: continue
        cov += bycond[c]
        tags = set(gamma.tag_slugs(m))
        if tags & TECH:
            tech += bycond[c]; tev[ev[c]] += bycond[c]; ntech += 1
    span = (now - min((f["timestamp"] for f in fills), default=now)) / 86400
    return r, len(fills), span, tot, tech, len(bycond), ntech, tev.most_common(4), f"cov={cov/tot if tot else 0:.2f}"
with ThreadPoolExecutor(6) as ex:
    res = list(ex.map(scr, cands))
out = []
print(f"{'name':26} {'kept_all':>10} {'catM':>8} {'fills30':>7} {'days':>5} {'usd':>10} {'tech%':>5} {'techUsd':>9} {'mk':>5} {'tMk':>4} {'$/fill':>7}  note; top tech events")
for r, n, span, tot, tech, nc, nt, ev, note in sorted(res, key=lambda x: -x[4]):
    print(f"{r['name'][:26]:26} {r['kept_all']:10.0f} {r.get('cat_month') or 0:8.0f} {n:7d} {span:5.1f} {tot:10.0f} {100*tech/tot if tot else 0:5.1f} {tech:9.0f} {nc:5d} {nt:4d} {tot/n if n else 0:7.0f}  {note}; " + "; ".join(f"{(k or '')[:38]}:{v:.0f}" for k, v in ev[:3]))
    out.append({"name": r["name"], "wallet": r["wallet"], "fills30": n, "span_days": span, "usd": tot, "tech_usd": tech, "markets": nc, "tech_markets_top80": nt})
json.dump(out, open("screen.json", "w"), indent=1)
