"""Screen leaderboard candidates: what share of the last 30 days' fills is in economics-keyword markets?"""
import json, re, sys, time, collections
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, "/home/user/polymarket-lab")
from pmlab import dataapi
ECON = re.compile(r"(\bfed\b|fomc|interest-rate|rate-cut|rate-hike|bps|\bcpi\b|inflation|jobs|payroll|unemployment|jobless|gdp|recession|\becb\b|bank-of-|boj|boe|\brba\b|\bsnb\b|\bpce\b|\bppi\b|powell|fed-chair|treasury-yield|mortgage|tariff-revenue|central-bank|riksbank|norges|selic|copom|banxico|cbrt|turkey-rate)", re.I)
L = json.load(open("leaders.json"))
now = int(time.time())
def ok(r):
    ms = [v for _, v in r["months"][-3:]]
    return (r["mkts"] >= 150 or r["fills"] >= 1500) and r["kept_all"] > 0 and sum(1 for v in ms if v > 0) >= 2 and (r["rebates_all"] / r["kept_all"] < 0.4)
cands = [r for r in L if ok(r)]
def scr(r):
    fills = list(dataapi.iter_trades(user=r["wallet"], start=now - 30 * 86400, end=now, taker_only=False, max_rows=4000))
    tot = eco = 0.0; ev = collections.Counter(); conds = set(); econds = set()
    for f in fills:
        u = float(f["size"]) * float(f["price"]); tot += u
        s = (f.get("event_slug") or "") + " " + (f.get("slug") or "")
        conds.add(f["condition_id"])
        if ECON.search(s):
            eco += u; ev[f.get("event_slug")] += u; econds.add(f["condition_id"])
    span = (now - min((f["timestamp"] for f in fills), default=now)) / 86400
    return r, len(fills), span, tot, eco, len(conds), len(econds), ev.most_common(4)
with ThreadPoolExecutor(6) as ex:
    res = list(ex.map(scr, cands))
out = []
print(f"{'name':26} {'kept_all':>10} {'catM':>8} {'fills30':>7} {'days':>5} {'usd':>10} {'eco%':>5} {'mk':>5} {'ecoMk':>5} {'$/fill':>7}  top econ events")
for r, n, span, tot, eco, nc, ne, ev in sorted(res, key=lambda x: -(x[4] / x[3] if x[3] else 0)):
    print(f"{r['name'][:26]:26} {r['kept_all']:10.0f} {r['cat_month'] or 0:8.0f} {n:7d} {span:5.1f} {tot:10.0f} {100*eco/tot if tot else 0:5.1f} {nc:5d} {ne:5d} {tot/n if n else 0:7.0f}  " + "; ".join(f"{k}:{v:.0f}" for k, v in ev[:3]))
    out.append({"name": r["name"], "wallet": r["wallet"], "fills30": n, "span_days": span, "usd": tot, "eco_share": eco / tot if tot else 0, "markets": nc, "eco_markets": ne})
json.dump(out, open("screen.json", "w"), indent=1)
