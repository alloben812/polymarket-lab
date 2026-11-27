"""Stage 3: aggregate episodes (protocol: Split, unit, clustering; Decision rule; Attacks).
usage: python3 -I a3_report.py  -> out/report.txt, out/episodes_R5.csv (small)
"""
import json, os, glob, collections
import numpy as np

D = "/home/user/polymarket-lab/data/gaps_negrisk"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(7)
L = []


def p(*a):
    s = " ".join(str(x) for x in a); print(s); L.append(s)


def part(tag):
    return "early" if tag[:10] <= "2026-11-23" else "late"


def cat(slug):
    s = slug.lower()
    if "temperature" in s: return "weather"
    if "tweets" in s or "posts" in s: return "post-count"
    if any(k in s for k in ["decision", "fed-", "cpi", "rate"]): return "rates/econ"
    if "above" in s: return "crypto-ladder"
    if any(k in s for k in ["epl-", "ucl-", "lal-", "sea-", "bun-", "fl1-", "nba-", "nfl-", "-winner", "champion"]): return "sports"
    return "other"


def boot_mean_by_cluster(vals, clusters, B=2000):
    by = collections.defaultdict(list)
    for v, c in zip(vals, clusters):
        by[c].append(v)
    keys = list(by)
    if not keys:
        return (float("nan"),) * 3
    sums = np.array([sum(by[k]) for k in keys]); cnts = np.array([len(by[k]) for k in keys])
    est = sums.sum() / cnts.sum()
    bs = []
    for _ in range(B):
        ix = rng.integers(0, len(keys), len(keys))
        bs.append(sums[ix].sum() / cnts[ix].sum())
    return est, float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def boot_total_by_cluster(vals, clusters, B=2000):
    by = collections.defaultdict(float)
    for v, c in zip(vals, clusters):
        by[c] += v
    keys = list(by); s = np.array([by[k] for k in keys])
    if not keys:
        return 0.0, 0.0, 0.0
    bs = [s[rng.integers(0, len(s), len(s))].sum() for _ in range(B)]
    return float(s.sum()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def main():
    files = sorted(glob.glob(f"{D}/epi/*.json"))
    tags = [os.path.basename(f)[:-5] for f in files]
    hours = collections.Counter(part(t) for t in tags)
    p("hours with episodes file:", len(tags), dict(hours))
    # stage 1 and A1
    s1 = collections.defaultdict(lambda: collections.Counter())
    a1 = collections.Counter()
    nev = collections.defaultdict(list)
    for t in tags:
        sc = json.load(open(f"{D}/scan/{t}.json"))
        for fam in ["B1", "B2", "C1", "C2"]:
            s1[part(t)][fam] += len(sc[fam])
        for k, v in (sc.get("A1") or {}).items():
            if k in ("pairs", "ask_sum_lt1", "bid_sum_gt1"):
                a1[k] += v
        for k, v in sc["n_events"].items():
            nev[k].append(v)
    p("stage-1 price-only positive intervals:", {k: dict(v) for k, v in s1.items()})
    p("events scanned per hour (mean):", {k: round(np.mean(v), 1) for k, v in nev.items()})
    p("A1 archive both-token same-ms pairs:", dict(a1))
    U = {e["slug"]: e for e in json.load(open(f"{D}/universe.json"))}

    def days_left(e):
        try:
            end = np.datetime64(U[e["ev"]]["endDate"].replace("Z", ""), "s").astype("int64")
            return (end - e["t0"] / 1000) / 86400
        except Exception:
            return float("nan")
    E = []
    for f, t in zip(files, tags):
        sc = json.load(open(f"{D}/scan/{t}.json"))
        iv = collections.defaultdict(list)
        for fam in ["B1", "B2", "C1", "C2"]:
            for it in sc[fam]:
                key = (fam, it["ev"], (it["bid_m"], it["ask_m"]) if fam in ("C1", "C2") else None)
                iv[key].append((it["t0"], it["t1"]))
        for e in json.load(open(f))["episodes"]:
            key = (e["fam"], e["ev"], tuple(e["pair"]) if e.get("pair") else None)
            tr = e["t0"] + 5000
            e["field_ok"] = any(a <= tr < b for a, b in iv.get(key, []))
            e["tag"] = t; e["part"] = part(t); e["day"] = t[:10]; e["cat"] = cat(e["ev"])
            e["cl"] = e["ev"]
            e["days"] = days_left(e)
            E.append(e)
    rows = []
    for fam in ["B1", "B2", "C1", "C2"]:
        for pt in ["early", "late"]:
            X = [e for e in E if e["fam"] == fam and e["part"] == pt]
            H = hours[pt] or 1
            p(f"\n== {fam} {pt}: hours {H}, episodes (net>0, size>=5) {len(X)} in {len(set(e['ev'] for e in X))} events;"
              f" per day {len(X) * 24 / H:.1f}")
            if not X:
                continue
            d = np.array([e["dur"] for e in X])
            p(f"   duration s: median {np.median(d):.2f} p75 {np.percentile(d, 75):.2f} p90 {np.percentile(d, 90):.1f} max {d.max():.0f};"
              f" >=1s {np.mean(d >= 1):.2f} >=5s {np.mean(d >= 5):.2f} censored {sum(e['cens'] for e in X)}")
            p(f"   net per set at start: median {np.median([e['net0'] for e in X]) * 100:.2f}c, mean {np.mean([e['net0'] for e in X]) * 100:.2f}c;"
              f" size at start median {np.median([e['size0'] for e in X]):.1f} sets; stale-book flag {np.mean([e['mism0'] > 0 for e in X]):.2f}")
            p("   by category:", dict(collections.Counter(e["cat"] for e in X)))
            for R in [1, 2, 5, 10]:
                Y = [e for e in X if e.get(f"R{R}")]
                Yc = [e for e in Y if e["mism0"] == 0]
                tot20 = sum(e[f"R{R}"]["pnl20"] for e in Yc); tot5 = sum(e[f"R{R}"]["pnl5"] for e in Yc)
                p(f"   R={R:>2}s takeable {len(Y)} (clean book {len(Yc)}, events {len(set(e['ev'] for e in Yc))}) per day {len(Yc) * 24 / H:.1f};"
                  f" sum pnl $20-size {tot20:.2f} (per day {tot20 * 24 / H:.2f}), $5-size {tot5:.2f} (per day {tot5 * 24 / H:.2f})")
                if R == 5 and Y:
                    ta = sum(e["R5"]["pnl20"] for e in Y)
                    ma, la, ha = boot_mean_by_cluster([e["R5"]["pnl20"] for e in Y], [e["cl"] for e in Y])
                    p(f"      sensitivity, stale-flagged included: {len(Y)} takeable in {len(set(e['ev'] for e in Y))} events, per day {len(Y) * 24 / H:.1f};"
                      f" mean pnl $20 {ma:.3f} [{la:.3f}, {ha:.3f}], per day {ta * 24 / H:.2f};"
                      f" median R5 net per set {np.median([e['R5']['net'] for e in Y]) * 100:.2f}c; prints {np.mean([e['prints'] > 0 for e in Y]):.2f}")
                    Yf = [e for e in Y if e["field_ok"]]
                    if Yf:
                        mf, lf, hf = boot_mean_by_cluster([e["R5"]["pnl20"] for e in Yf], [e["cl"] for e in Yf])
                        p(f"      exchange-field check at t0+5s (price-only, any book flag): {len(Yf)} of {len(Y)} confirmed, {len(set(e['ev'] for e in Yf))} events,"
                          f" per day {len(Yf) * 24 / H:.1f}; mean pnl $20 {mf:.3f} [{lf:.3f}, {hf:.3f}]; per day {sum(e['R5']['pnl20'] for e in Yf) * 24 / H:.2f};"
                          f" clean-book among them {sum(e['mism0'] == 0 for e in Yf)}")
                    else:
                        p(f"      exchange-field check at t0+5s: 0 of {len(Y)} confirmed")
                if R == 5 and Yc:
                    m, lo, hi = boot_mean_by_cluster([e["R5"]["pnl20"] for e in Yc], [e["cl"] for e in Yc])
                    tt, tlo, thi = boot_total_by_cluster([e["R5"]["pnl20"] * 24 / H for e in Yc], [e["cl"] for e in Yc])
                    m5, lo5, hi5 = boot_mean_by_cluster([e["R5"]["pnl5"] for e in Yc], [e["cl"] for e in Yc])
                    nps = [e["R5"]["net"] for e in Yc]
                    p(f"      R5 mean pnl per trade $20: {m:.3f} [{lo:.3f}, {hi:.3f}]  $5: {m5:.3f} [{lo5:.3f}, {hi5:.3f}]"
                      f"  net per set median {np.median(nps) * 100:.2f}c; per-day total $20 {tt:.2f} [{tlo:.2f}, {thi:.2f}]")
                    p(f"      R5 sets at $20 median {np.median([e['R5']['sets20'] for e in Yc]):.1f}; cost/set median {np.median([e['R5']['cost'] for e in Yc]):.3f};"
                      f" with prints during episode {np.mean([e['prints'] > 0 for e in Yc]):.2f};"
                      f" same leg starts and ends it {np.mean([bool(e['trig_end']) and set(e['trig_start']) == set(e['trig_end']) for e in Yc]):.2f}")
                    byev = collections.Counter()
                    for e in Yc:
                        byev[e["ev"]] += e["R5"]["pnl20"]
                    top = byev.most_common(3); tot = sum(byev.values()) or 1
                    dl = np.array([e["days"] for e in Yc])
                    p(f"      days from episode to event end (capital lock for B1/C): median {np.nanmedian(dl):.1f}, share <= 1 day {np.mean(dl <= 1):.2f}")
                    p(f"      concentration: top event {top[0][0]} {top[0][1] / tot:.2f}; top3 {sum(v for _, v in top) / tot:.2f}")
                    for e in Yc:
                        rows.append([fam, pt, e["tag"], e["ev"], e["cat"], e["n_legs"], round(e["dur"], 2), round(e["net0"], 4),
                                     round(e["R5"]["net"], 4), round(e["R5"]["size"], 1), round(e["R5"]["cost"], 3),
                                     round(e["R5"]["pnl5"], 3), round(e["R5"]["pnl20"], 3), e["prints"], round(e["days"], 2)])
    # descriptive: by day (21-22 Nov = Saturday-Sunday)
    hd = collections.Counter(t[:10] for t in tags)
    p("\nby day (hours; R5 clean takeable episodes / sum pnl $20) per family:")
    for dday in sorted(hd):
        cells = []
        for fam in ["B1", "B2", "C1", "C2"]:
            Y = [e for e in E if e["fam"] == fam and e["day"] == dday and e.get("R5") and e["mism0"] == 0]
            cells.append(f"{fam} {len(Y)}/{sum(e['R5']['pnl20'] for e in Y):.2f}")
        p(f"   {dday} hours {hd[dday]}: " + "; ".join(cells))
    with open(f"{OUT}/episodes_R5.csv", "w") as fh:
        fh.write("fam,part,hour,event,cat,legs,dur_s,net0,net_R5,size_R5,cost_R5,pnl5,pnl20,prints,days_to_end\n")
        for r in rows:
            fh.write(",".join(str(x) for x in r) + "\n")
    open(f"{OUT}/report.txt", "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
