"""Download posts, events and whole-market tapes for post-count events (protocol.md, family A).
python3 -I fetch.py   (writes only to data/gaps_counter/)"""
import datetime as dt, gzip, json, re, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT))
from pmlab import dataapi, gamma
D = ROOT / 'data' / 'gaps_counter'; (D / 'tapes').mkdir(parents=True, exist_ok=True); (D / 'posts').mkdir(exist_ok=True)
HANDLES = ['elonmusk', 'realDonaldTrump', 'WhiteHouse', 'ZelenskyyUa', 'NYCMayor', 'cz_binance', 'tedcruz', 'khamenei_ir']
STOP = dt.datetime(2026, 11, 27, 19, 40, tzinfo=dt.timezone.utc).timestamp()
ts = lambda s: int(dt.datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp())
z = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
def get(u):
    for i in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}), timeout=60) as r: return json.loads(r.read())
        except Exception as e: print('retry', u[:90], e, flush=True); time.sleep(3 * (i + 1))
    raise RuntimeError(u)
def posts(h):
    f = D / 'posts' / f'{h}.json'
    if f.exists(): return
    out = {}; t0 = ts('2026-08-26T00:00:00Z'); now = int(time.time())
    while t0 < now:
        t1 = min(now, t0 + 5 * 86400)
        for p in get(f'https://xtracker.polymarket.com/api/users/{h}/posts?startDate={z(t0)}&endDate={z(t1)}')['data']:
            out[p['id']] = (ts(p['createdAt']), ts(p['importedAt']))
        t0 = t1; time.sleep(0.3)
    json.dump(sorted(out.values()), open(f, 'w')); print('posts', h, len(out), flush=True)
def events():
    EV = []
    for h in HANDLES:
        for t in json.load(open(D / f'xt_trackings_{h}.json')):
            if not t.get('marketLink'): continue
            s, e = ts(t['startDate']), ts(t['endDate']) + 1
            days = round((e - s) / 86400)
            if days in (2, 7) and ts('2026-10-01T00:00:00Z') <= e <= ts('2026-11-27T17:00:01Z'):
                EV.append({'handle': h, 's': s, 'e': e, 'days': days, 'slug': t['marketLink'].rstrip('/').split('/')[-1]})
    EV.sort(key=lambda x: -x['e']); return EV
def tape(cid):
    f = D / 'tapes' / f'{cid}.json.gz'
    if f.exists(): return
    rows = [{'t': r['timestamp'], 'tok': r['token_id'], 'side': r['side'], 'p': float(r['price']), 's': float(r['size'])}
            for r in dataapi.iter_trades(condition=cid, taker_only=True)]
    json.dump(rows, gzip.open(f, 'wt'))
if __name__ == '__main__':
    for h in HANDLES: posts(h)
    EV = events(); print('events in range', len(EV), flush=True)
    meta = []; mf = D / 'events_meta.json'
    with ThreadPoolExecutor(3) as ex:
        for i, ev in enumerate(EV):
            if time.time() > STOP: print('STOP rule hit at event', i, flush=True); break
            g = gamma.event_by_slug(ev['slug'])
            if not g: print('no gamma event', ev['slug'], flush=True); continue
            mk = []
            for m in g.get('markets') or []:
                mk.append({'slug': m.get('slug'), 'cid': m.get('conditionId'), 'toks': gamma.jfield(m.get('clobTokenIds')),
                           'outcomes': gamma.jfield(m.get('outcomes')), 'prices': gamma.jfield(m.get('outcomePrices')),
                           'closed': m.get('closed'), 'fee': m.get('feeType'), 'vol': m.get('volumeNum')})
            list(ex.map(tape, [m['cid'] for m in mk if m['cid']]))
            meta.append({**ev, 'volume': g.get('volume'), 'markets': mk})
            json.dump(meta, open(mf, 'w'))
            print(i, ev['slug'], len(mk), round(time.time()), flush=True)
    print('done', len(meta), flush=True)
