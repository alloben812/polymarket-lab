"""Falsification checks for the up/down accounts (fills of 2026-11-21..26)."""
import json, collections, statistics, math
import numpy as np
import ud
from pmlab import fair, stats
ACCTS = {"0x50f7": "0xee65685de42f8de9a03b4c53ee77d56a20d2cfc9", "tiredofwinning2much": "0xcd4a4057125bceabd687c38167deeacf425b224e",
         "mo-money": "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3", "0x0dbd0e1d": "0x0dbd0e1d5999a401263dc26cbf1597f2be0cfcd5"}
R = {n: ud.enrich(ud.fills(n, w)["fills"], ud.finals(n)) for n, w in ACCTS.items()}
# ---- 1. calibration of the Binance fair model on the passive account's fills (one observation per market x minute)
print("1. calibration of pmlab.fair (sigma_mult 1.3) at tiredofwinning2much's fill times, Up probability vs official outcome, one obs per market-minute")
seen = {}
for r in R["tiredofwinning2much"]:
    if not r["final_official"] or r["left"] < 5: continue
    up_fair = r["fair"] if r["outcome"] == "Up" else 1 - r["fair"]; up_win = r["final"] if r["outcome"] == "Up" else 1 - r["final"]
    seen[(r["condition_id"], r["tm"] // 60)] = (max(up_fair, 1 - up_fair), up_win if up_fair >= .5 else 1 - up_win, r["condition_id"])
b = collections.defaultdict(list)
for f, w, c in seen.values():
    b["0.50-0.60" if f < .6 else "0.60-0.70" if f < .7 else "0.70-0.80" if f < .8 else "0.80-0.90" if f < .9 else "0.90-0.97" if f < .97 else "0.97-1.00"].append((f, w, c))
for k in sorted(b):
    v = b[k]; print(f"   leader fair {k}: n={len(v):5} markets={len({c for _,_,c in v}):4} mean fair {np.mean([x[0] for x in v]):.3f}  leader won {np.mean([x[1] for x in v]):.3f}")
# ---- 2. profile of fair around the fill (speed): fair(tm+k) - price, weighted by shares
print("\n2. Binance fair value of the bought outcome at (match time + k s) minus fill price, cents per share, buys only")
KS = (-30, -10, -5, -3, -2, -1, 0, 1, 2, 3, 5, 10, 30)
print(f"{'account role':34}" + "".join(f"{k:>7}" for k in KS) + "   fills")
for n, rows in R.items():
    for role in "TM":
        for lab, sel in (("all", lambda r: True), ("px 0.30-0.95", lambda r: .3 <= r["price"] < .95)):
            rr = [r for r in rows if r["role"] == role and r["side"] == "BUY" and sel(r) and r["left"] > 15]
            if len(rr) < 200: continue
            out = []
            for k in KS:
                num = den = 0.0
                for r in rr:
                    P = ud.px(r["asset"]); v = fair.fair_up(P, r["tm"] + k, r["t0"], r["t1"] - r["t0"], 60, r["k"])
                    if v != v: continue
                    v = v if r["outcome"] == "Up" else 1 - v
                    num += (v - r["price"]) * r["size"]; den += r["size"]
                out.append(100 * num / den)
            print(f"{(n + ' ' + role + ' ' + lab)[:34]:34}" + "".join(f"{x:7.2f}" for x in out) + f"   {len(rr)}")
# ---- 3. does BTC lead the alt fills? signed spot move (bp) in the 5 s and 30 s before the match, own asset and BTC
print("\n3. signed spot move before the match (bp, + = towards the bought outcome): own asset / BTC, taker buys")
B = ud.px("btc")
for n in ("0x0dbd0e1d", "mo-money"):
    for a in ("btc", "eth", "sol", "xrp"):
        rr = [r for r in R[n] if r["role"] == "T" and r["side"] == "BUY" and r["asset"] == a and r["left"] > 15]
        if len(rr) < 50: continue
        P = ud.px(a); w = np.array([r["size"] for r in rr]); s = np.array([1 if r["outcome"] == "Up" else -1 for r in rr])
        def mv(Q, d0, d1): return np.array([(Q.price(r["tm"] - d1) / Q.price(r["tm"] - d0) - 1) * 1e4 for r in rr]) * s
        def wm(x): ok = ~np.isnan(x); return (x[ok] * w[ok]).sum() / w[ok].sum()
        print(f"   {n:12} {a}: fills {len(rr):5}  own -5..0s {wm(mv(P,5,0)):6.2f}  own -30..-5s {wm(mv(P,30,5)):6.2f}  own 0..+30s {wm(mv(P,0,-30)):6.2f} | btc -5..0s {wm(mv(B,5,0)):6.2f}  btc -30..-5s {wm(mv(B,30,5)):6.2f}")
# ---- 4. 0x50f7: the 0.95+ buys. When, how far from the strike, how often wrong
print("\n4. 0x50f7 buys at price >= 0.95")
rr = [r for r in R["0x50f7"] if r["price"] >= .95 and r["side"] == "BUY"]
usd = lambda x: sum(r["size"] * r["price"] for r in x)
print(f"   fills {len(rr)}, usd {usd(rr):,.0f}, markets {len({r['condition_id'] for r in rr})}, maker share {usd([r for r in rr if r['role']=='M'])/usd(rr):.2f}")
def lb(l): return "a >120s before end" if l > 120 else "b 60-120s" if l > 60 else "c 30-60s" if l > 30 else "d 10-30s" if l > 10 else "e 0-10s" if l > 0 else "f after end 0-30s" if l > -30 else "g after end >30s"
g = collections.defaultdict(list)
for r in rr: g[lb(r["left"])].append(r)
print(f"   {'when':22} {'fills':>5} {'mkts':>5} {'usd':>10} {'avg_px':>7} {'med |gap| bp':>12} {'med gap/sigma':>13} {'lost mkts':>9} {'lost usd':>9} {'net$':>8} {'net c/sh':>8}")
for k in sorted(g):
    v = g[k]; ms = {r["condition_id"] for r in v}; lost = [r for r in v if r["final"] == 0]
    net = sum(r["size"] * (r["final"] - r["price"]) - r["fee"] for r in v); sh = sum(r["size"] for r in v)
    gs = [r["gap_bp"] / (r["sig"] * 1e4 * math.sqrt(max(r["left"], 1))) for r in v if r["sig"] == r["sig"] and r["sig"] > 0 and r["left"] > 0]
    print(f"   {k:22} {len(v):5} {len(ms):5} {usd(v):10,.0f} {usd(v)/sh:7.4f} {statistics.median(abs(r['gap_bp']) for r in v):12.1f} {statistics.median(gs) if gs else float('nan'):13.1f} {len({r['condition_id'] for r in lost}):9} {usd(lost):9,.0f} {net:8,.0f} {100*net/sh:8.3f}")
lost = [r for r in rr if r["final"] == 0]
bym = collections.defaultdict(list)
for r in lost: bym[r["slug"]].append(r)
print("   losing markets:")
for s, v in sorted(bym.items(), key=lambda x: -usd(x[1])):
    print(f"     {s:32} usd {usd(v):8,.0f} fills {len(v):3} roles {''.join(sorted({r['role'] for r in v}))} px {min(r['price'] for r in v):.3f}-{max(r['price'] for r in v):.3f} left {max(r['left'] for r in v):4}..{min(r['left'] for r in v):4}s gap_bp at fill {statistics.median(r['gap_bp'] for r in v):6.1f} fair {statistics.median(r['fair'] for r in v):.3f}")
wins = [r for r in rr if r["final"] == 1]
print(f"   breakeven: avg win per $ = {sum(r['size']*(1-r['price']) for r in wins)/usd(wins)*100:.3f}c; loss share needed to wipe it = same; observed lost usd share {usd(lost)/usd(rr)*100:.3f}%")
by = collections.Counter()
for r in rr: by["decided: after window end" if r["left"] <= 0 else "inside last 60 s (TWAP running)" if r["left"] <= 60 else "more than 60 s before end"] += r["size"] * r["price"]
print("   usd by state of the deciding observation:", {k: round(v) for k, v in by.items()})
# ---- 5. tired: quoting pattern inside a market (levels per side, time between fills) and how residual arises
print("\n5. tiredofwinning2much: per-market behaviour")
bym = collections.defaultdict(list)
for r in R["tiredofwinning2much"]: bym[r["condition_id"]].append(r)
first = [min(r["rel"] for r in v) for v in bym.values()]; last = [min(r["left"] for r in v) for v in bym.values()]
print(f"   first fill median {statistics.median(first):.0f}s after window start; last fill median {statistics.median(last):.0f}s before end; fills per market median {statistics.median(len(v) for v in bym.values())}")
sizes = collections.Counter(round(r["size"]) for r in R["tiredofwinning2much"]); print("   most common fill sizes (shares):", sizes.most_common(6))
imb = []
for v in bym.values():
    u = sum(r["size"] for r in v if r["outcome"] == "Up"); d_ = sum(r["size"] for r in v if r["outcome"] == "Down")
    imb.append(abs(u - d_) / max(u + d_, 1e-9))
print(f"   |Up-Down| share imbalance per market: median {statistics.median(imb):.2f}, p90 {sorted(imb)[int(.9*len(imb))]:.2f}")
