import json, urllib.request, gzip
G="https://gamma-api.polymarket.com"; D="https://data-api.polymarket.com/v2"
def get(u, data=None):
    h={"User-Agent":"Mozilla/5.0","Accept":"application/json","Accept-Encoding":"gzip"}
    body=None
    if data is not None: body=json.dumps(data).encode(); h["Content-Type"]="application/json"
    with urllib.request.urlopen(urllib.request.Request(u,data=body,headers=h),timeout=60) as f:
        raw=f.read()
        if f.headers.get("Content-Encoding")=="gzip": raw=gzip.decompress(raw)
        return json.loads(raw)
seen={}
for cat in ("sports","overall","esports"):
    for sb in ("PNL","VOLUME"):
        for per in ("month","week"):
            try:
                d=get(D+f"/leaderboard?category={cat}&time_period={per}&sort_by={sb}&limit=100")
            except Exception as e:
                print("ERR",cat,sb,per,e); continue
            for r in d.get("data") or []:
                seen.setdefault(r["user_id"].lower(),{})[(cat,per,sb)]=(r.get("rank"),round(r.get("pnl") or 0),round(r.get("volume") or 0),r.get("user_name"))
print("leaderboard wallets",len(seen))
S="0x204f72f35326db932158cba6adff0b9a1da95e14"
addrs=list(seen)+[S]; tt={}; mt={}
for i in range(0,len(addrs),50):
    for x in (get(G+"/tiers",{"addresses":addrs[i:i+50]}).get("tiers") or []): tt[x["address"].lower()]=x
    for x in (get(G+"/v1/maker-tier/tiers",{"addresses":addrs[i:i+50]}).get("tiers") or []): mt[x["address"].lower()]=x
s=tt[S]; sm=mt[S]
for a in addrs[:-1]:
    x=tt.get(a) or {}; y=mt.get(a) or {}
    if abs((x.get("wv_30d") or 0)-s["wv_30d"])<1 or abs((y.get("wv_30d") or 0)-sm["wv_30d"])<1:
        print("SAME GROUP:",a,x.get("tier_name"),x.get("wv_30d"),"maker",y.get("wv_30d"),"own",y.get("own_wv_30d"))
        for k,v in seen[a].items(): print("     ",k,v)
# top sports month by PNL for context
top=sorted(((v[("sports","month","PNL")],a) for a,v in seen.items() if ("sports","month","PNL") in v))[:12]
for v,a in top: print("  sports month PNL",v,a,(tt.get(a) or {}).get("tier_name"),round((mt.get(a) or {}).get("own_wv_30d") or 0))
