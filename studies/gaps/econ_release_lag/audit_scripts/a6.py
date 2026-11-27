import sys; sys.path.insert(0, "/tmp/claude-0/-home-user/05556429-066d-541b-b886-b8da26bcc648/scratchpad/audit")
import json, collections, time, math, random, statistics as st
from a1 import *
FEE_CHANGE=1795219140
rep=[m for m in kept if m["T"]>=SPLIT]
def day(m): return time.strftime("%Y-%m-%d", time.gmtime(m["T"]))
def summarize(name, ms, res, days):
    cl=collections.defaultdict(float)
    for m in ms: cl[m["T"]]+=res[m["cond"]]["net"]
    xs=list(cl.values()); mu,se,t=tstat(xs); tot=sum(xs); cost=sum(res[m["cond"]]["cost"] for m in ms)
    print(f"  {name:<62} rel {len(xs):>2} (nonzero {sum(1 for x in xs if x>0):>2}) mk {len(ms):>3} (fills {sum(1 for m in ms if res[m['cond']]['fills']):>2}) net {tot:8.1f} cost {cost:7.0f} $/day {tot/days:6.2f} t {t:5.2f}")
    return tot
for d in (30,5):
    print(f"\n===== d = {d} s")
    res={m["cond"]: e4(rows_gaps(m), m, d) for m in kept}
    summarize("ALL (analyst definition)", kept, res, 87); base=summarize("REPORTING (analyst definition)", rep, res, 43)
    # per-day and per-market concentration, reporting part
    byday=collections.defaultdict(float); 
    for m in rep: byday[day(m)]+=res[m["cond"]]["net"]
    bd=max(byday, key=byday.get); print("   reporting: best day", bd, round(byday[bd],1), "| days with profit:", sum(1 for v in byday.values() if v>0), "of", len(byday), "release days")
    summarize("REPORTING minus best day", [m for m in rep if day(m)!=bd], res, 43)
    top10=sorted(rep, key=lambda m:-res[m["cond"]]["net"])[:10]; t10={m["cond"] for m in top10}
    print("   best ten markets carry", round(sum(res[c]["net"] for c in t10),1))
    summarize("REPORTING minus best ten markets", [m for m in rep if m["cond"] not in t10], res, 43)
    summarize("REPORTING minus best day and best ten markets", [m for m in rep if m["cond"] not in t10 and day(m)!=bd], res, 43)
    alld=collections.defaultdict(float)
    for m in kept: alld[day(m)]+=res[m["cond"]]["net"]
    bda=max(alld, key=alld.get); summarize(f"ALL minus best day ({bda})", [m for m in kept if day(m)!=bda], res, 87)
    ta={m["cond"] for m in sorted(kept, key=lambda m:-res[m["cond"]]["net"])[:10]}
    summarize("ALL minus best ten markets", [m for m in kept if m["cond"] not in ta], res, 87)
    # exclusions that correspond to named defects
    summarize("REPORTING unflagged only", [m for m in rep if not m["flag"]], res, 43)
    summarize("REPORTING unflagged, without AR-CPI-oct (first reaction at +39 s)", [m for m in rep if not m["flag"] and m["release"]!="AR-CPI-oct"], res, 43)
    summarize("REPORTING unflagged, without AR-CPI-oct and DE-GDP-q3", [m for m in rep if not m["flag"] and m["release"] not in ("AR-CPI-oct","DE-GDP-q3")], res, 43)
    summarize("REPORTING tier A (US official) only", [m for m in rep if m["tier"]=="A"], res, 43)
    summarize("REPORTING tier A unflagged", [m for m in rep if m["tier"]=="A" and not m["flag"]], res, 43)
    summarize("ALL tier A unflagged", [m for m in kept if m["tier"]=="A" and not m["flag"]], res, 87)
    # fee sensitivity: measured economics rate ~0.04 before 2026-11-21 (NOTES), 0.01 after
    r2={}
    for m in kept:
        rate=0.04 if m["T"]<FEE_CHANGE else 0.01
        r2[m["cond"]]=e4(rows_gaps(m), m, d, rate=rate)
    print("   fees at 0.01:", round(sum(v["fee"] for v in res.values()),2), " at measured 0.04 before 11-21:", round(sum(v["fee"] for v in r2.values()),2))
    summarize("REPORTING, fee 0.04 before 2026-11-21", rep, r2, 43); summarize("ALL, fee 0.04 before 2026-11-21", kept, r2, 87)
    # lag sensitivity
    for lag in (2,4):
        r3={m["cond"]: e4(rows_gaps(m), m, d, lag=lag) for m in kept}
        summarize(f"REPORTING, lag {lag} s instead of 3", rep, r3, 43); summarize(f"ALL, lag {lag} s instead of 3", kept, r3, 87)
    # carry: only fills within 2 h of the release
    r4={m["cond"]: e4(rows_gaps(m), m, d, tmax=7200) for m in kept}
    summarize("REPORTING, fills within 2 h of T only", rep, r4, 43)
    # 're-dip' decomposition: fill price at least 5c below an earlier post-release print of the winner => fresh order, not a resting stale quote
    stale=fresh=0.0; srel=collections.defaultdict(float); frel=collections.defaultdict(float)
    for m in kept:
        w=0 if m["winner"]=="Yes" else 1
        rows=sorted(rows_gaps(m), key=lambda r:r[0]); hi={}; mx=0
        seq=[]
        for ts,side,oi,p,z,wal in rows:
            off=ts-3-m["T"]
            if off<0: continue
            wp=p if oi==w else 1-p
            seq.append((off,wp))
        for off,wp,q,wal in res[m["cond"]]["fills"]:
            prior=max([x[1] for x in seq if x[0]<off], default=0)
            g=q*(1-wp)-0.01*wp*(1-wp)*q
            if prior>=wp+0.05: fresh+=g; frel[m["release"]]+=g
            else: stale+=g; srel[m["release"]]+=g
    print(f"   decomposition of net: fills priced >=5c BELOW an earlier post-release print (offer appeared after the market had moved): {fresh:.1f}; other (could have been resting): {stale:.1f}")
    print("     fresh-offer by release:", {k:round(v,1) for k,v in sorted(frel.items(), key=lambda kv:-kv[1])[:8]})
    print("     possibly-resting by release:", {k:round(v,1) for k,v in sorted(srel.items(), key=lambda kv:-kv[1])[:8]})
    # caps
    print("   max cost in one market:", round(max(v["cost"] for v in res.values()),2), "| markets at the $500 cap:", sum(1 for v in res.values() if v["cost"]>499.99))
    # bootstrap over reporting clusters
    cl=collections.defaultdict(float)
    for m in rep: cl[m["T"]]+=res[m["cond"]]["net"]
    xs=list(cl.values()); rng=random.Random(1); bs=sorted(sum(xs[rng.randrange(len(xs))] for _ in xs) for _ in range(5000))
    print("   reporting total bootstrap 95% CI by release:", round(bs[125],1), "to", round(bs[4875],1), "| median release", st.median(xs), "| releases with zero:", sum(1 for x in xs if x==0), "of", len(xs))
# dropped tier-B releases at nominal T
dropped=[m for m in mk if status[m["release"]].startswith("DROPPED")]
for d in (5,30):
    r={m["cond"]: e4(rows_gaps(m), m, d) for m in dropped}
    print(f"\ndropped tier-B (27 mk) at nominal T, d={d}: net {sum(v['net'] for v in r.values()):.1f} cost {sum(v['cost'] for v in r.values()):.0f} markets with fills {sum(1 for v in r.values() if v['fills'])}")
    for m in dropped:
        if r[m["cond"]]["fills"]: print("    ", m["release"], m["slug"][:50], round(r[m["cond"]]["net"],1), r[m["cond"]]["fills"][:5])
