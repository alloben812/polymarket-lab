"""Audit: direction check of the T3 separation with own code and raw Binance 1 s dumps (not the study's px_dense.npz).
mv30 = Binance close at match time minus close 30 s earlier, bp, signed toward the tail; gap = (Binance close - price_to_beat)
in bp, signed so that positive = tail is behind. Equal weight inside (market, outcome); pooled cell <=5c, 225<=e<285.
Usage: python3 t3_direction.py TAILS.parquet"""
import glob, json, os, sys, zipfile, io
import numpy as np, pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0])
D = "/home/user/polymarket-lab/data"
T0 = 1788220800 - 86400
close = np.full(90 * 86400, np.nan)
for f in sorted(glob.glob(f"{D}/binance_1s/BTCUSDT-1s-2026-*.zip")):
    day = f[-14:-4]
    if not ("2026-08-31" <= day <= "2026-11-26"):
        continue
    with zipfile.ZipFile(f) as z:
        a = pd.read_csv(z.open(z.namelist()[0]), header=None, usecols=[0, 4]).to_numpy()
    ot = a[:, 0].astype(np.int64)
    ot = np.where(ot > 1e14, ot // 1_000_000, np.where(ot > 1e11, ot // 1000, ot))
    close[ot - T0] = a[:, 1]
print("binance seconds missing in Sep1-Nov26:", int(np.isnan(close[86400:88 * 86400]).sum()))
def px(t):  # close of the 1 s kline that ends at t (open time t-1)
    return close[np.asarray(t, dtype=np.int64) - 1 - T0]
ptb = {}
def get_ptb(t0):
    if t0 not in ptb:
        p = f"{D}/updown_meta/btc/5m/{t0}.json"
        ptb[t0] = json.load(open(p)).get("price_to_beat") if os.path.exists(p) else None
    return ptb[t0]
def feats(t0, o, mt):
    k = np.array([get_ptb(x) or np.nan for x in t0], float)
    sgn = np.where(np.asarray(o) == "Up", 1.0, -1.0)
    p0, p30 = px(mt), px(np.asarray(mt) - 30)
    return sgn * (p0 - p30) / p0 * 1e4, -sgn * (p0 - k) / k * 1e4
tl = pd.read_parquet(sys.argv[1]); tl = tl[(tl.e >= 225) & (tl.e < 285) & (tl.p <= 0.05)].copy()
tl["mv30"], tl["gap"] = feats(tl.t0.to_numpy(), tl.o.to_numpy(), (tl.bt - 3).to_numpy())
b = tl.groupby(["t0", "o"]).agg(mv30=("mv30", "mean"), gap=("gap", "mean"), won=("won", "first"))
f = pd.DataFrame(json.load(open(f"{D}/gaps_btc5m_tails/vega7_fills.json")))
f["t0"] = f.slug.str.rsplit("-", n=1).str[1].astype(int); f["e"] = f.timestamp - 3 - f.t0
f = f[(f.e >= 225) & (f.e < 285) & (f.price <= 0.05 + 1e-9) & (f.t0 >= 1788220800) & (f.t0 < 1795737600)].copy()
f["mv30"], f["gap"] = feats(f.t0.to_numpy(), f.outcome.to_numpy(), (f.timestamp - 3).to_numpy())
v = f.groupby(["t0", "outcome"]).agg(mv30=("mv30", "mean"), gap=("gap", "mean"))
for c in ("mv30", "gap"):
    sd = np.sqrt((b[c].var() + v[c].var()) / 2)
    print(f"{c}: Vega7 mean {v[c].mean():+.2f} median {v[c].median():+.2f} (n {v[c].notna().sum()}) | baseline mean {b[c].mean():+.2f} median {b[c].median():+.2f} (n {b[c].notna().sum()}) | std diff {(v[c].mean()-b[c].mean())/sd:+.2f}")
    q = b[c].quantile([1/3, 2/3]).to_numpy()
    print("   baseline hit by tercile:", [f"{100*b[(b[c] > lo) & (b[c] <= hi)].won.mean():.1f}%" for lo, hi in ((-1e9, q[0]), (q[0], q[1]), (q[1], 1e9))])
