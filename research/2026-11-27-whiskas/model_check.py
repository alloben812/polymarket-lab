import sys,json,re,math,collections
sys.path.insert(0,sys.argv[1])
from btc import Btc,fair_up
b=Btc(sys.argv[2]); res=json.load(open(sys.argv[3]))
print("btc seconds",len(b.p),"nan share",float((~b.ok).mean()))
mk=[]
for c,v in res.items():
    m=re.match(r'btc-updown-5m-(\d+)$',v['slug'] or '')
    if not m or not v['resolved']: continue
    t0=int(m.group(1)); up=1 if v['final'].get('Up')==1.0 else 0
    K=b.twap(t0,60); A=b.twap(t0+300,60)
    if K!=K or A!=A: continue
    mk.append((t0,up,K,A))
print("btc-5m markets with price data:",len(mk))
agree=sum(1 for t0,up,K,A in mk if (A>=K)==(up==1)); print(f"Binance-proxy outcome agrees with actual resolution: {agree}/{len(mk)} = {agree/len(mk)*100:.2f}%")
dis=[abs(A/K-1)*1e4 for t0,up,K,A in mk if (A>=K)!=(up==1)]; al=[abs(A/K-1)*1e4 for t0,up,K,A in mk]
import statistics as st
print(f"|move| bps: all median {st.median(al):.2f}; disagreeing median {st.median(dis) if dis else float('nan'):.2f} max {max(dis) if dis else 0:.2f}")
print(f"base rate Up: {sum(up for _,up,_,_ in mk)/len(mk):.3f}")
# calibration of the model at several times in the window
for mult in (1.0,1.3):
  print(f"\nsigma multiplier {mult}")
  for dt in (0,30,60,120,180,240,270,290):
    bins=collections.defaultdict(lambda:[0,0.0,0.0]); br=0; ll=0; n=0
    for t0,up,K,A in mk:
        f=fair_up(b,t0+dt,t0,K,sig_mult=mult)
        if f!=f: continue
        k=min(int(f*10),9); x=bins[k]; x[0]+=1; x[1]+=f; x[2]+=up
        br+=(f-up)**2; n+=1; fc=min(max(f,1e-4),1-1e-4); ll+=-(up*math.log(fc)+(1-up)*math.log(1-fc))
    s=" ".join(f"{bins[k][1]/bins[k][0]:.2f}->{bins[k][2]/bins[k][0]:.2f}({bins[k][0]})" for k in sorted(bins))
    print(f" t+{dt:3d}s brier {br/n:.4f} logloss {ll/n:.4f} | {s}")
