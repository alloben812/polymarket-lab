"""Event-level cash result of conversion accounts (unit = event; rewards and rebates are account-level and excluded).
   python3 evstats.py <tag> ...     reads <tag>.cash.json written by cash.py"""
import json, sys
from pmlab import stats
sign = {'TRADE_BUY': -1, 'TRADE_SELL': 1, 'SPLIT': -1, 'MERGE': 1, 'REDEEM': 1, 'CONVERSION': 1}
for tag in sys.argv[1:]:
    d = json.load(open(tag + '.cash.json')); ev = []
    for k, c in d['byev'].items():
        buy = c.get('TRADE_BUY', 0)
        if buy < 50: continue
        net = sum(sign.get(t, 0) * v for t, v in c.items()); ev.append((k, net, buy, c.get('CONVERSION', 0)))
    conv = [e for e in ev if e[3] > 0.3 * e[2]]; oth = [e for e in ev if e[3] <= 0.3 * e[2]]
    for name, grp in (('conversion events (conv > 30% of buys)', conv), ('other events', oth)):
        if len(grp) < 3: continue
        m, se, t = stats.mean_se([e[1] for e in grp]); r, rse, rt = stats.ratio_cluster([e[1] for e in grp], [e[2] for e in grp])
        print(f"{tag:16} {name:40} n {len(grp):4} buys ${sum(e[2] for e in grp):12,.0f} net cash ${sum(e[1] for e in grp):10,.0f} = {100 * r:+.2f}% of buys (t {rt:.1f} by event); events with net > 0: {sum(1 for e in grp if e[1] > 0) / len(grp):.0%}; mean per event ${m:,.0f} (t {t:.1f})")
        s = sorted(grp, key=lambda e: e[1]); print('      worst:', [(e[0][:34], round(e[1])) for e in s[:3]], ' best:', [(e[0][:34], round(e[1])) for e in s[-3:]])
    t = d['tot']; print(f"      account level: rewards {t.get('REWARD', 0):,.0f} maker rebate {t.get('MAKER_REBATE', 0):,.0f} taker rebate {t.get('TAKER_REBATE', 0):,.0f}; net cash {d['net']:,.0f} + open value {d['pos_value']:,.0f}")
