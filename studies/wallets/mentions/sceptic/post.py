"""Second pass over the s_*.json / fills files: clean-jump speed, fee actually charged, sides, non-mention pnl, splits."""
import sys, json, collections, statistics as st, datetime as dt, re
sys.path.insert(0, '/home/user/polymarket-lab')
from pmlab import gamma, dataapi
PAT = re.compile(r"(^|-)(say|says|said|mention|mentions|mentioned)(-|$)")
W = {"oidocrop": "0x23c46463c281deb26a041fdcc24ae9c5d7629c42", "Quant": "0x66c1a6fe836ff555ca32848646acedbbe93bfa3f", "Faston": "0xa7fea388f955a9517067111030eb771c6d911f3e"}
FULL = {"oidocrop": "oidocrop", "Quant": "QuantDeLaFugazi", "Faston": "Faston"}
def tstat(v):
    v = list(v)
    if len(v) < 2: return 0
    sd = st.pstdev(v); return sum(v) / (sd * len(v) ** 0.5) if sd else 0
def rate(t):   # schedule suggested by the notes: zero fee 20-31 Oct, 0.01 from 21 Nov; r0 before (to be fitted)
    if 1792454400 <= t < 1793491200: return 0.0          # 2026-10-20 00:00 .. 2026-11-01 00:00 UTC
    if t >= 1795219200: return 0.01                      # 2026-11-21 00:00 UTC
    return None
for n, w in W.items():
    print(f"\n===== {n}")
    both_mk, both_ev = {}, collections.defaultdict(float)
    for tag in ("W0", "A"):
        d = json.load(open(f"s_{FULL[n]}_{tag}.json"))
        fp = f"_fills_{FULL[n]}_W0.json" if tag == "W0" else f"../_fills_{FULL[n]}_45.json"
        fills, _ = json.load(open(fp))
        S = {s['c']: s for s in d['stories']}
        both_mk.update(d['mk_pnl'])
        for k, v in d['ev_pnl'].items(): both_ev[k] += v
        # clean jumps: a print below 0.60 at most 30 min before the first print >= 0.60 (the analyst's R5 definition)
        clean = {c for c, s in S.items() if s['fy'] >= 0.5 and s['tpre'] and s['first_move'] and s['first_move'] - s['tpre'] <= 1800}
        tj = [j for j in d['jump'] if j['c'] in clean and j['role'] == 'T' and j['long_yes']]
        first = {}
        for j in sorted(tj, key=lambda j: j['lag']): first.setdefault(j['c'], j)
        lags = [j['lag'] for j in first.values()]
        c = lambda a, b: sum(1 for x in lags if a <= x <= b)
        f10 = [j for j in tj if j['lag'] <= 10]
        print(f"[{tag}] clean jumps among its Yes markets {len(clean)}; traded as taker long-Yes in {len(first)}: first fill <=2s {c(-99,2)}, 3-10s {c(3,10)}, 11-60s {c(11,60)}, >60s {c(61,10**9)}; it IS the first print in {sum(1 for j in first.values() if j['rank']==0)}; fills at lag<=10s: ${sum(j['usd'] for j in f10):.0f} -> pnl {sum(j['pnl'] for j in f10):+.0f} (below 0.95: {sum(j['pnl'] for j in f10 if j['yp']<0.95):+.0f} in {len({j['c'] for j in f10 if j['yp']<0.95})} markets); all clean-jump taker fills pnl {sum(j['pnl'] for j in tj):+.0f}")
        # buys below 0.95: where
        cls = collections.defaultdict(lambda: [0, 0.0, 0.0, set(), set()])
        for s in S.values():
            for x in s['fills']:
                if x['side'] != 'BUY' or x['p'] >= 0.95: continue
                k = 'JUMP<=10s' if (x['ph'] == 'JUMP' and x['rf'] is not None and 0 <= x['rf'] <= 10) else ('JUMP later' if x['ph'] == 'JUMP' else x['ph'])
                a = cls[k]; a[0] += 1; a[1] += x['p'] * x['s']; a[2] += x['pnl']; a[3].add(s['c'])
                if x['pnl'] > 0: a[4].add(s['c'])
        print("   buys below 0.95:", {k: f"{len(a[3])} mk, ${a[1]:.0f}, pnl {a[2]:+.0f}" for k, a in sorted(cls.items())}, f"| TOTAL pnl {sum(a[2] for a in cls.values()):+.0f} on ${sum(a[1] for a in cls.values()):.0f}")
        # PRE buys by side
        sd = collections.defaultdict(lambda: [0.0, 0.0, {}, 0])
        for s in S.values():
            for x in s['fills']:
                if x['side'] == 'BUY' and x['ph'] == 'PRE':
                    a = sd[(x['o'], x['role'])]; a[0] += x['p'] * x['s']; a[1] += x['pnl']; a[2][s['c']] = a[2].get(s['c'], 0) + x['pnl']
        print("   PRE buys by outcome and role:", {str(k): f"${a[0]:.0f} pnl {a[1]:+.0f} ({100*a[1]/max(a[0],1):+.1f}%) mk {sum(1 for v in a[2].values() if v>0)}/{len(a[2])} t {tstat(a[2].values()):.1f}" for k, a in sorted(sd.items())})
        hrs = [-(x['rs']) / 3600 for s in S.values() for x in s['fills'] if x['ph'] == 'PRE' and x['rs'] is not None]
        if hrs: print(f"   PRE fills: {len(hrs)}, median {st.median(hrs):.1f} h before the scheduled start (p25 {sorted(hrs)[len(hrs)//4]:.1f}, p75 {sorted(hrs)[3*len(hrs)//4]:.1f})")
        both = sum(1 for s in S.values() if len({x['o'] for x in s['fills'] if x['side'] == 'BUY'}) == 2)
        print(f"   markets where it bought BOTH outcomes: {both} of {len(S)}")
        # fee actually charged on mention fills: fit r0 on this wallet's own charges
        mset = set(S)
        base = collections.defaultdict(float)
        for f in fills:
            if f['role'] != 'T': continue
            p, s = float(f['price']), float(f['size'])
            r = rate(f['timestamp'])
            base[('m' if f['condition_id'] in mset else 'o', 'r0' if r is None else r)] += s * p * (1 - p)
        print("   taker fee base s*p*(1-p):", {str(k): round(v) for k, v in sorted(base.items(), key=str)})
    v = list(both_mk.values()); top = sorted(v, reverse=True)
    print(f"[90 days, both windows] markets {len(v)} net {sum(v):+.0f} t by market {tstat(v):.2f}; events {len(both_ev)} t by event {tstat(both_ev.values()):.2f}; without the 3 best markets {sum(top[3:]):+.0f} (t {tstat(top[3:]):.2f}); without the 3 best events {sum(sorted(both_ev.values(), reverse=True)[3:]):+.0f}")
