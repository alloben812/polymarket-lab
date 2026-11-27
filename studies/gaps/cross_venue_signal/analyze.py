"""Protocol runs (6 trading variants + diagnostics) for studies/gaps/cross_venue_signal/protocol.md.
Writes out/report.txt, out/variants.csv, out/trades_<variant>.csv (small)."""
from __future__ import annotations

import csv
import gzip
import json
import math
import random
import statistics as st
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "gaps_cross_venue_signal"
TAPE_DIRS = [DATA / "tapes", ROOT / "data" / "gaps_sports_lag" / "tapes"]
OUT = Path(__file__).resolve().parent / "out"
RATE = 0.05
WIN = 1800
XS = (0.03, 0.05, 0.08)
STAKE = 10.0
FEE_OVERRIDE = None  # for the fee-sensitivity attack only


def tape(cid):
    for d in TAPE_DIRS:
        p = d / f"{cid}.jsonl.gz"
        if p.exists():
            with gzip.open(p, "rt") as f:
                return [json.loads(l) for l in f]
    return None


def fl(x):
    try:
        v = float(x)
        return v if v > 1.0 else None
    except (TypeError, ValueError):
        return None


def demargin(o):
    if any(v is None for v in o):
        return None
    inv = [1 / v for v in o]
    s = sum(inv)
    return [v / s for v in inv]


def fair(m, closing):
    od = m["odds"]
    c = "C" if closing else ""
    p = demargin([fl(od.get(f"BFE{c}{x}")) for x in "HDA"])
    if p:
        return p, "BFE"
    p = demargin([fl(od.get(f"Avg{c}{x}")) for x in "HDA"])
    return (p, "Avg") if p else (None, None)


def e1_time(k):
    """Latest Tuesday or Friday 18:00 UTC that is at least 30 min before kick-off."""
    lim = k - 1800
    d = datetime.fromtimestamp(lim, timezone.utc).replace(hour=18, minute=0, second=0, microsecond=0)
    t = int(d.timestamp())
    if t > lim:
        t -= 86400
    for _ in range(8):
        if datetime.fromtimestamp(t, timezone.utc).weekday() in (1, 4):
            return t
        t -= 86400
    return None


def fee(p):
    r = RATE if FEE_OVERRIDE is None else FEE_OVERRIDE
    return r * p * (1 - p)


def load():
    ms = json.load(open(DATA / "matches.json"))
    out, drop = [], defaultdict(int)
    for m in ms:
        tp = {r: tape(m["markets"][r]["cid"]) for r in "HDA"}
        if any(v is None for v in tp.values()):
            drop["no tape (not fetched)"] += 1
            continue
        res = m["odds"]["FTR"]
        ok = True
        for r in "HDA":
            op = m["markets"][r].get("outcomePrices")
            try:
                op = [float(x) for x in json.loads(op)]
            except Exception:  # noqa: BLE001
                op = None
            if not op or sorted(op) != [0.0, 1.0]:
                ok = False
                drop["market not resolved 1/0"] += 1
                break
            if (op[0] == 1.0) != (res == r):
                ok = False
                drop["gamma vs FTR disagree"] += 1
                break
        if not ok:
            continue
        m["tapes"] = tp
        m["won"] = {r: res == r for r in "HDA"}
        out.append(m)
    return out, drop


def candidates(m, E, pf):
    """Taker BUY prints in [E, E+WIN] for the six tokens: (t, role, outcome, price, size, fair, win)."""
    c = []
    for i, r in enumerate("HDA"):
        for x in m["tapes"][r]:
            if x["t"] < E:
                continue
            if x["t"] > E + WIN:
                break
            if x["s"] != "BUY" or not (0.01 <= x["p"] <= 0.99):
                continue
            f = pf[i] if x["o"] == "Yes" else 1 - pf[i]
            w = m["won"][r] if x["o"] == "Yes" else not m["won"][r]
            c.append((x["t"], r, x["o"], x["p"], x["z"], f, w))
    c.sort(key=lambda z: z[0])
    return c


def last_yes(m, r, E):
    """Last print price of the Yes token (Yes price or 1 - No price) strictly before E."""
    v = None
    for x in m["tapes"][r]:
        if x["t"] >= E:
            break
        v = x["p"] if x["o"] == "Yes" else 1 - x["p"]
    return v


