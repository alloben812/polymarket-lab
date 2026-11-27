"""Audit stage 2: data integrity, settlement direction, fees, M2, proxy check; cross-check of my fair grid with the analyst's.
Usage: python3 -I a2_checks.py <scratch_dir>"""
import sys
import numpy as np, pandas as pd

S = sys.argv[1]
BIG = "/home/user/polymarket-lab/data/gaps_crypto_lowfee"
T_REPORT = 1795564800
NAMES = ["eth-5m", "eth-15m", "sol-15m", "xrp-15m", "btc-15m", "btc-5m"]
DUR = {"eth-5m": 300, "btc-5m": 300}
pd.set_option("display.width", 250)


def rc(num, den):
    num, den = np.asarray(num, float), np.asarray(den, float)
    n = len(num); r = num.sum() / den.sum()
    e = num - r * den
    se = np.sqrt(n / (n - 1) * (e * e).sum()) / den.sum()
    return r, se, r / se


for name in NAMES:
    dur = DUR.get(name, 900)
    mk = pd.read_parquet(f"{S}/{name}_mk.parquet"); f = pd.read_parquet(f"{S}/{name}_tape.parquet")
    g = np.load(f"{S}/{name}_G.npz")
    print(f"\n===== {name}: markets {len(mk)}, found {int(mk.found.sum())}, rows {len(f)}")
    print("rates", mk.rate.value_counts().to_dict(), "| fee_type", mk.fee_type.value_counts().to_dict(), "| lookback", mk.lookback.value_counts().to_dict(),
          "| closed", int(mk.closed.sum()), "| slug_ok", int(mk.slug_ok.sum()), "| t1_ok", int(mk.t1_ok.sum()), "| cond unique", mk.cond.nunique())
    print("official: up share %.3f | (final>=ptb)!=up_won: %d | final==ptb ties: %d | missing ptb/final: %d" % (
        mk.up_won.mean(), int(((mk.final >= mk.ptb) != mk.up_won).sum()), int((mk.final == mk.ptb).sum()), int(mk.ptb.isna().sum() + mk.final.isna().sum())))
    # tape integrity
    vol = mk.dropna(subset=["volume"])
    rel = (vol.shares / vol.volume)
    print("tape: unsorted files %d | markets with 0 rows %d | max rows %d | exact dup rows %d (%.2f%%) | gamma volume present %d, tape shares / gamma volume: median %.4f, <0.98: %d, >1.02: %d" % (
        int((~mk.sorted).sum()), int((mk.n_rows == 0).sum()), int(mk.n_rows.max()), int(mk.dups.sum()), 100 * mk.dups.sum() / len(f), len(vol), rel.median(), int((rel < 0.98).sum()), int((rel > 1.02).sum())))
    print("     rows per file that are multiples of 500/1000:", int(((mk.n_rows % 500 == 0) & (mk.n_rows > 0)).sum()),
          "| p<=0 or >=1:", int(((f.p <= 0) | (f.p >= 1)).sum()), "| z<=0:", int((f.z <= 0).sum()), "| sides", f.s.value_counts().to_dict(), "| outcomes", f.o.value_counts().to_dict())
    rt = (f.t - f.t0) / dur
    print("     block time rel. to window: before t0 %.3f, inside %.3f, after t1 %.3f | earliest %.1f h before t0, latest %.0f s after t1 | last in-window row median %.0f s before t1" % (
        (rt < 0).mean(), ((rt >= 0) & (rt < 1)).mean(), (rt >= 1).mean(), -(f.t - f.t0).min() / 3600, (f.t - f.t0 - dur).max(),
        (mk.t0 + dur - mk.t_max).clip(lower=0).median()))
    # M2 from scratch
    up_won = f.t0.map(mk.set_index("t0").up_won).to_numpy(bool)
    rate = f.t0.map(mk.set_index("t0").rate).to_numpy(float)
    tok_won = np.where(f.o == "Up", up_won, ~up_won).astype(float)
    buy = (f.s == "BUY").to_numpy()
    gross = np.where(buy, tok_won - f.p, f.p - tok_won) * f.z
    fee = rate * f.p * (1 - f.p) * f.z
    d = pd.DataFrame({"t0": f.t0, "gross": gross, "fee": fee, "net": gross - fee, "z": f.z, "usd": f.p * f.z})
    for per, sel in (("all", d.t0 > 0), ("tune", d.t0 < T_REPORT), ("report", d.t0 >= T_REPORT)):
        a = d[sel].groupby("t0").sum()
        r, se, t = rc(a.net, a.z); r2, _, _ = rc(a.net, a.usd)
        print("M2 %-6s mkts %4d shares %12.0f usd %11.0f gross %.3f fee %.3f net %.3f c/sh se %.3f t %.2f | net %% turnover %.3f | wallets %d" % (
            per, len(a), a.z.sum(), a.usd.sum(), 100 * a.gross.sum() / a.z.sum(), 100 * a.fee.sum() / a.z.sum(), 100 * r, 100 * se, t, 100 * r2, f[sel.to_numpy()].w.nunique()))
    # three fills by hand
    for i in (0, len(f) // 2, len(f) - 1):
        x = f.iloc[i]; uw = bool(mk.set_index("t0").up_won[x.t0]); rt_ = float(mk.set_index("t0").rate[x.t0])
        won = (x.o == "Up") == uw
        gr = (1.0 * won - x.p) if x.s == "BUY" else (x.p - 1.0 * won)
        print("   hand: %s %s %.4f sh at %.4f, up_won=%s -> token won=%s, gross/sh %.4f, fee/sh %.6f (rate %.2f), net $ %.4f" % (x.s, x.o, x.z, x.p, uw, won, gr, rt_ * x.p * (1 - x.p), rt_, x.z * (gr - rt_ * x.p * (1 - x.p))))
    # proxy
    pr = mk.dropna(subset=["twap1_bin"])
    bp = ((pr.twap1_bin - pr.final) - (pr.k_bin - pr.ptb)) / pr.ptb * 1e4
    wrong = (pr.twap1_bin >= pr.k_bin) != pr.up_won
    print("proxy: n %d sd %.2f bp, wrong %d (%.2f%%), max official move in misses %.2f bp, median basis %.1f bp" % (len(pr), bp.std(), int(wrong.sum()), 100 * wrong.mean(),
          ((pr.final / pr.ptb - 1).abs() * 1e4)[wrong].max(), ((pr.k_bin / pr.ptb - 1) * 1e4).median()))
    # compare my grid with the analyst's
    ga = np.load(f"{BIG}/{name}_grid.npz")
    assert (ga["t0"] == g["t0"]).all()
    diff = np.abs(ga["G"] - g["G"])
    print("fair grid: max |mine - analyst| = %.2e, NaN mine %d analyst %d" % (np.nanmax(diff), int(np.isnan(g["G"]).sum()), int(np.isnan(ga["G"]).sum())))
    fa = pd.read_parquet(f"{BIG}/{name}_fills.parquet")
    print("analyst fills rows", len(fa), "| sum z equal:", bool(abs(fa.z.sum() - f.z.sum()) < 1e-6), "| rate values", fa.rate.value_counts().to_dict())
