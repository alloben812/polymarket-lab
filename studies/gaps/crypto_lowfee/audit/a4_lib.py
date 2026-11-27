"""Functions of a4_rules.py (prints, look, capped, summ, m4_sel, m5_sel), split out so that a5_extra.py can reuse them."""
import sys
import numpy as np, pandas as pd

S = sys.argv[1]
OUTA = "/home/user/polymarket-lab/studies/gaps/crypto_lowfee/out"
T_START, T_REPORT = 1795219200, 1795564800
NAMES = ["eth-5m", "eth-15m", "sol-15m", "xrp-15m", "btc-15m", "btc-5m"]
DUR = {"eth-5m": 300, "btc-5m": 300}
ND = {"tune": 4, "report": 2}
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500)


def rc(num, den):
    num, den = np.asarray(num, float), np.asarray(den, float)
    n = len(num)
    if n < 2:
        return (num.sum() / den.sum() if n else np.nan), np.nan, np.nan
    r = num.sum() / den.sum(); e = num - r * den
    se = np.sqrt(n / (n - 1) * (e * e).sum()) / den.sum()
    return r, se, r / se


def prints(name, BL):
    dur = DUR.get(name, 900)
    mk = pd.read_parquet(f"{S}/{name}_mk.parquet").set_index("t0"); f = pd.read_parquet(f"{S}/{name}_tape.parquet"); g = np.load(f"{S}/{name}_G.npz")
    pos = pd.Series(np.arange(len(g["t0"])), index=g["t0"])
    buy = (f.s == "BUY").to_numpy(); tok_up = (f.o == "Up").to_numpy()
    d = pd.DataFrame({"t0": f.t0.to_numpy(), "r": f.t0.map(pos).to_numpy(), "m": (f.t - BL).to_numpy(), "eq_up": np.where(buy, tok_up, ~tok_up),
                      "q": np.where(buy, f.p, 1 - f.p), "z": f.z.to_numpy(), "rate": f.t0.map(mk.rate).to_numpy(), "up_won": f.t0.map(mk.up_won).to_numpy(bool)})
    d["won"] = (d.eq_up == d.up_won).astype(float)
    d["per"] = np.where(d.t0 < T_REPORT, "tune", "report")
    d["day"] = (d.t0 - T_START) // 86400
    return d, g["G"], g["dev"], dur


def look(A, r, i, dur):
    ok = (i >= 0) & (i < dur)
    return np.where(ok, A[r, np.clip(i, 0, dur - 1)], np.nan)


def capped(d):
    sz = np.minimum(d.z.to_numpy(), 50.0)
    cum = pd.Series(sz).groupby([d.t0.to_numpy(), d.eq_up.to_numpy()], sort=False).cumsum().to_numpy()
    sh = np.clip(300.0 - (cum - sz), 0.0, sz)
    d = d.assign(sh=sh)
    d = d[d.sh > 0]
    return d.assign(net=d.sh * (d.won - d.q) - d.sh * d.rate * d.q * (1 - d.q), cost=d.sh * d.q)


def summ(x, per):
    x = x[x.per == per]
    if not len(x):
        return {"trades": 0, "mkts": 0}
    a = x.groupby("t0")[["net", "sh", "cost"]].sum()
    r, se, t = rc(a.net, a.sh)
    return {"trades": len(x), "mkts": len(a), "net_c": round(100 * r, 2), "se_c": round(100 * se, 2) if se == se else np.nan, "t": round(t, 2) if t == t else np.nan,
            "pct": round(100 * a.net.sum() / a.cost.sum(), 2), "usd_day": round(a.net.sum() / ND[per], 1), "avg_q": round(a.cost.sum() / a.sh.sum(), 3)}


def m4_sel(d, G, dur, D, thr):
    b = d[(d.m >= d.t0 + 5) & (d.m <= d.t0 + dur - 5)]
    fup = look(G, b.r.to_numpy(), (b.m - D - 1 - b.t0).to_numpy(), dur)
    fo = np.where(b.eq_up, fup, 1 - fup)
    edge = fo - b.q.to_numpy() - (b.rate * b.q * (1 - b.q)).to_numpy()
    return b[np.nan_to_num(edge, nan=-9.0) >= thr]


def m5_sel(d, G, dev, dur, margin, twobp):
    b = d[(d.m >= d.t0 + dur - 45) & (d.m <= d.t0 + dur - 2)]
    i = (b.m - 2 - b.t0).to_numpy()
    fup = look(G, b.r.to_numpy(), i, dur)
    fo = np.where(b.eq_up, fup, 1 - fup)
    c = (fo >= 0.97) & (b.q.to_numpy() <= fo - margin)
    if twobp:
        c &= np.nan_to_num(look(dev, b.r.to_numpy(), i, dur), nan=0.0) >= 0.0002
    return b[c]


