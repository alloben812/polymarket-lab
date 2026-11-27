"""Post-hoc diagnostics on the frozen V1/V2 entries (no new rule, no threshold change): concentration by speaker/show,
month, and the old-fee sensitivity. Output: out/attack.txt"""
import json, collections, datetime as dt, re
from pmlab.stats import ratio_cluster
TR = json.load(open('out/trades.json'))
U = {x['c']: x for x in json.load(open('/home/user/polymarket-lab/data/gaps_mentions_model/universe.json'))}
L = []
def P(*a): s = ' '.join(str(v) for v in a); print(s); L.append(s)
def pnl(t, rate=0.01, cap=20):
    p = t['p']; sh = min(t['avail'], cap / p)
    return sh * t['won'] - sh * p - rate * sh * p * (1 - p), sh * p
def summ(name, trs, rate=0.01):
    ev = collections.defaultdict(lambda: [0.0, 0.0])
    for t in trs:
        a, b = pnl(t, rate); ev[t['event']][0] += a; ev[t['event']][1] += b
    if len(ev) < 2: P(f'   {name}: n={len(trs)} events={len(ev)}'); return
    r, se, tt = ratio_cluster([v[0] for v in ev.values()], [v[1] for v in ev.values()])
    P(f'   {name}: trades {len(trs)} events {len(ev)} return {100*r:+.1f}% +-{196*se:.1f} pnl ${sum(v[0] for v in ev.values()):+.0f}')
def grp(t):
    x = U[t['c']]; s = x['spk']
    if s in (None, 'anyone', 'announcers', 'someone'):
        q = x['q'].lower()
        for k in ('big brother', 'joe rogan', 'all-in', 'lemonade stand', 'south park', 'game', 'snl', 'saturday night'):
            if k in q: return k
        return 'other show'
    return s if s in ('trump', 'mrbeast', 'jd vance', 'andy burnham', 'warsh') else ('earnings co.' if x['type'] == 'earnings' else 'other speaker')
for v in ('V1', 'V2'):
    P(f'== {v}')
    for sg in ('S1', 'S2'):
        trs = [t for t in TR[v] if t['seg'] == sg]
        P(f'  segment {sg} by speaker/show group:')
        g = collections.defaultdict(list)
        for t in trs: g[grp(t)].append(t)
        for k, vv in sorted(g.items(), key=lambda kv: -len(kv[1])): summ(k, vv)
        P(f'  segment {sg} by month:')
        g = collections.defaultdict(list)
        for t in trs: g[dt.datetime.fromtimestamp(t['start'], dt.timezone.utc).strftime('%Y-%m')].append(t)
        for k, vv in sorted(g.items()): summ(k, vv)
        summ(f'{sg} at the old 0.04 fee (the fee those prices were set under)', trs, rate=0.04)
    P('  entry price buckets (pooled):')
    g = collections.defaultdict(list)
    for t in TR[v]: g[f"{t['side']} {min(int(t['p']*10)/10, 0.9):.1f}"].append(t)
    for k, vv in sorted(g.items()): summ(k, vv)
open('out/attack.txt', 'w').write('\n'.join(L) + '\n')
