"""Mark-outs of an account's fills against the whole-market tape.   python3 markout.py <tag> <n_markets> [family]

For the account's top markets (by its own turnover) pull the full tape (cached), build the YES-equivalent last-trade
price series from OTHER wallets' fills, and for every fill of the account measure, signed in the account's favour:
  pre   = (price paid vs the last other-wallet print more than 3 s before the fill)   -> did it chase or fade?
  mo_k  = move of the last print k minutes after the fill, relative to the fill price -> was it right, and how soon?
Also: how many other-taker fills in the same direction happened in the 30 s before (is it first or a follower).
Errors are clustered by market.
"""
import bisect, collections, json, os, sys, time
from pmlab import dataapi, stats
tag, nm = sys.argv[1], int(sys.argv[2]); famsel = sys.argv[3] if len(sys.argv) > 3 else None
base = '/home/user/polymarket-lab/data/politics_wallets/'; os.makedirs(base + 'tapes', exist_ok=True)
fills = json.load(open(base + tag + '.fills.json')); meta = {m['condition']: m for m in json.load(open(tag + '.json'))['_markets']}
wal = json.load(open(tag + '.json'))['account']['wallet'].lower()
for f in fills: f['size'] = float(f['size']); f['price'] = float(f['price'])
if famsel: fills = [f for f in fills if (meta.get(f['condition_id']) or {}).get('family') == famsel]
turn = collections.Counter()
for f in fills: turn[f['condition_id']] += f['size'] * f['price']
def tape(c):
    p = base + 'tapes/' + c + '.json'
    if os.path.exists(p): return json.load(open(p))
    rows = [[r['timestamp'], r['side'], r.get('outcome_index'), float(r['price']), float(r['size']), (r.get('proxy_wallet') or '').lower()] for r in dataapi.iter_trades(condition=c, max_rows=40000)]
    rows.sort(); json.dump(rows, open(p, 'w')); return rows
rows_out = []; cov = 0
for c, _ in turn.most_common(nm):
    tp = tape(c)
    if not tp: continue
    oth = [(t, (p if oi == 0 else 1 - p), s, sd, oi) for t, sd, oi, p, s, w in tp if w != wal]
    ts = [x[0] for x in oth]; t0 = tp[0][0]
    for f in fills:
        if f['condition_id'] != c or f['timestamp'] < t0 + 600: continue
        yes = f['outcome'] in ('Yes',) or (f['outcome'] not in ('Yes', 'No') and False)
        oi = 0 if f['outcome'] == 'Yes' else 1
        py = f['price'] if oi == 0 else 1 - f['price']                     # YES-equivalent fill price
        d = 1 if (f['side'] == 'BUY') == (oi == 0) else -1                 # +1 = long YES exposure
        t = f['timestamp']
        i = bisect.bisect_left(ts, t - 3) - 1
        if i < 0: continue
        pre = d * (py - oth[i][1])
        def at(k):
            j = bisect.bisect_right(ts, t + k) - 1
            return None if j < 0 or ts[-1] < t + k else d * (oth[j][1] - py)
        lo = bisect.bisect_left(ts, t - 33); same = 0
        for x in oth[lo:i + 1]:
            dd = 1 if (x[3] == 'BUY') == (x[4] == 0) else -1
            same += dd == d
        rows_out.append(dict(c=c, role=f['role'], side=f['side'], sh=f['size'], pre=pre, m1=at(60), m10=at(600), m60=at(3600), m24=at(86400), same=same, age=t - ts[i]))
    cov += 1
print(f"{tag}: {len(rows_out)} fills in {cov} markets (family {famsel}); cents per share, share-weighted, clustered by market")
for key in sorted({(r['role'], r['side']) for r in rows_out}) + [('all', 'all')]:
    sel = [r for r in rows_out if key[0] == 'all' or (r['role'], r['side']) == key]
    out = [f"{key[0]} {key[1]:4} n {len(sel):5} sh {sum(r['sh'] for r in sel):9.0f}"]
    for k in ('pre', 'm1', 'm10', 'm60', 'm24'):
        s2 = [r for r in sel if r[k] is not None]
        if len({r['c'] for r in s2}) < 2: out.append(f"{k} n/a"); continue
        num = collections.Counter(); den = collections.Counter()
        for r in s2: num[r['c']] += 100 * r[k] * r['sh']; den[r['c']] += r['sh']
        cs = list(num); e = stats.ratio_cluster([num[c] for c in cs], [den[c] for c in cs])
        out.append(f"{k} {e[0]:+.2f} (t {e[2]:.1f}, {len(cs)} mk)")
    fol = sum(1 for r in sel if r['same'] > 0) / max(1, len(sel)); out.append(f"preceded by same-direction prints in 30 s: {fol:.0%}; median age of last print {sorted(r['age'] for r in sel)[len(sel) // 2]} s")
    print('  ' + ' | '.join(out))
json.dump(rows_out, open(tag + '.markout.json', 'w'))
