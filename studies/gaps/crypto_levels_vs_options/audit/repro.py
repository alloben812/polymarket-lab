"""Sceptic's independent rebuild of the crypto-levels headline (European daily ladders, DVOL model).
Reads only RAW inputs (universe.json metadata, ph/*.json, Binance/DVOL npy, tape/*.json.gz); shares no code with the analyst.
Writes my_entries.parquet (all 9 variants, with tape-check columns)."""
import json, gzip, math, sys
from pathlib import Path
import numpy as np, pandas as pd
from statistics import NormalDist
_nd = NormalDist()
def Phi(x):
    return np.array([_nd.cdf(float(z)) if z == z else np.nan for z in np.asarray(x, dtype=float)])
D = Path("/home/user/polymarket-lab/data/gaps_levels")
OUT = Path.cwd()  # run from a scratch directory: writes my_entries/my_hourly/my_panel parquet there
uni = [u for u in json.load(open(D / "universe.json")) if u["grp"] == "euro"]
YEAR = 365 * 86400.0

def kl(sym):
    a = np.load(D / f"{sym}_1m.npy")
    k = pd.DataFrame({"close_time": a[:, 0].astype("int64") + 60, "S": a[:, 4]}).sort_values("close_time")
    return k
def dv(cur):
    a = np.load(D / f"dvol_{cur}.npy")
    return pd.DataFrame({"dv_end": a[:, 0].astype("int64") + 3600, "sig": a[:, 1] / 100.0}).sort_values("dv_end")
K1 = {"BTC": kl("BTCUSDT"), "ETH": kl("ETHUSDT")}; DV = {"BTC": dv("BTC"), "ETH": dv("ETH")}

G = (0.05, 0.08, 0.12); B = {"2-12h": (2, 12), "12-48h": (12, 48), "48h-7d": (48, 168)}
rows = []; panel_stats = []; full = []
for u in uni:
    ph = json.load(open(D / "ph" / f"{u['cond']}.json"))
    df = pd.DataFrame([(int(x[0]), float(x[1])) for x in ph if x[2] == 300 and x[0] < u["T"]], columns=["t", "pm"]).drop_duplicates("t").sort_values("t")
    if df.empty: continue
    # spot: last 1-minute close whose candle ended at or before t, at most 5 minutes old
    df = pd.merge_asof(df, K1[u["asset"]], left_on="t", right_on="close_time", direction="backward")
    df.loc[(df.t - df.close_time) > 300, "S"] = np.nan
    df = pd.merge_asof(df, DV[u["asset"]], left_on="t", right_on="dv_end", direction="backward")
    df.loc[(df.t - df.dv_end) > 6 * 3600, "sig"] = np.nan
    df["tau"] = u["T"] - df.t
    v = df.sig ** 2 * df.tau / YEAR
    df["pf"] = Phi((np.log(df.S / u["K"]) - v / 2) / np.sqrt(v))
    df = df.dropna(subset=["S", "pf"]).reset_index(drop=True)
    df["gap"] = df.pm - df.pf
    nxt = dict(zip(df.t.values.tolist(), df.pm.values.tolist()))
    full.append(df.assign(cond=u["cond"])[["cond", "t", "pm", "pf", "S", "sig", "tau"]])
    hh = df[(df.t % 3600 == 0)]
    panel_stats.append(hh.assign(cond=u["cond"])[["cond", "t", "pm", "pf", "gap", "tau"]])
    for g in G:
        for bn, (lo, hi) in B.items():
            last = None
            for t, gap, tau, pf, pm in zip(df.t.values, df.gap.values, df.tau.values, df.pf.values, df.pm.values):
                h = tau / 3600.0
                if abs(gap) < g or h < lo or (h >= hi if bn != "48h-7d" else h > hi): continue
                if last is not None and t - last < 12 * 3600: continue
                p1 = nxt.get(int(t) + 300)
                if p1 is None: continue
                side = "YES" if gap < 0 else "NO"
                pe = (p1 if side == "YES" else 1 - p1) + 0.01
                if pe < 0.01 or pe > 0.99: continue
                last = t
                sh = 20.0 / pe
                won = (u["yes_won"] == (side == "YES"))
                fee = sh * 0.01 * pe * (1 - pe)
                pnl = sh * (1.0 if won else 0.0) - 20.0 - fee
                rows.append(dict(cond=u["cond"], slug=u["slug"], asset=u["asset"], date=u["date"], freq=u["freq"], K=u["K"], T=u["T"], start=u["start"], g=g, band=bn, t=int(t), side=side, gap=gap, pf=pf, pm=pm, p1=p1, pe=pe, shares=sh, fee=fee, won=won, pnl=pnl, tau_h=h))
E = pd.DataFrame(rows)
E["period"] = np.where(E.date <= "2026-11-15", "tune", "report"); E["cluster"] = E.asset + "_" + E.date
H = pd.concat(panel_stats); H.to_parquet(OUT / "my_hourly.parquet"); pd.concat(full).to_parquet(OUT / "my_panel.parquet")

# tape check, my own: block time bt, match time = bt - 3. For a window (a, b] in match time collect sizes buyable at <= pe
tapes = {}
def tape(c):
    if c not in tapes:
        p = D / "tape" / f"{c}.json.gz"
        tapes[c] = pd.DataFrame(json.load(gzip.open(p, "rt")), columns=["bt", "side", "outcome", "size", "price"]) if p.exists() else None
    return tapes[c]
def buyable(tp, side, a, b):
    """prints that show `side` could be bought: taker BUY of side at p, or taker SELL of the other outcome at q -> 1-q"""
    o = "Yes" if side == "YES" else "No"
    w = tp[(tp.bt - 3 > a) & (tp.bt - 3 <= b)]
    x = w[(w.side == "BUY") & (w.outcome == o)].assign(bp=lambda d: d.price)
    y = w[(w.side == "SELL") & (w.outcome != o)].assign(bp=lambda d: 1 - d.price)
    return pd.concat([x, y]), len(w)
res = []
for r in E.itertuples():
    tp = tape(r.cond)
    out = {}
    if tp is None:
        res.append(dict(has_tape=False)); continue
    for name, a, b in (("w0", r.t, r.t + 600), ("w300", r.t + 300, r.t + 900), ("w300s", r.t + 300, r.t + 600)):
        bp, n = buyable(tp, r.side, a, b)
        ok = bp[bp.bp <= r.pe + 1e-9]
        out[f"conf_{name}"] = len(ok) > 0; out[f"size_{name}"] = float(ok["size"].sum()); out[f"n_{name}"] = n
        out[f"vwap_{name}"] = float((ok["size"] * ok.bp).sum() / ok["size"].sum()) if len(ok) else np.nan
    out["has_tape"] = True
    res.append(out)
E = pd.concat([E, pd.DataFrame(res)], axis=1)
E.to_parquet(OUT / "my_entries.parquet")
print("entries", len(E), "distinct", len(E.drop_duplicates(["cond", "t", "side"])), "markets", E.cond.nunique(), "no tape rows", (~E.has_tape).sum())
