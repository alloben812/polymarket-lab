"""Post-hoc look at earlier entry windows (NOT a protocol variant: exploratory, counts as extra variants). Weighted mean net edge with match-level SE; early/late split."""
import sys, math, datetime as dt; sys.path.insert(0,'.')
from a1_recompute import *
CUT = dt.datetime(2026,10,26,13,35,tzinfo=dt.timezone.utc).timestamp()
def run2(lo_h,hi_h,pmin=0.05,pmax=0.45):
    rows=[]
    for cls, recs, w in (('A', U['A'], 1), ('C', U['control'], 8)):
        for r in recs:
            if cls=='A':
                m=[x for x in r['markets'] if x['type']=='moneyline'][0]; cid,outs,fin,start,closed=m['cid'],m['outcomes'],m.get('api_final') or m['final'],m['start'] or r['startTime'],m['closed']
            else:
                cid,outs,fin,start,closed=r['cid'],r['outcomes'],r.get('api_final') or r['final'],r['start'],r['closed']
            if start is None: continue
            tp=load(cid)
            if tp is None: continue
            for t,i,p,z in buyables(tp,outs):
                if start-lo_h*H<=t<=start-hi_h*H and pmin-1e-9<=p<=pmax+1e-9:
                    rows.append(dict(cls=cls,w=w,p=p,pay=fin[i],z=z,start=start,closed=closed,lead=(start-t)/H,part='early' if closed<CUT else 'late')); break
    return rows
def rep(rows,label,rate=0.05):
    if not rows: print(label,'none'); return
    W=sum(r['w'] for r in rows)
    e=[r['pay']-r['p']-rate*r['p']*(1-r['p']) for r in rows]
    m=sum(r['w']*x for r,x in zip(rows,e))/W
    se=math.sqrt(sum((r['w']*(x-m))**2 for r,x in zip(rows,e)))/W
    wo=sum(r['cls']=='A' for r in rows); q=sum(r['w'] for r in rows if r['cls']=='A')/W
    prem=sum(r['w']*(0.5-r['p']) for r in rows if r['cls']=='A')/W; fee=sum(r['w']*rate*r['p']*(1-r['p']) for r in rows)/W
    print(f"{label:30s} n={len(rows):4d} wo={wo:3d} q={q*100:.2f}% prem-fee={100*(prem-fee):+.2f}c net={m*100:+.2f}c [{(m-1.96*se)*100:+.2f},{(m+1.96*se)*100:+.2f}] t={m/se:+.2f}")
if __name__=='__main__':
    for lo,hi in ((6,1),(24,6),(48,24),(72,24),(48,6),(36,12),(100,24)):
        rows=run2(lo,hi)
        rep(rows,f'T-{lo}..T-{hi}h all')
        for part in ('early','late'):
            rep([r for r in rows if r['part']==part],f'   {part}')
    # lead dist of walkover vs control (first print any time before T)
