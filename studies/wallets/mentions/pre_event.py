"""Variant 4 (exploratory): pre-event calibration by market kind; account PRE picks vs blind same-event baseline."""
import sys, os, json, gzip, re, collections, statistics as st
D = os.path.dirname(os.path.abspath(__file__))
TAPES = '/home/user/polymarket-lab/data/mentions_tapes'
MK = json.load(open(D + '/_category_markets.json'))
def tape(c): return json.load(gzip.open(f"{TAPES}/{c}.json.gz", 'rt'))
def yes(r): return r['p'] if r['o'] == 'Yes' else 1 - r['p']
def etype(slug):
    if 'earnings-call' in slug: return 'earnings'
    if any(k in slug for k in ('this-week', 'in-october', 'in-november', 'headlines', 'this-month')): return 'period'
    return 'live'
def mean_se(d):
    allv = [v for vs in d.values() for v in vs]
    if not allv: return (0, 0, 0)
    n = len(allv); m = sum(allv) / n
    return m, (sum(sum(v - m for v in vs) ** 2 for vs in d.values()) ** 0.5) / n, n
rows = []
for m in MK:
    if not os.path.exists(f"{TAPES}/{m['c']}.json.gz"): continue
    T = tape(m['c'])
    if not T: continue
    st_ = m['start']
    if st_ and m['closed'] and st_ > m['closed']: st_ = None
    m['type'] = etype(m['event']); m['t0'] = st_ or T[0]['t']
    if m['type'] == 'period' or not st_: continue
    pre = [r for r in T if st_ - 48 * 3600 <= r['t'] < st_]
    if not pre: continue
    m['pre'] = yes(pre[-1]); m['thr'] = bool(re.search(r'\d+\+ times', m['q'] or ''))
    rows.append(m)
ev0 = {}
for m in MK:
    if 't0' in m: ev0[m['event']] = min(ev0.get(m['event'], 9e18), m['t0'])
order = sorted(ev0, key=ev0.get); half = {e: ('TUNE' if i < len(order) / 2 else 'TEST') for i, e in enumerate(order)}
def rn(p, f): c = min(1 - p + 0.02, 0.999); return ((1 - f) - c - 0.01 * c * (1 - c)) / c
def ry(p, f): c = min(p + 0.02, 0.999); return (f - c - 0.01 * c * (1 - c)) / c
print(f"markets with a pre-event price: {len(rows)} in {len({m['event'] for m in rows})} events; mean pre yes_px {st.mean(m['pre'] for m in rows):.3f} vs resolved Yes {st.mean(m['fy'] for m in rows):.3f}")
for h in ('TUNE', 'TEST'):
    for typ in ('live', 'earnings'):
        for thr in (False, True):
            for lo, hi, nm in ((0.05, 0.5, 'px .05-.50'), (0.5, 0.95, 'px .50-.95')):
                sel = [m for m in rows if half[m['event']] == h and m['type'] == typ and m['thr'] == thr and lo <= m['pre'] < hi]
                if len(sel) < 8: continue
                dn = collections.defaultdict(list); dy = collections.defaultdict(list)
                for m in sel: dn[m['event']].append(rn(m['pre'], m['fy'])); dy[m['event']].append(ry(m['pre'], m['fy']))
                a, b = mean_se(dn), mean_se(dy)
                print(f"  {h} {typ:8s} {'N+ times ' if thr else 'single   '} {nm}: n={len(sel):3d} ev={len(dn):2d} mean px {st.mean(m['pre'] for m in sel):.2f} Yes rate {st.mean(m['fy'] for m in sel):.2f} | No {100*a[0]:6.1f}%+-{100*a[1]:.1f} | Yes {100*b[0]:6.1f}%+-{100*b[1]:.1f}")
bycond = {m['c']: m for m in rows}
for label in ('jkerkela', 'Faston', '0xtrador'):
    d = json.load(open(f"{D}/deep_{label}.json"))
    pick = collections.defaultdict(lambda: collections.defaultdict(list)); hrs = []
    evs = set()
    for s in d['stories']:
        for f in s['fills']:
            if f['ph'] != 'PRE' or f['side'] != 'BUY': continue
            side = 'No' if f['o'] == 'No' else 'Yes'
            usd = f['p'] * f['s']
            pick[side][s['event']].append((f['pnl'], usd)); evs.add(s['event'])
            if f['rel_start'] is not None: hrs.append(-f['rel_start'] / 3600)
    print(f"== {label}: PRE buys; median hours before scheduled start {st.median(hrs) if hrs else None:.1f}")
    for side in ('No', 'Yes'):
        pv = pick[side]
        usd = sum(u for vs in pv.values() for _, u in vs); pnl = sum(p for vs in pv.values() for p, _ in vs)
        base = collections.defaultdict(list)
        for m in rows:
            if m['event'] in pv and 0.05 <= m['pre'] <= 0.95: base[m['event']].append(rn(m['pre'], m['fy']) if side == 'No' else ry(m['pre'], m['fy']))
        b = mean_se(base)
        evpos = sum(1 for vs in pv.values() if sum(p for p, _ in vs) > 0)
        print(f"   picks buy {side}: usd {usd:.0f} pnl {pnl:.0f} ({100*pnl/max(usd,1):.1f}%), events {len(pv)} positive {evpos} | blind buy-{side} on all {b[2]} siblings of those events at pre price: {100*b[0]:.1f}% +-{100*b[1]:.1f}")
