import json, urllib.request, urllib.parse, gzip, datetime as dt, collections
def get(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json","Accept-Encoding":"gzip"})
    with urllib.request.urlopen(req,timeout=60) as r:
        b=r.read()
        if r.headers.get("Content-Encoding")=="gzip": b=gzip.decompress(b)
        return json.loads(b)
G="https://gamma-api.polymarket.com"; D="https://data-api.polymarket.com/v2"
w="0xc227bdcfa753509ba71a271121cab504a029d0c5"
t0=int(dt.datetime(2026,5,3,11,0,tzinfo=dt.timezone.utc).timestamp())
d=get(f"{D}/trades?user={w}&start={t0-600}&end={t0+900}&taker_only=false&limit=1000"); rows=d.get("data") or []
for r in rows: print("Mep72",dt.datetime.fromtimestamp(int(r["timestamp"]),dt.timezone.utc).strftime("%H:%M:%S"),r["side"],r["outcome"],r["price"],r["size"],r["slug"])
cands=[]
for a in ("sol","btc"):
    for st in (t0,t0-300):
        for q in (f"markets?slug={a}-updown-5m-{st}", f"markets?slug={a}-updown-5m-{st}&closed=true", f"events?slug={a}-updown-5m-{st}"):
            try:
                m=get(f"{G}/{q}"); print(q,"->",len(m))
                if m and a=="sol":
                    x=m[0]; x=(x.get("markets") or [x])[0]; cands.append((st,x))
            except Exception as ex: print(q,"ERR",ex)
seen=set()
for st,m in cands:
    cid=m["conditionId"]
    if cid in seen: continue
    seen.add(cid); end=st+300
    print("MARKET",m.get("slug"),"|",m.get("question"),"| volumeNum",m.get("volumeNum"),m.get("outcomes"),m.get("outcomePrices"))
    rows=[]; cur=None
    for _ in range(80):
        d=get(f"{D}/trades?condition={cid}&limit=1000"+(f"&cursor={urllib.parse.quote(cur)}" if cur else ""))
        r=d.get("data") or []; rows+=r; cur=(d.get("pagination") or {}).get("next_cursor")
        if not cur or not r: break
    pre=[r for r in rows if int(r["timestamp"])<end]; post=[r for r in rows if int(r["timestamp"])>=end]
    f=lambda rs:(len(rs),round(sum(float(r["price"])*float(r["size"]) for r in rs),2),round(sum(float(r["size"]) for r in rs)),len({r["proxy_wallet"] for r in rs}))
    print("   rows",len(rows),"| before end (n,$,shares,wallets)",f(pre),"| at/after end",f(post))
    if post:
        ts=[int(r["timestamp"])-end for r in post]; print("   post offsets s min/max",min(ts),max(ts))
        by=collections.Counter(); usd=collections.Counter()
        for r in post:
            k=(r["side"],r["outcome"], "<=3c" if float(r["price"])<=0.03 else (">=97c" if float(r["price"])>=0.97 else "mid")); by[k]+=float(r["size"]); usd[k]+=float(r["size"])*float(r["price"])
        for k in by: print("   post",k,"shares",round(by[k]),"usd",round(usd[k],2))
        print("   Mep72:",[(int(r["timestamp"])-end,r["side"],r["outcome"],r["price"],r["size"]) for r in rows if r["proxy_wallet"].lower()==w][:10])
