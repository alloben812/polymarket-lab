#!/usr/bin/env python3
"""Corrected wallet summary: uses fees_paid (fees net of refunds) and economic_pnl deltas. usage: wc2.py outdir label=addr ..."""
import json, sys, time, urllib.request, datetime as dt, collections, os
DATA="https://data-api.polymarket.com/v2"; GAMMA="https://gamma-api.polymarket.com"
def get(url, data=None, tries=5):
    last=None
    for i in range(tries):
        try:
            h={"User-Agent":"Mozilla/5.0","Accept":"application/json"}; body=None
            if data is not None: body=json.dumps(data).encode(); h["Content-Type"]="application/json"
            with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=h), timeout=60) as r: return json.loads(r.read())
        except Exception as e: last=e; time.sleep(1.5*(i+1))
    return {"_err": str(last)}
outdir=sys.argv[1]
for arg in sys.argv[2:]:
    label, w = arg.split("=")
    fn=os.path.join(outdir, f"{label}.v2.json")
    if os.path.exists(fn): continue
    st=(get(f"{DATA}/user-stats?user={w}").get("data")) or {}
    pts=sorted(((get(f"{DATA}/user-pnl?user={w}&interval=all&fidelity=1d").get("data")) or {}).get("points") or [], key=lambda x:x["timestamp"])
    tt=(get(f"{GAMMA}/tiers", {"addresses":[w]}).get("tiers") or [None])[0]
    mt=(get(f"{GAMMA}/v1/maker-tier/tiers", {"addresses":[w]}).get("tiers") or [None])[0]
    last=collections.OrderedDict()
    for q in pts: last[dt.datetime.fromtimestamp(q["timestamp"], dt.timezone.utc).strftime("%Y-%m")]=q
    prev={}; months=[]
    for m,q in last.items():
        f=lambda k:(q.get(k) or 0)-(prev.get(k) or 0)
        reb=f("taker_rebate")+f("maker_rebate")+f("reward_income")+f("referral_income")
        months.append({"month":m,"gross":round(f("trade_pnl")),"fees_charged":round(f("fees")),"fees_refunded":round(f("fees_refunded")),"fees_paid":round(f("fees_paid")),
                       "rebates":round(reb),"net":round(f("economic_pnl")),"net_no_reb":round(f("economic_pnl")-reb),"vol":round(f("volume_usdc")),"fills":round(f("trade_count"))})
        prev=q
    json.dump({"label":label,"wallet":w,"stats":st,"taker_tier":tt,"maker_tier":mt,"monthly":months}, open(fn,"w"))
    print("ok", label, len(pts), flush=True); time.sleep(0.3)
