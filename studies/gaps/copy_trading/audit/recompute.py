"""Independent recompute of the d10/d60/d300 HOLD late-window return from raw cache (no import of analyze.py / pmlab.updown).
Run: python3 -I recompute.py"""
import gzip, json, math, collections, random, sys
C = "/home/user/polymarket-lab/data/gaps_copy/"
def L(p):
    return json.load(gzip.open(p, "rt"))
sample = json.load(open(C + "sample.json")); meta = json.load(open(C + "meta.json")); res = json.load(open(C + "resolutions.json"))
late = [e for e in sample if e["win"] == "late"]
print("late entries", len(late))
def rate(m):
    if m is None: return 0.05, "fallback"
    if m.get("feesEnabled") is False: return 0.0, "off"
    r = (m.get("feeSchedule") or {}).get("rate")
    return (float(r), "gamma") if r is not None else (0.05, "fallback")
def ratio_cluster(num, den):
    n = len(num); D = sum(den); r = sum(num) / D
    var = n / (n - 1) * sum((a - r * b) ** 2 for a, b in zip(num, den)) / D ** 2
    return r, math.sqrt(var)
def evaluate(d, mode="print", stale=None, filt=None):
    rows_out = []
    srcs = collections.Counter()
    for e in late:
        if filt and not filt(e): continue
        c, x, tb, w = e["c"], e["o"], e["t"], e["wallet"]
        try: tp = L(C + f"tape/{c}.json.gz")
        except Exception: continue
        rz = res.get(c) or {}
        fin = (rz.get("final") or {}).get(x)
        resolved = bool(rz.get("resolved")) and fin is not None
        tape = tp["rows"]
        def bp(r):  # price at which x could be bought, from this print
            if r["s"] == "BUY" and r["o"] == x: return r["p"]
            if r["s"] == "SELL" and r["o"] != x: return 1 - r["p"]
        # payoff
        if resolved: pay = float(fin)
        else:
            last = None; lt = -1
            for r in tape:
                if r["o"] == x: p = r["p"]
                else: p = 1 - r["p"]
                if r["t"] > lt: lt, last = r["t"], p
            if last is None: continue
            pay = last
        rt, src = rate(meta.get(c)); srcs[src] += 1
        if mode == "print":
            blk = collections.defaultdict(lambda: [0.0, 0.0])
            for r in tape:
                p = bp(r)
                if p is None: continue
                if tb + d <= r["t"] - 3 <= tb + d + 30:
                    blk[r["t"]][0] += p * r["z"]; blk[r["t"]][1] += r["z"]
            if not blk: rows_out.append(dict(e=e, filled=False)); continue
            T = min(blk); val, z = blk[T]; v = val / z
            q = min(10 / v, z)
        else:  # 'stale': last buyable print with match time <= tb+d and >= tb+d-stale (diagnostic, no future info)
            best = None
            for r in tape:
                p = bp(r)
                if p is None: continue
                mt = r["t"] - 3
                if tb + d - stale <= mt <= tb + d - 0 and (best is None or r["t"] > best[0]): best = (r["t"], p, r["z"])
            if best is None: rows_out.append(dict(e=e, filled=False)); continue
            v = best[1]; q = 10 / v
        if q * v < 1: rows_out.append(dict(e=e, filled=False)); continue
        cost = q * v + q * rt * v * (1 - v)
        rows_out.append(dict(e=e, filled=True, cost=cost, net=q * pay - cost, v=v, resolved=resolved, c=c))
    return rows_out, srcs
def summarize(rows, label):
    f = [r for r in rows if r["filled"]]
    by = collections.defaultdict(lambda: [0.0, 0.0])
    for r in f: by[r["c"]][0] += r["net"]; by[r["c"]][1] += r["cost"]
    num = [v[0] for v in by.values()]; den = [v[1] for v in by.values()]
    r, se = ratio_cluster(num, den)
    print(f"{label}: entries {len(rows)} filled {len(f)} ({len(f)/max(1,len(rows)):.0%}) markets {len(by)} spent {sum(den):.0f} net {sum(num):+.0f} ret {r:+.1%} se {se:.1%} t {r/se:+.2f}")
    return r
if __name__ == "__main__":
    for d in (10, 60, 300):
        rows, srcs = evaluate(d); summarize(rows, f"d{d} hold (print rule)")
    print("fee rate sources (d300 pass)", dict(srcs))
