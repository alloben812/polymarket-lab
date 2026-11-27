import sys; sys.path.insert(0, "/tmp/claude-0/-home-user/05556429-066d-541b-b886-b8da26bcc648/scratchpad/audit")
import json, gzip, collections, statistics as st, os
from a1 import *
# 1. tape notional vs gamma volume for complete tapes
rat=[]
for m in mk:
    d=json.load(gzip.open(f"{D}/tapes/{m['cond']}.json.gz"))
    if d["status"]!="complete": continue
    notional=sum(r[4]*r[5] for r in d["rows"]); rat.append((notional/m["vol"], m["release"], m["slug"][:40], round(notional), round(m["vol"]), d["n"], m["negRisk"]))
rs=sorted(x[0] for x in rat)
print("complete tapes:", len(rat), "tape notional / volumeNum: min %.2f p10 %.2f median %.2f p90 %.2f max %.2f"%(rs[0], rs[len(rs)//10], st.median(rs), rs[9*len(rs)//10], rs[-1]))
print("  ratio<0.5:", sum(r<0.5 for r in rs), " 0.5-0.9:", sum(0.5<=r<0.9 for r in rs), " 0.9-1.1:", sum(0.9<=r<=1.1 for r in rs), " >1.1:", sum(r>1.1 for r in rs))
for x in sorted(rat)[:6]+sorted(rat)[-4:]: print("   ", x)
# 2. lag check: block-time offset (ts - T) of first print showing a big move toward the winner in uncertain markets
M={x["cond"]:x for x in json.load(open(f"{D}/measures.json"))}
hist=collections.Counter(); early=[]
for m in kept:
    w=0 if m["winner"]=="Yes" else 1
    rows=sorted(rows_gaps(m), key=lambda r:r[0])
    wp=lambda r: r[3] if r[2]==w else 1-r[3]
    pre=[r for r in rows if r[0]-m["T"] < -30]
    if not pre: continue
    ref=wp(pre[-1])
    if ref>=0.90: continue
    for r in rows:
        o=r[0]-m["T"]
        if o < -30: continue
        if wp(r) >= max(0.90, ref+0.10):
            hist[o if o<12 else 12]+=1
            if o<3: early.append((m["release"], m["slug"][:38], o, round(ref,2), round(wp(r),3), r[1], round(r[4],1)))
            break
print("\nblock-time offset (ts - T, NOT lag-adjusted) of first print with winner >= 0.90 in uncertain markets:", sorted(hist.items()))
print("  prints stamped before T+3 (classified 'pre-release' by LAG=3):", len(early))
for e in early: print("    ", e)
# how many markets have E1 taken from a print in block window [T-3 .. T+2] at a jumped price
jump=0; 
for m in kept:
    w=0 if m["winner"]=="Yes" else 1
    rows=sorted(rows_gaps(m), key=lambda r:r[0])
    wp=lambda r: r[3] if r[2]==w else 1-r[3]
    a=[r for r in rows if r[0]-m["T"]<0]; b=[r for r in rows if 0<=r[0]-m["T"]<3]
    if a and b and abs(wp(b[-1])-wp(a[-1]))>=0.10: jump+=1
print("  markets where a print stamped T..T+2 (counted as pre-release, sets E1) differs >=0.10 from the last print stamped < T:", jump)
# 3. rules text for the non-US +30 s contributors
ev=json.load(gzip.open(f"{D}/events_core.json.gz"))
for pat in ("germany-gdp-growth-in-q3","south-korea-gdp-growth-yoy-in-q3","argentina-monthly-inflation-october","core-cpi-yoy-october","october-inflation-us-annual"):
    for e in ev:
        if e["slug"].startswith(pat):
            print("\n###", e["slug"], "| closed", e.get("closedTime"), "| endDate", e.get("endDate"), "| nmarkets", len(e.get("markets") or []))
            print((e.get("description") or (e["markets"][0].get("description") or ""))[:1500])
            break
