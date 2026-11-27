"""Stage 1 (vectorised): per hour, YES-space top-of-book prices of every universe market from the exchange's own
best_bid/best_ask fields; per event/ladder the net per set of B1, B2, C1, C2 at every state; flags (event, hour)
with any positive net (prices only, no size). Also A1 on rows where both tokens print at the same ms.
usage: python3 -I a1_scan.py <tag> ...   -> data/gaps_negrisk/scan/<tag>.json
"""
import json, os, sys, datetime as dt
import numpy as np, pandas as pd, pyarrow.parquet as pq, pyarrow.compute as pc
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import D, families, jl

FAM = families()


def tokmap():
    m = {}
    for k in FAM:
        for e in FAM[k]:
            for x in e["markets"]:
                m[int(x["yes"])] = (x["conditionId"], 1)
                m[int(x["no"])] = (x["conditionId"], 0)
    return m


TOK = tokmap()


def b2i(b):
    return int.from_bytes(b, "big")


def load_top(tag):
    import pyarrow as pa
    t = pq.read_table(f"{D}/hours/{tag}.ev.parquet", columns=["event_type", "timestamp", "asset_id", "best_bid",
                      "best_ask", "recv_lag_ms", "row_ordinal"])
    t = t.filter(pc.is_in(t["event_type"], value_set=pa.array(["price_change", "best_bid_ask"])))
    t = t.filter(pc.and_(pc.is_valid(t["best_bid"]), pc.is_valid(t["best_ask"])))
    da = pc.dictionary_encode(t["asset_id"]).combine_chunks()
    keys = [TOK.get(b2i(a)) for a in da.dictionary.to_pylist()]
    ci = np.array([(-1 if k is None else 0) for k in keys])
    conds = np.array([k[0] if k else None for k in keys], dtype=object)
    isy = np.array([k[1] if k else -1 for k in keys])
    ind = da.indices.to_numpy()
    df = pd.DataFrame({
        "ts": t["timestamp"].cast(pa.int64()).to_numpy() + t["recv_lag_ms"].to_numpy(),
        "timestamp": t["timestamp"].cast(pa.int64()).to_numpy(),
        "row_ordinal": t["row_ordinal"].to_numpy(),
        "cond": conds[ind], "isyes": isy[ind],
        "bb": t["best_bid"].cast(pa.float64()).to_numpy(), "ba": t["best_ask"].cast(pa.float64()).to_numpy()})
    df = df[df.isyes >= 0]
    y = df.isyes.values == 1
    df["yb"] = np.where(y, df.bb.values, 1 - df.ba.values); df["ya"] = np.where(y, df.ba.values, 1 - df.bb.values)
    return df[["ts", "row_ordinal", "cond", "isyes", "yb", "ya", "timestamp"]]


def load_open(tag):
    import pyarrow as pa
    o = pq.read_table(f"{D}/hours/{tag}.open.parquet", columns=["asset_id", "best_bid", "best_ask", "resolved"])
    o = pa.table({"asset_id": o["asset_id"], "best_bid": o["best_bid"].cast(pa.float64()),
                  "best_ask": o["best_ask"].cast(pa.float64()), "resolved": o["resolved"]}).to_pandas()
    res = {}
    for a, bb, ba, r in zip(o.asset_id, o.best_bid, o.best_ask, o.resolved):
        k = TOK.get(b2i(a))
        if not k:
            continue
        c, y = k
        bb = 0.0 if pd.isna(bb) else float(bb); ba = 1.0 if pd.isna(ba) else float(ba)
        if y == 1 or c not in res:
            res[c] = (bb, ba, bool(r)) if y == 1 else (1 - ba, 1 - bb, bool(r))
    return res


def fee(p, r):
    return r * p * (1 - p)


def closed_before(m, h0):
    ct = m.get("closedTime")
    if not ct or not m.get("closed"):
        return False
    try:
        t = pd.Timestamp(ct.replace(" ", "T"))
        t = t.tz_localize("UTC") if t.tzinfo is None else t
        return t.timestamp() < h0
    except Exception:
        return False


def resolved_no(m):
    p = jl(m.get("outcomePrices"))
    return bool(p) and str(p[0]) in ("0", "0.0")


GIDX = {}


def grid(df, conds, op, h0):
    """time x market matrices of yb, ya (YES space), forward filled from the opening state."""
    ii = [GIDX[c] for c in conds if c in GIDX]
    sub = df.iloc[np.concatenate(ii)] if ii else df.iloc[:0]
    idx = {c: i for i, c in enumerate(conds)}
    init = pd.DataFrame({"ts": h0 * 1000 - 1, "row_ordinal": -1, "cond": conds,
                         "yb": [op.get(c, (0.0, 1.0, False))[0] for c in conds],
                         "ya": [op.get(c, (0.0, 1.0, False))[1] for c in conds]})
    sub = pd.concat([init, sub[["ts", "row_ordinal", "cond", "yb", "ya"]]]).sort_values(["ts", "row_ordinal"], kind="stable")
    sub = sub.groupby(["ts", "cond"], sort=True).last().reset_index()
    YB = sub.pivot(index="ts", columns="cond", values="yb").reindex(columns=conds).ffill()
    YA = sub.pivot(index="ts", columns="cond", values="ya").reindex(columns=conds).ffill()
    return YB.index.values, YB.values, YA.values


