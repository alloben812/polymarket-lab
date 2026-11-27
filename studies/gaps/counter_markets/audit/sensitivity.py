import sys; sys.path.insert(0,'/home/user/polymarket-lab/studies/gaps/counter_markets/audit')
import numpy as np, collections, math
import recompute as R
ev=R.events
G=(1,2,3,5,8,12,20,30,50,100,1000)
def nblogpmf(r,mu,k):
    mu=max(mu,0.05); return math.lgamma(r+k)-math.lgamma(k)-math.lgamma(r+1)+k*math.log(k/(k+mu))+r*math.log(mu/(k+mu))
def fitk(part='EARLY'):
    ks={}
    for h in (72,24,12,6):
        pr=[]
        for e in ev:
            if e['part']!=part: continue
            t=e['e']-h*3600
            if t-e['s']<86400: continue
            N=R.N_at(e,t); pr.append((e['F']-N, N*(e['e']-t)/(t-e['s'])))
        ks[h]=max(k for k in G if k<=100) if False else max([k for k in G if k<=100],key=lambda k:sum(nblogpmf(max(r,0),mu,k) for r,mu in pr))
    return ks
# information set B: reader of the source, created + 30 s
orig={id(e):e['imp'] for e in ev}
created={}
for e in ev:
    P=R.posts(e['handle']); w=P[(P[:,0]>=e['s'])&(P[:,0]<e['e'])]
    created[id(e)]=np.sort(w[:,0]+30)
for lab in ('imported (author)','created+30s (reads the source)'):
    for e in ev: e['imp']=orig[id(e)] if lab.startswith('imported') else created[id(e)]
    ks=fitk('EARLY'); print(lab,'k fitted on EARLY:',ks)
    for th in (0.05,0.10):
        for part in ('EARLY','LATE'):
            tr=R.run({part},theta=th,KS=ks); R.summarize(tr,f'  M1 theta {th} {part}')
    if lab.startswith('imported'):
        for k in (1,3,8,20):
            tr=R.run({'LATE'},theta=0.10,KS={72:k,24:k,12:k,6:k}); R.summarize(tr,f'  sens: LATE theta 0.10 uniform k={k}')
