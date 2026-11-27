"""(c) Deribit listed options vs model (a): call/put spreads and near-ATM implied vol, BTC, last 10 daily expiries."""
import sys, json, math, datetime as dt
import numpy as np, pandas as pd
from common import *
from pmlab.http import get_json, HttpError
D = "https://www.deribit.com/api/v2/public/get_tradingview_chart_data"
M = Minute("BTCUSDT"); DV = Dvol("BTC")

def chart(name, a, b):
    try:
        r = get_json(D, {"instrument_name": name, "start_timestamp": a * 1000, "end_timestamp": b * 1000, "resolution": 60}, cache=True)["result"]
    except HttpError as e:
        return []
    if r.get("status") != "ok": return []
    return [(int(t) // 1000, c, v) for t, c, v in zip(r["ticks"], r["close"], r["volume"]) if v and v > 0]

def black_call(S, K, sig, tau_y):
    v = sig * math.sqrt(tau_y)
    d1 = (math.log(S / K) + v * v / 2) / v
    N = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
    return S * N(d1) - K * N(d1 - v)

def iv(price, S, K, tau_y, call):
    if not call: price = price + S - K  # parity, zero rates
    if price <= max(S - K, 0) + 1e-9 or price >= S: return float("nan")
    lo, hi = 0.01, 5.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if black_call(S, K, mid, tau_y) < price: lo = mid
        else: hi = mid
    return (lo + hi) / 2

rows = []; got = 0
day = dt.date(2026, 11, 26)
while got < 10 and day >= dt.date(2026, 10, 27):
    exp = int(dt.datetime(day.year, day.month, day.day, 8, tzinfo=dt.timezone.utc).timestamp())
    code = f"{day.day}{day.strftime('%b').upper()}{day.strftime('%y')}"
    a, b = exp - 24 * 3600, exp - 2 * 3600
    s0 = float(M.spot(np.array([a]))[0]); k0 = round(s0 / 500) * 500
    n_inst = 0
    for K in range(int(k0 - 6000), int(k0 + 6001), 500):
        for cp in ("C", "P"):
            c = chart(f"BTC-{code}-{K}-{cp}", a, b)
            n_inst += bool(c)
            for t, px, vol in c:
                te = t + 3600  # candle end
                if te > b: continue
                S = float(M.spot(np.array([te]))[0])
                rows.append((code, exp, K, cp, te, px, px * S, vol, S))
    print(code, "instruments with traded candles:", n_inst, file=sys.stderr)
    if n_inst: got += 1
    day -= dt.timedelta(days=1)
T = pd.DataFrame(rows, columns=["exp_code", "exp", "K", "cp", "t", "px_btc", "px_usd", "vol", "S"])
T.to_parquet(DATA / "deribit_c.parquet")
print(f"traded hourly candles: {len(T)} over {T.exp_code.nunique()} expiries ({sorted(T.exp_code.unique())}), instruments {T.groupby(['exp_code','K','cp']).ngroups}")
T["tau"] = T.exp - T.t; T["sig_a"] = DV.at(T.t.values)
# near-ATM implied vol vs DVOL
A = T[(np.abs(np.log(T.K / T.S)) <= 0.015) & (T.tau >= 2 * 3600) & (T.tau <= 24 * 3600)].copy()
A["iv"] = [iv(r.px_usd, r.S, r.K, r.tau / YEAR, r.cp == "C") for r in A.itertuples()]
A = A.dropna(subset=["iv"]); A["ratio"] = A.iv / A.sig_a
print(f"near-ATM IV (|ln K/S|<=1.5%, 2-24h to expiry): n {len(A)}, IV median {A.iv.median():.3f}, DVOL median {A.sig_a.median():.3f}, ratio IV/DVOL quartiles {A.ratio.quantile(.25):.3f} / {A.ratio.median():.3f} / {A.ratio.quantile(.75):.3f}, mean {A.ratio.mean():.3f}")
print("ratio by expiry:"); print(A.groupby("exp_code").ratio.agg(["size", "median"]).round(3).to_string())
A["tb"] = pd.cut(A.tau / 3600, [2, 6, 12, 24.01]); print(A.groupby("tb", observed=True).ratio.agg(["size", "median"]).round(3).to_string())
# spreads
out = []
for (code, t, cp), g in T.groupby(["exp_code", "t", "cp"]):
    g = g.sort_values("K")
    for i in range(len(g) - 1):
        r1, r2 = g.iloc[i], g.iloc[i + 1]
        dK = r2.K - r1.K
        if dK > 1000: continue
        dig = (r1.px_usd - r2.px_usd) / dK if cp == "C" else 1 - (r2.px_usd - r1.px_usd) / dK
        raw = dig; dig = min(1.0, max(0.0, dig))
        Km = (r1.K + r2.K) / 2
        pa = float(p_above(np.array([r1.S]), Km, np.array([r1.sig_a]), np.array([r1.tau]))[0])
        out.append((code, t, cp, Km, r1.S, r1.tau / 3600, dig, raw, pa))
Sp = pd.DataFrame(out, columns=["exp_code", "t", "cp", "Km", "S", "tau_h", "dig", "raw", "pa"])
Sp["d"] = Sp.pa - Sp.dig
print(f"\nspread digitals: n {len(Sp)} ({(Sp.cp=='C').sum()} call spreads, {(Sp.cp=='P').sum()} put spreads); model(a) - option digital: mean {Sp.d.mean():+.4f} median {Sp.d.median():+.4f} mean abs {Sp.d.abs().mean():.4f} sd {Sp.d.std():.4f}; share of raw spreads outside [0,1]: {((Sp.raw<0)|(Sp.raw>1)).mean():.3f}")
Sp["mb"] = pd.cut(Sp.pa, [0, 0.1, 0.3, 0.7, 0.9, 1.0000001], labels=["0-0.1", "0.1-0.3", "0.3-0.7", "0.7-0.9", "0.9-1"], right=False)
print(Sp.groupby("mb", observed=True).agg(n=("d", "size"), model=("pa", "mean"), option=("dig", "mean"), mean_diff=("d", "mean"), median_diff=("d", "median"), mae=("d", lambda x: x.abs().mean())).round(4).to_string())
Sp.to_parquet(DATA / "deribit_c_spreads.parquet")
