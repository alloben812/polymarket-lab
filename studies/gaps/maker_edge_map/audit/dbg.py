import sys, json, pandas as pd
sys.path.insert(0,'.')
import recompute as R
D=R.D
S=json.load(open(D+"/sample_ext.json"))
F=pd.read_parquet(D+"/fills_ext.parquet")
F=F[(F["var"]=="V2o")&(F.family=="btc-5m")&(F.half=="late")]
cnt=F.groupby("cid").size().to_dict()
import types
bad=0
for r in [r for r in S if r["family"]=="btc-5m" and r["half"]=="late"][:100]:
    # monkeypatch run for single market
    res=R.run([r],"btc-5m","late",0,"at")
    if res["fills"]!=cnt.get(r["conditionId"],0):
        bad+=1
        if bad<=3:
            g=F[F.cid==r["conditionId"]]
            print(r["slug"],res["fills"],cnt.get(r["conditionId"],0)); print(g[["tf","q","sh","fin"]].head(8)); 
print("bad",bad)
r=[r for r in S if r["slug"]=="btc-updown-5m-1795491600"][0]
g=F[F.cid==r["conditionId"]]
print(sorted((g.tf-g.tf.min()).round(1).tolist()))
P=R.load(r); t0=P[0][0]
print([(round(p[0]-t0,1),round(p[1],3),p[2]) for p in P[:60]])
