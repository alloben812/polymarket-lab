"""Step 5: speed of absorption, dollars per time bucket, first-10-second wallets (protocol section 5).
Reads out/jumps.json (main and R) and the tapes; writes out/measure.json. No rule P&L here."""
import collections, json
from common import *
from s4_jumps import load_tape

BUCKETS = [(0, 10), (10, 30), (30, 120), (120, 600), (600, 7200)]


def offer_price(r, fi):
    """F-price at which F was on offer when this row matched, or None when the row shows a bid for F instead."""
    if r["s"] == "BUY" and r["i"] == fi:
        return r["p"]
    if r["s"] == "SELL" and r["i"] != fi:
        return 1 - r["p"]
    return None


def fprice(r, fi):
    return r["p"] if r["i"] == fi else 1 - r["p"]


def measure(j, tape):
    fi = 0 if j["dir"] > 0 else 1
    t0b = j["t0_block"]
    k0 = next(k for k, r in enumerate(tape) if r["t"] == t0b and fprice(r, fi) >= j["pf_pre"] + 0.10)
    move = j["p10"] - j["pf_pre"]
    out = {"c": j["c"], "t0": j["t0"], "move": move}
    for name, lvl, horizon in (("t50", j["pf_pre"] + 0.5 * move, 86400), ("t90", j["pf_pre"] + 0.9 * move, 86400), ("t95", 0.95, 86400)):
        out[name] = next((r["t"] - t0b for r in tape[k0:] if r["t"] <= t0b + horizon and fprice(r, fi) >= lvl), None)
    bk = []
    for a, b in BUCKETS:
        rows = [r for r in tape[k0:] if t0b + a <= r["t"] < t0b + b]
        usd = sum(r["z"] * r["p"] for r in rows)
        off = [(offer_price(r, fi), r["z"]) for r in rows]
        off = [(p, z) for p, z in off if p is not None]
        ousd = sum(p * z for p, z in off)
        osh = sum(z for p, z in off)
        o90 = sum(p * z for p, z in off if p <= 0.90)
        o90sh = sum(z for p, z in off if p <= 0.90)
        bk.append({"a": a, "b": b, "n": len(rows), "usd": usd, "buy_usd": ousd, "buy_vwap": ousd / osh if osh else None,
                   "buy90_usd": o90, "buy90_vwap": o90 / o90sh if o90sh else None,
                   "profit_vs_1": sum((1 - p) * z for p, z in off)})
    out["buckets"] = bk
    w = collections.Counter()
    for r in tape[k0:]:
        if r["t"] >= t0b + 10:
            break
        p = offer_price(r, fi)
        if p is not None:
            w[r["w"]] += p * r["z"]
    tot = sum(w.values())
    out["first10"] = {"n_wallets": len(w), "usd": tot, "top3_share": (sum(v for _, v in w.most_common(3)) / tot) if tot else None,
                      "wallets": dict(w.most_common(20))}
    # last quote-side price just before t0 on the tape (what a resting order would have been run over at)
    return out


def main():
    jumps = [j for j in json.load(open(OUT / "jumps.json")) if j["status"] in ("main", "R")]
    res = []
    for j in jumps:
        res.append(measure(j, load_tape(j["c"])))
    json.dump(res, open(OUT / "measure.json", "w"))
    print("measured", len(res))


if __name__ == "__main__":
    main()
