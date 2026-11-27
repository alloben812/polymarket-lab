import sys; sys.path.insert(0, "/tmp/claude-0/-home-user/05556429-066d-541b-b886-b8da26bcc648/scratchpad/audit"); sys.dont_write_bytecode=True
import collections
from a1 import *
B=collections.defaultdict(lambda:[0.0,0.0,0.0,0.0])   # toward $, against $, toward gap (<0.95), n
for m in kept:
    w=0 if m["winner"]=="Yes" else 1
    for ts,side,oi,p,z,wal in rows_gaps(m):
        o=ts-m["T"]            # raw block-time offset
        if not (-60<=o<3): continue
        k="block T-60..T-1" if o<0 else f"block T+{o}"
        wp=p if oi==w else 1-p
        longw=(side=="BUY" and oi==w) or (side=="SELL" and oi!=w)
        if wp<0.90:
            if longw: B[k][0]+=z*p; B[k][2]+=z*(1-wp)
            else: B[k][1]+=z*p
            B[k][3]+=1
for k in sorted(B): print(k, "prints at winner price < 0.90:", int(B[k][3]), "| taker $ toward winner", round(B[k][0]), "gap $", round(B[k][2]), "| against", round(B[k][1]))
