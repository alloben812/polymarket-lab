"""Family A: counter model (M1 pace, M2 profile) vs bucket prices, protocol.md. python3 -I analyze.py > out/report.txt
Writes out/trades.csv (one row per entry) and out/variants.csv."""
import bisect, collections, csv, datetime as dt, gzip, json, math, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT))
from pmlab import stats
D = ROOT / 'data' / 'gaps_counter'; OUT = Path(__file__).resolve().parent / 'out'; OUT.mkdir(exist_ok=True)
RATE = 0.01; LAG = 3; WIN = 1800; HS = (72, 24, 12, 6); KGRID = (1, 2, 3, 5, 8, 12, 20, 30, 50, 100, 1000)
fee = lambda c: RATE * c * (1 - c)
iso = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime('%Y-%m-%d %H:%M')

def bucket(slug):
    m = re.search(r'-(\d+)-(\d+)$', slug)
    if m: return int(m.group(1)), int(m.group(2))
    m = re.search(r'-(\d+)-?plus$', slug) or re.search(r'-(\d+)-or-more$', slug)
    if m: return int(m.group(1)), 10 ** 7
    m = re.search(r'less-than-(\d+)$', slug) or re.search(r'-under-(\d+)$', slug)
    if m: return 0, int(m.group(1)) - 1
    return None

# ---------- load ----------
META = json.load(open(D / 'events_meta.json'))
POSTS = {}
def posts(h):
    if h not in POSTS:
        P = json.load(open(D / 'posts' / f'{h}.json'))
        POSTS[h] = (sorted(a for a, _ in P), [(a, b) for a, b in P])
    return POSTS[h]
EV, drop = [], collections.Counter()
for ev in META:
    mk = []
    for m in ev['markets']:
        b = bucket(m['slug'] or '')
        if b is None: mk = None; break
        mk.append((b, m))
    if not mk: drop['unparsed bucket'] += 1; continue
    mk.sort(key=lambda x: x[0])
    res = []
    for b, m in mk:
        pr = [float(x) for x in (m['prices'] or [])]
        if not m['closed'] or len(pr) != 2 or sorted(pr) != [0.0, 1.0]: res = None; break
        yi = m['outcomes'].index('Yes'); res.append((b, m, pr[yi]))
    if res is None: drop['not resolved 1/0'] += 1; continue
    if sum(r[2] for r in res) != 1: drop['not exactly one Yes'] += 1; continue
    created, P = posts(ev['handle'])
    F = bisect.bisect_left(created, ev['e']) - bisect.bisect_left(created, ev['s'])
    win = next(r[0] for r in res if r[2] == 1)
    imp = sorted(b for a, b in P if ev['s'] <= a < ev['e'])  # import times of posts counted in the window
    EV.append({**ev, 'mk': res, 'F': F, 'win': win, 'match': win[0] <= F <= win[1], 'imp': imp})
EV.sort(key=lambda x: x['e'])
half = len(EV) // 2
for i, ev in enumerate(EV): ev['part'] = 'EARLY' if i < half else 'LATE'
print(f'events loaded {len(META)}, usable {len(EV)}, dropped {dict(drop)}')
print(f'EARLY: {len(EV[:half])} events ending {iso(EV[0]["e"])} .. {iso(EV[half - 1]["e"])}; LATE: {len(EV[half:])} ending {iso(EV[half]["e"])} .. {iso(EV[-1]["e"])}')
mm = collections.Counter((ev['handle'], ev['match']) for ev in EV)
print('tracker count in resolved bucket (handle: match / total):', {h: f"{mm[(h, True)]}/{mm[(h, True)] + mm[(h, False)]}" for h in sorted({e['handle'] for e in EV})})
for ev in EV:
    if not ev['match']: print(f"   mismatch {ev['slug']}: tracker {ev['F']}, resolved bucket {ev['win']}")

