"""Independent recompute of V1 pooled (key number) from raw gamma events + raw cached tapes. Own parsing, own fill logic.
Does not import the study's code (only reads the same raw files)."""
import json, gzip, os, re, math, sys, collections
from datetime import datetime, timezone
RAW='/home/user/polymarket-lab/data/gaps_mentions_model/events_closed_raw.json'
TAP='/home/user/polymarket-lab/data/mentions_tapes'
def T(s):
    if not s: return None
    s=s.strip().replace(' ','T')
    s=re.sub(r'\+00(:00)*$','+00:00',s).replace('Z','+00:00')
    try: return datetime.fromisoformat(s).timestamp()
    except Exception: return None
LO=datetime(2026,8,1,tzinfo=timezone.utc).timestamp(); HI=datetime(2026,11,28,tzinfo=timezone.utc).timestamp()
S2=datetime(2026,9,29,tzinfo=timezone.utc).timestamp()
evs=json.load(open(RAW))
def run(start_mode='study', lag=3, rate=0.01, cap=20.0, lo_px=0.50, hi_px=0.95, win_h=24, slip=0.0, verbose=False):
    trades=[]
    for e in evs:
        slug=e['slug']
        if 'earnings' in slug: typ='earn'
        elif any(k in slug for k in ('this-week','in-october','in-november','in-december','in-september','in-august','in-july','in-june','headlines','this-month','week-of','by-','in-2026','this-year')): typ='period'
        else: typ='live'
        if typ=='period': continue
        st=T(e.get('startTime')); cr=T(e.get('creationDate') or e.get('createdAt'))
        mk=[]
        for m in e.get('markets') or []:
            try:
                outs=json.loads(m['outcomes']); op=[float(v) for v in json.loads(m['outcomePrices'])]
            except Exception: continue
            if outs!=['Yes','No'] or sorted(op)!=[0.0,1.0]: continue
            mk.append((m,op))
        if not mk: continue
        fc=min((T(m.get('closedTime')) for m,_ in mk if T(m.get('closedTime'))), default=None)
        if not(st and cr and fc and st-cr>=3600 and st<=fc): continue
        if not(LO<=st<HI): continue
        for m,op in mk:
            q=(m.get('question') or '').lower()
            if re.search(r'\d+\+\s*times',q): continue
            if not re.findall(r'["“”]([^"“”]+)["“”]',q): continue
            p=f"{TAP}/{m['conditionId']}.json.gz"
            if not os.path.exists(p): continue
            rows=json.load(gzip.open(p,'rt'))
            a,b=st-win_h*3600, st-300
            entry=None
            for r in sorted(rows,key=lambda r:r['t']):
                tt=r['t']-lag
                if not(a<=tt<=b): continue
                # No ask price implied by this row
                if r['side']=='BUY' and r['o']=='No': px=r['p']
                elif r['side']=='SELL' and r['o']=='Yes': px=1-r['p']
                else: continue
                if lo_px<=px<=hi_px:
                    entry=(tt,px,r['s']); break
            if entry is None: continue
            tt,px,sz=entry; px=px+slip
            won = (op[1]==1.0)  # No won iff outcomePrices = [0,1]
            sh=min(sz,cap/px)
            pnl=sh*(1 if won else 0)-sh*px-rate*sh*px*(1-px)
            trades.append(dict(ev=slug,t=tt,st=st,px=px,sh=sh,stake=sh*px,pnl=pnl,won=won,seg='S1' if st<S2 else 'S2',q=q[:90]))
    return trades
def summ(tr,name):
    byev=collections.defaultdict(lambda:[0,0])
    for t in tr: byev[t['ev']][0]+=t['pnl']; byev[t['ev']][1]+=t['stake']
    n=len(byev); num=sum(v[0] for v in byev.values()); den=sum(v[1] for v in byev.values())
    r=num/den; resid=[v[0]-r*v[1] for v in byev.values()]
    se=math.sqrt(n/(n-1)*sum(x*x for x in resid))/den
    print(f'{name}: trades {len(tr)} events {n} stake {den:,.0f} pnl {num:+,.1f} return {100*r:+.2f}% [{100*(r-1.96*se):+.2f},{100*(r+1.96*se):+.2f}] won {sum(t["won"] for t in tr)}')
    return r
if __name__=='__main__':
    tr=run()
    summ(tr,'V1 pooled'); summ([t for t in tr if t['seg']=='S1'],'V1 S1'); summ([t for t in tr if t['seg']=='S2'],'V1 S2')
    json.dump(tr,open('/tmp/claude-0/-home-user/05556429-066d-541b-b886-b8da26bcc648/scratchpad/v1_audit_trades.json','w'))
