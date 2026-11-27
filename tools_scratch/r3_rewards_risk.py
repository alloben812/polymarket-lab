# Risk side of the liquidity-rewards estimate (see r3_structure.md section 0). Read-only.
import json, subprocess, random, statistics as st, time, sys
D='/home/user/polymarket-lab/data/r3/'
rows=json.load(open(D+'reward_yield_rows.json'))
def central(r):
    q1,q2=r['q1'],r['q2']; mn,mx=min(q1,q2),max(q1,q2)
    comp = mn+(mx-mn)/3 if 0.10<=r['mid']<=0.90 else mn
    return r['rate']*r['qus']/(r['qus']+comp) if r['qus']>0 else 0
for r in rows:
    if r.get('elig'): r['rew_c']=round(central(r),3)
random.seed(3)
sub=[]
for tier in ['top','mid','low']:
    E=[r for r in rows if r['tier']==tier and r.get('elig')]
    sub+=random.sample(E,30)
out=[]
for r in sub:
    js=subprocess.run(["curl","-s","-m","40","--compressed","https://data-api.polymarket.com/v2/prices-history?token_id=%s&interval=1w"%r['tok']],capture_output=True,text=True).stdout
    try: pts=json.loads(js)['data']
    except Exception: print('fail',r['q'][:40],js[:100],file=sys.stderr); continue
    time.sleep(0.15)
    if len(pts)<50: continue
    p=[x['price'] for x in pts]; t=[x['timestamp'] for x in pts]
    days=(t[-1]-t[0])/86400
    d5=[p[i+1]-p[i] for i in range(len(p)-1) if t[i+1]-t[i]<=600]
    h=[p[i+12]-p[i] for i in range(0,len(p)-12,12)]
    s=r['s']; N=r['N']
    loss=sum(N*(abs(x)-s) for x in d5 if abs(x)>s)
    hits=sum(1 for x in d5 if abs(x)>s)
    out.append(dict(tier=r['tier'],q=r['q'][:60],rate=r['rate'],days=round(days,2),sd5=round(100*st.pstdev(d5),3),sd1h=round(100*st.pstdev(h),3) if len(h)>2 else None,
        rng=round(100*(max(p)-min(p)),1),s_c=round(100*s,2),hits_per_day=round(hits/days,2),loss_per_day=round(loss/days,2),rew_c=r['rew_c'],rew_lo=r['rew_lo'],rew_hi=r['rew_hi'],mid=r['mid'],end=r['end'][:10]))
json.dump(out,open(D+'reward_risk_rows.json','w'),indent=0)
json.dump(rows,open(D+'reward_yield_rows.json','w'),indent=0)
for tier in ['top','mid','low']:
    O=[o for o in out if o['tier']==tier]
    if not O: continue
    md=lambda k:round(st.median([o[k] for o in O if o[k] is not None]),3)
    mn=lambda k:round(st.mean([o[k] for o in O if o[k] is not None]),3)
    print(tier,'n',len(O),'median: sd5c',md('sd5'),'sd1h c',md('sd1h'),'7d range c',md('rng'),'hits/day',md('hits_per_day'),'loss/day',md('loss_per_day'),'rew central',md('rew_c'),'rew lo',md('rew_lo'),'| mean loss',mn('loss_per_day'),'mean rew_c',mn('rew_c'),'mean rew_lo',mn('rew_lo'))
    print('   markets where central reward > crude loss:',sum(1 for o in O if o['rew_c']>o['loss_per_day']),'/',len(O),'; where pessimistic reward > loss:',sum(1 for o in O if o['rew_lo']>o['loss_per_day']))
for o in sorted(out,key=lambda o:-(o['rew_c']-o['loss_per_day']))[:15]: print(o)
print('worst')
for o in sorted(out,key=lambda o:(o['rew_c']-o['loss_per_day']))[:8]: print(o)
