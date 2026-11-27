"""anothercoin: what are the 600+ neg-risk conversions?  Pull 14 days of activity and fills, group by event."""
import collections, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from pmlab import dataapi, wallet as W, gamma
wal = '0xc22b72b0fec23b797589ef6778bb6589e325deab'; end = int(time.time()); start = end - 14 * 86400
act = list(dataapi.iter_activity(wal, types='SPLIT,MERGE,REDEEM,CONVERSION', start=start, end=end))
print('activity rows', len(act), collections.Counter(a.get('type') for a in act))
conv = [a for a in act if a.get('type') == 'CONVERSION']
print('sample conversion row:', {k: v for k, v in conv[0].items() if k not in ('icon', 'bio', 'profile_image', 'profile_image_optimized')})
tot = collections.Counter()
for a in act: tot[a['type']] += float(a.get('usdc_size') or a.get('usdcSize') or 0)
print('usdc by type', {k: round(v) for k, v in tot.items()})
fills, _ = W.fetch_fills(wal, start, end, 60000)
ev = collections.defaultdict(lambda: dict(buy_no=0.0, buy_no_sh=0.0, buy_yes=0.0, buy_yes_sh=0.0, sell=0.0, n=0, mk=set(), conv=0.0, conv_n=0, redeem=0.0, fam=''))
for f in fills:
    e = ev[f['event_slug']]; usd = float(f['size']) * float(f['price']); e['n'] += 1; e['mk'].add(f['condition_id'])
    if f['side'] == 'BUY':
        k = 'buy_no' if f['outcome'] == 'No' else 'buy_yes'; e[k] += usd; e[k + '_sh'] += float(f['size'])
    else: e['sell'] += usd
for a in act:
    e = ev[a.get('event_slug')]; u = float(a.get('usdc_size') or 0)
    if a['type'] == 'CONVERSION': e['conv'] += u; e['conv_n'] += 1
    if a['type'] == 'REDEEM': e['redeem'] += u
cv = {k: e for k, e in ev.items() if e['conv_n']}
print(f'events traded {len(ev)}, events with conversions {len(cv)}')
S = collections.Counter()
for e in ev.values():
    S['buy_no'] += e['buy_no']; S['buy_yes'] += e['buy_yes']; S['sell'] += e['sell']; S['redeem'] += e['redeem']; S['conv'] += e['conv']
    S['buy_no_sh'] += e['buy_no_sh']; S['buy_yes_sh'] += e['buy_yes_sh']
print({k: round(v) for k, v in S.items()}, 'avg NO price', round(S['buy_no'] / max(1, S['buy_no_sh']), 3), 'avg YES price', round(S['buy_yes'] / max(1, S['buy_yes_sh']), 3))
print('top events by conversion usdc:')
for k, e in sorted(cv.items(), key=lambda kv: -kv[1]['conv'])[:14]:
    print(f"  {str(k)[:60]:60} mk {len(e['mk']):3} fills {e['n']:4} buyNO {e['buy_no']:7.0f} ({e['buy_no_sh']:6.0f} sh @ {e['buy_no'] / max(1, e['buy_no_sh']):.3f}) buyYES {e['buy_yes']:6.0f} sell {e['sell']:6.0f} conv_n {e['conv_n']:3} conv_usdc {e['conv']:7.0f} redeem {e['redeem']:6.0f}")
json.dump({'activity': act[:2000]}, open('anothercoin.activity.json', 'w'))
pos = dataapi.get_json(dataapi.DATA + '/positions', {'user': wal, 'limit': 500}).get('data') or []
print('open positions', len(pos), 'keys', sorted(pos[0].keys())[:30] if pos else None)
val = sum(float(p.get('current_value') or 0) for p in pos); print('current value of first 500 positions', round(val))
top = sorted(pos, key=lambda p: -float(p.get('current_value') or 0))[:12]
for p in top: print(f"  {str(p.get('slug') or p.get('title'))[:64]:64} {p.get('outcome')} size {float(p.get('size') or 0):8.0f} avg {float(p.get('avg_price') or 0):.3f} cur {float(p.get('cur_price') or p.get('current_price') or 0):.3f} value {float(p.get('current_value') or 0):7.0f} pnl {float(p.get('cash_pnl') or 0):7.0f}")
