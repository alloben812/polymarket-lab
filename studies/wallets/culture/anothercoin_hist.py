"""anothercoin: when did the profit accrue (daily economic_pnl), and which redeems / sells paid it?"""
import collections, datetime as dt, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from pmlab import dataapi, wallet as W
wal = '0xc22b72b0fec23b797589ef6778bb6589e325deab'; end = int(time.time()); start = end - 33 * 86400
day = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime('%m-%d')
pts = dataapi.user_pnl(wal, 'all', '1d'); prev = 0
print('daily change of economic_pnl (and trade_pnl):')
print('  ' + ' '.join(f"{day(p['timestamp'])}:{(p.get('economic_pnl') or 0) - (pts[i - 1].get('economic_pnl') or 0 if i else 0):+.0f}" for i, p in enumerate(pts)))
print('  keys', sorted(pts[-1].keys()))
act = list(dataapi.iter_activity(wal, types='REDEEM,CONVERSION,MERGE,SPLIT', start=start, end=end))
c = collections.Counter(); u = collections.Counter()
for a in act: c[a['type']] += 1; u[a['type']] += float(a.get('usdc_size') or 0)
print('33d activity', dict(c), {k: round(v) for k, v in u.items()})
red = sorted((a for a in act if a['type'] == 'REDEEM'), key=lambda a: -float(a.get('usdc_size') or 0))[:12]
for a in red: print(f"  REDEEM {day(a['timestamp'])} {float(a['usdc_size']):8.0f}  {str(a.get('slug'))[:80]}")
fills, tr = W.fetch_fills(wal, start, end, 60000)
print('33d fills', len(fills), 'truncated', tr)
S = collections.Counter()
for f in fills: S[(f['side'], f['outcome'])] += float(f['size']) * float(f['price'])
print({str(k): round(v) for k, v in S.items()})
sells = sorted((f for f in fills if f['side'] == 'SELL'), key=lambda f: -float(f['size']) * float(f['price']))[:12]
for f in sells: print(f"  SELL {day(f['timestamp'])} {f['role']} {float(f['size']):8.0f} @ {float(f['price']):.3f} = {float(f['size']) * float(f['price']):7.0f} {f['outcome']} {str(f['slug'])[:70]}")
# cheapest YES buys and biggest single buys: lottery tickets or arbitrage legs?
by = collections.defaultdict(lambda: [0.0, 0.0, 0])
for f in fills:
    if f['side'] == 'BUY':
        b = by[(f['event_slug'], f['outcome'])]; b[0] += float(f['size']) * float(f['price']); b[1] += float(f['size']); b[2] += 1
print('largest BUY groups (event, outcome):')
for (ev, o), b in sorted(by.items(), key=lambda kv: -kv[1][0])[:12]: print(f"  {str(ev)[:60]:60} {o:3} usd {b[0]:7.0f} sh {b[1]:7.0f} avg {b[0] / b[1]:.3f} fills {b[2]}")
net = S[('SELL', 'Yes')] + S[('SELL', 'No')] - S[('BUY', 'Yes')] - S[('BUY', 'No')] + u['REDEEM'] + u['CONVERSION'] + u['MERGE'] - u['SPLIT']
print(f'33d net cash from trading + redeem + conversion + merge - split: {net:.0f}')
