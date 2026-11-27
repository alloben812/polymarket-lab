"""Fetch (and cache) labelled fills of one account and describe HOW it trades.   python3 dive.py <tag> <wallet> <days> [family]

Joins fills to the per-market rows of <tag>.json (family, end, neg_risk, resolved).  FIFO round trips per token give
holding times and realised cents per share; what is not sold is 'held' (to settlement or still open).
"""
import collections, json, os, statistics as st, sys, time
from pmlab import wallet as W
tag, wal, days = sys.argv[1], sys.argv[2], float(sys.argv[3]); famsel = sys.argv[4] if len(sys.argv) > 4 else None
cache = f'/home/user/polymarket-lab/data/politics_wallets/{tag}.fills.json'
if os.path.exists(cache): fills = json.load(open(cache))
else:
    end = int(time.time()); fills, tr = W.fetch_fills(wal, end - int(days * 86400), end, 150000); json.dump(fills, open(cache, 'w'))
mk = {m['condition']: m for m in json.load(open(tag + '.json'))['_markets']}
for f in fills:
    f['size'] = float(f['size']); f['price'] = float(f['price']); f['usd'] = f['size'] * f['price']; m = mk.get(f['condition_id']) or {}
    f['fam'] = m.get('family', '?'); f['end'] = m.get('end'); f['neg'] = m.get('neg_risk'); f['res'] = m.get('resolved')
if famsel: fills = [f for f in fills if f['fam'] == famsel]
fills.sort(key=lambda f: f['timestamp'])
T = sum(f['usd'] for f in fills); print(f"{tag}: {len(fills)} fills, ${T:,.0f}, family filter {famsel}, markets {len({f['condition_id'] for f in fills})}, events {len({f['event_slug'] for f in fills})}")
def pct(xs, q): xs = sorted(xs); return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else None
c = collections.Counter(); u = collections.Counter()
for f in fills: k = (f['role'], f['side'], f['outcome'] if f['outcome'] in ('Yes', 'No') else 'other'); c[k] += 1; u[k] += f['usd']
print(' role/side/outcome $:', {k: round(v) for k, v in sorted(u.items(), key=lambda kv: -kv[1])})
print(' fill usd p10/p50/p90/p99:', [round(pct([f['usd'] for f in fills], q), 1) for q in (.1, .5, .9, .99)], ' neg-risk share of $:', round(sum(f['usd'] for f in fills if f['neg']) / max(T, 1), 2))
# time to end
b = collections.Counter()
for f in fills:
    if not f['end']: b['no end'] += f['usd']; continue
    d = (f['end'] - f['timestamp']) / 86400
    b['after end' if d < 0 else '<1d' if d < 1 else '1-7d' if d < 7 else '7-30d' if d < 30 else '30-180d' if d < 180 else '>180d'] += f['usd']
print(' $ by time to market end:', {k: round(v) for k, v in b.items()})
# FIFO round trips per token
lots = collections.defaultdict(collections.deque); rt = []; unmatched_sell = 0.0
for f in fills:
    q = lots[f['token_id']]
    if f['side'] == 'BUY': q.append([f['size'], f['price'], f['timestamp'], f['role']])
    else:
        s = f['size']
        while s > 1e-9 and q:
            l = q[0]; x = min(s, l[0]); rt.append((x, l[1], f['price'], f['timestamp'] - l[2], l[3], f['role'], f['event_slug'])); l[0] -= x; s -= x
            if l[0] <= 1e-9: q.popleft()
        unmatched_sell += s * f['price']
bought = sum(f['usd'] for f in fills if f['side'] == 'BUY'); rsh = sum(r[0] for r in rt)
print(f" bought ${bought:,.0f}; round-tripped inside window: {rsh:,.0f} shares, cost ${sum(r[0] * r[1] for r in rt):,.0f}, realised ${sum(r[0] * (r[2] - r[1]) for r in rt):,.0f} "
      f"({100 * sum(r[0] * (r[2] - r[1]) for r in rt) / max(1, rsh):.2f} c/share); sells of older inventory ${unmatched_sell:,.0f}")
if rt:
    hs = [r[3] for r in rt for _ in (0,)]; w = [r[0] * r[1] for r in rt]
    def wq(q):
        z = sorted(zip(hs, w)); tot = sum(w); a = 0
        for h, x in z:
            a += x
            if a >= q * tot: return h
    print(' holding time of round trips ($-weighted) p10/p50/p90:', [f"{wq(q) / 60:.1f} min" for q in (.1, .5, .9)], ' share of round-trip $ closed <60 s:', round(sum(x for h, x in zip(hs, w) if h < 60) / sum(w), 2), '<1 h:', round(sum(x for h, x in zip(hs, w) if h < 3600) / sum(w), 2))
    rr = collections.Counter(); rp = collections.Counter()
    for r in rt: rr[(r[4], r[5])] += r[0]; rp[(r[4], r[5])] += r[0] * (r[2] - r[1])
    print(' round trips by (entry role, exit role): shares, c/share:', {k: (round(v), round(100 * rp[k] / v, 2)) for k, v in rr.items()})
# price buckets of buys
pb = collections.Counter()
for f in fills:
    if f['side'] == 'BUY': p = f['price']; pb['<0.05' if p < .05 else '<0.30' if p < .3 else '<0.70' if p < .7 else '<0.90' if p < .9 else '<0.95' if p < .95 else '<0.99' if p < .99 else '>=0.99'] += f['usd']
print(' buy $ by price:', {k: round(v) for k, v in pb.items()})
# bursts: fills per (event, 10 s)
bur = collections.Counter((f['event_slug'], f['timestamp'] // 10) for f in fills); legs = collections.defaultdict(set)
for f in fills: legs[(f['event_slug'], f['timestamp'] // 10)].add(f['condition_id'])
print(' 10-second bursts:', len(bur), 'median fills', st.median(bur.values()), 'p90', pct(list(bur.values()), .9), ' bursts touching >=3 markets of one event:', sum(1 for v in legs.values() if len(v) >= 3))
day = collections.Counter(time.strftime('%m-%d', time.gmtime(f['timestamp'])) for f in fills); print(' fills per day:', dict(sorted(day.items())))
hr = collections.Counter(time.gmtime(f['timestamp']).tm_hour for f in fills); print(' fills per UTC hour:', [hr.get(h, 0) for h in range(24)])
evu = collections.Counter(); evn = collections.defaultdict(set)
for f in fills: evu[f['event_slug']] += f['usd']; evn[f['event_slug']].add(f['condition_id'])
print(' top events:'); [print(f"   {str(k)[:70]:70} mk {len(evn[k]):3} ${v:9,.0f}") for k, v in evu.most_common(14)]
