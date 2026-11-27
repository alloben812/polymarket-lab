"""Step 5: the four rule variants (delays) on class A (hindsight t_first; all markets and moneyline only), class B,
the causal follower on class A + sampled controls, the C-pin look-alikes, capacity, and (if out/public_times.json
exists) the rule from t_public. Prints tables; writes out/rule_events.json."""
import collections, datetime as dt, json, math, os, statistics, sys
from pmlab import updown
from pmlab.stats import mean_se, ratio_cluster, split_by_time
from common import *

STAV = "0xf5fe759cece500f58a431ef8dacea321f6e3e23d"
_cache = {}


def stream(m_cid, outcomes, vol=True):
    if not vol:
        return []
    if m_cid not in _cache:
        pr = prints(updown.tape(m_cid), outcomes)
        add_reference(pr)
        _cache[m_cid] = pr
    return _cache[m_cid]


def fin(m):
    f = m.get("api_final") or m.get("final")
    return (float(f[0]), float(f[1]))


def line(label, per_event, n_report=None):
    """per_event: list of dicts {net, cost, shares, fees} for ALL events of the group (zeros included)."""
    n = len(per_event)
    nets = [e["net"] for e in per_event]
    cost = sum(e["cost"] for e in per_event)
    sh = sum(e["shares"] for e in per_event)
    filled = sum(1 for e in per_event if e["shares"] > 0)
    m, se, t = mean_se(nets)
    r, rse, rt = ratio_cluster(nets, [e["cost"] for e in per_event])
    tot = sum(nets)
    return (f"{label} | {n} | {filled} | {sh:,.0f} | {cost:,.0f} | {cost / sh if sh else float('nan'):.3f} | {tot:,.0f} | {m:.2f} | {t:.2f} | "
            f"{r * 100 if r == r else float('nan'):.1f}% (t {rt:.1f}) | {tot / MONTHS:,.0f} | {tot / PERIOD_DAYS:.1f}")


HDR = "variant | events | with fill | shares | dollars | avg price | net $ | net/event | t (by match) | net/dollar | net $/month | net $/day"


