"""Runs V1, V2 and the +1c sensitivity exactly as in protocol.md. Writes out/results.txt and out/trades.json."""
import json, gzip, os, re, collections, datetime as dt, statistics as st
from pmlab.stats import ratio_cluster, bootstrap_sum_ci
D = '/home/user/polymarket-lab/data/gaps_mentions_model'
TAPES = '/home/user/polymarket-lab/data/mentions_tapes'
OUT = '/home/user/polymarket-lab/studies/gaps/mentions_model/out'
RATE = 0.01; CAP = 20.0; LAG = 3
U = json.load(open(f'{D}/universe.json'))
def T(y, m, d): return dt.datetime(y, m, d, tzinfo=dt.timezone.utc).timestamp()
LO, S2, S3, HI = T(2026, 8, 1), T(2026, 9, 29), T(2026, 11, 24), T(2026, 11, 28)
def seg(t): return 'S1' if t < S2 else ('S2' if t < S3 else 'S3')
GENERIC = {None, 'anyone', 'announcers', 'someone', 'anybody'}
MONTHS = 'january|february|march|april|may|june|july|august|september|october|november|december'
def during_key(q):
    ql = (q or '').lower()
    m = re.search(r'\bduring (.+?)\??$', ql)
    s = m.group(1) if m else ql
    s = re.sub(r'\d+(st|nd|rd|th)?', ' ', s); s = re.sub(rf'\b({MONTHS})\b', ' ', s)
    s = re.sub(r'\b(next|first|the|episode|week of|his|her|their|s|e|on|of)\b', ' ', s)
    return 'during:' + ' '.join(s.split())
def key(x):
    spk = x['spk'] if x['spk'] not in GENERIC else during_key(x['q'])
    return (x['type'], spk, x['terms'], x['n'])
# priors index (whole universe, live/earnings, resolved 0/1, closed time known)
PRI = collections.defaultdict(list)
for x in U:
    if x['type'] == 'period' or not x['closed'] or not x['terms']: continue
    PRI[key(x)].append((x['closed'], x['event'], x['fy']))
def prior(x, t):
    v = [fy for c, e, fy in PRI.get(key(x), []) if c < t and e != x['event']]
    return len(v), sum(v)
def tape(c):
    p = f'{TAPES}/{c}.json.gz'
    return json.load(gzip.open(p, 'rt')) if os.path.exists(p) else None
def buyable(rows, side):
    """(match time, price of `side`, shares) for every row that shows `side` could be bought."""
    out = []
    for r in rows:
        if r['side'] == 'BUY' and r['o'] == side: out.append((r['t'] - LAG, r['p'], r['s']))
        elif r['side'] == 'SELL' and r['o'] != side: out.append((r['t'] - LAG, 1 - r['p'], r['s']))
    return out
sel = [x for x in U if x['start_ok'] and LO <= x['start'] < HI and x['type'] != 'period']
missing = 0; trades = {'V1': [], 'V2': []}; buyable_usd = {'V1': [], 'V2': []}
ntape = 0; nprior3 = 0
for x in sel:
    rows = tape(x['c'])
    if rows is None: missing += 1; continue
    ntape += 1
    a, b = x['start'] - 24 * 3600, x['start'] - 300
    W = {s: [r for r in buyable(rows, s) if a <= r[0] <= b] for s in ('Yes', 'No')}
    won = {'Yes': x['fy'] == 1.0, 'No': x['fy'] == 0.0}
    base = dict(c=x['c'], event=x['event'], seg=seg(x['start']), start=x['start'], type=x['type'], q=x['q'][:110], vol=x['vol'])
    # V1
    if x['n'] == 0 and x['terms']:
        q = [r for r in W['No'] if 0.50 <= r[1] <= 0.95]
        if q:
            t, p, s = q[0]
            trades['V1'].append(dict(base, side='No', t=t, p=p, avail=s, won=won['No']))
            buyable_usd['V1'].append(sum(pp * ss for _, pp, ss in q))
    # V2
    if x['terms']:
        cand = []
        for side in ('Yes', 'No'):
            for t, p, s in W[side]:
                if not (0.03 <= p <= 0.97): continue
                n, k = prior(x, t)
                if n < 3: continue
                bb = (k + 1) / (n + 2)
                fair = bb if side == 'Yes' else 1 - bb
                if p <= fair - 0.15:
                    cand.append((t, side, p, s, n, k, bb)); break
        if cand:
            t, side, p, s, n, k, bb = min(cand)
            trades['V2'].append(dict(base, side=side, t=t, p=p, avail=s, won=won[side], n_prior=n, k_prior=k, b=bb))
        if prior(x, b)[0] >= 3: nprior3 += 1
def pnl(tr, slip=0.0, cap=CAP):
    p = min(tr['p'] + slip, 0.999)
    sh = min(tr['avail'], cap / p)
    return sh * (1.0 if tr['won'] else 0.0) - sh * p - RATE * sh * p * (1 - p), sh * p
