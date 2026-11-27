"""Variant 3b: who are the fastest long-Yes takers in the 131 clean live jumps (same definition as R5), what they pay and lock in."""
import sys, os, json, gzip, collections, statistics as st
sys.path.insert(0, '/home/user/polymarket-lab')
from pmlab import dataapi
D = os.path.dirname(os.path.abspath(__file__)); TAPES = '/home/user/polymarket-lab/data/mentions_tapes'
MK = json.load(open(D + '/_category_markets.json'))
def yes(r): return r['p'] if r['o'] == 'Yes' else 1 - r['p']
def long_yes(r): return (r['side'] == 'BUY') == (r['o'] == 'Yes')
def etype(slug):
    if 'earnings-call' in slug: return 'earnings'
    if any(k in slug for k in ('this-week', 'in-october', 'in-november', 'headlines', 'this-month')): return 'period'
    return 'live'
W = collections.defaultdict(lambda: dict(j10=set(), j60=set(), first=0, usd=0.0, prof=0.0, px=[], ev=set(), types=collections.Counter()))
njump = 0; vols = []
for m in MK:
    p = f"{TAPES}/{m['c']}.json.gz"
    if not os.path.exists(p): continue
    rows = json.load(gzip.open(p, 'rt'))
    if not rows: continue
    vols.append(m['vol'])
    if m['fy'] < 0.5: continue
    start = m['start'] if not (m['start'] and m['closed'] and m['start'] > m['closed']) else None
    ys = [yes(r) for r in rows]; n = len(rows)
    sufmin = [9] * (n + 1)
    for i in range(n - 1, -1, -1): sufmin[i] = min(ys[i], sufmin[i + 1])
    idet = next((i for i in range(n) if ys[i] >= 0.90 and sufmin[i] >= 0.70), None)
    if idet is None: continue
    ipre = next((j for j in range(idet - 1, -1, -1) if ys[j] < 0.60), None)
    if ipre is None: continue
    fm = rows[ipre + 1]
    if fm['t'] - rows[ipre]['t'] > 1800: continue
    typ = etype(m['event'])
    if typ != 'period' and start and fm['t'] < start: continue
    njump += 1
    if long_yes(fm): W[fm['w']]['first'] += 1
    for r in rows[ipre + 1:]:
        if not long_yes(r) or r['t'] > fm['t'] + 60: continue
        a = W[r['w']]
        a['j60'].add(m['c'])
        if r['t'] <= fm['t'] + 10:
            a['j10'].add(m['c']); a['usd'] += yes(r) * r['s']; a['prof'] += r['s'] * (1 - yes(r) - 0.01 * yes(r) * (1 - yes(r))); a['px'].append(yes(r)); a['ev'].add(m['event']); a['types'][typ] += 1
vols.sort()
print(f"universe volume per market: median ${vols[len(vols)//2]:.0f}, p75 ${vols[3*len(vols)//4]:.0f}, p90 ${vols[int(.9*len(vols))]:.0f}, max ${vols[-1]:.0f}; markets {len(vols)}; clean jumps {njump}")
top = sorted(W.items(), key=lambda x: -len(x[1]['j10']))[:14]
out = []
for w, a in top:
    try: name = next(iter(dataapi.iter_trades(user=w, max_rows=1)), {}).get('name') or w[:10]
    except Exception: name = w[:10]
    print(f"  {name[:22]:22s} {w} jumps<=10s {len(a['j10']):3d} (<=60s {len(a['j60']):3d}) first-printer {a['first']:3d} events {len(a['ev']):2d} types {dict(a['types'])} usd {a['usd']:7.0f} median px {st.median(a['px']):.3f} locked profit ${a['prof']:.0f}")
    out.append((name, w))
json.dump(out, open(D + '/_fast_wallets.json', 'w'))
