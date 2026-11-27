import json, subprocess, statistics as st, time, sys, bisect
D='/home/user/polymarket-lab/data/r3/'
rows={r['q'][:60]:r for r in json.load(open(D+'reward_yield_rows.json')) if r.get('elig')}
risk=json.load(open(D+'reward_risk_rows.json'))
hist=json.load(open(D+'reward_price_hist_1w.json'))
NOW=1795794000; START=NOW-7*86400
sel=[]
for tier in ['top','mid','low']: sel+=[o for o in risk if o['tier']==tier][:15]
out=[]
for o in sel:
    r=rows[o['q']]; h=hist.get(r['tok'])
    if not h: continue
    ts=[x[0] for x in h]; ps=[x[1] for x in h]
    tr=[]; cur=None
    for page in range(5):
        url="https://data-api.polymarket.com/v2/trades?condition=%s&limit=1000&start=%d"%(r['cid'],START)
        if cur: url+="&cursor="+cur
        js=subprocess.run(["curl","-s","-m","40","--compressed",url],capture_output=True,text=True).stdout
        try: d=json.loads(js)
        except Exception: break
        tr+=d.get('data',[]); cur=(d.get('pagination') or {}).get('next_cursor')
        time.sleep(0.1)
        if not cur or not d.get('data'): break
    if not tr: 
        out.append(dict(tier=o['tier'],q=o['q'],rate=o['rate'],n=0)); continue
    span=max(1.0,(max(x['timestamp'] for x in tr)-min(x['timestamp'] for x in tr))/86400) if len(tr)>=1000*5 else min(7.0,max(o['days'],1.0))
    pnl=0.0; sh=0.0; usd=0.0
    for x in tr:
        yes = x['outcome_index']==0
        p = x['price'] if yes else 1-x['price']
        buy_yes = (x['side']=='BUY')==yes
        i=bisect.bisect_left(ts,x['timestamp']+3600)
        f=ps[i] if i<len(ps) else ps[-1]
        pnl += x['size']*((p-f) if buy_yes else (f-p)); sh+=x['size']; usd+=x['size']*x['price']
    out.append(dict(tier=o['tier'],q=o['q'],rate=o['rate'],n=len(tr),capped=len(tr)>=5000,span_days=round(span,2),shares=round(sh),usd_per_day=round(usd/span),
        maker_markout_c_per_share=round(100*pnl/sh,3),maker_markout_usd_per_day=round(pnl/span,2),pool_plus_markout=round(o['rate']+pnl/span,2),depth_usd=r['depth_usd']))
json.dump(out,open(D+'reward_markout_rows.json','w'),indent=0)
for o in out: print(o)
for tier in ['top','mid','low','all']:
    O=[o for o in out if (o['tier']==tier or tier=='all') and o['n']>0]
    if not O: continue
    print(tier,'n',len(O),'median markout c/share',st.median([o['maker_markout_c_per_share'] for o in O]),'sum pool/day',round(sum(o['rate'] for o in O)),'sum markout/day',round(sum(o['maker_markout_usd_per_day'] for o in O)),
      'markets pool+markout>0:',sum(1 for o in O if o['pool_plus_markout']>0),'sum depth',sum(o['depth_usd'] for o in O),
      'net per $ depth per day %',round(100*sum(o['pool_plus_markout'] for o in O)/sum(o['depth_usd'] for o in O),3))