def summary(rets):
    n = len(rets)
    if n == 0:
        return dict(n=0)
    mu = st.mean(rets)
    se = st.stdev(rets) / math.sqrt(n) if n > 1 else float("nan")
    rng = random.Random(7)
    bs = sorted(st.mean(rng.choices(rets, k=n)) for _ in range(2000)) if n > 1 else [mu, mu]
    return dict(n=n, mean=mu, se=se, t=mu / se if se and se == se and se > 0 else float("nan"),
                lo=bs[int(0.025 * len(bs))], hi=bs[int(0.975 * len(bs)) - 1])


def day_se(trs):
    by = defaultdict(list)
    for t in trs:
        by[datetime.fromtimestamp(t["k"], timezone.utc).date()].append(t["ret"])
    if len(by) < 2:
        return float("nan")
    tot = [sum(v) for v in by.values()]
    n = sum(len(v) for v in by.values())
    mu = sum(tot) / n
    resid = [sum(x - mu for x in v) for v in by.values()]
    g = len(by)
    return math.sqrt(g / (g - 1) * sum(e * e for e in resid)) / n


def run(ms, sig, X):
    trs, pie = [], []
    for m in ms:
        pf, src = fair(m, closing=(sig == "S2"))
        if not pf:
            continue
        E = e1_time(m["k"]) if sig == "S1" else m["k"] - 1800
        if E is None or m["k"] - E > 96 * 3600:
            continue
        cs = candidates(m, E, pf)
        q = [c for c in cs if c[5] - c[3] >= X]
        for c in q:
            pie.append((m["k"], c[4], c[3], (1.0 if c[6] else 0.0) - c[3] - fee(c[3])))
        if not q:
            continue
        t, r, o, p, z, f, w = q[0]
        sh = min(STAKE / p, z)
        pnl_sh = (1.0 if w else 0.0) - p - fee(p)
        trs.append(dict(k=m["k"], div=m["div"], event=m["event"], E=E, t=t, lag=t - E, hours_before=(m["k"] - t) / 3600,
                        role=r, o=o, p=p, size=z, fair=f, gap=f - p, win=w, pnl_sh=pnl_sh, ret=pnl_sh / p,
                        usd=sh * p, pnl_usd=sh * pnl_sh, src=src))
    return trs, pie


def fmt(s):
    if not s.get("n"):
        return "n=0"
    return (f"n={s['n']:4d} ret/$ {s['mean']*100:+6.2f}% se {s['se']*100:5.2f} t {s['t']:+5.2f} "
            f"CI95 [{s['lo']*100:+6.2f}, {s['hi']*100:+6.2f}]%")


