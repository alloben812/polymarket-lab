import sys; sys.path.insert(0,'/home/user/polymarket-lab/studies/gaps/counter_markets/audit')
import numpy as np, bisect, collections
import recompute as R
ev=R.events
def yes_price(m, lo_t, hi_t):
    yi=m['outcomes'].index('Yes'); ytok=m['toks'][yi]
    ts,rows=R.tape(m['cid']); out=None
    for r in rows[bisect.bisect_left(ts,lo_t+3):]:
        mt=r['t']-3
        if mt>hi_t: break
        out=(r['p'] if r['tok']==ytok else 1-r['p']) if True else None
        if r['side']=='SELL' and r['tok']==ytok: out=r['p']
    return out
for lead in (600,300,120):
    T0=None; diff=0; n=0; rows=[]
    for e in ev:
        T=e['e']-lead
        created=[]  # source count at T (created+30 s <= T)
        P=R.posts(e['handle']); w=P[(P[:,0]>=e['s'])&(P[:,0]<e['e'])]
        Nc=int((w[:,0]+30<=T).sum()); Ni=R.N_at(e,T); F=e['F']
        b=lambda N: next((i for i,((lo,hi),m,y) in enumerate(e['mk']) if lo<=N<=hi),None)
        bc,bi,bf=b(Nc),b(Ni),b(F)
        n+=1
        if bc!=bi:
            diff+=1
            pc=yes_price(e['mk'][bc][1],T-300,T+60) if bc is not None else None
            pi=yes_price(e['mk'][bi][1],T-300,T+60) if bi is not None else None
            rows.append((e['slug'][:40],Nc,Ni,F,bc==bf,bi==bf,pc,pi))
    print(f'lead {lead}s: events {n}, bucket differs between source and tracker count: {diff}')
    for r in rows[:12]: print('   ',r)
    # of these: how often is the source bucket the final one vs tracker bucket
    print('   source bucket final:', sum(r[4] for r in rows), 'tracker bucket final:', sum(r[5] for r in rows), 'of', len(rows))
