# BTC 5m: what trades between the end of the window and settlement, 2026-11-26 (variant C1, the only one)
import sys, collections, statistics as st, datetime as dt
sys.path.insert(0,"/home/user/polymarket-lab")
from pmlab import updown
s=int(dt.datetime(2026,11,26,0,0,tzinfo=dt.timezone.utc).timestamp()); e=s+12*3600
n=0; agg=collections.Counter(); lastts=[]; shown=False
def pick(r,*ks):
    for k in ks:
        if k in r: return r[k]
for t0 in updown.windows("5m",s,e):
    try:
        m=updown.load_market("btc","5m",t0); rows=updown.tape(m["condition"])
    except Exception as ex:
        agg["err"]+=1; continue
    if not rows: continue
    if not shown: print("tape row:",{k:rows[0][k] for k in list(rows[0])[:12]}); shown=True
    n+=1; end=m["t1"]; up=m["final_price"]>=m["price_to_beat"]
    T=lambda r: float(pick(r,"timestamp","ts","t","time"))
    lastts.append(max(T(r) for r in rows)-end)
    for r in rows:
        p=float(pick(r,"price","p")); sz=float(pick(r,"size","sz","q","z")); usd=p*sz
        agg["total_usd"]+=usd
        if T(r)-3<end: continue
        agg["post_usd"]+=usd; agg["post_n"]+=1
        oc=str(pick(r,"outcome","o") or "").lower()
        isup = (oc=="up") if oc in("up","down") else (int(pick(r,"outcome_index","oi") or 0)==0)
        won = isup==up; side=str(pick(r,"side","s")).upper()
        key=("BUY" if side.startswith("B") else "SELL")+("_winner" if won else "_loser")
        agg[(key,"usd")]+=usd; agg[(key,"n")]+=1
        if key=="BUY_winner":
            agg[("BUY_winner","gain_after_fee")]+=(1-p)*sz-0.05*p*(1-p)*sz
            if p<0.97: agg[("BUY_winner_below_0.97","usd")]+=usd; agg[("BUY_winner_below_0.97","gain_after_fee")]+=(1-p)*sz-0.05*p*(1-p)*sz; agg[("BUY_winner_below_0.97","n")]+=1
        if key=="BUY_loser": agg[("BUY_loser","loss")]+=usd
print("markets",n,"errors",agg["err"])
print("total $ %.0f ; $ with block time >= end+3 s: %.0f (%.2f%%), fills %d"%(agg["total_usd"],agg["post_usd"],100*agg["post_usd"]/max(agg["total_usd"],1),agg["post_n"]))
for k,v in sorted((k,v) for k,v in agg.items() if isinstance(k,tuple)): print(" ",k, round(v,1))
if lastts: print("last fill relative to end (s): median %.0f p90 %.0f max %.0f"%(st.median(lastts), sorted(lastts)[int(0.9*len(lastts))], max(lastts)))
