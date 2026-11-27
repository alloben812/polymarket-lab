import datetime as dt, collections, re, json, urllib.request
from pmlab import dataapi
def ts(s): return int(dt.datetime.strptime(s,"%Y-%m-%d").replace(tzinfo=dt.timezone.utc).timestamp())
def cat(t):
    t=t or ""
    if re.search(r"temperature|hurricane|tropical storm|rainfall|snow|hottest|°|precipitation|landfall|earthquake",t,re.I): return "weather"
    if re.search(r" vs\.? |O/U|Spread|Both Teams|win on 20|draw",t,re.I): return "sports"
    if re.search(r"tweet|posts? ",t,re.I): return "tweets"
    return "other"
W="0x594edb9112f526fa6a80b8f858a6379c8a2c1c11"
by=collections.defaultdict(collections.Counter); oth=collections.Counter(); n=0
for r in dataapi.iter_trades(user=W,start=ts("2026-08-25"),end=ts("2026-11-28"),taker_only=False):
    m=dt.datetime.fromtimestamp(int(r["timestamp"]),dt.timezone.utc).strftime("%Y-%m"); c=cat(r.get("title")); v=float(r["size"])*float(r["price"])
    by[m][c]+=v; n+=1
    if c=="other": oth[re.sub(r"\d+","#",r.get("title") or "?")[:50]]+=v
print("ColdMath fills",n)
for m in sorted(by): print("  ",m,{k:round(v) for k,v in by[m].most_common()})
print("   other top:",[(k,round(v)) for k,v in oth.most_common(5)])
# implied weather taker rate for BeefSlayer
Bf="0x331bf91c132af9d921e1908ca0979363fc47193f"
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"}),timeout=60) as f: return json.loads(f.read())
pts=sorted(get(f"https://data-api.polymarket.com/v2/user-pnl?user={Bf}&interval=all&fidelity=1d")["data"]["points"],key=lambda x:x["timestamp"])
def fees_at(t):  # cumulative fees at last point <= t
    v=0
    for q in pts:
        if q["timestamp"]<=t: v=q.get("fees") or 0
    return v
for a,b in (("2026-09-01","2026-10-01"),("2026-10-01","2026-10-19"),("2026-11-01","2026-11-20"),("2026-11-22","2026-11-27")):
    tak=list(dataapi.iter_trades(user=Bf,start=ts(a),end=ts(b)-1,taker_only=True))
    w=sum(float(r["size"])*float(r["price"])*(1-float(r["price"])) for r in tak if cat(r.get("title"))=="weather")
    wall=sum(float(r["size"])*float(r["price"])*(1-float(r["price"])) for r in tak)
    f=-(fees_at(ts(b))-fees_at(ts(a)))
    print(f"BeefSlayer {a}..{b}: taker fills {len(tak)} sum shares*p*(1-p) all {wall:,.0f} (weather {wall and w/wall*100:.0f}%) fees charged {f:,.1f} -> implied rate {f/max(wall,1e-9):.4f}")
