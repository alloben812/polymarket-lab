"""Markets the protocol dropped for volumeNum < 5,000: what did the same E3/E4 look like there? (selection on a post-event variable)"""
import sys; sys.path.insert(0, "/tmp/claude-0/-home-user/05556429-066d-541b-b886-b8da26bcc648/scratchpad/audit"); sys.dont_write_bytecode=True
import json, gzip, collections, time, os, calendar
from a1 import *
from a4 import get, tape
import rc_copy as rc
def ts(s):
    s=(s or "").replace(" ","T")[:19]
    return calendar.timegm(time.strptime(s,"%Y-%m-%dT%H:%M:%S")) if len(s)==19 else None
ev=json.load(gzip.open(f"{D}/events_core.json.gz")); small=[]
for e in ev:
    r=rc.match(e["slug"])
    if not r or status.get(r["id"],"DROPPED").startswith("DROPPED"): continue
    for m in e.get("markets") or []:
        v=float(m.get("volumeNum") or 0); out=m.get("outcomes"); out=json.loads(out) if isinstance(out,str) else out
        c=ts(m.get("closedTime"))
        if v<5000 and v>0 and out==["Yes","No"] and c and c>r["T"]:
            small.append({"release":r["id"],"type":r["type"],"tier":r["tier"],"T":r["T"],"cond":m["conditionId"],"slug":m["slug"],"vol":v,"flag":r["flag"],"closed_ts":c})
print("small markets (0 < volumeNum < 5,000, closed after T, kept releases):", len(small), "in", len({m['T'] for m in small}), "release seconds")
os.makedirs("small", exist_ok=True)
conds=[m["cond"] for m in small]; win={}
for i in range(0,len(conds),10):
    d=get("tokens", condition=",".join(conds[i:i+10])); fin=collections.defaultdict(dict)
    for t in d.get("data") or []:
        if t.get("resolved"): fin[t["condition_id"]][t["outcome"]]=t.get("final_price")
    for c,f in fin.items():
        try:
            if float(f["Yes"])==1.0 and float(f["No"])==0.0: win[c]="Yes"
            elif float(f["No"])==1.0 and float(f["Yes"])==0.0: win[c]="No"
        except Exception: pass
    time.sleep(0.12)
small=[dict(m, winner=win[m["cond"]]) for m in small if m["cond"] in win]
print("resolved 1/0:", len(small))
for m in small:
    p=f"small/{m['cond']}.json"
    if not os.path.exists(p):
        rows=tape(m["cond"], m["T"]-7203); json.dump([(x["timestamp"], x["side"], x["outcome_index"], float(x["price"]), float(x["size"]), x["proxy_wallet"]) for x in rows], open(p,"w")); time.sleep(0.12)
json.dump(small, open("small_markets.json","w"))
def rws(m): return [tuple(r) for r in json.load(open(f"small/{m['cond']}.json"))]
for d in (5,30,120):
    res={m["cond"]: e4(rws(m), m, d) for m in small}
    for name, ms, days in (("ALL", small, 87), ("REPORTING", [m for m in small if m["T"]>=SPLIT], 43)):
        cl=collections.defaultdict(float)
        for m in ms: cl[m["T"]]+=res[m["cond"]]["net"]
        tot=sum(cl.values()); print(f"d={d:>3} small {name:<9} markets {len(ms)} (fills {sum(1 for m in ms if res[m['cond']]['fills'])}) releases {len(cl)} (nonzero {sum(1 for v in cl.values() if v>0)}) net {tot:8.1f} cost {sum(res[m['cond']]['cost'] for m in ms):7.0f} $/day {tot/days:.2f}")
    if d==30:
        for m in sorted(small, key=lambda m:-res[m["cond"]]["net"])[:12]:
            if res[m["cond"]]["fills"]: print("     ", m["release"], m["slug"][:48], "vol", round(m["vol"]), "flag" if m["flag"] else "", "net", round(res[m["cond"]]["net"],1), res[m["cond"]]["fills"][:4])
# E3 in small markets
gap=[0.0]*5; BK=[(0,5),(5,30),(30,120),(120,600),(600,10**9)]
for m in small:
    w=0 if m["winner"]=="Yes" else 1
    for t,side,oi,p,z,wl in rws(m):
        off=t-3-m["T"]; wp=p if oi==w else 1-p
        if off>=0 and wp<0.95-1e-9 and ((side=="BUY" and oi==w) or (side=="SELL" and oi!=w)):
            gap[next(i for i,(lo,hi) in enumerate(BK) if lo<=off<hi)]+=z*(1-wp)
print("E3(a) gap dollars in small markets by bucket:", [round(g) for g in gap], "total", round(sum(gap)))
