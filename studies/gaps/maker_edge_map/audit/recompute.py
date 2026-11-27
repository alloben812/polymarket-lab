"""Independent recompute of the V2 touch-maker markouts (audit). Pure python + stdlib, written from protocol.md only.
usage: python3 -I recompute.py <sample.json> <family> <half> [offset_ticks] [mode strict|at] [volfilter_cents]"""
import gzip, json, sys, math, bisect, datetime as dt

D = "/home/user/polymarket-lab/data/gaps_maker_edge"

def parse(s):
    s = s.strip().replace(" ", "T")
    if s.endswith("Z"): s = s[:-1] + "+00:00"
    elif s.endswith("+00"): s += ":00"
    return dt.datetime.fromisoformat(s).timestamp()

def load(r):
    rows = [json.loads(l) for l in gzip.open(f"{D}/tapes/{r['conditionId']}.jsonl.gz", "rt")]
    tok0 = json.loads(r["outcomes"])[0]
    P = []
    for q in rows:
        x = q["p"] if q["o"] == tok0 else 1 - q["p"]
        ask = (q["s"] == "BUY") == (q["o"] == tok0)      # aggressor bought token0
        P.append((q["t"] - 3.0, x, ask, q["z"]))
    P.sort(key=lambda a: a[0])
    return P

class Book:
    def __init__(s, P):
        s.A = [(t, x) for t, x, a, z in P if a]; s.B = [(t, x) for t, x, a, z in P if not a]
        s.At = [t for t, x in s.A]; s.Bt = [t for t, x in s.B]
    @staticmethod
    def last(L, Ts, T, stale):
        i = bisect.bisect_right(Ts, T) - 1
        if i < 0 or T - L[i][0] > stale: return None
        return L[i][1]
    def ask(s, T, st): return s.last(s.A, s.At, T, st)
    def bid(s, T, st): return s.last(s.B, s.Bt, T, st)

def run(sample, fam, half, off=0, mode="strict", volf=None, which="V2"):
    num = {"fin": [], "m30": [], "m300": []}; den = {"fin": [], "m30": [], "m300": []}; usd = {"fin": [], "m30": []}
    nfill = 0
    for r in sample:
        if r["family"] != fam or r["half"] != half: continue
        P = load(r)
        if not P: continue
        pay0 = float(r["payout"][0]); tres = parse(r.get("closedTime") or r["endDate"]); tick = float(r.get("orderPriceMinTickSize") or 0.01)
        bk = Book(P)
        def mid0(T):
            if T >= tres: return pay0
            a, b = bk.ask(T, 3600), bk.bid(T, 3600)
            return None if a is None or b is None else (a + b) / 2
        t0 = P[0][0]; k = 0
        mnum = {"fin": 0.0, "m30": 0.0, "m300": 0.0}; mden = {"fin": 0.0, "m30": 0.0, "m300": 0.0}; mus = {"fin": 0.0, "m30": 0.0}
        tt = [p[0] for p in P]
        while t0 + 10 * k < tres:
            tau = t0 + 10 * k; k += 1
            b, a = bk.bid(tau, 900), bk.ask(tau, 900)
            if b is None or a is None: continue
            b = round(b / tick) * tick; a = round(a / tick) * tick
            if not (a > b + 1e-9 and b > 1e-9 and a < 1 - 1e-9): continue
            if volf is not None:  # skip when the last print moved more than volf cents vs 30 s earlier (uses only past prints)
                m_now = (bk.ask(tau, 900) + bk.bid(tau, 900)) / 2; pa, pb_ = bk.ask(tau - 30, 900), bk.bid(tau - 30, 900)
                if pa is not None and pb_ is not None and abs(m_now - (pa + pb_) / 2) * 100 > volf: continue
            bb = b - off * tick; aa = a + off * tick
            lo, hi = tau + 2, tau + 10
            i = bisect.bisect_right(tt, lo)
            fb = fa = False
            while i < len(P) and tt[i] <= hi:
                t, x, isask, z = P[i]; i += 1
                if not isask and not fb and (x < bb - 1e-9 if mode == "strict" else x <= bb + 1e-9):
                    fb = True; fills = [(t, 0, bb, z)]
                elif isask and not fa and (x > aa + 1e-9 if mode == "strict" else x >= aa - 1e-9):
                    fa = True; fills = [(t, 1, 1 - aa, z)]
                else: continue
                for (tf, tok, q, zz) in fills:
                    sh = min(10.0 / q, zz); nfill += 1
                    payX = pay0 if tok == 0 else 1 - pay0
                    vals = {"fin": payX - q}
                    for h in (30, 300):
                        m = mid0(tf + h)
                        vals[f"m{h}"] = None if m is None else ((m if tok == 0 else 1 - m) - q)
                    for key, v in vals.items():
                        if v is None: continue
                        mnum[key] += v * sh; mden[key] += sh
                        if key in mus: mus[key] += q * sh   # dollars paid (for %$)
        for key in num:
            if mden[key] > 0: num[key].append(mnum[key]); den[key].append(mden[key])
    res = {"fills": nfill}
    for key in num:
        n = len(num[key]); D_ = sum(den[key])
        if n < 2 or D_ == 0: res[key] = (float("nan"),) * 3 + (n,); continue
        rr = sum(num[key]) / D_
        se = math.sqrt(n / (n - 1) * sum((a - rr * b) ** 2 for a, b in zip(num[key], den[key]))) / D_
        res[key] = (100 * rr, 100 * 1.96 * se, n)
    return res

if __name__ == "__main__":
    sp, fam, half = sys.argv[1:4]
    off = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    mode = sys.argv[5] if len(sys.argv) > 5 else "strict"
    volf = float(sys.argv[6]) if len(sys.argv) > 6 else None
    S = json.load(open(f"{D}/{sp}"))
    R = run(S, fam, half, off, mode, volf)
    print(fam, half, "off", off, mode, "volf", volf, "fills", R["fills"],
          " ".join(f"{k}={v[0]:+.2f}±{v[1]:.2f}(n={v[2]})" for k, v in R.items() if k != "fills"))
