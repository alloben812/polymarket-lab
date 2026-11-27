"""Stage 2 (protocol: Book reconstruction, Fill rule, Attacks): full level replay of the candidate events of an hour
(those with a positive price-only interval in stage 1), episodes with size >= 5, reaction R = 1, 2, 5, 10 s.
usage: python3 -I a2_episodes.py <tag> ...   -> data/gaps_negrisk/epi/<tag>.json
"""
import json, os, sys, datetime as dt
import numpy as np, pyarrow as pa, pyarrow.parquet as pq, pyarrow.compute as pc
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import D, families
from a1_scan import closed_before, resolved_no, fee, b2i

FAM = families()
BYSLUG = {(k, e["slug"]): e for k in FAM for e in FAM[k]}
RS = [1, 2, 5, 10]
MINSZ = 5.0


def f(x):
    return float(x) if x is not None else None


def load_rows(tag, conds):
    vs = pa.array([bytes.fromhex(c[2:]) for c in conds], type=pa.binary())
    t = pq.read_table(f"{D}/hours/{tag}.ev.parquet", columns=["event_type", "timestamp", "market", "asset_id", "best_bid",
                      "best_ask", "bids", "asks", "price", "size", "side", "recv_lag_ms", "row_ordinal"])
    t = t.filter(pc.is_in(t["market"], value_set=vs))
    ts = (t["timestamp"].cast(pa.int64()).to_numpy() + t["recv_lag_ms"].to_numpy())
    order = np.lexsort((t["row_ordinal"].to_numpy(), ts))
    t = t.take(pa.array(order)); ts = ts[order]
    o = pq.read_table(f"{D}/hours/{tag}.open.parquet", columns=["market", "asset_id", "bids", "asks", "resolved"])
    o = o.filter(pc.is_in(o["market"], value_set=vs))
    return t, ts, o


class Book:
    __slots__ = ("b", "a")

    def __init__(self):
        self.b, self.a = {}, {}

    def top(self):
        bp = max(self.b) if self.b else 0.0
        ap = min(self.a) if self.a else 1.0
        return bp, (self.b.get(bp, 0.0)), ap, (self.a.get(ap, 0.0))


def set_side(book, levels, is_yes, side_bid):
    d = {}
    for lv in levels or []:
        p, s = float(lv["price"]), float(lv["size"])
        if s > 0:
            d[(p if is_yes else round(1 - p, 6))] = s
    if is_yes == side_bid:
        book.b = d
    else:
        book.a = d


