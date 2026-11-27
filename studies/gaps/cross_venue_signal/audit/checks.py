import sys; sys.path.insert(0,'.')
from recompute import *
import collections
ln=[]
for r in rows:
    for x in 'HDA': ln.append((len(r['tp'][x]),r['ev'],x))
ln.sort(reverse=True); print('largest tapes',ln[:6], 'zero-len', sum(1 for l in ln if l[0]==0))
# coverage: first print relative to kickoff, last print relative to kickoff
import statistics as st
fp=[];lp=[];dup=0
for r in rows:
    allp=[z for x in 'HDA' for z in r['tp'][x]]
    fp.append((min(z['t'] for z in allp)-r['k'])/3600); lp.append((max(z['t'] for z in allp)-r['k'])/3600)
print('first print h rel kickoff median',st.median(fp),'last',st.median(lp))
# weekday
c=collections.Counter(datetime.fromtimestamp(r['k'],timezone.utc).strftime('%a') for r in rows); print(c)
# how many prints are in-play (after kick-off)? S2 window ends at k-30m+30m = k so none
# gap distribution of ALL buy prints in the 30 min after E1, count matches with a print >=3pt gap in either direction (abs) to see symmetric noise
n=0;pos=0;neg=0
for r in rows:
    if r['e1'] is None or r['k']-r['e1']>96*3600: continue
    for (t,x,tok,p,z,i) in prints(r,r['e1'],1800):
        f=r['s1'][i] if tok=='Yes' else 1-r['s1'][i]
        if f-p>=0.03: pos+=1
        if p-f>=0.03: neg+=1
print('S1 prints cheap>=3',pos,'rich>=3',neg)
# S1 wide: fraction of matches with any BUY print in E1..k-30
cnt=0
for r in rows:
    if r['e1'] is None or r['k']-r['e1']>96*3600: continue
    if prints(r,r['e1'],r['k']-1800-r['e1']): cnt+=1
print('matches with any print E1..k-30m',cnt)
# E1 hours before kickoff distribution
h=[(r['k']-r['e1'])/3600 for r in rows if r['e1']]; print('E1 hours median',st.median(h),'max',max(h))
# Wide S1 variant restricted to the 'live-feed' idea is not testable. Day-cluster on wide S1 X=3
tr=evaluate('S1',0.03,lambda r,E:max(0,r['k']-1800-E))
import collections
by=collections.defaultdict(list)
for t in tr: by[datetime.fromtimestamp(t['k'],timezone.utc).date()].append(t['ret'])
n=len(tr); mu=st.mean(t['ret'] for t in tr)
res=[sum(x-mu for x in v) for v in by.values()]; g=len(by)
print('wide S1 X3 day-cluster se',math.sqrt(g/(g-1)*sum(e*e for e in res))/n*100,'mean',mu*100,'days',g)
# time from E1 to trade for wide S1
print('median hours before kickoff at trade',st.median((t['k']-t['t'])/3600 for t in tr))
