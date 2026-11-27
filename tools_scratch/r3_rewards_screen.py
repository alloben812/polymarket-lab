import json, subprocess, statistics as st, sys, time, bisect, collections, re
D='/home/user/polymarket-lab/data/r3/'; TODAY='2026-11-27'; CAP=200.0
def curl(a): return subprocess.run(["curl","-s","-m","40","--compressed"]+a,capture_output=True,text=True).stdout
allm=json.load(open(D+'reward_markets_all.json'))
seen=set(); u=[]
for m in allm:
    if m['condition_id'] in seen: continue
    seen.add(m['condition_id']); u.append(m)
def cfg(m): return [c for c in m['rewards_config'] if c['start_date']<=TODAY<=c['end_date']]
def rate(m): return sum(c['rate_per_day'] for c in cfg(m))
act=sorted([m for m in u if rate(m)>=20],key=lambda m:-rate(m))
print('markets with rate>=20:',len(act),'sum pool',round(sum(rate(m) for m in act)))
books={}
toks=[m['tokens'][0]['token_id'] for m in act]
for i in range(0,len(toks),100):
    r=curl(["-X","POST","https://clob.polymarket.com/books","-H","Content-Type: application/json","-d",json.dumps([{'token_id':t} for t in toks[i:i+100]])])
    try:
        for b in json.loads(r): books[b['asset_id']]=b
    except Exception: print('books fail',i,r[:120],file=sys.stderr)
    time.sleep(0.25)
def fam(q):
    ql=q.lower()
    if 'ornn' in ql: return 'ornn-gpu'
    if 'temperature' in ql: return 'weather-temp'
    if re.search(r'\bvs\.?\b|win on 20|o/u|spread:|both teams',ql): return 'sports-game'
    if re.search(r'election|prime minister|president|mayor|seats|senate|governor|nominee',ql): return 'politics'
    if re.search(r'bitcoin|btc|ethereum|eth |solana|fdv|token|xrp',ql): return 'crypto'
    if re.search(r'fed |rate|inflation|cpi|gdp|treasury|unemployment|bank of',ql): return 'econ'
    return 'other'
rows=[]
for m in act:
    t=m['tokens'][0]['token_id']; b=books.get(t)
    if not b: continue
    v=m['rewards_max_spread']/100.0; ms=m['rewards_min_size']; tick=float(b['tick_size'])
    fb=sorted([(float(x['price']),float(x['size'])) for x in b['bids'] if float(x['size'])>=ms],reverse=True)
    fa=sorted([(float(x['price']),float(x['size'])) for x in b['asks'] if float(x['size'])>=ms])
    base=dict(cid=m['condition_id'],tok=t,q=m['question'],fam=fam(m['question']),rate=rate(m),v=m['rewards_max_spread'],ms=ms,vol24=m.get('volume_24hr') or 0,end=(m.get('end_date') or '')[:10],
              cfg_start=min(c['start_date'] for c in cfg(m)),asset=cfg(m)[0]['asset_address'][:8],comp=m.get('market_competitiveness'))
    if not fb or not fa or v<=0: base.update(elig=False); rows.append(base); continue
    mp=(fb[0][0]+fa[0][0])/2; hs=(fa[0][0]-fb[0][0])/2
    S=lambda s:((v-s)/v)**2 if 0<=s<v else 0.0
    q1=sum(S(mp-p)*sz for p,sz in fb); q2=sum(S(p-mp)*sz for p,sz in fa)
    depth=sum(p*sz for p,sz in fb if mp-p<v)+sum((1-p)*sz for p,sz in fa if p-mp<v)
    s=max(tick,0.01,hs); N=CAP/(1-2*s) if s<0.5 else 0
    elig=N>=ms and s<v; qus=N*S(s) if elig else 0
    mn,mx=min(q1,q2),max(q1,q2); inr=0.10<=mp<=0.90
    cc=mn+(mx-mn)/3 if inr else mn; lo_c=mx/3 if inr else 0.0; hi_c=q1+q2 if inr else mn
    f=lambda qq: base['rate']*qus/(qus+qq) if qus>0 else 0
    base.update(elig=elig,mid=round(mp,4),hs=round(hs,4),q1=round(q1),q2=round(q2),depth=round(depth),N=round(N,1),s=s,qus=round(qus,1),rew_c=round(f(cc),2),rew_lo=round(f(hi_c),2),rew_hi=round(f(lo_c),2))
    rows.append(base)
