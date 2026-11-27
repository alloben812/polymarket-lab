# Who holds inventory in the quiet rewarded markets, and how much reward income do those wallets show? Read-only.
import json, subprocess, time, collections
D='/home/user/polymarket-lab/data/r3/'
def curl(u): return subprocess.run(["curl","-s","-m","40","--compressed",u],capture_output=True,text=True).stdout
res=json.load(open(D+'reward_quiet_pool.json'))
cids=[x['cid'] for x in res][:40]
W=collections.Counter(); names={}; nm=collections.Counter()
for i in range(0,len(cids),20):
    d=json.loads(curl("https://data-api.polymarket.com/v2/holders?condition=%s&limit=15"%",".join(cids[i:i+20])))
    for tok in d.get('data',[]):
        for h in tok['holders']:
            W[h['proxy_wallet']]+=h['amount']; names[h['proxy_wallet']]=h.get('name') or h.get('pseudonym'); nm[h['proxy_wallet']]+=1
    time.sleep(0.2)
top=[w for w,_ in sorted(nm.items(),key=lambda kv:(-kv[1],-W[kv[0]]))[:45]]
out=[]
for w in top:
    try: s=json.loads(curl("https://data-api.polymarket.com/v2/user-stats?user="+w))['data']
    except Exception: continue
    p=s.get('all_time_pnl') or {}
    out.append(dict(w=w,name=names[w],n_mkts=nm[w],shares=round(W[w]),join=str(s.get('join_date'))[:10],trade_pnl=p.get('trade_pnl'),fees=p.get('fees'),maker_rebate=p.get('maker_rebate'),taker_rebate=p.get('taker_rebate'),reward=p.get('reward_income'),econ=p.get('economic_pnl'),keys=sorted(p.keys())))
    time.sleep(0.1)
json.dump(out,open(D+'reward_wallets.json','w'),indent=0)
print(out[0]['keys'] if out else None)
f=lambda x: 'None' if x is None else format(float(x),',.0f')
for o in sorted(out,key=lambda o:-(float(o['reward'] or 0))):
    print(o['w'],(o['name'] or '')[:22].ljust(22),'mkts',o['n_mkts'],'shares',o['shares'],'join',o['join'],'trade',f(o['trade_pnl']),'fees',f(o['fees']),'mkr_reb',f(o['maker_rebate']),'reward',f(o['reward']),'econ',f(o['econ']))
