import sys; sys.argv=['x','3']
LAG=3
src=open('recompute.py').read()
exec(src.split("for lo_name")[0])
# coverage of receipt data and tape duplicates
lo=int(dt.datetime(2026,11,12,tzinfo=dt.timezone.utc).timestamp()); hi=int(dt.datetime(2026,11,25,tzinfo=dt.timezone.utc).timestamp())
inw=[k for k in kills if lo<=k[2]<hi]; withrec=[k for k in inw if REC.get((k[0]["icao"],k[2])) is not None]
print("kills with obs in 12-24 Nov:",len(inw),"with AWC receipt:",len(withrec))
miss=collections.Counter(k[0]["icao"] for k in inw if REC.get((k[0]["icao"],k[2])) is None); print("missing receipt by station:",dict(miss))
dup=tot=0; seen_cond=set()
for e,i,t,f in kills:
    c=e["buckets"][i]["cond"]
    if c in seen_cond: continue
    seen_cond.add(c); s=set()
    for tr in tape(c):
        k=(tr["h"],tr["w"],tr["s"],tr["o"],tr["p"],tr["z"]); tot+=1
        if k in s: dup+=1
        s.add(k)
print("tape rows on dead-bucket markets:",tot,"exact duplicate rows:",dup)
tot=0; pre=0
for e,i,t,f in inw:
    if REC.get((e["icao"],t)) is not None: continue
    for mt,py,z,tr in stale_rows(e,i,t):
        if py<0.02: continue
        if mt>=t+300: tot+=z*py
        else: pre+=z*py
print("62 kills without receipt: stale profit before obs+300 $%.0f, after obs+300 $%.1f"%(pre,tot))
