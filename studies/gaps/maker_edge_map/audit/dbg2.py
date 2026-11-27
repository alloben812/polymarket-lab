import sys, json, pandas as pd, numpy as np
sys.path.insert(0,'.')
import recompute as R
D=R.D
S=json.load(open(D+"/sample_ext.json")); F=pd.read_parquet(D+"/fills_ext.parquet")
r=[r for r in S if r["slug"]=="btc-updown-5m-1795491600"][0]
g=F[(F.cid==r["conditionId"])&(F["var"]=="V2o")]
theirs=sorted(zip(g.tf.round(0), g.q.round(3)))
# mine: instrument
import bisect
P=R.load(r); bk=R.Book(P); tt=[p[0] for p in P]
tres=R.parse(r["closedTime"]); tick=float(r["orderPriceMinTickSize"] or .01); t0=P[0][0]
mine=[]; k=0
while t0+10*k<tres:
    tau=t0+10*k; k+=1
    b,a=bk.bid(tau,900),bk.ask(tau,900)
    if b is None or a is None: continue
    b=round(b/tick)*tick; a=round(a/tick)*tick
    if not (a>b+1e-9 and b>1e-9 and a<1-1e-9): continue
    i=bisect.bisect_right(tt,tau+2)
    while i<len(P) and tt[i]<=tau+10:
        t,x,isask,z=P[i]; i+=1
        if not isask and x<=b+1e-9: mine.append((round(t),round(b,3))); break
    i=bisect.bisect_right(tt,tau+2)
    while i<len(P) and tt[i]<=tau+10:
        t,x,isask,z=P[i]; i+=1
        if isask and x>=a-1e-9: mine.append((round(t),round(1-a,3))); break
mine.sort()
print(len(mine),len(theirs)); 
ms=set(mine); ts=set(theirs)
print("only theirs",sorted(ts-ms)[:10]); print("only mine",sorted(ms-ts)[:10])
print(tick, r["orderPriceMinTickSize"])
