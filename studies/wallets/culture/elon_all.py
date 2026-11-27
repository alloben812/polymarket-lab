"""Unconditional description of Elon post-count events (see protocol addendum 3).  python3 -I elon_all.py"""
import bisect, collections, datetime as dt, json, re, statistics as st, sys, time, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT))
from pmlab import dataapi, gamma
def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}), timeout=60) as r: return json.loads(r.read())
ts = lambda s: int(dt.datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp())
P = json.load(open(ROOT / 'data' / 'xtracker' / 'elon_posts.json')); PT = [a for a, _ in P]
count = lambda a, b: bisect.bisect_left(PT, b) - bisect.bisect_left(PT, a)
tr = get('https://xtracker.polymarket.com/api/users/elonmusk/trackings?activeOnly=false')['data']
now = time.time(); EV = []
for t in tr:
    s, e = ts(t['startDate']), ts(t['endDate']) + 1
    if t.get('marketLink') and s >= PT[0] + 28 * 86400 and e < now - 3600 and e - s <= 8 * 86400: EV.append((e, s, t['marketLink'].rstrip('/').split('/')[-1]))
EV.sort(); print(f'events {len(EV)} (ended {dt.datetime.fromtimestamp(EV[0][0], dt.timezone.utc):%m-%d} .. {dt.datetime.fromtimestamp(EV[-1][0], dt.timezone.utc):%m-%d}); posts by UTC hour, last 28 d:',
                 ' '.join(f'{h}:{sum(1 for a in PT if a > now - 28 * 86400 and (a // 3600) % 24 == h)}' for h in range(24)))
def diurnal(s, t, e):
    how = collections.Counter((a // 3600) % 168 for a in PT if s - 28 * 86400 <= a < s)
    exp = 0.0; x = t
    while x < e:
        nx = min(e, (x // 3600 + 1) * 3600); exp += how[(x // 3600) % 168] / 4 * (nx - x) / 3600; x = nx
    return exp
def bucket(slug):
    m = re.search(r'-(\d+)-(\d+)$', slug)
    if m: return int(m.group(1)), int(m.group(2))
    m = re.search(r'-(\d+)plus$', slug)
    if m: return int(m.group(1)), 10 ** 6
    m = re.search(r'less-than-(\d+)$', slug)
    if m: return 0, int(m.group(1)) - 1
    return None
ERR = collections.defaultdict(list); WP = collections.defaultdict(list); R = collections.defaultdict(list); shown = False
for e, s, slug in EV:
    F = count(s, e); ev = gamma.event_by_slug(slug) or {}
    mk = []
    for m in ev.get('markets') or []:
        b = bucket(m.get('slug') or '')
        if b: mk.append((b, gamma.jfield(m.get('clobTokenIds'))[0], m))
    mk.sort(key=lambda x: x[0]); win = next((x for x in mk if x[0][0] <= F <= x[0][1]), None)
    ph = {}
    def price(tok, t):
        if tok not in ph:
            rows = dataapi.prices_history(tok, e - 26 * 3600, e, 300)
            ph[tok] = sorted((int(r.get('timestamp') or r.get('t')), float(r.get('price') if r.get('price') is not None else r.get('p'))) for r in rows)
        v = ph[tok]; i = bisect.bisect_right([a for a, _ in v], t) - 1
        return v[i][1] if i >= 0 else None
    line = f"{slug[20:52]:32} days {(e - s) / 86400:3.0f} final {F:4} mkts {len(mk):2}"
    for hh in (24, 12, 6, 2):
        t = e - hh * 3600
        if t <= s: continue
        N = count(s, t); pace = N + N / (t - s) * (e - t); dm = N + diurnal(s, t, e)
        if hh != 2: ERR[(hh, 'pace')].append(F - pace); ERR[(hh, 'diurnal')].append(F - dm)
        if not mk: continue
        wp = price(win[1], t) if win else None
        if wp is not None: WP[hh].append(wp)
        line += f" | T-{hh}h N {N:3} pace {pace:4.0f} diur {dm:4.0f} winpx {wp if wp is None else round(wp, 2)}"
        if hh == 2: continue
        idx = next((i for i, x in enumerate(mk) if x[0][0] <= pace <= x[0][1]), None)
        idd = next((i for i, x in enumerate(mk) if x[0][0] <= dm <= x[0][1]), None)
        for name, base, k in (('pace', idx, 0), ('pace+1', idx, 1), ('pace-1', idx, -1), ('diurnal', idd, 0)):
            if base is None or not (0 <= base + k < len(mk)): continue
            b, tok, m = mk[base + k]; p = price(tok, t)
            if p is None or not (0.01 <= p <= 0.95): continue
            c = p + 0.01; R[(hh, name)].append(((1.0 if b[0] <= F <= b[1] else 0.0) - c - 0.01 * c * (1 - c), c))
    print(line[:250])
print('\nprojection error final - projection (posts): bias / RMSE / n')
for k in sorted(ERR): v = ERR[k]; print(f'  T-{k[0]:2}h {k[1]:8} bias {st.mean(v):6.1f} rmse {(sum(x * x for x in v) / len(v)) ** .5:6.1f} n {len(v)}')
for hh, v in sorted(WP.items(), reverse=True): v = sorted(v); print(f'  winner price T-{hh:2}h: median {v[len(v) // 2]:.2f}, <=0.20 in {sum(1 for x in v if x <= .2)}/{len(v)}, <=0.50 in {sum(1 for x in v if x <= .5)}/{len(v)}')
print('exploratory rules (price+1c, fee in; NOT a fill test); "diurnal" row added as a 10th-12th variant:')
for k in sorted(R):
    v = R[k]; x = [a for a, _ in v]
    if len(x) > 2: print(f'  T-{k[0]:2}h buy {k[1]:8} events {len(x):2} hit {sum(1 for a in x if a > 0):2} avg cost {st.mean(c for _, c in v):.2f} pnl/share {100 * st.mean(x):6.1f} c (se {100 * st.stdev(x) / len(x) ** .5:.1f}, t {st.mean(x) / (st.stdev(x) / len(x) ** .5):5.2f})')
