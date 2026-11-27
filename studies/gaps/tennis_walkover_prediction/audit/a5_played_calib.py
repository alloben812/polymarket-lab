import sys, math; sys.path.insert(0,'.')
from a3_early_entry import *
for lo,hi in ((6,1),(24,6),(48,24),(100,1)):
    rows=[r for r in run2(lo,hi) if r['cls']=='C']
    W=sum(r['w'] for r in rows); x=[r['pay']-r['p'] for r in rows]
    m=sum(r['w']*v for r,v in zip(rows,x))/W; se=math.sqrt(sum((r['w']*(v-m))**2 for r,v in zip(rows,x)))/W
    print(f"played-only T-{lo}..T-{hi}h n={len(rows)} W={W:.0f} mean(win-p)={m*100:+.2f}c [{(m-1.96*se)*100:+.2f},{(m+1.96*se)*100:+.2f}]")
# walkover count and sizes per week, buyable size in 24-48h
rows=run2(48,24)
import statistics as st
print('48-24h first print size shares median',st.median(r['z'] for r in rows),'avg p',sum(r['p'] for r in rows)/len(rows))
