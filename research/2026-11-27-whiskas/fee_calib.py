import json,sys,datetime as dt,calendar
pts=sorted(json.load(open(sys.argv[1]))['data']['points'],key=lambda p:p['timestamp'])
def at(ts):
    c=[p for p in pts if p['timestamp']<=ts]; return c[-1]
def win(a,b):
    A=at(calendar.timegm(dt.datetime.strptime(a,'%Y-%m-%d %H:%M').timetuple())); B=at(calendar.timegm(dt.datetime.strptime(b,'%Y-%m-%d %H:%M').timetuple()))
    return {k:(B.get(k) or 0)-(A.get(k) or 0) for k in ('fees','trade_pnl','taker_rebate','maker_rebate','volume','volume_usdc','trade_count')}
for name,a,b,path in (('jul','2026-07-20 00:00','2026-07-22 00:00','jul'),('sep','2026-09-02 00:00','2026-09-04 00:00','sep'),('oct','2026-10-06 00:00','2026-10-08 00:00','oct'),('recent','2026-11-21 00:00','2026-11-27 14:00','recent')):
    w=win(a,b)
    rows=[json.loads(l) for l in open(f"{sys.argv[2]}/{path}_labeled.jsonl")]
    ta=dt.datetime.strptime(a,'%Y-%m-%d %H:%M').replace(tzinfo=dt.timezone.utc).timestamp(); tb=dt.datetime.strptime(b,'%Y-%m-%d %H:%M').replace(tzinfo=dt.timezone.utc).timestamp()
    rows=[r for r in rows if ta<=r['timestamp']<tb]
    wT=sum(r['size']*r['price']*(1-r['price']) for r in rows if r['role']=='T'); wM=sum(r['size']*r['price']*(1-r['price']) for r in rows if r['role']=='M')
    usd=sum(r['size']*r['price'] for r in rows); sh=sum(r['size'] for r in rows)
    print(f"{name:7s} API: fees {w['fees']:.0f} gross {w['trade_pnl']:.0f} tk_reb {w['taker_rebate']:.0f} mk_reb {w['maker_rebate']:.0f} vol_usdc {w['volume_usdc']:.0f} shares {w['volume']:.0f} fills {w['trade_count']:.0f}")
    print(f"        mine: usdc {usd:.0f} shares {sh:.0f} rows {len(rows)}  taker Σsh·p(1-p) {wT:.0f}  maker Σ {wM:.0f}")
    print(f"        implied taker fee coefficient = fees/ΣT = {(-w['fees']/wT):.4f};  taker rebate/fees = {w['taker_rebate']/-w['fees']*100:.1f}%;  maker rebate / (coef·ΣM) = {w['maker_rebate']/((-w['fees']/wT)*wM)*100:.1f}%")
