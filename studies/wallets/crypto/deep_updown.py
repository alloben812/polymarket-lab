"""Up/down accounts: where in the window, at what price vs Binance fair value, pairs vs residual, concurrency."""
import sys, collections, statistics, json
import ud
ACCTS = {"0x50f7": "0xee65685de42f8de9a03b4c53ee77d56a20d2cfc9", "tiredofwinning2much": "0xcd4a4057125bceabd687c38167deeacf425b224e",
         "mo-money": "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3", "0x0dbd0e1d": "0x0dbd0e1d5999a401263dc26cbf1597f2be0cfcd5"}
name = sys.argv[1]
d = ud.fills(name, ACCTS[name]); fin = ud.finals(name)
raw = d["fills"]; rows = ud.enrich(raw, fin)
print(f"== {name}: fills {len(raw)} (truncated={d['truncated']}), enriched up/down fills {len(rows)}, official outcome for {sum(r['final_official'] for r in rows)}")
agree = [r for r in rows if r["final_official"] and r["proxy"] is not None]
print("Binance proxy agrees with official outcome on fills:", sum(1 for r in agree if r["proxy"] == r["final"]), "/", len(agree))
sells = [r for r in rows if r["side"] == "SELL"]
print("sell fills:", len(sells), "usd", round(sum(r["size"] * r["price"] for r in sells)))
ud.tab(rows, lambda r: (r["role"], r["fam"]), title="by role and family")
def pb(p): return "0.00-0.05" if p < .05 else "0.05-0.30" if p < .3 else "0.30-0.70" if p < .7 else "0.70-0.95" if p < .95 else "0.95-0.99" if p < .99 else "0.99-1.00"
ud.tab(rows, lambda r: (r["role"], pb(r["price"])), title="by role and price")
def lb(r):
    l = r["left"]
    return "a >600s left" if l > 600 else "b 300-600" if l > 300 else "c 120-300" if l > 120 else "d 60-120" if l > 60 else "e 20-60 (in TWAP)" if l > 20 else "f 0-20" if l > 0 else "g after end 0-30s" if l > -30 else "h after end >30s"
ud.tab(rows, lambda r: (r["role"], lb(r)), title="by role and seconds left to window end (match time = block time - 3 s)")
def fb(r):
    x = r["fair"] - r["price"]
    return None if x != x else "fair-px < -10c" if x < -.10 else "-10..-3c" if x < -.03 else "-3..0c" if x < 0 else "0..3c" if x < .03 else "3..10c" if x < .10 else "> +10c"
ud.tab(rows, lambda r: (r["role"], fb(r)), title="by role and (Binance fair - fill price) at match time")
# pairs vs residual per market
bym = collections.defaultdict(lambda: {"Up": [0.0, 0.0], "Down": [0.0, 0.0], "fin": None, "fam": None, "fee": 0.0})
for r in rows:
    if r["side"] != "BUY" or r["final"] is None: continue
    m = bym[r["condition_id"]]; m[r["outcome"]][0] += r["size"]; m[r["outcome"]][1] += r["size"] * r["price"]; m["fam"] = r["fam"]; m["fee"] += r["fee"]
    m["fin"] = r["final"] if r["outcome"] == "Up" else 1 - r["final"]
tot = collections.defaultdict(lambda: collections.Counter())
for c, m in bym.items():
    u, dn = m["Up"], m["Down"]; pair = min(u[0], dn[0]); T = tot[m["fam"]]
    T["mkts"] += 1; T["both"] += 1 if pair > 0 else 0
    if pair > 0:
        pc = u[1] / u[0] + dn[1] / dn[0]; T["pair_sh"] += pair; T["pair_cost"] += pair * pc; T["pair_pnl"] += pair * (1 - pc)
    for o, x, win in (("Up", u, m["fin"]), ("Down", dn, 1 - m["fin"])):
        res = x[0] - pair
        if res > 1e-9:
            ap = x[1] / x[0]; T["res_sh"] += res; T["res_cost"] += res * ap; T["res_pnl"] += res * (win - ap); T["res_win_sh"] += res * win
    T["fee"] += m["fee"]
print("\npairs vs residual (buys only, per market; pair = min(Up shares, Down shares) at each side's average price)")
print(f"{'family':10} {'mkts':>5} {'both':>5} {'pair_sh':>9} {'pair_cost':>9} {'pair_pnl$':>9} {'res_sh':>9} {'res_avg_px':>10} {'res_win%':>8} {'res_pnl$':>9} {'fees$':>7}")
for f, T in sorted(tot.items()):
    print(f"{f:10} {T['mkts']:5} {T['both']:5} {T['pair_sh']:9.0f} {T['pair_cost']/T['pair_sh'] if T['pair_sh'] else float('nan'):9.4f} {T['pair_pnl']:9.0f} {T['res_sh']:9.0f} {T['res_cost']/T['res_sh'] if T['res_sh'] else float('nan'):10.3f} {100*T['res_win_sh']/T['res_sh'] if T['res_sh'] else float('nan'):8.1f} {T['res_pnl']:9.0f} {T['fee']:7.0f}")
# concurrency and sizing
sz = sorted(r["size"] * r["price"] for r in rows)
print(f"\nfill usd: median {statistics.median(sz):.2f}, p90 {sz[int(.9*len(sz))]:.2f}, max {sz[-1]:.0f}")
per_m = collections.Counter()
for r in rows: per_m[r["condition_id"]] += r["size"] * r["price"]
v = sorted(per_m.values()); print(f"usd per market: median {statistics.median(v):.0f}, p90 {v[int(.9*len(v))]:.0f}, max {v[-1]:.0f}; markets {len(v)}")
live = collections.defaultdict(set)
for r in rows: live[r["tm"] // 60].add(r["condition_id"])
c = sorted(len(s) for s in live.values()); print(f"distinct markets with a fill per minute: median {statistics.median(c)}, p90 {c[int(.9*len(c))]}, max {c[-1]}")
days = collections.defaultdict(float)
for r in rows:
    if r["final"] is not None and r["side"] == "BUY": days[r["tm"] // 86400] += r["size"] * (r["final"] - r["price"]) - r["fee"]
print("net by UTC day:", {k * 86400: round(v) for k, v in sorted(days.items())})
json.dump([{k: r[k] for k in ("slug", "outcome", "side", "role", "size", "price", "tm", "left", "fair", "gap_bp", "final", "final_official", "fee", "condition_id")} for r in rows], open(ud.HERE / "out" / f"ud_{name}.json", "w"))
