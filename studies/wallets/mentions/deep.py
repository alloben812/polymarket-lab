"""Variant 2: per-account anatomy of mention-market trading over a 45-day window.
usage: python3 deep.py <label> <0xwallet> [days]
Writes deep_<label>.json (tables + per-market stories) and prints a text report."""
import sys, os, json, re, time, gzip, statistics as st, collections, datetime as dt
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, '/home/user/polymarket-lab')
from pmlab import gamma, dataapi, wallet as W

D = os.path.dirname(os.path.abspath(__file__))
TAPES = '/home/user/polymarket-lab/data/mentions_tapes'
os.makedirs(TAPES, exist_ok=True)
PAT = re.compile(r"(^|-)(say|says|said|mention|mentions|mentioned)(-|$)")
NOW = 1795794000  # 2026-11-27 ~15:40 UTC, fixed so reruns see the same window
RATE = 0.01

def is_mention(md, slug):
    return any('mention' in t for t in gamma.tag_slugs(md or {})) or bool(PAT.search(slug or ''))

def tape(cond, closed):
    p = f"{TAPES}/{cond}.json.gz"
    if os.path.exists(p):
        return json.load(gzip.open(p, 'rt'))
    rows = [dict(t=r['timestamp'], w=r['proxy_wallet'], side=r['side'], o=r['outcome'], p=float(r['price']), s=float(r['size']))
            for r in dataapi.iter_trades(condition=cond)]
    rows.sort(key=lambda r: r['t'])
    if closed:
        json.dump(rows, gzip.open(p, 'wt'))
    return rows

def yes(r):
    return r['p'] if r['o'] == 'Yes' else 1 - r['p']

def det_times(rows, final_yes):
    ys = [yes(r) for r in rows]
    n = len(ys)
    if n == 0 or final_yes is None:
        return None, None
    if final_yes >= 0.5:
        sufmin = [0] * (n + 1); sufmin[n] = 9
        for i in range(n - 1, -1, -1): sufmin[i] = min(ys[i], sufmin[i + 1])
        for i in range(n):
            if ys[i] >= 0.90 and sufmin[i] >= 0.70:
                pre = None
                for j in range(i - 1, -1, -1):
                    if ys[j] < 0.60: pre = rows[j]['t']; break
                return pre, rows[i]['t']
    else:
        sufmax = [0] * (n + 1); sufmax[n] = -9
        for i in range(n - 1, -1, -1): sufmax[i] = max(ys[i], sufmax[i + 1])
        for i in range(n):
            if ys[i] <= 0.10 and sufmax[i] <= 0.30:
                return None, rows[i]['t']
    return None, None

def ts(v): return W._ts(v)
def iso(t): return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime('%m-%d %H:%M:%S') if t else '-'

def bucket(p):
    for hi, name in [(0.05, '0-.05'), (0.2, '.05-.2'), (0.5, '.2-.5'), (0.8, '.5-.8'), (0.95, '.8-.95'), (0.99, '.95-.99'), (1.01, '.99-1')]:
        if p < hi: return name

