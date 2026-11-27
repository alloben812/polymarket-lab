"""Lead-lag between Binance BTCUSDT (ms trades) and the Polymarket BTC-5m Up mid (REST book snapshots, server ms timestamps)."""
import json,sys,time,math,urllib.request,bisect,statistics as st
import numpy as np
def get(url):
    for i in range(6):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(req,timeout=40) as r: return json.loads(r.read())
        except Exception as e: time.sleep(1+i)
    raise SystemExit("fail "+url)
snaps=[json.loads(l) for l in open(sys.argv[1])]
snaps=[s for s in snaps if s['ub'] and s['ua']]
t_a=min(s['ts'] for s in snaps); t_b=max(s['ts'] for s in snaps)
print(f"snapshots {len(snaps)} span {(t_b-t_a)/60000:.1f} min, markets {len(set(s['t0'] for s in snaps))}")
# ---- Binance aggTrades for [t_a-1200s, t_b]
B="https://data-api.binance.vision/api/v3/aggTrades?symbol=BTCUSDT"
tr=[]; start=t_a-1200_000
d=get(f"{B}&startTime={start}&endTime={start+3_000_000}&limit=1000")
while d:
    tr+=[(x['T'],float(x['p'])) for x in d]
    if d[-1]['T']>=t_b or len(d)<1000: 
        if d[-1]['T']>=t_b or (time.time()*1000-d[-1]['T'])<3000: break
    d=get(f"{B}&fromId={d[-1]['a']+1}&limit=1000")
    if not d: break
T=np.array([x[0] for x in tr]); P=np.array([x[1] for x in tr])
print(f"binance aggTrades {len(tr)} from {T[0]} to {T[-1]} ({(T[-1]-T[0])/60000:.1f} min), {len(tr)/((T[-1]-T[0])/1000):.1f}/s")
def S_at(tms):
    i=np.searchsorted(T,tms,side='right')-1
    return P[np.clip(i,0,len(P)-1)]
# 1s closes for sigma
sec0=int(T[0]//1000)+1; sec1=int(T[-1]//1000)
secs=np.arange(sec0,sec1+1); close=S_at(secs*1000)
lr=np.diff(np.log(close))
def sigma(tsec,look=900):
    j=int(tsec)-sec0; i=max(j-look,0)
    if j<=i+60: return float('nan')
    return math.sqrt(float(np.mean(lr[i:j]**2)))*1.3
def twap(tsec_end,L=60):
    j=int(tsec_end)-sec0; i=j-L
    if i<0: return float('nan')
    return float(np.mean(close[i+1:j+1]))
def ncdf(x): return 0.5*(1+math.erf(x/math.sqrt(2)))
def fair(S,K,sig,t,t0):
    Tavg=t0+240; Tend=t0+300
    if t<=Tavg: sd=sig*S*math.sqrt((Tavg-t)+20.0); mean=S
    else:
        r=Tend-t; e=t-Tavg; j=int(t)-sec0; i=int(Tavg)-sec0
        sofar=float(np.mean(close[i+1:j+1])) if j>i else S
        mean=(e/60)*sofar+(r/60)*S; sd=(r/60)*sig*S*math.sqrt(max(r,0.5)/3)
    return ncdf((mean-K)/max(sd,1e-9))
# ---- build aligned 250ms grid per market
G=250; rows=[]
bym={}
for s in snaps: bym.setdefault(s['t0'],[]).append(s)
resp_lags=list(range(-4,25))   # in grid steps (250ms): -1s .. +6s
X=[];Y=[]; diag=[]
for t0,ss in sorted(bym.items()):
    ss.sort(key=lambda s:s['ts']); K=twap(t0); 
    if K!=K: continue
    ts=np.array([s['ts'] for s in ss]); mid=np.array([(s['ub'][0][0]+s['ua'][0][0])/2 for s in ss])
    g=np.arange(max(ts[0],(t0+5)*1000),min(ts[-1],(t0+235)*1000),G)   # only before the averaging window
    if len(g)<200: continue
    idx=np.searchsorted(ts,g,side='right')-1; m=mid[idx]; stale=g-ts[idx]
    Sg=S_at(g); sig=sigma(t0)
    if sig!=sig: continue
    f=np.array([fair(float(Sg[i]),K,sig,g[i]/1000.0,t0) for i in range(len(g))])
    # model-implied change in fair value caused by the BTC move over each 250ms step (time held fixed)
    f_prev=np.array([fair(float(Sg[i-1]),K,sig,g[i]/1000.0,t0) for i in range(1,len(g))])
    dx=f[1:]-f_prev; dm=np.diff(m)
    ok=(m[1:]>0.15)&(m[1:]<0.85)&(stale[1:]<600)
    diag.append((t0,len(g),float(np.corrcoef(f,m)[0,1]),float(np.mean(np.abs(f-m)))))
    L=len(dm)
    for i in range(30,L-30):
        if not ok[i]: continue
        X.append([dx[i-k] for k in resp_lags]); Y.append(dm[i])
X=np.array(X);Y=np.array(Y)
print("markets used:",[(d[0],d[1],f"corr(model,mid)={d[2]:.3f}",f"mean|f-mid|={d[3]:.3f}") for d in diag])
print("regression samples",len(Y))
beta,_,_,_=np.linalg.lstsq(X,Y,rcond=None)
tot=beta.sum()
print("\nImpulse response: share of the Polymarket mid adjustment that happens k*250ms after a Binance move (regression of dMid on lagged model-implied dFair)")
cum=0
for k,bk in zip(resp_lags,beta):
    cum+=bk
    print(f"  lag {k*G:+5d} ms  beta {bk:+.3f}  cumulative {cum/tot*100:6.1f}%")
print(f"sum of betas (1.0 = model delta fully reflected): {tot:.3f}")
# simple cross-correlation at each lag
print("\ncross-correlation corr(dFair_binance[t-lag], dMid_poly[t]):")
for j,k in enumerate(resp_lags):
    c=np.corrcoef(X[:,j],Y)[0,1]; print(f"  lag {k*G:+5d} ms  {c:+.3f}")
