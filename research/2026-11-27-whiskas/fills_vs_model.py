import sys,json,re,math,collections,statistics as st
sys.path.insert(0,sys.argv[1])
from btc import Btc,fair_up
import numpy as np
b=Btc(sys.argv[2]); res=json.load(open(sys.argv[3])); SM=1.3; FEE=0.05
rows=[]
for path in sys.argv[4:]:
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
        rows.append(r)
print("fills with btc data:",len(rows))
# 1) which lag aligns Binance-implied fair value with fill prices best
print("\nlag(s)  mean|fair-px|  corr(fair,px)   [all fills]")
for lag in (0,1,2,3,4,5,6,8,10,15):
    f=[];p=[]
    for r in rows[::7]:
        fu=fair_up(b,r['timestamp']-lag,r['t0'],r['K'],sig_mult=SM)
        if fu!=fu: continue
        f.append(fu if r['sgn']>0 else 1-fu); p.append(r['price'])
    f=np.array(f);p=np.array(p)
    print(f"{lag:5d}  {np.mean(np.abs(f-p)):.4f}        {np.corrcoef(f,p)[0,1]:.4f}")
json.dump(None,open('/dev/null','w'))
