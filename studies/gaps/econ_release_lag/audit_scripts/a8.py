import sys; sys.path.insert(0, "/tmp/claude-0/-home-user/05556429-066d-541b-b886-b8da26bcc648/scratchpad/audit"); sys.dont_write_bytecode=True
import json, gzip, collections, time, re
from a1 import *
from a4 import get
import rc_copy as rc
# 1. winners straight from the tokens endpoint, all kept markets
bad=0; n=0; odd=[]
conds=[m["cond"] for m in kept]; bc={m["cond"]:m for m in kept}
for i in range(0,len(conds),10):
    d=get("tokens", condition=",".join(conds[i:i+10])); fin=collections.defaultdict(dict); res=collections.defaultdict(list)
    for t in d.get("data") or []:
        fin[t["condition_id"]][t["outcome"]]=t.get("final_price"); res[t["condition_id"]].append(bool(t.get("resolved")))
    for c in conds[i:i+10]:
        n+=1; f=fin.get(c,{}); 
        try: w="Yes" if float(f.get("Yes"))==1.0 and float(f.get("No"))==0.0 else ("No" if float(f.get("No"))==1.0 and float(f.get("Yes"))==0.0 else None)
        except Exception: w=None
        if w!=bc[c]["winner"] or not all(res[c]): bad+=1; odd.append((bc[c]["slug"][:50], f, res[c], bc[c]["winner"]))
    time.sleep(0.15)
print("winners re-checked live:", n, "mismatches:", bad, odd[:5])
# 2. are the key +30 s fills really taker fills of those wallets? (user feed, taker_only default vs false)
def fills(w, t0, t1, taker_only=None):
    d=get("trades", user=w, start=t0, end=t1, limit=1000, taker_only=taker_only)
    return [(x["timestamp"], x["side"], x["outcome"], round(float(x["price"]),4), round(float(x["size"]),2), x["condition_id"][:10]) for x in d.get("data") or []]
checks=[("will-argentinas-monthly-inflation-in-october-2026-be-between-1pt9", 55), ("will-argentinas-monthly-inflation-in-october-2026-be-between-2pt2", 75), ("will-germany-gdp-growth-in-q3-2026-be-at-least-1pt3", 58), ("will-germany-gdp-growth-in-q3-2026-be-between-1pt0", 58), ("will-south-korea-gdp-growth-in-q3-2026-be-between-3pt0", 269)]
for pat, off in checks:
    m=next(x for x in kept if x["slug"].startswith(pat)); live=json.load(open(f"live/{m['cond']}.json"))
    for x in live:
        o=x["timestamp"]-3-m["T"]
        if o==off and x["side"]=="BUY":
            w=x["proxy_wallet"]; t=x["timestamp"]
            tk=collections.Counter(fills(w, t-2, t+2)); al=collections.Counter(fills(w, t-2, t+2, "false")); time.sleep(0.2)
            key=(t, x["side"], x["outcome"], round(float(x["price"]),4), round(float(x["size"]),2), x["condition_id"][:10])
            print(f"{pat[5:45]} +{off}s {x.get('name','')[:14]:<14} {x['side']} {x['outcome']} {float(x['price']):.4f} x {float(x['size']):.2f}: in taker feed {tk.get(key,0)}, in full feed {al.get(key,0)}; maker-only rows of this wallet in +-2 s: {sum((al-tk).values())}")
# 3. events_raw vs events_core: release-like events that never reached the calendar
raw=json.load(gzip.open(f"{D}/events_raw.json.gz")); core={e["slug"] for e in json.load(gzip.open(f"{D}/events_core.json.gz"))}
print("\nevents_raw", len(raw), "events_core", len(core))
kw=re.compile(r"(inflation|cpi|ppi|pce|gdp|unemployment|jobs|payroll|jolts|pmi|ism-|sentiment|retail-sales|jobless|claims|decision|interest-rate|rate-cut|rate-hike|fed-|ecb|bank-of|central-bank|housing-starts|trade-balance|durable|confidence)")
miss=[]
for e in raw:
    if e["slug"] in core: continue
    v=sum(float(x.get("volumeNum") or 0) for x in (e.get("markets") or []))
    if kw.search(e["slug"]): miss.append((v, e["slug"], (e.get("endDate") or "")[:10], rc.match(e["slug"]) is not None))
print("release-like slugs in raw but not in core:", len(miss), "| of which a calendar pattern would match:", sum(1 for x in miss if x[3]))
for v,s,d,mt in sorted(miss, reverse=True)[:30]: print(f"   {v:>12,.0f} {d} {'MATCH' if mt else '     '} {s[:95]}")
# excluded-by-rule events inside core, by reason, with volume
byr=collections.defaultdict(lambda:[0,0.0,[]])
for e in json.load(gzip.open(f"{D}/events_core.json.gz")):
    if rc.match(e["slug"]): continue
    why=rc.excluded_reason(e["slug"]); v=sum(float(x.get("volumeNum") or 0) for x in (e.get("markets") or []))
    byr[why][0]+=1; byr[why][1]+=v; byr[why][2].append((v,e["slug"][:60]))
print("\nexcluded inside events_core:")
for k,(c,v,l) in byr.items(): print(f"   {c:>3} events ${v:>13,.0f}  {k[:70]} | e.g. {[s for _,s in sorted(l,reverse=True)[:3]]}")
