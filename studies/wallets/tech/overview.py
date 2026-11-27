"""88-day overview per account: API bottom line vs tool, and tech sub-families (markets, turnover, role, price, timing)."""
import statistics as st, collections, sys
from common import *
for name in ACC:
    d = load(name); a = d["api_window"]; ms = d["_markets"]; fl = d["_fills"]
    done = [m for m in ms if m["resolved"] and not m["incomplete"]]
    print(f"\n===== {name}: fills {len(fl)}, markets {len(ms)} (tech {sum(m['tech'] for m in ms)}), turnover {sum(m['turnover'] for m in ms):.0f}, tech turnover {sum(m['turnover'] for m in ms if m['tech']):.0f}")
    print(f"  API 88d: gross {a['trade_pnl']:.0f} fees {a['fees']:.0f} rebates {a['taker_rebate']+a['maker_rebate']+a['reward_income']:.0f} kept {a['economic_pnl']:.0f} volume {a['volume_usdc']:.0f} fills {a['trade_count']:.0f} | tool resolved-complete: {len(done)} mkts gross {sum(m['gross'] for m in done):.0f} fee {sum(m['fee'] for m in done):.0f}; resolved-incomplete {sum(1 for m in ms if m['resolved'] and m['incomplete'])}, open {sum(1 for m in ms if not m['resolved'])}; inv {d['account']['inventory_events']}")
    bym = {m["condition"]: m for m in ms}
    rows = collections.defaultdict(lambda: collections.defaultdict(float)); bp = collections.defaultdict(list); lead = collections.defaultdict(list)
    for r in fl:
        m = bym[r["condition_id"]]; k = m["sub"]; u = r["size"] * r["price"] if not isinstance(r["size"], str) else float(r["size"]) * float(r["price"])
        rows[k]["usd"] += u; rows[k]["T" if r["role"] == "T" else "M"] += u; rows[k][r["side"]] += u; rows[k]["n"] += 1
        if r["side"] == "BUY":
            bp[k].append((float(r["price"]), u))
            if m.get("closed_at"): lead[k].append(((m["closed_at"] - r["timestamp"]) / 3600, u))
    def wq(xs, q):
        xs = sorted(xs); tot = sum(w for _, w in xs); c = 0
        for v, w in xs:
            c += w
            if c >= q * tot: return v
        return float("nan")
    print(f"  {'sub':10} {'mk':>4} {'res':>4} {'inc':>4} {'usd':>8} {'T%':>4} {'buy%':>4} {'fills':>5} {'net_res':>8} {'win%':>4} | buy px q25/50/75 | $ share >=.95 | hours buy->closed q25/50/75 | $ share bought <6h before close")
    for k in sorted(rows, key=lambda k: -rows[k]["usd"]):
        mk = [m for m in ms if m["sub"] == k]; dn = [m for m in mk if m["resolved"] and not m["incomplete"]]
        x = rows[k]; b = bp[k]; l = lead[k]; tb = sum(u for _, u in b) or 1; tl = sum(u for _, u in l) or 1
        print(f"  {k:10} {len(mk):4d} {len(dn):4d} {sum(1 for m in mk if m['incomplete']):4d} {x['usd']:8.0f} {100*x['T']/x['usd']:4.0f} {100*x['BUY']/x['usd']:4.0f} {int(x['n']):5d} {sum(m['net'] for m in dn):8.0f} {100*sum(1 for m in dn if m['net']>0)/len(dn) if dn else 0:4.0f} | {wq(b,.25):.2f}/{wq(b,.5):.2f}/{wq(b,.75):.2f} | {sum(u for p,u in b if p>=.95)/tb:.2f} | {wq(l,.25):7.1f}/{wq(l,.5):7.1f}/{wq(l,.75):7.1f} | {sum(u for h,u in l if h<6)/tl:.2f}")
