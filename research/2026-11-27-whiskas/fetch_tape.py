#!/usr/bin/env python3
"""Download the full public trade tape (taker side, one row per fill) for a list of markets."""
import json, sys, time, urllib.request, urllib.parse, os, re
from concurrent.futures import ThreadPoolExecutor
B="https://data-api.polymarket.com/v2"
def get(url,tries=7):
    for i in range(tries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
            with urllib.request.urlopen(req,timeout=60) as r: return json.loads(r.read())
        except Exception as e:
            time.sleep(1.5*(i+1))
    return None
def fetch(item):
    cond,slug,outdir=item
    out=os.path.join(outdir,slug+".jsonl")
    if os.path.exists(out): return slug,-1
    url=B+"/trades?"+urllib.parse.urlencode({"condition":cond,"limit":1000})
    rows=[]
    while True:
        d=get(url)
        if d is None: return slug,None
        rs=d.get("data") or []
        rows+= [{"s":r["side"],"o":r["outcome"],"z":r["size"],"p":r["price"],"t":r["timestamp"],"w":r["proxy_wallet"][-6:],"h":r["transaction_hash"][-8:]} for r in rs]
        nc=(d.get("pagination") or {}).get("next_cursor")
        if not nc or not rs: break
        url=B+"/trades?"+urllib.parse.urlencode({"condition":cond,"cursor":nc})
    with open(out+".tmp","w") as f:
        for r in rows: f.write(json.dumps(r)+"\n")
    os.rename(out+".tmp",out)
    return slug,len(rows)
labeled,outdir,start,end,step=sys.argv[1],sys.argv[2],int(sys.argv[3]),int(sys.argv[4]),int(sys.argv[5])
seen={}
for l in open(labeled):
    r=json.loads(l); m=re.match(r'btc-updown-5m-(\d+)$',r['slug'] or '')
    if m: seen[int(m.group(1))]=(r['condition_id'],r['slug'])
t0s=sorted(t for t in seen if start<=t<end)[::step]
items=[(seen[t][0],seen[t][1],outdir) for t in t0s]
print("markets to fetch",len(items)); tot=0
with ThreadPoolExecutor(4) as ex:
    for i,(slug,n) in enumerate(ex.map(fetch,items)):
        if n and n>0: tot+=n
        if i%40==0: sys.stderr.write(f"  {i}/{len(items)} last {slug} rows {n} total {tot}\n")
print("total rows",tot)
