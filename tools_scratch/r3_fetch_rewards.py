import json, subprocess, sys, base64
out=[]; cur=None; n=0
while True:
    args=["curl","-s","-m","40","-G","https://clob.polymarket.com/rewards/markets/multi","--data-urlencode","order_by=rate_per_day","--data-urlencode","position=DESC","--data-urlencode","page_size=500"]
    if cur: args+=["--data-urlencode","next_cursor="+cur]
    r=subprocess.run(args,capture_output=True,text=True).stdout
    d=json.loads(r)
    out+=d["data"]; n+=1
    cur=d.get("next_cursor")
    print(n,len(d["data"]),cur,file=sys.stderr)
    if not d["data"] or cur in (None,"LTE=") or n>40: break
json.dump(out,open("/home/user/polymarket-lab/data/r3/reward_markets_all.json","w"))
print(len(out))
