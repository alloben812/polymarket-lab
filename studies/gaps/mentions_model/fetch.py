"""Download missing whole-market tapes for the protocol sample into data/mentions_tapes (same format as before)."""
import json, gzip, os, sys, datetime as dt, time
from concurrent.futures import ThreadPoolExecutor
from pmlab import dataapi
TAPES = '/home/user/polymarket-lab/data/mentions_tapes'
U = json.load(open('/home/user/polymarket-lab/data/gaps_mentions_model/universe.json'))
lo = dt.datetime(2026, 8, 1, tzinfo=dt.timezone.utc).timestamp(); hi = dt.datetime(2026, 11, 28, tzinfo=dt.timezone.utc).timestamp()
sel = [x for x in U if x['start_ok'] and lo <= x['start'] < hi and x['type'] != 'period']
sel.sort(key=lambda x: -x['start'])  # newest first: if time runs out the cut is by date (protocol rule)
todo = [x['c'] for x in sel if not os.path.exists(f"{TAPES}/{x['c']}.json.gz")]
print('to fetch', len(todo), flush=True)
def get(c):
    p = f"{TAPES}/{c}.json.gz"
    try:
        rows = [dict(t=r['timestamp'], w=r['proxy_wallet'], side=r['side'], o=r['outcome'], p=float(r['price']), s=float(r['size'])) for r in dataapi.iter_trades(condition=c)]
    except Exception as e:
        return c, 'ERR ' + str(e)[:80]
    rows.sort(key=lambda r: r['t'])
    tmp = p + '.tmp'; json.dump(rows, gzip.open(tmp, 'wt')); os.replace(tmp, p)
    return c, len(rows)
t0 = time.time(); done = 0
with ThreadPoolExecutor(3) as ex:
    for c, n in ex.map(get, todo):
        done += 1
        if done % 100 == 0 or str(n).startswith('ERR'): print(done, c[:10], n, round(time.time() - t0), flush=True)
print('done', done, round(time.time() - t0), flush=True)
