"""How a conversion account builds and unwinds NO baskets.   python3 negrisk_story.py <tag> <wallet> <days> [n_events]
Per event: outcomes traded, NO shares and average NO price per outcome, basket cost (sum of average NO prices over the
outcomes it bought), what a conversion of m NO legs pays (m - 1), YES sold afterwards, conversions (count, USDC)."""
import collections, json, os, sys, time
from pmlab import dataapi, gamma
tag, wal, days = sys.argv[1], sys.argv[2], float(sys.argv[3]); ne = int(sys.argv[4]) if len(sys.argv) > 4 else 8
base = '/home/user/polymarket-lab/data/politics_wallets/'; fills = json.load(open(base + tag + '.fills.json'))
end = max(f['timestamp'] for f in fills); start = min(f['timestamp'] for f in fills)
ap = base + tag + '.act.json'
if os.path.exists(ap): act = json.load(open(ap))
else:
    act = [{k: a.get(k) for k in ('type', 'timestamp', 'usdc_size', 'size', 'event_slug', 'condition_id', 'slug')} for a in dataapi.iter_activity(wal, types='CONVERSION,MERGE,REDEEM,SPLIT', start=start, end=end)]; json.dump(act, open(ap, 'w'))
ev = collections.defaultdict(list)
for f in fills: f['size'] = float(f['size']); f['price'] = float(f['price']); ev[f['event_slug']].append(f)
ca = collections.defaultdict(lambda: collections.Counter()); cn = collections.Counter(); ct = collections.defaultdict(list)
for a in act:
    ca[a['event_slug']][a['type']] += float(a.get('usdc_size') or 0); cn[(a['event_slug'], a['type'])] += 1
    if a['type'] == 'CONVERSION': ct[a['event_slug']].append(a['timestamp'])
rank = sorted(ev, key=lambda k: -ca[k]['CONVERSION'])[:ne]
tot = collections.Counter()
for k in ev:
    fs = ev[k]
    if not ca[k]['CONVERSION']: continue
    nb = sum(f['size'] * f['price'] for f in fs if f['side'] == 'BUY' and f['outcome'] == 'No'); tot['no_buy'] += nb
    tot['no_buy_maker'] += sum(f['size'] * f['price'] for f in fs if f['side'] == 'BUY' and f['outcome'] == 'No' and f['role'] == 'M')
    tot['yes_buy'] += sum(f['size'] * f['price'] for f in fs if f['side'] == 'BUY' and f['outcome'] == 'Yes'); tot['yes_sell'] += sum(f['size'] * f['price'] for f in fs if f['side'] == 'SELL' and f['outcome'] == 'Yes')
    tot['yes_sell_maker'] += sum(f['size'] * f['price'] for f in fs if f['side'] == 'SELL' and f['outcome'] == 'Yes' and f['role'] == 'M')
    tot['no_sell'] += sum(f['size'] * f['price'] for f in fs if f['side'] == 'SELL' and f['outcome'] == 'No'); tot['conv'] += ca[k]['CONVERSION']; tot['merge'] += ca[k]['MERGE']; tot['events'] += 1
print(f"{tag}: {days:.0f} days; events with conversions {tot['events']}: NO bought ${tot['no_buy']:,.0f} (maker {tot['no_buy_maker'] / max(1, tot['no_buy']):.0%}), YES bought ${tot['yes_buy']:,.0f}, YES sold ${tot['yes_sell']:,.0f} (maker {tot['yes_sell_maker'] / max(1, tot['yes_sell']):.0%}), NO sold ${tot['no_sell']:,.0f}, conversions ${tot['conv']:,.0f}, merges ${tot['merge']:,.0f}")
px = collections.Counter()
for k in ev:
    if not ca[k]['CONVERSION']: continue
    for f in ev[k]:
        if f['side'] == 'BUY' and f['outcome'] == 'No': p = f['price']; px['<0.50' if p < .5 else '<0.80' if p < .8 else '<0.90' if p < .9 else '<0.95' if p < .95 else '<0.99' if p < .99 else '>=0.99'] += f['size'] * p
print('  NO buys in conversion events by price ($):', {a: round(b) for a, b in sorted(px.items())})
for k in rank:
    fs = ev[k]; per = collections.defaultdict(lambda: [0.0, 0.0, 0.0]); ysell = collections.defaultdict(lambda: [0.0, 0.0])
    for f in fs:
        if f['side'] == 'BUY' and f['outcome'] == 'No': x = per[f['slug']]; x[0] += f['size']; x[1] += f['size'] * f['price']; x[2] += f['size'] * (f['role'] == 'M')
        if f['side'] == 'SELL' and f['outcome'] == 'Yes': y = ysell[f['slug']]; y[0] += f['size']; y[1] += f['size'] * f['price']
    try: g = gamma.event_by_slug(k, cache=True) or {}
    except Exception: g = {}
    nmk = len(g.get('markets') or [])
    m = len(per); cost = sum(x[1] / x[0] for x in per.values() if x[0]); sh = sorted(x[0] for x in per.values())
    gaps = sorted(set(ct[k])); first_buy = min(f['timestamp'] for f in fs)
    print(f"\n  {k[:66]}: event has {nmk} outcomes; NO bought on {m}: shares per leg min/med/max {sh[0]:.0f}/{sh[len(sh) // 2]:.0f}/{sh[-1]:.0f}; sum of avg NO prices {cost:.3f} vs payout m-1 = {m - 1}  -> basket margin {100 * (m - 1 - cost):+.1f} c per set BEFORE fees and before the free YES legs;")
    print(f"     conversions {cn[(k, 'CONVERSION')]} = ${ca[k]['CONVERSION']:,.0f}; merges ${ca[k]['MERGE']:,.0f}; YES sold on {len(ysell)} outcomes ${sum(y[1] for y in ysell.values()):,.0f}; maker share of NO shares {sum(x[2] for x in per.values()) / max(1, sum(x[0] for x in per.values())):.0%}; median delay first NO buy of a day -> conversion not measured; conversions on {len({t // 86400 for t in gaps})} days")
    for s, x in sorted(per.items(), key=lambda kv: -kv[1][1])[:6]: print(f"       NO {s[:58]:58} {x[0]:8.0f} sh @ {x[1] / x[0]:.4f}")
