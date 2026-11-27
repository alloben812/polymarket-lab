"""Independent re-computation (audit). Does not import the author's analyze.py. Reads data/gaps_sports_lag raw tapes.
Recomputes soccer trigger-T d=3 variant: hold, 5-min markout, real round trip; clustered by game (own ratio estimator)."""
import gzip, json, math, bisect, statistics
from collections import defaultdict
from pathlib import Path

D = Path(__file__).resolve().parents[4] / "data" / "gaps_sports_lag"
games = json.load(open(D / "games.json"))
RATE = 0.05
SPLIT = 1795478400  # 2026-11-24 00:00:00 UTC
assert SPLIT == 1795478400 and __import__("datetime").datetime.utcfromtimestamp(SPLIT).isoformat() == "2026-11-24T00:00:00"

def fee(p): return RATE * p * (1 - p)

def tape(cid):
    return [json.loads(l) for l in gzip.open(D / "tapes" / f"{cid}.jsonl.gz", "rt")]

def conv(rows, tok):
    """list of (match_time, price of tok, buyable?, sellable?, shares, wallet) sorted"""
    out = []
    for r in rows:
        mt = r["t"] - 3
        if r["o"] == tok:
            p = r["p"]; buy = r["s"] == "BUY"
        else:
            p = 1 - r["p"]; buy = r["s"] == "SELL"
        out.append((mt, p, buy, not buy, r["z"], r["w"]))
    out.sort(key=lambda x: x[0])
    return out

def sl(c, ts, a, b):
    return c[bisect.bisect_left(ts, a):bisect.bisect_right(ts, b)]

def fav(g, key, ev):
    hs = ev["team_id"] == g["home_id"]
    if key == "home": return "Yes" if hs else "No"
    if key == "away": return "No" if hs else "Yes"
    return "Yes" if abs(ev["after"][0] - ev["after"][1]) < abs(ev["before"][0] - ev["before"][1]) else "No"

def cluster_ratio(num, den):
    n = len(num); r = sum(num) / sum(den)
    res = [a - r * b for a, b in zip(num, den)]
    se = math.sqrt(n / (n - 1) * sum(e * e for e in res)) / sum(den)
    return r, se, r / se

def summarise(tag, rows, key):
    for per in ("early", "late", "all"):
        tt = [r for r in rows if (per == "all" or r["per"] == per) and r[key] is not None]
        num, den = defaultdict(float), defaultdict(float)
        for r in tt:
            num[r["g"]] += r[key] * r["sh"]; den[r["g"]] += r["sh"]
        ks = list(num)
        r, se, t = cluster_ratio([num[k] for k in ks], [den[k] for k in ks])
        print(f"{tag:22s} {key:5s} {per:5s} n={len(tt):4d} games={len(ks):3d} {100*r:6.2f} c/sh se {100*se:5.2f} t {t:5.2f}")

def run(d=3, delay=1, thr=0.03, filt=None, label=None):
    rows = []
    for g in games:
        if g["sport"] != "soccer": continue
        per = "early" if g["t0"] < SPLIT else "late"
        tp = {k: tape(m["cid"]) for k, m in g["markets"].items()}
        ev = g["events"]
        for i, e in enumerate(ev):
            if i and e["t"] - ev[i - 1]["t"] < 180: continue
            te = e["t"]
            for k, m in g["markets"].items():
                tok = fav(g, k, e)
                c = conv(tp[k], tok); ts = [x[0] for x in c]
                pre = sl(c, ts, te - 120, te - 10)
                if not pre: continue
                ppre = statistics.median(x[1] for x in pre)
                if not .05 <= ppre <= .95: continue
                trig = next((x for x in sl(c, ts, te - 30, te + 300) if x[1] >= ppre + thr), None)
                if trig is None: continue
                if filt and not filt(g, k, e, c, ts, trig, ppre): continue
                ta = trig[0] + d + delay
                fl = next((x for x in sl(c, ts, ta, ta + 30) if x[2]), None)
                if fl is None: continue
                p = fl[1]; sh = min(fl[4], 20 / p)
                fin = m["final"][tok]
                mk = sl(c, ts, ta + 240, ta + 360)
                ex = next((x for x in sl(c, ts, ta + 300, ta + 360) if x[3]), None)
                rows.append(dict(g=g["event"], per=per, sh=sh, p=p,
                                 hold=fin - p - fee(p),
                                 mark=(statistics.median(x[1] for x in mk) - p - fee(p)) if mk else None,
                                 rt=(ex[1] - p - fee(p) - fee(ex[1])) if ex else None))
    lab = label or f"soccer T d={d}"
    print(f"-- {lab}: filled {len(rows)}")
    for key in ("hold", "mark", "rt"):
        summarise(lab, rows, key)
    return rows

if __name__ == "__main__":
    run(3)
