"""Is the scheduled start (gameStartTime) treated the same for walkovers and played matches? Compare gamma gameStartTime vs event startTime, and match duration (closed-start) for controls; lead of first print per class."""
import sys, gzip, json, statistics as st; sys.path.insert(0,'.')
from a1_recompute import *
import datetime as dt
def ts(s):
    if not s: return None
    s=str(s).strip().replace(' ','T')
    if s.endswith('+00'): s+=':00'
    if s.endswith('Z'): s=s[:-1]+'+00:00'
    try: d=dt.datetime.fromisoformat(s)
    except Exception: return None
    if d.tzinfo is None: d=d.replace(tzinfo=dt.timezone.utc)
    return d.timestamp()
A={r['slug'] for r in U['A']}; C={r['slug'] for r in U['control']}
diff={'A':[], 'C':[]}; dur={'A':[], 'C':[]}
with gzip.open('/home/user/polymarket-lab/data/gaps_tennis_wo/events.jsonl.gz','rt') as f:
    for l in f:
        ev=json.loads(l); s=ev.get('slug')
        k='A' if s in A else 'C' if s in C else None
        if not k: continue
        ml=[m for m in ev['markets'] if m.get('sportsMarketType')=='moneyline']
        if not ml: continue
        m=ml[0]; g=ts(m.get('gameStartTime')); e=ts(ev.get('startTime')); c=ts(m.get('closedTime'))
        if g and e: diff[k].append((g-e)/3600)
        if g and c: dur[k].append((c-g)/3600)
for k in 'AC':
    d=diff[k]; print(k,'n',len(d),'gameStart-eventStart: share !=0 %.3f'%(sum(1 for x in d if abs(x)>1e-6)/len(d)),'median',st.median(d))
    d=dur[k]; qs=st.quantiles(d,n=10); print('  closed-gameStart hours deciles',[round(x,1) for x in qs])
# first-print lead per class
for cls,recs in (('A',U['A']),('C',U['control'])):
    leads=[]; n=0
    for r in recs:
        if cls=='A':
            m=[x for x in r['markets'] if x['type']=='moneyline'][0]; cid,outs,start=m['cid'],m['outcomes'],m['start'] or r['startTime']
        else: cid,outs,start=r['cid'],r['outcomes'],r['start']
        tp=load(cid); n+=1
        if not tp: continue
        leads.append((start-(min(x['t'] for x in tp)-3))/3600)
    qs=st.quantiles(leads,n=10); print(cls,'tapes',len(leads),'of',n,'first-print lead hours deciles',[round(x,1) for x in qs])
