"""Per-market stories for one account: rules, when the market 'knew', when the account traded, at what price,
where the price went, the outcome.  Read-only, public data.

  python3 story.py <name|0x..> --days 60 --match '<regex on slug>' --tag out_name [--max-markets 150]

For every market (condition) the account traded in the window and whose slug matches:
  yes-price tape  = whole market tape, every fill converted to the price of the first outcome ("Yes")
  T90 / T99       = first tape time after which EVERY later trade is on the final side of 0.90 / 0.99 (0.10 / 0.01)
                    -> a market-implied proxy for "the deciding information is public and absorbed"
  per fill        = pnl to final (resolved) or to last tape price (unresolved, flagged), taker fee 0.01*p*(1-p)*shares
                    at culture/other 1% markets (rate from pmlab.fees.market_rate, fallback 0.01), drift +1h and +24h
"""
import argparse, bisect, collections, datetime as dt, json, re, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from pmlab import dataapi, gamma, wallet as W, fees

def iso(t): return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime('%m-%d %H:%M') if t else '-'

def tape(cond, max_rows=40000):
    rows = []
    for r in dataapi.iter_trades(condition=cond, max_rows=max_rows):
        rows.append((int(r['timestamp']), r.get('outcome'), float(r['price']), float(r['size']), r.get('token_id')))
    rows.sort()
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ref'); ap.add_argument('--days', type=float, default=60); ap.add_argument('--match', default='.')
    ap.add_argument('--tag', required=True); ap.add_argument('--max-markets', type=int, default=150)
    ap.add_argument('--max-fills', type=int, default=60000)
    a = ap.parse_args()
    name, wal = gamma.resolve_profile(a.ref)
    end = int(time.time()); start = int(end - a.days * 86400)
    fills, trunc = W.fetch_fills(wal, start, end, a.max_fills)
    rx = re.compile(a.match)
    fills = [f for f in fills if rx.search(f.get('slug') or '')]
    by = collections.defaultdict(list)
    for f in fills: by[f['condition_id']].append(f)
    conds = sorted(by, key=lambda c: -sum(float(f['size']) * float(f['price']) for f in by[c]))[:a.max_markets]
    print(f'{name} {wal} window {iso(start)}..{iso(end)} truncated={trunc} matching fills {len(fills)} markets {len(by)} (using {len(conds)})')
    meta = gamma.markets_by_condition(conds)
    res = dataapi.resolutions(conds)
    with ThreadPoolExecutor(4) as ex: tapes = dict(zip(conds, ex.map(tape, conds)))
    out = []
    for c in conds:
        md = meta.get(c) or {}; rs = res.get(c) or {}; tp = tapes[c]
        outs = gamma.jfield(md.get('outcomes')) or list((rs.get('final') or {}).keys()) or ['Yes', 'No']
        first = outs[0]
        yp = [(t, p if o == first else 1 - p) for t, o, p, s, _ in tp]
        ts_list = [t for t, _ in yp]
        final = (rs.get('final') or {}).get(first) if rs.get('resolved') else None
        mark = final if final is not None else (yp[-1][1] if yp else None)
        def t_cross(th):
            if final is None or not yp: return None
            ok = (lambda p: p >= th) if final >= 0.5 else (lambda p: p <= 1 - th)
            i = len(yp)
            while i > 0 and ok(yp[i - 1][1]): i -= 1
            return yp[i][0] if i < len(yp) else None
        t90, t99 = t_cross(0.90), t_cross(0.99)
        def px_at(t):
            i = bisect.bisect_right(ts_list, t) - 1
            return yp[i][1] if i >= 0 else None
        endt = W._ts(md.get('endDate')); closed = W._ts(md.get('closedTime'))
        rate = fees.market_rate(md) if md else None
        if rate is None: rate = 0.01
        rows = []; pos = collections.Counter()
        for f in sorted(by[c], key=lambda f: f['timestamp']):
            t = int(f['timestamp']); p = float(f['price']); s = float(f['size']); o = f['outcome']; buy = f['side'] == 'BUY'
            py = p if o == first else 1 - p
            sign = (1 if o == first else -1) * (1 if buy else -1)       # +1 = long the first outcome
            fee = rate * p * (1 - p) * s if f['role'] == 'T' else 0.0
            pnl = sign * s * (mark - py) - fee if mark is not None else None
            p1, p24 = px_at(t + 3600), px_at(t + 86400)
            pos[o] += s if buy else -s
            rows.append(dict(t=t, role=f['role'], side=f['side'], outcome=o, p=p, size=s, usd=p * s, py=py, sign=sign, fee=fee, pnl=pnl,
                             d1=sign * (p1 - py) if p1 is not None else None, d24=sign * (p24 - py) if p24 is not None else None,
                             after90=(t90 is not None and t >= t90), after99=(t99 is not None and t >= t99),
                             h_to_end=(endt - t) / 3600 if endt else None, h_to_t90=(t90 - t) / 3600 if t90 else None))
        buy_usd = sum(r['usd'] for r in rows if r['side'] == 'BUY'); sell_usd = sum(r['usd'] for r in rows if r['side'] == 'SELL')
        out.append(dict(cond=c, slug=md.get('slug') or by[c][0].get('slug'), q=md.get('question'), end=endt, closed=closed, first=first,
                        final=final, mark=mark, resolved=final is not None, t90=t90, t99=t99, tape_n=len(tp), tape_first=ts_list[0] if tp else None,
                        vol=md.get('volumeNum'), neg=md.get('negRisk'), rate=rate, desc=(md.get('description') or '')[:600],
                        res_src=md.get('resolutionSource'), fills=rows, buy_usd=buy_usd, sell_usd=sell_usd,
                        net_pos={k: round(v, 2) for k, v in pos.items()},
                        pnl=sum(r['pnl'] for r in rows if r['pnl'] is not None), fee=sum(r['fee'] for r in rows)))
    json.dump(dict(name=name, wallet=wal, start=start, end=end, markets=out), open(f'{a.tag}.story.json', 'w'))
    # ---- text report
    L = []
    for m in sorted(out, key=lambda m: m['fills'][0]['t']):
        fr = m['fills']; w = sum(r['usd'] for r in fr) or 1
        avg_py = sum(r['py'] * r['usd'] for r in fr) / w
        L.append(f"{(m['slug'] or '')[:62]:62} fin {('%.0f' % m['final']) if m['resolved'] else 'open'} n {len(fr):3} "
                 f"M% {100 * sum(r['usd'] for r in fr if r['role'] == 'M') / w:3.0f} buy {m['buy_usd']:7.0f} sell {m['sell_usd']:6.0f} "
                 f"pyAvg {avg_py:.2f} first {iso(fr[0]['t'])} last {iso(fr[-1]['t'])} end {iso(m['end'])} T90 {iso(m['t90'])} T99 {iso(m['t99'])} "
                 f"closed {iso(m['closed'])} pnl {m['pnl']:8.0f}")
    def agg(label, sel):
        rs = [(m, r) for m in out for r in m['fills'] if r['pnl'] is not None and m['resolved'] and sel(m, r)]
        if not rs: return f'{label:38} -'
        usd = sum(r['usd'] for _, r in rs); pnl = sum(r['pnl'] for _, r in rs); mk = len({m['cond'] for m, _ in rs})
        d1 = [r['d1'] * r['size'] for _, r in rs if r['d1'] is not None]; sh = sum(r['size'] for _, r in rs)
        return f"{label:38} fills {len(rs):5} mkts {mk:4} usd {usd:9.0f} pnl {pnl:9.0f} ({100 * pnl / usd:6.1f}% of usd) drift1h {100 * sum(d1) / sh:6.2f}c/sh"
    S = ['', 'RESOLVED markets only, pnl to final after est. taker fees:']
    S.append(agg('all', lambda m, r: True))
    S.append(agg('before T90', lambda m, r: not r['after90']))
    S.append(agg('after T90, before T99', lambda m, r: r['after90'] and not r['after99']))
    S.append(agg('after T99', lambda m, r: r['after99']))
    for ro in 'MT':
        for sd in ('BUY', 'SELL'):
            S.append(agg(f'role {ro} {sd}', lambda m, r, ro=ro, sd=sd: r['role'] == ro and r['side'] == sd))
    for lo, hi in ((0, .05), (.05, .2), (.2, .4), (.4, .6), (.6, .8), (.8, .95), (.95, .99), (.99, 1.01)):
        S.append(agg(f'fill price {lo:.2f}-{hi:.2f}', lambda m, r, lo=lo, hi=hi: lo <= r['p'] < hi))
    for lab, lo, hi in (('>7d to end', 168, 1e9), ('2-7d', 48, 168), ('1-2d', 24, 48), ('6-24h', 6, 24), ('0-6h', 0, 6), ('after end', -1e9, 0)):
        S.append(agg(f'time to end {lab}', lambda m, r, lo=lo, hi=hi: r['h_to_end'] is not None and lo <= r['h_to_end'] < hi))
    res = [m for m in out if m['resolved']]
    wins = sum(1 for m in res if m['pnl'] > 0)
    S.append(f"markets resolved {len(res)} winners {wins} total pnl {sum(m['pnl'] for m in res):.0f}; unresolved {len(out) - len(res)} mark-to-tape pnl {sum(m['pnl'] for m in out if not m['resolved']):.0f}")
    held = [m for m in res if m['buy_usd'] > 0]
    S.append(f"sell/buy usd ratio (exit vs hold): {sum(m['sell_usd'] for m in held) / max(1, sum(m['buy_usd'] for m in held)):.2f}; median market buy usd {sorted(m['buy_usd'] for m in out)[len(out) // 2]:.0f}")
    hw = collections.Counter(dt.datetime.fromtimestamp(r['t'], dt.timezone.utc).strftime('%a %H') for m in out for r in m['fills'])
    S.append('fills by weekday+hour UTC (top 14): ' + ', '.join(f'{k}:{v}' for k, v in hw.most_common(14)))
    days = collections.defaultdict(set)
    for m in out:
        for r in m['fills']: days[r['t'] // 86400].add(m['cond'])
    dd = sorted(len(v) for v in days.values())
    S.append(f'active days {len(dd)}; markets traded per active day median {dd[len(dd) // 2]} max {dd[-1]}')
    open(f'{a.tag}.story.txt', 'w').write('\n'.join(L + S) + '\n')
    print('\n'.join(S)); print(f'markets table -> {a.tag}.story.txt')
main()
