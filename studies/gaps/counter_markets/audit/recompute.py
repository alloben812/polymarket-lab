"""Independent recomputation of the selected variant (M1 pace, theta 0.10, $20 cap) on the LATE half.
Own code: own bucket parser, own NB cdf (scipy), own fill loop. Reads only cached data in data/gaps_counter/.
python3 -I recompute.py"""
import bisect, gzip, json, re, sys, collections
from pathlib import Path
import numpy as np
D = Path('/home/user/polymarket-lab/data/gaps_counter')
META = json.load(open(D / 'events_meta.json'))
KS = {72: 3, 24: 1, 12: 1, 6: 1}   # dispersions the author fitted on EARLY (refit below as a check)

def bounds(slug):
    tail = slug.split('of-tweets-')[-1] if False else slug
    m = re.search(r'-(\d+)-(\d+)$', slug)
    if m: return int(m[1]), int(m[2])
    m = re.search(r'-(\d+)-?plus$|-(\d+)-or-more$', slug)
    if m: return int(m[1] or m[2]), 10**7
    m = re.search(r'less-than-(\d+)$|-under-(\d+)$', slug)
    if m: return 0, int(m[1] or m[2]) - 1
    raise ValueError(slug)

cache = {}
def posts(h):
    if h not in cache:
        P = json.load(open(D / 'posts' / f'{h}.json')); cache[h] = np.array(P, dtype=np.int64)
    return cache[h]

events = []
for ev in META:
    mk = []
    ok = True
    for m in ev['markets']:
        pr = [float(x) for x in m['prices']]
        if not m['closed'] or sorted(pr) != [0.0, 1.0]: ok = False; break
        mk.append((bounds(m['slug']), m, pr[m['outcomes'].index('Yes')]))
    if not ok: continue
    P = posts(ev['handle'])
    inwin = P[(P[:, 0] >= ev['s']) & (P[:, 0] < ev['e'])]
    ev = dict(ev, mk=sorted(mk, key=lambda x: x[0]), imp=np.sort(inwin[:, 1]), F=len(inwin))
    events.append(ev)
events.sort(key=lambda x: x['e'])
half = len(events) // 2
for i, ev in enumerate(events): ev['part'] = 'EARLY' if i < half else 'LATE'
print('usable events', len(events), 'early', half, 'late', len(events) - half)

def N_at(ev, t): return int(np.searchsorted(ev['imp'], t, side='right'))
def fee(c): return 0.01 * c * (1 - c)

tapes = {}
def tape(cid):
    if cid not in tapes:
        rows = json.load(gzip.open(D / 'tapes' / f'{cid}.json.gz', 'rt'))
        rows.sort(key=lambda r: r['t']); tapes[cid] = ([r['t'] for r in rows], rows)
    return tapes[cid]

LF = np.concatenate([[0.0], np.cumsum(np.log(np.arange(1, 20001)))])  # log n!
def nbcdf(x, mu, k):
    # NB(k, mean mu), integer k: pmf(r) = C(r+k-1, r) p^k (1-p)^r, p = k/(k+mu); P(R <= x)
    if x < 0: return 0.0
    x = min(x, 6000); r = np.arange(0, x + 1); p = k / (k + mu)
    lp = LF[r + k - 1] - LF[k - 1] - LF[r] + k * np.log(p) + r * np.log1p(-p)
    return float(min(1.0, np.exp(lp).sum()))
def qbucket(mu, k, N, lo, hi):
    mu = max(mu, 0.05)
    return max(0.0, nbcdf(hi - N, mu, k) - nbcdf(lo - 1 - N, mu, k))

def run(parts, theta=0.10, cap=20.0, KS=KS, rate=0.01, wkend_only=None):
    out = []
    for ev in events:
        if ev['part'] not in parts: continue
        for h in (72, 24, 12, 6):
            t = ev['e'] - h * 3600
            if t - ev['s'] < 86400: continue
            prints = []
            for (lo, hi), m, yes in ev['mk']:
                yi = m['outcomes'].index('Yes'); ytok, ntok = m['toks'][yi], m['toks'][1 - yi]
                ts, rows = tape(m['cid'])
                for r in rows[bisect.bisect_left(ts, t + 3):]:
                    mt = r['t'] - 3
                    if mt > t + 1800: break
                    if r['side'] == 'BUY': tok, c = r['tok'], r['p']
                    else: tok, c = (ntok if r['tok'] == ytok else ytok), 1 - r['p']
                    prints.append((mt, lo, hi, tok == ytok, c, r['s'], yes, m['cid']))
            prints.sort(key=lambda x: x[0]); done = set()
            for mt, lo, hi, isyes, c, sz, yes, cid in prints:
                if (cid, isyes) in done or not (0.02 <= c <= 0.97): continue
                N = N_at(ev, mt); mu = N * (ev['e'] - mt) / (mt - ev['s'])
                q = qbucket(mu, KS[h], N, lo, hi); q = q if isyes else 1 - q
                if q - c - rate * c * (1 - c) < theta: continue
                done.add((cid, isyes)); sh = min(sz, cap / c); pay = yes if isyes else 1 - yes
                out.append(dict(event=ev['slug'], handle=ev['handle'], part=ev['part'], h=h, mt=mt, c=c, q=q, sh=sh, usd=sh * c,
                                pnl=sh * (pay - c - rate * c * (1 - c)), win=pay, e=ev['e'], s=ev['s'], bucket=(lo, hi), isyes=isyes))
    return out

def summarize(tr, label):
    by = collections.defaultdict(float); usd = collections.defaultdict(float)
    for x in tr: by[x['event']] += x['pnl']; usd[x['event']] += x['usd']
    n = len(tr); tot = sum(by.values()); sp = sum(usd.values())
    best = max(by, key=by.get); rest = sum(v for k, v in by.items() if k != best) / sum(v for k, v in usd.items() if k != best)
    num = np.array([by[k] for k in by]); den = np.array([usd[k] for k in by]); r = num.sum() / den.sum()
    se = np.sqrt(len(num) / (len(num) - 1) * np.sum((num - r * den) ** 2) / den.sum() ** 2)
    print(f'{label}: entries {n} events {len(by)} spent ${sp:,.0f} net ${tot:+.1f} = {100*tot/sp:+.1f}% of $, t {r/se:+.2f}, w/o best event {100*rest:+.1f}%')
    return by

if __name__ == '__main__':
    late = run({'LATE'}); summarize(late, 'M1 theta0.10 $20 LATE (independent)')
    early = run({'EARLY'}); summarize(early, 'M1 theta0.10 $20 EARLY (independent)')
    import pickle; pickle.dump((late, early), open('/tmp/m1_audit.pkl', 'wb'))
