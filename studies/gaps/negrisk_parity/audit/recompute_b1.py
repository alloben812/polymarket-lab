"""Independent recompute of B1 (neg-risk YES basket, asks sum < 1 after fees) from raw cached archive hours.
Own replay code (not a2_episodes.py). Subset: non-augmented negRisk events with >=2 markets whose every market is
live and unresolved at hour start. Usage: python3 -I recompute_b1.py <hourtag> -> audit/b1_<tag>.json
Reports: positive states/episodes (net>0, min top size>=5), continuous-5s takeable (author's definition),
relaxed takeable (state at t0+5s positive although the episode was interrupted in between), share of hour positive.
"""
import json, sys, os
import numpy as np, pyarrow as pa, pyarrow.parquet as pq, pyarrow.compute as pc
D = "/home/user/polymarket-lab/data/gaps_negrisk"
AUD = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, "/home/user/polymarket-lab/studies/gaps/negrisk_parity")
from common import families

tag = sys.argv[1]
FAM = families()
evs = {}
for e in FAM["B"]:
    if e.get("negRiskAugmented"):
        continue
    evs[e["slug"]] = e
tokmap = {}
for slug, e in evs.items():
    for m in e["markets"]:
        tokmap[int(m["yes"])] = (slug, m["conditionId"], True)
        tokmap[int(m["no"])] = (slug, m["conditionId"], False)

o = pq.read_table(f"{D}/hours/{tag}.open.parquet", columns=["asset_id", "bids", "asks", "resolved"])
book = {}   # cond -> [bids dict, asks dict] YES space
res = set(); seen = set()
def ingest(d, levels, yes, bid_side):
    nd = {}
    for lv in levels or []:
        p = float(lv["price"]); s = float(lv["size"])
        if s > 0:
            nd[p if yes else round(1 - p, 4)] = s
    return nd
for a, bids, asks, r in zip(o["asset_id"].to_pylist(), o["bids"].to_pylist(), o["asks"].to_pylist(), o["resolved"].to_pylist()):
    k = tokmap.get(int.from_bytes(a, "big"))
    if not k: continue
    slug, c, y = k
    seen.add(c)
    if r: res.add(c)
    bk = book.setdefault(c, [{}, {}])
    if y:
        bk[0] = ingest(None, bids, True, True); bk[1] = ingest(None, asks, True, False)
    elif not bk[0] and not bk[1]:
        bk[1] = ingest(None, bids, False, True); bk[0] = ingest(None, asks, False, False)
# events usable: every market seen in opening state and none resolved
use = {}
for slug, e in evs.items():
    cs = [m["conditionId"] for m in e["markets"]]
    if all(c in seen for c in cs) and not any(c in res for c in cs):
        use[slug] = e
conds = {m["conditionId"] for e in use.values() for m in e["markets"]}
vs = pa.array([bytes.fromhex(c[2:]) for c in sorted(conds)], type=pa.binary())
t = pq.read_table(f"{D}/hours/{tag}.ev.parquet", columns=["event_type", "timestamp", "market", "asset_id", "bids", "asks",
                  "price", "size", "side", "recv_lag_ms", "row_ordinal"])
t = t.filter(pc.and_(pc.is_in(t["market"], value_set=vs), pc.is_in(t["event_type"], value_set=pa.array(["book", "price_change"]))))
ts = t["timestamp"].cast(pa.int64()).to_numpy() + t["recv_lag_ms"].to_numpy()
order = np.lexsort((t["row_ordinal"].to_numpy(), ts))
t = t.take(pa.array(order)); ts = ts[order]
et = t["event_type"].to_pylist(); aid = t["asset_id"].to_pylist(); pr = t["price"].cast(pa.float64()).to_pylist()
sz = t["size"].cast(pa.float64()).to_pylist(); sd = t["side"].to_pylist(); bids = t["bids"].to_pylist(); asks = t["asks"].to_pylist()
h0 = int(np.datetime64(tag[:13], "h").astype("datetime64[s]").astype("int64")); hend = (h0 + 3600) * 1000; hstart = h0 * 1000
bymk = {}
for slug, e in use.items():
    for m in e["markets"]:
        bymk[m["conditionId"]] = slug
