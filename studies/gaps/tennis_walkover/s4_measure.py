"""Step 4: W1, W2, W4, W5, W6 for class A (and t_first for class B). Writes out/events_A.json, out/events_B.json,
out/w4_prints.json and prints the tables (redirect to out/s4_tables.txt)."""
import collections, json, statistics, sys
from pmlab import updown
from common import *

STAV = "0xf5fe759cece500f58a431ef8dacea321f6e3e23d"
BUCKETS = [("pre5m", -300, -1e-9), ("0-10s", 0, 10), ("10-60s", 10 + 1e-9, 60), ("1-5m", 60 + 1e-9, 300), ("5-30m", 300 + 1e-9, 1800)]


def load_stream(m):
    if not m.get("vol"):
        return []
    tp = updown.tape(m["cid"])
    pr = prints(tp, m["outcomes"])
    add_reference(pr)
    return pr


def measure_event(r, cls):
    ml = next(m for m in r["markets"] if m["cid"] == r["ml"])
    streams = {m["cid"]: load_stream(m) for m in r["markets"]}
    out = {"slug": r["slug"], "title": r["title"], "series": r["series"], "cls": cls, "start": ml["start"] or r["startTime"],
           "closed": ml["closed"], "ml_vol": ml["vol"], "n_markets": len(r["markets"]),
           "n_markets_traded": sum(1 for v in streams.values() if v), "ml_prints": len(streams[ml["cid"]])}
    tf = None
    src = None
    if cls == "A":
        h = hindsight_t_first(streams[ml["cid"]])
        if h:
            tf, src = h, ml["cid"]
            out.update({"fav": h["fav"], "und": h["r"], "first_x": h["x"], "strays": h["strays"], "tf_src": "moneyline"})
    if tf is None:
        cands = []
        for m in r["markets"]:
            if m["cid"] == ml["cid"] and cls == "A":
                continue
            if tuple(m.get("api_final") or ()) != (0.5, 0.5):
                continue
            h = hindsight_t_first(streams[m["cid"]])
            if h:
                cands.append((h["t"], m["cid"], h, m["type"]))
        if cands:
            cands.sort()
            tf, src = cands[0][2], cands[0][1]
            out.update({"tf_src": cands[0][3], "first_x": tf["x"], "und_src": tf["r"]})
    if tf is None:
        out["t_first"] = None
        why = "no tape" if not any(streams.values()) else ("no moneyline tape" if not streams[ml["cid"]] else "no qualifying move")
        out["no_tf_reason"] = why
        if streams[ml["cid"]]:
            pr = streams[ml["cid"]]
            out["ml_first_a"] = pr[0]["a"]
            out["ml_last_a"] = pr[-1]["a"]
            out["ml_min_dist"] = min(abs(x["a"] - 0.5) for x in pr)
        return out, []
    t0 = tf["t"]
    out["t_first"] = t0
    out["w5_to_close"] = (ml["closed"] - t0) if ml["closed"] else None
    out["start_minus_tf"] = (out["start"] - t0) if out["start"] else None
    # t_50
    t50 = next((x["t"] for x in streams[src] if x["t"] >= t0 and 0.48 - 1e-9 <= x["a"] <= 0.52 + 1e-9), None)
    out["t_50"] = t50
    out["tf_to_t50"] = (t50 - t0) if t50 is not None else None
    # W4 prints
    w4 = []
    for m in r["markets"]:
        for x in streams[m["cid"]]:
            dt_ = x["t"] - t0
            if -300 <= dt_ <= 1800 and x["bp"] < 0.45 - 1e-9:
                w4.append({"slug": r["slug"], "ml": m["cid"] == ml["cid"], "type": m["type"], "dt": dt_, "p": x["bp"], "z": x["z"], "w": x["w"],
                           "final": (m.get("api_final") or [None, None])[x["bo"]]})
    for name, lo, hi in BUCKETS:
        sel = [x for x in w4 if lo <= x["dt"] <= hi]
        out[f"w4_{name}_usd"] = sum(x["z"] * x["p"] for x in sel)
        out[f"w4_{name}_sh"] = sum(x["z"] for x in sel)
        out[f"w4_{name}_usd_ml"] = sum(x["z"] * x["p"] for x in sel if x["ml"])
    post = [x for x in w4 if x["dt"] >= 0]
    if post:
        first_t = min(x["dt"] for x in post)
        out["w4_first_dt"] = first_t
        out["w4_first_wallets"] = sorted({x["w"] for x in post if x["dt"] == first_t})
    # W6
    sell = buy = tot = 0.0
    if t50 is not None and ml["closed"]:
        for m in r["markets"]:
            for x in streams[m["cid"]]:
                if t50 <= x["t"] <= ml["closed"]:
                    tot += x["z"] * x["p"]
                    if x["s"] == "SELL" and 0.48 - 1e-9 <= x["p"] <= 0.495 + 1e-9:
                        sell += x["z"] * x["p"]
                    elif x["s"] == "BUY" and 0.505 - 1e-9 <= x["p"] <= 0.52 + 1e-9:
                        buy += x["z"] * (1 - x["p"])
    out["w6_sell_usd"], out["w6_buy_usd"], out["w6_all_usd_after_t50"] = sell, buy, tot
    return out, w4


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return float("nan")
    k = (len(xs) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def fmt_t(s):
    if s is None or s != s:
        return "n/a"
    s = float(s)
    a = abs(s)
    if a < 120:
        return f"{s:.0f} s"
    if a < 7200:
        return f"{s / 60:.1f} min"
    return f"{s / 3600:.1f} h"


def main():
    U = json.load(open(DATA / "universe.json"))
    only = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else None
    res = {"A": [], "B": []}
    allw4 = []
    for cls in ("A", "B"):
        for r in U[cls]:
            if only and only not in r["slug"]:
                continue
            o, w4 = measure_event(r, cls)
            res[cls].append(o)
            if cls == "A":
                allw4 += w4
    if only:
        for cls in res:
            for o in res[cls]:
                print(json.dumps({k: (iso(v) if k in ("t_first", "t_50", "start", "closed") else v) for k, v in o.items()}, indent=1))
        return
    json.dump(res["A"], open(OUT / "events_A.json", "w"))
    json.dump(res["B"], open(OUT / "events_B.json", "w"))
    json.dump(allw4, open(OUT / "w4_prints.json", "w"))

    A = res["A"]
    print(f"class A events {len(A)}; with any traded market {sum(1 for o in A if o['n_markets_traded'])}; with moneyline tape {sum(1 for o in A if o['ml_prints'])}; with t_first {sum(1 for o in A if o['t_first'])}")
    print("t_first source:", dict(collections.Counter(o.get("tf_src") for o in A if o["t_first"])))
    print("no t_first reasons:", dict(collections.Counter(o.get("no_tf_reason") for o in A if not o["t_first"])))
    nq = [o for o in A if o.get("no_tf_reason") == "no qualifying move"]
    print("  of 'no qualifying move': moneyline never within 0.05 of 0.50:", sum(1 for o in nq if o.get("ml_min_dist", 0) > 0.05),
          "; first print already within 0.05 of 0.50:", sum(1 for o in nq if abs(o.get("ml_first_a", 0) - 0.5) <= 0.05))
    T = [o for o in A if o["t_first"]]
    print("by series (all / with t_first):", {s: (sum(1 for o in A if o["series"] == s), sum(1 for o in T if o["series"] == s)) for s in sorted({o["series"] for o in A})})
    M = [o for o in T if o.get("tf_src") == "moneyline"]
    print(f"\nW1 (moneyline t_first, n={len(M)}): underdog before the news median {statistics.median(o['und'] for o in M):.3f} "
          f"(p10 {pct([o['und'] for o in M], .1):.3f}, p90 {pct([o['und'] for o in M], .9):.3f}); favourite median {statistics.median(o['fav'] for o in M):.3f}")
    print("   underdog buckets:", {b: sum(1 for o in M if lo <= o["und"] < hi) for b, lo, hi in [("<0.15", 0, .15), ("0.15-0.30", .15, .30), ("0.30-0.40", .30, .40), ("0.40-0.45", .40, .4500001)]})
    print(f"   first move print price (underdog terms) median {statistics.median(o['first_x'] for o in M):.3f}")
    x = [o["tf_to_t50"] for o in T if o["tf_to_t50"] is not None]
    print(f"\nt_first -> first print within 0.48-0.52 (n={len(x)} of {len(T)}): median {fmt_t(statistics.median(x))}, p25 {fmt_t(pct(x, .25))}, p75 {fmt_t(pct(x, .75))}, p90 {fmt_t(pct(x, .9))}; "
          f"<=10 s {sum(1 for v in x if v <= 10)}, <=60 s {sum(1 for v in x if v <= 60)}, <=5 min {sum(1 for v in x if v <= 300)}, <=30 min {sum(1 for v in x if v <= 1800)}")
    x = [o["w5_to_close"] for o in T if o["w5_to_close"] is not None]
    print(f"W5 t_first -> resolution (n={len(x)}): median {fmt_t(statistics.median(x))}, p25 {fmt_t(pct(x, .25))}, p75 {fmt_t(pct(x, .75))}, p90 {fmt_t(pct(x, .9))}, max {fmt_t(max(x))}")
    x = [o["start_minus_tf"] for o in T if o["start_minus_tf"] is not None]
    print(f"scheduled start - t_first (n={len(x)}): median {fmt_t(statistics.median(x))}, p25 {fmt_t(pct(x, .25))}, p75 {fmt_t(pct(x, .75))}; t_first after the scheduled start in {sum(1 for v in x if v < 0)} events")

    print("\nW4: buyable below 0.45 around t_first (all markets of the event; class A events with t_first)")
    print("bucket | events with any | shares | dollars | vwap | dollars moneyline only | wallets | top3 share")
    for name, lo, hi in BUCKETS:
        sel = [p for p in allw4 if lo <= p["dt"] <= hi]
        usd = sum(p["z"] * p["p"] for p in sel)
        sh = sum(p["z"] for p in sel)
        byw = collections.Counter()
        for p in sel:
            byw[p["w"]] += p["z"] * p["p"]
        top3 = sum(v for _, v in byw.most_common(3)) / usd if usd else float("nan")
        print(f"{name} | {len({p['slug'] for p in sel})} | {sh:,.0f} | {usd:,.0f} | {usd / sh if sh else float('nan'):.3f} | {sum(p['z'] * p['p'] for p in sel if p['ml']):,.0f} | {len(byw)} | {top3:.2f}")
    post = [p for p in allw4 if p["dt"] >= 0]
    usd = sum(p["z"] * p["p"] for p in post)
    byw = collections.Counter()
    for p in post:
        byw[p["w"]] += p["z"] * p["p"]
    print(f"total 0-30 min: ${usd:,.0f} over {len({p['slug'] for p in post})} events, {len(byw)} wallets; per month ${usd / MONTHS:,.0f}")
    print("top 10 takers (0-30 min, dollars, share, events):")
    for w, v in byw.most_common(10):
        print(f"   {w} {v:,.0f} {v / usd:.3f} {len({p['slug'] for p in post if p['w'] == w})}" + ("  <- Stavenson" if w == STAV else ""))
    gross = sum(p["z"] * (0.5 - p["p"]) for p in post if p["final"] == 0.5)
    fees = sum(p["z"] * fee_ps(p["p"]) for p in post)
    print(f"gross gain of those takers at 0.50 payoff ${gross:,.0f}, fees ${fees:,.0f}; prints whose market did not resolve 0.5: {sum(1 for p in post if p['final'] != 0.5)}")
    fw = collections.Counter()
    nfirst = 0
    for o in T:
        if o.get("w4_first_wallets"):
            nfirst += 1
            for w in o["w4_first_wallets"]:
                fw[w] += 1
    print(f"first taker below 0.45 at/after t_first: {nfirst} events; wallets that were first (co-first counted):")
    for w, c in fw.most_common(8):
        print(f"   {w} {c}" + ("  <- Stavenson" if w == STAV else ""))
    print(f"   distinct first wallets {len(fw)}")
    print("W4 by underdog-before bucket (moneyline t_first events): n | median $ 0-30m | sum $")
    for b, lo, hi in [("<0.15", 0, .15), ("0.15-0.30", .15, .30), ("0.30-0.40", .30, .40), ("0.40-0.45", .40, .4500001)]:
        g = [o for o in M if lo <= o["und"] < hi]
        v = [sum(o[f"w4_{n}_usd"] for n in ("0-10s", "10-60s", "1-5m", "5-30m")) for o in g]
        if g:
            print(f"   {b}: {len(g)} | {statistics.median(v):,.0f} | {sum(v):,.0f}")

    s, b, tot = sum(o.get("w6_sell_usd", 0) for o in T), sum(o.get("w6_buy_usd", 0) for o in T), sum(o.get("w6_all_usd_after_t50", 0) for o in T)
    print(f"\nW6 resting-bid leg (t_50 -> resolution, all markets): taker sells at 0.48-0.495 ${s:,.0f}; taker buys at 0.505-0.52 (maker holds the other side at 0.48-0.495) ${b:,.0f}; "
          f"together ${s + b:,.0f} = ${(s + b) / MONTHS:,.0f} a month; all dollars printed after t_50 ${tot:,.0f}; events with any {sum(1 for o in T if o.get('w6_sell_usd', 0) + o.get('w6_buy_usd', 0) > 0)}")
    Bv = res["B"]
    print(f"\nclass B events {len(Bv)}; with t_first {sum(1 for o in Bv if o['t_first'])}; t_first source {dict(collections.Counter(o.get('tf_src') for o in Bv if o['t_first']))}")


if __name__ == "__main__":
    main()
