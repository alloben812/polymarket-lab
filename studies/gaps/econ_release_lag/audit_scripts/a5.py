import sys; sys.path.insert(0, "/tmp/claude-0/-home-user/05556429-066d-541b-b886-b8da26bcc648/scratchpad/audit")
import json, collections, time
from a1 import *
from a4 import get
sample=json.load(open("sample.json")); bycond={m["cond"]:m for m in kept}
tot={5:[0,0,0,0],30:[0,0,0,0]}; ndiff=0; dup_same_tx=dup_diff_tx=0; nrows=0; multi_tx=0; pages=collections.Counter()
for c in sample:
    m=bycond[c]; live=json.load(open(f"live/{c}.json"))
    lr=[(x["timestamp"], x["side"], x["outcome_index"], float(x["price"]), float(x["size"]), x["proxy_wallet"]) for x in live]
    cr=rows_gaps(m)
    lo=max(min(r[0] for r in lr), min(r[0] for r in cr))
    A=collections.Counter(r for r in lr if r[0]>=lo and r[0] >= m["T"]-7200); B=collections.Counter(r for r in cr if r[0]>=lo and r[0] >= m["T"]-7200)
    if A!=B: ndiff+=1; print("ROW DIFF", m["release"], m["slug"][:40], sum((A-B).values()), sum((B-A).values()))
    # duplicates by tx hash
    g=collections.defaultdict(list)
    for x in live: g[(x["timestamp"], x["side"], x["outcome_index"], float(x["price"]), float(x["size"]), x["proxy_wallet"])].append(x["transaction_hash"])
    for k,v in g.items():
        if len(v)>1:
            if len(set(v))==1: dup_same_tx+=len(v)-1
            else: dup_diff_tx+=len(v)-1
    nrows+=len(live)
    # rows per tx: taker-order aggregation check
    txc=collections.Counter(x["transaction_hash"] for x in live)
    multi_tx+=sum(1 for v in txc.values() if v>1)
    for d in (5,30):
        a=e4(lr,m,d); b=e4(cr,m,d); tot[d][0]+=a["net"]; tot[d][1]+=b["net"]; tot[d][2]+=a["cost"]; tot[d][3]+=b["cost"]
print(f"sample {len(sample)} markets, rows {nrows}; markets with row differences vs cache: {ndiff}")
print(f"identical-looking rows: same tx hash {dup_same_tx}, different tx hash {dup_diff_tx}; tx hashes carrying >1 row: {multi_tx}")
for d in (5,30): print(f"d={d}: live download net {tot[d][0]:.1f} cost {tot[d][2]:.0f} | analyst cache net {tot[d][1]:.1f} cost {tot[d][3]:.0f}")
# what do multi-row transactions look like? (AR-CPI-oct, +55 s)
for slugpat, offs in (("will-argentinas-monthly-inflation-in-october-2026-be-between-1pt9", (36,80)), ("will-argentinas-monthly-inflation-in-october-2026-be-between-2pt2",(36,80)), ("will-germany-gdp-growth-in-q3-2026-be-at-least-1pt3",(50,120)), ("will-germany-gdp-growth-in-q3-2026-be-between-1pt0",(50,120))):
    m=next(x for x in kept if x["slug"].startswith(slugpat)); live=json.load(open(f"live/{m['cond']}.json"))
    print("\n", m["slug"][:60], "winner", m["winner"])
    for x in sorted(live, key=lambda x:x["timestamp"]):
        o=x["timestamp"]-3-m["T"]
        if offs[0]<=o<=offs[1]: print(f"   +{o:>3}s {x['side']:<4} {x['outcome']:<3} p={float(x['price']):.4f} z={float(x['size']):>8.2f} {x['proxy_wallet'][:10]} tx={x['transaction_hash'][:12]} name={x.get('name','')[:18]}")
