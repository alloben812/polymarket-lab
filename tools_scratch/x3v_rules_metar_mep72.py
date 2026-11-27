import json, urllib.request, urllib.parse, gzip, time, datetime as dt
def get(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json","Accept-Encoding":"gzip"})
    with urllib.request.urlopen(req,timeout=60) as r:
        b=r.read()
        if r.headers.get("Content-Encoding")=="gzip": b=gzip.decompress(b)
        return json.loads(b)
G="https://gamma-api.polymarket.com"
for slug,keys in [("highest-temperature-in-seoul-on-november-28-2026",["routine","SPECI","tenths"]),
                  ("elon-musk-of-tweets-november-20-november-27-2026",["xtracker","5 minutes","secondary"]),
                  ("what-will-jensen-huang-say-during-his-gtc-washington-dc-keynote",["audio/video","video"])]:
    try:
        ev=get(f"{G}/events?slug={slug}")
        if not ev: print(slug,"NOT FOUND"); continue
        e=ev[0]; ms=e.get("markets") or []; m=ms[0] if ms else {}
        desc=(e.get("description") or m.get("description") or "")
        print("EVENT",slug,"| markets",len(ms),"| vol24h",e.get("volume24hr"),"| resSrc",(e.get("resolutionSource") or m.get("resolutionSource")))
        print("   fee",m.get("feeSchedule"),"secondsDelay",m.get("secondsDelay","ABSENT"),"liveness",m.get("customLiveness"),"bond",m.get("umaBond"))
        for k in keys:
            i=desc.find(k); print("   ",k,"->",("..."+desc[max(0,i-80):i+160].replace("\n"," ")+"...") if i>=0 else "NOT IN TEXT")
    except Exception as ex: print(slug,"ERR",ex)
# aviationweather receipt lag
try:
    rows=get("https://aviationweather.gov/api/data/metar?ids=RKSI,EGLC,KLGA&format=json&hours=4")
    for r in rows[:14]:
        ob=r.get("obsTime"); rc=r.get("receiptTime")
        rct=dt.datetime.fromisoformat(rc.replace("Z","+00:00").replace(" ","T")) if rc else None
        if rct and rct.tzinfo is None: rct=rct.replace(tzinfo=dt.timezone.utc)
        print("METAR",r.get("icaoId"),r.get("metarType"),dt.datetime.fromtimestamp(ob,dt.timezone.utc).strftime("%H:%M:%S"),"receipt",rc,"lag_s",int(rct.timestamp()-ob) if rct else None)
except Exception as ex: print("AWC ERR",ex)
# Mep72 around the article's example market: SOL 5m ending 2026-05-03 07:00 ET = 11:00 UTC
D="https://data-api.polymarket.com/v2"
w="0xc227bdcfa753509ba71a271121cab504a029d0c5"
s=int(dt.datetime(2026,5,3,10,50,tzinfo=dt.timezone.utc).timestamp()); e=s+1500
try:
    d=get(f"{D}/trades?user={w}&start={s}&end={e}&taker_only=false&limit=1000")
    rows=d.get("data") or d
    print("Mep72 fills in window:",len(rows))
    tot=0; sh=0
    for r in rows[:400]:
        t=r.get("timestamp"); 
        if "sol" in (r.get("slug") or r.get("market_slug") or r.get("title") or "").lower():
            print("  ",dt.datetime.fromtimestamp(int(t),dt.timezone.utc).strftime("%H:%M:%S"),r.get("side"),r.get("outcome"),r.get("price"),r.get("size"),(r.get("slug") or r.get("market_slug") or r.get("title"))[:50])
        tot+=float(r.get("price",0))*float(r.get("size",0)); sh+=float(r.get("size",0))
    print("  window total $",round(tot,2),"shares",round(sh),"keys",list(rows[0].keys())[:14] if rows else None)
except Exception as ex: print("DATA ERR",ex)
# whole Apr 26 - May 10 for Mep72: shares bought by price band
try:
    s=int(dt.datetime(2026,4,19,tzinfo=dt.timezone.utc).timestamp()); e=int(dt.datetime(2026,5,10,tzinfo=dt.timezone.utc).timestamp())
    cur=None; n=0; buy_sh=0; buy_usd=0; cheap_sh=0; cheap_usd=0; sell_usd=0
    for _ in range(40):
        u=f"{D}/trades?user={w}&start={s}&end={e}&taker_only=false&limit=1000"+(f"&cursor={urllib.parse.quote(cur)}" if cur else "")
        d=get(u); rows=d.get("data") or []
        for r in rows:
            n+=1; p=float(r["price"]); q=float(r["size"])
            if (r.get("side") or "").upper()=="BUY":
                buy_sh+=q; buy_usd+=p*q
                if p<=0.03: cheap_sh+=q; cheap_usd+=p*q
            else: sell_usd+=p*q
        cur=(d.get("pagination") or {}).get("next_cursor")
        if not cur or not rows: break
    print(f"Mep72 Apr19-May10: fills {n}, buys ${buy_usd:,.0f} for {buy_sh:,.0f} shares; of which <=3c: ${cheap_usd:,.0f} for {cheap_sh:,.0f} shares (max payout ${cheap_sh:,.0f}); sells ${sell_usd:,.0f}")
except Exception as ex: print("DATA2 ERR",ex)
