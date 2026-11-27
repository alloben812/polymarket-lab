import sys, collections
sys.path.insert(0, ".")
from recompute import *
from diag import ref, agg, k
# 1. adjusted reference: all entries, wallet price + slip, fee always
for slip in (0.0, 0.01, 0.02):
    rs = []
    for key, r in ref.items():
        e = r["e"]; p0 = min(0.99, e["p"] + slip)
        # recompute payoff from ref net: pay = (net+cost)/q
        q0 = 10 / e["p"]; pay = (r["net"] + r["cost"]) / q0
        rt, _ = rate(meta.get(e["c"])); q = 10 / p0
        cost = q * p0 + q * rt * p0 * (1 - p0)
        rs.append(dict(c=e["c"], cost=cost, net=q * pay - cost))
    agg(rs, f"ALL entries, price = wallet+{slip:.2f}, fee always")
    # taker entries only
    agg([x for x, (key, r) in zip(rs, ref.items()) if r["taker"]], f"   TAKER entries only")
    agg([x for x, (key, r) in zip(rs, ref.items()) if r["taker"] and r["resolved"]], f"   TAKER, resolved only")
# 2. own-fill share in d10 fills
for d in (10, 60, 300):
    own = oth = 0; ownr = []; othr = []
    for e in late:
        pass
rows, _ = evaluate(10)
cnt = collections.Counter(); sub = {"own": [], "other": []}
for r in rows:
    if not r["filled"]: continue
    e = r["e"]; tb = e["t"]; d = 10
    tp = L(C + f"tape/{e['c']}.json.gz")["rows"]
    T = None
    # find fill block again
    blk = {}
    for x in tp:
        p = (x["p"] if x["s"] == "BUY" and x["o"] == e["o"] else (1 - x["p"] if x["s"] == "SELL" and x["o"] != e["o"] else None))
        if p is not None and tb + d <= x["t"] - 3 <= tb + d + 30: blk.setdefault(x["t"], []).append(x)
    T = min(blk)
    ownflag = any(x["w"] == e["wallet"] for x in blk[T])
    cnt[ownflag] += 1; sub["own" if ownflag else "other"].append(r)
print("d10 fill blocks containing wallet's own rows:", dict(cnt))
agg(sub["own"], "d10 copy, fills in blocks with wallet's own rows")
agg(sub["other"], "d10 copy, fills from other traders only")
# 3. tape completeness
inc = 0
import glob
for p in glob.glob(C + "tape/*.json.gz"):
    t = L(p)
    if not t["complete"]: inc += 1
print("incomplete tapes", inc)
# 4. payoff sign sanity: resolved markets, last tape price of x vs final
bad = tot = 0
for e in late:
    rz = res.get(e["c"]) or {}; fin = (rz.get("final") or {}).get(e["o"])
    if not (rz.get("resolved") and fin is not None): continue
    tp = L(C + f"tape/{e['c']}.json.gz")["rows"]
    if not tp: continue
    last = max(tp, key=lambda r: r["t"]); px = last["p"] if last["o"] == e["o"] else 1 - last["p"]
    tot += 1
    if abs(px - float(fin)) > 0.5: bad += 1
print("resolved entries", tot, "last tape price contradicts final (>0.5 away):", bad)
