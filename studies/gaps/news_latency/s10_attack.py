"""Step 10 (post-hoc, written after the s6/s8 tables were seen): attacks on the positive rule result.
Nothing here changes the verdict variants; every run is counted in results.md.
A1 bootstrap CI by news cluster; A2 drop the best clusters; A3 one trade per news cluster (earliest jump);
A4 'doubt' labels moved to unscheduled; A5 the same rule on ALL tape-timed jumps incl. those not confirmed at +10 min
(removes the selection on the price 10 minutes later), every label; A6 the rule at $20 instead of $200;
A7 share of the window's buyer profit the rule claims (the 'pie')."""
import collections, csv, json, sys
from pmlab import stats
from common import *
from s4_jumps import load_tape
from s5_measure import offer_price
import s6_rule

DELAYS = [10, 30, 120, 600]


def payoff_of(j, res, mk):
    r = res.get(j["c"]) or {}
    m = mk[j["c"]]
    oy, on = outcomes(m)
    fin = r.get("final") or {}
    if r.get("resolved") and fin.get(oy) is not None:
        y = float(fin[oy]); resolved = True
    else:
        try:
            y = float(json.loads(m["outcomePrices"])[0])
        except Exception:  # noqa: BLE001
            return None, False
        resolved = False
    return (y if j["dir"] > 0 else 1 - y), resolved


def run(js, budget=200.0):
    s6_rule.BUDGET = budget
    out = {}
    for j in js:
        tape = load_tape(j["c"])
        for d in DELAYS:
            spent, shares, fee, fills = s6_rule.run_rule(j, tape, d)
            net = shares * j["payoff"] - spent - fee if shares else 0.0
            out[(j["c"], j["t0"], d)] = (spent, net)
    s6_rule.BUDGET = 200.0
    return out


def summ(js, rr, d, key="cluster"):
    by = collections.defaultdict(float)
    sp = collections.defaultdict(float)
    for j in js:
        s, n = rr[(j["c"], j["t0"], d)]
        by[j[key]] += n
        sp[j[key]] += s
    v = list(by.values())
    m, se, t = stats.mean_se(v)
    lo, hi = stats.bootstrap_sum_ci(v)
    return {"n": len(js), "clusters": len(v), "spent": sum(sp.values()), "net": sum(v), "t": t, "ci": (lo, hi),
            "filled": sum(1 for j in js if rr[(j["c"], j["t0"], d)][0] > 0), "by": by}


def line(name, r):
    return (f"| {name} | {r['n']} | {r['clusters']} | {r['filled']} | {r['spent']:.0f} | {r['net']:+.0f} | "
            f"{r['ci'][0]:+.0f} .. {r['ci'][1]:+.0f} | {r['t']:.2f} |")


