import json, urllib.request, urllib.parse, gzip, collections, statistics as st
G="https://gamma-api.polymarket.com"; C="https://clob.polymarket.com"; D="https://data-api.polymarket.com/v2"
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
    try:
        page=get(G+f"/markets?closed=false&active=true&order=volume24hr&ascending=false&limit=100&offset={off}")
    except Exception as e:
        print("ERR page",off,e); break
    if not page: break
    ms+=page
print("markets scanned",len(ms))
hold=[m for m in ms if m.get("holdingRewardsEnabled")]
print("holdingRewardsEnabled True:",len(hold))
for m in hold[:15]: print("   ",m.get("slug")[:70],"|",m.get("feeType"),"| vol24",round(m.get("volume24hr") or 0),"| end",m.get("endDate"),"| last",m.get("lastTradePrice"))
print("  by feeType:",collections.Counter(m.get("feeType") for m in hold).most_common())
delay_keys=set(k for m in ms for k in m if "delay" in k.lower())
print("delay keys:",delay_keys)
for k in delay_keys:
    c=collections.Counter((m.get("feeType"),m.get(k)) for m in ms)
    print("  ",k,sorted(c.items(),key=lambda x:-x[1])[:25])
# reward pools
by=collections.defaultdict(list); nopool=collections.Counter()
for m in ms:
    r=sum(float(x.get("rewardsDailyRate") or 0) for x in (m.get("clobRewards") or []))
    if r>0: by[m.get("feeType")].append(r)
    else: nopool[m.get("feeType")]+=1
for k,v in sorted(by.items(),key=lambda x:-sum(x[1])):
    v=sorted(v); print(f"  pool {k}: n={len(v)} sum/day=${sum(v):,.0f} median=${st.median(v):.2f} p90=${v[int(.9*(len(v)-1))]:.2f} max=${v[-1]:.0f} | no pool: {nopool[k]}")
print("  no pool only:",{k:v for k,v in nopool.items() if k not in by})
# delayed sports sample
smp=[m for m in ms if any((m.get(k) or 0) for k in delay_keys)]
for m in smp[:12]: print("   delayed:",m.get("slug")[:60],{k:m.get(k) for k in delay_keys},m.get("gameStartTime"))
# book ordering
for m in ms[:1]:
    t=json.loads(m["clobTokenIds"])[0]; b=get(C+"/book?token_id="+t)
    print("BOOK",m.get("slug")[:50],"asks first3",[a["price"] for a in b["asks"][:3]],"last3",[a["price"] for a in b["asks"][-3:]],"bids first3",[a["price"] for a in b["bids"][:3]],"last3",[a["price"] for a in b["bids"][-3:]])
# swisstony group
try:
    seen={}
    for sb in ("PNL","VOLUME"):
        for per in ("month","week"):
            d=get(D+f"/leaderboard?category=sports&time_period={per}&sort_by={sb}&limit=50")
            rows=d.get("data") or d
            for r in rows:
                w=r.get("proxy_wallet") or r.get("user") or r.get("wallet") or r.get("address")
                if w: seen[w.lower()]=(r.get("name") or r.get("user_name") or r.get("pseudonym"), r.get("pnl"), r.get("volume"))
    print("leaderboard wallets",len(seen))
    addrs=list(seen)+["0x204f72f35326db932158cba6adff0b9a1da95e14"]
    tt={}; mt={}
    for i in range(0,len(addrs),50):
        for x in (get(G+"/tiers",{"addresses":addrs[i:i+50]}).get("tiers") or []): tt[x["address"].lower()]=x
        for x in (get(G+"/v1/maker-tier/tiers",{"addresses":addrs[i:i+50]}).get("tiers") or []): mt[x["address"].lower()]=x
    s=tt.get("0x204f72f35326db932158cba6adff0b9a1da95e14"); sm=mt.get("0x204f72f35326db932158cba6adff0b9a1da95e14")
    print("swisstony tiers",s,sm)
    for a in addrs[:-1]:
        x=tt.get(a) or {}; y=mt.get(a) or {}
        if (s and abs((x.get("wv_30d") or 0)-s["wv_30d"])<1) or (sm and abs((y.get("wv_30d") or 0)-sm["wv_30d"])<1):
            print("   SAME GROUP:",a,seen[a],x.get("tier_name"),x.get("wv_30d"),y.get("wv_30d"),y.get("own_wv_30d"))
except Exception as e:
    import traceback; traceback.print_exc()
