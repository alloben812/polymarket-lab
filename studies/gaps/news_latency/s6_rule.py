"""Step 6: the pre-registered rule, four delays (protocol section 6). Writes out/rule.json (one row per jump x delay)
and out/fills.json. Usage: s6_rule.py [N]  -> only the first N jumps by t0 (sanity slice)."""
import json, sys
from pmlab import fees
from common import *
from s4_jumps import load_tape
from s5_measure import offer_price

DELAYS = [10, 30, 120, 600]
BUDGET, WINDOW, PMAX = 200.0, 600, 0.90


def run_rule(j, tape, d):
    fi = 0 if j["dir"] > 0 else 1
    a, b = j["t0_block"] + d, j["t0_block"] + d + WINDOW
    spent = shares = fee = 0.0
    fills = []
    for r in tape:
        if r["t"] < a:
            continue
        if r["t"] > b or spent >= BUDGET - 1e-9:
            break
        p = offer_price(r, fi)
        if p is None or p > PMAX or p <= 0:
            continue
        q = min(r["z"], (BUDGET - spent) / p)
        if q <= 0:
            continue
        spent += q * p
        shares += q
        f = fees.fee_per_share(p, j["fee_rate"]) * q
        fee += f
        fills.append({"c": j["c"], "d": d, "t": r["t"], "dt": r["t"] - j["t0_block"], "p": p, "q": q, "fee": f})
    return spent, shares, fee, fills


def main():
    jumps = [j for j in json.load(open(OUT / "jumps.json")) if j["status"] in ("main", "R")]
    jumps.sort(key=lambda j: j["t0"])
    tag = ""
    if len(sys.argv) > 1:
        jumps = jumps[:int(sys.argv[1])]
        tag = "_slice"
    rows, allf = [], []
    for j in jumps:
        tape = load_tape(j["c"])
        payoff = j["settle_f"] if j["resolved"] else j["mark_f"]
        for d in DELAYS:
            spent, shares, fee, fills = run_rule(j, tape, d)
            net = shares * payoff - spent - fee if shares else 0.0
            rows.append({"c": j["c"], "t0": j["t0"], "d": d, "spent": spent, "shares": shares, "fee": fee, "payoff": payoff,
                         "resolved": j["resolved"], "net": net, "avg_p": spent / shares if shares else None, "n_fills": len(fills)})
            for f in fills:
                f["payoff"] = payoff
                f["resolved"] = j["resolved"]
            allf.extend(fills)
    json.dump(rows, open(OUT / f"rule{tag}.json", "w"))
    json.dump(allf, open(OUT / f"fills{tag}.json", "w"))
    print("jumps", len(jumps), "rows", len(rows), "fills", len(allf))


if __name__ == "__main__":
    main()
