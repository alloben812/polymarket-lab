"""Blind screen: what do the candidate accounts trade right now? (no PnL here)"""
import sys, time, json, collections
from concurrent.futures import ThreadPoolExecutor
from pmlab import wallet, gamma
import re
ES = re.compile(r'^(cs2|csgo|lol|dota2|dota|val|valorant|cod|r6|rl|ow|mlbb|hok|sc2|pubg|apex|kog|wr|ff|eafc|sf6|codmw|rocket|league-of-legends|counter-strike|honor|crossfire|lolw|cs)-')
names = sys.argv[1:]
board = {r['name']: r['wallet'] for r in json.load(open('studies/wallets/esports/leaders_top60.json'))['rows']} if False else None
def scr(nw):
    name, w = nw
    end = int(time.time()); start = end - 7*86400
    try:
        fills, trunc = wallet.fetch_fills(w, start, end, max_fills=3000)
    except Exception as e:
        return name, str(e)[:60]
    usd = collections.Counter(); pref = collections.Counter(); mk = 0; tot = 0; conds=set(); buys=0
    for f in fills:
        d = float(f['size'])*float(f['price']); tot += d
        s = f.get('slug') or ''
        p = s.split('-')[0]
        pref[p] += d
        if ES.match(s): usd['es'] += d
        if f['role']=='M': mk += d
        if f['side']=='BUY': buys += d
        conds.add(f['condition_id'])
    span = (max(f['timestamp'] for f in fills)-min(f['timestamp'] for f in fills))/86400 if fills else 0
    top = ' '.join(f"{k}:{v/tot*100:.0f}" for k,v in pref.most_common(6)) if tot else ''
    return name, f"fills={len(fills):5d}{'T' if trunc else ' '} span={span:4.1f}d mkts={len(conds):4d} usd={tot:10,.0f} es%={usd['es']/tot*100 if tot else 0:3.0f} maker%={mk/tot*100 if tot else 0:3.0f} buy%={buys/tot*100 if tot else 0:3.0f} | {top}"
rows = json.load(open('studies/wallets/esports/leaders_top60.json'))
rows = rows['rows'] if isinstance(rows, dict) else rows
want = [(r['name'], r['wallet']) for r in rows if r['name'] in names]
with ThreadPoolExecutor(6) as ex:
    for name, s in ex.map(scr, want):
        print(f"{name[:24]:24s} {s}", flush=True)
