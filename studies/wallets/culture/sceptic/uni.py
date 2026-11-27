"""Universe checks U1/U2 (protocol addendum S1): all closed box-office events, whoever traded them."""
import sys, os, json, gzip, bisect, collections, statistics as st, datetime as dt
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, '/home/user/polymarket-lab')
from pmlab import gamma, dataapi, wallet as W
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
TAPES = '/home/user/polymarket-lab/data/culture_tapes'
T0, T1 = 1785542400, 1795435200   # 1 Aug .. 23 Nov 12:00
evs = json.load(open(f'{D}/_events_box-office.json'))
cd = set(); 
for tag in ('W1', 'W0'):
    for f in json.load(open(f'{D}/_fills_cat-dog_{tag}.json'))[0]: cd.add(f['condition_id'])
ms = []
for e in evs:
    end = W._ts(e.get('endDate'))
    if not end or not (T0 <= end <= T1): continue
    for m in e.get('markets') or []:
        op = gamma.jfield(m.get('outcomePrices')); outs = gamma.jfield(m.get('outcomes'))
        if not op or not outs or not m.get('closed'): continue
        f = float(op[0])
        if f not in (0.0, 1.0): continue
        ms.append(dict(cond=m['conditionId'], slug=m['slug'], event=e['slug'], end=W._ts(m.get('endDate')) or end, first=outs[0], final=f, vol=m.get('volumeNum') or 0))
print('events in range', len({m['event'] for m in ms}), 'markets', len(ms), 'traded by cat-dog', sum(1 for m in ms if m['cond'] in cd))
def tape(m):
    p = f"{TAPES}/{m['cond']}.json.gz"
    if os.path.exists(p): rows = json.load(gzip.open(p, 'rt'))
    else:
        rows = [dict(t=int(r['timestamp']), w=r.get('proxy_wallet'), o=r.get('outcome'), p=float(r['price']), s=float(r['size']), side=r.get('side'), tx=r.get('transaction_hash'))
                for r in dataapi.iter_trades(condition=m['cond'], max_rows=60000)]
        rows.sort(key=lambda r: r['t']); json.dump(rows, gzip.open(p, 'wt'))
    return [(r['t'], r['p'] if r['o'] == m['first'] else 1 - r['p']) for r in rows]
with ThreadPoolExecutor(6) as ex: tapes = list(ex.map(tape, ms))
evtouched = {m['event'] for m in ms if m['cond'] in cd}
B = 600
def ruleJ(sel, name):
    per = {}; njump = 0; nofill = 0; cont = []; contm = collections.defaultdict(list)
    for m, tp in zip(ms, tapes):
        if not tp or not sel(m): continue
        bars = collections.OrderedDict()
        for t, p in tp: bars.setdefault(t // B, []).append(p)
        res = []; last = None
        for k in bars:
            cur = bars[k][-1]
            if last is not None and len(bars[k]) >= 3 and abs(cur - last) >= 0.10 and 0.05 <= last <= 0.95 and 0.05 <= cur <= 0.95:
                njump += 1; sign = 1 if cur > last else -1
                nxt = bars.get(k + 1)
                cont.append(sign * (m['final'] - cur)); contm[m['cond']].append(sign * (m['final'] - cur))
                if not nxt: nofill += 1
                else:
                    py = max(nxt) if sign > 0 else min(nxt); ptok = py if sign > 0 else 1 - py
                    if 0.02 <= py <= 0.98: res.append(sign * (m['final'] - py) - 0.01 * ptok * (1 - ptok))
            last = cur
        if res: per[m['cond']] = st.mean(res)
    x = list(per.values()); cm = [st.mean(v) for v in contm.values()]
    if len(x) < 3: print(f'  {name}: too few'); return
    print(f"  {name:34} markets with a jump {len(contm):4} jumps {njump:4} no print next bar {nofill:4} | follow at worst next-bar print: mkts {len(x):3} pnl/share {100 * st.mean(x):6.2f} c t {st.mean(x) / (st.stdev(x) / len(x) ** .5):5.2f}"
          f" | outcome minus price right after jump, by market: {100 * st.mean(cm):6.2f} c t {st.mean(cm) / (st.stdev(cm) / len(cm) ** .5):5.2f}")
print('U1 rule J:')
ruleJ(lambda m: True, 'all markets')
ruleJ(lambda m: m['cond'] in cd, 'markets cat-dog traded')
ruleJ(lambda m: m['cond'] not in cd, 'markets cat-dog did not trade')
ruleJ(lambda m: m['event'] not in evtouched, 'events cat-dog never touched')
ruleJ(lambda m: m['end'] < 1790553600, 'ended before 28 Sep'); ruleJ(lambda m: m['end'] >= 1790553600, 'ended from 28 Sep')
print('U2 blind benchmark at end - 70 h, buckets priced 0.10-0.90 (per dollar, unit = event, no fee):')
def bench(sel, name):
    ey = collections.defaultdict(lambda: [0.0, 0.0]); en = collections.defaultdict(lambda: [0.0, 0.0]); n = 0
    for m, tp in zip(ms, tapes):
        if not tp or not sel(m): continue
        ts = [t for t, _ in tp]; t = m['end'] - 70 * 3600
        i = bisect.bisect_right(ts, t) - 1
        if i < 0 or ts[i] < t - 48 * 3600: continue
        p = tp[i][1]
        if not (0.10 <= p <= 0.90): continue
        n += 1
        ey[m['event']][0] += m['final'] - p; ey[m['event']][1] += p                 # 1 share of Yes
        en[m['event']][0] += (1 - m['final']) - (1 - p); en[m['event']][1] += 1 - p   # 1 share of No
    for lab, e in (('Yes', ey), ('No', en)):
        num = [v[0] for v in e.values()]; den = sum(v[1] for v in e.values())
        if len(num) < 3: continue
        se = st.stdev(num) * len(num) ** .5
        print(f"  {name:30} blind {lab:3}: buckets {n:4} events {len(num):3} return {100 * sum(num) / den:6.1f}% of dollars (t by event {sum(num) / se:5.2f})")
bench(lambda m: True, 'all events'); bench(lambda m: m['cond'] in cd, 'buckets cat-dog traded'); bench(lambda m: m['cond'] not in cd, 'buckets it did not trade')
json.dump(ms, open(f'{D}/_universe_markets.json', 'w'))
