"""How the maker accounts earn: pair/leftover decomposition, round trips, exposure, capital tied, exits.
Uses fills + inventory events only (all markets of the 14-day window)."""
import json, collections, statistics as st, sys
import lib
from pmlab import stats
def P(*a): print(*a, flush=True)
q = lambda v, p: sorted(v)[min(len(v) - 1, int(len(v) * p))] if v else None
for name in sys.argv[1:]:
    F = lib.fills(name); I = lib.inv(name); conds = {f["condition_id"] for f in F}; M = lib.meta(conds); R = lib.resol(conds)
    usd = lambda r: r["size"] * r["price"]
    # capital: running cash
    ev = [(f["timestamp"], (-usd(f) if f["side"] == "BUY" else usd(f))) for f in F] + [(int(e["timestamp"]), float(e.get("usdc_size") or 0)) for e in I if e.get("type") in ("MERGE", "REDEEM")]
    ev.sort(); cash = 0; low = 0; path = []
    for t, x in ev: cash += x; low = min(low, cash); path.append(cash)
    byc = collections.defaultdict(list)
    for f in F: byc[f["condition_id"]].append(f)
    pair = []; left = []; rt = []; invp = []; maxexp = []; flips = []; span = []; lastfill_to_close = []
    for c, fs in byc.items():
        r = R.get(c) or {}; m = M.get(c) or {}
        if not r.get("resolved"): continue
        outs = lib.gamma.jfield(m.get("outcomes")) or []; 
        if len(outs) != 2: continue
        fin = [float(r["final"].get(o) or 0) for o in outs]
        b = {o: [0.0, 0.0] for o in outs}; s = {o: [0.0, 0.0] for o in outs}
        net = 0.0; mx = 0.0; sign = 0; nf = 0
        for f in fs:
            o = f["outcome"]
            if o not in b: continue
            (b if f["side"] == "BUY" else s)[o][0] += f["size"]; (b if f["side"] == "BUY" else s)[o][1] += usd(f)
            d = (1 if o == outs[0] else -1) * (1 if f["side"] == "BUY" else -1)
            pr0 = f["price"] if o == outs[0] else 1 - f["price"]
            net += d * f["size"]; mx = max(mx, abs(net) * (pr0 if net > 0 else 1 - pr0))
            sg = 1 if net > 1 else -1 if net < -1 else 0
            if sg and sign and sg != sign: nf += 1
            if sg: sign = sg
        maxexp.append(mx); flips.append(nf); span.append((fs[-1]["timestamp"] - fs[0]["timestamp"]) / 60)
        ct = lib.ts(m.get("closedTime"))
        if ct: lastfill_to_close.append((ct - fs[-1]["timestamp"]) / 60)
        # round trips per outcome (sell matched against buys of the same outcome)
        rtp = 0.0; rem = {}
        for o in outs:
            n = min(b[o][0], s[o][0])
            if n > 0: rtp += n * (s[o][1] / s[o][0] - b[o][1] / b[o][0])
            rem[o] = (b[o][0] - n, b[o][1] / b[o][0] if b[o][0] else 0, s[o][0] - n, s[o][1] / s[o][0] if s[o][0] else 0)
        # pairs among the remaining long shares
        n = min(rem[outs[0]][0], rem[outs[1]][0]); pp = n * (1 - rem[outs[0]][1] - rem[outs[1]][1]) if n > 0 else 0.0
        lp = 0.0
        for i, o in enumerate(outs):
            lp += (rem[o][0] - n) * (fin[i] - rem[o][1]) + rem[o][2] * (rem[o][3] - fin[i])   # leftover longs and net shorts (sold more than bought in the window)
        pair.append(pp); left.append(lp); rt.append(rtp); invp.append(sum(b[o][1] for o in outs))
    tot = sum(pair) + sum(left) + sum(rt)
    ms = lambda v: (lambda r: f"{sum(v):10,.0f} (t {r[2]:.2f})")(stats.mean_se(v))
    P(f"== {name}: resolved binary markets {len(pair)}; buys ${sum(invp):,.0f}")
    P(f"   round trips (sold what it bought): {ms(rt)}   pairs (both outcomes held, at average cost): {ms(pair)}   leftover one-sided inventory to settlement: {ms(left)}   total {tot:,.0f} before fees")
    P(f"   peak capital tied (lowest running cash in the window): ${-low:,.0f}; max one-sided exposure per market: median ${q(maxexp,.5):,.0f} p90 ${q(maxexp,.9):,.0f} max ${max(maxexp):,.0f}; exposure sign flips per market median {q(flips,.5)} p90 {q(flips,.9)}")
    P(f"   minutes in a market (first to last fill): median {q(span,.5):.0f} p90 {q(span,.9):.0f}; last fill -> on-chain close: median {q(lastfill_to_close,.5):.0f} min")
    mg = [e for e in I if e.get("type") == "MERGE"]; 
    if mg:
        dl = []
        for e in mg:
            m = M.get(e["condition_id"]) or {}; ct = lib.ts(m.get("closedTime"))
            if ct: dl.append((ct - int(e["timestamp"])) / 60)
        P(f"   merges {len(mg)}, ${sum(float(e.get('usdc_size') or 0) for e in mg):,.0f}; minutes before the on-chain close: median {q(dl,.5):.0f} p10 {q(dl,.1):.0f} p90 {q(dl,.9):.0f} (positive = during the match)")
    sz = [usd(f) for f in F if f["role"] == "M"]; 
    if sz: P(f"   maker fill $: median {q(sz,.5):,.0f} p90 {q(sz,.9):,.0f}; maker fills per market median {q([sum(1 for f in fs if f['role']=='M') for fs in byc.values()],.5)}")
    day = collections.defaultdict(float)
    Jm = {m["condition"]: m for m in json.load(open(f"{lib.HERE}/{name}.json"))["_markets"]}
    for c, fs in byc.items():
        if c in Jm and Jm[c].get("resolved"): day[fs[0]["timestamp"] // 86400] += Jm[c]["net"]
    dv = [day[k] for k in sorted(day)]; P(f"   daily net after fees: {' '.join(f'{x/1000:.1f}k' for x in dv)}; positive days {sum(1 for x in dv if x > 0)}/{len(dv)}; day-level t {stats.mean_se(dv)[2]:.2f}")
