"""Sub-family breakdown of a story file: where inside 'culture' the money comes from (unit = market, and = event)."""
import json, re, sys, collections, statistics as st
RULES = [('elon-tweets', r'elon-musk-of-tweets|elon-musk.*tweets'), ('box-office', r'box-office|domestic|opening-weekend|gross'),
         ('spotify', r'spotify|monthly-listeners'), ('billboard', r'billboard|hot-100|song-in-the-us|us-song|top-song|song-this-week|-song-'),
         ('album', r'album|first-week-sales'), ('youtube-views', r'mrbeast|views|trailer'), ('streamers', r'kai-cenat|ishowspeed|xqc|jynxzi|stream|marathon|twitch|kick'),
         ('awards', r'oscar|grammy|emmy|golden-globe|award|nominat'), ('rt/metacritic', r'rotten|tomatometer|metascore|metacritic'),
         ('games', r'gta|game'), ('celebrity', r'james-bond|announced|taylor|kanye|divorce|engaged|pregnan|married'),
         ('sports', r'^(nba|nfl|nhl|mlb|cbb|cfb|epl|ucl|atp|wta|ufc|dota|lol|cs2|val)-|-vs-|spread|total-'),
         ('mcap/fin', r'market-cap|largest-company|treasury|yield|fed-|stock|ipo')]
def fam(s):
    for n, r in RULES:
        if re.search(r, s or ''): return n
    return 'other'
tag = sys.argv[1]; d = json.load(open(tag + '.story.json'))
G = collections.defaultdict(list)
for m in d['markets']: G[fam(m['slug'])].append(m)
print(f"{tag}: {len(d['markets'])} markets")
print(f"  {'subfamily':14} {'mkts':>4} {'res':>4} {'win':>4} {'usd':>8} {'pnl_res':>8} {'%usd':>6} {'t_mkt':>6} {'open_mtm':>8} {'taker%':>6} {'medH2end':>8} {'beforeT90%':>10}")
for k, v in sorted(G.items(), key=lambda kv: -sum(sum(r['usd'] for r in m['fills']) for m in kv[1])):
    res = [m for m in v if m['resolved']]; pn = [m['pnl'] for m in res]
    usd = sum(r['usd'] for m in res for r in m['fills']) or 1
    allf = [r for m in v for r in m['fills']]; u = sum(r['usd'] for r in allf) or 1
    t = (st.mean(pn) / (st.stdev(pn) / len(pn) ** .5)) if len(pn) > 2 and st.stdev(pn) > 0 else float('nan')
    h = sorted(r['h_to_end'] for r in allf if r['h_to_end'] is not None)
    b90 = sum(r['usd'] for m in res for r in m['fills'] if not r['after90']) / usd
    print(f"  {k:14} {len(v):4} {len(res):4} {sum(1 for x in pn if x > 0):4} {u:8.0f} {sum(pn):8.0f} {100 * sum(pn) / usd:6.1f} {t:6.2f} {sum(m['pnl'] for m in v if not m['resolved']):8.0f} "
          f"{100 * sum(r['usd'] for r in allf if r['role'] == 'T') / u:6.0f} {h[len(h) // 2] if h else float('nan'):8.0f} {100 * b90:10.0f}")
# event level (strip the trailing bucket numbers) for bucket families
E = collections.defaultdict(lambda: [0.0, 0.0, 0, 0])
for m in d['markets']:
    if not m['resolved']: continue
    ev = re.sub(r'(-\d+){1,3}$|-(less-than|at-least|between|more-than|exactly|under|over)-.*$|-\d+m.*$', '', re.sub(r'-(\d+)-(\d+)$', '', m['slug'] or ''))
    e = E[(fam(m['slug']), ev)]; e[0] += m['pnl']; e[1] += sum(r['usd'] for r in m['fills']); e[2] += 1
by = collections.defaultdict(list)
for (f, ev), e in E.items(): by[f].append(e[0])
print('  event level (resolved):')
for f, pn in sorted(by.items(), key=lambda kv: -len(kv[1])):
    if len(pn) < 3: continue
    t = st.mean(pn) / (st.stdev(pn) / len(pn) ** .5) if st.stdev(pn) > 0 else float('nan')
    print(f"    {f:14} events {len(pn):3} winners {sum(1 for x in pn if x > 0):3} total {sum(pn):8.0f} mean {st.mean(pn):7.0f} median {st.median(pn):7.0f} worst {min(pn):7.0f} best {max(pn):7.0f} t {t:5.2f}")