json.dump(rows,open(D+'reward_screen_rows.json','w'),indent=0)
E=[r for r in rows if r.get('elig')]
print('with book',len(rows),'eligible with $200',len(E))
print('ALL eligible: sum pool',round(sum(r['rate'] for r in E)),'sum in-band depth $',round(sum(r['depth'] for r in E)),'-> pool/depth per day %',round(100*sum(r['rate'] for r in E)/sum(r['depth'] for r in E),3))
print('fam | n | sum pool/day | sum depth | pool/depth %/day | median vol24 | $200 reward lo/central/hi median')
for fm,c in collections.Counter(r['fam'] for r in E).most_common():
    F=[r for r in E if r['fam']==fm]
    print(fm,len(F),round(sum(r['rate'] for r in F)),round(sum(r['depth'] for r in F)),round(100*sum(r['rate'] for r in F)/max(1,sum(r['depth'] for r in F)),2),round(st.median([r['vol24'] for r in F])),
          round(st.median([r['rew_lo'] for r in F]),2),round(st.median([r['rew_c'] for r in F]),2),round(st.median([r['rew_hi'] for r in F]),2))
print('cfg_start distribution (eligible):',collections.Counter(r['cfg_start'][:7] for r in E).most_common(8))
print('reward asset:',collections.Counter(r['asset'] for r in E))
# quiet pool rule
Q=sorted([r for r in E if r['rate']>=100 and r['vol24']<5000],key=lambda r:-r['rate'])
print('quiet-pool rule passes:',len(Q),collections.Counter(r['fam'] for r in Q))
NOW=int(time.time()); START=NOW-7*86400
res=[]
for r in Q[:60]:
    js=curl(["https://data-api.polymarket.com/v2/prices-history?token_id=%s&interval=1w"%r['tok']])
    try: h=json.loads(js)['data']
    except Exception: continue
    ts=[x['timestamp'] for x in h]; ps=[x['price'] for x in h]
    tr=[]; cur=None
    for page in range(5):
        url="https://data-api.polymarket.com/v2/trades?condition=%s&limit=1000&start=%d"%(r['cid'],START)
        if cur: url+="&cursor="+cur
        try: d=json.loads(curl([url]))
        except Exception: break
        tr+=d.get('data',[]); cur=(d.get('pagination') or {}).get('next_cursor')
        if not cur or not d.get('data'): break
    time.sleep(0.1)
    days=max(1.0,min(7.0,(ts[-1]-ts[0])/86400)) if ts else 7.0
    pnl=sh=0.0
    for x in tr:
        yes=x['outcome_index']==0; p=x['price'] if yes else 1-x['price']; by=(x['side']=='BUY')==yes
        i=bisect.bisect_left(ts,x['timestamp']+3600); f=ps[i] if i<len(ps) else (ps[-1] if ps else p)
        pnl+=x['size']*((p-f) if by else (f-p)); sh+=x['size']
    rng=100*(max(ps)-min(ps)) if ps else None
    res.append(dict(cid=r['cid'],q=r['q'][:75],fam=r['fam'],rate=r['rate'],ms=r['ms'],v=r['v'],mid=r['mid'],depth=r['depth'],vol24=round(r['vol24']),fills_7d=len(tr),takers=len(set(x['proxy_wallet'] for x in tr)),days=round(days,2),
        rng_c=round(rng,1) if rng is not None else None,markout_c=round(100*pnl/sh,2) if sh else 0,markout_usd_day=round(pnl/days,2),net_agg=round(r['rate']+pnl/days,2),
        rew_lo=r['rew_lo'],rew_c=r['rew_c'],rew_hi=r['rew_hi'],cfg_start=r['cfg_start'],end=r['end']))
json.dump(res,open(D+'reward_quiet_pool.json','w'),indent=0)
for x in res: print(x)
if res:
    print('QUIET n',len(res),'sum pool',round(sum(x['rate'] for x in res)),'sum markout/day',round(sum(x['markout_usd_day'] for x in res)),'sum depth',sum(x['depth'] for x in res),
      'net %/day on depth',round(100*sum(x['net_agg'] for x in res)/sum(x['depth'] for x in res),2),'median $200 reward lo/c/hi',st.median([x['rew_lo'] for x in res]),st.median([x['rew_c'] for x in res]),st.median([x['rew_hi'] for x in res]),
      'sum $200-rewards if in all (lo/c):',round(sum(x['rew_lo'] for x in res)),round(sum(x['rew_c'] for x in res)))