# ---------- models ----------
PROF = {}
def profile(h, s):
    key = (h, s)
    if key not in PROF:
        created, _ = posts(h); c = collections.Counter()
        for a in created[bisect.bisect_left(created, s - 28 * 86400): bisect.bisect_left(created, s)]: c[(a // 3600) % 168] += 1
        PROF[key] = [c[i] / 4 for i in range(168)]
    return PROF[key]
def integ(pr, a, b):
    tot, x = 0.0, a
    while x < b:
        nx = min(b, (x // 3600 + 1) * 3600); tot += pr[(x // 3600) % 168] * (nx - x) / 3600; x = nx
    return tot
def ncount(ev, t): return bisect.bisect_right(ev['imp'], t)
def mu_of(model, ev, t, N):
    if model == 'M1': return N * (ev['e'] - t) / (t - ev['s'])
    pr = profile(ev['handle'], ev['s']); return integ(pr, t, ev['e']) * (N + 1) / (integ(pr, ev['s'], t) + 1)
CDF = {}
def cdf(mu, k):
    mu = max(0.05, round(mu, 1)); key = (mu, k)
    if key not in CDF:
        p = k / (k + mu); M = int(mu * 6 + 60 + 6 * math.sqrt(mu + mu * mu / k))
        pm = math.exp(k * math.log(p)); out = []; acc = 0.0
        for r in range(M):
            acc += pm; out.append(acc); pm *= (r + k) / (r + 1) * (1 - p)
        CDF[key] = out
    return CDF[key]
def cprob(mu, k, x):  # P(R <= x)
    if x < 0: return 0.0
    c = cdf(mu, k); return c[x] if x < len(c) else 1.0
def qbucket(mu, k, N, lo, hi): return max(0.0, cprob(mu, k, hi - N) - cprob(mu, k, lo - 1 - N))
def nb_logpmf(r, mu, k):
    mu = max(mu, 0.05)
    return math.lgamma(r + k) - math.lgamma(k) - math.lgamma(r + 1) + k * math.log(k / (k + mu)) + r * math.log(mu / (k + mu))

def dec_times(ev): return [(h, ev['e'] - h * 3600) for h in HS if ev['e'] - h * 3600 - ev['s'] >= 24 * 3600]
KFIT = {}
print('\nNB dispersion k fitted on EARLY events (counts only): model h -> k (n, mean |R - mu|)')
for model in ('M1', 'M2'):
    for h in HS:
        pairs = []
        for ev in EV[:half]:
            for hh, t in dec_times(ev):
                if hh != h: continue
                N = ncount(ev, t); pairs.append((ev['F'] - N, mu_of(model, ev, t, N)))
        if not pairs: KFIT[(model, h)] = 20; continue
        best = max(KGRID, key=lambda k: sum(nb_logpmf(max(r, 0), mu, k) for r, mu in pairs))
        KFIT[(model, h)] = best
        print(f'  {model} h={h:2}: k={best:5} (n={len(pairs)}, mean |R-mu| {sum(abs(r - mu) for r, mu in pairs) / len(pairs):.1f}, bias {sum(r - mu for r, mu in pairs) / len(pairs):+.1f})')

# ---------- tapes ----------
TP = {}
def tape(cid):
    if cid not in TP: TP[cid] = sorted(json.load(gzip.open(D / 'tapes' / f'{cid}.json.gz', 'rt')), key=lambda r: r['t'])
    return TP[cid]

def run(model, theta, cap):
    trades = []
    for ev in EV:
        for h, t in dec_times(ev):
            k = KFIT[(model, h)]; prints = []
            for (lo, hi), m, yes in ev['mk']:
                toks = m['toks']; yi = m['outcomes'].index('Yes'); ytok, ntok = toks[yi], toks[1 - yi]
                rows = tape(m['cid']); i = bisect.bisect_left([r['t'] for r in rows], t + LAG)
                last = {}
                for r in rows[max(0, i - 200): i]:  # recent prices per token for the move diagnostic
                    tk = r['tok'] if r['side'] == 'BUY' else (ntok if r['tok'] == ytok else ytok)
                    c = r['p'] if r['side'] == 'BUY' else 1 - r['p']; last.setdefault(tk, []).append((r['t'] - LAG, c))
                for r in rows[i:]:
                    mt = r['t'] - LAG
                    if mt > t + WIN: break
                    if r['side'] == 'BUY': tk, c = r['tok'], r['p']
                    else: tk, c = (ntok if r['tok'] == ytok else ytok), 1 - r['p']
                    prints.append((mt, (lo, hi), tk == ytok, c, r['s'], yes, m['cid'], tk))
            prints.sort(key=lambda x: x[0]); done = set(); hist = collections.defaultdict(list)
            for mt, (lo, hi), isyes, c, sz, yes, cid, tk in prints:
                prev = [pc for pt, pc in hist[tk] if mt - 60 <= pt < mt]; hist[tk].append((mt, c))
                key = (cid, isyes)
                if key in done or not (0.02 <= c <= 0.97): continue
                N = ncount(ev, mt); mu = mu_of(model, ev, mt, N); q = qbucket(mu, k, N, lo, hi)
                if not isyes: q = 1 - q
                if q - c - fee(c) < theta: continue
                done.add(key); sh = min(sz, cap / c); pay = yes if isyes else 1 - yes
                moved = any(abs(c - pc) >= 0.05 for pc in prev)
                trades.append({'event': ev['slug'], 'handle': ev['handle'], 'part': ev['part'], 'h': h, 'mt': mt, 'bucket': f'{lo}-{hi}',
                               'side': 'YES' if isyes else 'NO', 'c': c, 'q': round(q, 4), 'shares': sh, 'usd': sh * c,
                               'pnl': sh * (pay - c - fee(c)), 'win': pay, 'moved60': moved, 'wkend': dt.datetime.fromtimestamp(t, dt.timezone.utc).weekday() >= 5,
                               'end': ev['e']})
    return trades

def summ(tr, label):
    by = collections.defaultdict(lambda: [0.0, 0.0, 0.0])
    for x in tr: b = by[x['event']]; b[0] += x['pnl']; b[1] += x['shares']; b[2] += x['usd']
    if not tr: return {'label': label, 'trades': 0, 'events': 0}
    keys = list(by); num = [by[k][0] for k in keys]; sh = [by[k][1] for k in keys]; usd = [by[k][2] for k in keys]
    r_sh, se_sh, t_sh = stats.ratio_cluster(num, sh); r_usd, se_usd, t_usd = stats.ratio_cluster(num, usd)
    lo, hi = stats.bootstrap_sum_ci(num)
    best = max(keys, key=lambda k: by[k][0]); rest = [k for k in keys if k != best]
    wo = sum(by[k][0] for k in rest) / max(1e-9, sum(by[k][2] for k in rest))
    return {'label': label, 'trades': len(tr), 'events': len(keys), 'usd': sum(usd), 'pnl': sum(num), 'c_per_sh': 100 * r_sh, 'se_c': 100 * se_sh,
            'pct_usd': 100 * r_usd, 't': t_usd, 'ci_lo': lo, 'ci_hi': hi, 'pct_wo_best': 100 * wo, 'hit': sum(x['win'] for x in tr) / len(tr),
            'avg_c': sum(x['c'] for x in tr) / len(tr), 'avg_q': sum(x['q'] for x in tr) / len(tr)}
def fmt(s):
    if not s.get('trades'): return f"  {s['label']:44} no trades"
    return (f"  {s['label']:44} trades {s['trades']:4} events {s['events']:3} usd {s['usd']:8.0f} net {s['pnl']:+8.1f} "
            f"| {s['c_per_sh']:+6.2f} c/sh (se {s['se_c']:.2f}) {s['pct_usd']:+6.1f}% of $ t {s['t']:+5.2f} | 95% CI total [{s['ci_lo']:+.0f}, {s['ci_hi']:+.0f}] "
            f"| w/o best event {s['pct_wo_best']:+.1f}% | hit {s['hit']:.2f} avg price {s['avg_c']:.2f} avg q {s['avg_q']:.2f}")

ALL = {}; rows = []
print('\n=== variants ($20 cap) ===')
for model in ('M1', 'M2'):
    for theta in (0.05, 0.10):
        tr = run(model, theta, 20); ALL[(model, theta)] = tr
        for part in ('EARLY', 'LATE'):
            s = summ([x for x in tr if x['part'] == part], f'{model} theta={theta:.2f} {part}'); print(fmt(s)); rows.append({**s, 'model': model, 'theta': theta, 'part': part, 'cap': 20})
sel = max(ALL, key=lambda k: (summ([x for x in ALL[k] if x['part'] == 'EARLY'], '').get('pct_usd', -1e9), k[1]))
print(f'\nSELECTED on EARLY (highest net % of $): {sel[0]} theta={sel[1]}')
tr = ALL[sel]; late = [x for x in tr if x['part'] == 'LATE']
print('\n=== selected variant, LATE sub-cuts (descriptive) ===')
cuts = [('events ending >= 2026-11-21', lambda x: x['end'] >= 1795219200), ('decision on Sat/Sun UTC', lambda x: x['wkend']),
        ('decision Mon-Fri UTC', lambda x: not x['wkend']), ('elonmusk', lambda x: x['handle'] == 'elonmusk'), ('other handles', lambda x: x['handle'] != 'elonmusk'),
        ('side YES', lambda x: x['side'] == 'YES'), ('side NO', lambda x: x['side'] == 'NO')] + [(f'h={h}', (lambda h: lambda x: x['h'] == h)(h)) for h in HS]
for name, f in cuts: print(fmt(summ([x for x in late if f(x)], name)))
print('\n=== selected variant, both parts, by handle ===')
for h in sorted({x['handle'] for x in tr}):
    for part in ('EARLY', 'LATE'): print(fmt(summ([x for x in tr if x['handle'] == h and x['part'] == part], f'{h} {part}')))
print('\n=== $5 cap, selected variant ===')
tr5 = run(sel[0], sel[1], 5)
for part in ('EARLY', 'LATE'): s = summ([x for x in tr5 if x['part'] == part], f'{sel[0]} theta={sel[1]} $5cap {part}'); print(fmt(s)); rows.append({**s, 'model': sel[0], 'theta': sel[1], 'part': part, 'cap': 5})
# per-day numbers on LATE
if late:
    span = (max(x['end'] for x in late) - min(EV[half]['s'], min(x['mt'] for x in late))) / 86400
    d0, d1 = min(x['mt'] for x in late), max(x['mt'] for x in late); days = max(1.0, (d1 - d0) / 86400)
    print(f"\nLATE entries span {days:.1f} days ({iso(d0)} .. {iso(d1)}): {len(late) / days:.1f} entries/day, ${sum(x['usd'] for x in late) / days:.0f}/day spent, net ${sum(x['pnl'] for x in late) / days:+.1f}/day")
    print(f"net per trade at $20 cap: {sum(x['pnl'] for x in late) / len(late):+.3f} USD (avg spend {sum(x['usd'] for x in late) / len(late):.2f}); "
          f"$5 cap: {sum(x['pnl'] for x in tr5 if x['part'] == 'LATE') / max(1, sum(1 for x in tr5 if x['part'] == 'LATE')):+.3f} USD")
    full = [x for x in tr5 if x['part'] == 'LATE']
    print(f"share of LATE entries with a >=5c move of the same token within the previous 60 s: {sum(x['moved60'] for x in late) / len(late):.2f}")
    print(f"share of LATE entries filled at the full $20 (print size >= 20/c): {sum(1 for x in late if x['usd'] >= 19.99) / len(late):.2f}")
    ph = collections.Counter(int(x['q'] * 10) / 10 for x in late)
print('\n=== calibration of the selected model on its entries (both parts): q bin -> n, mean q, win rate, mean price ===')
for part in ('EARLY', 'LATE'):
    cb = collections.defaultdict(list)
    for x in tr:
        if x['part'] == part: cb[min(9, int(x['q'] * 10))].append(x)
    for b in sorted(cb):
        v = cb[b]; print(f"  {part} q {b / 10:.1f}-{(b + 1) / 10:.1f}: n {len(v):4} mean q {sum(x['q'] for x in v) / len(v):.3f} win {sum(x['win'] for x in v) / len(v):.3f} price {sum(x['c'] for x in v) / len(v):.3f}")
with open(OUT / 'variants.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=sorted({k for r in rows for k in r})); w.writeheader(); w.writerows(rows)
with open(OUT / 'trades.csv', 'w', newline='') as f:
    keys = ['event', 'handle', 'part', 'h', 'mt', 'bucket', 'side', 'c', 'q', 'shares', 'usd', 'pnl', 'win', 'moved60', 'wkend']
    w = csv.DictWriter(f, fieldnames=keys, extrasaction='ignore'); w.writeheader()
    for x in tr: w.writerow({**x, 'shares': round(x['shares'], 2), 'usd': round(x['usd'], 2), 'pnl': round(x['pnl'], 3)})
