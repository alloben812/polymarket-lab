"""Market-by-market stories for one account (88 days to 2026-11-27): what it bought, when, at what price, exit or hold, outcome.
usage: stories.py <label> <wallet> [n_markets]"""
import json, sys, collections, datetime as dt, statistics as st, pickle, os
sys.path.insert(0, "/home/user/polymarket-lab")
from pmlab import wallet as W, gamma, dataapi
label, addr = sys.argv[1], sys.argv[2]; N = int(sys.argv[3]) if len(sys.argv) > 3 else 14
END = 1795793940; START = END - 88 * 86400
fp = f"/home/user/polymarket-lab/data/econ_tapes/fills_{label}.pkl"
if os.path.exists(fp):
    fills = pickle.load(open(fp, "rb"))
else:
    fills, _ = W.fetch_fills(addr, START, END, 60000); pickle.dump(fills, open(fp, "wb"))
d = json.load(open(f"{label}_88d.json"))
mk = {m["condition"]: m for m in d["_markets"]}
f = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%m-%d %H:%M")
econ = [m for m in d["_markets"] if m["family"] == "economics"]
by = collections.defaultdict(list)
for r in fills:
    by[r["condition_id"]].append(r)
meta = gamma.markets_by_condition([m["condition"] for m in sorted(econ, key=lambda m: -m["turnover"])[:N]])
print(f"##### {label}: {len(fills)} fills, {len(econ)} economics markets")
# aggregate behaviour over ALL economics markets
buy_sh = sell_sh = 0; pos_cost = []; hold_days = []; weeks = collections.defaultdict(set); bpx = []
for m in econ:
    fs = by.get(m["condition"], [])
    b = sum(r["size"] for r in fs if r["side"] == "BUY"); s = sum(r["size"] for r in fs if r["side"] == "SELL")
    buy_sh += b; sell_sh += s
    if m["buy_usd"] > 0: pos_cost.append(m["buy_usd"])
    for r in fs:
        weeks[dt.datetime.fromtimestamp(r["timestamp"], dt.timezone.utc).strftime("%G-%V")].add(m["condition"])
        if r["side"] == "BUY": bpx.append((r["price"], r["size"] * r["price"]))
    if m.get("end") and fs:
        t0 = min(r["timestamp"] for r in fs if r["side"] == "BUY") if any(r["side"] == "BUY" for r in fs) else None
        if t0: hold_days.append((m["end"] - t0) / 86400)
tot = sum(u for _, u in bpx) or 1
def share(lo, hi): return sum(u for p, u in bpx if lo <= p < hi) / tot
print(f"  shares bought {buy_sh:.0f}, sold {sell_sh:.0f} (sold/bought {sell_sh/buy_sh if buy_sh else 0:.2f}); position cost per market: median {st.median(pos_cost) if pos_cost else 0:.0f}, p90 {sorted(pos_cost)[int(len(pos_cost)*.9)] if pos_cost else 0:.0f}, max {max(pos_cost) if pos_cost else 0:.0f}")
print(f"  first buy to scheduled end, days: median {st.median(hold_days) if hold_days else 0:.1f}, p10 {sorted(hold_days)[int(len(hold_days)*.1)] if hold_days else 0:.1f}, p90 {sorted(hold_days)[int(len(hold_days)*.9)] if hold_days else 0:.1f}")
print(f"  econ markets touched per ISO week: " + " ".join(f"{k[-2:]}:{len(v)}" for k, v in sorted(weeks.items())))
print(f"  buy $ by price: <0.05 {share(0,.05):.2f} | .05-.3 {share(.05,.3):.2f} | .3-.7 {share(.3,.7):.2f} | .7-.9 {share(.7,.9):.2f} | .9-.97 {share(.9,.97):.2f} | >=.97 {share(.97,1.01):.2f}")
for m in sorted(econ, key=lambda m: -m["turnover"])[:N]:
    md = meta.get(m["condition"], {})
    fs = sorted(by.get(m["condition"], []), key=lambda r: r["timestamp"])
    fin = m.get("final")
    print(f"\n- {m['slug'][:80]}  end={f(m['end']) if m['end'] else '-'} closed={f(m['closed_at']) if m.get('closed_at') else 'open'} final={fin if fin else md.get('outcomePrices')} vol={float(md.get('volumeNum') or 0):.0f}")
    desc = (md.get("description") or "").replace("\n", " ")
    print(f"    rules: {desc[:230]}")
    agg = collections.OrderedDict()
    for r in fs:
        k = (dt.datetime.fromtimestamp(r["timestamp"], dt.timezone.utc).strftime("%m-%d"), r["side"], r["role"], r["outcome"])
        a = agg.setdefault(k, [0, 0.0, 0.0, r["timestamp"], r["timestamp"]]); a[0] += 1; a[1] += r["size"]; a[2] += r["size"] * r["price"]; a[4] = r["timestamp"]
    items = list(agg.items())
    show = items if len(items) <= 9 else items[:5] + [None] + items[-3:]
    for it in show:
        if it is None: print(f"    ... {len(items)-8} more day-groups ..."); continue
        k, a = it
        print(f"    {k[0]} {f(a[3])[6:]}-{f(a[4])[6:]} {k[1]:4} {k[2]} {k[3]:4} n={a[0]:4d} sh={a[1]:9.0f} px={a[2]/a[1]:.3f} usd={a[2]:8.0f}")
    print(f"    net shares now {({k: round(v) for k, v in m['sh'].items() if abs(v) > 0.5})}; cash {m['cash']:.0f}; net {m.get('net') if m.get('resolved') and not m['incomplete'] else 'n/a (open or incomplete)'}")
