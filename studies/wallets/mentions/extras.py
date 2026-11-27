"""Variant 2c: holding period, peak capital, clean-jump reaction lags, hour-of-day regularity, per-month mention PnL from deep_<label>.json."""
import json, sys, os, statistics as st, collections, datetime as dt
D = os.path.dirname(os.path.abspath(__file__))
for label in sys.argv[1:]:
    d = json.load(open(f"{D}/deep_{label}.json"))
    S = d['stories']
    hold, ev, lags, px, clean, by_week = [], [], [], [], 0, collections.defaultdict(float)
    mk_week = collections.defaultdict(int)
    for s in S:
        net_sh = collections.defaultdict(float); cost = 0.0
        for f in s['fills']:
            usd = f['p'] * f['s']
            if f['side'] == 'BUY':
                ev.append((f['t'], usd)); cost += usd
                if s['closed']: hold.append((s['closed'] - f['t']) / 3600 * usd)
            else:
                ev.append((f['t'], -usd)); cost -= usd
        if s['closed']: ev.append((s['closed'], -max(cost, 0)))
        wk = dt.datetime.fromtimestamp(s['fills'][0]['t'], dt.timezone.utc).strftime('%G-W%V')
        by_week[wk] += s['pnl']; mk_week[wk] += 1
        if s['final_yes'] >= 0.5 and s['first_move'] and s['tpre'] and s['first_move'] - s['tpre'] <= 1800 and (not s['start'] or s['first_move'] >= s['start']):
            clean += 1
            ly = [f for f in s['fills'] if ((f['side'] == 'BUY') == (f['o'] == 'Yes')) and f['t'] >= s['first_move'] - 5]
            if ly:
                lags.append(ly[0]['t'] - s['first_move']); px.append(ly[0]['p'] if ly[0]['o'] == 'Yes' else 1 - ly[0]['p'])
    ev.sort(); cur = peak = 0.0
    for t, x in ev:
        cur += x; peak = max(peak, cur)
    buy_usd = sum(x for _, x in ev if x > 0)
    tot_hold = sum(hold)
    def share(lo, hi): return sum(1 for l in lags if lo <= l < hi)
    print(f"== {label}: usd-weighted mean hours from buy to resolution {tot_hold/max(buy_usd,1):.1f}; peak capital tied in mention markets ~${peak:.0f}; buys ${buy_usd:.0f} -> turns capital {buy_usd/max(peak,1):.1f}x in {d['days']}d")
    print(f"   clean live jumps traded {clean}; first long-Yes fill lag vs first print: <=2s {share(-5,3)}, 3-10s {share(3,11)}, 11-60s {share(11,61)}, 1-10min {share(61,601)}, >10min {share(601,10**9)}; median price paid {st.median(px) if px else None}")
    print("   weekly mention pnl:", {k: (round(v), mk_week[k]) for k, v in sorted(by_week.items())}, f"positive weeks {sum(1 for v in by_week.values() if v>0)}/{len(by_week)}")
    hrs = collections.Counter(dt.datetime.fromtimestamp(f['t'], dt.timezone.utc).hour for s in S for f in s['fills'])
    print("   fills by UTC hour:", [hrs.get(h, 0) for h in range(24)])
