"""Sceptic: jozeslemsek whole-life cash reconstruction (2026-03-25 .. 2026-11-27), per-market P&L with open inventory
marked three ways, concentration, month of realisation, where the inventory sits."""
import pickle, collections, json, datetime as dt, math, re
from pmlab import dataapi
d = pickle.load(open("/home/user/polymarket-lab/data/econ_tapes/sceptic_jozeslemsek.pkl", "rb"))
fills, act = d["fills"], d["act"]; pos = d["pos"]["data"]
mon = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m")
buy = sum(f["size"] * f["price"] for f in fills if f["side"] == "BUY"); sell = sum(f["size"] * f["price"] for f in fills if f["side"] == "SELL")
fee = sum(0.03 * f["size"] * f["price"] * (1 - f["price"]) for f in fills if f["role"] == "T")
typ = collections.defaultdict(float)
for r in act:
    if r["type"] != "TRADE": typ[r["type"]] += float(r.get("usdc_size") or 0)
print(f"life cash: buys {buy:.0f} sells {sell:.0f} redeems {typ['REDEEM']:.0f} rewards {typ['REWARD']:.0f} maker rebates {typ['MAKER_REBATE']:.0f} yield {typ['YIELD']:.2f}; taker fee (API all-time) 193 net of refund")
cash = sell - buy + typ["REDEEM"] + typ["REWARD"] + typ["MAKER_REBATE"] + typ["YIELD"] - 193
pv = sum(p["current_value"] for p in pos); pc = sum(p["total_cost_usdc"] for p in pos)
print(f"net cash out of the account's whole life: {cash:.0f}; open positions: {len(pos)} rows, cost {pc:.0f}, API current value {pv:.0f}; cash + value = {cash+pv:.0f} (API economic_pnl 6,714)")
# per token: shares left, cash
tok = collections.defaultdict(lambda: {"sh": 0.0, "cash": 0.0, "cond": None, "slug": None, "ev": None, "out": None, "last_sell": 0, "bm": collections.defaultdict(float)})
for f in sorted(fills, key=lambda f: f["timestamp"]):
    t = tok[f["token_id"]]; t["cond"] = f["condition_id"]; t["slug"] = f["slug"]; t["ev"] = f.get("event_slug") or f["slug"]; t["out"] = f["outcome"]
    s = 1 if f["side"] == "BUY" else -1
    t["sh"] += s * f["size"]; t["cash"] -= s * f["size"] * f["price"]; t["bm"][mon(f["timestamp"])] -= s * f["size"] * f["price"]
conds = sorted({t["cond"] for t in tok.values()})
res = dataapi.resolutions(conds)
posv = {p["token_id"]: p for p in pos}
mk = collections.defaultdict(lambda: {"cash": 0.0, "val_final": 0.0, "val_api": 0.0, "cost_left": 0.0, "resolved": True, "slug": None, "ev": None, "neg": 0})
for tid, t in tok.items():
    m = mk[t["cond"]]; m["slug"] = t["slug"]; m["ev"] = t["ev"]; m["cash"] += t["cash"]
    r = res.get(t["cond"]) or {}
    if t["sh"] < -1: m["neg"] += 1
    if r.get("resolved"):
        m["val_final"] += max(t["sh"], 0) * float((r["final"].get(t["out"]) or 0))
    else:
        m["resolved"] = False
        p = posv.get(tid)
        if p: m["val_api"] += p["current_value"]; m["cost_left"] += p["total_cost_usdc"]
R = [m for m in mk.values() if m["resolved"]]; O = [m for m in mk.values() if not m["resolved"]]
def t_(xs):
    n = len(xs); mu = sum(xs) / n; v = sum((x - mu) ** 2 for x in xs) / (n - 1); return mu / math.sqrt(v / n)
