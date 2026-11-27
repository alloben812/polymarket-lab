import json,sys,datetime as dt,collections
d=json.load(open(sys.argv[1]))['data']
pts=sorted(d['points'],key=lambda p:p['timestamp'])
K=['trade_pnl','fees','taker_rebate','maker_rebate','reward_income','economic_pnl','volume','volume_usdc','trade_count']
def day(t): return dt.datetime.fromtimestamp(t,dt.timezone.utc).strftime('%Y-%m-%d')
# last point per day
last={}
for p in pts: last[day(p['timestamp'])]=p
days=sorted(last)
print("days",len(days),days[0],days[-1])
def delta(a,b,k): return (b.get(k) or 0)-(a.get(k) or 0)
zero={k:0 for k in K}
# monthly
print(f"\n{'month':8s} {'gross':>10s} {'fees':>10s} {'tk_reb':>9s} {'mk_reb':>8s} {'NET':>10s} {'net_noreb':>10s} {'vol_usdc':>11s} {'shares':>11s} {'fills':>9s} {'fee/usdc':>8s} {'tkreb%':>6s} {'gross/sh¢':>9s}")
months=collections.OrderedDict()
for dd in days: months.setdefault(dd[:7],[]).append(dd)
prev=zero
for m,ds in months.items():
    cur=last[ds[-1]]
    g=delta(prev,cur,'trade_pnl'); f=delta(prev,cur,'fees'); tr=delta(prev,cur,'taker_rebate'); mr=delta(prev,cur,'maker_rebate'); rw=delta(prev,cur,'reward_income')
    v=delta(prev,cur,'volume_usdc'); sh=delta(prev,cur,'volume'); n=delta(prev,cur,'trade_count')
    net=g+f+tr+mr+rw
    print(f"{m:8s} {g:10.0f} {f:10.0f} {tr:9.0f} {mr:8.0f} {net:10.0f} {g+f:10.0f} {v:11.0f} {sh:11.0f} {n:9.0f} {(-f/v*100 if v else 0):7.2f}% {(-tr/f*100 if f else 0):5.1f}% {(g/sh*100 if sh else 0):9.2f}")
    prev=cur
# weekly last 12 weeks
print("\nlast 14 weeks (7-day buckets ending at last day):")
print(f"{'end':10s} {'gross':>9s} {'fees':>9s} {'tk_reb':>8s} {'mk_reb':>7s} {'NET':>9s} {'net_noreb':>9s} {'vol_usdc':>10s} {'fills':>8s}")
idx=list(range(len(days)-1,-1,-7))[:15][::-1]
for a,b in zip(idx[:-1],idx[1:]):
    pa,pb=last[days[a]],last[days[b]]
    g=delta(pa,pb,'trade_pnl'); f=delta(pa,pb,'fees'); tr=delta(pa,pb,'taker_rebate'); mr=delta(pa,pb,'maker_rebate'); rw=delta(pa,pb,'reward_income')
    print(f"{days[b]:10s} {g:9.0f} {f:9.0f} {tr:8.0f} {mr:7.0f} {g+f+tr+mr+rw:9.0f} {g+f:9.0f} {delta(pa,pb,'volume_usdc'):10.0f} {delta(pa,pb,'trade_count'):8.0f}")
# daily stats of economic pnl
import statistics as st
dn=[]; dnr=[]
prev=zero
for dd in days:
    cur=last[dd]
    g=delta(prev,cur,'trade_pnl'); f=delta(prev,cur,'fees'); tr=delta(prev,cur,'taker_rebate'); mr=delta(prev,cur,'maker_rebate'); rw=delta(prev,cur,'reward_income')
    dn.append(g+f+tr+mr+rw); dnr.append(g+f); prev=cur
def dd_max(xs):
    c=0;peak=0;mdd=0
    for x in xs:
        c+=x; peak=max(peak,c); mdd=max(mdd,peak-c)
    return mdd
print(f"\ndaily NET (with rebates): mean {st.mean(dn):.0f} median {st.median(dn):.0f} sd {st.pstdev(dn):.0f} min {min(dn):.0f} max {max(dn):.0f} losing days {sum(1 for x in dn if x<0)}/{len(dn)} maxDD {dd_max(dn):.0f}")
print(f"daily net WITHOUT rebates: mean {st.mean(dnr):.0f} median {st.median(dnr):.0f} sd {st.pstdev(dnr):.0f} min {min(dnr):.0f} max {max(dnr):.0f} losing days {sum(1 for x in dnr if x<0)}/{len(dnr)} maxDD {dd_max(dnr):.0f}")
print("worst 5 days (net w/ rebates):", sorted(zip(dn,days))[:5])
