"""Falsification of 'the profit is just the November sell-off': the same direction split on an EARLIER window.
No intraday model here (Yahoo keeps 1-minute bars 30 days); realized result per buy fill, clustered by market."""
import sys, json, os, collections, datetime as dt
import fin, ladder, yh
from pmlab import gamma, dataapi, wallet as W, stats, fees
def load2(name, start, end):
    p = f"{fin.HERE}/cache/{name}_{start}_{end}.json"
    if os.path.exists(p): return json.load(open(p))
    fills, trunc = W.fetch_fills(fin.WALLETS[name], start, end, 80000)
    conds = sorted({f["condition_id"] for f in fills}); res = dataapi.resolutions(conds)
    out = dict(fills=fills, res=res, truncated=trunc); json.dump(out, open(p, "w")); return out
def d_of(title, out):
    kind, _ = ladder.strike(title); yes = out in ("Yes", "Up")
    return None if kind in (None, "range") else ("bull" if (yes == (kind in ("hitHIGH", "above", "updown"))) else "bear")
a, b = int(sys.argv[1]), int(sys.argv[2])
for tk in ("SPY", "NVDA"):
    j = yh._get(f"https://query1.finance.yahoo.com/v8/finance/chart/{tk}?interval=1d&period1={a - 86400}&period2={b + 86400}")
    r = j["chart"]["result"][0]; cl = [x for x in r["indicators"]["quote"][0]["close"] if x]
    print(f"{tk}: {cl[0]:.2f} -> {cl[-1]:.2f} ({cl[-1] / cl[0] - 1:+.1%}) over the window, min {min(cl):.2f} max {max(cl):.2f}")
for n in sys.argv[3:]:
    d = load2(n, a, b); rows = []
    for f in d["fills"]:
        ty, tk = fin.mtype(f["title"], f["slug"]); r = d["res"].get(f["condition_id"]) or {}
        if not ty or f["side"] != "BUY" or not r.get("resolved"): continue
        di = d_of(f["title"], f["outcome"]); fp = (r.get("final") or {}).get(f["outcome"])
        if di is None or fp is None: continue
        px, sz = float(f["price"]), float(f["size"]); t = int(f["timestamp"])
        fee = fees.fee_per_share(px, 0.0 if 1792454400 <= t < 1793491200 else 0.04) if f["role"] == "T" else 0     # zero-fee promo 20-31 Oct
        rows.append(dict(c=f["condition_id"], di=di, px=px, sz=sz, g=(fp - px - fee) * sz, role=f["role"], ty=ty, tk=tk))
    print(f"\n#### {n} {dt.datetime.utcfromtimestamp(a):%Y-%m-%d}..{dt.datetime.utcfromtimestamp(b):%Y-%m-%d}: fills {len(d['fills'])} (truncated={d['truncated']}), resolved price-market buys {len(rows)}")
    def tab(keyfn):
        G = collections.defaultdict(list)
        for r in rows: G[keyfn(r)].append(r)
        for k, rs in sorted(G.items(), key=lambda kv: str(kv[0])):
            byc = collections.defaultdict(lambda: [0.0, 0.0])
            for r in rs: byc[r["c"]][0] += r["g"]; byc[r["c"]][1] += r["sz"]
            est, se, t = stats.ratio_cluster([v[0] for v in byc.values()], [v[1] for v in byc.values()]) if len(byc) > 2 else (float("nan"),) * 3
            usd = sum(r["px"] * r["sz"] for r in rs); net = sum(r["g"] for r in rs)
            print(f"    {str(k):28} mkts {len(byc):4} usd {usd:8.0f} avg px {usd / sum(r['sz'] for r in rs):.2f} net ${net:8.0f} ({net / usd:6.1%}) c/sh {100 * est:6.2f} t {t:5.1f}")
    tab(lambda r: ("ALL",)); tab(lambda r: r["di"]); tab(lambda r: (r["di"], "px<0.45" if r["px"] < .45 else "px>=0.45")); tab(lambda r: ("role", r["role"])); tab(lambda r: ("type", r["ty"]))
