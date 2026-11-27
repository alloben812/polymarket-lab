"""Diagnostic (not a variant): how often does the level replay agree with the exchange's own best_bid/best_ask field
on price_change rows? Run on the markets of the B-family events of one hour.
usage: python3 -I d1_replaycheck.py <tag> [max_events]
"""
import sys, os, collections
import pyarrow as pa
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from a2_episodes import load_rows, Book, set_side, FAM, b2i


def main(tag, nmax=60):
    evs = FAM["B"][:nmax]
    conds = sorted({m["conditionId"] for e in evs for m in e["markets"]})
    tok = {}
    for e in evs:
        for m in e["markets"]:
            tok[int(m["yes"])] = (m["conditionId"], True); tok[int(m["no"])] = (m["conditionId"], False)
    t, TS, o = load_rows(tag, conds)
    books = {c: Book() for c in conds}
    for a, bids, asks in zip(o["asset_id"].to_pylist(), o["bids"].to_pylist(), o["asks"].to_pylist()):
        k = tok.get(b2i(a))
        if k and (k[1] or not (books[k[0]].b or books[k[0]].a)):
            set_side(books[k[0]], bids, k[1], True); set_side(books[k[0]], asks, k[1], False)
    et = t["event_type"].to_pylist(); aid = t["asset_id"].to_pylist()
    bb = t["best_bid"].cast(pa.float64()).to_pylist(); ba = t["best_ask"].cast(pa.float64()).to_pylist()
    bids = t["bids"].to_pylist(); asks = t["asks"].to_pylist(); pr = t["price"].cast(pa.float64()).to_pylist()
    sz = t["size"].cast(pa.float64()).to_pylist(); sd = t["side"].to_pylist()
    c_ = collections.Counter()
    for i in range(len(et)):
        if aid[i] is None:
            continue
        k = tok.get(b2i(aid[i]))
        if not k:
            continue
        c, y = k
        if et[i] == "book":
            set_side(books[c], bids[i], y, True); set_side(books[c], asks[i], y, False)
        elif et[i] == "price_change" and pr[i] is not None:
            p = pr[i] if y else round(1 - pr[i], 6)
            isbid = (sd[i] == "BUY") == y
            d = books[c].b if isbid else books[c].a
            if sz[i] and sz[i] > 0:
                d[p] = sz[i]
            else:
                d.pop(p, None)
        if et[i] in ("price_change", "best_bid_ask") and bb[i] is not None:
            yb, ya = (bb[i], ba[i]) if y else (1 - ba[i], 1 - bb[i])
            tb, _, ta, _ = books[c].top()
            ok = abs(tb - yb) < 1e-6 and abs(ta - ya) < 1e-6
            c_[(et[i], "yes" if y else "no", ok)] += 1
    for k in sorted(c_):
        print(k, c_[k])


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 60)
