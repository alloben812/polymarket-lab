import json, gzip, re, sys, time, os, urllib.request, urllib.parse, datetime as dt, statistics as st, collections
sys.path.insert(0, "/home/user/polymarket-lab")
from pmlab import dataapi
OUT="/home/user/polymarket-lab/data/x3/wx"
UA={"User-Agent":"Mozilla/5.0","Accept-Encoding":"gzip","Accept":"application/json"}
def get(url, cache=None):
    if cache and os.path.exists(cache): return json.load(open(cache))
    for i in range(4):
        try:
            req=urllib.request.Request(url,headers=UA)
            with urllib.request.urlopen(req,timeout=40) as r:
                b=r.read()
                if r.headers.get("Content-Encoding")=="gzip": b=gzip.decompress(b)
                d=json.loads(b) if b.strip() else []
                if cache: json.dump(d,open(cache,"w"))
                return d
        except Exception as ex:
            err=ex; time.sleep(1.5*(i+1))
    print("FAIL",url,err); return None
def ts(s): return dt.datetime.fromisoformat(s.replace("Z","+00:00")).timestamp()
# 1. events
evs=[]
for off in range(0,1500,50):
    e=get(f"https://gamma-api.polymarket.com/events?closed=true&tag_slug=daily-temperature&limit=50&offset={off}&order=endDate&ascending=false", cache=f"{OUT}/ev_{off}.json")
    if not e: break
    evs+=e
    if min((x.get("endDate") or "9") for x in e) < "2026-11-20": break
print("events fetched",len(evs))
days={"november-%d-2026"%d for d in range(21,27)}
sel=[e for e in evs if e["slug"].startswith("highest-temperature-in-") and any(e["slug"].endswith(d) for d in days)]
print("selected highest events on Nov 21-26:",len(sel))
def bucket_of(title):
    m=re.match(r"\s*(-?\d+)\s*°C(?:\s+or\s+(below|higher|above))?",title or "")
    if not m: return None
    v=int(m.group(1)); k=m.group(2)
    return (-999,v) if k=="below" else (v,999) if k in("higher","above") else (v,v)
def qual(raw):
    m=re.search(r"\sT([01])(\d{3})[01]\d{3}",raw)
    if m: x=(-1 if m.group(1)=="1" else 1)*int(m.group(2))/10
    else:
        m=re.search(r"\s(M?\d{2})/(M?\d{2})?\s",raw+" ")
        if not m: return None
        x=float(m.group(1).replace("M","-"))
    import math
    return math.floor(x+0.5)
def price_at(points,t):
    p=None
    for q in points:
        if q[0]<=t: p=q[1]
        else: break
    return p