def main():
    label, wal = sys.argv[1], sys.argv[2]
    days = int(sys.argv[3]) if len(sys.argv) > 3 else 45
    fp = f"{D}/_fills_{label}_{days}.json"
    if os.path.exists(fp):
        fills, trunc = json.load(open(fp))
    else:
        fills, trunc = W.fetch_fills(wal, NOW - days * 86400, NOW, 120000)
        json.dump([fills, trunc], open(fp, 'w'))
    conds = sorted({f['condition_id'] for f in fills})
    meta = gamma.markets_by_condition(conds)
    mconds = [c for c in conds if is_mention(meta.get(c), next(f['slug'] for f in fills if f['condition_id'] == c))]
    res = dataapi.resolutions(mconds, cache=False)
    allusd = sum(f['size'] * f['price'] for f in fills)
    mf = [f for f in fills if f['condition_id'] in set(mconds)]
    musd = sum(f['size'] * f['price'] for f in mf)
    print(f"== {label} {wal} window {days}d truncated={trunc} fills={len(fills)} usd={allusd:.0f} | mention fills={len(mf)} markets={len(mconds)} usd={musd:.0f} ({100*musd/max(allusd,1):.0f}% of turnover)")
    closed = {c: bool((meta.get(c) or {}).get('closed')) for c in mconds}
    with ThreadPoolExecutor(5) as ex:
        tapes = dict(zip(mconds, ex.map(lambda c: tape(c, closed[c]), mconds)))
    byc = collections.defaultdict(list)
    for f in mf: byc[f['condition_id']].append(f)
    agg = collections.defaultdict(lambda: dict(fills=0, usd=0.0, pnl=0.0, mk=set(), win_mk=collections.defaultdict(float)))
    def add(key, f, pnl, c):
        a = agg[key]; a['fills'] += 1; a['usd'] += f['size'] * f['price']; a['pnl'] += pnl; a['mk'].add(c); a['win_mk'][c] += pnl
    stories, jump_stats, ev_pnl, mk_pnl = [], [], collections.defaultdict(float), {}
    unresolved = 0
    held_sh = sold_sh = bought_sh = 0.0
    day_mk = collections.defaultdict(set)
    late_buy = collections.defaultdict(float)
    for c in mconds:
        md = meta.get(c) or {}
        r = res.get(c) or {}
        fin = (r.get('final') or {})
        fy = fin.get('Yes')
        ev = (md.get('events') or [{}])[0]
        start = ts(ev.get('startTime')) or ts(md.get('eventStartTime')) or ts(md.get('gameStartTime'))
        closed_at = ts(md.get('closedTime'))
        rows = tapes[c]
        if not r.get('resolved') or fy is None:
            unresolved += 1
            continue
        tpre, tdet = det_times(rows, fy)
        first_move = None
        if fy >= 0.5 and tdet:
            for x in rows:
                if (tpre is None or x['t'] > tpre) and yes(x) >= 0.60: first_move = x['t']; break
        srows = []
        tot = 0.0
        for f in sorted(byc[c], key=lambda f: f['timestamp']):
            t, p, s = f['timestamp'], float(f['price']), float(f['size'])
            F = fin.get(f['outcome'])
            pnl = s * (F - p) if f['side'] == 'BUY' else s * (p - F)
            if f['role'] == 'T': pnl -= RATE * p * (1 - p) * s
            tot += pnl
            yp = p if f['outcome'] == 'Yes' else 1 - p
            # direction in Yes terms
            long_yes = (f['side'] == 'BUY') == (f['outcome'] == 'Yes')
            if fy >= 0.5:
                if tdet is None: ph = 'NODET'
                elif tpre is not None and t <= tpre: ph = 'PRE' if (start and t < start) else ('LIVE' if start else 'NOSTART')
                elif tpre is None and t < tdet and start and t < start: ph = 'PRE'
                elif t <= tdet + 60: ph = 'JUMP'
                else: ph = 'POST'
            else:
                if tdet is None: ph = 'NODET'
                elif t >= tdet: ph = 'POST'
                elif start and t < start: ph = 'PRE'
                elif start: ph = 'LIVE'
                else: ph = 'NOSTART'
            add(('phase', ph), f, pnl, c)
            add(('phase_role_dir', ph, f['role'], 'longYes' if long_yes else 'longNo'), f, pnl, c)
            add(('role_side', f['role'], f['side']), f, pnl, c)
            win_side_px = yp if fy >= 0.5 else 1 - yp   # price of the eventually-winning outcome at this fill
            on_winner = long_yes == (fy >= 0.5)
            add(('winner_px', 'onWinner' if on_winner else 'onLoser', bucket(win_side_px)), f, pnl, c)
            if f['side'] == 'BUY' and p >= 0.95: late_buy[ph] += p * s
            if f['side'] == 'BUY': bought_sh += s
            else: sold_sh += s
            day_mk[t // 86400].add(c)
            srows.append(dict(t=t, rel_start=(t - start) if start else None, rel_det=(t - tdet) if tdet else None, role=f['role'], side=f['side'], o=f['outcome'], p=round(p, 4), s=round(s, 1), ph=ph, pnl=round(pnl, 2)))
            if fy >= 0.5 and ph == 'JUMP' and first_move:
                rank = len([x for x in rows if (tpre is None or x['t'] > tpre) and x['t'] < t])
                jump_stats.append(dict(c=c, slug=md.get('slug'), lag=t - first_move, rank=rank, role=f['role'], long_yes=long_yes, yp=round(yp, 3), usd=round(p * s, 1), pnl=round(pnl, 2), jump_len=tdet - (tpre or first_move)))
        mk_pnl[c] = tot
        ev_pnl[ev.get('slug') or md.get('slug')] += tot
        stories.append(dict(c=c, q=md.get('question'), event=ev.get('slug'), tags=gamma.tag_slugs(md), start=start, tpre=tpre, tdet=tdet, first_move=first_move, closed=closed_at, final_yes=fy,
                            vol=md.get('volumeNum'), n_tape=len(rows), pnl=round(tot, 2), usd=round(sum(x['p'] * x['s'] for x in srows), 1), fills=srows, rules=(md.get('description') or '')[:400]))
    def show(prefix):
        rows = [(k, a) for k, a in agg.items() if k[0] == prefix]
        rows.sort(key=lambda x: str(x[0]))
        for k, a in rows:
            wins = sum(1 for v in a['win_mk'].values() if v > 0)
            print(f"  {str(k[1:]):42s} fills={a['fills']:5d} mk={len(a['mk']):4d} usd={a['usd']:9.0f} pnl={a['pnl']:9.1f} ({100*a['pnl']/max(a['usd'],1):6.1f}% of usd) mk_win={wins}/{len(a['mk'])}")
    nres = len(mk_pnl)
    wins = sum(1 for v in mk_pnl.values() if v > 0)
    tot = sum(mk_pnl.values())
    vals = list(mk_pnl.values())
    se = (st.pstdev(vals) * len(vals) ** 0.5) if len(vals) > 1 else 0
    print(f"resolved mention markets={nres} unresolved={unresolved} | net after fee ${tot:.0f} | market win rate {wins}/{nres} | t(by market)={tot/se if se else 0:.2f} | events={len(ev_pnl)} positive events={sum(1 for v in ev_pnl.values() if v>0)}")
    usd_mk = [s['usd'] for s in stories]
    if usd_mk:
        print(f"sizing: median ${st.median(usd_mk):.0f}/market, p90 ${sorted(usd_mk)[int(.9*len(usd_mk))]:.0f}, max ${max(usd_mk):.0f}; max markets touched in one day {max(len(v) for v in day_mk.values())}; days active {len(day_mk)}; shares bought {bought_sh:.0f} sold {sold_sh:.0f} (sell/buy {sold_sh/max(bought_sh,1):.2f})")
    print("by phase:"); show('phase')
    print("by phase, role, direction:"); show('phase_role_dir')
    print("by role, side:"); show('role_side')
    print("by price of the eventual winner at fill time:"); show('winner_px')
    lb = sum(late_buy.values())
    print("buys at price>=0.95 by phase (usd):", {k: round(v) for k, v in late_buy.items()}, f"-> share in JUMP/POST = {100*(late_buy.get('JUMP',0)+late_buy.get('POST',0))/max(lb,1):.0f}%")
    yes_mk = [s for s in stories if s['final_yes'] >= 0.5 and s['tdet']]
    jm = {j['c'] for j in jump_stats if j['role'] == 'T' and j['long_yes'] and j['yp'] < 0.90}
    print(f"Yes-resolved markets traded={len(yes_mk)}; with a TAKER long-Yes fill inside the jump window at yes_px<0.90: {len(jm)} ({100*len(jm)/max(len(yes_mk),1):.0f}%)")
    if jump_stats:
        tj = [j for j in jump_stats if j['role'] == 'T' and j['long_yes']]
        if tj:
            lags = sorted(j['lag'] for j in tj)
            print(f"  taker long-Yes jump fills n={len(tj)} lag vs first print>=0.60: median {st.median(lags):.0f}s p25 {lags[len(lags)//4]}s p75 {lags[3*len(lags)//4]}s; median yes_px {st.median(j['yp'] for j in tj):.3f}; median tape rank {st.median(j['rank'] for j in tj):.0f}; pnl ${sum(j['pnl'] for j in tj):.0f}")
        mj = [j for j in jump_stats if j['role'] == 'M']
        if mj:
            print(f"  maker fills inside jump windows n={len(mj)} longYes={sum(1 for j in mj if j['long_yes'])} longNo(picked off)={sum(1 for j in mj if not j['long_yes'])} pnl ${sum(j['pnl'] for j in mj):.0f}")
    evs = sorted(ev_pnl.items(), key=lambda x: -abs(x[1]))[:12]
    print("largest events by |pnl|:", [(k[:48], round(v)) for k, v in evs])
    json.dump(dict(label=label, wallet=wal, days=days, truncated=trunc, n_fills=len(fills), usd_all=allusd, usd_mentions=musd, stories=stories, jump=jump_stats,
                   ev_pnl=ev_pnl, agg={str(k): dict(fills=a['fills'], usd=a['usd'], pnl=a['pnl'], mk=len(a['mk'])) for k, a in agg.items()}), open(f"{D}/deep_{label}.json", 'w'))

main()
