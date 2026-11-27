import sys,json,re,glob,os,collections,math,statistics as st
res=json.load(open(sys.argv[2])); FEE=0.05
byslug={v['slug']:v for v in res.values()}
tot=collections.defaultdict(lambda:[0,0.0,0.0,0.0,0.0])   # n, shares, usd, pnl_gross, fee
wal=collections.defaultdict(lambda:[0,0.0,0.0,0.0,0.0])
tb=collections.defaultdict(lambda:[0,0.0,0.0,0.0,0.0]); pbk=collections.defaultdict(lambda:[0,0.0,0.0,0.0,0.0])
nm=0; vols=[]; mk_pnl=[]
for path in sorted(glob.glob(os.path.join(sys.argv[1],"*.jsonl"))):
    slug=os.path.basename(path)[:-6]; rv=byslug.get(slug)
    if not rv or not rv['resolved']: continue
    t0=int(slug.rsplit('-',1)[1]); nm+=1; v=0; mp=0
    for l in open(path):
        r=json.loads(l); win=1.0 if rv['final'].get(r['o'])==1.0 else 0.0
        z=r['z']; p=r['p']; usd=z*p; fee=FEE*z*p*(1-p)
        g=(win-p)*z if r['s']=='BUY' else (p-win)*z
        for d,k in ((tot,r['s']),(wal,r['w']),(tb,min(max((r['t']-3-t0)//30,-1),10)),(pbk,min(int(p*10),9))):
            a=d[k]; a[0]+=1; a[1]+=z; a[2]+=usd; a[3]+=g; a[4]+=fee
        v+=usd; mp+=g
    vols.append(v); mk_pnl.append(mp)
print(f"markets {nm}; taker-side volume per market: median ${st.median(vols):.0f} mean ${st.mean(vols):.0f}")
def show(title,d,keys=None,fmt=str):
    print("\n"+title); print(f"{'key':>12s} {'fills':>8s} {'shares':>10s} {'usdc':>10s} {'gross¢/sh':>9s} {'fee¢/sh':>8s} {'net¢/sh':>8s} {'gross$':>9s} {'net$':>9s}")
    for k in (keys or sorted(d)):
        n,sh,usd,g,fee=d[k]
        print(f"{fmt(k):>12s} {n:8d} {sh:10.0f} {usd:10.0f} {g/sh*100:+9.2f} {fee/sh*100:8.2f} {(g-fee)/sh*100:+8.2f} {g:+9.0f} {g-fee:+9.0f}")
show("ALL TAKERS by side",tot)
A=[sum(d[k][i] for k in d) for d in (tot,) for i in range(5)]
n,sh,usd,g,fee=A
print(f"\nALL TAKERS: shares {sh:.0f} usdc {usd:.0f}  gross {g:+.0f}$ ({g/sh*100:+.2f}c/sh, {g/usd*100:+.2f}% of usdc)  fees {fee:.0f}$ ({fee/sh*100:.2f}c/sh)  net {g-fee:+.0f}$ ({(g-fee)/usd*100:+.2f}%)")
print(f"=> ALL MAKERS combined (mirror): {-g:+.0f}$ = {-g/sh*100:+.2f}c per share traded, per market {-g/nm:+.1f}$")
se=st.pstdev(mk_pnl)/math.sqrt(nm); print(f"   per-market taker gross: mean {st.mean(mk_pnl):+.1f}$ sd {st.pstdev(mk_pnl):.0f}$  (SE {se:.1f}$, t={st.mean(mk_pnl)/se:+.2f})")
show("TAKERS by time in window (30s buckets from start; -1 = before start)",tb,fmt=lambda k:f"{int(k)*30}s")
show("TAKERS by price decile",pbk,fmt=lambda k:f"{k/10:.1f}-{(k+1)/10:.1f}")
print(f"\ndistinct taker wallets: {len(wal)}")
top=sorted(wal.items(),key=lambda kv:-kv[1][2])[:15]
show("TOP 15 TAKER WALLETS by volume",dict(top),keys=[k for k,_ in top])
tv=sum(a[2] for a in wal.values()); print(f"top15 share of taker volume: {sum(a[2] for _,a in top)/tv*100:.1f}%")
# distribution of wallet results
big=[(k,a) for k,a in wal.items() if a[2]>=2000]
print(f"wallets with >= $2k taker volume in sample: {len(big)}; profitable gross: {sum(1 for k,a in big if a[3]>0)}; profitable net of fees: {sum(1 for k,a in big if a[3]-a[4]>0)}")
small=[(k,a) for k,a in wal.items() if a[2]<2000]
sg=sum(a[3] for k,a in small); sf=sum(a[4] for k,a in small); su=sum(a[2] for k,a in small)
print(f"small wallets (<$2k): {len(small)} wallets, usdc {su:.0f} ({su/tv*100:.1f}% of volume), gross {sg:+.0f}$ ({sg/su*100:+.2f}%), net {sg-sf:+.0f}$ ({(sg-sf)/su*100:+.2f}%)")
bg=sum(a[3] for k,a in big); bf=sum(a[4] for k,a in big); bu=sum(a[2] for k,a in big)
print(f"big wallets (>=$2k): {len(big)} wallets, usdc {bu:.0f} ({bu/tv*100:.1f}% of volume), gross {bg:+.0f}$ ({bg/bu*100:+.2f}%), net {bg-bf:+.0f}$ ({(bg-bf)/bu*100:+.2f}%)")
