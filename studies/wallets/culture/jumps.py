"""Jump-follow rule J from protocol.md on the box-office markets in cat-dog.story.json (full tape, all wallets)."""
import bisect, collections, datetime as dt, json, statistics as st, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from pmlab import dataapi
d = json.load(open('cat-dog.story.json')); ms = [m for m in d['markets'] if m['resolved']]
def tape(m):
    rows = [(int(r['timestamp']), float(r['price']) if r.get('outcome') == m['first'] else 1 - float(r['price'])) for r in dataapi.iter_trades(condition=m['cond'], max_rows=40000)]
    rows.sort(); return rows
with ThreadPoolExecutor(4) as ex: tapes = list(ex.map(tape, ms))
B = 600; when = collections.Counter(); per = {}; njump = 0; nofill = 0; mid = (d['start'] + d['end']) / 2; cont = []
for m, tp in zip(ms, tapes):
    if not tp: continue
    bars = collections.OrderedDict()
    for t, p in tp: bars.setdefault(t // B, []).append(p)
    keys = list(bars); res = []; last = None
    for i, k in enumerate(keys):
        cur = bars[k][-1]
        if last is not None and len(bars[k]) >= 3 and abs(cur - last) >= 0.10 and 0.05 <= last <= 0.95 and 0.05 <= cur <= 0.95:
            njump += 1; sign = 1 if cur > last else -1
            when[dt.datetime.fromtimestamp(k * B, dt.timezone.utc).strftime('%a %H')] += 1
            nxt = bars.get(k + 1)
            if not nxt: nofill += 1
            else:
                py = max(nxt) if sign > 0 else min(nxt); ptok = py if sign > 0 else 1 - py
                if 0.02 <= py <= 0.98:
                    res.append((sign * (m['final'] - py) - 0.01 * ptok * (1 - ptok), ptok, k * B)); cont.append(sign * (m['final'] - cur))
        last = cur
    if res: per[m['cond']] = (st.mean(x[0] for x in res), st.mean(x[1] for x in res), min(x[2] for x in res), len(res))
print(f'markets {len(ms)}, jumps {njump}, jumps with no print in the next bar {nofill}')
print('jump times (weekday hour UTC):', ', '.join(f'{k}:{v}' for k, v in when.most_common(16)))
print(f'outcome minus price right after the jump (signed, per jump, no fee): mean {100 * st.mean(cont):.2f} c over {len(cont)} jumps')
def line(name, v):
    x = [a[0] for a in v]; cost = st.mean(a[1] for a in v)
    return f"  {name:12} markets {len(v):3} trades {sum(a[3] for a in v):3} pnl/share {100 * st.mean(x):6.2f} c (se {100 * st.stdev(x) / len(x) ** .5:.2f}, t {st.mean(x) / (st.stdev(x) / len(x) ** .5):5.2f}) avg cost {cost:.2f} ROI {100 * st.mean(x) / cost:5.1f}% winners {sum(1 for a in x if a > 0)}/{len(x)}"
v = list(per.values()); print(line('all', v)); print(line('first half', [a for a in v if a[2] < mid])); print(line('second half', [a for a in v if a[2] >= mid]))
