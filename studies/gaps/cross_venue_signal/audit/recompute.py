"""Independent recompute (audit). Reads raw cached data only: football-data CSVs, gamma match list (matches.json used only
for the cid/role/outcome mapping, re-validated against FTR), taker tapes. Own de-margin, own E1, own fill rule."""
import csv, gzip, json, math, statistics as st, sys, random
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
R = Path('/home/user/polymarket-lab/data')
D = R/'gaps_cross_venue_signal'
LON = ZoneInfo('Europe/London')
ms = json.load(open(D/'matches.json'))
# raw CSV rows keyed by (div, home, away, date)
fd = {}
for div in ['E0','E1','SP1','D1','I1','F1']:
    for r in csv.DictReader(open(D/'raw'/f'fd_2627_{div}.csv', encoding='utf-8-sig')):
        if r.get('FTR'): fd[(div, r['HomeTeam'], r['AwayTeam'], r['Date'])] = r
def tape(cid):
    for d in (D/'tapes', R/'gaps_sports_lag'/'tapes'):
        p = d/f'{cid}.jsonl.gz'
        if p.exists(): return [json.loads(l) for l in gzip.open(p,'rt')]
def dm(h,d,a):
    inv=[1/float(h),1/float(d),1/float(a)]; s=sum(inv); return [x/s for x in inv]
def e1(k):
    dt = datetime.fromtimestamp(k-1800, timezone.utc)
    for back in range(0,9):
        c = (dt - timedelta(days=back)).replace(hour=18,minute=0,second=0,microsecond=0)
        if c.timestamp() <= k-1800 and c.weekday() in (1,4): return int(c.timestamp())
FEE=0.05
fee=lambda p: FEE*p*(1-p)
rows=[]
unsorted=0
for m in ms:
    r = fd[(m['div'], m['home'], m['away'], m['date'])]
    # independent kickoff from CSV
    k = int(datetime.strptime(r['Date']+' '+r['Time'],'%d/%m/%Y %H:%M').replace(tzinfo=LON).timestamp())
    assert abs(k-m['k'])<1
    s1 = dm(r['BFEH'],r['BFED'],r['BFEA']) if r['BFEH'] and r['BFED'] and r['BFEA'] else dm(r['AvgH'],r['AvgD'],r['AvgA'])
    s2 = dm(r['BFECH'],r['BFECD'],r['BFECA'])
    tp = {x: tape(m['markets'][x]['cid']) for x in 'HDA'}
    for x in 'HDA':
        ts=[z['t'] for z in tp[x]]
        if ts!=sorted(ts): unsorted+=1
    rows.append(dict(k=k,div=m['div'],ev=m['event'],s1=s1,s2=s2,tp=tp,ftr=r['FTR'],e1=e1(k)))
print('matches',len(rows),'unsorted tapes',unsorted)
def prints(row, E, W, sell=False, thr=None):
    out=[]
    for i,x in enumerate('HDA'):
        for z in row['tp'][x]:
            if z['t']<E or z['t']>E+W: continue
            if not (0.01<=z['p']<=0.99): continue
            if z['s']=='BUY': tok=z['o']; p=z['p']
            elif sell:  # taker SELL of token T at p == a resting bid == buyable complement at 1-p
                tok='No' if z['o']=='Yes' else 'Yes'; p=1-z['p']
                if not (0.01<=p<=0.99): continue
            else: continue
            out.append((z['t'],x,tok,p,z['z'],i))
    out.sort()
    return out
def evaluate(sig, X, Ewin, sell=False, getE=None):
    trs=[]
    for row in rows:
        pf = row['s1'] if sig=='S1' else row['s2']
        E = row['e1'] if sig=='S1' else row['k']-1800
        if sig=='S1' and (E is None or row['k']-E>96*3600): continue
        if getE: E = getE(row, E)
        W = Ewin(row, E)
        for (t,x,tok,p,z,i) in prints(row,E,W,sell):
            f = pf[i] if tok=='Yes' else 1-pf[i]
            if f-p>=X-1e-12:
                win = (row['ftr']==x) if tok=='Yes' else (row['ftr']!=x)
                pnl=(1.0 if win else 0)-p-fee(p)
                trs.append(dict(k=row['k'],t=t,p=p,f=f,win=win,ret=pnl/p,pnl=pnl,z=z,ev=row['ev'],E=E,div=row['div']))
                break
    return trs
def summ(trs, label):
    n=len(trs)
    if n==0: print(f'{label}: n=0'); return
    r=[t['ret'] for t in trs]; mu=st.mean(r)
    se=st.stdev(r)/math.sqrt(n) if n>1 else float('nan')
    g=st.mean(t['f']-t['p'] for t in trs)
    # exact unit = match, one trade each -> no clustering needed beyond match. day-cluster:
    print(f'{label}: n={n} ret/$ {mu*100:+.1f}% se {se*100:.1f} win {st.mean(t["win"] for t in trs):.2f} avg gap {g*100:.1f}pts avg p {st.mean(t["p"] for t in trs):.3f}')
if __name__=='__main__':
    ks=sorted(r['k'] for r in rows); split=ks[len(ks)//2]
    print('=== A. replicate protocol (BUY only, 30-min window) ===')
    for sig in ('S1','S2'):
        for X in (0.03,0.05,0.08):
            tr=evaluate(sig,X,lambda r,E:1800)
            summ([t for t in tr if t['k']<split],f'{sig} X={X} early'); summ([t for t in tr if t['k']>=split],f'{sig} X={X} late')
    print('=== B. include taker SELL prints as buyable complement ===')
    for sig in ('S1','S2'):
        for X in (0.03,0.05):
            tr=evaluate(sig,X,lambda r,E:1800,sell=True)
            summ(tr,f'{sig} X={X} all'); 
            summ([t for t in tr if t['k']<split],f'  early'); summ([t for t in tr if t['k']>=split],f'  late')
    print('=== C. S1 window widened: E1 .. kickoff-30min (BUY only / +SELL) ===')
    for sell in (False,True):
        for X in (0.03,0.05,0.08):
            tr=evaluate('S1',X,lambda r,E:max(0,r['k']-1800-E),sell=sell)
            summ(tr,f'S1 wide sell={sell} X={X} all')
            summ([t for t in tr if t['k']<split],f'  early'); summ([t for t in tr if t['k']>=split],f'  late')
    print('=== D. S2 (closing line) window widened: k-3h..k-30min is look-ahead; k-30min..k (in-play start excluded) ===')
    for sell in (False,True):
        for X in (0.03,0.05):
            tr=evaluate('S2',X,lambda r,E:1800,sell=sell,getE=lambda r,E:r['k']-1800)
            summ(tr,f'S2 last30 sell={sell} X={X}')
            tr=evaluate('S2',X,lambda r,E:3*3600,sell=sell,getE=lambda r,E:r['k']-3*3600)
            summ(tr,f'S2 -3h..0 sell={sell} X={X}')
