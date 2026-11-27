"""Variant 3: category-wide tests R1-R5 on all sibling markets of the events the studied accounts touched."""
import sys, os, json, glob, gzip, collections, statistics as st, datetime as dt
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, '/home/user/polymarket-lab')
from pmlab import gamma, dataapi, wallet as W
D = os.path.dirname(os.path.abspath(__file__))
TAPES = '/home/user/polymarket-lab/data/mentions_tapes'
ts = W._ts
def tape(cond):
    p = f"{TAPES}/{cond}.json.gz"
    if os.path.exists(p): return json.load(gzip.open(p, 'rt'))
    rows = [dict(t=r['timestamp'], w=r['proxy_wallet'], side=r['side'], o=r['outcome'], p=float(r['price']), s=float(r['size'])) for r in dataapi.iter_trades(condition=cond)]
    rows.sort(key=lambda r: r['t'])
    json.dump(rows, gzip.open(p, 'wt'))
    return rows
def yes(r): return r['p'] if r['o'] == 'Yes' else 1 - r['p']
def long_yes(r): return (r['side'] == 'BUY') == (r['o'] == 'Yes')
def etype(slug):
    if 'earnings-call' in slug: return 'earnings'
    if any(k in slug for k in ('this-week', 'in-october', 'in-november', 'headlines', 'this-month')): return 'period'
    return 'live'
def mean_se(xs_by_event):
    """xs_by_event: {event: [values]} -> mean per unit, se clustered by event."""
    allv = [v for vs in xs_by_event.values() for v in vs]
    if not allv: return 0, 0, 0
    n = len(allv); m = sum(allv) / n
    sums = [sum(v - m for v in vs) for vs in xs_by_event.values()]
    se = (sum(s * s for s in sums) ** 0.5) / n
    return m, se, n

evslugs = set()
for f in glob.glob(D + '/deep_*.json'):
    for s in json.load(open(f))['stories']:
        if s['event']: evslugs.add(s['event'])
cache = D + '/_category_markets.json'
if os.path.exists(cache):
    MK = json.load(open(cache))
else:
    MK = []
    for sl in sorted(evslugs):
        ev = gamma.event_by_slug(sl, cache=True) or {}
        est = ts(ev.get('startTime'))
        for m in ev.get('markets') or []:
            try: op = [float(x) for x in gamma.jfield(m.get('outcomePrices'))]
            except Exception: continue
            if not m.get('closed') or sorted(op) != [0.0, 1.0]: continue
            MK.append(dict(c=m['conditionId'], q=m.get('question'), event=sl, start=est, closed=ts(m.get('closedTime')), fy=op[0], vol=float(m.get('volumeNum') or 0)))
    json.dump(MK, open(cache, 'w'))
print(f"events {len(evslugs)} resolved markets {len(MK)}")
with ThreadPoolExecutor(5) as ex:
    T = dict(zip([m['c'] for m in MK], ex.map(tape, [m['c'] for m in MK])))
MK = [m for m in MK if T[m['c']]]
for m in MK:
    if m['start'] and m['closed'] and m['start'] > m['closed']: m['start'] = None
    m['type'] = etype(m['event'])
    m['t0'] = m['start'] or T[m['c']][0]['t']
