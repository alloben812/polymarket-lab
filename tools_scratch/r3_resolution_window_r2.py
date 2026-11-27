import json, subprocess, time, sys, collections, statistics as st, datetime as dt
D='/home/user/polymarket-lab/data/r3/'
def curl(u): return subprocess.run(["curl","-s","-m","40","--compressed","-H","Accept-Encoding: gzip",u],capture_output=True,text=True).stdout
mk=[]; off=0
while True:
    js=curl("https://gamma-api.polymarket.com/markets?closed=true&end_date_min=2026-11-17T00:00:00Z&volume_num_min=10000&limit=100&offset=%d&order=volumeNum&ascending=false"%off)
    try: d=json.loads(js)
    except Exception: print('gamma fail',js[:200],file=sys.stderr); break
    if not d or not isinstance(d,list): print("gamma stop at",off,str(d)[:150],file=sys.stderr); break
    for m in d:
        s=(m.get('slug') or '')
        if 'updown' in s or 'up-or-down' in s or __import__('re').search(r'-20\d\d-\d\d-\d\d(-|$)',s): continue
        mk.append(m)
    off+=100; time.sleep(0.2)
    if off>=6000: break
mk=mk[:500]
print('gamma markets',len(mk),file=sys.stderr)
res={}
cids=[m['conditionId'] for m in mk]
for i in range(0,len(cids),20):
    try:
        for r in json.loads(curl("https://data-api.polymarket.com/v2/resolutions?condition="+",".join(cids[i:i+20])))['data']:
            res[r.get('condition_id')]=r
    except Exception as e: print('res fail',i,file=sys.stderr)
    time.sleep(0.1)
def ts(s): return dt.datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()
rows=[]; fills=[]
for m in mk:
    r=res.get(m['conditionId'])
    if not r or not r.get('resolved_at'): continue
    T=ts(r['resolved_at'])
    try: op=[float(x) for x in json.loads(m['outcomePrices'])]
    except Exception: continue
    rate=float((m.get('feeSchedule') or {}).get('rate') or 0)
    tr=[]; cur=None
    for page in range(3):
        u="https://data-api.polymarket.com/v2/trades?condition=%s&limit=1000&start=%d&end=%d"%(m['conditionId'],int(T-86400),int(T)+1)
        if cur: u+="&cursor="+cur
        try: d=json.loads(curl(u))
        except Exception: break
        tr+=d.get('data',[]); cur=(d.get('pagination') or {}).get('next_cursor')
        if not cur or not d.get('data'): break
    time.sleep(0.05)
    endd=m.get('endDate'); 
    rows.append(dict(cid=m['conditionId'],slug=m.get('slug'),q=m.get('question'),vol=m.get('volumeNum'),rate=rate,reporter=r.get('reporter'),disputed=r.get('was_disputed'),resolved_at=r['resolved_at'],
                     endDate=endd,closedTime=m.get('closedTime'),payout=op,ntr=len(tr),lag_h=round((T-ts(endd))/3600,2) if endd else None))
    for x in tr:
        if x['price']<0.90 or x['timestamp']>T: continue
        pay=op[x['outcome_index']] if x['outcome_index']<len(op) else None
        if pay is None: continue
        fills.append((m['conditionId'],x['side'],x['price'],x['size'],T-x['timestamp'],pay,rate,r.get('reporter'),bool(r.get('was_disputed'))))
json.dump(rows,open(D+'resolution_markets_r2.json','w'),indent=0); json.dump(fills,open(D+'resolution_fills_r2.json','w'))
print('markets with resolution',len(rows),'fills>=0.90',len(fills))
