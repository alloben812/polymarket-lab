import json, urllib.request, gzip, collections, re
G="https://gamma-api.polymarket.com"; D="https://data-api.polymarket.com/v2"
def get(u, data=None):
    h={"User-Agent":"Mozilla/5.0","Accept":"application/json","Accept-Encoding":"gzip"}
    body=None
    if data is not None: body=json.dumps(data).encode(); h["Content-Type"]="application/json"
    with urllib.request.urlopen(urllib.request.Request(u,data=body,headers=h),timeout=60) as f:
        raw=f.read()
        if f.headers.get("Content-Encoding")=="gzip": raw=gzip.decompress(raw)
        return json.loads(raw)
ms=[]
for off in range(0,1000,100):
    ms+=get(G+f"/markets?closed=false&active=true&order=volume24hr&ascending=false&limit=100&offset={off}")
sp=[m for m in ms if m.get("feeType")=="sports_fees_v3"]
def league(m): return re.split(r"-",m.get("slug") or "")[0]
c=collections.defaultdict(collections.Counter)
for m in sp: c[league(m) if m.get("gameStartTime") else "(no game time)"][m.get("secondsDelay")]+=1
print("sports secondsDelay by slug prefix:")
for k,v in sorted(c.items(),key=lambda x:-sum(x[1].values()))[:30]: print("  ",k,dict(v))
w=[m for m in ms if m.get("feeType")=="weather_fees"]
for m in w:
    r=sum(float(x.get("rewardsDailyRate") or 0) for x in (m.get("clobRewards") or []))
    if r>0: print("  weather pool",m["slug"][:70],r,"minSize",m.get("rewardsMinSize"),"maxSpread",m.get("rewardsMaxSpread"),"vol24",round(m.get("volume24hr") or 0))
print("weather no-pool sample",[m["slug"][:45] for m in w if not m.get("clobRewards")][:6])
d=get(D+"/leaderboard?category=sports&time_period=month&sort_by=PNL&limit=5")
print("LB shape:",json.dumps(d)[:600])
