"""Audit stage 5: (1) is the lag drift in the tape or in the Binance files? Chainlink official values as an independent clock;
(2) M1 spot check, pre-fee-change rows; (3) M2 buckets; (4) dependence between markets/series for the selected M4 variants;
(5) selected variants under other block lags. Usage: python3 -I a5_extra.py <scratch_dir>"""
import io, sys, zipfile
import numpy as np, pandas as pd

S = sys.argv[1]
ROOT = "/home/user/polymarket-lab"
BASE, T_START, T_REPORT, FEE_CHANGE = 1795132800, 1795219200, 1795564800, 1795219140
SYM = {"eth-5m": "ETHUSDT", "sol-15m": "SOLUSDT", "xrp-15m": "XRPUSDT", "btc-15m": "BTCUSDT"}
DUR = {"eth-5m": 300, "btc-5m": 300}
NAMES = ["eth-5m", "eth-15m", "sol-15m", "xrp-15m", "btc-15m", "btc-5m"]
pd.set_option("display.width", 250)


def rc(num, den):
    num, den = np.asarray(num, float), np.asarray(den, float); n = len(num)
    r = num.sum() / den.sum(); e = num - r * den
    se = np.sqrt(n / (n - 1) * (e * e).sum()) / den.sum()
    return r, se, r / se