evorder = sorted({m['event']: min(x['t0'] for x in MK if x['event'] == m['event']) for m in MK}.items(), key=lambda x: x[1])
half = {e: ('TUNE' if i < len(evorder) / 2 else 'TEST') for i, (e, _) in enumerate(evorder)}
print(f"markets with tape {len(MK)}; events {len(evorder)}; by type {collections.Counter(m['type'] for m in MK)}; share resolved Yes {sum(m['fy'] for m in MK)/len(MK):.3f}; total volume ${sum(m['vol'] for m in MK):,.0f}")
print("split date:", dt.datetime.fromtimestamp(evorder[len(evorder)//2][1], dt.timezone.utc).date(), "window", dt.datetime.fromtimestamp(evorder[0][1], dt.timezone.utc).date(), "..", dt.datetime.fromtimestamp(evorder[-1][1], dt.timezone.utc).date())

# ---- R1/R2 calibration of pre-event price
B = [(0.1, '0-.10'), (0.25, '.10-.25'), (0.4, '.25-.40'), (0.6, '.40-.60'), (0.75, '.60-.75'), (0.9, '.75-.90'), (1.01, '.90-1')]
def bk(p):
    for hi, n in B:
        if p < hi: return n
cal = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(list)))  # half -> bucket -> event -> [(px, fy)]
for m in MK:
    if m['type'] == 'period' or not m['start']: continue
    pre = [r for r in T[m['c']] if m['start'] - 48 * 3600 <= r['t'] < m['start']]
    if not pre: continue
    px = yes(pre[-1]); m['pre'] = px
    cal[half[m['event']]][bk(px)][m['event']].append((px, m['fy']))
print("\nR1/R2 pre-event calibration (last print <=48h before scheduled start; live+earnings events). Returns per $1 staked, fee in, fill = print + 0.02; se clustered by event")
for h in ('TUNE', 'TEST'):
    print(f" {h}:")
    for _, b in B:
        d = cal[h][b]
        if not d: continue
        allv = [v for vs in d.values() for v in vs]
        n = len(allv); mp = sum(p for p, _ in allv) / n; fr = sum(f for _, f in allv) / n
        def ret_no(p, f):
            c = min(1 - p + 0.02, 0.999); return ((1 - f) - c - 0.01 * c * (1 - c)) / c
        def ret_yes(p, f):
            c = min(p + 0.02, 0.999); return (f - c - 0.01 * c * (1 - c)) / c
        rn = mean_se({e: [ret_no(p, f) for p, f in vs] for e, vs in d.items()})
        ry = mean_se({e: [ret_yes(p, f) for p, f in vs] for e, vs in d.items()})
        print(f"   yes_px {b:8s} n={n:4d} events={len(d):3d} mean px {mp:.3f} resolved Yes {fr:.3f} | buy No: {100*rn[0]:6.1f}% +-{100*rn[1]:.1f} | buy Yes: {100*ry[0]:6.1f}% +-{100*ry[1]:.1f}")

# ---- R3/R4 follow the confirmation
print("\nR3 follow-the-confirmation (first in-event print with bought-outcome price >= 0.95, then first same-outcome print >= L s later at 0.90..0.99; fill +0.005; fee in)")
res3 = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(list)))
r4 = dict(yes_conf=0, yes_conf_wrong=0, no_conf=0, no_conf_wrong=0)
wrong_examples = []
for m in MK:
    rows = [r for r in T[m['c']] if r['t'] >= m['t0']] if m['type'] != 'period' else T[m['c']]
    first = {}
    for r in rows:
        if r['side'] != 'BUY' or r['p'] < 0.95: continue
        first.setdefault(r['o'], r)
    for o, r0 in first.items():
        F = m['fy'] if o == 'Yes' else 1 - m['fy']
        key = 'yes_conf' if o == 'Yes' else 'no_conf'
        r4[key] += 1
        if F < 0.5:
            r4[key + '_wrong'] += 1; wrong_examples.append((o, m['q'][:70], round(r0['p'], 3), m['type']))
        for L in (0, 5, 30, 120, 600):
            nxt = next((r for r in rows if r['t'] >= r0['t'] + L and r is not r0 and r['side'] == 'BUY' and r['o'] == o), None) if L else r0
            if nxt is None or not (0.90 <= nxt['p'] <= 0.99): continue
            c = min(nxt['p'] + 0.005, 0.995)
            ret = (F - c - 0.01 * c * (1 - c)) / c
            hrs = ((m['closed'] or nxt['t']) - nxt['t']) / 3600
            res3[(half[m['event']], o)][L][m['event']].append((ret, hrs, nxt['p'] * nxt['s']))
for (h, o), dL in sorted(res3.items()):
    for L, d in sorted(dL.items()):
        mm = mean_se({e: [x[0] for x in vs] for e, vs in d.items()})
        allv = [x for vs in d.values() for x in vs]
        wins = sum(1 for x in allv if x[0] > 0)
        print(f"   {h} buy {o:3s} L={L:4d}s markets={mm[2]:4d} events={len(d):3d} mean ret {100*mm[0]:6.2f}% +-{100*mm[1]:.2f} win {wins}/{len(allv)} median hours to resolution {st.median(x[1] for x in allv):.1f} median print usd {st.median(x[2] for x in allv):.0f}")
print("R4 false confirmations:", r4)
for w in wrong_examples[:25]: print("    wrong:", w)

