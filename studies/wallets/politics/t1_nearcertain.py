"""T1 of protocol.md: taker buys at 0.95-0.999 on the cached politics tapes, after fee, clustered by market."""
import collections, glob, json, os
from pmlab import dataapi, stats
base = '/home/user/polymarket-lab/data/politics_wallets/tapes/'; meta = {}
for f in glob.glob('*.json'):
    try: d = json.load(open(f))
    except Exception: continue
    if isinstance(d, dict) and '_markets' in d:
        for m in d['_markets']: meta[m['condition']] = m
conds = [os.path.basename(p)[:-5] for p in glob.glob(base + '*.json')]
conds = [c for c in conds if (meta.get(c) or {}).get('family') == 'politics']
res = dataapi.resolutions(conds, cache=False)
rows = []; used = 0
for c in conds:
    r = res.get(c)
    if not r or not r['resolved']: continue
    fin = r['final']; names = list(r['tokens'])            # outcome order as returned
    f_yes = fin.get('Yes'); f_no = fin.get('No')
    if f_yes is None or f_no is None: continue
    tp = json.load(open(base + c + '.json')); used += 1; end = meta[c].get('end'); last = tp[-1][0]
    for t, sd, oi, px, sz, w in tp:
        if sd != 'BUY' or not (0.95 <= px < 0.999): continue
        final = float(f_yes if oi == 0 else f_no); rate = 0.05 if t < 1795219200 else 0.01
        fee = rate * px * (1 - px)
        rows.append(dict(c=c, last=last, t=t, px=px, sz=sz, pnl=(final - px - fee) * sz, gross=(final - px) * sz, w=w, tte=(end - t) if end else None, lost=final < 0.5))
print(f"politics tapes {len(conds)}, resolved {used}, taker buys at 0.95-0.999: {len(rows)} fills, {len({r['c'] for r in rows})} markets, {len({r['w'] for r in rows})} wallets, ${sum(r['px'] * r['sz'] for r in rows):,.0f}")
def rep(name, sel):
    num = collections.Counter(); den = collections.Counter(); g = collections.Counter()
    for r in sel: num[r['c']] += 100 * r['pnl']; den[r['c']] += r['sz']; g[r['c']] += 100 * r['gross']
    cs = list(num)
    if len(cs) < 2: print(f"  {name:34} n/a"); return
    e = stats.ratio_cluster([num[c] for c in cs], [den[c] for c in cs]); e0 = stats.ratio_cluster([g[c] for c in cs], [den[c] for c in cs])
    lostm = len({r['c'] for r in sel if r['lost']})
    print(f"  {name:34} fills {len(sel):6} markets {len(cs):3} (lost in {lostm}) shares {sum(den.values()):10,.0f}  gross {e0[0]:+.2f} c/sh  after fee {e[0]:+.2f} c/sh (se {e[1]:.2f}, t {e[2]:.1f})  total ${sum(num.values()) / 100:,.0f}")
order = sorted({r['c']: r['last'] for r in rows}.items(), key=lambda kv: kv[1]); half = {c for c, _ in order[:len(order) // 2]}
rep('ALL', rows); rep('tune (earlier half of markets)', [r for r in rows if r['c'] in half]); rep('REPORT (later half of markets)', [r for r in rows if r['c'] not in half])
for a, b in ((.95, .97), (.97, .99), (.99, .999)): rep(f'price {a}-{b}', [r for r in rows if a <= r['px'] < b])
for name, lo, hi in (('after gamma end date', -1e12, 0), ('0-6 h to end', 0, 21600), ('6-24 h to end', 21600, 86400), ('1-7 d to end', 86400, 604800), ('over 7 d to end', 604800, 1e12)):
    rep(name, [r for r in rows if r['tte'] is not None and lo <= r['tte'] < hi])
wl = collections.defaultdict(lambda: [0.0, 0.0, set()])
for r in rows: x = wl[r['w']]; x[0] += r['pnl']; x[1] += r['px'] * r['sz']; x[2].add(r['c'])
print('  top wallets by $ bought at 0.95+:'); [print(f"    {w} ${x[1]:9,.0f} in {len(x[2]):3} markets, after fee ${x[0]:8,.0f}") for w, x in sorted(wl.items(), key=lambda kv: -kv[1][1])[:8]]
print('  wallets with >= 10 markets:', sum(1 for x in wl.values() if len(x[2]) >= 10), ' of them positive after fee:', sum(1 for x in wl.values() if len(x[2]) >= 10 and x[0] > 0))
