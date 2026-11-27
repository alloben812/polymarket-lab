import json,sys,time,urllib.request,datetime as dt,statistics as st,calendar
def get(url):
    for i in range(5):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
            with urllib.request.urlopen(req,timeout=40) as r: return json.loads(r.read())
        except Exception as e: time.sleep(1+i)
    return None
days=sys.argv[1:]
print(f"{'day':10s} {'n':>3s} {'median vol$':>11s} {'mean vol$':>10s} {'est. daily BTC-5m vol$':>22s}  feeSchedule / tick / twap")
for day in days:
    y,m,d=map(int,day.split('-')); base=calendar.timegm((y,m,d,0,0,0))
    vols=[];meta=None
    for h in range(0,24,1):
        t0=base+h*3600+ (h%12)*300   # spread across the hour
        r=get(f"https://gamma-api.polymarket.com/markets?slug=btc-updown-5m-{t0}&closed=true")
        if not r:
            r=get(f"https://gamma-api.polymarket.com/markets?slug=btc-updown-5m-{t0}")
        if r:
            mkt=r[0]; v=float(mkt.get('volumeNum') or mkt.get('volume') or 0); vols.append(v)
            meta=(mkt.get('feeSchedule'),mkt.get('orderPriceMinTickSize'),(mkt.get('cryptoMarketConfig') or {}).get('id'),mkt.get('feeType'))
        time.sleep(0.05)
    if vols: print(f"{day:10s} {len(vols):3d} {st.median(vols):11.0f} {st.mean(vols):10.0f} {st.mean(vols)*288:22.0f}  {meta}")
    else: print(day,"no data")
