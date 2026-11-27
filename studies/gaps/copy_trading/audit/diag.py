import sys, collections, math, json
sys.path.insert(0, ".")
from recompute import *
# reference on same entries
def ref_rows():
    out = {}
    for e in late:
        c, x, tb, w = e["c"], e["o"], e["t"], e["wallet"]
        tp = L(C + f"tape/{c}.json.gz")["rows"]
        rz = res.get(c) or {}; fin = (rz.get("final") or {}).get(x); resolved = bool(rz.get("resolved")) and fin is not None
        if resolved: pay = float(fin)
        else:
            lt = -1; last = None
            for r in tp:
                p = r["p"] if r["o"] == x else 1 - r["p"]
                if r["t"] > lt: lt, last = r["t"], p
            pay = last
        taker = any(r["t"] == tb and r["w"] == w and r["o"] == x and r["s"] == "BUY" for r in tp)
        rt, _ = rate(meta.get(c)); p0 = e["p"]; q = 10 / p0
        fee = q * rt * p0 * (1 - p0) if taker else 0
        cost = q * p0 + fee
        out[(w, e["tok"], tb)] = dict(cost=cost, net=q * pay - cost, c=c, taker=taker, p0=p0, resolved=resolved, filled=True, e=e)
    return out
ref = ref_rows()
def agg(rs, label):
    by = collections.defaultdict(lambda: [0.0, 0.0])
    for r in rs: by[r["c"]][0] += r["net"]; by[r["c"]][1] += r["cost"]
    num = [v[0] for v in by.values()]; den = [v[1] for v in by.values()]
    if len(num) < 3: print(label, "too few"); return
    r, se = ratio_cluster(num, den)
    print(f"{label}: n {len(rs)} mkts {len(by)} spent {sum(den):.0f} net {sum(num):+.0f} ret {r:+.1%} se {se:.1%} t {r/se:+.2f}")
k = lambda e: (e["wallet"], e["tok"], e["t"])
agg(list(ref.values()), "REF all")
for d in (10, 60, 300):
    rows, _ = evaluate(d)
    fs = {k(r["e"]) for r in rows if r["filled"]}
    agg([ref[x] for x in ref if x in fs], f"REF on d{d}-FILLED entries")
    agg([ref[x] for x in ref if x not in fs], f"REF on d{d}-UNFILLED entries")
    # copy-vs-ref paired on filled entries: copy net vs ref net at same entries
    # slippage in price terms
    sl = [r["v"] - ref[k(r["e"])]["p0"] for r in rows if r["filled"]]
    sl.sort(); print("   slip median", sl[len(sl)//2], "mean", sum(sl)/len(sl))
    # resolved only
    agg([r for r in rows if r["filled"] and r["resolved"]], f"d{d} COPY resolved-only")
# stale-ask variants
for d in (10, 60):
    for st in (30, 120, 600):
        rows, _ = evaluate(d, mode="stale", stale=st)
        summarize(rows, f"d{d} STALE<= {st}s")
        fs = {k(r["e"]) for r in rows if r["filled"]}
        agg([ref[x] for x in ref if x in fs], f"      REF same entries")
