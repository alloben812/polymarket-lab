# NBA: final buzzer (ESPN play-by-play wallclock) -> Polymarket moneyline price, proposal and settlement times
import json, gzip, sys, urllib.request, datetime as dt, statistics as st
sys.path.insert(0,"/home/user/polymarket-lab")
from pmlab import dataapi
UA={"User-Agent":"Mozilla/5.0","Accept-Encoding":"gzip","Accept":"application/json"}
def get(url):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=40) as r:
        b=r.read()
        if r.headers.get("Content-Encoding")=="gzip": b=gzip.decompress(b)
        return json.loads(b)
def ts(s): return dt.datetime.fromisoformat(s.replace("Z","+00:00")).timestamp()
FIX={"gs":"gsw","ny":"nyk","sa":"sas","no":"nop","utah":"uta","wsh":"was"}
out=[]; shown=False
for day in ("20261122","20261123","20261124","20261125","20261126"):
    sb=get(f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={day}")
    for ev in sb.get("events",[]):
        comp=ev["competitions"][0]
        if not comp["status"]["type"].get("completed"): continue
        home=[c for c in comp["competitors"] if c["homeAway"]=="home"][0]; away=[c for c in comp["competitors"] if c["homeAway"]=="away"][0]
        ab=lambda c: FIX.get(c["team"]["abbreviation"].lower(), c["team"]["abbreviation"].lower())
        slug=f"nba-{ab(away)}-{ab(home)}-{day[:4]}-{day[4:6]}-{day[6:]}"
        try:
            g=get(f"https://gamma-api.polymarket.com/events?slug={slug}")
            if not g: print("no gamma event",slug); continue
            mk=[m for m in g[0]["markets"] if m["slug"]==slug]
            if not mk: print("no moneyline",slug); continue
            mk=mk[0]
            summ=get(f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={ev['id']}")
            plays=[p for p in summ.get("plays",[]) if p.get("wallclock")]
            end=ts(plays[-1]["wallclock"]); lasttxt=plays[-1].get("text")
            prices=json.loads(mk["outcomePrices"]); win=0 if float(prices[0])>0.5 else 1
            rows=list(dataapi.iter_trades(condition=mk["conditionId"], start=int(end-900), end=int(end+3*3600)))
            rows.sort(key=lambda r:r["timestamp"])
            def wp(r):  # price of the winner implied by the fill
                p=float(r["price"]); return p if int(r["outcome_index"])==win else 1-p
            pre=[r for r in rows if end-120<=r["timestamp"]<end]
            post=[r for r in rows if r["timestamp"]>=end+3]
            first99=next((r["timestamp"]-end for r in rows if r["timestamp"]>=end-600 and wp(r)>=0.99), None)
            lt99=[(wp(r),float(r["size"]),r) for r in post if wp(r)<0.99]
            usd_lt99=sum(p*s for p,s,_ in lt99); edge_lt99=sum((1-p)*s for p,s,_ in lt99)
            usd_post=sum(wp(r)*float(r["size"]) for r in post)
            res=get("https://data-api.polymarket.com/v2/resolutions?condition="+mk["conditionId"])
            rr=res.get("data") or res.get("resolutions") or res.get("items") or [] if isinstance(res,dict) else res
            r0=rr[0] if rr else {}
            if not shown: print("raw resolution:",json.dumps(res)[:900])
            if not shown and r0: print("resolution keys:",sorted(r0.keys())); shown=True
            def tt(k):
                v=r0.get(k)
                if v is None: return None
                return (ts(v) if isinstance(v,str) else float(v))-end
            out.append(dict(slug=slug,last=lasttxt,pre_p=(st.median(wp(r) for r in pre) if pre else None),first99=first99,n_post=len(post),usd_post=usd_post,usd_lt99=usd_lt99,edge_lt99=edge_lt99,
                            proposed=tt("proposed_at") or tt("proposal_time") or tt("last_proposed_at") or tt("requested_at"),resolved=tt("resolved_at"),disputed=r0.get("was_disputed"),closed=(ts(mk["closedTime"].replace(" ","T").replace("+00","+00:00"))-end if mk.get("closedTime") else None)))
        except Exception as ex:
            print("ERR",slug,repr(ex)[:150])
json.dump(out,open("/home/user/polymarket-lab/data/x3/nba_postgame.json","w"),default=str)
f=lambda x,fmt="%.0f": "-" if x is None else fmt%x
print("slug | winner price median last 2 min | first fill >=0.99 (s after last play) | $ after end | $ below 0.99 after end | (1-p)*size below 0.99 | proposed (s) | resolved (s) | closedTime (s)")
for o in out: print(o["slug"],"|",f(o["pre_p"],"%.3f"),"|",f(o["first99"]),"|",f(o["usd_post"]),"|",f(o["usd_lt99"]),"|",f(o["edge_lt99"]),"|",f(o["proposed"]),"|",f(o["resolved"]),"|",f(o["closed"]),"|",(o["last"] or "")[:25])
v=[o["first99"] for o in out if o["first99"] is not None]
if v: print("games",len(out),"first>=0.99 median %.0f s, quartiles %s"%(st.median(v),[round(x) for x in st.quantiles(v,n=4)]))
r=[o["resolved"] for o in out if o["resolved"] is not None]
if r: print("resolved after last play: median %.0f min (min %.0f, max %.0f)"%(st.median(r)/60,min(r)/60,max(r)/60))
print("sum $ traded below 0.99 on the winner after the end: %.0f ; sum of (1-p)*size: %.0f"%(sum(o["usd_lt99"] for o in out),sum(o["edge_lt99"] for o in out)))
