# Variant 2 (added after variant 1 was seen; counted as a second variant): inventory model.
# Maker quotes N shares at mid-s / mid+s around the previous 5-min price; if the next 5-min price is <= bid he buys N
# at the bid (if inventory < +N), if >= ask he sells N at the ask (if inventory > -N). Marked at the last price.
# Optimistic: every touch fills at our price, bounces earn the spread, no queue. Read-only.
import json, subprocess, statistics as st, time, sys
D='/home/user/polymarket-lab/data/r3/'
rows={r['q'][:60]:r for r in json.load(open(D+'reward_yield_rows.json')) if r.get('elig')}
risk=json.load(open(D+'reward_risk_rows.json'))
hist={}
out=[]
for o in risk:
    r=rows[o['q']]
    js=subprocess.run(["curl","-s","-m","40","--compressed","https://data-api.polymarket.com/v2/prices-history?token_id=%s&interval=1w"%r['tok']],capture_output=True,text=True).stdout
    try: pts=json.loads(js)['data']
    except Exception: continue
    time.sleep(0.1)
    hist[r['tok']]=[(x['timestamp'],x['price']) for x in pts]
    p=[x['price'] for x in pts]; days=(pts[-1]['timestamp']-pts[0]['timestamp'])/86400
    s=r['s']; N=r['N']; inv=0; cash=0.0; fills=0
    for i in range(len(p)-1):
        bid=p[i]-s; ask=p[i]+s
        if p[i+1]<=bid and inv<N: inv+=N; cash-=N*bid; fills+=1
        elif p[i+1]>=ask and inv>-N: inv-=N; cash+=N*ask; fills+=1
    pnl=cash+inv*p[-1]
    o2=dict(o); o2.update(inv_pnl_per_day=round(pnl/days,2),fills_per_day=round(fills/days,1)); out.append(o2)
json.dump(hist,open(D+'reward_price_hist_1w.json','w'))
json.dump(out,open(D+'reward_risk_rows.json','w'),indent=0)
for tier in ['top','mid','low']:
    O=[o for o in out if o['tier']==tier]
    md=lambda k:round(st.median([o[k] for o in O]),2); mn=lambda k:round(st.mean([o[k] for o in O]),2)
    net=[o['rew_c']+o['inv_pnl_per_day'] for o in O]; netlo=[o['rew_lo']+o['inv_pnl_per_day'] for o in O]
    print(tier,'n',len(O),'inv-model trading pnl/day median',md('inv_pnl_per_day'),'mean',mn('inv_pnl_per_day'),'fills/day med',md('fills_per_day'),
      '| reward+pnl central: median',round(st.median(net),2),'mean',round(st.mean(net),2),'share>0',round(sum(1 for x in net if x>0)/len(O),2),
      '| pessimistic reward+pnl: median',round(st.median(netlo),2),'mean',round(st.mean(netlo),2))
# split: weather daily vs rest ; quiet (sd1h<0.3c) vs not
W=[o for o in out if 'temperature' in o['q']]; NW=[o for o in out if 'temperature' not in o['q']]
for nm,O in [('weather-temp',W),('other',NW),('quiet sd1h<0.3c',[o for o in out if (o['sd1h'] or 0)<0.3]),('active sd1h>=0.3c',[o for o in out if (o['sd1h'] or 0)>=0.3])]:
    if O: print(nm,'n',len(O),'median rate',st.median([o['rate'] for o in O]),'median rew_c',round(st.median([o['rew_c'] for o in O]),2),'median rew_lo',round(st.median([o['rew_lo'] for o in O]),2),'median inv pnl/day',round(st.median([o['inv_pnl_per_day'] for o in O]),2),'mean inv pnl/day',round(st.mean([o['inv_pnl_per_day'] for o in O]),2),'median crude loss',round(st.median([o['loss_per_day'] for o in O]),2), 'share rew_c>=1:',round(sum(1 for o in O if o['rew_c']>=1)/len(O),2))