L = []
def P(*a): s = ' '.join(str(v) for v in a); print(s); L.append(s)
def summary(name, trs, slip=0.0, drop_best=0):
    ev = collections.defaultdict(lambda: [0.0, 0.0])
    for tr in trs:
        a, b = pnl(tr, slip); ev[tr['event']][0] += a; ev[tr['event']][1] += b
    if drop_best:
        for e in sorted(ev, key=lambda e: -ev[e][0])[:drop_best]: del ev[e]
    if not ev: P(f'  {name}: no trades'); return None
    num = [v[0] for v in ev.values()]; den = [v[1] for v in ev.values()]
    r, se, tt = ratio_cluster(num, den)
    lo_b, hi_b = bootstrap_sum_ci(num)
    n = len(trs); w = sum(t['won'] for t in trs)
    P(f'  {name}: trades {n} events {len(ev)} won {w}/{n} mean px {st.mean(t["p"] for t in trs):.3f} stake ${sum(den):,.0f} pnl ${sum(num):+,.1f} '
      f'| return {100*r:+.2f}% 95% [{100*(r-1.96*se):+.2f}, {100*(r+1.96*se):+.2f}] t {tt:.2f} | boot total [{lo_b:+.1f}, {hi_b:+.1f}] '
      f'| net/trade ${sum(num)/n:+.3f} at <=$20 (avg stake ${sum(den)/n:.2f}); at $5 cap ${sum(pnl(t, slip, 5)[0] for t in trs)/n:+.3f}')
    return r, se
P(f'sample: {len(sel)} markets in {len({x["event"] for x in sel})} events; tapes found {ntape}, missing {missing}; markets with >=3 priors at the window end {nprior3}')
res = {}
for v in ('V1', 'V2'):
    P(f'\n== {v}')
    trs = trades[v]
    for sg, f in (('S1 early (fresh)', lambda t: t['seg'] == 'S1'), ('S2 discovery', lambda t: t['seg'] == 'S2'), ('S3 late fresh', lambda t: t['seg'] == 'S3'),
                  ('late S2+S3', lambda t: t['seg'] != 'S1'), ('fresh S1+S3', lambda t: t['seg'] != 'S2'), ('pooled', lambda t: True)):
        res[(v, sg)] = summary(sg, [t for t in trs if f(t)])
    P(' attacks:')
    res[(v, 'drop3')] = summary('pooled without 3 best events', trs, drop_best=3)
    res[(v, 'slip')] = summary('R-sens pooled at price +0.01', trs, slip=0.01)
    summary('R-sens fresh S1+S3 at +0.01', [t for t in trs if t['seg'] != 'S2'], slip=0.01)
    P(' descriptive:')
    for tp in ('live', 'earnings'): summary(f'type {tp}', [t for t in trs if t['type'] == tp])
    wk = lambda t: dt.datetime.fromtimestamp(t['start'], dt.timezone.utc).weekday() >= 5
    summary('weekend starts (UTC Sat/Sun)', [t for t in trs if wk(t)]); summary('weekday starts', [t for t in trs if not wk(t)])
    if v == 'V2':
        for sd in ('Yes', 'No'): summary(f'side {sd}', [t for t in trs if t['side'] == sd])
    hrs = [(t['start'] - t['t']) / 3600 for t in trs]
    if hrs: P(f'  entry hours before start: median {st.median(hrs):.1f}; available shares at entry row median {st.median(t["avail"] for t in trs):.0f}; '
              f'share of entries where the row allowed the full $20: {sum(1 for t in trs if t["avail"]*t["p"]>=20)/len(trs):.2f}; '
              f'buyable $ at qualifying rows per market median {st.median(buyable_usd[v]) if buyable_usd[v] else 0:.0f}')
# descriptive universe counts
P('\n== universe (all binary mention markets resolved 0/1, by closed week, Aug-Nov 2026)')
wk_m = collections.Counter(); wk_e = collections.defaultdict(set); wk_v = collections.Counter()
for x in U:
    if x['closed'] and LO <= x['closed'] < HI:
        w = dt.datetime.fromtimestamp(x['closed'], dt.timezone.utc).strftime('%G-W%V'); wk_m[w] += 1; wk_e[w].add(x['event']); wk_v[w] += x['vol']
for w in sorted(wk_m): P(f'  {w}: markets {wk_m[w]} events {len(wk_e[w])} volume ${wk_v[w]:,.0f}')
dow = collections.Counter(); dow_m = collections.Counter(); evseen = set()
for x in sel:
    d = dt.datetime.fromtimestamp(x['start'], dt.timezone.utc).strftime('%a'); dow_m[d] += 1
    if x['event'] not in evseen: evseen.add(x['event']); dow[d] += 1
P('  sample events by UTC weekday of start:', dict(dow), ' markets:', dict(dow_m))
json.dump(trades, open(f'{OUT}/trades.json', 'w'))
open(f'{OUT}/results.txt', 'w').write('\n'.join(L) + '\n')
