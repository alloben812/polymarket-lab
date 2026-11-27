"""Market stories for one account around its biggest jump reactions: rules text, jump, its fills, exit, outcome.
   python3 car_stories.py <tag> [n=12]"""
import collections, json, sys, time
from pmlab import gamma, dataapi
tag = sys.argv[1]; n = int(sys.argv[2]) if len(sys.argv) > 2 else 12
base = '/home/user/polymarket-lab/data/politics_wallets/'
J = json.load(open(tag + '.jumps.json')); fills = json.load(open(base + tag + '.fills.json'))
J = [j for j in J if j['lag'] is not None and j['lag'] <= 300]; J.sort(key=lambda j: -abs(j['cap']))
seen = []; pick = []
for j in J:
    if j['c'] in seen: continue
    seen.append(j['c']); pick.append(j)
    if len(pick) >= n: break
gm = gamma.markets_by_condition([j['c'] for j in pick]); res = dataapi.resolutions([j['c'] for j in pick], cache=False)
fm = lambda t: time.strftime('%m-%d %H:%M:%S', time.gmtime(t))
for j in pick:
    g = gm.get(j['c']) or {}; r = res.get(j['c']) or {}
    desc = ' '.join((g.get('description') or '').split())
    own = sorted([f for f in fills if f['condition_id'] == j['c']], key=lambda f: f['timestamp'])
    def agg(lo, hi):
        a = collections.defaultdict(lambda: [0.0, 0.0])
        for f in own:
            if lo <= f['timestamp'] - j['t'] < hi: x = a[(f['role'], f['side'], f['outcome'])]; x[0] += float(f['size']); x[1] += float(f['size']) * float(f['price'])
        return '; '.join(f"{k[0]} {k[1]} {k[2]} {v[0]:.0f} sh @ {v[1] / v[0]:.3f}" for k, v in a.items() if v[0]) or '-'
    net = collections.Counter()
    for f in own: net[f['outcome']] += float(f['size']) * (1 if f['side'] == 'BUY' else -1)
    print(f"\n* {j['slug']}  (fee type {g.get('feeType')}, end {g.get('endDate')}, closed {g.get('closedTime')}, volume ${float(g.get('volumeNum') or 0):,.0f})")
    print(f"  rules: {desc[:330]}")
    print(f"  source field: {g.get('resolutionSource') or '-'} | jump {fm(j['t'])} UTC {j['pre']:.2f} -> {j['lvl5']:.2f} (YES), takers in first 60 s: {j['n_wal60']}; account first fill lag {j['lag']} s")
    print(f"  account: 30 min before: {agg(-1800, 0)}")
    print(f"           0-5 min after: {agg(0, 300)}")
    print(f"           5 min - 24 h after: {agg(300, 86400)}")
    print(f"  net shares over the 30-day window: {dict((k, round(v)) for k, v in net.items())}; resolved {r.get('resolved')} final {r.get('final')}")
