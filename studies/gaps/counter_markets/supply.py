"""Family B (and A) supply: events and volume per ISO week, ended 2026-10-01 .. 2026-11-27 (protocol.md).
python3 -I supply.py > out/supply.txt"""
import collections, datetime as dt, json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT))
from pmlab import http
FAM = {'box-office': r'box-office|domestic-gross|opening-weekend', 'billboard': r'billboard', 'spotify': r'spotify',
       'rotten-tomatoes': r'rotten-tomatoes', 'app-store': r'app-store', 'youtube': r'views'}
ts = lambda s: dt.datetime.fromisoformat(s.replace('Z', '+00:00'))
seen = {}; rows = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0.0]))
for tag, pat in FAM.items():
    off = 0
    while True:
        d = http.get_json('https://gamma-api.polymarket.com/events', {'tag_slug': tag, 'closed': 'true', 'limit': 50, 'offset': off,
                          'end_date_min': '2026-10-01T00:00:00Z', 'end_date_max': '2026-11-28T00:00:00Z'}, cache=True)
        for e in d:
            if e['slug'] in seen or not re.search(pat, e['slug']) or not e.get('endDate'): continue
            seen[e['slug']] = tag; w = ts(e['endDate']).strftime('%G-W%V')
            rows[tag][w][0] += 1; rows[tag][w][1] += float(e.get('volume') or 0)
        if len(d) < 50: break
        off += 50
A = json.load(open(ROOT / 'data' / 'gaps_counter' / 'events_meta.json'))
for ev in A:
    w = dt.datetime.fromtimestamp(ev['e'], dt.timezone.utc).strftime('%G-W%V'); g = 'posts-elon' if ev['handle'] == 'elonmusk' else 'posts-other'
    rows[g][w][0] += 1; rows[g][w][1] += float(ev.get('volume') or 0)
wks = sorted({w for r in rows.values() for w in r})
print('events per ISO week (closed, end date in week) / total volume $K; posts-* from the study sample (may be cut by the budget rule)')
print(f"{'family':16}" + ''.join(f'{w[-3:]:>11}' for w in wks) + '   events/wk  $K/wk')
for f in sorted(rows):
    r = rows[f]; n = sum(v[0] for v in r.values()); v = sum(v[1] for v in r.values())
    print(f'{f:16}' + ''.join(f"{r[w][0]:4}/{r[w][1] / 1e3:6.0f}" if w in r else f"{'':11}" for w in wks) + f'   {n / len(wks):8.1f} {v / 1e3 / len(wks):7.0f}')
