"""Compact one-screen summary of every pmlab.wallet JSON in this folder (screening step)."""
import json, glob, collections, re, sys
names = sys.argv[1:] or sorted(f[:-5] for f in glob.glob('*.json') if f not in ('leaders.json',) and '.' not in f[:-5].replace('0x',''))
for n in names:
    try: d = json.load(open(n + '.json'))
    except Exception as e: print(n, 'ERR', e); continue
    if 'summary' not in d: continue
    s, a, w = d['summary'], d['account'], d.get('api_window') or {}
    print(f"\n=== {n}  fills {s['fills']} mkts {s['markets']} (res {s['resolved_complete_markets']}, incompl {s['incomplete_markets']}, open {s['unresolved_markets']}) "
          f"turn ${s['turnover_usd']:,.0f} maker {s['maker_share_usd']:.0%} sell {s['sell_share_usd']:.0%} avgfill ${s['avg_fill_usd']:.0f} medmkt ${s['median_market_turnover']:.0f} trunc={a.get('truncated')}")
    print(f"    tool: gross {s['gross']:,.0f} fees {s['fees_est']:,.0f} net {s['net']:,.0f} win% {s.get('win_share_markets')}   API: gross {w.get('trade_pnl',0):,.0f} fees {w.get('fees',0):,.0f} "
          f"reb {((w.get('taker_rebate') or 0)+(w.get('maker_rebate') or 0)):,.0f} rewards {(w.get('reward_income') or 0):,.0f} kept {w.get('economic_pnl',0):,.0f} vol {w.get('volume_usdc',0):,.0f}  inv {a.get('inventory_events')}")
    for f in d['by_family'][:6]:
        print(f"    {f['family']:<14} mk {f['markets']:>5} res {f['resolved_complete']:>4} turn {f['turnover']:>9,.0f} taker {(f['taker_share'] or 0):.2f} net {(f['net'] or 0):>9,.0f} ({f['net_pct_turnover']}%) t {f['t_by_market']}")
    ev = collections.Counter(); evn = collections.Counter()
    for m in d['_markets']:
        if m['family'] != 'politics': continue
        k = re.sub(r'\d+', '#', m['slug'] or '')[:60]
        ev[k] += m['turnover']; evn[k] += 1
    print('    top politics slug patterns:', '; '.join(f"{k} [{evn[k]}m ${v:,.0f}]" for k, v in ev.most_common(7)))