pr = sorted((m["cash"] + m["val_final"] for m in R), reverse=True)
print(f"\nRESOLVED markets (whole life, complete by construction): {len(R)}, P&L {sum(pr):.0f}, positive {sum(1 for x in pr if x>0)}, t {t_(pr):.2f}; top3 {sum(pr[:3]):.0f}, rest {sum(pr[3:]):.0f} (t {t_(pr[3:]):.2f}); worst3 {sum(pr[-3:]):.0f}")
for m in sorted(R, key=lambda m: -(m["cash"] + m["val_final"]))[:5]: print(f"    {m['slug'][:70]:70} {m['cash']+m['val_final']:8.0f}")
po = sorted(((m["cash"] + m["val_api"], m["cash"], m["val_api"], m["cost_left"], m["slug"], m["ev"]) for m in O), reverse=True)
print(f"OPEN markets: {len(O)}: cash so far {sum(x[1] for x in po):.0f}, API value of what is left {sum(x[2] for x in po):.0f} (cost {sum(x[3] for x in po):.0f}); P&L if marked at API price {sum(x[0] for x in po):.0f}, if the rest expires worthless {sum(x[1] for x in po):.0f}")
print(f"   top3 open markets at API mark {sum(x[0] for x in po[:3]):.0f}; rest {sum(x[0] for x in po[3:]):.0f}")
for x in po[:8]: print(f"    {x[4][:66]:66} pnl@mark {x[0]:7.0f} cash {x[1]:7.0f} value_left {x[2]:6.0f}")
ev = collections.defaultdict(float)
for m in O: ev[m["ev"]] += m["cash"] + m["val_api"]
for m in R: ev[m["ev"]] += m["cash"] + m["val_final"]
es = sorted(ev.items(), key=lambda kv: -kv[1]); tot = sum(ev.values())
print(f"\nBY EVENT (resolved at final, open at API mark): {len(es)} events, total {tot:.0f}; top3 {sum(v for _, v in es[:3]):.0f}; top10 {sum(v for _, v in es[:10]):.0f}; positive {sum(1 for _, v in es if v > 0)}")
for k, v in es[:10]: print(f"    {k[:70]:70} {v:7.0f}")
print("    ... worst:", [(k[:40], round(v)) for k, v in es[-4:]])
fedev = sum(v for k, v in ev.items() if re.search(r"fed-|fomc|rate-(hike|cut)|fed$", k)); print(f"   events with 'fed' in the slug: {fedev:.0f} of {tot:.0f}")
# inventory: where and at what price
print("\nOPEN INVENTORY by current price:")
for lo, hi in ((0, 0.01), (0.01, 0.05), (0.05, 0.2), (0.2, 1.01)):
    s = [p for p in pos if lo <= p["current_price"] < hi]
    print(f"   price {lo}-{hi}: {len(s)} positions, cost {sum(p['total_cost_usdc'] for p in s):.0f}, API value {sum(p['current_value'] for p in s):.0f}, shares {sum(p['current_size'] for p in s):.0f}")
for p in sorted(pos, key=lambda p: -p["total_cost_usdc"])[:10]: print(f"    {p['slug'][:64]:64} sh {p['current_size']:8.0f} avg {p['avg_price']:.4f} now {p['current_price']:.4f} cost {p['total_cost_usdc']:6.0f} value {p['current_value']:6.0f}")
# buy price distribution by dollars, whole life and November
for lab, sel in (("life", fills), ("Nov", [f for f in fills if mon(f["timestamp"]) == "2026-11"])):
    b = [f for f in sel if f["side"] == "BUY"]; tot_b = sum(f["size"] * f["price"] for f in b)
    sh = collections.OrderedDict()
    for lo, hi in ((0, 0.01), (0.01, 0.03), (0.03, 0.10), (0.10, 0.30), (0.30, 1.01)):
        sh[f"{lo}-{hi}"] = round(100 * sum(f["size"] * f["price"] for f in b if lo <= f["price"] < hi) / tot_b)
    print(f"buy dollars by price ({lab}, ${tot_b:.0f}): {dict(sh)}; maker share of buy $ {100*sum(f['size']*f['price'] for f in b if f['role']=='M')/tot_b:.0f}%")
json.dump({"cash": cash, "pos_value": pv, "resolved_pnl": sum(pr), "open_cash": sum(x[1] for x in po), "open_value": sum(x[2] for x in po), "events": es[:20]}, open("jozes_life.json", "w"))
