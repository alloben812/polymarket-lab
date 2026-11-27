"""Audit step 3: independent re-implementation of the causal follower (protocol 2.6) and the hindsight class A line
(2.3 + 2.5), from raw tapes and raw gamma metadata. Does not import the study's common.py or s*.py."""
import gzip, json, os, math, statistics, collections, datetime as dt, bisect, sys
SC = "/tmp/claude-0/-home-user/05556429-066d-541b-b886-b8da26bcc648/scratchpad/"
TD = "/home/user/polymarket-lab/data/tape/"
U = json.load(open(SC + "aud_universe.json")); K = U["k"]
LAG, FEE, CAP, PMAX, WIN = 3, 0.05, 300.0, 0.46, 1800
D_ = [10, 60, 300, 900]
P1 = dt.datetime(2026, 11, 25, 23, 59, 59, tzinfo=dt.timezone.utc).timestamp()
E = 1e-9

def tape(cid, outs):
    p = TD + cid + ".jsonl.gz"
    if not os.path.exists(p): return []
    out = []
    for l in gzip.open(p, "rt"):
        x = json.loads(l)
        if x["o"] not in outs: continue
        i = outs.index(x["o"]); p_ = x["p"]
        a = p_ if i == 0 else 1 - p_                       # price of outcome 0
        bo, bp = (i, p_) if x["s"] == "BUY" else (1 - i, 1 - p_)  # what a taker could buy
        out.append([x["t"] - LAG, a, bo, bp, x["z"], x["w"]])
    out.sort(key=lambda r: r[0])                           # stable: keeps file order within a second
    T = [r[0] for r in out]
    ref = []
    for j, r in enumerate(out):
        hi = bisect.bisect_right(T, r[0] - 120); lo = bisect.bisect_left(T, r[0] - 21600)
        w = [out[q][1] for q in range(lo, hi)]
        if len(w) < 3: w = [out[q][1] for q in range(max(0, hi - 3), hi)]
        if not w: ref.append(None); continue
        R = statistics.median(w); und = 0 if R < 0.5 else 1; rr = min(R, 1 - R)
        xx = r[1] if und == 0 else 1 - r[1]
        ref.append((und, rr, xx, rr <= 0.45 + E and xx >= rr + 0.05 - E))
    return out, ref

def rule(streams, starts, cap=CAP, pmax=PMAX, only_side=None):
    ev = []
    for k, (pr, fin) in enumerate(streams):
        for j, r in enumerate(pr):
            if r[3] <= pmax + E and any(s <= r[0] <= s + WIN for s in starts):
                ev.append((r[0], k, j, r, fin))
    ev.sort(key=lambda e: e[:3])
    left = cap; cost = fee = pay = sh = 0.0; nf = 0
    for t, k, j, r, fin in ev:
        if left <= E: break
        p = r[3]; f = FEE * p * (1 - p); q = min(r[4], left / (p + f))
        left -= q * (p + f); cost += q * p; fee += q * f; pay += q * fin[r[2]]; sh += q; nf += 1
    return pay - cost - fee, cost, sh, fee

def episodes(pr, ref):
    o = []; last = None
    for j, rf in enumerate(ref):
        if rf and rf[3]:
            if last is None or pr[j][0] - last > 1800: o.append(j)
            last = pr[j][0]
    return o

cache = {}
def get(r):
    if r["cid"] not in cache: cache[r["cid"]] = tape(r["cid"], r["out"])
    return cache[r["cid"]]

def causal_rows(recs, d, filt=None):
    rows = []
    for r in recs:
        res = get(r)
        if not res or not res[0] or r["start"] is None:
            rows.append((r["closed"], 0.0, 0.0, False)); continue
        pr, ref = res
        eps = [j for j in episodes(pr, ref) if pr[j][0] < r["start"] and (filt is None or filt(pr, ref, j))]
        if not eps: rows.append((r["closed"], 0.0, 0.0, False)); continue
        n, c, s, f = rule([(pr, r["fin"])], [pr[j][0] + d for j in eps])
        rows.append((r["closed"], n, c, True))
    return rows

def combine(ra, rc, lo=None):
    if lo is not None:
        ra = [x for x in ra if x[0] >= lo]; rc = [x for x in rc if x[0] >= lo]
    a = [x[1] for x in ra]; c = [x[1] for x in rc]
    tot = sum(a) + K * sum(c)
    se = math.sqrt(len(a) * statistics.variance(a) + K * K * len(c) * statistics.variance(c))
    trig = sum(x[3] for x in ra) + K * sum(x[3] for x in rc)
    return tot, tot / se if se else float("nan"), len(ra), len(rc), sum(a), sum(c), trig

if __name__ == "__main__":
    A = sorted(U["A"], key=lambda r: r["closed"]); S = U["S"]
    cut = A[int(0.67 * len(A))]["closed"]
    print("reporting cut", dt.datetime.fromtimestamp(cut, dt.timezone.utc), "A late", sum(1 for r in A if r["closed"] >= cut))
    filters = {"protocol": None}
    if "--explore" in sys.argv:
        # exploratory, NOT protocol: trigger print itself within 0.47-0.53 of outcome 0 (a sweep to 50-50)
        filters["sweep_to_0.47+"] = lambda pr, ref, j: ref[j][2] >= 0.47 - E
        filters["sweep_to_0.47+_ref<=0.40"] = lambda pr, ref, j: ref[j][2] >= 0.47 - E and ref[j][1] <= 0.40 + E
    for name, fl in filters.items():
        for d in D_:
            ra = causal_rows(A, d, fl); rc = causal_rows(S, d, fl)
            full = combine(ra, rc); late = combine(ra, rc, cut)
            print(f"[{name}] d={d:>3}s  ALL: net {full[0]:9.0f} t {full[1]:5.2f} (A {full[4]:7.0f}, C {full[5]:7.0f} x{K}, triggered {full[6]})"
                  f" | REPORT: net {late[0]:8.0f} t {late[1]:5.2f} (A n={late[2]} {late[4]:6.0f}, C n={late[3]} {late[5]:6.0f} x{K})")
