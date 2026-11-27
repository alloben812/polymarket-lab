"""Step 4: time each candidate on the tape, confirm it, test the 2-hour hold, attach settlement (protocol section 3)."""
import bisect, collections, gzip, json
from pmlab import dataapi
from common import *

LAG = 3


def load_tape(cid):
    path = TAPES / f"{cid}.jsonl.gz"
    if not path.exists():
        return None
    with gzip.open(path, "rt") as f:
        return [json.loads(l) for l in f]


def load_ph(cid):
    d = json.load(gzip.open(PH / f"{cid}.json.gz", "rt"))
    return {60: d["p60"], 300: d["p300"], 1800: d["p1800"]}


def price_at_or_after(ph, t):
    """Finest-bucket YES point with timestamp in [t, t + 2 buckets]."""
    for b in (60, 300, 1800):
        pts = ph[b]
        k = bisect.bisect_left(pts, [t, -1])
        if k < len(pts) and pts[k][0] <= t + 2 * b:
            return pts[k][1], b
    return None, None


def main():
    cands = json.load(open(OUT / "candidates.json"))
    mk = {m["conditionId"]: m for m in universe()}
    res = dataapi.resolutions(sorted({c["c"] for c in cands}))
    json.dump(res, open(OUT / "resolutions.json", "w"))
    out, drop = [], collections.Counter()
    for c in cands:
        m = mk[c["c"]]
        tape = load_tape(c["c"])
        if tape is None:
            drop["no tape file"] += 1
            continue
        d = 1 if c["p_post"] > c["p_pre"] else -1
        pf_pre = c["p_pre"] if d > 0 else 1 - c["p_pre"]

        def pf(r):
            y = r["p"] if r["i"] == 0 else 1 - r["p"]
            return y if d > 0 else 1 - y

        lo, hi = c["T_pre"] - 5 + LAG, c["T_post"] + c["bucket"] + LAG
        k0 = next((k for k, r in enumerate(tape) if lo <= r["t"] <= hi and pf(r) >= pf_pre + 0.10), None)
        if k0 is None:
            drop["no tape jump"] += 1
            continue
        t0b = tape[k0]["t"]
        last10 = None
        for r in tape[k0:]:
            if r["t"] > t0b + 600:
                break
            last10 = r
        p10 = pf(last10)
        rec = {"c": c["c"], "slug": m["slug"], "question": m["question"], "event": (m["events"] or [{}])[0].get("slug"),
               "tags": m["tags"], "cat": category(m), "fee_rate": fee_rate(m), "feeType": m.get("feeType"),
               "dir": d, "pf_pre": round(pf_pre, 4), "T_pre": c["T_pre"], "bucket": c["bucket"], "t0_block": t0b, "t0": t0b - LAG,
               "t0_iso": iso(t0b - LAG), "p_first": round(pf(tape[k0]), 4), "p10": round(p10, 4), "volumeNum": m["volumeNum"],
               "endDate": m.get("endDate"), "closedTime": m.get("closedTime"), "closed": m.get("closed"), "negRisk": m.get("negRisk")}
        prev = next((r for r in reversed(tape[:k0]) if r["t"] >= t0b - 86400), None)
        rec["p_tape_pre"] = None if prev is None else round(pf(prev), 4)
        rec["tape_pre_age"] = None if prev is None else t0b - prev["t"]
        if p10 - pf_pre < 0.40:
            drop["not confirmed on tape"] += 1
            rec["status"] = "unconfirmed"
            out.append(rec)
            continue
        if prev is not None and p10 - pf(prev) < 0.25:
            drop["pre-price artefact"] += 1
            rec["status"] = "artefact"
            out.append(rec)
            continue
        ph = load_ph(c["c"])
        y2, b2 = price_at_or_after(ph, t0b - LAG + 7200)
        r = res.get(c["c"]) or {}
        o_yes, o_no = outcomes(m)
        fin = r.get("final") or {}
        settle_yes = None
        if r.get("resolved") and fin.get(o_yes) is not None:
            settle_yes = float(fin[o_yes])
        mark_yes = None
        try:
            mark_yes = float(json.loads(m["outcomePrices"])[0])
        except Exception:  # noqa: BLE001
            pass
        ct = parse_time(m.get("closedTime")) if m.get("closed") else None
        if y2 is None:
            if settle_yes is not None and ct is not None and ct <= t0b + 7200 + 3600:
                y2, b2 = settle_yes, "settled"
            else:
                # no price point: last tape print at or before t0 + 2 h
                lastp = None
                for rr in tape[k0:]:
                    if rr["t"] > t0b + 7200:
                        break
                    lastp = rr
                y2, b2 = ((lastp["p"] if lastp["i"] == 0 else 1 - lastp["p"]), "tape")
        p2h = y2 if d > 0 else 1 - y2
        rec.update({"p2h": round(p2h, 4), "p2h_src": b2,
                    "settle_f": None if settle_yes is None else (settle_yes if d > 0 else 1 - settle_yes),
                    "mark_f": None if mark_yes is None else (mark_yes if d > 0 else 1 - mark_yes),
                    "resolved": settle_yes is not None})
        rec["status"] = "main" if p2h - pf_pre >= 0.5 * (p10 - pf_pre) else "R"
        out.append(rec)
    out.sort(key=lambda r: r["t0"])
    # news clusters: same gamma event, t0 within 30 minutes (single linkage)
    last = {}
    n = 0
    for r in out:
        if r["status"] in ("unconfirmed", "artefact"):
            continue
        key = r["event"] or r["c"]
        if key in last and r["t0"] - last[key][0] <= 1800:
            r["cluster"] = last[key][1]
        else:
            n += 1
            r["cluster"] = n
        last[key] = (r["t0"], r["cluster"])
    json.dump(out, open(OUT / "jumps.json", "w"), indent=0)
    print("candidates", len(cands), "dropped", dict(drop))
    print("status", collections.Counter(r["status"] for r in out))
    ok = [r for r in out if r["status"] in ("main", "R")]
    print("clusters", len({r["cluster"] for r in ok}), "markets", len({r["c"] for r in ok}))
    print("resolved", collections.Counter((r["status"], r["resolved"]) for r in ok))
    print("p2h source", collections.Counter(str(r["p2h_src"]) for r in ok))


if __name__ == "__main__":
    main()
