"""Audit stage 8: when did the tape-vs-Binance lag shorten? Centre of mass of the M3 correlation over lags 0..4 by 4-hour block,
eth-5m + eth-15m + btc-15m + btc-5m pooled (weights = pairs). Usage: python3 -I a8_lag_when.py <scratch_dir>"""
import sys
import numpy as np, pandas as pd
S = sys.argv[1]
T_START = 1795219200
DUR = {"eth-5m": 300, "btc-5m": 300}
acc = {}
for name in ["eth-5m", "eth-15m", "btc-15m", "btc-5m"]:
    dur = DUR.get(name, 900)
    f = pd.read_parquet(f"{S}/{name}_tape.parquet"); g = np.load(f"{S}/{name}_G.npz"); T0, G = g["t0"], g["G"]
    pos = {t: i for i, t in enumerate(T0)}
    up = np.where(f.o == "Up", f.p, 1 - f.p)
    d = pd.DataFrame({"r": f.t0.map(pos).to_numpy(), "i": (f.t - f.t0).to_numpy(), "uz": up * f.z, "z": f.z.to_numpy()})
    d = d[(d.i >= 0) & (d.i <= dur)].groupby(["r", "i"])[["uz", "z"]].sum().reset_index()
    U = np.full((len(T0), dur + 1), np.nan); U[d.r.to_numpy(), d.i.to_numpy()] = (d.uz / d.z).to_numpy()
    U = pd.DataFrame(U).ffill(axis=1).to_numpy()
    F = np.full((len(T0), dur + 1), np.nan); F[:, 1:] = G
    dF = np.full_like(F, np.nan); dF[:, 1:] = F[:, 1:] - F[:, :-1]; dU = np.full_like(U, np.nan); dU[:, 1:] = U[:, 1:] - U[:, :-1]
    blk = (T0 - T_START) // 14400
    for b in np.unique(blk):
        m = blk == b
        cs = []
        for L in range(0, 5):
            x, y = dF[m][:, :dur + 1 - L].ravel(), dU[m][:, L:].ravel(); ok = np.isfinite(x) & np.isfinite(y)
            cs.append(np.corrcoef(x[ok], y[ok])[0, 1])
        acc.setdefault(int(b), []).append(np.array(cs))
print("4-hour block (UTC start) : centre of mass of corr over lags 0..4 s, mean of four liquid series | peak lag")
for b in sorted(acc):
    c = np.mean(acc[b], axis=0)
    ts = pd.Timestamp(T_START + b * 14400, unit="s")
    print(ts.strftime("%m-%d %H:%M"), "%.2f" % ((np.arange(5) * c).sum() / c.sum()), int(np.argmax(c)), np.round(c, 2))
