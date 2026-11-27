"""Maker what-if with a less pessimistic fill rule: besides prints that go THROUGH our bid (full clip),
prints exactly AT our bid fill a fraction PHI of the print size (queue sharing)."""
import sys,json,re,glob,os,collections,math,statistics as st
sys.path.insert(0,sys.argv[1])
from btc import Btc,fair_up
b=Btc(sys.argv[2]); res=json.load(open(sys.argv[3])); tapedir=sys.argv[4]
LAG=3; SM=1.3
byslug={v['slug']:v for v in res.values()}
mk=[]
for path in sorted(glob.glob(os.path.join(tapedir,"*.jsonl"))):
    slug=os.path.basename(path)[:-6]; rv=byslug.get(slug)
    if not rv or not rv['resolved']: continue
    t0=int(slug.rsplit('-',1)[1]); K=b.twap(t0,60)
    if K!=K: continue
    rows=[json.loads(l) for l in open(path)]; rows.sort(key=lambda r:r['t'])
    mk.append((t0,K,1.0 if rv['final'].get('Up')==1.0 else 0.0,rows))
def tstat(xs):
    n=len(xs); m=st.mean(xs); s=st.pstdev(xs); return m/(s/math.sqrt(n)) if s>0 else 0.0
fc={}
def fair(t,t0,K):
    v=fc.get((t,t0))
    if v is None: v=fair_up(b,t,t0,K,sig_mult=SM); fc[(t,t0)]=v
    return v
print("markets",len(mk))
print(f"{'PHI':>4s} {'D':>2s} {'δ¢':>4s} {'fills':>7s} {'shares':>9s} {'usdc':>9s} {'thru%':>6s} {'edge thru¢':>10s} {'edge touch¢':>11s} {'ALL ¢/sh':>8s} {'net$':>8s} {'net%':>6s} {'t(mkt)':>6s} {'$/mkt':>6s}")
for PHI in (0.25,0.5):
  for D in (0,1,2):
    for delta in (0.01,0.02,0.03,0.05):
        sh=usd=g=n=0.0; per=[]; shT=gT=shA=gA=0.0
        for t0,K,up_win,rows in mk:
            inv={'Up':0.0,'Down':0.0}; mp=0.0
            for r in rows:
                m=r['t']-LAG
                if m<t0+2 or m>t0+290: continue
                fu=fair(m-D,t0,K)
                if fu!=fu: continue
                X=r['o'] if r['s']=='SELL' else ('Down' if r['o']=='Up' else 'Up')
                q=r['p'] if r['s']=='SELL' else 1-r['p']
                f=fu if X=='Up' else 1-fu
                bid=math.floor((f-delta)*100+1e-9)/100.0
                if bid<0.03 or bid>0.95 or inv[X]>=300: continue
                win=up_win if X=='Up' else 1-up_win
                if bid>q+0.0005:
                    z=min(r['z'],20.0,300-inv[X]); shT+=z; gT+=(win-bid)*z
                elif abs(bid-q)<=0.0005:
                    z=min(r['z']*PHI,20.0,300-inv[X]); shA+=z; gA+=(win-bid)*z
                else: continue
                if z<=0: continue
                inv[X]+=z; n+=1; sh+=z; usd+=z*bid; g+=(win-bid)*z; mp+=(win-bid)*z
            per.append(mp)
        print(f"{PHI:4.2f} {D:2d} {delta*100:4.0f} {n:7.0f} {sh:9.0f} {usd:9.0f} {shT/sh*100:6.1f} {gT/max(shT,1)*100:+10.2f} {gA/max(shA,1)*100:+11.2f} {g/sh*100:+8.2f} {g:+8.0f} {g/usd*100:+6.2f} {tstat(per):+6.2f} {g/len(mk):+6.1f}")