def main():
    global FEE_OVERRIDE
    OUT.mkdir(exist_ok=True)
    ms, drop = load()
    ms.sort(key=lambda m: m["k"])
    ks = [m["k"] for m in ms]
    split = ks[len(ks) // 2]
    early = [m for m in ms if m["k"] < split]
    late = [m for m in ms if m["k"] >= split]
    L = []
    P = lambda *a: L.append(" ".join(str(x) for x in a))  # noqa: E731
    d = lambda t: datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d %H:%M")  # noqa: E731
    P(f"sample: {len(ms)} matches with three resolved markets and tapes; dropped {dict(drop)}")
    P(f"kick-offs {d(ks[0])} .. {d(ks[-1])}; split at {d(split)}: early {len(early)}, late {len(late)}")
    P("by league:", dict(sorted(defaultdict(int, {k: sum(1 for m in ms if m['div'] == k) for k in {m['div'] for m in ms}}).items())))
    rows = []
    chosen = {}
    allres = {}
    for sig in ("S1", "S2"):
        best = None
        for X in XS:
            te, pe = run(early, sig, X)
            tl, pl = run(late, sig, X)
            se_, sl_ = summary([t["ret"] for t in te]), summary([t["ret"] for t in tl])
            allres[(sig, X)] = (te, tl, pe, pl)
            if se_.get("n", 0) >= 20 and (best is None or se_["mean"] >= best[1] - 1e-12):
                best = (X, se_["mean"])
            for part, s, trs in (("early", se_, te), ("late", sl_, tl)):
                rows.append(dict(signal=sig, X=X, part=part, n=s.get("n", 0), ret_per_usd=s.get("mean"), se=s.get("se"),
                                 t=s.get("t"), ci_lo=s.get("lo"), ci_hi=s.get("hi"),
                                 day_se=day_se(trs) if trs else None,
                                 c_per_share=st.mean([t["pnl_sh"] for t in trs]) * 100 if trs else None,
                                 win_rate=st.mean([t["win"] for t in trs]) if trs else None,
                                 avg_price=st.mean([t["p"] for t in trs]) if trs else None,
                                 avg_fair=st.mean([t["fair"] for t in trs]) if trs else None,
                                 usd_avg=st.mean([t["usd"] for t in trs]) if trs else None))
        chosen[sig] = best[0] if best else None
    P("")
    P("=== Trading variants (return per dollar staked after the 0.05 fee; one trade per match) ===")
    for r in rows:
        mark = " <- chosen on early" if chosen.get(r["signal"]) == r["X"] else ""
        if r["n"]:
            P(f"{r['signal']} X={r['X']:.2f} {r['part']:5s} n={r['n']:4d} ret/$ {r['ret_per_usd']*100:+6.2f}% "
              f"(se {r['se']*100:.2f}, t {r['t']:+.2f}, CI95 [{r['ci_lo']*100:+.2f}, {r['ci_hi']*100:+.2f}], day-cl se "
              f"{(r['day_se'] or float('nan'))*100:.2f}) c/sh {r['c_per_share']:+.2f} win {r['win_rate']:.3f} "
              f"avg price {r['avg_price']:.3f} avg fair {r['avg_fair']:.3f} avg $ {r['usd_avg']:.2f}{mark}")
        else:
            P(f"{r['signal']} X={r['X']:.2f} {r['part']:5s} n=0{mark}")
    with open(OUT / "variants.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    # per-variant detail for chosen ones
    for sig in ("S1", "S2"):
        X = chosen[sig]
        if X is None:
            continue
        te, tl, pe, pl = allres[(sig, X)]
        with open(OUT / f"trades_{sig}_X{int(X*100):02d}.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list((te + tl)[0]) + ["part"])
            w.writeheader()
            for t in te:
                w.writerow({**t, "part": "early"})
            for t in tl:
                w.writerow({**t, "part": "late"})
        P("")
        P(f"--- {sig} X={X} detail ---")
        for part, trs, pie in (("early", te, pe), ("late", tl, pl)):
            if not trs:
                continue
            days = (max(t["k"] for t in trs) - min(t["k"] for t in trs)) / 86400 + 1
            P(f"{part}: {len(trs)} trades over {days:.0f} days = {len(trs)/days:.2f}/day; median lag after E "
              f"{st.median([t['lag'] for t in trs]):.0f} s; median hours before kick-off {st.median([t['hours_before'] for t in trs]):.1f}; "
              f"fair source {dict((s, sum(1 for t in trs if t['src']==s)) for s in ('BFE','Avg'))}")
            P(f"   PnL at <=$10/trade: {sum(t['pnl_usd'] for t in trs):+.2f} USD on {sum(t['usd'] for t in trs):.0f} USD staked; "
              f"median print size {st.median([t['size']*t['p'] for t in trs]):.2f} USD; share with print >= $10: "
              f"{sum(1 for t in trs if t['size']*t['p'] >= 10)/len(trs):.2f}")
            P(f"   pie (all qualifying taker BUY prints in the windows): {len(pie)} prints, {sum(z*p for _,z,p,_ in pie):.0f} USD, "
              f"realised net {sum(z*x for _,z,_,x in pie):+.0f} USD")
            for lab, sub in (("Yes", [t for t in trs if t["o"] == "Yes"]), ("No", [t for t in trs if t["o"] == "No"]),
                             ("price<0.35", [t for t in trs if t["p"] < 0.35]), ("price>=0.35", [t for t in trs if t["p"] >= 0.35]),
                             ("draw tokens", [t for t in trs if t["role"] == "D"])):
                P(f"   {lab:12s} {fmt(summary([t['ret'] for t in sub]))}")
            byl = defaultdict(list)
            for t in trs:
                byl[t["div"]].append(t["ret"])
            P("   by league: " + "; ".join(f"{k} n={len(v)} {st.mean(v)*100:+.1f}%" for k, v in sorted(byl.items())))
            srt = sorted(trs, key=lambda t: -t["pnl_usd"])
            P(f"   without the 5 best trades: {fmt(summary([t['ret'] for t in srt[5:]]))}")
    # fee sensitivity: gross (fee 0) for all variants
    P("")
    P("=== Attack: gross (fee 0) for every variant, late part ===")
    FEE_OVERRIDE = 0.0
    for sig in ("S1", "S2"):
        for X in XS:
            tl, _ = run(late, sig, X)
            te, _ = run(early, sig, X)
            P(f"{sig} X={X:.2f} gross early {fmt(summary([t['ret'] for t in te]))} | late {fmt(summary([t['ret'] for t in tl]))}")
    FEE_OVERRIDE = None
    # diagnostics
    P("")
    P("=== Diagnostic: which three-way probability is sharper (log-loss, Brier; lower is better) ===")
    rec = []
    for m in ms:
        p1, _ = fair(m, False)
        p2, _ = fair(m, True)
        E1 = e1_time(m["k"])
        E2 = m["k"] - 1800
        if not p1 or not p2 or E1 is None or m["k"] - E1 > 96 * 3600:
            continue
        a = [last_yes(m, r, E1) for r in "HDA"]
        b = [last_yes(m, r, E2) for r in "HDA"]
        if any(v is None or v <= 0 for v in a + b):
            continue
        a = [v / sum(a) for v in a]
        b = [v / sum(b) for v in b]
        y = [1.0 if m["won"][r] else 0.0 for r in "HDA"]
        rec.append(dict(m=m, pmE1=a, pmE2=b, s1=p1, s2=p2, y=y))
    def ll(p, y):
        return -math.log(max(1e-6, sum(pi * yi for pi, yi in zip(p, y))))
    def br(p, y):
        return sum((pi - yi) ** 2 for pi, yi in zip(p, y))
    P(f"matches with all four probabilities: {len(rec)}")
    for lab in ("pmE1", "s1", "pmE2", "s2"):
        P(f"   {lab:5s} log-loss {st.mean(ll(r[lab], r['y']) for r in rec):.4f}  Brier {st.mean(br(r[lab], r['y']) for r in rec):.4f}")
    dd = [ll(r["pmE1"], r["y"]) - ll(r["s1"], r["y"]) for r in rec]
    P(f"   log-loss PM(E1) - S1 per match: mean {st.mean(dd):+.4f} se {st.stdev(dd)/math.sqrt(len(dd)):.4f}")
    dd = [ll(r["pmE2"], r["y"]) - ll(r["s2"], r["y"]) for r in rec]
    P(f"   log-loss PM(E2) - S2 per match: mean {st.mean(dd):+.4f} se {st.stdev(dd)/math.sqrt(len(dd)):.4f}")
    xs, ys = [], []
    for r in rec:
        for i in range(3):
            xs.append(r["s1"][i] - r["pmE1"][i])
            ys.append(r["pmE2"][i] - r["pmE1"][i])
    sxx = sum(x * x for x in xs)
    P(f"   gap closure: slope of PM move E1->E2 on (S1 - PM at E1) = {sum(x*y for x,y in zip(xs,ys))/sxx:.3f} "
      f"(n={len(xs)} outcomes); median |S1 - PM(E1)| {st.median(abs(x) for x in xs)*100:.2f} pts; "
      f"median |S2 - PM(E2)| {st.median(abs(r['s2'][i]-r['pmE2'][i]) for r in rec for i in range(3))*100:.2f} pts")
    xs2 = [r["s2"][i] - r["s1"][i] for r in rec for i in range(3)]
    ys2 = [r["pmE2"][i] - r["pmE1"][i] for r in rec for i in range(3)]
    P(f"   bookmaker move S1->S2 vs PM move E1->E2: corr {st.correlation(xs2, ys2):.3f}; "
      f"median |S2-S1| {st.median(abs(x) for x in xs2)*100:.2f} pts; median hours E1->kick-off "
      f"{st.median((r['m']['k']-e1_time(r['m']['k']))/3600 for r in rec):.1f}")
    (OUT / "report.txt").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--sanity":
        ms, drop = load()
        print(len(ms), dict(drop))
        sys.exit()
    main()