def intervals(ts, pos, hend):
    out = []
    i = 0; n = len(pos)
    while i < n:
        if pos[i]:
            j = i
            while j + 1 < n and pos[j + 1]:
                j += 1
            end = ts[j + 1] if j + 1 < n else hend
            out.append((int(ts[i]), int(end), j + 1 >= n))
            i = j + 1
        else:
            i += 1
    return out


def scan(tag):
    h0 = int(dt.datetime.strptime(tag, "%Y-%m-%dT%H").replace(tzinfo=dt.timezone.utc).timestamp())
    hend = (h0 + 3600) * 1000
    df = load_top(tag); op = load_open(tag)
    GIDX.clear(); GIDX.update(df.groupby("cond").indices)
    res = {"tag": tag, "rows": int(len(df)), "B1": [], "B2": [], "C1": [], "C2": [], "A1": {}, "n_events": {}}
    # A1: both tokens' rows at the same exchange ms
    g = df.groupby(["cond", "timestamp"]).isyes.nunique()
    both = g[g == 2].index
    if len(both):
        s = df.set_index(["cond", "timestamp"]).loc[both].reset_index()
        last = s.groupby(["cond", "timestamp", "isyes"])[["yb", "ya"]].last().unstack("isyes")
        # YES-space of each token: YES ask + NO ask = ya_yes + (1 - yb_from_no)
        ask_sum = last[("ya", 1)] + (1 - last[("yb", 0)])
        bid_sum = last[("yb", 1)] + (1 - last[("ya", 0)])
        res["A1"] = {"pairs": int(len(last)), "ask_sum_lt1": int((ask_sum < 1 - 1e-9).sum()),
                     "bid_sum_gt1": int((bid_sum > 1 + 1e-9).sum()), "ask_sum_min": float(ask_sum.min()),
                     "bid_sum_max": float(bid_sum.max())}
    for fam in ["B", "C1", "C2"]:
        ne = 0
        for e in FAM[fam]:
            ms = e["markets"]
            live = [m for m in ms if not closed_before(m, h0) and not op.get(m["conditionId"], (0, 1, False))[2]]
            dead = [m for m in ms if m not in live]
            if len(live) < 2 or not any(m["conditionId"] in op or m["conditionId"] in set() for m in live):
                continue
            conds = [m["conditionId"] for m in live]
            if not (any(c in GIDX for c in conds) or any(c in op for c in conds)):
                continue
            ne += 1
            r = np.array([m["rate"] for m in live])
            ts, YB, YA = grid(df, conds, op, h0)
            YB = np.nan_to_num(YB, nan=0.0); YA = np.nan_to_num(YA, nan=1.0)
            if fam == "B":
                ok_b1 = (not e.get("negRiskAugmented")) and all(resolved_no(m) for m in dead)
                if ok_b1:
                    has = (YA < 1).all(axis=1)
                    net1 = 1 - (YA + fee(YA, r)).sum(axis=1)
                    pos = has & (net1 > 1e-9)
                    for a, b, cen in intervals(ts, pos, hend):
                        k = (ts >= a) & (ts < b)
                        res["B1"].append({"ev": e["slug"], "n": len(live), "t0": a, "t1": b, "cens": cen,
                                          "max_net": float(net1[k].max())})
                leg = YB > 0
                net2 = (np.where(leg, YB - fee(YB, r), 0)).sum(axis=1) - 1
                pos = (leg.sum(axis=1) >= 2) & (net2 > 1e-9)
                for a, b, cen in intervals(ts, pos, hend):
                    k = (ts >= a) & (ts < b)
                    res["B2"].append({"ev": e["slug"], "n": len(live), "aug": bool(e.get("negRiskAugmented")),
                                      "t0": a, "t1": b, "cens": cen, "max_net": float(net2[k].max())})
            else:
                key = (lambda m: m["K"]) if fam == "C1" else (lambda m: m["endDate"])
                order = sorted(range(len(live)), key=lambda i: key(live[i]))
                for ii, i in enumerate(order):
                    for j in order[ii + 1:]:
                        # C1: lo=i (lower K), hi=j: need bid(hi) > ask(lo); C2: early=i, late=j: need bid(early) > ask(late)
                        if fam == "C1":
                            bidx, askx = j, i
                        else:
                            bidx, askx = i, j
                        bb, aa = YB[:, bidx], YA[:, askx]
                        net = bb - aa - fee(aa, r[askx]) - fee(1 - bb, r[bidx])
                        pos = (bb > 0) & (aa < 1) & (net > 1e-9)
                        for a, b, cen in intervals(ts, pos, hend):
                            k = (ts >= a) & (ts < b)
                            res[fam].append({"ev": e["slug"], "bid_m": conds[bidx], "ask_m": conds[askx],
                                             "t0": a, "t1": b, "cens": cen, "max_net": float(net[k].max())})
        res["n_events"][fam] = ne
    os.makedirs(f"{D}/scan", exist_ok=True)
    json.dump(res, open(f"{D}/scan/{tag}.json", "w"))
    print(tag, "rows", res["rows"], "events", res["n_events"], {k: len(res[k]) for k in ["B1", "B2", "C1", "C2"]},
          "A1", res["A1"], flush=True)


if __name__ == "__main__":
    for tag in sys.argv[1:]:
        scan(tag)
