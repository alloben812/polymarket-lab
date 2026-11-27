"""Cash reconstruction for accounts that use neg-risk conversions (the profile PnL cannot be trusted for them).

  python3 cash.py <tag> <wallet> <days|all>

net cash = sells + merges + redeems + conversion USDC + rewards + rebates - buys - splits (fees are inside trade cash
only if the API reports usdc net of fee; we report the API fee line separately).  True result for a window that covers
the whole life of the account = net cash + value of open positions now.
"""
import collections, json, sys, time
from pmlab import dataapi
from pmlab.http import get_json
tag, wal, span = sys.argv[1], sys.argv[2], sys.argv[3]
end = int(time.time()); start = 1704067200 if span == 'all' else end - int(float(span) * 86400)
tot = collections.Counter(); cnt = collections.Counter(); first = end; sample = {}
byev = collections.defaultdict(collections.Counter)
n = 0
for a in dataapi.iter_activity(wal, start=start, end=end):
    n += 1
    t = a.get('type'); side = a.get('side') or ''
    k = t + ('_' + side if t == 'TRADE' else '')
    u = float(a.get('usdc_size') or 0)
    tot[k] += u; cnt[k] += 1; first = min(first, int(a.get('timestamp') or end))
    sample.setdefault(k, {x: y for x, y in a.items() if x not in ('icon', 'bio', 'profile_image', 'profile_image_optimized', 'name', 'pseudonym')})
    byev[a.get('event_slug') or a.get('slug') or '?'][k] += u
sign = {'TRADE_BUY': -1, 'TRADE_SELL': 1, 'SPLIT': -1, 'MERGE': 1, 'REDEEM': 1, 'CONVERSION': 1, 'REWARD': 1, 'MAKER_REBATE': 1, 'TAKER_REBATE': 1}
net = sum(sign.get(k, 0) * v for k, v in tot.items())
pos = list(dataapi._walk('positions', {'user': wal, 'limit': 500}, 20000))
val = sum(float(p.get('current_value') or 0) for p in pos)
cost = sum(float(p.get('initial_value') or 0) for p in pos)
st = dataapi.user_stats(wal).get('all_time_pnl') or {}
print(f"=== {tag} {wal} window {span}: activity rows {n}, first row {time.strftime('%Y-%m-%d', time.gmtime(first))}")
print('   usdc by type:', {k: round(v) for k, v in sorted(tot.items())}, ' counts:', dict(cnt))
print(f"   net cash {net:,.0f} | open positions {len(pos)} value now {val:,.0f} (initial_value field {cost:,.0f}) | net cash + value {net + val:,.0f}")
print(f"   API all-time: trade_pnl {st.get('trade_pnl') or 0:,.0f} fees {st.get('fees') or 0:,.0f} economic {st.get('economic_pnl') or 0:,.0f} unrealized {st.get('unrealized_pnl')}")
ev = sorted(byev.items(), key=lambda kv: -kv[1].get('CONVERSION', 0))[:8]
for k, c in ev:
    if c.get('CONVERSION'): print(f"     {str(k)[:58]:58} buy {c['TRADE_BUY']:8.0f} sell {c['TRADE_SELL']:7.0f} conv {c['CONVERSION']:8.0f} merge {c['MERGE']:7.0f} redeem {c['REDEEM']:7.0f}")
top = sorted(pos, key=lambda p: -float(p.get('current_value') or 0))[:6]
for p in top: print(f"     pos {str(p.get('slug') or p.get('title'))[:56]:56} {p.get('outcome')} size {float(p.get('size') or 0):9.0f} avg {float(p.get('avg_price') or 0):.3f} value {float(p.get('current_value') or 0):8.0f}")
json.dump({'byev': {str(k): dict(v) for k, v in byev.items()}, 'tot': tot, 'cnt': cnt, 'net': net, 'pos_value': val, 'n_pos': len(pos), 'first': first, 'sample': sample, 'api': st}, open(f'{tag}.cash.json', 'w'), default=str)
