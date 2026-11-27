"""Build the market universe (metadata only, no outcome statistics). Output: data/gaps_mentions_model/universe.json"""
import json, re, os, datetime as dt, collections, sys
from pmlab import gamma
D = '/home/user/polymarket-lab/data/gaps_mentions_model'
TAPES = '/home/user/polymarket-lab/data/mentions_tapes'
def ts(s):
    if not s: return None
    s = s.replace(' ', 'T').replace('+00', '+00:00') if s.endswith('+00') else s
    try: return dt.datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp()
    except Exception: return None
PERIOD = ('this-week', 'in-october', 'in-november', 'in-december', 'in-september', 'in-august', 'in-july', 'in-june',
          'headlines', 'this-month', 'week-of', 'by-', 'in-2026', 'this-year')
def etype(slug):
    if 'earnings-call' in slug or 'earnings' in slug: return 'earnings'
    if any(k in slug for k in PERIOD): return 'period'
    return 'live'
def parse_q(q):
    ql = (q or '').lower().replace('“', '"').replace('”', '"')
    m = re.match(r'will (.+?) (?:say|mention)\b', ql)
    spk = m.group(1).strip() if m else None
    if spk: spk = re.sub(r'^(donald |president |the )', '', spk)
    terms = '|'.join(sorted(t.strip() for t in re.findall(r'"([^"]+)"', ql)))
    n = re.search(r'(\d+)\+\s*times', ql)
    return spk, terms, int(n.group(1)) if n else 0
evs = json.load(open(f'{D}/events_closed_raw.json'))
U = []
for e in evs:
    st = ts(e.get('startTime')); cr = ts(e.get('creationDate') or e.get('createdAt'))
    mk = []
    for m in e.get('markets') or []:
        try: op = [float(x) for x in gamma.jfield(m.get('outcomePrices'))]
        except Exception: continue
        outs = gamma.jfield(m.get('outcomes'))
        if sorted(op) != [0.0, 1.0] or outs != ['Yes', 'No']: continue
        spk, terms, n = parse_q(m.get('question'))
        mk.append(dict(c=m['conditionId'], q=m.get('question'), event=e['slug'], closed=ts(m.get('closedTime')), fy=op[0],
                       vol=float(m.get('volumeNum') or 0), spk=spk, terms=terms, n=n, ft=m.get('feeType')))
    if not mk: continue
    first_close = min((x['closed'] for x in mk if x['closed']), default=None)
    ok = bool(st and cr and st - cr >= 3600 and first_close and st <= first_close)
    for x in mk:
        x.update(start=st if ok else None, start_ok=ok, type=etype(e['slug']))
        U.append(x)
json.dump(U, open(f'{D}/universe.json', 'w'))
cached = set(f[:-8] for f in os.listdir(TAPES))
lo, hi = dt.datetime(2026, 8, 1, tzinfo=dt.timezone.utc).timestamp(), dt.datetime(2026, 11, 28, tzinfo=dt.timezone.utc).timestamp()
sel = [x for x in U if x['start_ok'] and lo <= x['start'] < hi and x['type'] != 'period']
print('universe binary markets', len(U), 'start_ok', sum(x['start_ok'] for x in U))
print('Aug1-Nov27 live/earnings with valid start:', len(sel), 'events', len({x['event'] for x in sel}), 'cached tapes', sum(x['c'] in cached for x in sel))
print('by type', collections.Counter(x['type'] for x in sel), 'with speaker', sum(1 for x in sel if x['spk']))
allp = [x for x in U if x['closed'] and lo <= x['closed'] < hi]
print('all Aug1-Nov27 by closed:', len(allp), 'events', len({x['event'] for x in allp}), 'type', collections.Counter(x['type'] for x in allp), 'start_ok share', sum(x['start_ok'] for x in allp)/len(allp))
print('speakers top', collections.Counter(x['spk'] for x in sel).most_common(15))
