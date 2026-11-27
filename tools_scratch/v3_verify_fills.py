import sys, time, datetime as dt, collections, re
from pmlab import dataapi
def ts(s): return int(dt.datetime.strptime(s,"%Y-%m-%d").replace(tzinfo=dt.timezone.utc).timestamp())
def prof(name,w,a,b):
    allr=list(dataapi.iter_trades(user=w,start=ts(a),end=ts(b),taker_only=False))
    tak=list(dataapi.iter_trades(user=w,start=ts(a),end=ts(b),taker_only=True))
    key=lambda r:(r.get("transaction_hash"),r.get("asset") or r.get("token_id"),r.get("price"),r.get("size"),r.get("timestamp"))
    n=lambda rs:sum(float(r["size"])*float(r["price"]) for r in rs)
    print(f"{name} {a}..{b}: fills {len(allr)} notional ${n(allr):,.0f} | taker rows {len(tak)} notional ${n(tak):,.0f} = {n(tak)/max(n(allr),1)*100:.0f}% taker")
    if allr: print("   row keys:",sorted(allr[0].keys())[:30])
    g=collections.Counter(); 
    for r in allr:
        t=(r.get("title") or r.get("market_title") or r.get("slug") or "?")
        t=re.sub(r"\d+","#",t)[:55]; g[t]+=float(r["size"])*float(r["price"])
    for k,v in g.most_common(8): print(f"   ${v:>10,.0f}  {k}")
    side=collections.Counter()
    for r in allr: side[r.get("side")]+=float(r["size"])*float(r["price"])
    print("   by side:",{k:round(v) for k,v in side.items()})
    # taker buys by price bucket
    bk=collections.Counter()
    for r in tak:
        p=float(r["price"]); bk[("<0.05" if p<.05 else "0.05-0.2" if p<.2 else "0.2-0.5" if p<.5 else "0.5-0.8" if p<.8 else "0.8-0.95" if p<.95 else ">=0.95", r.get("side"))]+=float(r["size"])*p
    print("   taker notional by price/side:",{k:round(v) for k,v in sorted(bk.items())})
prof("ColdMath","0x594edb9112f526fa6a80b8f858a6379c8a2c1c11","2026-11-22","2026-11-28")
prof("BeefSlayer","0x331bf91c132af9d921e1908ca0979363fc47193f","2026-09-01","2026-11-28")