# ---- R5 jump capacity
print("\nR5 jump anatomy (Yes-resolved, last print <0.60 within 30 min before the first print >=0.60, in-event)")
jm = []; firstw = collections.Counter(); first10 = collections.Counter()
for m in MK:
    if m['fy'] < 0.5: continue
    rows = T[m['c']]; ys = [yes(r) for r in rows]; n = len(rows)
    sufmin = [9] * (n + 1)
    for i in range(n - 1, -1, -1): sufmin[i] = min(ys[i], sufmin[i + 1])
    idet = next((i for i in range(n) if ys[i] >= 0.90 and sufmin[i] >= 0.70), None)
    if idet is None: continue
    ipre = next((j for j in range(idet - 1, -1, -1) if ys[j] < 0.60), None)
    if ipre is None: continue
    ifm = ipre + 1
    fm = rows[ifm]
    if fm['t'] - rows[ipre]['t'] > 1800: continue
    if m['type'] != 'period' and m['start'] and fm['t'] < m['start']: continue
    t95 = next((r['t'] for r in rows[ifm:] if yes(r) >= 0.95), None)
    cap = {}
    for L in (0, 3, 10, 30, 60, 300):
        for thr in (0.90, 0.95):
            sel = [r for r in rows[ifm:] if r['t'] >= fm['t'] + L and long_yes(r) and yes(r) < thr and yes(r) >= 0.5]
            cap[(L, thr)] = (sum(yes(r) * r['s'] for r in sel), sum(r['s'] * (1 - yes(r) - 0.01 * yes(r) * (1 - yes(r))) for r in sel))
    jm.append(dict(m=m, pre_px=ys[ipre], fm_px=yes(fm), gap=fm['t'] - rows[ipre]['t'], d95=(t95 - fm['t']) if t95 else None, cap=cap, wallets10=len({r['w'] for r in rows[ifm:] if r['t'] <= fm['t'] + 10})))
    if long_yes(fm): firstw[fm['w']] += 1
    for w in {r['w'] for r in rows[ifm:] if r['t'] <= fm['t'] + 10 and long_yes(r)}: first10[w] += 1
print(f"  clean jumps: {len(jm)} markets in {len({j['m']['event'] for j in jm})} events; median pre px {st.median(j['pre_px'] for j in jm):.2f}; median first-print px {st.median(j['fm_px'] for j in jm):.3f}; share where the FIRST print is already >=0.90: {sum(1 for j in jm if j['fm_px']>=0.90)/len(jm):.2f}")
d95 = sorted(j['d95'] for j in jm if j['d95'] is not None)
print(f"  seconds from first print>=0.60 to first print>=0.95: p25 {d95[len(d95)//4]} median {d95[len(d95)//2]} p75 {d95[3*len(d95)//4]} p90 {d95[int(.9*len(d95))]}; distinct wallets in first 10 s: median {st.median(j['wallets10'] for j in jm)}")
for thr in (0.90, 0.95):
    for L in (0, 3, 10, 30, 60, 300):
        usd = sum(j['cap'][(L, thr)][0] for j in jm); prof = sum(j['cap'][(L, thr)][1] for j in jm)
        nz = sum(1 for j in jm if j['cap'][(L, thr)][0] > 0)
        for h in ('TUNE', 'TEST'):
            pass
        pt = sum(j['cap'][(L, thr)][1] for j in jm if half[j['m']['event']] == 'TEST')
        top = max(j['cap'][(L, thr)][1] for j in jm)
        print(f"  long-Yes taker prints at 0.50<=px<{thr} at lag>={L:3d}s after first move: ${usd:9.0f} bought, locked-in profit ${prof:8.0f} (TEST half ${pt:7.0f}; largest single market ${top:.0f}) in {nz}/{len(jm)} markets")
names = {}
def nm(w):
    if w not in names:
        try: names[w] = next(iter(dataapi.iter_trades(user=w, max_rows=1)), {}).get('name') or w[:10]
        except Exception: names[w] = w[:10]
    return names[w]
print("  first long-Yes printer per jump (wallet: markets):", [(nm(w), n) for w, n in firstw.most_common(12)])
print("  long-Yes within 10 s of first move (wallet: markets):", [(nm(w), n) for w, n in first10.most_common(12)])
json.dump(dict(n_markets=len(MK), r4=r4, jumps=[dict(q=j['m']['q'], event=j['m']['event'], pre_px=j['pre_px'], fm_px=j['fm_px'], gap=j['gap'], d95=j['d95']) for j in jm]), open(D + '/category_out.json', 'w'))