print("== (1) shift of the Binance 60 s average that best matches the official Chainlink values, by UTC day (sd of window drift in bp at shift 0 / best)")
for name, sym in SYM.items():
    c = np.full(7 * 86400, np.nan)
    for d in range(20, 27):
        z = zipfile.ZipFile(f"{ROOT}/data/binance_1s/{sym}-1s-2026-11-{d}.zip")
        a = np.loadtxt(io.BytesIO(z.read(z.namelist()[0])), delimiter=",", usecols=(0, 4))
        c[(a[:, 0] // 1_000_000).astype(np.int64) - BASE] = a[:, 1]
    C = np.concatenate([[0.0], np.cumsum(c)])
    mk = pd.read_parquet(f"{S}/{name}_mk.parquet"); dur = DUR.get(name, 900)
    mk = mk[mk.t0 + dur + 20 < BASE + 7 * 86400]
    i0, i1 = (mk.t0 - BASE).to_numpy(), (mk.t0 + dur - BASE).to_numpy()
    day = ((mk.t0 - T_START) // 86400).to_numpy()
    shifts = np.arange(-4, 13)
    out = []
    for k in range(6):
        m = day == k
        sd = []
        for s in shifts:
            tw0 = (C[i0[m] - s + 1] - C[i0[m] - s - 59]) / 60; tw1 = (C[i1[m] - s + 1] - C[i1[m] - s - 59]) / 60
            sd.append(np.std((np.log(tw1 / mk.final.to_numpy()[m]) - np.log(tw0 / mk.ptb.to_numpy()[m])) * 1e4))
        sd = np.array(sd); j = int(np.argmin(sd))
        j = min(max(j, 1), len(sd) - 2)
        den = sd[j - 1] - 2 * sd[j] + sd[j + 1]
        best = shifts[j] + 0.5 * (sd[j - 1] - sd[j + 1]) / den
        out.append(f"11-{21 + k}: {best:.1f}s ({sd[4]:.2f}/{sd.min():.2f})")
    print(f"{name:8s}", " | ".join(out))

print("\n== (2) M1 spot check and rows before the fee change (20 Nov 23:59 UTC)")
for name in NAMES:
    dur = DUR.get(name, 900)
    f = pd.read_parquet(f"{S}/{name}_tape.parquet"); mk = pd.read_parquet(f"{S}/{name}_mk.parquet")
    usd = f.p * f.z
    w = usd.groupby(f.w).sum().sort_values(ascending=False)
    inw = f[(f.t - 3 >= f.t0) & (f.t - 3 < f.t0 + dur)]
    pre = f.t < FEE_CHANGE
    print("%-8s $/day %.0f | median $/market %.0f | wallets %d | top-5 share %.3f | seconds with a fill %.3f | fills <5 sh %.3f | rows before fee change %d (%.2f%% of $)" % (
        name, usd.sum() / 6 * (1726 / 300 if name == "btc-5m" else 1), usd.groupby(f.t0).sum().median(), f.w.nunique(), w.head(5).sum() / w.sum(),
        inw.groupby("t0").t.nunique().sum() / (len(mk) * dur), (f.z < 5).mean(), int(pre.sum()), 100 * usd[pre].sum() / usd.sum()))

print("\n== (3) M2 buckets rebuilt: net c/sh (t) by time bucket (match = block - 3) and by equivalent-buy price")
best = []
for name in NAMES:
    dur = DUR.get(name, 900)
    f = pd.read_parquet(f"{S}/{name}_tape.parquet"); mk = pd.read_parquet(f"{S}/{name}_mk.parquet").set_index("t0")
    uw = f.t0.map(mk.up_won).to_numpy(bool); rate = f.t0.map(mk.rate).to_numpy(float)
    buy = (f.s == "BUY").to_numpy(); tokw = np.where(f.o == "Up", uw, ~uw).astype(float)
    net = (np.where(buy, tokw - f.p, f.p - tokw) - rate * f.p * (1 - f.p)) * f.z
    q = np.where(buy, f.p, 1 - f.p)
    rel = (f.t - 3 - f.t0) / dur
    tb = np.select([rel < 0, rel < 0.25, rel < 0.5, rel < 0.75, rel < 1.0], ["pre", "Q1", "Q2", "Q3", "Q4"], "post")
    qb = pd.cut(q, [0, 0.10, 0.30, 0.50, 0.70, 0.90, 1.0001], right=False).astype(str)
    d = pd.DataFrame({"t0": f.t0, "net": net, "z": f.z, "tb": tb, "qb": qb, "side": np.where(buy, "BUY", "SELL")})
    line = []
    for col in ("tb", "qb", "side"):
        for key, x in d.groupby(col):
            a = x.groupby("t0")[["net", "z"]].sum(); r, se, t = rc(a.net, a.z)
            line.append(f"{key} {100 * r:+.2f}({t:+.1f})"); best.append((t, name, key, 100 * r))
    print(f"{name:8s}", "  ".join(line))
best.sort(reverse=True)
print("largest t over all 84 cells:", [(round(t, 2), n, k, round(r, 2)) for t, n, k, r in best[:4]])

print("\n== (4) dependence: per-market net $ of the selected M4 variants (block lag 3), reporting and all days")
R = pd.read_csv(f"{S}/audit_rules.csv")
import importlib.util
spec = importlib.util.spec_from_file_location("a4", f"{ROOT}/studies/gaps/crypto_lowfee/audit/a4_lib.py"); a4 = importlib.util.module_from_spec(spec); sys.argv = ["x", S]; spec.loader.exec_module(a4)
SEL4 = {"eth-15m": (0, 0.01), "sol-15m": (0, 0.02), "xrp-15m": (2, 0.01), "btc-15m": (0, 0.04), "eth-5m": (0, 0.02)}
per_mkt = {}
for name, (D, thr) in SEL4.items():
    d, G, dev, dur = a4.prints(name, 3)
    x = a4.capped(a4.m4_sel(d, G, dur, D, thr))
    a = x.groupby("t0")[["net", "sh"]].sum(); per_mkt[name] = a
    ac1 = a.net.reindex(sorted(a.index)).autocorr(1)
    rep = a[a.index >= T_REPORT]
    blk = rep.groupby((rep.index - T_REPORT) // 10800).sum(); r, se, t = rc(blk.net, blk.sh)
    hb = rep.groupby((rep.index - T_REPORT) // 3600).sum(); r2, se2, t2 = rc(hb.net, hb.sh)
    print("%-8s lag-1 autocorr of market net %.3f | report net c/sh %.2f: t by 1-hour block %.2f (n=%d), by 3-hour block %.2f (n=%d)" % (name, ac1, 100 * r, t2, len(hb), t, len(blk)))
m = pd.DataFrame({k: v.net for k, v in per_mkt.items() if k != "eth-5m"}).dropna()
print("correlation of per-window net $ between the four 15m series (same windows, n=%d):" % len(m)); print(m.corr().round(2).to_string())
e5 = per_mkt["eth-5m"].net; e5 = e5.groupby(e5.index // 900 * 900).sum()
print("eth-5m (summed to 15m) vs eth-15m: %.2f" % pd.concat([e5, per_mkt["eth-15m"].net], axis=1).dropna().corr().iloc[0, 1])

print("\n== (5) selected variants in the reporting period under block lag 3 / 2 / 1")
sel = [("eth-5m", "M4", "D0_thr0.02"), ("eth-15m", "M4", "D0_thr0.01"), ("sol-15m", "M4", "D0_thr0.02"), ("xrp-15m", "M4", "D2_thr0.01"), ("btc-15m", "M4", "D0_thr0.04"),
       ("eth-5m", "M5", "mrg0.08"), ("eth-5m", "M5", "mrg0.03_2bp"), ("btc-15m", "M5", "mrg0.03")]
for s, fam, v in sel:
    x = R[(R.series == s) & (R.variant == v) & (R.period == "report")].sort_values("BL", ascending=False)
    print(f"{s:8s} {fam} {v:12s}", " | ".join(f"BL={int(b)}: {n:+.2f} c/sh t {t:+.1f} mkts {int(k)} ${u:+.0f}/day" for b, n, t, k, u in zip(x.BL, x.net_c, x.t, x.mkts, x.usd_day)))
