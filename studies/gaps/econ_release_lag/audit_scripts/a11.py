import sys; sys.path.insert(0, "/tmp/claude-0/-home-user/05556429-066d-541b-b886-b8da26bcc648/scratchpad/audit"); sys.dont_write_bytecode=True
import json, collections
from a1 import *
# prints in the last 60 s before T (lag-adjusted) for the five 'investigated and kept' releases + all tier A: size and direction
for rel in ("US-EMP-august","US-CPI-august","US-PCE-august","US-ISMM-october","AR-CPI-oct","AR-CPI-sep","AR-CPI-aug"):
    ms=[m for m in kept if m["release"]==rel]; pre=[]; first=[]
    for m in ms:
        w=0 if m["winner"]=="Yes" else 1
        for ts,side,oi,p,z,wal in rows_gaps(m):
            off=ts-3-m["T"]; wp=p if oi==w else 1-p
            if -60<=off<0: pre.append((off, m["slug"][-28:], side, "W" if oi==w else "L", round(p,3), round(z,1), round(z*p,1)))
            if 0<=off<=60: first.append((off, round(wp,3), round(z*p)))
    first.sort()
    print(rel, "| prints in [-60,0):", len(pre), "dollars", round(sum(x[-1] for x in pre),1), sorted(pre)[:6], "| first post prints:", first[:4], "| post prints in first 60 s:", len(first))
# pre-release informed drift: in the last 60 s before T, did takers move toward the winner? (dollar-weighted, all kept releases)
tow=away=0.0
for m in kept:
    w=0 if m["winner"]=="Yes" else 1
    for ts,side,oi,p,z,wal in rows_gaps(m):
        off=ts-3-m["T"]
        if -60<=off<0:
            longw=(side=="BUY" and oi==w) or (side=="SELL" and oi!=w)
            if longw: tow+=z*p
            else: away+=z*p
print("last 60 s before T, all kept markets: taker dollars toward the winner", round(tow), "against", round(away))
# releases per calendar day and count of days
import time
days=collections.Counter(time.strftime("%Y-%m-%d", time.gmtime(m["T"])) for m in {m["T"]:m for m in kept}.values())
print("release days:", len(days), "| reporting release days:", sum(1 for d in days if d>="2026-10-15"))
