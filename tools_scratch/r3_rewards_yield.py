# Read-only measurement of liquidity-rewards yield. See catalog/raw/r3_structure.md section 0 for the rule.
import json, subprocess, random, statistics, sys, time
D='/home/user/polymarket-lab/data/r3/'
TODAY='2026-11-27'; CAP=200.0
def curl(args):
    return subprocess.run(["curl","-s","-m","40","--compressed"]+args,capture_output=True,text=True).stdout
allm=json.load(open(D+'reward_markets_all.json'))
seen=set(); u=[]
for m in allm:
    if m['condition_id'] in seen: continue
    seen.add(m['condition_id']); u.append(m)
def rate(m): return sum(c['rate_per_day'] for c in m['rewards_config'] if c['start_date']<=TODAY<=c['end_date'])
act=sorted([m for m in u if rate(m)>0],key=lambda m:-rate(m))
random.seed(3)
top=act[:150]
mid=random.sample([m for m in act[150:] if 10<=rate(m)<=200],150)
low=random.sample([m for m in act if 2<=rate(m)<10],100)
sample=[('top',m) for m in top]+[('mid',m) for m in mid]+[('low',m) for m in low]
# books
books={}
toks=[m['tokens'][0]['token_id'] for _,m in sample]
for i in range(0,len(toks),50):
    body=json.dumps([{'token_id':t} for t in toks[i:i+50]])
    r=curl(["-X","POST","https://clob.polymarket.com/books","-H","Content-Type: application/json","-d",body])
    try:
        for b in json.loads(r): books[b['asset_id']]=b
    except Exception as e: print('books fail',i,r[:200],file=sys.stderr)
    time.sleep(0.3)
json.dump(books,open(D+'reward_books_snapshot.json','w'))
rows=[]
for tier,m in sample:
    t=m['tokens'][0]['token_id']; b=books.get(t)
    if not b: continue
    v=m['rewards_max_spread']/100.0; ms=m['rewards_min_size']; tick=float(b['tick_size'])
    bids=sorted([(float(x['price']),float(x['size'])) for x in b['bids']],reverse=True)
    asks=sorted([(float(x['price']),float(x['size'])) for x in b['asks']])
    fb=[x for x in bids if x[1]>=ms]; fa=[x for x in asks if x[1]>=ms]
    if not fb or not fa or v<=0: 
        rows.append(dict(tier=tier,q=m['question'],rate=rate(m),elig=False,why='empty/one-sided book')); continue
    mp=(fb[0][0]+fa[0][0])/2; hs=(fa[0][0]-fb[0][0])/2
    S=lambda s:((v-s)/v)**2 if 0<=s<v else 0.0
    q1=sum(S(mp-p)*sz for p,sz in fb); q2=sum(S(p-mp)*sz for p,sz in fa)
    d1=sum(p*sz for p,sz in fb if mp-p<v); d2=sum((1-p)*sz for p,sz in fa if p-mp<v)
    s=max(tick,0.01,hs)
    N=CAP/(1-2*s) if s<0.5 else 0
    elig = N>=ms and s<v
    qus=N*S(s) if elig else 0
    qc=min(q1,q2); lo=max(q1,q2)/3; hi=q1+q2
    r=rate(m)
    f=lambda qq: r*qus/(qus+qq) if qus>0 else 0
    rows.append(dict(tier=tier,q=m['question'],cid=m['condition_id'],tok=t,rate=r,v=m['rewards_max_spread'],ms=ms,mid=round(mp,4),hs=round(hs,4),tick=tick,
        q1=round(q1),q2=round(q2),depth_usd=round(d1+d2),comp=m.get('market_competitiveness'),vol24=m.get('volume_24hr'),end=m.get('end_date'),
        elig=elig,s=round(s,4),N=round(N,1),qus=round(qus,1),rew=round(f(qc),3),rew_lo=round(f(hi),3),rew_hi=round(f(lo),3)))
json.dump(rows,open(D+'reward_yield_rows.json','w'),indent=0)
print('rows',len(rows))
