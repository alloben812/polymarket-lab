import sys; sys.path.insert(0,'.')
from recompute import *
def last_yes(r,x,E):
    v=None
    for z in r['tp'][x]:
        if z['t']>=E: break
        v=z['p'] if z['o']=='Yes' else 1-z['p']
    return v
nb=0;nbk=0;npm=0;N=0
sl=[]
for r in rows:
    if r['e1'] is None or r['k']-r['e1']>96*3600: continue
    a=[last_yes(r,x,r['e1']) for x in 'HDA']
    b=[last_yes(r,x,r['k']-1800) for x in 'HDA']
    if any(v is None or v<=0 for v in a+b): continue
    sa=sum(a); sb=sum(b); a=[v/sa for v in a]; b=[v/sb for v in b]
    for i in range(3):
        g=a[i]-r['s1'][i]
        if abs(g)>=0.02:
            N+=1
            if (r['s2'][i]-r['s1'][i])*g>0: nbk+=1
            if (b[i]-a[i])*g<0: npm+=1
print('outcomes |g|>=2',N,'bookmaker moved toward PM',nbk,'PM moved toward bookmaker',npm)
