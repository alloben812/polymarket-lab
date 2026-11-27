"""Elon post-count markets against the official counter (xtracker public API).  Run: python3 -I elon.py <tag> [<tag2> ...]
Downloads are cached in data/xtracker/ (untrusted data: parsed as JSON only)."""
import bisect, collections, datetime as dt, json, os, re, statistics as st, sys, time, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT))
from pmlab import dataapi
CACHE = ROOT / 'data' / 'xtracker'; CACHE.mkdir(parents=True, exist_ok=True)
def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}), timeout=60) as r:
        return json.loads(r.read())
ts = lambda s: int(dt.datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp())
iso = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime('%m-%d %H:%M')
def posts():
    f = CACHE / 'elon_posts.json'
    if f.exists() and time.time() - f.stat().st_mtime < 6 * 3600: return json.load(open(f))
    out = {}; t0 = ts('2026-09-20T00:00:00Z'); now = int(time.time())
    while t0 < now:
        t1 = min(now, t0 + 5 * 86400); z = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
        for p in get(f'https://xtracker.polymarket.com/api/users/elonmusk/posts?startDate={z(t0)}&endDate={z(t1)}')['data']:
            out[p['id']] = (ts(p['createdAt']), ts(p['importedAt']))
        t0 = t1; time.sleep(0.5)
    rows = sorted(out.values()); json.dump(rows, open(f, 'w')); return rows
P = posts(); PT = [a for a, _ in P]
tr = get('https://xtracker.polymarket.com/api/users/elonmusk/trackings?activeOnly=false')['data']
TR = {t['marketLink'].rstrip('/').split('/')[-1]: (ts(t['startDate']), ts(t['endDate']) + 1) for t in tr if t.get('marketLink')}
lag = [b - a for a, b in P if a > time.time() - 30 * 86400]; lag.sort()
print(f'posts cached {len(P)} from {iso(PT[0])} to {iso(PT[-1])}; trackings {len(TR)}')
print(f'tracker import lag (importedAt - createdAt), last 30 d, n={len(lag)}: median {lag[len(lag) // 2]} s, p10 {lag[len(lag) // 10]} s, p90 {lag[9 * len(lag) // 10]} s, p99 {lag[99 * len(lag) // 100]} s')
count = lambda a, b: bisect.bisect_left(PT, b) - bisect.bisect_left(PT, a)
def bucket(slug):
    m = re.search(r'-(\d+)-(\d+)$', slug)
    if m: return int(m.group(1)), int(m.group(2))
    m = re.search(r'-(\d+)plus$', slug) or re.search(r'-(\d+)-or-more$', slug)
    if m: return int(m.group(1)), 10 ** 6
    m = re.search(r'less-than-(\d+)$', slug) or re.search(r'-under-(\d+)$', slug)
    if m: return 0, int(m.group(1)) - 1
    return None
def event_of(slug):
    best = None
    for e in TR:
        if slug.startswith(e) and (best is None or len(e) > len(best)): best = e
    return best
for tag in sys.argv[1:]:
    d = json.load(open(tag + '.story.json')); wal = d['wallet']
    EV = collections.defaultdict(list)
    for m in d['markets']:
        e = event_of(m['slug'] or ''); b = bucket(m['slug'] or '')
        if e and b: EV[e].append((m, b))
    print(f"\n=== {tag}: {len(d['markets'])} markets -> {sum(len(v) for v in EV.values())} matched to {len(EV)} tracker events")
    bad = []; good = {}
    for e, v in EV.items():
        s, en = TR[e]; F = count(s, en); win = [b for m, b in v if m['resolved'] and m['final'] == 1.0]
        if en > time.time() or s < PT[0]: continue
        if win and not (win[0][0] <= F <= win[0][1]): bad.append((e, F, win[0])); continue
        good[e] = F
    print(f'  data check: {len(good)} events usable; tracker count outside the bucket that resolved Yes in {len(bad)}: {bad[:6]}')
    A = collections.defaultdict(lambda: [0, 0.0, 0.0, set()]); late = [0, 0.0, 0.0]; rows = []
    for e, F in good.items():
        s, en = TR[e]
        for m, (lo, hi) in EV[e]:
            if not m['resolved']: continue
            w = (hi - lo + 1) if hi < 10 ** 5 else 20
            for r in m['fills']:
                t = r['t']; N = count(s, min(t, en)); el = max(1, min(t, en) - s); proj = N + N / el * max(0, en - t) if t > s else None
                dead = N > hi or t >= en
                if dead: late[0] += 1; late[1] += r['usd']; late[2] += r['pnl']
                if proj is None: cls = 'before window opens'
                else:
                    off = ((lo + min(hi, lo + w - 1)) / 2 - proj) / w
                    cls = 'offset <=-2' if off <= -1.5 else 'offset -1' if off <= -0.5 else 'offset 0 (on pace)' if off < 0.5 else 'offset +1' if off < 1.5 else 'offset >=+2'
                h = (en - t) / 3600
                hb = '>72h' if h > 72 else '24-72h' if h > 24 else '6-24h' if h > 6 else '0-6h' if h > 0 else 'after'
                for k in (('pace', cls), ('hours', hb), ('pace x hours', cls + ' | ' + hb)):
                    a = A[k]; a[0] += 1; a[1] += r['usd']; a[2] += r['pnl']; a[3].add(e)
    for k in sorted(A):
        a = A[k]
        if a[1] > 150: print(f"  {k[0]:13} {k[1]:36} fills {a[0]:5} events {len(a[3]):3} usd {a[1]:8.0f} pnl {a[2]:9.0f} ({100 * a[2] / a[1]:7.1f}%)")
    print(f'  fills in a bucket already dead by arithmetic or after the window: {late[0]} fills usd {late[1]:.0f} pnl {late[2]:.0f}')
    if tag != sys.argv[1]: continue
    # market description: price of the eventual winner before the end (events from this story only)
    print('  price of the eventual winning bucket before the end (tape last print), and where the pace projection pointed:')
    res = collections.defaultdict(list)
    for e, F in sorted(good.items(), key=lambda kv: TR[kv[0]][1]):
        s, en = TR[e]; win = [(m, b) for m, b in EV[e] if m['resolved'] and m['final'] == 1.0]
        if not win: continue
        m, (lo, hi) = win[0]; w = hi - lo + 1 if hi < 10 ** 5 else 20
        tp = sorted((int(r['timestamp']), float(r['price']) if r.get('outcome') == m['first'] else 1 - float(r['price'])) for r in dataapi.iter_trades(condition=m['cond'], max_rows=40000))
        tt = [a for a, _ in tp]; line = f"    {e[20:62]:42} final {F:4} bucket {lo}-{hi if hi < 10 ** 5 else '+'}:"
        for hh in (48, 24, 12, 6, 2):
            t = en - hh * 3600; i = bisect.bisect_right(tt, t) - 1; px = tp[i][1] if i >= 0 else float('nan')
            N = count(s, t); proj = N + N / max(1, t - s) * (en - t); off = (F - proj) / w
            res[hh].append((px, off)); line += f" T-{hh}h px {px:.2f} need {F - N:3} proj-miss {off:+.1f}b |"
        print(line)
    for hh, v in res.items():
        px = sorted(x for x, _ in v if x == x)
        print(f"    T-{hh:2}h: winner price median {px[len(px) // 2]:.2f}, <=0.20 in {sum(1 for x in px if x <= 0.2)}/{len(px)} events, <=0.50 in {sum(1 for x in px if x <= 0.5)}/{len(px)}; |pace miss| median {st.median(abs(o) for _, o in v):.1f} buckets")
