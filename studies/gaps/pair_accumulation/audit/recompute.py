"""Independent recomputation (no pmlab imports, no code from the study). Raw tapes + gamma meta JSON only.
Usage: python3 -I recompute.py   (run from anywhere)"""
import gzip, json, os, sys, math
from collections import defaultdict
ROOT = "/home/user/polymarket-lab/data"
T0 = 1795219200                      # 2026-11-21 00:00 UTC (checked with datetime)
T1 = T0 + 6 * 86400
SPLIT = T0 + 4 * 86400
DUR = {"5m": 300, "15m": 900, "1h": 3600}
SER = [("btc","5m",1),("eth","5m",1),("sol","5m",1200),("xrp","5m",1200),("btc","15m",1),("eth","15m",1),
       ("sol","15m",1),("xrp","15m",1),("btc","1h",1),("eth","1h",1),("sol","1h",1),("xrp","1h",1)]
LV = [0.45, 0.40, 0.30, 0.05]

def hit_prices(rows, lag):
    """yield (match_time, outcome, price) for 'a resting bid on outcome at >= price was hit'.
    Own derivation: taker SELL of X at p lifts bids on X at <= p. Taker BUY of Y at q is matched against asks of Y
    or (by minting) against bids on the complement at 1-q, so a bid on other(Y) at >= 1-q was hit."""
    for r in rows:
        t = r["t"] - lag
        if r["s"] == "SELL":
            yield t, r["o"], r["p"]
        else:
            yield t, ("Down" if r["o"] == "Up" else "Up"), 1.0 - r["p"]

def ask_prices(rows, lag):
    for r in rows:
        t = r["t"] - lag
        if r["s"] == "BUY":
            yield t, r["o"], r["p"]
        else:
            yield t, ("Down" if r["o"] == "Up" else "Up"), 1.0 - r["p"]

def run(lag=3, skip=True, strict=True, series=SER, out=None):
    res = defaultdict(list)   # (series,L) -> list of (t0, net)
    legs = defaultdict(lambda: [0, 0, 0.0])  # (L): filled legs, won legs, pnl per share sum
    nm = 0
    for asset, dur, grid in series:
        step = DUR[dur]
        for t0 in range(T0, T1, step):
            if t0 % grid: continue
            mp = f"{ROOT}/updown_meta/{asset}/{dur}/{t0}.json"
            if not os.path.exists(mp): continue
            m = json.load(open(mp))
            if m.get("up_won") is None: continue
            tp = f"{ROOT}/tape/{m['condition']}.jsonl.gz"
            if not os.path.exists(tp): continue
            rows = [json.loads(x) for x in gzip.open(tp, "rt")]
            t1 = t0 + step
            hits = [(t, o, p) for t, o, p in hit_prices(rows, lag) if t0 <= t < t1]
            pre = [(t, o, p) for t, o, p in ask_prices(rows, lag) if t0 - 30 <= t < t0]
            won = {"Up": 1.0 if m["up_won"] else 0.0, "Down": 0.0 if m["up_won"] else 1.0}
            nm += 1
            for L in LV:
                S = 10.0 / L
                net = 0.0
                for X in ("Up", "Down"):
                    if skip and any(o == X and p <= L + 1e-9 for t, o, p in pre): continue
                    f = any(o == X and (p < L - 1e-9 if strict else p <= L + 1e-9) for t, o, p in hits)
                    if f:
                        net += S * (won[X] - L)
                        legs[L][0] += 1; legs[L][1] += won[X]; legs[L][2] += won[X] - L
                res[(f"{asset}-{dur}", L)].append((t0, net))
    return res, legs, nm

def cl(vals):  # vals: list of (t0, net); cluster by UTC hour
    n = len(vals); mean = sum(v for _, v in vals) / n
    g = defaultdict(float)
    for t, v in vals: g[t // 3600] += v - mean
    G = len(g); se = math.sqrt(sum(x * x for x in g.values()) * G / (G - 1)) / n
    return mean, se, mean / se

if __name__ == "__main__":
    lines = []
    def rep(tag, **kw):
        res, legs, nm = run(**kw)
        lines.append(f"## {tag}  (markets read: {nm})")
        for L in LV:
            allv = [x for (s, l), v in res.items() if l == L for x in v]
            m, se, t = cl(allv)
            early = [x for x in allv if x[0] < SPLIT]; late = [x for x in allv if x[0] >= SPLIT]
            me, _, te = cl(early); ml, _, tl = cl(late)
            fl, wl, pps = legs[L]
            lines.append(f"L={L}: n={len(allv)} net/window={m:+.3f} (se {se:.3f}, t {t:+.1f}) early {me:+.3f} (t {te:+.1f}) late {ml:+.3f} (t {tl:+.1f}) | filled legs {fl}, win rate {wl/max(fl,1):.3f}, net/share {pps/max(fl,1):+.4f}")
        print("\n".join(lines[-5:]), flush=True)
    rep("A. replicate: lag 3, skip, strict (all 12 series)")
    rep("B. no placement skip", skip=False)
    rep("C. lag 0", lag=0)
    rep("D. lag 6", lag=6)
    rep("E. touch (<=) fills", strict=False)
    rep("F. touch + no skip + lag 0 (most generous)", strict=False, skip=False, lag=0)
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "recompute_out.txt"), "w").write("\n".join(lines) + "\n")
