import sys; sys.path.insert(0,'/home/user/polymarket-lab/studies/gaps/counter_markets/audit')
import numpy as np, collections, math
import recompute as R
ev=R.events
# lag-contaminated events: any post counted in window imported > 1h after creation
for e in ev:
    P=R.posts(e['handle']); w=P[(P[:,0]>=e['s'])&(P[:,0]<e['e'])]
    e['maxlag']=int((w[:,1]-w[:,0]).max()) if len(w) else 0
    e['nlag']=int(((w[:,1]-w[:,0])>3600).sum())
bad=[e for e in ev if e['nlag']>0]
print('events with posts imported >1h late:', len(bad), 'early', sum(e['part']=='EARLY' for e in bad), 'late', sum(e['part']=='LATE' for e in bad))
for e in bad[:30]: print(' ', e['slug'][:55], e['part'], e['nlag'], e['maxlag'])
# k MLE on EARLY, all vs clean
def nblogpmf(r,mu,k):
    mu=max(mu,0.05); return math.lgamma(r+k)-math.lgamma(k)-math.lgamma(r+1)+k*math.log(k/(k+mu))+r*math.log(mu/(k+mu))
G=(1,2,3,5,8,12,20,30,50,100,1000)
for lab,sel in (('EARLY all',lambda e:e['part']=='EARLY'),('EARLY clean',lambda e:e['part']=='EARLY' and e['nlag']==0),('LATE (in-sample, descriptive)',lambda e:e['part']=='LATE')):
    res={}
    for h in (72,24,12,6):
        pr=[]
        for e in ev:
            if not sel(e): continue
            t=e['e']-h*3600
            if t-e['s']<86400: continue
            N=R.N_at(e,t); pr.append((e['F']-N, N*(e['e']-t)/(t-e['s'])))
        res[h]=(max(G,key=lambda k:sum(nblogpmf(max(r,0),mu,k) for r,mu in pr)),len(pr))
    print(lab,res)
