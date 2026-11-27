"""Sizing: peak capital tied up, markets open at once, share of market volume.  python3 capital.py <tag> ..."""
import json, sys, statistics as st
for tag in sys.argv[1:]:
    d = json.load(open(tag + '.story.json')); ev = []; opn = []
    for m in d['markets']:
        cost = 0.0
        for r in m['fills']:
            dv = r['usd'] if r['side'] == 'BUY' else -r['usd']; cost += dv; ev.append((r['t'], dv, 0))
        tend = m['closed'] or m['t99'] or d['end']
        ev.append((max(tend, m['fills'][-1]['t']) + 1, -cost, 0)); opn.append((m['fills'][0]['t'], 1)); opn.append((max(tend, m['fills'][-1]['t']), -1))
    ev.sort(); run = peak = 0.0
    for t, dv, _ in ev: run += dv; peak = max(peak, run)
    opn.sort(); c = pk = 0; ser = []
    for t, x in opn: c += x; pk = max(pk, c); ser.append(c)
    vols = [m['vol'] for m in d['markets'] if m['vol']]; sh = [sum(r['usd'] for r in m['fills']) / m['vol'] for m in d['markets'] if m['vol']]
    fu = sorted(r['usd'] for m in d['markets'] for r in m['fills']); mb = sorted(m['buy_usd'] for m in d['markets'])
    days = (d['end'] - d['start']) / 86400; pnl = sum(m['pnl'] for m in d['markets'] if m['resolved'])
    print(f"{tag:17} days {days:3.0f} mkts {len(d['markets']):3} peak net cost tied up ${peak:7.0f} | open markets median {st.median(ser):3.0f} max {pk:3} | fill usd median {fu[len(fu) // 2]:5.0f} p90 {fu[9 * len(fu) // 10]:5.0f} | per-market buy median {mb[len(mb) // 2]:5.0f} p90 {mb[9 * len(mb) // 10]:6.0f} | market volume median ${st.median(vols):7.0f} | account turnover / market volume median {100 * st.median(sh):4.1f}% | resolved pnl {pnl:6.0f} = {100 * pnl / max(1, peak):4.0f}% of peak capital in window")