def run(tag):
    h0 = int(dt.datetime.strptime(tag, "%Y-%m-%dT%H").replace(tzinfo=dt.timezone.utc).timestamp())
    hend = (h0 + 3600) * 1000
    sc = json.load(open(f"{D}/scan/{tag}.json"))
    cands = {}
    for fam, k in [("B1", "B"), ("B2", "B"), ("C1", "C1"), ("C2", "C2")]:
        for it in sc[fam]:
            key = (k, it["ev"])
            cands.setdefault(key, {"fams": set(), "pairs": set()})
            cands[key]["fams"].add(fam)
            if fam in ("C1", "C2"):
                cands[key]["pairs"].add((it["bid_m"], it["ask_m"]))
    out = {"tag": tag, "episodes": []}
    if not cands:
        json.dump(out, open(f"{D}/epi/{tag}.json", "w")); return
    conds_all = sorted({m["conditionId"] for key in cands for m in BYSLUG[key]["markets"]})
    t, TS, o = load_rows(tag, conds_all)
    tok = {}
    for key in cands:
        for m in BYSLUG[key]["markets"]:
            tok[int(m["yes"])] = (m["conditionId"], True); tok[int(m["no"])] = (m["conditionId"], False)
    books = {c: Book() for c in conds_all}
    resolved = set()
    for a, bids, asks, r in zip(o["asset_id"].to_pylist(), o["bids"].to_pylist(), o["asks"].to_pylist(), o["resolved"].to_pylist()):
        k = tok.get(b2i(a))
        if not k:
            continue
        c, y = k
        if r:
            resolved.add(c)
        if y or not (books[c].b or books[c].a):
            set_side(books[c], bids, y, True); set_side(books[c], asks, y, False)
    et = t["event_type"].to_pylist(); mk = [None] * len(et)
    aid = t["asset_id"].to_pylist(); bb = t["best_bid"].cast(pa.float64()).to_pylist(); ba = t["best_ask"].cast(pa.float64()).to_pylist()
    bids = t["bids"].to_pylist(); asks = t["asks"].to_pylist(); pr = t["price"].cast(pa.float64()).to_pylist()
    sz = t["size"].cast(pa.float64()).to_pylist(); sd = t["side"].to_pylist()
    # event definitions
    evs = []
    for key, cd in cands.items():
        e = BYSLUG[key]
        live = [m for m in e["markets"] if not closed_before(m, h0) and m["conditionId"] not in resolved]
        dead = [m for m in e["markets"] if m not in live]
        rate = {m["conditionId"]: m["rate"] for m in live}
        if key[0] == "B":
            if "B1" in cd["fams"] and not e.get("negRiskAugmented") and all(resolved_no(m) for m in dead):
                evs.append(("B1", e["slug"], [m["conditionId"] for m in live], rate, None))
            if "B2" in cd["fams"]:
                evs.append(("B2", e["slug"], [m["conditionId"] for m in live], rate, None))
        else:
            for (bm, am) in cd["pairs"]:
                evs.append((key[0], e["slug"], [bm, am], rate, (bm, am)))
    bymk = {}
    for i, ev in enumerate(evs):
        for c in ev[2]:
            bymk.setdefault(c, []).append(i)
    tops = {c: books[c].top() for c in conds_all}
    rep = {}  # last reported (exchange field) YES-space best per market
    trades = {c: [] for c in conds_all}

    def state(ev):
        fam, slug, cs, rate, pair = ev
        if fam == "B1":
            if any(tops[c][2] >= 1 for c in cs):
                return None
            cost = sum(tops[c][2] + fee(tops[c][2], rate[c]) for c in cs)
            return 1 - cost, min(tops[c][3] for c in cs), cost, [tops[c][2] for c in cs]
        if fam == "B2":
            legs = [c for c in cs if tops[c][0] > 0]
            if len(legs) < 2:
                return None
            net = sum(tops[c][0] - fee(tops[c][0], rate[c]) for c in legs) - 1
            cost = sum(1 - tops[c][0] + fee(tops[c][0], rate[c]) for c in legs)
            return net, min(tops[c][1] for c in legs), cost, [tops[c][0] for c in legs]
        bm, am = pair
        b, a = tops[bm][0], tops[am][2]
        if b <= 0 or a >= 1:
            return None
        net = b - a - fee(a, rate[am]) - fee(1 - b, rate[bm])
        cost = a + fee(a, rate[am]) + (1 - b) + fee(1 - b, rate[bm])
        return net, min(tops[bm][1], tops[am][3]), cost, [b, a]

    seqs = [[] for _ in evs]  # (ts, net, size, cost, legs, trigger_market)
    n = len(et); i = 0
    while i < n:
        tsi = TS[i]; touched = set()
        while i < n and TS[i] == tsi:
            k = tok.get(b2i(aid[i])) if aid[i] is not None else None
            if k:
                c, y = k; e_ = et[i]
                if e_ == "book":
                    set_side(books[c], bids[i], y, True); set_side(books[c], asks[i], y, False); touched.add(c)
                elif e_ == "price_change" and pr[i] is not None:
                    p = pr[i] if y else round(1 - pr[i], 6)
                    isbid = (sd[i] == "BUY") == y
                    d = books[c].b if isbid else books[c].a
                    if sz[i] and sz[i] > 0:
                        d[p] = sz[i]
                    else:
                        d.pop(p, None)
                    touched.add(c)
                elif e_ == "last_trade_price" and pr[i] is not None:
                    trades[c].append((int(tsi), pr[i] if y else round(1 - pr[i], 6), sz[i]))
                if e_ in ("price_change", "best_bid_ask") and bb[i] is not None and ba[i] is not None:
                    rep[c] = (bb[i], ba[i]) if y else (1 - ba[i], 1 - bb[i])
            i += 1
        evset = set()
        for c in touched:
            tops[c] = books[c].top(); evset.update(bymk.get(c, []))
        for j in evset:
            st = state(evs[j])
            trig = [c for c in touched if c in evs[j][2]]
            if st is None:
                st = (-1.0, 0.0, 0.0, [])
            ok = st[0] > 1e-9 and st[1] >= MINSZ
            sq = seqs[j]
            if sq and sq[-1][6] == ok and not ok:
                continue
            mism = 0
            if ok:
                for c in evs[j][2]:
                    r_ = rep.get(c)
                    if r_ and (abs(r_[0] - tops[c][0]) > 1e-6 or abs(r_[1] - tops[c][2]) > 1e-6):
                        mism += 1
            sq.append((int(tsi), st[0], st[1], st[2], st[3], trig, ok, mism))
    # episodes
    for j, ev in enumerate(evs):
        sq = seqs[j]
        k = 0
        while k < len(sq):
            if not sq[k][6]:
                k += 1; continue
            s0 = k
            while k + 1 < len(sq) and sq[k + 1][6]:
                k += 1
            t0 = sq[s0][0]; end = sq[k + 1][0] if k + 1 < len(sq) else hend
            cens = k + 1 >= len(sq)
            seg = sq[s0:k + 1]
            rec = {"fam": ev[0], "ev": ev[1], "pair": ev[4], "n_legs": len(ev[2]), "t0": t0, "t1": end, "dur": (end - t0) / 1000,
                   "cens": cens, "net0": seg[0][1], "size0": seg[0][2], "cost0": seg[0][3], "legs0": seg[0][4],
                   "trig_start": seg[0][5], "trig_end": sq[k + 1][5] if not cens else None, "mism0": seg[0][7],
                   "max_net": max(x[1] for x in seg)}
            for R in RS:
                tR = t0 + R * 1000
                if end <= tR:
                    rec[f"R{R}"] = None; continue
                st = [x for x in seg if x[0] <= tR][-1]
                r = {"net": st[1], "size": st[2], "cost": st[3]}
                for S in (5, 20):
                    sets = min(st[2], np.floor(S / st[3])) if st[3] > 0 else 0
                    r[f"pnl{S}"] = float(sets * st[1]) if sets >= MINSZ else 0.0
                    r[f"sets{S}"] = float(sets)
                rec[f"R{R}"] = r
            # attack 2: prints on any leg at the quoted leg price during the episode
            legs_c = ev[2] if ev[0] != "B2" else [c for c in ev[2] if tops.get(c) is not None]
            nprint = 0
            for c in legs_c:
                for (tt, p, s) in trades[c]:
                    if t0 <= tt <= end:
                        nprint += 1
            rec["prints"] = nprint
            out["episodes"].append(rec)
            k += 1
    os.makedirs(f"{D}/epi", exist_ok=True)
    json.dump(out, open(f"{D}/epi/{tag}.json", "w"))
    print(tag, "cands", len(cands), "evs", len(evs), "episodes", len(out["episodes"]),
          "R5", sum(1 for x in out["episodes"] if x.get("R5")), flush=True)


if __name__ == "__main__":
    os.makedirs(f"{D}/epi", exist_ok=True)
    for tag in sys.argv[1:]:
        run(tag)
