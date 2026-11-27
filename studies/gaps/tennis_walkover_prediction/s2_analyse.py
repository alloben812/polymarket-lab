"""Step 2: protocol 5-8 on data/gaps_tennis_wo_pred/trades.json. Prints every table to stdout (saved to out/)."""
from __future__ import annotations

import collections
import datetime as dt
import json
import math
from pathlib import Path

ROWS = json.load(open("/home/user/polymarket-lab/data/gaps_tennis_wo_pred/trades.json"))
FEE = 0.05
CUT = dt.datetime(2026, 10, 26, 13, 35, tzinfo=dt.timezone.utc).timestamp()
P0 = dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc).timestamp()
P1 = dt.datetime(2026, 11, 25, 23, 59, 59, tzinfo=dt.timezone.utc).timestamp()
DAYS = {"early": (CUT - P0) / 86400, "late": (P1 - CUT) / 86400, "all": (P1 - P0) / 86400}
FEATS = ["itf", "doubles", "short_rest", "long_prev", "recent_ret", "double_duty", "wo_history"]
SIZES = [5, 10, 20]


def fee(p):
    return FEE * p * (1 - p)


EL = [r for r in ROWS if r["elig"]]
for r in EL:
    r["part"] = "early" if r["closed"] < CUT else "late"
    r["e"] = r["pay"] - r["p"] - fee(r["p"])
    r["g"] = r["pay"] - r["p"]
    r["wo"] = r["cls"] == "A"
    r["day"] = dt.datetime.fromtimestamp(r["start"], dt.timezone.utc).strftime("%Y-%m-%d")


def wmean(rs, key, cluster=None):
    W = sum(r["w"] for r in rs)
    if W == 0:
        return float("nan"), float("nan")
    m = sum(r["w"] * key(r) for r in rs) / W
    if cluster is None:
        se = math.sqrt(sum((r["w"] * (key(r) - m)) ** 2 for r in rs)) / W
    else:
        g = collections.defaultdict(float)
        for r in rs:
            g[cluster(r)] += r["w"] * (key(r) - m)
        se = math.sqrt(sum(v * v for v in g.values())) / W
    return m, se


def summary(rs, part, label, maker=False):
    if not rs:
        return f"{label:28s} {part:5s} n=0"
    n = len(rs)
    W = sum(r["w"] for r in rs)
    nwo = sum(r["wo"] for r in rs)
    q = sum(r["w"] * r["wo"] for r in rs) / W
    mp = sum(r["w"] * r["p"] for r in rs) / W
    m, se = wmean(rs, lambda r: r["e"])
    md, sed = wmean(rs, lambda r: r["e"], cluster=lambda r: r["day"])
    out = [f"{label:28s} {part:5s} n={n:4d} wN={W:6.0f} wo={nwo:3d} q={q*100:4.1f}% p={mp:.3f} "
           f"edge/sh={m*100:+.2f}c [{(m-1.96*se)*100:+.2f},{(m+1.96*se)*100:+.2f}] t={m/se if se else 0:+.2f} (day-cl t={md/sed if sed else 0:+.2f})"]
    days = DAYS[part]
    per_week = W / days * 7
    sz = []
    for S in SIZES:
        q_sh = [min(r["z"], S / (r["p"] + fee(r["p"]))) for r in rs]
        usd = sum(r["w"] * qq * (r["p"] + fee(r["p"])) for r, qq in zip(rs, q_sh)) / W
        net = sum(r["w"] * qq * r["e"] for r, qq in zip(rs, q_sh)) / W
        full = sum(r["w"] for r, qq in zip(rs, q_sh) if qq * (r["p"] + fee(r["p"])) >= S - 1e-6) / W
        sz.append(f"${S}: fill ${usd:.2f} (full {full*100:.0f}%) net/trade ${net:+.3f} -> ${net*W/days:+.2f}/day")
    out.append(f"{'':34s}trades/week {per_week:6.1f} | " + " | ".join(sz))
    return "\n".join(out)


def maker_summary(rs, part, label):
    lines = []
    for kind in ("mk_thr_z", "mk_at_z"):
        W = sum(r["w"] for r in rs)
        filled = [r for r in rs if r[kind] > 0]
        Wf = sum(r["w"] for r in filled)
        if not filled:
            lines.append(f"{label:28s} {part:5s} maker[{kind}] no fills")
            continue
        m, se = wmean(filled, lambda r: r["pay"] - r["bid"])
        nwo = sum(r["wo"] for r in filled)
        net20 = sum(r["w"] * min(r[kind], 20 / r["bid"]) * (r["pay"] - r["bid"]) for r in filled) / W
        lines.append(f"{label:28s} {part:5s} maker[{'through' if kind=='mk_thr_z' else 'at-price'}] filled {len(filled)}/{len(rs)} "
                     f"(w {Wf/W*100:.0f}%) wo={nwo} edge/sh={m*100:+.2f}c [{(m-1.96*se)*100:+.2f},{(m+1.96*se)*100:+.2f}] "
                     f"net per placed $20 bid ${net20:+.3f}")
    return "\n".join(lines)


def parts(rs):
    return {"early": [r for r in rs if r["part"] == "early"], "late": [r for r in rs if r["part"] == "late"], "all": rs}


