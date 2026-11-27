"""One-touch group: independent rebuild of the 9 variants + effect of dropping signals whose entry bucket falls after the hit."""
import json, gzip, math
import numpy as np, pandas as pd
from pathlib import Path
from statistics import NormalDist
from pmlab.http import get_json
N = NormalDist().cdf
D = Path("/home/user/polymarket-lab/data/gaps_levels"); YEAR = 365 * 86400.0
uni = [u for u in json.load(open(D / "universe.json")) if u["grp"] == "ot"]
K1 = {}; DV = {}
for a in ("BTC", "ETH"):
    k = np.load(D / f"{a}USDT_1m.npy"); K1[a] = (k[:, 0].astype("int64"), k[:, 2], k[:, 3], k[:, 4])
    d = np.load(D / f"dvol_{a}.npy"); DV[a] = (d[:, 0].astype("int64") + 3600, d[:, 1] / 100)
rows = []; late = []
for u in uni:
    ot, hi, lo, cl = K1[u["asset"]]; de, ds = DV[u["asset"]]
    ph = sorted({int(x[0]): float(x[1]) for x in json.load(open(D / "ph" / f"{u['cond']}.json")) if x[2] == 300 and x[0] < u["T"]}.items())
    if not ph: continue
    s0 = max(u["start"], u["ev_start"]); i0 = max(0, -(-(s0 - ot[0]) // 60)) if False else max(0, (s0 - ot[0]) // 60); i1 = min(len(ot), (u["T"] - ot[0]) // 60)
    h = np.where(hi[i0:i1] >= u["K"])[0] if u["up"] else np.where(lo[i0:i1] <= u["K"])[0]
    t_hit = int(ot[i0 + h[0]]) if len(h) else None
    pts = {}
    for t, pm in ph:
        i = (t - ot[0]) // 60 - 1; j = np.searchsorted(de, t, side="right") - 1
        if i < 0 or j < 0 or t - de[j] > 6 * 3600: continue
        S = cl[i]; sig = ds[j]; tau = u["T"] - t; v = sig * sig * tau / YEAR; sv = math.sqrt(v); b = abs(math.log(u["K"] / S))
        if (S >= u["K"]) if u["up"] else (S <= u["K"]): continue
        pf = (N((-b - v / 2) / sv) + S / u["K"] * N((-b + v / 2) / sv)) if u["up"] else (N((-b + v / 2) / sv) + S / u["K"] * N((-b - v / 2) / sv))
        pts[t] = (pm, pf, tau / 3600, t_hit is None or t < t_hit)
    raw = dict(ph)
    for g in (0.05, 0.08, 0.12):
        for bn, (a, b_) in {"2-12h": (2, 12), "12-48h": (12, 48), "48h-7d": (48, 168)}.items():
            last = None
            for t in sorted(pts):
                pm, pf, h_, pre = pts[t]
                if not pre: break
                gap = pm - pf
                if abs(gap) < g or h_ < a or (h_ >= b_ if bn != "48h-7d" else h_ > b_): continue
                if last is not None and t - last < 12 * 3600: continue
                side = "YES" if gap < 0 else "NO"
                nx = pts.get(t + 300)
                if nx is None or not nx[3]:
                    if t_hit is not None and t + 300 >= t_hit and (t + 300) in raw:   # entry bucket is at/after the hit: analyst drops it
                        p1 = raw[t + 300]; pe = (p1 if side == "YES" else 1 - p1) + 0.01
                        if 0.01 <= pe <= 0.99:
                            won = side == "YES"; sh = 20 / pe; late.append((u["slug"], u["date"], g, bn, side, pe, (sh if won else 0) - 20 - sh * 0.01 * pe * (1 - pe)))
                    continue
                pe = (nx[0] if side == "YES" else 1 - nx[0]) + 0.01
                if pe < 0.01 or pe > 0.99: continue
                last = t; sh = 20 / pe; won = u["yes_won"] == (side == "YES")
                rows.append((u["cond"], g, bn, t, side, pe, (sh if won else 0) - 20 - sh * 0.01 * pe * (1 - pe), u["date"]))
E = pd.DataFrame(rows, columns=["cond", "g", "band", "t", "side", "pe", "pnl", "date"])
A = pd.read_parquet(D / "entries_ot_pa.parquet")
m = E.merge(A, on=["cond", "g", "band", "t", "side"], how="outer", suffixes=("", "_a"), indicator=True)
print("one-touch entries mine", len(E), "analyst", len(A), m._merge.value_counts().to_dict(), "max |pnl diff| %.2e" % (m[m._merge == "both"].pnl - m[m._merge == "both"].pnl_a).abs().max())
Lt = pd.DataFrame(late, columns=["slug", "date", "g", "band", "side", "pe", "pnl"])
Lt["period"] = np.where(Lt.date <= "2026-11-15", "tune", "report")
print("signals dropped only because the entry bucket came after the barrier was hit:", len(Lt), "; their P&L had they been entered at the post-hit price + 1c:", Lt.groupby(["period", "side"]).pnl.agg(["size", "sum"]).round(1).to_dict("index"))
E["period"] = np.where(E.date <= "2026-11-15", "tune", "report"); print("paper pnl by period (all 9 variants pooled):", E.groupby("period").pnl.sum().round(0).to_dict())
# Binance vs USD index basis, live
b = float(get_json("https://data-api.binance.vision/api/v3/ticker/price", {"symbol": "BTCUSDT"})["price"]); dbt = get_json("https://www.deribit.com/api/v2/public/get_index_price", {"index_name": "btc_usd"})["result"]["index_price"]
cb = float(get_json("https://api.exchange.coinbase.com/products/BTC-USD/ticker")["price"])
print(f"live basis check: Binance BTCUSDT {b:.2f}, Deribit btc_usd index {dbt:.2f}, Coinbase BTC-USD {cb:.2f}; Binance - Deribit = {b - dbt:+.2f}")