kills=[]; eod=[]; dropped=collections.Counter(); used=0
OFFS=[-300,-60,0,60,120,300,600,1800]
for e in sel[:150]:
    src=e.get("resolutionSource") or ""
    m=re.search(r"ids=(\w+).*date=([0-9T:\-]+Z).*hours=(\d+)",src)
    if not m or "aviationweather" not in src: dropped["no_avwx_source"]+=1; continue
    sid,date,hours=m.group(1),m.group(2),int(m.group(3))
    mk=[]
    for mm in e.get("markets") or []:
        b=bucket_of(mm.get("groupItemTitle"))
        if b is None: mk=None; break
        toks=json.loads(mm["clobTokenIds"]); pr=json.loads(mm.get("outcomePrices") or "[0,0]")
        mk.append(dict(b=b,tok=toks[0],cond=mm["conditionId"],won=float(pr[0])>0.5,slug=mm["slug"]))
    if not mk: dropped["not_celsius"]+=1; continue
    obs=get(src.replace("format=raw","format=json"), cache=f"{OUT}/metar_{e['slug']}.json")
    if not obs: dropped["no_metar"]+=1; continue
    end=ts(date)-3*3600; start=end-24*3600
    rows=[]
    for o in obs:
        raw=o.get("rawOb") or ""
        if raw.startswith("SPECI") or o.get("metarType")=="SPECI": continue
        t=o.get("obsTime")
        if t is None or not(start<=t<end): continue
        q=qual(raw)
        if q is None: continue
        rc=o.get("receiptTime"); rc=ts(rc.replace(" ","T")+("" if rc.endswith("Z") else "Z")) if rc else None
        rows.append((t,rc,q,raw))
    rows.sort()
    if len(rows)<12: dropped["few_obs"]+=1; continue
    mx=max(r[2] for r in rows)
    win=[x for x in mk if x["won"]]
    if len(win)!=1: dropped["no_single_winner"]+=1; continue
    if not(win[0]["b"][0]<=mx<=win[0]["b"][1]): dropped["max_mismatch"]+=1; continue
    used+=1
    def bk(v): 
        for x in mk:
            if x["b"][0]<=v<=x["b"][1]: return x
    run=None
    for (t,rc,q,raw) in rows:
        if run is not None and q>run and rc:
            dead=bk(run); new=bk(q)
            if dead and new and dead is not new:
                pts=[(p["t"] if "t" in p else p.get("timestamp"), float(p["p"] if "p" in p else p.get("price"))) for p in dataapi.prices_history(dead["tok"], int(t-1200), int(rc+2400), 60)]
                pts.sort()
                p0=price_at(pts,t-1)
                if p0 is not None and p0>=0.05:
                    kills.append(dict(ev=e["slug"],sid=sid,obs=t,rc=rc,lag=rc-t,old=run,new=q,p_pre=p0,cond=dead["cond"],
                        rc_p={o:price_at(pts,rc+o) for o in OFFS}, ob_p={o:price_at(pts,t+o) for o in OFFS}, npts=len(pts)))
        run=q if run is None else max(run,q)
    # end of day
    t,rc,q,raw=rows[-1]
    if rc:
        pts=[(p["t"] if "t" in p else p.get("timestamp"), float(p["p"] if "p" in p else p.get("price"))) for p in dataapi.prices_history(win[0]["tok"], int(rc-1800), int(rc+7200), 60)]
        pts.sort()
        eod.append(dict(ev=e["slug"],sid=sid,rc=rc,lag=rc-t,p={o:price_at(pts,rc+o) for o in (-600,0,300,900,3600)},cond=win[0]["cond"]))
json.dump(dict(kills=kills,eod=eod,dropped=dropped,used=used),open(f"{OUT}/result_w1.json","w"))
print("used events",used,"dropped",dict(dropped))
print("kill events with dead price>=0.05:",len(kills),"in",len({k['ev'] for k in kills}),"events")
if kills:
    print("receipt lag (s): median %.0f min %.0f max %.0f"%(st.median(k['lag'] for k in kills),min(k['lag'] for k in kills),max(k['lag'] for k in kills)))
    print("pre price median %.3f"%st.median(k['p_pre'] for k in kills))
    for name in ("rc_p","ob_p"):
        print("offsets relative to", "receipt" if name=="rc_p" else "obsTime")
        for o in OFFS:
            v=[k[name][o] for k in kills if k[name][o] is not None]
            if v: print("  %+5ds n=%3d median=%.3f mean=%.3f share>=0.02=%.2f share>=0.05=%.2f"%(o,len(v),st.median(v),st.mean(v),sum(x>=0.02 for x in v)/len(v),sum(x>=0.05 for x in v)/len(v)))
if eod:
    print("end-of-day winner price, n events",len(eod))
    for o in (-600,0,300,900,3600):
        v=[k['p'][o] for k in eod if k['p'][o] is not None]
        if v: print("  %+5ds n=%3d median=%.3f share<0.99=%.2f share<0.97=%.2f"%(o,len(v),st.median(v),sum(x<0.99 for x in v)/len(v),sum(x<0.97 for x in v)/len(v)))
