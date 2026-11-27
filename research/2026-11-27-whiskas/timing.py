import json,sys,collections,re,statistics as st
rows=[json.loads(l) for l in open(sys.argv[1])]
res=json.load(open(sys.argv[2])); FEE=0.05
for r in rows:
    r['t0']=int(re.search(r'-(\d{9,})$',r['slug']).group(1)); r['dt']=r['timestamp']-r['t0']
    rv=res[r['condition_id']]; r['win']=1.0 if rv['final'].get(r['outcome'])==1.0 else 0.0
def table(title, keyf, order=None):
    print("\n"+title)
    print(f"{'bucket':>14s} role {'fills':>6s} {'shares':>8s} {'%sh':>5s} {'avg_px':>6s} {'win':>6s} {'edge¢/sh':>8s} {'fee¢/sh':>7s} {'net¢/sh':>7s} {'gross$':>7s} {'net$':>7s}")
    agg=collections.defaultdict(lambda:[0,0.0,0.0,0.0,0.0])
    for r in rows:
        a=agg[(keyf(r),r['role'])]; a[0]+=1; a[1]+=r['size']; a[2]+=r['size']*r['price']; a[3]+=r['size']*r['win']
        if r['role']=='T': a[4]+=FEE*r['size']*r['price']*(1-r['price'])
    tot=sum(a[1] for a in agg.values())
    keys=sorted(agg, key=lambda k:(order.index(k[0]) if order else k[0], k[1]))
    for k in keys:
        n,sh,usd,win,fee=agg[k]
        print(f"{str(k[0]):>14s} {k[1]:>4s} {n:6d} {sh:8.0f} {sh/tot*100:5.1f} {usd/sh:6.3f} {win/sh:6.3f} {(win-usd)/sh*100:+8.2f} {fee/sh*100:7.2f} {(win-usd-fee)/sh*100:+7.2f} {win-usd:+7.0f} {win-usd-fee:+7.0f}")
def tb(r):
    d=r['dt']
    if d<0: return 'pre(<0s)'
    for lo,hi in ((0,30),(30,60),(60,120),(120,180),(180,240),(240,270),(270,285),(285,300)):
        if lo<=d<hi: return f'{lo:03d}-{hi:03d}s'
    return 'post(>=300s)'
table("BY TIME IN WINDOW (seconds from market start)", tb)
def pb(r):
    p=r['price']
    for lo,hi in ((0,.05),(.05,.15),(.15,.30),(.30,.45),(.45,.55),(.55,.70),(.70,.85),(.85,.95),(.95,1.01)):
        if lo<=p<hi: return f'{lo:.2f}-{hi:.2f}'
table("BY PRICE BUCKET", pb)
dts=[r['dt'] for r in rows]; print("\ndt range", min(dts), max(dts), "pre-window fills:", sum(1 for d in dts if d<0), " post-window:", sum(1 for d in dts if d>=300))
# fills per market / order sizes
sz=collections.Counter(round(r['size']) for r in rows if r['role']=='T'); print("top taker fill sizes:", sz.most_common(8))
sz=collections.Counter(round(r['size']) for r in rows if r['role']=='M'); print("top maker fill sizes:", sz.most_common(8))
