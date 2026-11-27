"""Does the account lead the repricing or follow it?  For each fill (own rows removed from the tape):
  pre30 / pre120 = signed move of the independent price in the 30 / 120 minutes BEFORE the fill
  post10 / post60 = signed move in the 10 / 60 minutes AFTER (from the last independent price before the fill)
  slip = fill price minus last independent price (signed): what it paid to get in
Classes: FOLLOW = pre120 >= +5c (price already running its way), FADE = pre120 <= -5c, QUIET = in between.
  python3 leadlag.py <tag> [slug-regex]"""
import bisect, collections, json, re, statistics as st, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from pmlab import dataapi
tag = sys.argv[1]; rx = re.compile(sys.argv[2] if len(sys.argv) > 2 else '.')
d = json.load(open(tag + '.story.json')); wal = d['wallet'].lower()
ms = [m for m in d['markets'] if rx.search(m['slug'] or '')]
def tape(m):
    own = collections.Counter((r['t'], round(r['p'], 4), round(r['size'], 2)) for r in m['fills']); rows = []
    for r in dataapi.iter_trades(condition=m['cond'], max_rows=40000):
        k = (int(r['timestamp']), round(float(r['price']), 4), round(float(r['size']), 2))
        if (r.get('proxy_wallet') or '').lower() == wal: continue
        if own[k] > 0: own[k] -= 1; continue
        p = float(r['price']); rows.append((int(r['timestamp']), p if r.get('outcome') == m['first'] else 1 - p))
    rows.sort(); return rows
with ThreadPoolExecutor(4) as ex: tapes = list(ex.map(tape, ms))
C = collections.defaultdict(lambda: collections.defaultdict(float)); MK = collections.defaultdict(set)
for m, tp in zip(ms, tapes):
    ts = [t for t, _ in tp]
    def px(t):
        i = bisect.bisect_right(ts, t) - 1
        return tp[i][1] if i >= 0 else None
    for r in m['fills']:
        if not (0.03 <= r['p'] <= 0.97): continue          # skip dust / redemption-like prints
        b, b30, b120, a10, a60 = px(r['t'] - 1), px(r['t'] - 1800), px(r['t'] - 7200), px(r['t'] + 600), px(r['t'] + 3600)
        if None in (b, b30, b120, a10, a60): continue
        s = r['sign']; pre120 = s * (b - b120)
        cls = 'FOLLOW' if pre120 >= 0.05 else 'FADE' if pre120 <= -0.05 else 'QUIET'
        for k in (cls + ' ' + r['role'], 'ALL ' + r['role'], 'ALL'):
            c = C[k]; sh = r['size']; c['n'] += 1; c['sh'] += sh; c['usd'] += r['usd']
            c['pre30'] += s * (b - b30) * sh; c['pre120'] += pre120 * sh; c['slip'] += s * (r['py'] - b) * sh
            c['post10'] += s * (a10 - b) * sh; c['post60'] += s * (a60 - b) * sh
            if r['pnl'] is not None and m['resolved']: c['pnl'] += r['pnl']; c['rusd'] += r['usd']
            MK[k].add(m['cond'])
print(f'{tag}: fills priced 0.03-0.97 with a full independent tape around them')
print(f"  {'class':10} {'fills':>5} {'mkts':>4} {'usd':>8} {'pre120':>7} {'pre30':>6} {'slip':>6} {'post10':>6} {'post60':>6}  pnl_to_final(resolved) %usd   (moves in cents/share, share-weighted)")
for k in sorted(C):
    c = C[k]; sh = c['sh']
    print(f"  {k:10} {int(c['n']):5} {len(MK[k]):4} {c['usd']:8.0f} {100 * c['pre120'] / sh:7.2f} {100 * c['pre30'] / sh:6.2f} {100 * c['slip'] / sh:6.2f} {100 * c['post10'] / sh:6.2f} {100 * c['post60'] / sh:6.2f}  {c['pnl']:9.0f} {100 * c['pnl'] / max(1, c['rusd']):6.1f}")