def month_of(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m")


def pin_after(pr, i):
    """C-pin: within 30 min after episode start i, a run of >=5 consecutive prints spanning >=300 s all in [0.47, 0.53]."""
    t0 = pr[i]["t"]
    j = i
    n = len(pr)
    while j < n and pr[j]["t"] <= t0 + 1800:
        if 0.47 - 1e-9 <= pr[j]["a"] <= 0.53 + 1e-9:
            k = j
            while k + 1 < n and 0.47 - 1e-9 <= pr[k + 1]["a"] <= 0.53 + 1e-9:
                k += 1
            if k - j + 1 >= 5 and pr[k]["t"] - pr[j]["t"] >= 300:
                return True
            j = k + 1
        else:
            j += 1
    return False


def main():
    U = json.load(open(DATA / "universe.json"))
    EA = {o["slug"]: o for o in json.load(open(OUT / "events_A.json"))}
    EB = {o["slug"]: o for o in json.load(open(OUT / "events_B.json"))}
    k = U["k"]
    out = {}

    # ---------------- class A, hindsight t_first
    def run_group(recs, E, key, anchor="t_first", ml_only=False, restrict=None):
        res = {d: [] for d in DELAYS}
        for r in recs:
            o = E[r["slug"]]
            if restrict is not None and r["slug"] not in restrict:
                continue
            t0 = o.get(anchor) if restrict is None else restrict[r["slug"]]
            for d in DELAYS:
                if t0 is None:
                    res[d].append({"slug": r["slug"], "net": 0.0, "cost": 0.0, "shares": 0.0, "fees": 0.0, "closed": o["closed"], "payoff": 0.0})
                    continue
                ms = [m for m in r["markets"] if (not ml_only or m["cid"] == r["ml"])]
                streams = [(stream(m["cid"], m["outcomes"], m["vol"]), fin(m)) for m in ms if m.get("vol") and (m.get("api_final") or m.get("final"))]
                x = run_rule(streams, [t0 + d])
                res[d].append({"slug": r["slug"], "net": x["net"], "cost": x["cost"], "shares": x["shares"], "fees": x["fees"], "payoff": x["payoff"],
                               "closed": o["closed"], "first_fill_dt": (x["fills"][0][0] - t0) if x["fills"] else None,
                               "wallets": sorted({f[4] for f in x["fills"]})})
        out[key] = res
        return res

    print("== Class A (moneyline resolved 50-50), rule from the hindsight t_first, ALL markets of the event")
    print(HDR)
    RA = run_group(U["A"], EA, "A_all")
    for d in DELAYS:
        print(line(f"d={d}s", RA[d]))
    print("\n== Class A, moneyline market only")
    print(HDR)
    RAm = run_group(U["A"], EA, "A_ml", ml_only=True)
    for d in DELAYS:
        print(line(f"d={d}s", RAm[d]))

    # sanity: payoff must be exactly 0.5 * shares when all markets of a class A event are 50-50
    bad = [(e["slug"], e["payoff"], e["shares"]) for d in DELAYS for e in RA[d] if abs(e["payoff"] - 0.5 * e["shares"]) > 1e-6]
    print(f"\nsanity: class A fills whose payoff is not 0.5/share: {len(bad)} event-variants", bad[:5])
    fee_chk = max((abs(e["fees"] - 0.05 * 0) if e["shares"] == 0 else 0) for d in DELAYS for e in RA[d])
    print("sanity: fee on empty events is zero:", fee_chk == 0)

    print("\n== Class A, by calendar month of resolution (all markets)")
    print("month | " + HDR)
    for mo in ("2026-09", "2026-10", "2026-11"):
        for d in DELAYS:
            g = [e for e in RA[d] if month_of(e["closed"]) == mo]
            print(mo + " | " + line(f"d={d}s", g))
    print("\n== Class A, time split by moneyline resolution time: earlier 67% vs reporting 33% (all markets)")
    print("part | " + HDR)
    for d in DELAYS:
        early, late = split_by_time(RA[d], key=lambda e: e["closed"], frac=0.67)
        print("earlier | " + line(f"d={d}s", early))
        print(f"reporting (from {iso(late[0]['closed'])}) | " + line(f"d={d}s", late))

    # ---------------- class B
    print("\n== Class B (moneyline 1/0, some side market 50-50), rule from the earliest hindsight t_first of its 50-50 markets, all markets")
    print(HDR)
    RB = run_group(U["B"], EB, "B_all")
    for d in DELAYS:
        print(line(f"d={d}s", RB[d]))

    # ---------------- capacity
    print("\n== Capacity: buyable at <= 0.46 in [t_first + d, + 30 min], class A, all markets, no cap")
    print("delay | events with any | shares | dollars | vwap | $ per month | gross gain at 0.50 | fees | distinct takers | top-3 share | Stavenson share")
    for d in [0] + DELAYS:
        usd = sh = gain = fee = 0.0
        byw = collections.Counter()
        evs = set()
        for r in U["A"]:
            t0 = EA[r["slug"]].get("t_first")
            if t0 is None:
                continue
            for m in r["markets"]:
                if not m.get("vol"):
                    continue
                for x in stream(m["cid"], m["outcomes"]):
                    if t0 + d <= x["t"] <= t0 + d + WINDOW and x["bp"] <= PMAX + 1e-9:
                        usd += x["z"] * x["bp"]
                        sh += x["z"]
                        gain += x["z"] * (fin(m)[x["bo"]] - x["bp"])
                        fee += x["z"] * fee_ps(x["bp"])
                        byw[x["w"]] += x["z"] * x["bp"]
                        evs.add(r["slug"])
        top3 = sum(v for _, v in byw.most_common(3)) / usd if usd else float("nan")
        print(f"d={d}s | {len(evs)} | {sh:,.0f} | {usd:,.0f} | {usd / sh if sh else float('nan'):.3f} | {usd / MONTHS:,.0f} | {gain:,.0f} | {fee:,.0f} | {len(byw)} | {top3:.2f} | {byw.get(STAV, 0) / usd if usd else float('nan'):.2f}")

    # ---------------- causal follower: class A moneylines + sampled control moneylines
    def causal(cid, outcomes, start, final, d, any_time=False):
        pr = stream(cid, outcomes)
        eps = [i for i in episodes(pr) if any_time or (start is not None and pr[i]["t"] < start)]
        if not eps:
            return None, eps, pr
        x = run_rule([(pr, final)], [pr[i]["t"] + d for i in eps])
        return x, eps, pr

    print(f"\n== Causal follower (pre-start episodes, moneyline only): class A + control sample (k={k}, {len(U['control'])} of {U['control_all_n']} control moneylines)")
    print("delay | group | markets | with a pre-start episode | with fill | dollars | avg price | net $ | net per triggered market | net/dollar")
    caus = {}
    detail = {}
    for d in DELAYS:
        rowsA, rowsC = [], []
        for r in U["A"]:
            m = next(m for m in r["markets"] if m["cid"] == r["ml"])
            o = EA[r["slug"]]
            if not m.get("vol") or o["start"] is None:
                rowsA.append({"slug": r["slug"], "net": 0.0, "cost": 0.0, "shares": 0.0, "trig": False, "closed": o["closed"]})
                continue
            x, eps, pr = causal(m["cid"], m["outcomes"], o["start"], fin(m), d)
            rowsA.append({"slug": r["slug"], "net": x["net"] if x else 0.0, "cost": x["cost"] if x else 0.0, "shares": x["shares"] if x else 0.0,
                          "trig": bool(eps), "closed": o["closed"]})
        for c in U["control"]:
            if c["start"] is None:
                rowsC.append({"slug": c["slug"], "net": 0.0, "cost": 0.0, "shares": 0.0, "trig": False, "closed": c["closed"]})
                continue
            x, eps, pr = causal(c["cid"], c["outcomes"], c["start"], (float(c["final"][0]), float(c["final"][1])), d)
            row = {"slug": c["slug"], "net": x["net"] if x else 0.0, "cost": x["cost"] if x else 0.0, "shares": x["shares"] if x else 0.0,
                   "trig": bool(eps), "closed": c["closed"], "n_eps": len(eps)}
            if x and x["fills"]:
                i0 = eps[0]
                row.update({"ep_t": pr[i0]["t"], "start": c["start"], "r": pr[i0]["r"], "x": pr[i0]["x"], "und": pr[i0]["und"], "final": c["final"],
                            "first_fill_t": x["fills"][0][0], "avg_p": x["cost"] / x["shares"]})
            rowsC.append(row)
        caus[d] = (rowsA, rowsC)
        for name, rows, mult in (("class A", rowsA, 1), (f"control sample", rowsC, 1)):
            tr = [e for e in rows if e["trig"]]
            cost, sh, net = sum(e["cost"] for e in rows), sum(e["shares"] for e in rows), sum(e["net"] for e in rows)
            r_, rse, rt = ratio_cluster([e["net"] for e in rows], [e["cost"] for e in rows])
            print(f"d={d}s | {name} | {len(rows)} | {len(tr)} | {sum(1 for e in rows if e['shares'] > 0)} | {cost:,.0f} | {cost / sh if sh else float('nan'):.3f} | {net:,.0f} | "
                  f"{net / len(tr) if tr else float('nan'):.2f} | {r_ * 100 if r_ == r_ else float('nan'):.1f}% (t {rt:.1f})")
        # combined, stratified: total = sum_A + k * sum_C
        nA, nC = len(rowsA), len(rowsC)
        sA, sC = sum(e["net"] for e in rowsA), sum(e["net"] for e in rowsC)
        vA = statistics.pvariance([e["net"] for e in rowsA]) * nA / (nA - 1)
        vC = statistics.pvariance([e["net"] for e in rowsC]) * nC / (nC - 1)
        tot = sA + k * sC
        se = math.sqrt(nA * vA + k * k * nC * vC)
        cost = sum(e["cost"] for e in rowsA) + k * sum(e["cost"] for e in rowsC)
        ntrig = sum(1 for e in rowsA if e["trig"]) + k * sum(1 for e in rowsC if e["trig"])
        print(f"d={d}s | COMBINED (A + {k} x control) | {nA + k * nC} | {ntrig} | - | {cost:,.0f} | - | {tot:,.0f} | {tot / ntrig if ntrig else float('nan'):.2f} | "
              f"{tot / cost * 100 if cost else float('nan'):.1f}% ; t {tot / se if se else float('nan'):.2f} ; per month {tot / MONTHS:,.0f} ; per day {tot / PERIOD_DAYS:.1f}")
        # reporting period (same cut as class A split)
        cutA = split_by_time(rowsA, key=lambda e: e["closed"], frac=0.67)[1][0]["closed"]
        lA = [e for e in rowsA if e["closed"] >= cutA]
        lC = [e for e in rowsC if e["closed"] >= cutA]
        if len(lA) > 1 and len(lC) > 1:
            tot2 = sum(e["net"] for e in lA) + k * sum(e["net"] for e in lC)
            se2 = math.sqrt(len(lA) * statistics.variance([e["net"] for e in lA]) + k * k * len(lC) * statistics.variance([e["net"] for e in lC]))
            days = (P1 - cutA) / 86400
            print(f"d={d}s | COMBINED reporting period (from {iso(cutA)}; A {len(lA)}, control {len(lC)} x {k}) | net {tot2:,.0f} | t {tot2 / se2 if se2 else float('nan'):.2f} | per day {tot2 / days:.1f}")
    out["causal"] = {str(d): {"A": caus[d][0], "C": caus[d][1]} for d in DELAYS}

    rowsA, rowsC = caus[10]
    trA, trC = sum(1 for e in rowsA if e["trig"]), sum(1 for e in rowsC if e["trig"])
    print(f"\nshare of pre-start episodes markets that are walkovers: {trA} class A vs {trC} x {k} = {trC * k} control -> {trA / (trA + trC * k) * 100:.1f}%")
    print("control: ten largest losses at d=10s (slug | episode time rel. scheduled start | ref underdog -> trigger price | avg buy | cost | net | final)")
    for e in sorted([e for e in rowsC if e["shares"] > 0], key=lambda e: e["net"])[:10]:
        print(f"   {e['slug']} | {(e['ep_t'] - e['start']) / 60:.0f} min | {e['r']:.2f} -> {e['x']:.2f} | {e['avg_p']:.3f} | {e['cost']:.0f} | {e['net']:.0f} | {e['final']}")
    print("control: ten largest gains at d=10s")
    for e in sorted([e for e in rowsC if e["shares"] > 0], key=lambda e: -e["net"])[:10]:
        print(f"   {e['slug']} | {(e['ep_t'] - e['start']) / 60:.0f} min | {e['r']:.2f} -> {e['x']:.2f} | {e['avg_p']:.3f} | {e['cost']:.0f} | {e['net']:.0f} | {e['final']}")
    cf = [e for e in rowsC if e["shares"] > 0]
    if cf:
        wins = sum(1 for e in cf if e["net"] > 0)
        print(f"control fills d=10s: {len(cf)} markets, {wins} profitable; mean avg price {statistics.mean(e['avg_p'] for e in cf):.3f}")

    # ---------------- C-pin
    print("\n== C-pin look-alikes (episode at any time followed within 30 min by >=5 consecutive prints over >=5 min inside 0.47-0.53), moneyline only")
    pinA = pinC = trigA = trigC = 0
    pin_rows = {d: [] for d in DELAYS}
    pin_desc = []
    for c in U["control"]:
        pr = stream(c["cid"], c["outcomes"])
        eps = episodes(pr)
        if eps:
            trigC += 1
        hit = next((i for i in eps if pin_after(pr, i)), None)
        if hit is None:
            continue
        pinC += 1
        fnl = (float(c["final"][0]), float(c["final"][1]))
        for d in DELAYS:
            x = run_rule([(pr, fnl)], [pr[hit]["t"] + d])
            pin_rows[d].append({"slug": c["slug"], "net": x["net"], "cost": x["cost"], "shares": x["shares"], "fees": x["fees"], "closed": c["closed"]})
        after = [y for y in pr if y["t"] > pr[hit]["t"] + 1800]
        pin_desc.append((c["slug"], (pr[hit]["t"] - c["start"]) / 60 if c["start"] else None, pr[hit]["r"], pr[hit]["x"], len(pr), c["final"],
                         [round(y["a"], 2) for y in pr[hit:hit + 1]] + [round(y["a"], 2) for y in after[:1]] + [round(y["a"], 2) for y in after[-1:]]))
    for r in U["A"]:
        m = next(m for m in r["markets"] if m["cid"] == r["ml"])
        if not m.get("vol"):
            continue
        pr = stream(m["cid"], m["outcomes"])
        eps = episodes(pr)
        if eps:
            trigA += 1
        if any(pin_after(pr, i) for i in eps):
            pinA += 1
    print(f"control sample: {trigC} markets with any episode, {pinC} with a pin ({pinC * k} scaled); class A moneylines: {trigA} with any episode, {pinA} with a pin")
    print(f"share of pins that are walkovers: {pinA} / ({pinA} + {pinC * k}) = {pinA / (pinA + pinC * k) * 100 if pinA + pinC else float('nan'):.1f}%")
    print(HDR.replace("events", "pinned control markets"))
    for d in DELAYS:
        print(line(f"d={d}s", pin_rows[d]) if pin_rows[d] else f"d={d}s | 0")
    print("pinned control markets (slug | episode min after scheduled start | ref -> trigger | prints | final | outcome0 price at trigger, first print after +30 min, last print):")
    for p in sorted(pin_desc, key=lambda p: p[0])[:60]:
        print("   ", p[0], "|", None if p[1] is None else round(p[1]), "|", f"{p[2]:.2f} -> {p[3]:.2f}", "|", p[4], "|", p[5], "|", p[6])
    out["pin"] = pin_rows

    # ---------------- rule from t_public
    pth = OUT / "public_times.json"
    if pth.exists():
        pub = {p["slug"]: p["t_public"] for p in json.load(open(pth)) if p.get("t_public") and p.get("precision") in ("second", "minute")}
        recs = [r for r in U["A"] if r["slug"] in pub]
        print(f"\n== Class A events with a public notice time (n={len(recs)}), rule from t_public, all markets")
        print(HDR)
        RP = run_group(recs, EA, "A_public", restrict=pub)
        for d in DELAYS:
            print(line(f"d={d}s", RP[d]))
        print("same events, rule from t_first (for comparison)")
        sl = set(pub)
        for d in DELAYS:
            print(line(f"d={d}s", [e for e in RA[d] if e["slug"] in sl]))
    json.dump(out, open(OUT / "rule_events.json", "w"))


if __name__ == "__main__":
    main()
