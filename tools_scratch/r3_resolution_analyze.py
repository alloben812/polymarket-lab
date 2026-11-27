import json,collections,statistics as st,re,sys
D='/home/user/polymarket-lab/data/r3/'
def pb(p): return '0.90-0.95' if p<0.95 else '0.95-0.98' if p<0.98 else '0.98-0.99' if p<0.99 else '0.99-1'
def tb(s): return '<2h' if s<7200 else '2-6h' if s<21600 else '6-24h'
def run(tag,rows,F,keep):
    rows=[r for r in rows if keep(r)]; ok={r['cid'] for r in rows}; qm={r['cid']:r for r in rows}
    F=[f for f in F if f[0] in ok]
    print('=====',tag,'markets',len(rows),'disputed',sum(1 for r in rows if r['disputed']),'fee rates',dict(collections.Counter(r['rate'] for r in rows)),'fills',len(F))
    l=sorted(r['lag_h'] for r in rows if r['lag_h'] is not None)
    if l: print('resolved_at - endDate (h) p10/p50/p90:',l[len(l)//10],l[len(l)//2],l[9*len(l)//10])
    agg=collections.defaultdict(lambda: collections.defaultdict(lambda:[0.0,0.0,0.0]))
    for cid,side,p,sz,dt_,pay,rate,rep,dis in F:
        if side!='BUY' or p>=1: continue
        fee=rate*p*(1-p)*sz
        for key in [(pb(p),tb(dt_)),(pb(p),'any'),('any',tb(dt_)),('any','any')]:
            a=agg[key][cid]; a[0]+=p*sz; a[1]+=(pay-p)*sz; a[2]+=fee
    print('TAKER BUY>=0.90  price|time  n_mkts  $bought  pooled_gross%  pooled_net%  per-market mean net%  share mkts net<0  worst mkt net $')
    for key in sorted(agg):
        M=agg[key]; cost=sum(a[0] for a in M.values()); g=sum(a[1] for a in M.values()); f=sum(a[2] for a in M.values())
        per=[(a[1]-a[2])/a[0] for a in M.values() if a[0]>0]
        print('  ',key,len(M),round(cost),round(100*g/cost,3),round(100*(g-f)/cost,3),round(100*st.mean(per),3),round(sum(1 for x in per if x<0)/len(per),3),round(min(a[1]-a[2] for a in M.values())))
    L=collections.defaultdict(float)
    for cid,side,p,sz,dt_,pay,rate,rep,dis in F:
        if side=='BUY' and pay<0.5: L[cid]+=p*sz
    print('markets where takers bought the eventual LOSER at >=0.90 in the last 24h:',len(L),'of',len(rows),' $',round(sum(L.values())))
    for cid,v in sorted(L.items(),key=lambda kv:-kv[1])[:5]: print('     $',round(v),'|',qm[cid]['q'][:70],'| resolved',qm[cid]['resolved_at'])
    cap=collections.defaultdict(lambda:[0.0,0.0,set()]); bad=collections.defaultdict(lambda:[0.0,set()])
    for cid,side,p,sz,dt_,pay,rate,rep,dis in F:
        if side=='SELL' and p<1:
            for key in [(pb(p),tb(dt_)),(pb(p),'any'),('any','any')]:
                if pay>0.5: c=cap[key]; c[0]+=p*sz; c[1]+=(1-p)*sz; c[2].add(cid)
                else: b=bad[key]; b[0]+=p*sz; b[1].add(cid)
    print('RESTING BID (taker sells at >=0.90): price|time  n_mkts  $winner sold  maker gain $  | $ of LOSER sold to bids (full loss)  n_mkts | net % on all $')
    for key in sorted(cap):
        c=cap[key]; b=bad.get(key,[0.0,set()]); tot=c[0]+b[0]
        print('  ',key,len(c[2]),round(c[0]),round(c[1]),'|',round(b[0]),len(b[1]),'|',round(100*(c[1]-b[0])/tot,3))
game=lambda r: bool(re.search(r'-20\d\d-\d\d-\d\d(-|$)',r['slug'] or ''))
rows=json.load(open(D+'resolution_markets.json')); F=json.load(open(D+'resolution_fills.json'))
run('R1 game markets (sports/esports)',rows,F,game)
run('R1 non-game',rows,F,lambda r: not game(r))
rows2=json.load(open(D+'resolution_markets_r2.json')); F2=json.load(open(D+'resolution_fills_r2.json'))
run('R2 non-game',rows2,F2,lambda r: True)
for r in rows2: print('   ',r['rate'],r['lag_h'],r['ntr'],round(r['vol']),r['q'][:70])
