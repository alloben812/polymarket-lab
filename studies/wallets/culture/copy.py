"""Copy rule C from protocol.md.  python3 copy.py <tag> [slug-regex]"""
import bisect, collections, json, re, statistics as st, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from pmlab import dataapi
tag = sys.argv[1]; rx = re.compile(sys.argv[2] if len(sys.argv) > 2 else '.')
d = json.load(open(tag + '.story.json')); wal = d['wallet'].lower()
ms = [m for m in d['markets'] if rx.search(m['slug'] or '') and m['resolved']]
def tape(m):
    own = collections.Counter((r['t'], round(r['p'], 4), round(r['size'], 2)) for r in m['fills']); rows = []
    for r in dataapi.iter_trades(condition=m['cond'], max_rows=40000):
        k = (int(r['timestamp']), round(float(r['price']), 4), round(float(r['size']), 2))
        if (r.get('proxy_wallet') or '').lower() == wal: continue
        if own[k] > 0: own[k] -= 1; continue
        p = float(r['price']); rows.append((int(r['timestamp']), p if r.get('outcome') == m['first'] else 1 - p, float(r['size'])))
    rows.sort(); return rows
with ThreadPoolExecutor(4) as ex: tapes = list(ex.map(tape, ms))
mid = (d['start'] + d['end']) / 2
for lab, lo, hi in (('V1 [60s,15min]', 60, 900), ('V2 [5min,30min]', 300, 1800)):
    per = {}; nosig = 0; nofill = 0; acct = {}
    for m, tp in zip(ms, tapes):
        ts = [t for t, _, _ in tp]; cl = collections.OrderedDict()
        for r in m['fills']:
            if r['role'] != 'T' or not (0.05 <= r['p'] <= 0.95): continue
            key = None
            for k in cl:
                if k[1] == r['sign'] and r['t'] - cl[k]['t0'] <= 1800: key = k
            if key is None: key = (r['t'], r['sign']); cl[key] = dict(t0=r['t'], usd=0.0, sh=0.0, cost=0.0)
            c = cl[key]; c['usd'] += r['usd']; c['sh'] += r['size']; c['cost'] += r['py'] * r['size']
        res = []; own_res = []
        for (t0, sign), c in cl.items():
            if c['usd'] < 200: continue
            nosig += 0
            i, j = bisect.bisect_left(ts, t0 + lo), bisect.bisect_right(ts, t0 + hi)
            if j <= i: nofill += 1; continue
            pr = [p for _, p, _ in tp[i:j]]
            py = max(pr) if sign > 0 else min(pr)
            if not (0.02 <= py <= 0.98): nofill += 1; continue
            p_tok = py if sign > 0 else 1 - py                      # price of the token we buy
            pnl = sign * (m['final'] - py) - 0.01 * p_tok * (1 - p_tok)
            res.append((pnl, p_tok, t0)); own_res.append(sign * (m['final'] - c['cost'] / c['sh']))
        if res: per[m['cond']] = (st.mean(x[0] for x in res), st.mean(x[1] for x in res), min(x[2] for x in res), len(res), st.mean(own_res))
    def line(name, v):
        if len(v) < 3: return f'    {name:12} n<3'
        x = [a[0] for a in v]; cost = st.mean(a[1] for a in v)
        return (f"    {name:12} markets {len(v):3} clusters {sum(a[3] for a in v):3} copy pnl/share {100 * st.mean(x):6.2f} c (se {100 * st.stdev(x) / len(x) ** .5:.2f}, t {st.mean(x) / (st.stdev(x) / len(x) ** .5):5.2f}) "
                f"avg cost {cost:.2f} -> ROI {100 * st.mean(x) / cost:5.1f}% | winners {sum(1 for a in x if a > 0)}/{len(x)} | account's own pnl/share on same clusters {100 * st.mean(a[4] for a in v):6.2f} c")
    v = list(per.values())
    print(f'{tag} {lab}: no independent print in window for {nofill} clusters')
    print(line('all', v)); print(line('first half', [a for a in v if a[2] < mid])); print(line('second half', [a for a in v if a[2] >= mid]))
