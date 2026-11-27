import sys,json,re,math,collections,statistics as st
sys.path.insert(0,sys.argv[1])
from btc import Btc,fair_up
import numpy as np
b=Btc(sys.argv[2]); res=json.load(open(sys.argv[3])); SM=1.3; FEE=0.05; LAG=int(sys.argv[4])
for path in sys.argv[5:]:
    rows=[]
    for l in open(path):
        r=json.loads(l)
        m=re.match(r'btc-updown-5m-(\d+)$',r['slug'] or '')
        if not m: continue
        r['t0']=int(m.group(1)); r['K']=b.twap(r['t0'],60)
        if r['K']!=r['K']: continue
        rv=res.get(r['condition_id'])
        if not rv or not rv['resolved']: continue
        r['win']=1.0 if rv['final'].get(r['outcome'])==1.0 else 0.0
        r['sgn']=1 if r['outcome']=='Up' else -1
        t=r['timestamp']-LAG
        fu=fair_up(b,t,r['t0'],r['K'],sig_mult=SM)
        if fu!=fu: continue
        r['fair']=fu if r['sgn']>0 else 1-fu
        r['medge']=r['fair']-r['price']
        p0=b.price(t)
        r['m1']=r['sgn']*(p0/b.price(t-1)-1)*1e4; r['m3']=r['sgn']*(p0/b.price(t-3)-1)*1e4; r['m10']=r['sgn']*(p0/b.price(t-10)-1)*1e4; r['m30']=r['sgn']*(p0/b.price(t-30)-1)*1e4
        r['f5']=r['sgn']*(b.price(t+5)/p0-1)*1e4; r['f30']=r['sgn']*(b.price(min(t+30,r['t0']+300))/p0-1)*1e4
        # fair value of the bought outcome 10s and 30s later (markout in probability terms)
        for h in (5,15,30):
            tt=min(t+h,r['t0']+299); f2=fair_up(b,tt,r['t0'],r['K'],sig_mult=SM); r[f'mo{h}']=(f2 if r['sgn']>0 else 1-f2)-r['price']
        rows.append(r)
    print(f"\n==================== {path.split('/')[-1]}  fills {len(rows)}  (lag {LAG}s)")
    for role in ('T','M'):
        rs=[r for r in rows if r['role']==role]; w=np.array([r['size'] for r in rs]); W=w.sum()
        def wm(k): return float((np.array([r[k] for r in rs])*w).sum()/W)
        fee=sum(FEE*r['size']*r['price']*(1-r['price']) for r in rs)/W if role=='T' else 0
        print(f"ROLE {role}: shares {W:.0f}  avg px {wm('price'):.3f}  model fair {wm('fair'):.3f}  MODEL EDGE at entry {wm('medge')*100:+.2f}c  realized {(wm('win')-wm('price'))*100:+.2f}c  fee {fee*100:.2f}c")
        print(f"   markout vs model fair: +5s {wm('mo5')*100:+.2f}c  +15s {wm('mo15')*100:+.2f}c  +30s {wm('mo30')*100:+.2f}c")
        print(f"   BTC move in buy direction (bps): prev1s {wm('m1'):+.3f} prev3s {wm('m3'):+.3f} prev10s {wm('m10'):+.3f} prev30s {wm('m30'):+.3f} | next5s {wm('f5'):+.3f} next30s {wm('f30'):+.3f}")
        up3=sum(r['size'] for r in rs if r['m3']>0)/W; dn3=sum(r['size'] for r in rs if r['m3']<0)/W
        print(f"   share bought WITH the last-3s BTC move: {up3*100:.1f}%  against: {dn3*100:.1f}%  flat: {(1-up3-dn3)*100:.1f}%")
        # by model-edge bucket
        print(f"   {'model edge bucket':>18s} {'%sh':>5s} {'avgpx':>6s} {'model¢':>7s} {'realized¢':>9s} {'net¢(after fee)':>15s}")
        bk=collections.defaultdict(lambda:[0.0,0.0,0.0,0.0,0.0])
        for r in rs:
            e=r['medge']
            k=( '<-5c' if e<-0.05 else '-5..-2c' if e<-0.02 else '-2..0c' if e<0 else '0..2c' if e<0.02 else '2..5c' if e<0.05 else '5..10c' if e<0.10 else '>10c')
            a=bk[k]; a[0]+=r['size']; a[1]+=r['size']*r['price']; a[2]+=r['size']*e; a[3]+=r['size']*r['win']; a[4]+=(FEE*r['size']*r['price']*(1-r['price']) if role=='T' else 0)
        for k in ('<-5c','-5..-2c','-2..0c','0..2c','2..5c','5..10c','>10c'):
            if k in bk:
                a=bk[k]; print(f"   {k:>18s} {a[0]/W*100:5.1f} {a[1]/a[0]:6.3f} {a[2]/a[0]*100:+7.2f} {(a[3]-a[1])/a[0]*100:+9.2f} {(a[3]-a[1]-a[4])/a[0]*100:+15.2f}")
