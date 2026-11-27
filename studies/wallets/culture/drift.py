"""Falsification helper: does the price keep moving the account's way AFTER its fills, measured only on OTHER
people's trades?  (If the account's own taker prints are the 'drift', the edge is an artefact.)

  python3 drift.py <tag> [slug-regex]     reads <tag>.story.json, refetches tapes, excludes the account's own rows
Reports, per horizon, the share-weighted mean signed move (cents/share) and the share of MARKETS with a positive
mean move; also splits fills by whether the market's last independent price before the fill was already beyond 0.90
in the final direction.
"""
import bisect, collections, json, re, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from pmlab import dataapi
tag = sys.argv[1]; rx = re.compile(sys.argv[2] if len(sys.argv) > 2 else '.')
d = json.load(open(tag + '.story.json')); wal = d['wallet'].lower()
ms = [m for m in d['markets'] if rx.search(m['slug'] or '')]
def tape(m):
    own = collections.Counter((r['t'], round(r['p'], 4), round(r['size'], 2)) for r in m['fills'])
    rows = []
    for r in dataapi.iter_trades(condition=m['cond'], max_rows=40000):
        k = (int(r['timestamp']), round(float(r['price']), 4), round(float(r['size']), 2))
        w = (r.get('proxy_wallet') or r.get('user') or r.get('wallet') or r.get('taker') or '').lower()
        if w == wal: continue
        if own[k] > 0: own[k] -= 1; continue
        p = float(r['price']); rows.append((int(r['timestamp']), p if r.get('outcome') == m['first'] else 1 - p))
    rows.sort(); return rows
with ThreadPoolExecutor(4) as ex: tapes = list(ex.map(tape, ms))
H = [('10m', 600), ('1h', 3600), ('6h', 21600), ('24h', 86400)]
acc = {h: [0.0, 0.0, collections.defaultdict(lambda: [0.0, 0.0])] for h, _ in H}
pre = collections.defaultdict(lambda: [0, 0.0, 0.0])
for m, tp in zip(ms, tapes):
    ts = [t for t, _ in tp]
    def px(t):
        i = bisect.bisect_right(ts, t) - 1
        return tp[i][1] if i >= 0 else None
    for r in m['fills']:
        before = px(r['t'] - 1)
        if m['resolved'] and before is not None and r['pnl'] is not None:
            known = (before >= 0.9) if m['final'] >= 0.5 else (before <= 0.1)
            right = (r['sign'] > 0) == (m['final'] >= 0.5)
            k = ('market already >=0.90 on final side' if known else 'market not yet decided', 'with outcome' if right else 'against outcome')
            pre[k][0] += 1; pre[k][1] += r['usd']; pre[k][2] += r['pnl']
        for h, s in H:
            later = px(r['t'] + s)
            if later is None or before is None: continue
            mv = r['sign'] * (later - r['py']) * r['size']
            a = acc[h]; a[0] += mv; a[1] += r['size']; a[2][m['cond']][0] += mv; a[2][m['cond']][1] += r['size']
print(f'{tag}: {len(ms)} markets, own rows excluded from the tape')
for h, _ in H:
    a = acc[h]; pm = [v[0] / v[1] for v in a[2].values() if v[1] > 0]
    import statistics as st
    se = st.pstdev(pm) / max(1, len(pm)) ** 0.5 if len(pm) > 1 else float('nan')
    print(f'  +{h:4} share-weighted move {100 * a[0] / max(1, a[1]):6.2f} c/sh | per-market mean {100 * st.mean(pm):6.2f} c (se {100 * se:.2f}, n {len(pm)}), positive in {sum(1 for x in pm if x > 0)}/{len(pm)} markets')
for k, v in sorted(pre.items()):
    print(f'  {k[0]:38} {k[1]:16} fills {v[0]:5} usd {v[1]:9.0f} pnl {v[2]:9.0f}')
