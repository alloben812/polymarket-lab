import sys; sys.path.insert(0, "/tmp/claude-0/-home-user/05556429-066d-541b-b886-b8da26bcc648/scratchpad/audit"); sys.dont_write_bytecode=True
import json, collections, statistics as st
from a1 import *
rep=[m for m in kept if m["T"]>=SPLIT]
def e4o(rows, m, d, order, cap=500.0, maxp=0.97, rate=0.01, lag=3):
    w=0 if m["winner"]=="Yes" else 1; P=[]
    for ts,side,oi,p,z,wal in rows:
        off=ts-lag-m["T"]
        if off<d: continue
        if side=="BUY" and oi==w: wp=p
        elif side=="SELL" and oi!=w: wp=1-p
        else: continue
        if wp>maxp+1e-9: continue
        P.append((off,wp,z,wal))
    P.sort(key=(lambda x:(x[0], x[1])) if order=="cheap" else (lambda x:(x[0], -x[1])))
    bud=cap; net=cost=0.0
    for off,wp,z,wal in P:
        q=min(z,bud/wp)
        if q<=1e-9: break
        net+=q*(1-wp)-rate*wp*(1-wp)*q; cost+=q*wp; bud-=q*wp
    return net,cost
for d in (5,30):
    for order in ("cheap","dear"):
        a=sum(e4o(rows_gaps(m),m,d,order)[0] for m in kept); b=sum(e4o(rows_gaps(m),m,d,order)[0] for m in rep)
        print(f"d={d} same-second prints taken {order}est first: ALL net {a:,.0f} ({a/87:.2f}/day) REPORTING {b:,.0f} ({b/43:.2f}/day)")
# extra start delays as a sensitivity diagnostic (not new strategy variants)
for d in (5,6,7,8,10,15,20,30,45,60):
    res={m["cond"]: e4(rows_gaps(m), m, d) for m in kept}
    a=sum(v["net"] for v in res.values()); b=sum(res[m["cond"]]["net"] for m in rep)
    us=sum(res[m["cond"]]["net"] for m in kept if m["tier"]=="A" and not m["flag"])
    print(f"start +{d:>2}s: ALL {a:7.0f} ({a/87:5.2f}/day)  REPORTING {b:7.0f} ({b/43:5.2f}/day)  tier A unflagged ALL {us:7.0f} ({us/87:5.2f}/day)")
# share of d=5 net in fills stamped +5/+6; who took those prints
res={m["cond"]: e4(rows_gaps(m), m, 5) for m in kept}
tot=0; f56=0; byw=collections.defaultdict(float)
for m in kept:
    for off,wp,q,wal in res[m["cond"]]["fills"]:
        g=q*(1-wp)-0.01*wp*(1-wp)*q; tot+=g; byw[wal]+=g
        if off in (5,6): f56+=g
top=sorted(byw.items(), key=lambda kv:-kv[1])
print(f"d=5: net {tot:.0f}; in fills stamped +5/+6 s: {f56:.0f} = {100*f56/tot:.0f}%; prints behind the net belong to {len(byw)} wallets; top 3 {100*sum(v for _,v in top[:3])/tot:.0f}% top 6 {100*sum(v for _,v in top[:6])/tot:.0f}%", top[:6])
res=({m["cond"]: e4(rows_gaps(m), m, 30) for m in kept}); byw=collections.defaultdict(float); tot=0
for m in kept:
    for off,wp,q,wal in res[m["cond"]]["fills"]:
        g=q*(1-wp)-0.01*wp*(1-wp)*q; tot+=g; byw[wal]+=g
top=sorted(byw.items(), key=lambda kv:-kv[1]); print(f"d=30: net {tot:.0f}; wallets behind the prints {len(byw)}; top 3 {100*sum(v for _,v in top[:3])/tot:.0f}%", [(w,round(v)) for w,v in top[:6]])
# per-release wallet concentration on E3(a)
per=collections.defaultdict(lambda: collections.defaultdict(float))
for m in kept:
    w=0 if m["winner"]=="Yes" else 1
    for ts,side,oi,p,z,wal in rows_gaps(m):
        off=ts-3-m["T"]; wp=p if oi==w else 1-p
        if off>=0 and wp<0.95-1e-9 and ((side=="BUY" and oi==w) or (side=="SELL" and oi!=w)): per[m["T"]][wal]+=z*(1-wp)
cnt=[len(v) for v in per.values()]; sh=[sum(sorted(v.values(),reverse=True)[:3])/sum(v.values()) for v in per.values()]
print("releases with any stale taker trade:", len(per), "median wallets", st.median(cnt), "median top-3 share", round(st.median(sh),3), "| releases where top-3 share < 90%:", sum(s<0.9 for s in sh))
# stale gap dollars per release: how concentrated in few releases
g=sorted(((sum(v.values()), T) for T,v in per.items()), reverse=True); tg=sum(x for x,_ in g)
print("E3 gap by release: top 3 releases", round(100*sum(x for x,_ in g[:3])/tg), "% ; top 10", round(100*sum(x for x,_ in g[:10])/tg), "% ; median release with any", round(st.median([x for x,_ in g])), "; releases with none:", 51-len(g))
