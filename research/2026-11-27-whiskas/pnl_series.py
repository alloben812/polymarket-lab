import json,sys,datetime as dt
d=json.load(open(sys.argv[1]))['data']
pts=d['points']
print("interval",d['interval'],"fidelity",d['fidelity'],"source_fidelity",d.get('source_fidelity'),"n",len(pts))
print("keys",list(pts[0].keys()))
def ts(t): return dt.datetime.fromtimestamp(t,dt.timezone.utc).strftime('%Y-%m-%d %H:%M')
print("first",ts(pts[0]['timestamp']),"last",ts(pts[-1]['timestamp']))
# find the point nearest to the article screenshot value 624300.88
target=624300.88
for k in ['trade_pnl','settled_pnl','economic_pnl','realized_pnl','position_pnl']:
    best=min(pts,key=lambda p:abs((p.get(k) or 0)-target))
    print(f"{k:14s} closest to 624300.88 -> {best[k]:.2f} at {ts(best['timestamp'])}")
# values at tweet time 2026-10-24 18:49 UTC
tt=1792867748
p=max([q for q in pts if q['timestamp']<=tt],key=lambda q:q['timestamp'])
print("\nAt tweet time (", ts(p['timestamp']),")")
for k in ['trade_pnl','fees','realized_pnl','maker_rebate','taker_rebate','reward_income','wallet_income','settled_pnl','economic_pnl','volume','volume_usdc','trade_count']:
    print(f"  {k:14s} {p.get(k)}")
