"""Tape-based what-if simulation of (B) a fair-value taker and (C) a fair-value maker on BTC 5m markets.
Uses on-chain trade prints (match time ~= block time - LAG), Binance 1s closes as the price feed, real resolutions.
D = how stale our price information is at the moment of the match (seconds). Conservative fills at OUR price only
when the print went strictly through our level."""
import sys,json,re,glob,os,collections,math,statistics as st
sys.path.insert(0,sys.argv[1])
from btc import Btc,fair_up
b=Btc(sys.argv[2]); res=json.load(open(sys.argv[3])); tapedir=sys.argv[4]
FEE=0.05; LAG=3; SM=1.3
byslug={v['slug']:v for v in res.values()}
mk=[]
for path in sorted(glob.glob(os.path.join(tapedir,"*.jsonl"))):
    slug=os.path.basename(path)[:-6]; rv=byslug.get(slug)
    if not rv or not rv['resolved']: continue
    t0=int(slug.rsplit('-',1)[1]); K=b.twap(t0,60)
    if K!=K: continue
    up_win=1.0 if rv['final'].get('Up')==1.0 else 0.0
    rows=[json.loads(l) for l in open(path)]
    rows.sort(key=lambda r:r['t'])
    mk.append((t0,K,up_win,rows))
print("markets",len(mk),"rows",sum(len(m[3]) for m in mk))
def tstat(xs):
    n=len(xs); m=st.mean(xs); s=st.pstdev(xs)
    return m/(s/math.sqrt(n)) if s>0 else 0.0
fcache={}
def fair(t,t0,K):
    k=(t,t0)
    v=fcache.get(k)
    if v is None:
        v=fair_up(b,t,t0,K,sig_mult=SM); fcache[k]=v
    return v
# ---------- (B) taker
print("\n(B) FAIR-VALUE TAKER: buy at the printed price when model_fair - price - fee >= thr  (max 50 sh per print)")
print(f"{'D':>2s} {'thr¢':>5s} {'trades':>7s} {'shares':>9s} {'usdc':>9s} {'avg_px':>6s} {'model¢':>7s} {'gross¢':>7s} {'fee¢':>5s} {'NET¢':>6s} {'net$':>8s} {'net%usdc':>8s} {'t(mkt)':>6s} {'mkts':>5s}")
for D in (0,1,2):
    for thr in (0.0,0.01,0.02,0.03,0.05):
        n=sh=usd=g=fee=me=0.0; per=[]
        for t0,K,up_win,rows in mk:
            mp=0.0
            for r in rows:
                m=r['t']-LAG
                if m<t0+2 or m>t0+295: continue
                fu=fair(m-D,t0,K)
                if fu!=fu: continue
                o=r['o'] if r['s']=='BUY' else ('Down' if r['o']=='Up' else 'Up')
                q=r['p'] if r['s']=='BUY' else 1-r['p']
                if q<=0.02 or q>=0.98: continue
                f=fu if o=='Up' else 1-fu
                fe=FEE*q*(1-q)
                if f-q-fe>=thr:
                    z=min(r['z'],50.0); win=up_win if o=='Up' else 1-up_win
                    n+=1; sh+=z; usd+=z*q; g+=(win-q)*z; fee+=fe*z; me+=(f-q)*z; mp+=(win-q-fe)*z
            per.append(mp)
        if sh>0: print(f"{D:2d} {thr*100:5.1f} {n:7.0f} {sh:9.0f} {usd:9.0f} {usd/sh:6.3f} {me/sh*100:+7.2f} {g/sh*100:+7.2f} {fee/sh*100:5.2f} {(g-fee)/sh*100:+6.2f} {g-fee:+8.0f} {(g-fee)/usd*100:+8.2f} {tstat(per):+6.2f} {sum(1 for x in per if x!=0):5d}")
# ---------- (C) maker
print("\n(C) FAIR-VALUE MAKER: resting bids on Up and Down at model_fair - delta (floored to 1c tick); filled at OUR price when a print goes strictly through it")
print("     clip 20 sh per print, inventory cap 300 sh per side per market; no fees for makers")
print(f"{'D':>2s} {'δ¢':>4s} {'fills':>7s} {'shares':>9s} {'usdc':>9s} {'avg_px':>6s} {'gross¢/sh':>9s} {'net$':>8s} {'net%usdc':>8s} {'t(mkt)':>6s} {'pairs%':>6s} {'paircost':>8s} {'$/mkt':>6s} {'win%mkt':>7s}")
for D in (0,1,2,4):
    for delta in (0.01,0.02,0.03,0.05,0.08):
        n=sh=usd=g=0.0; per=[]; pairs=0.0; pc_num=0.0
        for t0,K,up_win,rows in mk:
            inv={'Up':0.0,'Down':0.0}; cost={'Up':0.0,'Down':0.0}
            for r in rows:
                m=r['t']-LAG
                if m<t0+2 or m>t0+290: continue
                fu=fair(m-D,t0,K)
                if fu!=fu: continue
                # the print lets a holder SELL outcome X at price q (i.e. our bid on X above q would have been hit first)
                X=r['o'] if r['s']=='SELL' else ('Down' if r['o']=='Up' else 'Up')
                q=r['p'] if r['s']=='SELL' else 1-r['p']
                f=fu if X=='Up' else 1-fu
                bid=math.floor((f-delta)*100+1e-9)/100.0
                if bid<0.03 or bid>0.95: continue
                if bid>q+1e-9 and inv[X]<300:
                    z=min(r['z'],20.0,300-inv[X]); inv[X]+=z; cost[X]+=z*bid
                    n+=1; sh+=z; usd+=z*bid
            pay=inv['Up']*up_win+inv['Down']*(1-up_win); c=cost['Up']+cost['Down']
            g+=pay-c; per.append(pay-c)
            p_=min(inv['Up'],inv['Down']); pairs+=p_
            if p_>0: pc_num+=p_*(cost['Up']/inv['Up']+cost['Down']/inv['Down'])
        if sh>0: print(f"{D:2d} {delta*100:4.0f} {n:7.0f} {sh:9.0f} {usd:9.0f} {usd/sh:6.3f} {g/sh*100:+9.2f} {g:+8.0f} {g/usd*100:+8.2f} {tstat(per):+6.2f} {2*pairs/sh*100:6.1f} {(pc_num/pairs if pairs else 0):8.4f} {g/len(mk):+6.1f} {sum(1 for x in per if x>0)/len(per)*100:7.1f}")
