"""Auditor's independent recomputation of E4 (own code; reads raw cached rows, not lib.py / measures.json)."""
import json, gzip, os, math, collections, calendar, time, sys
D="/home/user/polymarket-lab/data/gaps_econ"; E="/home/user/polymarket-lab/data/econ_tapes"
mk=json.load(open(f"{D}/markets.json"))["markets"]
status=json.load(open(f"{D}/release_status.json"))
kept=[m for m in mk if not status[m["release"]].startswith("DROPPED")]
SPLIT=calendar.timegm((2026,10,15,0,0,0))
def rows_gaps(m):
    d=json.load(gzip.open(f"{D}/tapes/{m['cond']}.json.gz"))
    return [(r[0], r[1], r[2], r[4], r[5], r[6]) for r in d["rows"]]   # ts, side, oi, p, size, wallet
def rows_econ(m):
    p=f"{E}/{m['cond']}.json"
    if not os.path.exists(p): return None
    return [(r[0], r[2], r[3], r[4], r[5], r[1]) for r in json.load(open(p))]
def e4(rows, m, d, cap=500.0, maxp=0.97, rate=0.01, lag=3, dedup=False, tmax=None):
    w = 0 if m["winner"]=="Yes" else 1
    if dedup: rows=list(dict.fromkeys(rows))
    rows=sorted(rows, key=lambda r:r[0])
    bud=cap; sh=cost=fee=0.0; fills=[]
    for ts, side, oi, p, z, wal in rows:
        off = ts - lag - m["T"]
        if off < d: continue
        if tmax is not None and off > tmax: continue
        if side=="BUY" and oi==w: wp=p
        elif side=="SELL" and oi!=w: wp=1-p
        else: continue
        if wp > maxp+1e-9: continue
        q=min(z, bud/wp)
        if q<=1e-9: break
        sh+=q; cost+=q*wp; fee+=rate*wp*(1-wp)*q; bud-=q*wp; fills.append((off, round(wp,4), round(q,2), wal[:8] if wal else None))
    return {"sh":sh,"cost":cost,"fee":fee,"net":sh-cost-fee,"fills":fills}
def tstat(xs):
    n=len(xs); mu=sum(xs)/n
    if n<2: return mu, float('nan'), float('nan')
    se=math.sqrt(sum((x-mu)**2 for x in xs)/(n-1)/n); return mu, se, (mu/se if se>0 else float('nan'))
def agg(ms, res):
    cl=collections.defaultdict(float)
    for m in ms: cl[m["T"]]+=res[m["cond"]]["net"]
    xs=list(cl.values()); mu,se,t=tstat(xs)
    return dict(n_rel=len(cl), n_mk=len(ms), net=sum(xs), cost=sum(res[m["cond"]]["cost"] for m in ms), fee=sum(res[m["cond"]]["fee"] for m in ms),
                mk_f=sum(1 for m in ms if res[m["cond"]]["fills"]), rel_f=sum(1 for v in cl.values() if v>0), mean=mu, se=se, t=t)
if __name__=="__main__":
    print("kept markets", len(kept), "release seconds", len({m["T"] for m in kept}), "reporting", sum(m["T"]>=SPLIT for m in kept), len({m["T"] for m in kept if m["T"]>=SPLIT}))
    R={}
    for d in (5,30,120,600):
        res={m["cond"]: e4(rows_gaps(m), m, d) for m in kept}; R[d]=res
        a=agg(kept,res); b=agg([m for m in kept if m["T"]>=SPLIT],res)
        print(f"d={d:>3} ALL net {a['net']:8.1f} cost {a['cost']:8.0f} fee {a['fee']:6.2f} mk_f {a['mk_f']} rel_f {a['rel_f']} t {a['t']:.2f} | REP net {b['net']:8.1f} cost {b['cost']:8.0f} mk_f {b['mk_f']} rel_f {b['rel_f']} mean {b['mean']:.1f} se {b['se']:.1f} t {b['t']:.2f}  $/day {a['net']/87:.2f} / {b['net']/43:.2f}")
    # compare with analyst's measures.json
    M={x["cond"]:x for x in json.load(open(f"{D}/measures.json"))}
    for d in (5,30,120,600):
        diff=max(abs(R[d][c]["net"]-M[c]["e4"][str(d)]["net"]) for c in M)
        print("max abs diff vs analyst per market, d",d, round(diff,6))
    # independent data source: econ_tapes (other study's download)
    ov=[m for m in kept if os.path.exists(f"{E}/{m['cond']}.json")]
    print("overlap with econ_tapes:", len(ov), "markets,", len({m['T'] for m in ov}), "release seconds")
    for d in (5,30):
        r1={m["cond"]: e4(rows_gaps(m), m, d) for m in ov}; r2={m["cond"]: e4(rows_econ(m), m, d) for m in ov}
        print(f"d={d} overlap subset: gaps tapes net {sum(v['net'] for v in r1.values()):.1f} cost {sum(v['cost'] for v in r1.values()):.0f} | econ_tapes net {sum(v['net'] for v in r2.values()):.1f} cost {sum(v['cost'] for v in r2.values()):.0f}; markets differing >$0.5: {sum(1 for c in r1 if abs(r1[c]['net']-r2[c]['net'])>0.5)}")
        for m in ov:
            c=m["cond"]
            if abs(r1[c]['net']-r2[c]['net'])>0.5: print("   DIFF", m["release"], m["slug"][:45], round(r1[c]['net'],1), round(r2[c]['net'],1), len(rows_gaps(m)), len(rows_econ(m)))
    json.dump({str(d):{c:v for c,v in R[d].items()} for d in R}, open("my_e4.json","w"))
