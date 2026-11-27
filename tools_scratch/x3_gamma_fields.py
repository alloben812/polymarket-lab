import json, sys, urllib.request, gzip, collections
UA={"User-Agent":"Mozilla/5.0","Accept-Encoding":"gzip","Accept":"application/json"}
def get(url):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=40) as r:
        b=r.read()
        if r.headers.get("Content-Encoding")=="gzip": b=gzip.decompress(b)
        return json.loads(b)
# top open events by 24h volume, several pages
evs=[]
for off in range(0,1000,100):
    try:
        e=get(f"https://gamma-api.polymarket.com/events?closed=false&active=true&limit=100&offset={off}&order=volume24hr&ascending=false")
    except Exception as ex:
        print("ERR",off,ex); break
    if not e: break
    evs+=e
json.dump(evs,open("data/x3/open_events_top1000.json","w"))
print("events",len(evs))
keys=collections.Counter()
rows=[]
for e in evs:
    tags=[t.get("slug") for t in (e.get("tags") or [])]
    for m in e.get("markets") or []:
        for k in m: 
            if "elay" in k or "ports" in k or "ame" in k.lower() and "start" in k.lower(): keys[k]+=1
        rows.append((e.get("slug"),tags,m.get("secondsDelay"),m.get("feeSchedule"),m.get("feeType"),m.get("gameStartTime"),m.get("sportsMarketType"),e.get("seriesSlug")))
print(keys.most_common(30))
# delay by tag
by=collections.defaultdict(collections.Counter)
for slug,tags,sd,fs,ft,gst,smt,ser in rows:
    cat = ser or (tags[0] if tags else None)
    by[cat][sd]+=1
for cat,c in sorted(by.items(), key=lambda kv:-sum(kv[1].values()))[:70]:
    print(f"{str(cat)[:40]:40s} n={sum(c.values()):5d} secondsDelay={dict(c)}")
