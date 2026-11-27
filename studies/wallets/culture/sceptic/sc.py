"""Sceptic's re-run for the culture wallet study (protocol.md in this folder). Read-only, public data.

  python3 sc.py <label> <0xwallet> <tag> <t0> <t1> '<slug regex>' [--tapes]

Per-market PnL to final after the fee actually charged (activity TRADE rows: usdc_size - shares*price), events,
concentration, price x token table, T90 split, weekend phases, fade/follow on independent prints (--tapes).
Writes s_<label>_<tag>.json (per-market rows) next to this file."""
import sys, os, json, re, gzip, bisect, collections, statistics as st, datetime as dt
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, '/home/user/polymarket-lab')
from pmlab import gamma, dataapi, wallet as W

D = os.path.dirname(os.path.abspath(__file__))
TAPES = '/home/user/polymarket-lab/data/culture_tapes'
os.makedirs(TAPES, exist_ok=True)
EDGES = [(0, 'to 19 Oct'), (1792454400, '20-31 Oct'), (1793491200, '1-20 Nov'), (1795219200, 'from 21 Nov')]  # 20 Oct, 1 Nov, 21 Nov 00:00 UTC


def period(t):
    lab = EDGES[0][1]
    for e, l in EDGES:
        if t >= e: lab = l
    return lab


def iso(t): return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime('%m-%d %a %H:%M') if t else '-'


def tstat(v):
    v = list(v)
    if len(v) < 3 or st.stdev(v) == 0: return float('nan')
    return st.mean(v) / (st.stdev(v) / len(v) ** .5)


def tape(cond, closed=True):
    p = f"{TAPES}/{cond}.json.gz"
    if os.path.exists(p): return json.load(gzip.open(p, 'rt'))
    rows = [dict(t=int(r['timestamp']), w=r.get('proxy_wallet'), o=r.get('outcome'), p=float(r['price']), s=float(r['size']), side=r.get('side'), tx=r.get('transaction_hash'))
            for r in dataapi.iter_trades(condition=cond, max_rows=60000)]
    rows.sort(key=lambda r: r['t'])
    if closed: json.dump(rows, gzip.open(p, 'wt'))
    return rows


def cached(path, fn):
    if os.path.exists(path): return json.load(open(path))
    v = fn(); json.dump(v, open(path, 'w')); return v


