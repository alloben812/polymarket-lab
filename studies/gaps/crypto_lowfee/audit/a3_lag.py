"""Audit stage 3: M3 rebuilt with my own code (by period and by day), block-timestamp structure by day,
and a staleness regression at trade times. Usage: python3 -I a3_lag.py <scratch_dir>"""
import sys
import numpy as np, pandas as pd

S = sys.argv[1]
T_START, T_REPORT = 1795219200, 1795564800
NAMES = ["eth-5m", "eth-15m", "sol-15m", "xrp-15m", "btc-15m", "btc-5m"]
DUR = {"eth-5m": 300, "btc-5m": 300}
LAGS = list(range(-5, 31))
pd.set_option("display.width", 250)


def curve(dF, dU):
    out = []
    n = dF.shape[1]
    for L in LAGS:
        a, b = max(0, -L), min(n, n - L)
        x, y = dF[:, a:b].ravel(), dU[:, a + L:b + L].ravel()
        ok = np.isfinite(x) & np.isfinite(y)
        out.append(np.corrcoef(x[ok], y[ok])[0, 1])
    return np.array(out)


allts = []
for name in NAMES:
    dur = DUR.get(name, 900)
    f = pd.read_parquet(f"{S}/{name}_tape.parquet"); g = np.load(f"{S}/{name}_G.npz")
    T0, G = g["t0"], g["G"]
    pos = {t: i for i, t in enumerate(T0)}
    allts.append(pd.DataFrame({"t": f.t.to_numpy(), "series": name}))
    # U on block time: size-weighted implied Up price of the latest block second (>= t0) with rows
    up = np.where(f.o == "Up", f.p, 1 - f.p)
    d = pd.DataFrame({"r": f.t0.map(pos).to_numpy(), "i": (f.t - f.t0).to_numpy(), "uz": up * f.z, "z": f.z.to_numpy()})
    d = d[(d.i >= 0) & (d.i <= dur)].groupby(["r", "i"])[["uz", "z"]].sum().reset_index()
    U = np.full((len(T0), dur + 1), np.nan)
    U[d.r.to_numpy(), d.i.to_numpy()] = (d.uz / d.z).to_numpy()
    U = pd.DataFrame(U).ffill(axis=1).to_numpy()
    F = np.full((len(T0), dur + 1), np.nan); F[:, 1:] = G        # F(s) = information up to time s
    dF = np.full_like(F, np.nan); dF[:, 1:] = F[:, 1:] - F[:, :-1]
    dU = np.full_like(U, np.nan); dU[:, 1:] = U[:, 1:] - U[:, :-1]
    day = (T0 - T_START) // 86400
    rows = []
    for lab, sel in [("all", T0 > 0), ("tune", T0 < T_REPORT), ("report", T0 >= T_REPORT)] + [(f"11-{21 + k}", day == k) for k in range(6)]:
        c = curve(dF[sel], dU[sel])
        p = np.clip(c, 0, None)
        rows.append({"cut": lab, "peak": LAGS[int(np.argmax(c))], "corr": round(c.max(), 3), "mean_pos": round((np.array(LAGS) * p).sum() / p.sum(), 2),
                     "c0": round(c[5], 3), "c1": round(c[6], 3), "c2": round(c[7], 3), "c3": round(c[8], 3), "c4": round(c[9], 3),
                     "com0_4": round((np.arange(5) * c[5:10]).sum() / c[5:10].sum(), 2), "tail5_30/peak0_4": round(p[10:].sum() / p[5:10].sum(), 2)})
    print(f"\n== M3 rebuilt: {name}"); print(pd.DataFrame(rows).to_string(index=False))
    # the same curve restricted to seconds in which the tape actually printed (dU measured only at trade seconds)
    traded = np.zeros_like(U, bool); traded[d.r.to_numpy(), d.i.to_numpy()] = True
    dUt = np.where(traded, dU, np.nan)
    c = curve(dF, dUt); p = np.clip(c, 0, None)
    print("   only seconds with a print: peak %d corr %.3f mean_pos %.2f | corr at lags 0..8: %s" % (LAGS[int(np.argmax(c))], c.max(), (np.array(LAGS) * p).sum() / p.sum(), np.round(c[5:14], 3)))
    # staleness regression at trade seconds: u(s) - F(s-B) on [F(s-B) - F(s-B-k)], B = assumed block lag
    r, i, u = d.r.to_numpy(), d.i.to_numpy(), (d.uz / d.z).to_numpy()
    per = np.where(T0[r] < T_REPORT, "tune", "report")
    for B in (3, 2, 1):
        line = []
        for k in (3, 10):
            ok = (i - B - k >= 1) & (i <= dur - 1) & (u > 0.05) & (u < 0.95)
            now, old = F[r[ok], i[ok] - B], F[r[ok], i[ok] - B - k]
            y, x = u[ok] - now, now - old
            for pl in ("tune", "report"):
                m = per[ok] == pl
                # cluster-robust slope (clusters = markets)
                xm, ym = x[m] - x[m].mean(), y[m] - y[m].mean()
                b = (xm * ym).sum() / (xm * xm).sum()
                e = ym - b * xm
                sc = pd.Series(xm * e).groupby(r[ok][m]).sum()
                se = np.sqrt((sc ** 2).sum()) / (xm * xm).sum()
                line.append(f"k={k} {pl}: b={b:+.3f} (se {se:.3f}, n={m.sum()})")
        print(f"   stale-regression B={B}: " + " | ".join(line))

# block timestamp structure by UTC day, all six series pooled
a = pd.concat(allts)
a = a[(a.t >= T_START) & (a.t < T_START + 6 * 86400)]
print("\n== block-time structure (all fills of the six series pooled)")
for k in range(6):
    x = a[(a.t >= T_START + k * 86400) & (a.t < T_START + (k + 1) * 86400)]
    cnt = np.bincount((x.t - T_START - k * 86400).to_numpy(), minlength=86400).astype(float)
    ac = [np.corrcoef(cnt[:-j], cnt[j:])[0, 1] for j in (1, 2, 3, 4)]
    secs = np.flatnonzero(cnt > 0); gaps = np.diff(secs)
    print("11-%d fills %7d | seconds with a fill %.3f | even-second share %.3f | autocorr lag1..4 %s | gap between fill seconds: 1s %.2f 2s %.2f 3s+ %.2f" % (
        21 + k, len(x), (cnt > 0).mean(), x.t.mod(2).eq(0).mean(), np.round(ac, 3), (gaps == 1).mean(), (gaps == 2).mean(), (gaps >= 3).mean()))
