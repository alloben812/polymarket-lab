import json, math, pandas as pd, numpy as np
D="/home/user/polymarket-lab/data/gaps_maker_edge"
FX=pd.read_parquet(D+"/fills_ext.parquet"); F25=pd.read_parquet(D+"/fills.parquet")
seen=set(F25.cid.unique())
def rc(g,m):
    g=g[np.isfinite(g[m])]
    by=g.assign(n=g[m]*g.sh).groupby("cid").agg(n=("n","sum"),d=("sh","sum"))
    k=len(by); 
    if k<2: return (np.nan,np.nan,k)
    r=by.n.sum()/by.d.sum(); se=math.sqrt(k/(k-1)*((by.n-r*by.d)**2).sum())/by.d.sum()
    return 100*r,196*se,k
rows=[]
for fam in ["btc-5m","btc-15m","alt-updown-5m15m","crypto-updown-long"]:
  for pb in [".05-.20",".20-.40",".40-.60",".60-.80",".80-.95"]:
    for lab,sel in (("protocol25",FX.cid.isin(seen)),("new75",~FX.cid.isin(seen))):
      for v in ("V2","V1"):
        g=FX[(FX["var"]==v)&(FX.family==fam)&(FX.pb==pb)&sel]
        if len(g)<30: continue
        f=rc(g,"fin");a=rc(g,"m30")
        rows.append((fam,pb,lab,v,f"{f[0]:+.2f}±{f[1]:.2f}",f"{a[0]:+.2f}±{a[1]:.2f}",f[2],len(g)))
print(pd.DataFrame(rows,columns="fam pb sample var fin m30 mkts fills".split()).to_string())