def main():
    label, wal, tag, t0, t1, rx = sys.argv[1], sys.argv[2].lower(), sys.argv[3], int(sys.argv[4]), int(sys.argv[5]), re.compile(sys.argv[6])
    want_tapes = '--tapes' in sys.argv
    fills, trunc = cached(f"{D}/_fills_{label}_{tag}.json", lambda: list(W.fetch_fills(wal, t0, t1, 150000)))
    act = cached(f"{D}/_act_{label}_{tag}.json", lambda: list(dataapi.iter_activity(wal, start=t0, end=t1, max_rows=200000)))
    print(f"== {label} {wal} {tag} {iso(t0)} .. {iso(t1)}  fills {len(fills)} truncated={trunc}  activity rows {len(act)}")
    ty = collections.defaultdict(lambda: [0, 0.0])
    for a in act:
        ty[a['type']][0] += 1; ty[a['type']][1] += float(a.get('usdc_size') or 0)
    print('activity by type (n, usdc):', {k: (v[0], round(v[1])) for k, v in ty.items()})
    # ---- fee actually charged, from activity TRADE rows
    actfee = collections.defaultdict(list)
    for a in act:
        if a['type'] != 'TRADE': continue
        s, p, u = float(a['size']), float(a['price']), float(a['usdc_size'])
        diff = (u - s * p) if a['side'] == 'BUY' else (s * p - u)
        actfee[(a['transaction_hash'], a['token_id'], a['side'], round(s, 4))].append(diff)
    matched = 0
    for f in fills:
        f['price'] = float(f['price']); f['size'] = float(f['size']); f['timestamp'] = int(f['timestamp'])
        k = (f['transaction_hash'], f['token_id'], f['side'], round(f['size'], 4))
        f['fee_act'] = actfee[k].pop() if actfee.get(k) else None
        matched += f['fee_act'] is not None
    print(f"fills joined to an activity TRADE row: {matched} of {len(fills)}")
    per = collections.defaultdict(lambda: [0.0, 0.0, 0, 0])
    for f in fills:
        if f['role'] != 'T' or f['fee_act'] is None or not rx.search(f.get('slug') or ''): continue
        b = per[period(f['timestamp'])]; b[0] += f['fee_act']; b[1] += f['size'] * f['price'] * (1 - f['price']); b[2] += 1; b[3] += abs(f['fee_act']) < 1e-4
    rate = {}
    for k, b in per.items():
        rate[k] = b[0] / b[1] if b[1] else None
        print(f"  fee charged on matching taker fills, {k:12}: n {b[2]:5} zero-fee fills {b[3]:5} charged {b[0]:9.2f} implied rate {rate[k]:.4f}")
    mk = [f for f in fills if not rx.search(f.get('slug') or '')]
    print(f"fills matching the regex: {len(fills) - len(mk)}; not matching: {len(mk)} (usd {sum(f['size'] * f['price'] for f in mk):.0f})")
    other = collections.Counter()
    for f in mk: other[re.sub(r'\d+', '#', f.get('event_slug') or f.get('slug') or '')[:50]] += f['size'] * f['price']
    print('  largest non-matching event stems:', [(k, round(v)) for k, v in other.most_common(8)])
    fills = [f for f in fills if rx.search(f.get('slug') or '')]
    by = collections.defaultdict(list)
    for f in fills: by[f['condition_id']].append(f)
    conds = list(by)
    meta = gamma.markets_by_condition(conds); res = dataapi.resolutions(conds)
    convc = {a['condition_id'] for a in act if a['type'] == 'CONVERSION'}
    conve = {a.get('event_slug') for a in act if a['type'] == 'CONVERSION'}
    tapes = {}
    if want_tapes:
        with ThreadPoolExecutor(4) as ex:
            tapes = dict(zip(conds, ex.map(lambda c: tape(c, bool((res.get(c) or {}).get('resolved'))), conds)))
    out = []
    for c in conds:
        md = meta.get(c) or {}; rs = res.get(c) or {}
        outs = gamma.jfield(md.get('outcomes')) or list((rs.get('final') or {}).keys()) or ['Yes', 'No']
        first = outs[0]
        final = (rs.get('final') or {}).get(first) if rs.get('resolved') else None
        endt = W._ts(md.get('endDate'))
        own = {f['transaction_hash'] for f in by[c]}
        tp = tapes.get(c) or []
        yp = [(r['t'], r['p'] if r['o'] == first else 1 - r['p']) for r in tp]
        ind = [(r['t'], r['p'] if r['o'] == first else 1 - r['p']) for r in tp if r['tx'] not in own]
        its = [t for t, _ in ind]
        t90 = None
        if final is not None and yp:
            ok = (lambda p: p >= .9) if final >= .5 else (lambda p: p <= .1)
            i = len(yp)
            while i > 0 and ok(yp[i - 1][1]): i -= 1
            t90 = yp[i][0] if i < len(yp) else None
        def ipx(t):
            i = bisect.bisect_left(its, t) - 1
            return ind[i][1] if i >= 0 else None
        rows = []
        for f in sorted(by[c], key=lambda f: f['timestamp']):
            t, p, s, o, buy = f['timestamp'], f['price'], f['size'], f['outcome'], f['side'] == 'BUY'
            py = p if o == first else 1 - p
            sign = (1 if o == first else -1) * (1 if buy else -1)
            if f['fee_act'] is not None: fee = max(0.0, f['fee_act'])
            else: fee = (rate.get(period(t)) or 0.01) * p * (1 - p) * s if f['role'] == 'T' else 0.0
            pnl = sign * s * (final - py) - fee if final is not None else None
            mv = None
            if want_tapes:
                a, b = ipx(t - 7200), ipx(t)
                if a is not None and b is not None: mv = sign * (b - a)
            a10 = None
            if want_tapes:
                j = bisect.bisect_right(its, t + 600) - 1
                if j >= 0 and its[j] > t: a10 = sign * (ind[j][1] - py)
            rows.append(dict(t=t, role=f['role'], side=f['side'], o=o, p=p, s=s, usd=p * s, py=py, sign=sign, fee=fee, pnl=pnl, mv=mv, a10=a10,
                             after90=(t90 is not None and t >= t90), h_end=(endt - t) / 3600 if endt else None))
        out.append(dict(cond=c, slug=md.get('slug') or by[c][0].get('slug'), event=by[c][0].get('event_slug') or '', end=endt, first=first, final=final,
                        t90=t90, vol=md.get('volumeNum'), neg=md.get('negRisk'), conv=(c in convc or by[c][0].get('event_slug') in conve), fills=rows,
                        pnl=sum(r['pnl'] for r in rows) if final is not None else None, usd=sum(r['usd'] for r in rows),
                        buy=sum(r['usd'] for r in rows if r['side'] == 'BUY'), fee=sum(r['fee'] for r in rows)))
    json.dump(dict(label=label, wallet=wal, t0=t0, t1=t1, rate=rate, markets=out), open(f"{D}/s_{label}_{tag}.json", 'w'))
    R = [m for m in out if m['final'] is not None]
    print(f"markets {len(out)} resolved {len(R)} unresolved {len(out) - len(R)}; in events with a CONVERSION by this wallet: {sum(1 for m in out if m['conv'])}; negRisk {sum(1 for m in out if m['neg'])}")
    def summary(name, ms):
        ev = collections.defaultdict(float)
        for m in ms: ev[m['event']] += m['pnl']
        pn = sum(m['pnl'] for m in ms); usd = sum(m['usd'] for m in ms) or 1; e = list(ev.values())
        print(f"  {name:34} mkts {len(ms):4} win {sum(1 for m in ms if m['pnl'] > 0):4} events {len(e):3} win {sum(1 for x in e if x > 0):3} usd {usd:9.0f} pnl {pn:9.0f} ({100 * pn / usd:5.1f}%) fee {sum(m['fee'] for m in ms):7.0f} "
              f"t_event {tstat(e):5.2f} t_mkt {tstat([m['pnl'] for m in ms]):5.2f} worst ev {min(e) if e else 0:7.0f} best ev {max(e) if e else 0:7.0f}")
        return ev
    print('T1/T2 resolved markets, pnl to final after fee:')
    ev = summary('all', R)
    top3 = sorted(R, key=lambda m: -m['pnl'])[:3]
    print('   top 3 markets:', [(m['slug'][-45:], round(m['pnl'])) for m in top3])
    summary('without top 3 markets', [m for m in R if m not in top3])
    te = sorted(ev, key=lambda k: -ev[k])[:3]
    print('   top 3 events:', [(k[-45:], round(ev[k])) for k in te])
    summary('without top 3 events', [m for m in R if m['event'] not in te])
    summary('markets without own conversions', [m for m in R if not m['conv']])
    half = (t0 + t1) / 2
    summary('first half (by first fill)', [m for m in R if m['fills'][0]['t'] < half]); summary('second half', [m for m in R if m['fills'][0]['t'] >= half])
    def agg(name, sel):
        rs = [(m, r) for m in R for r in m['fills'] if sel(m, r)]
        if not rs: print(f"  {name:38} -"); return
        usd = sum(r['usd'] for _, r in rs); pn = sum(r['pnl'] for _, r in rs); bym = collections.defaultdict(float)
        for m, r in rs: bym[m['cond']] += r['pnl']
        won = sum(r['usd'] for m, r in rs if r['pnl'] > 0)
        print(f"  {name:38} fills {len(rs):5} mkts {len(bym):4} losing mkts {sum(1 for x in bym.values() if x < 0):3} usd {usd:9.0f} pnl {pn:9.0f} ({100 * pn / usd:6.1f}%) usd on winning side {100 * won / usd:3.0f}% t_mkt {tstat(bym.values()):5.2f}")
    print('by role/side:')
    for ro in 'TM':
        for sd in ('BUY', 'SELL'): agg(f'{ro} {sd}', lambda m, r, ro=ro, sd=sd: r['role'] == ro and r['side'] == sd)
    print('BUY fills by token and price paid (b):')
    for o in ('Yes', 'No'):
        for lo, hi in ((0, .1), (.1, .3), (.3, .6), (.6, .9), (.9, .995), (.995, 1.01)):
            agg(f'buy {o} at {lo:.2f}-{hi:.3f}', lambda m, r, o=o, lo=lo, hi=hi: r['side'] == 'BUY' and r['o'] == o and lo <= r['p'] < hi)
    print('SELL fills by price:')
    for lo, hi in ((0, .1), (.1, .9), (.9, .995), (.995, 1.01)):
        agg(f'sell at {lo:.2f}-{hi:.3f}', lambda m, r, lo=lo, hi=hi: r['side'] == 'SELL' and lo <= r['p'] < hi)
    print('time to gamma endDate:')
    for lab, lo, hi in (('>7d', 168, 1e9), ('2-7d', 48, 168), ('1-2d', 24, 48), ('6-24h', 6, 24), ('0-6h', 0, 6), ('after end', -1e9, 0)):
        agg(f'to end {lab}', lambda m, r, lo=lo, hi=hi: r['h_end'] is not None and lo <= r['h_end'] < hi)
    print('weekend phases (markets ending Sunday 12:00 UTC; fills priced 0.03-0.97):')
    def wk(m): return m['end'] and dt.datetime.fromtimestamp(m['end'], dt.timezone.utc).strftime('%a %H') == 'Sun 12'
    for lab, lo, hi in (('A before Fri 14 UTC', 46, 1e9), ('B Fri 14 - Sat 14', 22, 46), ('C Sat 14 - Sun 15', -3, 22), ('D Sun 15 - Mon 20', -32, -3), ('E after Mon 20', -1e9, -32)):
        agg(lab, lambda m, r, lo=lo, hi=hi: wk(m) and .03 <= r['p'] <= .97 and lo < r['h_end'] <= hi)
    if want_tapes:
        print('T90 split (tape):')
        agg('before T90', lambda m, r: not r['after90']); agg('after T90', lambda m, r: r['after90'])
        print('T3a taker BUY fills priced 0.03-0.97, independent price move over the prior 2 h, signed its way:')
        base = lambda m, r: r['role'] == 'T' and r['side'] == 'BUY' and .03 <= r['p'] <= .97
        agg('FOLLOW (>= +10 c)', lambda m, r: base(m, r) and r['mv'] is not None and r['mv'] >= .10)
        agg('FADE (<= -10 c)', lambda m, r: base(m, r) and r['mv'] is not None and r['mv'] <= -.10)
        agg('QUIET (|move| < 10 c)', lambda m, r: base(m, r) and r['mv'] is not None and abs(r['mv']) < .10)
        agg('no independent print 2 h before', lambda m, r: base(m, r) and r['mv'] is None)
        x = [(r['a10'], r['s']) for m in R for r in m['fills'] if base(m, r) and r['a10'] is not None]
        if x: print(f"  independent price 10 min after taker buys minus price paid: {100 * sum(a * s for a, s in x) / sum(s for _, s in x):.2f} c/share over {len(x)} fills; no independent print in 10 min: {sum(1 for m in R for r in m['fills'] if base(m, r) and r['a10'] is None)}")
    try:
        aw = W.api_window(wal, t0, t1)
        print('API over the window:', {k: round(v) for k, v in aw.items() if k in ('trade_pnl', 'fees', 'taker_rebate', 'maker_rebate', 'reward_income', 'economic_pnl', 'volume_usdc')})
    except Exception as e:
        print('api_window failed', e)


main()
