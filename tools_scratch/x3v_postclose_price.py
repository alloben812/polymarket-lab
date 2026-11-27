import json, urllib.request, urllib.parse, gzip, datetime as dt, time
def get(url):
    for i in range(4):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json","Accept-Encoding":"gzip"})
            with urllib.request.urlopen(req,timeout=60) as r:
                b=r.read()
                if r.headers.get("Content-Encoding")=="gzip": b=gzip.decompress(b)
                return json.loads(b)
        except Exception as ex:
            last=ex; time.sleep(1+i)
    raise last
G="https://gamma-api.polymarket.com"; D="https://data-api.polymarket.com/v2"
t0=int(dt.datetime(2026,11,26,12,0,tzinfo=dt.timezone.utc).timestamp())   # the half-day the researcher did NOT use
N=40; nm=0; tot_usd=0; sells=[]; buys_w=0; buys_l=0; allusd=0
for k in range(N):
    st=t0+300*k; end=st+300
    m=get(f"{G}/markets?slug=btc-updown-5m-{st}&closed=true")
    if not m: continue
    m=m[0]; outs=json.loads(m["outcomes"]); pr=json.loads(m["outcomePrices"])
    if "1" not in pr: continue
    win=outs[pr.index("1")]; cid=m["conditionId"]; nm+=1
    cur=None
    for _ in range(12):
        d=get(f"{D}/trades?condition={cid}&limit=1000"+(f"&cursor={urllib.parse.quote(cur)}" if cur else ""))
        rows=d.get("data") or []
        for r in rows:
            p=float(r["price"]); q=float(r["size"]); allusd+=p*q
            if int(r["timestamp"])>=end+3:
                if r["side"]=="SELL" and r["outcome"]==win: sells.append((p,q,int(r["timestamp"])-end))
                elif r["side"]=="BUY" and r["outcome"]==win: buys_w+=p*q
                elif r["side"]=="BUY": buys_l+=p*q
        cur=(d.get("pagination") or {}).get("next_cursor")
        if not cur or not rows: break
sh=sum(q for p,q,_ in sells); usd=sum(p*q for p,q,_ in sells)
print(f"markets {nm}, all $ {allusd:,.0f}; post-close(>=end+3s) taker SELLs of winner: {len(sells)} fills, {sh:,.0f} shares, ${usd:,.0f}, vwap {usd/sh if sh else 0:.4f}; discount to $1 total ${sh-usd:,.2f}")
bands=[(0,0.90),(0.90,0.97),(0.97,0.99),(0.99,0.995),(0.995,1.01)]
for lo,hi in bands:
    s=[(p,q) for p,q,_ in sells if lo<=p<hi]; print(f"  price [{lo},{hi}): fills {len(s)}, shares {sum(q for p,q in s):,.0f}, discount ${sum((1-p)*q for p,q in s):,.2f}")
print(f"post-close taker BUYs of winner ${buys_w:,.2f}; of loser ${buys_l:,.2f}")