def main():
    jumps = json.load(open(OUT / "jumps.json"))
    res = json.load(open(OUT / "resolutions.json"))
    mk = {m["conditionId"]: m for m in universe()}
    lab = {(r["c"], int(r["t0"])): r for r in csv.DictReader(open(OUT / "labels.csv"))}
    for j in jumps:
        p, rsv = payoff_of(j, res, mk)
        j["payoff"], j["resolved2"] = p, rsv
        j["half"] = 1 if j["t0"] < SPLIT else 2
        l = lab.get((j["c"], j["t0"]))
        j["label"] = l["label"] if l else None
        j["doubt"] = bool(l and l["doubt"])
        if "cluster" not in j:
            j["cluster"] = "u" + j["c"][:10] + str(j["t0"])
    ok = [j for j in jumps if j["payoff"] is not None]
    rr = run(ok)
    rr20 = run(ok, 20.0)
    out = ["| sample | jumps | clusters | with fill | $ spent | net $ | 95% CI of net (cluster bootstrap) | t (cluster) |", "|---|---|---|---|---|---|---|---|"]
    um = [j for j in ok if j["status"] == "main" and j["label"] == "unscheduled"]
    for half, nm in ((None, "whole"), (1, "first half"), (2, "second half")):
        sub = [j for j in um if half is None or j["half"] == half]
        for d in DELAYS:
            out.append(line(f"A1 unscheduled main, {nm}, d={d}", summ(sub, rr, d)))
    rep = [j for j in um if j["half"] == 2]
    for d in (30, 120):
        r = summ(rep, rr, d)
        top = sorted(r["by"].items(), key=lambda kv: -kv[1])
        for k in (1, 3, 5):
            drop = {c for c, _ in top[:k]}
            out.append(line(f"A2 second half, d={d}, without best {k} cluster(s)", summ([j for j in rep if j["cluster"] not in drop], rr, d)))
    for half, nm in ((None, "whole"), (2, "second half")):
        first = {}
        for j in sorted(um, key=lambda j: j["t0"]):
            if half is None or j["half"] == half:
                first.setdefault(j["cluster"], j)
        for d in DELAYS:
            out.append(line(f"A3 one jump per cluster, {nm}, d={d}", summ(list(first.values()), rr, d)))
    ud = [j for j in ok if j["status"] == "main" and (j["label"] == "unscheduled" or j["doubt"])]
    for d in (30, 120):
        out.append(line(f"A4 unscheduled + doubtful, main, second half, d={d}", summ([j for j in ud if j["half"] == 2], rr, d)))
    allj = [j for j in ok if j["status"] in ("main", "R", "unconfirmed", "artefact")]
    for half, nm in ((None, "whole"), (2, "second half")):
        sub = [j for j in allj if half is None or j["half"] == half]
        for d in DELAYS:
            out.append(line(f"A5 ALL tape-timed jumps (incl. not confirmed), every label, {nm}, d={d}", summ(sub, rr, d)))
        unc = [j for j in sub if j["status"] in ("unconfirmed", "artefact")]
        for d in (30, 120):
            out.append(line(f"A5b only NOT confirmed / artefact, {nm}, d={d}", summ(unc, rr, d)))
    for half, nm in ((None, "whole"), (2, "second half")):
        sub = [j for j in um if half is None or j["half"] == half]
        for d in DELAYS:
            out.append(line(f"A6 $20 budget, unscheduled main, {nm}, d={d}", summ(sub, rr20, d)))
        sub = [j for j in allj if half is None or j["half"] == half]
        for d in (30, 120):
            out.append(line(f"A6b $20 budget, ALL tape-timed jumps, {nm}, d={d}", summ(sub, rr20, d)))
    # A7 pie: realised profit of all F-buyers at <= 0.90 in [t0+d, t0+d+600] vs the rule's net
    out.append("\n| A7 pie, unscheduled main | delay | all buyers' realised $ at <= 0.90 in the window | rule net $ | rule share |")
    out.append("|---|---|---|---|---|")
    for half, nm in ((None, "whole"), (2, "second half")):
        sub = [j for j in um if half is None or j["half"] == half]
        for d in DELAYS:
            pie = 0.0
            for j in sub:
                fi = 0 if j["dir"] > 0 else 1
                for r in load_tape(j["c"]):
                    if j["t0_block"] + d <= r["t"] <= j["t0_block"] + d + 600:
                        p = offer_price(r, fi)
                        if p is not None and 0 < p <= 0.90:
                            pie += (j["payoff"] - p) * r["z"] - r["z"] * j["fee_rate"] * p * (1 - p)
            net = sum(rr[(j["c"], j["t0"], d)][1] for j in sub)
            out.append(f"| {nm} | {d} s | {pie:+,.0f} | {net:+,.0f} | {net / pie * 100 if pie else float('nan'):.0f}% |")
    st = collections.Counter(j["status"] for j in allj)
    out.append(f"\nA5 sample by status: {dict(st)}; payoff missing for {len(jumps) - len(ok)} jumps")
    (OUT / "attack.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
