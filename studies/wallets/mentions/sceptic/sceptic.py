"""Sceptic's re-run of the mentions wallet study on another window (definitions copied from ../deep.py).
usage: python3 sceptic.py <label> <0xwallet> <tag> <t0> <t1> [analyst_fills.json]
Read-only. Writes s_<label>_<tag>.json next to this file and prints a text report."""
import sys, os, json, re, gzip, statistics as st, collections, datetime as dt
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, '/home/user/polymarket-lab')
from pmlab import gamma, dataapi, wallet as W, stats

D = os.path.dirname(os.path.abspath(__file__))
TAPES = '/home/user/polymarket-lab/data/mentions_tapes'
PAT = re.compile(r"(^|-)(say|says|said|mention|mentions|mentioned)(-|$)")
RATE = 0.01


def is_mention(md, slug):
    return any('mention' in t for t in gamma.tag_slugs(md or {})) or bool(PAT.search(slug or ''))


def tape(cond, closed, fresh=False):
    p = f"{TAPES}/{cond}.json.gz"
    if os.path.exists(p) and not fresh:
        return json.load(gzip.open(p, 'rt'))
    rows = [dict(t=r['timestamp'], w=r['proxy_wallet'], side=r['side'], o=r['outcome'], p=float(r['price']), s=float(r['size']))
            for r in dataapi.iter_trades(condition=cond)]
    rows.sort(key=lambda r: r['t'])
    if closed and not fresh:
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


ts = W._ts
def iso(t): return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime('%m-%d %H:%M:%S') if t else '-'
def tstat(vals):
    vals = list(vals)
    if len(vals) < 2: return 0.0
    sd = st.pstdev(vals)
    return sum(vals) / (sd * len(vals) ** 0.5) if sd else 0.0