def main():
    print("Universe rows", len(ROWS), "eligible", len(EL), "A eligible", sum(r["wo"] for r in EL))
    print("ineligible: A", sum(1 for r in ROWS if r["cls"] == "A" and not r["elig"]), "controls", sum(1 for r in ROWS if r["cls"] == "C" and not r["elig"]))
    print("days", {k: round(v, 1) for k, v in DAYS.items()})
    print()
    print("=== Part (a): is the walkover premium priced in? (all eligible trades)")
    for part, rs in parts(EL).items():
        W = sum(r["w"] for r in rs)
        g, gse = wmean(rs, lambda r: r["g"])
        woc = sum(r["w"] * (0.5 - r["p"]) for r in rs if r["wo"]) / W
        exp_prem = (sum(r["w"] * r["wo"] for r in rs) / W) * (sum(r["w"] * (0.5 - r["p"]) for r in rs) / W)
        ctrl = [r for r in rs if not r["wo"]]
        c, cse = wmean(ctrl, lambda r: r["g"])
        mf = sum(r["w"] * fee(r["p"]) for r in rs) / W
        print(f"{part:5s} gross(pay-p)={g*100:+.2f}c +-{1.96*gse*100:.2f} | walkover contribution {woc*100:+.2f}c "
              f"(q x mean(0.5-p) = {exp_prem*100:.2f}c) | played matches only (win-p) {c*100:+.2f}c +-{1.96*cse*100:.2f} | mean fee {mf*100:.2f}c")
    print()
    print("=== V0 blind underdog")
    for part, rs in parts(EL).items():
        print(summary(rs, part, "V0 blind"))
    print("-- diagnostic cuts (all period)")
    for lo, hi in ((0.05, 0.15), (0.15, 0.30), (0.30, 0.4501)):
        for part, rs in parts([r for r in EL if lo <= r["p"] < hi]).items():
            print(summary(rs, part, f"  band {lo:.2f}-{hi:.2f}"))
    for s in sorted({r["series"] for r in EL}):
        print(summary([r for r in EL if r["series"] == s], "all", f"  series {s}"))
    for mo in ("09", "10", "11"):
        print(summary([r for r in EL if r["day"][5:7] == mo], "all", f"  month {mo}"))
    lead = sorted(r["lead_h"] for r in EL)
    print(f"  lead time of the trade before T: median {lead[len(lead)//2]:.2f} h")
    av = sorted(r["avail_usd"] for r in EL)
    zz = sorted(r["z"] * r["p"] for r in EL)
    print(f"  first print $ (shown size x p): median {zz[len(zz)//2]:.2f} p25 {zz[len(zz)//4]:.2f} p75 {zz[3*len(zz)//4]:.2f}")
    print(f"  buyable underdog $ <=0.45 in window: median {av[len(av)//2]:.1f} p25 {av[len(av)//4]:.1f} p75 {av[3*len(av)//4]:.1f}")
    print()
    print("=== Screening F1..F7 on EARLY only")
    early = [r for r in EL if r["part"] == "early"]
    Wb = sum(r["w"] for r in early)
    q0 = sum(r["w"] * r["wo"] for r in early) / Wb
    print(f"early base rate q0 = {q0*100:.2f}% (n={len(early)})")
    scr = {}
    for f in FEATS:
        fl = [r for r in early if r["F"][f]]
        if not fl:
            print(f"{f}: no flags")
            continue
        W = sum(r["w"] for r in fl)
        q = sum(r["w"] * r["wo"] for r in fl) / W
        m, se = wmean(fl, lambda r: r["e"])
        scr[f] = (len(fl), q, m)
        print(summary(fl, "early", f"F {f}") + f"\n{'':34s}lift q/q0 = {q/q0:.2f}")
    s1 = [f for f in scr if scr[f][0] >= 100]
    S1 = max(s1, key=lambda f: scr[f][2]) if s1 else None
    S2 = [f for f in scr if scr[f][0] >= 50 and scr[f][1] >= 1.5 * q0]
    print(f"\nS1 = {S1}  (candidates with >=100 early flags: {s1})")
    print(f"S2 = OR of {S2}")
    print()
    print("=== S1 and S2: early (selection) and LATE (test)")
    rules = {}
    if S1:
        rules["S1 " + S1] = lambda r, S1=S1: r["F"][S1]
    if S2:
        rules["S2 OR(" + ",".join(S2) + ")"] = lambda r: any(r["F"][f] for f in S2)
    for name, fn in rules.items():
        fl = [r for r in EL if fn(r)]
        for part, rs in parts(fl).items():
            print(summary(rs, part, name))
    print()
    print("=== Maker scenarios (fee 0, optimistic)")
    for part, rs in parts(EL).items():
        print(maker_summary(rs, part, "V0 blind"))
    for name, fn in rules.items():
        fl = [r for r in EL if fn(r)]
        for part, rs in parts(fl).items():
            print(maker_summary(rs, part, name))
    json.dump({"S1": S1, "S2": S2, "q0_early": q0, "screen": scr}, open(Path(__file__).parent / "out" / "selection.json", "w"), indent=1)


if __name__ == "__main__":
    main()
