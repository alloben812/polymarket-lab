"""Cb94C437: what do its bursts look like?  Composition of multi-market bursts and raw sequences for sample events."""
import collections, json, sys, time
fills = json.load(open('/home/user/polymarket-lab/data/politics_wallets/Cb94C437.fills.json'))
for f in fills: f['size'] = float(f['size']); f['price'] = float(f['price'])
fills.sort(key=lambda f: f['timestamp'])
# same-second / same-tx multi-leg composition
tx = collections.defaultdict(list)
for f in fills: tx[f['transaction_hash']].append(f)
comp = collections.Counter(); usd = collections.Counter()
for h, fs in tx.items():
    k = tuple(sorted(collections.Counter((f['side'], f['outcome'] if f['outcome'] in ('Yes','No') else 'o') for f in fs).items()))
    nm = len({f['condition_id'] for f in fs}); comp[(nm if nm < 4 else '4+', len(fs) if len(fs) < 4 else '4+')] += 1; usd[(nm if nm < 4 else '4+', len(fs) if len(fs) < 4 else '4+')] += sum(f['size'] * f['price'] for f in fs)
print('transactions:', len(tx), ' by (markets in tx, fills in tx): count, $', {k: (v, round(usd[k])) for k, v in sorted(comp.items(), key=lambda kv: -kv[1])[:10]})
# 5-second windows across an event: pairs of legs
win = collections.defaultdict(list)
for f in fills: win[(f['event_slug'], f['timestamp'] // 5)].append(f)
pc = collections.Counter(); pu = collections.Counter(); ex = []
for k, fs in win.items():
    cs = {f['condition_id'] for f in fs}
    if len(cs) < 2: continue
    sig = tuple(sorted({(f['side'], f['outcome']) for f in fs})); pc[sig] += 1; pu[sig] += sum(f['size'] * f['price'] for f in fs)
    if len(ex) < 400: ex.append((k, fs))
print('5 s windows with >=2 markets of one event:', sum(pc.values()), 'of', len(win), ' $', round(sum(pu.values())))
for s, v in pc.most_common(8): print('   ', s, v, round(pu[s]))
for sel in sys.argv[1:]:
    ev = [f for f in fills if f['event_slug'] == sel]
    print(f'\n--- {sel}: {len(ev)} fills; first 70 rows from the busiest day')
    day = collections.Counter(f['timestamp'] // 86400 for f in ev).most_common(1)[0][0]
    for f in [f for f in ev if f['timestamp'] // 86400 == day][:70]:
        print(f"  {time.strftime('%m-%d %H:%M:%S', time.gmtime(f['timestamp']))} {f['side']:4} {f['outcome'][:3]:3} {f['size']:9.1f} @ {f['price']:.4f}  {f['slug'][:55]}")
