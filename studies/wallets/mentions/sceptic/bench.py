"""Faston out of sample (W0): PRE picks vs blind same-side buying on every sibling market of the same events.
Rules copied from ../pre_event.py: pre price = last print within 48 h before the scheduled start, live + earnings
events only, blind fill at print + 0.02, fee 0.01*p*(1-p), siblings with 0.05 <= pre <= 0.95, errors by event."""
import sys, os, json, gzip, collections, statistics as st
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, '/home/user/polymarket-lab')
from pmlab import gamma, dataapi, wallet as W
TAPES = '/home/user/polymarket-lab/data/mentions_tapes'
ME = "0xa7fea388f955a9517067111030eb771c6d911f3e"
def etype(slug):
    if 'earnings-call' in slug: return 'earnings'
    if any(k in slug for k in ('this-week', 'in-october', 'in-november', 'in-september', 'in-august', 'headlines', 'this-month')): return 'period'
    return 'live'
def yes(r): return r['p'] if r['o'] == 'Yes' else 1 - r['p']
def tape(c):
    p = f"{TAPES}/{c}.json.gz"
    if os.path.exists(p): return json.load(gzip.open(p, 'rt'))
    rows = [dict(t=r['timestamp'], w=r['proxy_wallet'], side=r['side'], o=r['outcome'], p=float(r['price']), s=float(r['size'])) for r in dataapi.iter_trades(condition=c)]
    rows.sort(key=lambda r: r['t']); json.dump(rows, gzip.open(p, 'wt')); return rows
def mean_se(d):
    allv = [v for vs in d.values() for v in vs]
    if not allv: return (0, 0, 0)
    n = len(allv); m = sum(allv) / n
    return m, (sum(sum(v - m for v in vs) ** 2 for vs in d.values()) ** 0.5) / n, n
def rn(p, f): c = min(1 - p + 0.02, 0.999); return ((1 - f) - c - 0.01 * c * (1 - c)) / c
def ry(p, f): c = min(p + 0.02, 0.999); return (f - c - 0.01 * c * (1 - c)) / c
for tag in sys.argv[1:]:
    d = json.load(open(f"s_Faston_{tag}.json"))
    # PRE pnl by event type (the gamma start of a 'period' event is the END of the period)
    bt = collections.defaultdict(lambda: [0.0, 0.0, set()])
    pick = {'Yes': collections.defaultdict(list), 'No': collections.defaultdict(list)}
    for s in d['stories']:
        for f in s['fills']:
            if f['ph'] != 'PRE' or f['side'] != 'BUY': continue
            a = bt[etype(s['event'])]; a[0] += f['p'] * f['s']; a[1] += f['pnl']; a[2].add(s['event'])
            if etype(s['event']) != 'period': pick[f['o']][s['event']].append((f['pnl'], f['p'] * f['s']))
    print(f"[{tag}] PRE buys by event type:", {k: f"${a[0]:.0f} pnl {a[1]:+.0f} ({100*a[1]/max(a[0],1):+.1f}%) in {len(a[2])} events" for k, a in bt.items()})
    evs = sorted(set(pick['Yes']) | set(pick['No']))
    sib = []
    for e in evs:
        try: ev = gamma.event_by_slug(e, cache=True)
        except Exception as x: ev = None
        if not ev: continue
        start = W._ts(ev.get('startTime'))
        for m in ev.get('markets') or []:
            if m.get('conditionId'): sib.append(dict(c=m['conditionId'], event=e, start=start, closed=W._ts(m.get('closedTime')), q=m.get('question')))
    res = dataapi.resolutions([m['c'] for m in sib])
    with ThreadPoolExecutor(5) as ex: tp = dict(zip([m['c'] for m in sib], ex.map(lambda m: tape(m['c']), sib)))
    rows = []; mine_usd = tot_usd = 0.0
    for m in sib:
        r = res.get(m['c']) or {}; fy = (r.get('final') or {}).get('Yes')
        if not r.get('resolved') or fy not in (0, 1, 0.0, 1.0): continue
        st_ = m['start']
        if st_ and m['closed'] and st_ > m['closed']: st_ = None
        if not st_: continue
        pre = [x for x in tp[m['c']] if st_ - 48 * 3600 <= x['t'] < st_]
        if not pre: continue
        others = [x for x in pre if x['w'].lower() != ME]
        m['pre'] = yes(pre[-1]); m['pre_o'] = yes(others[-1]) if others else None; m['fy'] = fy; rows.append(m)
        mine_usd += sum(x['p'] * x['s'] for x in pre if x['w'].lower() == ME); tot_usd += sum(x['p'] * x['s'] for x in pre)
    print(f"   sibling markets fetched {len(sib)} in {len(evs)} events; with a pre price {len(rows)}; Faston's own TAKER prints are {100*mine_usd/max(tot_usd,1):.0f}% of the last-48h pre-event tape dollars")
    for side in ('No', 'Yes'):
        pv = pick[side]
        usd = sum(u for vs in pv.values() for _, u in vs); pnl = sum(p for vs in pv.values() for p, _ in vs)
        per_ev = [sum(p for p, _ in vs) / max(sum(u for _, u in vs), 1e-9) for vs in pv.values()]
        base = collections.defaultdict(list); base_o = collections.defaultdict(list)
        for m in rows:
            if m['event'] in pv and 0.05 <= m['pre'] <= 0.95: base[m['event']].append(rn(m['pre'], m['fy']) if side == 'No' else ry(m['pre'], m['fy']))
            if m['event'] in pv and m['pre_o'] is not None and 0.05 <= m['pre_o'] <= 0.95: base_o[m['event']].append(rn(m['pre_o'], m['fy']) if side == 'No' else ry(m['pre_o'], m['fy']))
        b, bo = mean_se(base), mean_se(base_o)
        print(f"   picks buy {side}: ${usd:.0f} pnl {pnl:+.0f} ({100*pnl/max(usd,1):+.1f}% dollar-weighted; mean of event returns {100*st.mean(per_ev):+.1f}%, {sum(1 for x in per_ev if x>0)}/{len(per_ev)} events positive) | blind buy-{side} on {b[2]} siblings: {100*b[0]:+.1f}% +-{100*b[1]:.1f} | same, pre price from other wallets' prints only ({bo[2]}): {100*bo[0]:+.1f}% +-{100*bo[1]:.1f}")
