# Verification check (stated before running): paper rule = YES price in [0.75,0.95], buy NO at 1-p (and at 1-p+0.02), fee 0.01*p*(1-p), hold to settlement.
# One entry per market per time point; time points local 07,09,11,13,15 h (peak assumed ~15 h local); cluster by event. Data: lab cache (30-min prices-history).
import json,bisect,collections,datetime as dt,re
B='/home/user/polymarket-lab/studies/wallets/weather/out/'
MK=json.load(open(B+'mk.json')); PX=json.load(open(B+'px.json'))
k=next(iter(MK)); print('sample mk',{a:(b if not isinstance(b,(dict,list)) else str(b)[:80]) for a,b in MK[k].items()})
ests=[d['est'] for d in MK.values() if 'est' in d and d.get('final')]; print('markets',len(MK),'with px',sum(1 for c in PX if PX[c]),'est range',dt.datetime.utcfromtimestamp(min(ests)),dt.datetime.utcfromtimestamp(max(ests)))
TEN=('atlanta','nyc','new-york','chicago','seattle','london','seoul','miami','shanghai','toronto','tokyo')
def at(pts,t):
    ts=[p[0] for p in pts]; i=bisect.bisect_right(ts,t)-1
    return pts[i][1] if i>=0 and t-pts[i][0]<=2*3600 else None
def ts(v):
    n=len(v)
    if n<3: return float('nan')
    mu=sum(v)/n; se=(sum((x-mu)**2 for x in v)/(n-1)/n)**0.5
    return mu/se if se else float('nan')
for sub in ('all48','paper10'):
  for off in (7,9,11,13,15):
    ev=collections.Counter(); ev2=collections.Counter(); n=0; w=0; cost=0; cost2=0; sp=0
    for c,pts in PX.items():
        d=MK[c]
        if not pts or 'est' not in d or not d.get('final'): continue
        if sub=='paper10' and not any(('-in-'+x+'-') in d['event'] for x in TEN): continue
        p=at(pts,d['est']+off*3600)
        if p is None or not(0.75<=p<=0.95): continue
        y=float(d['final']['Yes']); r=1-p; fee=0.01*r*(1-r)
        ev[d['event']]+=(1-y)-r-fee; ev2[d['event']]+=(1-y)-(r+0.02)-fee; n+=1; w+=1-y; cost+=r; cost2+=r+0.02; sp+=p
    if n: print(f'{sub} local {off:02d}h: n={n} events={len(ev)} meanYES={sp/n:.3f} NOwin={w/n:.3f} (implied {1-sp/n:.3f})  ret@mid={100*sum(ev.values())/cost:+.1f}% t={ts(list(ev.values())):.2f}  ret@+2c={100*sum(ev2.values())/cost2:+.1f}% t={ts(list(ev2.values())):.2f}')
