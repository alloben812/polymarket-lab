import sys; sys.path.insert(0, "/tmp/claude-0/-home-user/05556429-066d-541b-b886-b8da26bcc648/scratchpad/audit"); sys.dont_write_bytecode=True
import json, gzip, collections, statistics as st
from a1 import *
import rc_copy as rc
# volume definition
rat=[]
for m in mk:
    d=json.load(gzip.open(f"{D}/tapes/{m['cond']}.json.gz"))
    if d["status"]!="complete": continue
    sh=sum(r[5] for r in d["rows"]); usd=sum(r[4]*r[5] for r in d["rows"]); rat.append((sh/m["vol"], usd/m["vol"]))
a=sorted(x[0] for x in rat); print("complete tapes: sum(shares)/volumeNum  min %.3f p10 %.3f median %.3f p90 %.3f max %.3f"%(a[0],a[len(a)//10],st.median(a),a[9*len(a)//10],a[-1]), "| within 2%:", sum(abs(x-1)<0.02 for x in a), "of", len(a))
# E2 / E3 own recomputation with lag sensitivity
BK=[(0,5),(5,30),(30,120),(120,600),(600,10**9)]
for lag in (3,2,0):
    e2=[]; gap=[0.0]*5; usd=[0.0]*5; wal=collections.defaultdict(float); n_unc=0; perrel=collections.defaultdict(list); gap_b=0.0; within7=0.0
    e1s=[]
    for m in kept:
        w=0 if m["winner"]=="Yes" else 1
        rows=sorted(rows_gaps(m), key=lambda r:r[0])
        P=[(ts-lag-m["T"], side, oi, (p if oi==w else 1-p), p, z, wal_) for ts,side,oi,p,z,wal_ in rows]
        pre=[x for x in P if x[0]<0]; post=[x for x in P if x[0]>=0]
        e1=pre[-1][3] if pre else None; e1s.append(e1)
        if e1 is not None and e1<0.90:
            n_unc+=1; t=next((x[0] for x in post if x[3]>=0.95-1e-9), None); e2.append(t)
            if t is not None: perrel[m["T"]].append(t)
        for off,side,oi,wp,p,z,wl in post:
            if wp<0.95-1e-9:
                informed=(side=="BUY" and oi==w) or (side=="SELL" and oi!=w)
                if informed:
                    i=next(i for i,(lo,hi) in enumerate(BK) if lo<=off<hi); gap[i]+=z*(1-wp); usd[i]+=z*p; wal[wl or "unknown"]+=z*(1-wp)
                    if off<=7: within7+=z*(1-wp)
                else: gap_b+=z*(1-wp)
    ok=sorted(x for x in e2 if x is not None); tot=sum(gap); top=sorted(wal.values(), reverse=True)
    pr=sorted(st.median(v) for v in perrel.values())
    print(f"\nLAG={lag}: median E1 {st.median([x for x in e1s if x is not None]):.3f}; uncertain markets {n_unc}; median s to 0.95: {st.median(ok)}; within 5/30/120 s: {sum(x<=5 for x in ok)}/{sum(x<=30 for x in ok)}/{sum(x<=120 for x in ok)}; never {sum(x is None for x in e2)}; per-release median {st.median(pr)} ({len(pr)} releases)")
    print(f"   E3(a) dollars {sum(usd):,.0f} gap {tot:,.0f} | gap by bucket {[round(g) for g in gap]} | within 30 s {100*(gap[0]+gap[1])/tot:.1f}% | within 7 s {100*within7/tot:.1f}% | wallets {len(wal)} top3 {100*sum(top[:3])/tot:.1f}% top10 {100*sum(top[:10])/tot:.1f}% | E3(b) gap {gap_b:,.0f}")
# wrong-side takers shortly after the release (people who acted on the number and bought the eventual loser at >= 0.50)
ws=collections.defaultdict(lambda:[0,0.0,0.0]); 
for m in kept:
    w=0 if m["winner"]=="Yes" else 1
    for ts,side,oi,p,z,wl in rows_gaps(m):
        off=ts-3-m["T"]
        if not (0<=off<=600): continue
        lp = (p if oi!=w else 1-p)          # price paid for the LOSER by the taker, if the taker ended up long the loser
        long_loser = (side=="BUY" and oi!=w) or (side=="SELL" and oi==w)
        if long_loser and lp>=0.50:
            x=ws[m["release"]]; x[0]+=1; x[1]+=z*lp; x[2]=max(x[2],lp)
print("\ntakers who went long the eventual LOSER at >= 0.50 within 10 min after T (count, dollars lost, max price):")
for k,v in sorted(ws.items(), key=lambda kv:-kv[1][1]): print("   ", k, v[0], round(v[1]), round(v[2],3))
print("   total lost $", round(sum(v[1] for v in ws.values())), "in", len(ws), "releases")
# coverage: events in the discovery file that no calendar row matches and no exclusion explains
ev=json.load(gzip.open(f"{D}/events_core.json.gz")); un=[]; ex=0; ma=0
for e in ev:
    if rc.match(e["slug"]): ma+=1; continue
    if rc.excluded_reason(e["slug"]): ex+=1; continue
    v=sum(float(x.get("volumeNum") or 0) for x in (e.get("markets") or [])); un.append((v, e["slug"], (e.get("endDate") or "")[:10]))
print(f"\nevents_core: {len(ev)} events; matched {ma}; excluded by rule {ex}; neither {len(un)}")
for v,s,d in sorted(un, reverse=True)[:45]: print(f"   {v:>12,.0f} {d} {s[:90]}")