def main():
    label, wal, tag, t0, t1 = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
    fp = sys.argv[6] if len(sys.argv) > 6 else f"{D}/_fills_{label}_{tag}.json"
    if os.path.exists(fp):
        fills, trunc = json.load(open(fp))
    else:
        fills, trunc = W.fetch_fills(wal, t0, t1, 120000)
        json.dump([fills, trunc], open(fp, 'w'))
    for f in fills:
        f['price'] = float(f['price']); f['size'] = float(f['size'])
    conds = sorted({f['condition_id'] for f in fills})
    meta = gamma.markets_by_condition(conds)
    slug_of = {}
    for f in fills: slug_of.setdefault(f['condition_id'], f['slug'])
    mset = {c for c in conds if is_mention(meta.get(c), slug_of[c])}
    mconds = sorted(mset)
    res = dataapi.resolutions(conds, cache=False)
    allusd = sum(f['size'] * f['price'] for f in fills)
    mf = [f for f in fills if f['condition_id'] in mset]
    musd = sum(f['size'] * f['price'] for f in mf)
    print(f"== {label} {wal} [{iso(t0)} -> {iso(t1)}] tag={tag} truncated={trunc} fills={len(fills)} usd={allusd:.0f} | mention fills={len(mf)} markets={len(mconds)} usd={musd:.0f} ({100*musd/max(allusd,1):.0f}% of turnover)")
    closed = {c: bool((meta.get(c) or {}).get('closed')) for c in mconds}
    with ThreadPoolExecutor(5) as ex:
        tapes = dict(zip(mconds, ex.map(lambda c: tape(c, closed[c]), mconds)))
    byc = collections.defaultdict(list)
    for f in fills: byc[f['condition_id']].append(f)

    agg = collections.defaultdict(lambda: dict(fills=0, usd=0.0, pnl=0.0, mk=collections.defaultdict(float)))
    def add(key, f, pnl, c):
        a = agg[key]; a['fills'] += 1; a['usd'] += f['size'] * f['price']; a['pnl'] += pnl; a['mk'][c] += pnl
    stories, jump, ev_pnl, mk_pnl, wk_pnl = {}, [], collections.defaultdict(float), {}, collections.defaultdict(float)
    late_buy = collections.defaultdict(float)
    bought = sold = 0.0
    conf_mk, conf_wrong, conf_usd, conf_pnl = set(), set(), 0.0, 0.0
    unres = dict(n=0, cost=0.0, mtm=0.0)
    for c in mconds:
        md = meta.get(c) or {}
        r = res.get(c) or {}
        fin = r.get('final') or {}
        fy = fin.get('Yes')
        ev = (md.get('events') or [{}])[0]
        start = ts(ev.get('startTime')) or ts(md.get('eventStartTime')) or ts(md.get('gameStartTime'))
        rows = tapes[c]
        if not r.get('resolved') or fy is None:
            unres['n'] += 1
            last_yes = yes(rows[-1]) if rows else 0.5
            for f in byc[c]:
                lp = last_yes if f['outcome'] == 'Yes' else 1 - last_yes
                sgn = 1 if f['side'] == 'BUY' else -1
                unres['cost'] += sgn * f['size'] * f['price']; unres['mtm'] += sgn * f['size'] * (lp - f['price'])
            continue
        tpre, tdet = det_times(rows, fy)
        first_move = None
        if fy >= 0.5 and tdet:
            for x in rows:
                if (tpre is None or x['t'] > tpre) and yes(x) >= 0.60: first_move = x['t']; break
        srows, tot = [], 0.0
        for f in sorted(byc[c], key=lambda f: f['timestamp']):
            t, p, s = f['timestamp'], f['price'], f['size']
            F = fin.get(f['outcome'])
            pnl = s * (F - p) if f['side'] == 'BUY' else s * (p - F)
            if f['role'] == 'T': pnl -= RATE * p * (1 - p) * s
            tot += pnl
            yp = p if f['outcome'] == 'Yes' else 1 - p
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
            if f['side'] == 'BUY':
                band = '>=0.95' if p >= 0.95 else ('0.80-0.95' if p >= 0.80 else ('0.50-0.80' if p >= 0.5 else '<0.50'))
                add(('buy_band', band), f, pnl, c)                      # NOT conditioned on the outcome
                add(('buy_lt95' if p < 0.95 else 'buy_ge95', ph, f['role']), f, pnl, c)
                bought += s
                if p >= 0.95:
                    late_buy[ph] += p * s; conf_mk.add(c); conf_usd += p * s; conf_pnl += pnl
                    if F is not None and F < 0.5: conf_wrong.add(c)
            else:
                sold += s
            srows.append(dict(t=t, rs=(t - start) if start else None, rd=(t - tdet) if tdet else None, rf=(t - first_move) if first_move else None,
                              role=f['role'], side=f['side'], o=f['outcome'], p=round(p, 4), s=round(s, 1), ph=ph, pnl=round(pnl, 2)))
            if fy >= 0.5 and ph == 'JUMP' and first_move:
                rank = len([x for x in rows if (tpre is None or x['t'] > tpre) and x['t'] < t])
                jump.append(dict(c=c, lag=t - first_move, rank=rank, role=f['role'], long_yes=long_yes, yp=yp, usd=p * s, pnl=pnl))
        mk_pnl[c] = tot
        evs = ev.get('slug') or md.get('slug')
        ev_pnl[evs] += tot
        wk_pnl[dt.datetime.fromtimestamp(srows[0]['t'], dt.timezone.utc).strftime('%G-W%V')] += tot
        stories[c] = dict(c=c, q=md.get('question'), event=evs, start=start, tpre=tpre, first_move=first_move, tdet=tdet, closed=ts(md.get('closedTime')),
                          fy=fy, vol=md.get('volumeNum'), n_tape=len(rows), pnl=round(tot, 2), usd=round(sum(x['p'] * x['s'] for x in srows), 1), fills=srows,
                          rules=(md.get('description') or '')[:300])

    def show(prefix):
        for k, a in sorted(((k, a) for k, a in agg.items() if k[0] == prefix), key=lambda x: str(x[0])):
            wins = sum(1 for v in a['mk'].values() if v > 0)
            print(f"  {str(k[1:]):34s} fills={a['fills']:5d} mk={len(a['mk']):4d} usd={a['usd']:9.0f} pnl={a['pnl']:9.1f} ({100*a['pnl']/max(a['usd'],1):6.1f}%) mk_win={wins}/{len(a['mk'])}")
    vals = list(mk_pnl.values())
    tot = sum(vals)
    usd_res = sum(s['usd'] for s in stories.values())
    print(f"resolved mention markets={len(vals)} unresolved={unres['n']} (net cost ${unres['cost']:.0f}, marked at last print {unres['mtm']:+.0f}) | turnover ${usd_res:.0f} | NET after 0.01 fee ${tot:.0f} | market wins {sum(1 for v in vals if v>0)}/{len(vals)} | t by market {tstat(vals):.2f} | events {len(ev_pnl)} positive {sum(1 for v in ev_pnl.values() if v>0)} | t by event {tstat(ev_pnl.values()):.2f}")
    if len(ev_pnl) > 2:
        lo, hi = stats.bootstrap_sum_ci(list(ev_pnl.values()))
        print(f"  bootstrap 95% CI of the sum, resampling events: [{lo:.0f}, {hi:.0f}]")
    print("  weeks:", {k: round(v) for k, v in sorted(wk_pnl.items())})
    mfr = [f for f in mf if f['condition_id'] in mk_pnl]
    mk_usd = sum(f['price'] * f['size'] for f in mfr if f['role'] == 'M')
    print(f"  maker share: {100*sum(1 for f in mfr if f['role']=='M')/max(len(mfr),1):.0f}% of fills, {100*mk_usd/max(usd_res,1):.0f}% of dollars; shares sold/bought {sold/max(bought,1):.2f}; median $/market {st.median([s['usd'] for s in stories.values()] or [0]):.0f}")
    print("by phase:"); show('phase')
    print("by phase, role, direction:"); show('phase_role_dir')
    print("BUYS by price band (all buys, winners and losers together):"); show('buy_band')
    print("buys below 0.95 by phase and role:"); show('buy_lt95')
    print("buys at >= 0.95 by phase and role:"); show('buy_ge95')
    lb = sum(late_buy.values())
    print(f"buys at >=0.95: usd by phase {({k: round(v) for k, v in late_buy.items()})} -> JUMP/POST share {100*(late_buy.get('JUMP',0)+late_buy.get('POST',0))/max(lb,1):.0f}% | markets {len(conf_mk)}, wrong side {len(conf_wrong)} | pnl {conf_pnl:+.0f} on ${conf_usd:.0f} ({100*conf_pnl/max(conf_usd,1):+.2f}%)")
    for c in conf_wrong: print(f"    wrong: {stories[c]['q']} pnl {stories[c]['pnl']}")
    tj = [j for j in jump if j['role'] == 'T' and j['long_yes']]
    if tj:
        bym = {}
        for j in sorted(tj, key=lambda j: j['lag']): bym.setdefault(j['c'], j)
        lags = [j['lag'] for j in bym.values()]
        cut = lambda a, b: sum(1 for x in lags if a <= x <= b)
        print(f"taker long-Yes fills in jump windows: {len(tj)} fills in {len(bym)} markets; first fill lag vs first print>=0.60: <=2s {cut(-9,2)}, 3-10s {cut(3,10)}, 11-60s {cut(11,60)}, >60s {cut(61,10**9)}; first on tape (rank 0) {sum(1 for j in bym.values() if j['rank']==0)}; median yes px {st.median(j['yp'] for j in tj):.3f}; below 0.90 in {len({j['c'] for j in tj if j['yp']<0.90})} markets; pnl {sum(j['pnl'] for j in tj):+.0f} on ${sum(j['usd'] for j in tj):.0f}; of that at lag<=10s {sum(j['pnl'] for j in tj if j['lag']<=10):+.0f}")
    # concentration
    top = sorted(mk_pnl.items(), key=lambda x: -x[1])
    print("CONCENTRATION: top 3 markets:", [(stories[c]['q'][:60], round(v)) for c, v in top[:3]], f"-> rest {tot - sum(v for _, v in top[:3]):+.0f} on {len(top)-3} markets, t {tstat([v for _, v in top[3:]]):.2f}")
    evt = sorted(ev_pnl.items(), key=lambda x: -x[1])
    if evt:
        print(f"  best event {evt[0][0][:60]} {evt[0][1]:+.0f} -> rest {tot - evt[0][1]:+.0f}; best 3 events {sum(v for _, v in evt[:3]):+.0f} -> rest {tot - sum(v for _, v in evt[:3]):+.0f}; worst 3 markets {[(stories[c]['q'][:50], round(v)) for c, v in top[-3:]]}")
    # non-mention markets of the same wallet, same window (gross of fee, resolved only)
    oth = collections.defaultdict(float); oth_usd = 0.0; oth_unres = 0
    for c in conds:
        if c in mset: continue
        r = res.get(c) or {}
        if not r.get('resolved'): oth_unres += 1; continue
        for f in byc[c]:
            F = (r.get('final') or {}).get(f['outcome'])
            if F is None: continue
            oth[c] += f['size'] * (F - f['price']) * (1 if f['side'] == 'BUY' else -1); oth_usd += f['size'] * f['price']
    print(f"NON-mention markets in the same window: resolved {len(oth)} (unresolved {oth_unres}), turnover ${oth_usd:.0f}, pnl BEFORE fee {sum(oth.values()):+.0f}, t by market {tstat(oth.values()):.2f}")
    # fee actually charged
    try:
        pts = dataapi.user_pnl(wal)
        a = max((q for q in pts if q['timestamp'] <= t0), key=lambda q: q['timestamp'], default={})
        b = max((q for q in pts if q['timestamp'] <= t1), key=lambda q: q['timestamp'], default={})
        d = lambda k: (b.get(k) or 0) - (a.get(k) or 0)
        base = sum(f['size'] * f['price'] * (1 - f['price']) for f in fills if f['role'] == 'T')
        print(f"API over the window (all categories): trade_pnl {d('trade_pnl'):+.0f}, fees {d('fees'):+.1f}, refunded {d('fees_refunded'):+.1f}, rebates+rewards {d('taker_rebate')+d('maker_rebate')+d('reward_income'):+.1f}, economic {d('economic_pnl'):+.0f} | implied taker rate = {-d('fees')/max(base,1e-9):.4f} (fees / sum s*p*(1-p) of taker fills = {base:.0f})")
    except Exception as e:
        print('user_pnl failed', e)
    try:
        ops = collections.Counter(); opu = collections.Counter()
        for r in dataapi.iter_activity(wal, types="SPLIT,MERGE,CONVERSION", start=t0, end=t1):
            ops[r.get('type')] += 1; opu[r.get('type')] += float(r.get('usdc_size') or 0)
        print("inventory operations in window:", dict(ops), {k: round(v) for k, v in opu.items()})
    except Exception as e:
        print('activity failed', e)
    # raw timelines for the five largest |pnl| markets (tape re-pulled fresh from the API)
    print("RAW timelines, five largest |pnl| markets (fresh tape):")
    for c, v in sorted(mk_pnl.items(), key=lambda x: -abs(x[1]))[:5]:
        s = stories[c]
        rows = tape(c, True, fresh=True)
        print(f" * {s['q']} | vol {s['vol'] and round(s['vol'])} | final Yes={s['fy']} | start {iso(s['start'])} last<0.60 {iso(s['tpre'])} first>=0.60 {iso(s['first_move'])} first>=0.90 held {iso(s['tdet'])} closed {iso(s['closed'])} | pnl {v:+.0f} | tape rows fresh {len(rows)} cached {s['n_tape']}")
        for x in s['fills'][:10]:
            near = [y for y in rows if abs(y['t'] - x['t']) <= 30]
            mine = [y for y in near if y['w'].lower() == wal.lower() and y['t'] == x['t']]
            before = [yes(y) for y in rows if x['t'] - 600 <= y['t'] < x['t']][-3:]
            after = [yes(y) for y in rows if x['t'] < y['t'] <= x['t'] + 600][:3]
            print(f"     {iso(x['t'])} {x['role']} {x['side']} {x['o']} {x['s']:.0f}@{x['p']:.3f} ph={x['ph']} from_start={x['rs']} from_first60={x['rf']} pnl {x['pnl']:+.0f} | on tape as taker: {'yes' if mine else 'no'} | yes px 10 min before {[round(z,3) for z in before]} after {[round(z,3) for z in after]}")
        if len(s['fills']) > 10: print(f"     ... {len(s['fills'])-10} more fills")
    json.dump(dict(label=label, wallet=wal, t0=t0, t1=t1, stories=list(stories.values()), mk_pnl=mk_pnl, ev_pnl=ev_pnl, jump=jump), open(f"{D}/s_{label}_{tag}.json", 'w'))


main()
