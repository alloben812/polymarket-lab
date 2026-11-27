# Same rule as scan.py; only the "fully quoted" definition is split by side (asks for long, bids for short),
# to match the researcher's universe. Counted as variant 2 of the verification scan.
import json,urllib.request,gzip,statistics as st,time
def get(u):
    r=urllib.request.Request(u,headers={'Accept-Encoding':'gzip','User-Agent':'research-client'})
    b=urllib.request.urlopen(r,timeout=60).read()
    try: b=gzip.decompress(b)
    except Exception: pass
    return json.loads(b)
B='https://gamma-api.polymarket.com'
evs=[]
for off in range(0,400,100):
    evs+=get(B+f'/events?closed=false&active=true&order=volume24hr&ascending=false&limit=100&offset={off}'); time.sleep(0.3)
n=0;la=[];lb=[];L=[];S=[];Lnet=[];Snet=[]
for e in evs:
    if not e.get('negRisk'): continue
    ms=[m for m in (e.get('markets') or []) if not m.get('closed') and m.get('active')]
    if len(ms)<2: continue
    n+=1
    aug=bool(e.get('negRiskAugmented'))
    rate=[float((m.get('feeSchedule') or {}).get('rate') or 0) for m in ms]
    asks=[m.get('bestAsk') for m in ms]; bids=[m.get('bestBid') for m in ms]
    if all(a is not None for a in asks):
        A=sum(map(float,asks)); fa=sum(r*float(a)*(1-float(a)) for r,a in zip(rate,asks)); la.append(A)
        if A<1: L.append((e['slug'],len(ms),round(A,4),round(fa,4),aug))
        if A+fa<1 and not aug: Lnet.append(e['slug'])
    if all(b is not None for b in bids):
        Bd=sum(map(float,bids)); fb=sum(r*float(b)*(1-float(b)) for r,b in zip(rate,bids)); lb.append(Bd)
        if Bd>1: S.append((e['slug'],len(ms),round(Bd,4),round(fb,4),aug))
        if Bd-fb>1: Snet.append(e['slug'])
print('negRisk',n,'asks-complete',len(la),'median',round(st.median(la),4),'bids-complete',len(lb),'median',round(st.median(lb),4))
print('long raw',len(L),'augmented',sum(1 for x in L if x[4]),'non-aug:',[x for x in L if not x[4]],'net exec',Lnet)
print('short raw',len(S),S,'net exec',Snet)
