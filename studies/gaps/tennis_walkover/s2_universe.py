"""Step 2: classes A (moneyline 50-50), B (side market 50-50, moneyline 1/0), control list; Data API confirmation."""
import json, math, collections
from pmlab import dataapi
from common import *


def main():
    A, B, ctrl = [], [], []
    n_ev = n_match = n_mk = 0
    odd = collections.Counter()
    types = collections.Counter()
    for ev in load_events():
        n_ev += 1
        ms = ev.get("markets") or []
        ml = [m for m in ms if m.get("sportsMarketType") == "moneyline"]
        if not ml:
            continue
        n_match += 1
        ml = ml[0]
        rec = {"slug": ev["slug"], "title": ev["title"], "series": ev.get("seriesSlug"), "startTime": ts(ev.get("startTime")),
               "eventClosed": ts(ev.get("closedTime")), "league": (ev.get("eventMetadata") or {}).get("league"),
               "teams": ev.get("teams"), "gameId": ev.get("gameId"), "score": ev.get("score"), "period": ev.get("period"),
               "finished": ts(ev.get("finishedTimestamp")), "markets": []}
        half = []
        for m in ms:
            fp = final_prices(m)
            ct = ts(m.get("closedTime"))
            n_mk += 1
            mm = {"cid": m["conditionId"], "slug": m["slug"], "type": m.get("sportsMarketType"), "outcomes": jf(m.get("outcomes")),
                  "final": fp, "closed": ct, "start": ts(m.get("gameStartTime")), "vol": m.get("volumeNum"), "line": m.get("line"),
                  "q": m.get("question"), "in_period": bool(ct and P0 <= ct <= P1)}
            rec["markets"].append(mm)
            if fp is None:
                odd["no_final"] += 1
            elif fp == (0.5, 0.5):
                if mm["in_period"]:
                    half.append(mm)
                    types[mm["type"]] += 1
            elif set(fp) != {0.0, 1.0}:
                odd[f"other_final {fp}"] += 1
        mlm = next(x for x in rec["markets"] if x["cid"] == ml["conditionId"])
        rec["ml"] = mlm["cid"]
        if mlm["final"] == (0.5, 0.5) and mlm["in_period"]:
            A.append(rec)
        elif half and mlm["final"] is not None and set(mlm["final"]) == {0.0, 1.0}:
            B.append(rec)
        elif half:
            odd["half_side_but_ml_other"] += 1
        if mlm["final"] is not None and set(mlm["final"]) == {0.0, 1.0} and mlm["in_period"] and mlm["vol"] is not None:
            ctrl.append({"slug": ev["slug"], "series": ev.get("seriesSlug"), "cid": mlm["cid"], "outcomes": mlm["outcomes"],
                         "final": mlm["final"], "closed": mlm["closed"], "start": mlm["start"] or rec["startTime"], "vol": mlm["vol"]})
    print("events", n_ev, "match events", n_match, "markets", n_mk)
    print("class A", len(A), "class B", len(B), "control ML 1/0 with volume", len(ctrl))
    print("50-50 markets in period by type", dict(types))
    print("odd", dict(odd))
    print("A by series", collections.Counter(r["series"] for r in A))
    print("B by series", collections.Counter(r["series"] for r in B))
    N = len(ctrl)
    k = math.ceil(N / 3000) if N > 3000 else 1
    samp = [c for c in ctrl if sample_hash(c["cid"]) % k == 0]
    print("control sample k", k, "n", len(samp))

    # Data API confirmation
    ids = [m["cid"] for r in A + B for m in r["markets"]] + [c["cid"] for c in samp]
    res = dataapi.resolutions(ids)
    dis = []
    for r in A + B:
        for m in r["markets"]:
            d = res.get(m["cid"])
            if not d:
                m["api_final"] = None
                dis.append((m["slug"], "missing"))
                continue
            f = tuple(d["final"].get(o) for o in m["outcomes"])
            m["api_final"] = f
            m["api_resolved"] = d["resolved"]
            if m["final"] is not None and tuple(float(x) if x is not None else None for x in f) != m["final"]:
                dis.append((m["slug"], m["final"], f))
    for c in samp:
        d = res.get(c["cid"])
        f = tuple(d["final"].get(o) for o in c["outcomes"]) if d else None
        c["api_final"] = f
        if f is None or tuple(float(x) if x is not None else None for x in f) != c["final"]:
            dis.append((c["slug"], c["final"], f))
    print("disagreements gamma vs data api:", len(dis), dis[:20])
    json.dump({"A": A, "B": B, "control_all_n": N, "k": k, "control": samp}, open(DATA / "universe.json", "w"))


if __name__ == "__main__":
    main()