# Quant: what are the non-mention markets, and where do the splits go
for tag, fp in (("W0", "_fills_QuantDeLaFugazi_W0.json"), ("A", "../_fills_QuantDeLaFugazi_45.json")):
    fills, _ = json.load(open(fp))
    S = {s['c'] for s in json.load(open(f"s_QuantDeLaFugazi_{tag}.json"))['stories']}
    conds = sorted({f['condition_id'] for f in fills} - S)
    res = dataapi.resolutions(conds)
    pn = collections.defaultdict(float); us = collections.defaultdict(float); ti = {}
    for f in fills:
        c = f['condition_id']
        if c in S or not (res.get(c) or {}).get('resolved'): continue
        F = res[c]['final'].get(f['outcome'])
        if F is None: continue
        pn[c] += float(f['size']) * (F - float(f['price'])) * (1 if f['side'] == 'BUY' else -1); us[c] += float(f['size']) * float(f['price']); ti[c] = f['title']
    top = sorted(pn.items(), key=lambda x: -abs(x[1]))[:8]
    print(f"\nQuant {tag} non-mention: total {sum(pn.values()):+.0f} on ${sum(us.values()):.0f}; largest:", [(ti[c][:70], round(v), round(us[c])) for c, v in top])
    t0, t1 = min(f['timestamp'] for f in fills), max(f['timestamp'] for f in fills)
    ops = collections.defaultdict(float)
    for r in dataapi.iter_activity(W['Quant'], types="SPLIT,MERGE", start=t0, end=t1):
        ops[(r.get('type'), (r.get('title') or r.get('slug') or '?')[:60], r.get('condition_id') in S)] += float(r.get('usdc_size') or 0)
    print("   splits/merges by market (type, title, is-mention):", sorted(((k, round(v)) for k, v in ops.items()), key=lambda x: -x[1])[:10])
