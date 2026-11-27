import json,sys,time,urllib.request,calendar,statistics as st
def get(url):
    for i in range(4):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
            with urllib.request.urlopen(req,timeout=30) as r: return json.loads(r.read())
        except Exception as e: time.sleep(1+i)
    return None
base=calendar.timegm((2026,11,25,0,0,0))
print(f"{'series':18s} {'n':>3s} {'median vol$':>11s} {'mean vol$':>10s} {'mkts/day':>8s} {'est daily $':>12s}  fee / tick")
for pref,dur in (("btc-updown-5m",300),("eth-updown-5m",300),("sol-updown-5m",300),("xrp-updown-5m",300),("doge-updown-5m",300),("hype-updown-5m",300),("btc-updown-15m",900),("eth-updown-15m",900),("sol-updown-15m",900),("xrp-updown-15m",900),("btc-updown-4h",14400)):
    vols=[];meta=None
    for h in range(0,24,2):
        t0=base+h*3600; t0-=t0%dur
        r=get(f"https://gamma-api.polymarket.com/markets?slug={pref}-{t0}&closed=true")
        if r:
            m=r[0]; vols.append(float(m.get('volumeNum') or 0)); meta=((m.get('feeSchedule') or {}).get('rate'),m.get('orderPriceMinTickSize'),m.get('feeType'))
        time.sleep(0.03)
    if vols: print(f"{pref:18s} {len(vols):3d} {st.median(vols):11.0f} {st.mean(vols):10.0f} {86400//dur:8d} {st.mean(vols)*(86400//dur):12.0f}  {meta}")
    else: print(f"{pref:18s} no markets found")