rate = {m["conditionId"]: m["rate"] for e in use.values() for m in e["markets"]}
def top(c):
    b, a = book[c]
    ap = min(a) if a else 1.0
    return ap, (a.get(ap, 0.0) if a else 0.0)
tops = {c: top(c) for c in conds}
def state(slug):
    cost = 0.0; mn = 1e18
    for m in use[slug]["markets"]:
        c = m["conditionId"]; ap, s = tops[c]
        if ap >= 1: return -1.0, 0.0, 0.0
        cost += ap + rate[c] * ap * (1 - ap); mn = min(mn, s)
    return 1 - cost, mn, cost
seq = {slug: [(hstart, ) + state(slug)] for slug in use}   # (ts, net, size, cost)
n = len(et); i = 0
while i < n:
    tsi = ts[i]; touched = set()
    while i < n and ts[i] == tsi:
        k = tokmap.get(int.from_bytes(aid[i], "big")) if aid[i] is not None else None
        if k:
            slug, c, y = k
            if et[i] == "book":
                bk = book[c]
                bk[0] = ingest(None, bids[i], y, True) if y else bk[0]
                if y:
                    bk[1] = ingest(None, asks[i], True, False)
                else:
                    bk[1] = ingest(None, bids[i], False, True); bk[0] = ingest(None, asks[i], False, False)
                touched.add(c)
            elif pr[i] is not None:
                p = pr[i] if y else round(1 - pr[i], 4)
                isbid = (sd[i] == "BUY") == y
                d = book[c][0 if isbid else 1]
                if sz[i] and sz[i] > 0: d[p] = sz[i]
                else: d.pop(p, None)
                touched.add(c)
        i += 1
    for c in touched: tops[c] = top(c)
    for slug in {bymk[c] for c in touched}:
        s = state(slug)
        if s[0] > 1e-9 and s[1] >= 5: s = (s[0], s[1], s[2])
        else: s = (-1.0, 0.0, 0.0) if not (s[0] > 1e-9 and s[1] >= 5) else s
        if (seq[slug][-1][1] > 1e-9) != (s[0] > 1e-9) or s[0] > 1e-9:
            seq[slug].append((int(tsi),) + s)
out = {"tag": tag, "events_used": len(use), "episodes": []}
tot_pos_ms = 0
for slug, sq in seq.items():
    # build piecewise-constant state function
    tt = np.array([x[0] for x in sq]); nn = np.array([x[1] for x in sq]); ss = np.array([x[2] for x in sq])
    pos = nn > 1e-9
    ends = np.append(tt[1:], hend)
    tot_pos_ms += int(((ends - tt)[pos]).clip(min=0).sum())
    k = 0
    while k < len(sq):
        if not pos[k]: k += 1; continue
        s0 = k
        while k + 1 < len(sq) and pos[k + 1]: k += 1
        t0 = tt[s0]; end = ends[k]
        idx = np.searchsorted(tt, t0 + 5000, side="right") - 1 if t0 + 5000 < hend else None
        cont = bool(end > t0 + 5000)
        relax = bool(idx is not None and pos[idx])
        out["episodes"].append({"ev": slug, "t0": int(t0), "dur": float(end - t0) / 1000, "net0": float(nn[s0]), "size0": float(ss[s0]),
                                "cont5": cont, "relax5": relax, "net5": float(nn[idx]) if relax else None,
                                "size5": float(ss[idx]) if relax else None, "cost5": float(sq[idx][3]) if relax else None})
        k += 1
out["pos_share_ms"] = tot_pos_ms
json.dump(out, open(f"{AUD}/b1_{tag}.json", "w"))
E_=1
print(tag, "events", len(use), "episodes", len(out["episodes"]), "cont5", sum(e["cont5"] for e in out["episodes"]), "relax5", sum(e["relax5"] for e in out["episodes"]))
