import json, gzip, re, collections, statistics as S
from datetime import datetime, timezone
import sys; sys.path.insert(0,'.')
from recompute_v1 import T, evs, LO, HI
tr=json.load(open('/tmp/claude-0/-home-user/05556429-066d-541b-b886-b8da26bcc648/scratchpad/v1_audit_trades.json'))
E_={e['slug']:e for e in evs}
# event-level: startTime hour distribution, vs endDate, vs first close
rows=[]
for slug in {t['ev'] for t in tr}:
    e=E_[slug]; st=T(e['startTime']); ed=T(e.get('endDate')); 
    fc=min(T(m.get('closedTime')) for m in e['markets'] if T(m.get('closedTime')))
    lc=max(T(m.get('closedTime')) for m in e['markets'] if T(m.get('closedTime')))
    rows.append((slug,st,ed,fc,lc))
print('events',len(rows))
print('start hour UTC dist',collections.Counter(datetime.fromtimestamp(r[1],timezone.utc).strftime('%H:%M') for r in rows).most_common(8))
print('first_close - start hours quantiles',[round(q,1) for q in S.quantiles([(r[3]-r[1])/3600 for r in rows],n=10)])
print('endDate - start hours quantiles',[round(q,1) for q in S.quantiles([(r[2]-r[1])/3600 for r in rows if r[2]],n=10)])
# entries relative to first close
d=[(r[3]) for r in rows]
# per trade: hours before start and hours before first close of event
fcm={r[0]:r[3] for r in rows}
h=[(t['st']-t['t'])/3600 for t in tr]; hc=[(fcm[t['ev']]-t['t'])/3600 for t in tr]
print('entry hours before start q',[round(q,1) for q in S.quantiles(h,n=10)])
print('entry hours before first close q',[round(q,1) for q in S.quantiles(hc,n=10)])
# print a few 00:00Z examples
for r in rows[:12]:
    print(r[0][:70],datetime.fromtimestamp(r[1],timezone.utc).strftime('%m-%d %H:%M'),'end',datetime.fromtimestamp(r[2],timezone.utc).strftime('%m-%d %H:%M') if r[2] else None,'fclose',datetime.fromtimestamp(r[3],timezone.utc).strftime('%m-%d %H:%M'))
