# Tape of the dead bucket around each kill event: who traded it between the observation time stamp and +10 min.
import json, sys, collections, statistics as st
sys.path.insert(0, "/home/user/polymarket-lab")
from pmlab import dataapi
R=json.load(open("/home/user/polymarket-lab/data/x3/wx/result_w1.json"))
kills=R["kills"]
w_sell=collections.Counter(); w_sell_n=collections.Counter(); w_ev=collections.defaultdict(set)
tot=collections.Counter(); first=[]; shown=0
for k in kills:
    rows=list(dataapi.iter_trades(condition=k["cond"], start=int(k["obs"]-600), end=int(k["rc"]+600)))
    if shown==0 and rows: print("row keys:", sorted(rows[0].keys())); shown=1
    rows.sort(key=lambda r:r["timestamp"])
    fs=None
    for r in rows:
        t=r["timestamp"]; p=float(r["price"]); s=float(r["size"]); side=r.get("side"); oi=r.get("outcome_index", r.get("outcomeIndex"))
        # normalise to the Yes token of the dead bucket: selling Yes == buying No
        yes_sell = (side=="SELL" and oi in (0,"0")) or (side=="BUY" and oi in (1,"1"))
        py = p if oi in (0,"0") else 1-p
        rel = "pre" if t<k["obs"]-60 else "obs_to_rc" if t<k["rc"] else "post_rc"
        if yes_sell and py>=0.02:
            gain=(py-0.01*py*(1-py))*s
            tot[(rel,"taker_sells_dead_usd")]+=gain; tot[(rel,"n")]+=1
            if rel!="pre":
                w=r.get("proxy_wallet") or r.get("user") or r.get("taker") or r.get("wallet")
                w_sell[w]+=gain; w_sell_n[w]+=1; w_ev[w].add(k["ev"])
                if fs is None: fs=t-k["obs"]
        elif (not yes_sell) and py>=0.02:
            tot[(rel,"taker_buys_dead_usd")]+=py*s; tot[(rel,"nb")]+=1
    if fs is not None: first.append((fs, k["lag"]))
print("kill events:",len(kills))
for key,v in sorted(tot.items()): print(key, round(v,1))
print("first taker sell of dead bucket (>=2c) after obs-60s, seconds after obsTime: n=%d median=%.0f quartiles=%s"%(len(first), st.median(f for f,_ in first), [round(x) for x in st.quantiles([f for f,_ in first],n=4)]))
print("  ... of which before the aviationweather receipt: %d of %d"%(sum(f<l for f,l in first),len(first)))
print("top wallets selling dead buckets after the observation (gain = proceeds net of fee, bucket went to 0):")
for w,g in w_sell.most_common(12): print(" ",w, "usd %.0f"%g, "fills",w_sell_n[w], "events",len(w_ev[w]))
print("total wallets",len(w_sell),"total usd %.0f"%sum(w_sell.values()))
json.dump(dict(tot={str(k):v for k,v in tot.items()}, wallets=w_sell.most_common(40)), open("/home/user/polymarket-lab/data/x3/wx/tape_w1.json","w"))
