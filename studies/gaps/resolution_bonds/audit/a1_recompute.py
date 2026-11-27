"""Audit a1: independent recomputation from raw caches (universe/sample metadata, resolutions, prices-history, tapes).
Own parsing, own trigger, own stats. Writes audit/a1_entries.pkl for later checks."""
import gzip, json, math, pickle, sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
D = Path("/home/user/polymarket-lab/data/gaps_resolution_bonds")
OUT = Path(__file__).resolve().parent
SPLIT = datetime(2026, 11, 13, tzinfo=timezone.utc).timestamp()
CMIN = datetime(2026, 10, 20, tzinfo=timezone.utc).timestamp(); CMAX = datetime(2026, 11, 25, tzinfo=timezone.utc).timestamp()

def T(s):
    s = str(s).replace(" ", "T")
    if s.endswith("Z"): s = s[:-1] + "+00:00"
    if s.endswith("+00"): s += ":00"
    d = datetime.fromisoformat(s)
    return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()

def rate(m):
    if m.get("feesEnabled") is False: return 0.0
    r = (m.get("feeSchedule") or {}).get("rate")
    return 0.05 if r is None else float(r)

def ct(vals, clusters):
    """mean of vals with SE clustered by cluster (ratio estimator, each obs weight 1)."""
    s, n = defaultdict(float), defaultdict(int)
    for v, c in zip(vals, clusters): s[c] += v; n[c] += 1
    N = len(vals); G = len(s)
    if N == 0: return float("nan"), float("nan"), float("nan")
    m = sum(vals) / N
    if G < 2: return m, float("nan"), float("nan")
    var = sum((s[c] - m * n[c]) ** 2 for c in s) * G / (G - 1) / N ** 2
    se = math.sqrt(var)
    return m, se, (m / se if se > 0 else float("inf"))

def wil(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h

uni = {m["conditionId"]: m for m in (json.loads(l) for l in gzip.open(D / "universe.jsonl.gz", "rt"))}
samp = set(json.loads(l)["conditionId"] for l in gzip.open(D / "sample.jsonl.gz", "rt"))
res = json.load(open(D / "resolutions.json")); res.update(json.load(open(D / "ext/resolutions.json")))

def payoff(m):
    r = res.get(m["conditionId"])
    if not r or not r.get("resolved"): return None
    p = [r["final"].get(o) for o in m["outcomes"]]
    return None if any(x is None for x in p) else p

def series(h, closed):
    """return dict t->(p0,p1) for usable buckets; for single-token histories p1 = 1-p0"""
    if isinstance(h[0] if h else None, list) and h and isinstance(h[0][0], list):  # two tokens
        a = {t: p for t, p, rs in h[0] if rs == 300 and t < closed}
        b = {t: p for t, p, rs in h[1] if rs == 300 and t < closed}
        out = {}
        for t in set(a) | set(b):
            p0 = a.get(t); p1 = b.get(t)
            if p0 is None: p0 = 1 - p1
            if p1 is None: p1 = 1 - p0
            out[t] = (p0, p1)
        return out
    return {t: (p, 1 - p) for t, p, rs in h if rs == 300 and t < closed}

entries = []; stat = defaultdict(int)
for src, path in (("sample", D / "hist.jsonl.gz"), ("ext", D / "ext/hist.jsonl.gz")):
    for line in gzip.open(path, "rt"):
        h = json.loads(line); m = uni[h["cid"]]
        if src == "sample" and m["conditionId"] not in samp: stat["notinsample"] += 1; continue
        if h.get("err") or h.get("skip") or not h["h"]: stat[src + "_noh"] += 1; continue
        end, closed = T(m["endDate"]), T(m["closedTime"])
        assert CMIN <= closed < CMAX
        pay = payoff(m)
        if pay is None: stat[src + "_unres"] += 1; continue
        # independent payoff check vs gamma outcomePrices
        op = [float(x) for x in m["outcomePrices"]]
        if [round(x, 3) for x in op] != [round(x, 3) for x in pay]: stat[src + "_pay_mismatch_gamma"] += 1
        S = series(h["h"], closed)
        e = None
        for t in sorted(S):
            if t < end - 3600: continue
            p0, p1 = S[t]
            if abs(p0 - p1) < 1e-9: continue
            k = 0 if p0 > p1 else 1
            pf = max(p0, p1)
            if 0.95 - 1e-9 <= pf < 0.98 - 1e-9:
                nx = S.get(t + 300) if t + 300 < closed else None
                e = dict(cid=m["conditionId"], slug=m["slug"], fam=m["family"], ev=m.get("event_slug") or m["slug"], src=src,
                         end=end, closed=closed, late=closed >= SPLIT, rate=rate(m), t=t, k=k, p=pf, pay=pay[k],
                         tok=m["clobTokenIds"][k], pnext=None if nx is None else nx[k], vol=m["volumeNum"])
                break
        stat[src + "_markets"] += 1
        if e: entries.append(e)
print(dict(stat))
pickle.dump(entries, open(OUT / "a1_entries.pkl", "wb"))
fee = lambda p, r: r * p * (1 - p)
L = []
def row(name, es, pricef):
    es = [e for e in es if pricef(e) is not None]
    if not es: return
    v = [e["pay"] - pricef(e) - fee(pricef(e), e["rate"]) for e in es]
    m, se, t = ct(v, [e["ev"] for e in es]); k = sum(e["pay"] < 1 for e in es)
    L.append(f"{name} | {len(es)} | {len(set(e['ev'] for e in es))} | {k} | {100*m:+.2f} | {100*se:.2f} | {t:+.1f}")
L.append("row | markets | events | lost | net c/share | SE c | t(event)")
smp = [e for e in entries if e["src"] == "sample"]
for fam in ("ALL", "sports", "weather", "crypto", "politics"):
    for per in ("early", "late"):
        es = [e for e in smp if (fam == "ALL" or e["fam"] == fam) and e["late"] == (per == "late")]
        row(f"sample C-mid {fam} {per}", es, lambda e: e["p"])
        row(f"sample C-cons {fam} {per}", es, lambda e: None if e["pnext"] is None else min(e["pnext"] + 0.005, 0.999))
for fam in ("crypto", "politics"):
    for per in ("early", "late"):
        es = [e for e in entries if e["src"] == "ext" and e["fam"] == fam and e["late"] == (per == "late")]
        row(f"ext C-mid {fam} {per}", es, lambda e: e["p"])
print("\n".join(L))
(OUT / "a1_out.txt").write_text(json.dumps(dict(stat)) + "\n" + "\n".join(L) + "\n")
