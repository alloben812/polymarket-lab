import json, sys
import numpy as np, pyarrow as pa, pyarrow.parquet as pq, pyarrow.compute as pc
sys.path.insert(0,"/home/user/polymarket-lab/studies/gaps/negrisk_parity")
from common import families, D
tag="2026-11-26T06"; slug=sys.argv[1]; T0=int(sys.argv[2])
e=[x for x in families()["B"] if x["slug"]==slug][0]
tok={}
for m in e["markets"]:
    tok[int(m["yes"])]=(m["groupItemTitle"] if "groupItemTitle" in m else m["question"][-20:],True,m["rate"]); tok[int(m["no"])]=(tok[int(m["yes"])][0],False,m["rate"])
vs=pa.array([bytes.fromhex(m["conditionId"][2:]) for m in e["markets"]],type=pa.binary())
t=pq.read_table(f"{D}/hours/{tag}.ev.parquet",columns=["event_type","timestamp","market","asset_id","best_bid","best_ask","price","size","side","recv_lag_ms","row_ordinal","mirror_dropped"])
t=t.filter(pc.is_in(t["market"],value_set=vs))
ts=t["timestamp"].cast(pa.int64()).to_numpy()+t["recv_lag_ms"].to_numpy()
sel=(ts>=T0-3000)&(ts<=T0+14000)
t=t.filter(pa.array(sel)); ts=ts[sel]
order=np.argsort(ts,kind="stable"); 
rows=t.take(pa.array(order)).to_pylist(); ts=ts[order]
last={}
for r,tt in zip(rows,ts):
    k=tok.get(int.from_bytes(r["asset_id"],"big"))
    if not k: continue
    if r["event_type"] in("price_change","best_bid_ask") and r["best_bid"] is not None:
        bb=float(r["best_bid"]);ba=float(r["best_ask"])
        ya,yb=(ba,bb) if k[1] else (1-bb,1-ba)
        last[k[0]]=(yb,ya)
        print(tt-T0, r["event_type"], k[0][:14], "YES" if k[1] else "NO", r["side"], r["price"], r["size"], "drop" if r["mirror_dropped"] else "", "fieldYESask", round(ya,4), "sumfieldask", round(sum(v[1] for v in last.values()),4), len(last))
