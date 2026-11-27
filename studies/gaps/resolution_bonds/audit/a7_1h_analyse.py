"""Audit a7: the study's crypto rule (trigger = first 5-min mid of the favourite in [0.95,0.98) from endDate-1h;
buy = first taker BUY print on that token in [0.95,0.98) >= 10 s later) on the btc/eth-updown-1h markets of
18-26 Nov that the study's universe excluded. Payoff from gamma outcomePrices; fee from feeSchedule."""
import gzip, json, math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
D = Path("/home/user/polymarket-lab/data/gaps_resolution_bonds/audit_1h"); OUT = Path(__file__).resolve().parent
J = lambda v: json.loads(v) if isinstance(v, str) else v
def T(s):
    s = str(s).replace(" ", "T").replace("Z", "+00:00")
    if s.endswith("+00"): s += ":00"
    return datetime.fromisoformat(s).timestamp()
def ct(vals, cl):
    s, n = defaultdict(float), defaultdict(int)
    for v, c in zip(vals, cl): s[c] += v; n[c] += 1
    N, G = len(vals), len(s); m = sum(vals) / N
    if G < 2: return m, float("nan"), float("nan")
    se = math.sqrt(sum((s[c] - m * n[c]) ** 2 for c in s) * G / (G - 1)) / N
    return m, se, m / se if se else float("inf")
def wil(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h
ms = json.load(open(D / "markets.json"))
G = []; stat = defaultdict(int); nentry = []
for m in ms:
    p = D / f"{m['conditionId']}.json.gz"
    if not p.exists(): stat["nofile"] += 1; continue
    d = json.load(gzip.open(p, "rt"))
    if d["err"]: stat["err"] += 1; continue
    op = [float(x) for x in J(m["outcomePrices"])]
    if max(op) < 0.99: stat["unresolved"] += 1; continue
    toks = J(m["clobTokenIds"]); end = T(m["endDate"]); closed = T(m["closedTime"]) if m.get("closedTime") else None
    if closed is None: stat["noclosed"] += 1; continue
    rate = float((m.get("feeSchedule") or {}).get("rate") or 0) if m.get("feesEnabled") is not False else 0.0
    stat["markets"] += 1; stat[f"rate {rate}"] += 1
    pts = sorted((t, pr) for t, pr, rs in d["h"] if rs == 300 and end - 3600 <= t < closed)
    e = None
    for t, p0 in pts:
        k = 0 if p0 > 0.5 else 1; pf = max(p0, 1 - p0)
        if 0.95 - 1e-9 <= pf < 0.98 - 1e-9: e = (t, k, pf); break
    if not e: continue
    t, k, pf = e; tok = toks[k]; pay = op[k]
    nentry.append(pay)
    f = next(((tt, pp) for tt, side, tk, pp, sz, w in sorted(d["rows"]) if side == "BUY" and tk == tok and tt >= t + 10 and tt <= closed and 0.95 - 1e-9 <= pp < 0.98 - 1e-9), None)
    if not f: continue
    c = f[1] + rate * f[1] * (1 - f[1])
    G.append(dict(slug=m["slug"], pay=pay, price=f[1], cost=c, r=10 * (pay - c) / c, vol=float(m.get("volumeNum") or 0),
                  day=datetime.fromtimestamp(end, tz=timezone.utc).strftime("%m-%d"), wk=datetime.fromtimestamp(end, tz=timezone.utc).weekday() >= 5,
                  delay=f[0] - t, ttc=(closed - f[0]) / 60))
L = [json.dumps(dict(stat)), f"5-min entries {len(nentry)}, lost {sum(p<1 for p in nentry)}",
     "subset | markets | lost | loss % (Wilson) | break-even % | net per 10 USD | t (market) | t (day)"]
def rep(name, g):
    if not g: L.append(f"{name} | 0"); return
    k = sum(x["pay"] < 1 for x in g); lo, hi = wil(k, len(g))
    a = ct([x["r"] for x in g], list(range(len(g)))); b = ct([x["r"] for x in g], [x["day"] for x in g])
    L.append(f"{name} | {len(g)} | {k} | {100*k/len(g):.2f} ({100*lo:.1f}-{100*hi:.1f}) | {100*(1-sum(x['cost'] for x in g)/len(g)):.2f} | {a[0]:+.3f} | {a[2]:+.1f} | {b[2]:+.1f}")
rep("all btc+eth 1h", G)
rep("btc", [x for x in G if x["slug"].startswith("btc")]); rep("eth", [x for x in G if x["slug"].startswith("eth")])
rep("volume >= 10k (the study's filter)", [x for x in G if x["vol"] >= 10000]); rep("volume < 10k", [x for x in G if x["vol"] < 10000])
rep("weekend", [x for x in G if x["wk"]]); rep("weekday", [x for x in G if not x["wk"]])
rep("+1 tick", [dict(x, cost=x["cost"] + 0.01, r=10 * (x["pay"] - x["cost"] - 0.01) / (x["cost"] + 0.01)) for x in G])
L.append("losers: " + "; ".join(f"{x['slug']} p={x['price']:.3f} {x['ttc']:.0f} min before close" for x in G if x["pay"] < 1))
print("\n".join(L)); (OUT / "a7_out.txt").write_text("\n".join(L) + "\n")
