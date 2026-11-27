"""Descriptive diagnostic (no rule, no caps): every buyable print of the Binance leader in the last 60 s, split by whether
|expected average - K| >= E99 on the D=1 clock, by price bucket. Also: tapes that stop early."""
import importlib.util, io, contextlib, math, sys
import numpy as np, pandas as pd
spec = importlib.util.spec_from_file_location("a3", "a3_rules.py"); a3 = importlib.util.module_from_spec(spec)
with contextlib.redirect_stdout(io.StringIO()):
    spec.loader.exec_module(a3)
attach, pr, mk, E99, SPLIT, RATE, rc = a3.attach, a3.pr, a3.mk, a3.E99, a3.SPLIT, a3.RATE, a3.rc
df = pr.copy(); df["m"] = df.bt - 3
df = df[(df.m >= df.t1 - 60) & (df.m <= df.t1 - 2)].copy(); df = attach(df, df.m - 2)
df = df[(df.b_up == df.fav_up) & (df.bq >= .5)].copy()
df["win"] = (df.b_up == df.up_won).astype(float); df["net"] = df.z * (df.win - df.bq - RATE * df.bq * (1 - df.bq))
B = [(.5, .9), (.9, .95), (.95, .97), (.97, .98), (.98, .99), (.99, 1.01), (.5, 1.01)]
for lab, sel in (("FAR: |EA-K| >= E99 (18.63)", df.dist >= E99), ("NEAR: |EA-K| < E99", df.dist < E99)):
    print("==", lab, "- leader side by the D=1 Binance clock, all buyable prints, no caps ==")
    for lo, hi in B:
        out = [f"{lo:.2f}-{min(hi,1):.2f}"]
        for a, b, days in ((0, 10**12, 6), (0, SPLIT, 4), (SPLIT, 10**12, 2)):
            s = df[sel & (df.bq >= lo - 1e-12) & (df.bq < hi - 1e-12) & (df.t0 >= a) & (df.t0 < b)]
            if s.empty: out.append("none"); continue
            g = s.groupby("t0").agg(net=("net", "sum"), z=("z", "sum"), w=("win", "min")); r, se, t = rc(g.net.values, g.z.values)
            out.append(f"mk {len(g)} (lost {int((g.w==0).sum())}) sh {s.z.sum():,.0f} win {np.average(s.win, weights=s.z):.4f} net {100*r:+.2f}c t {t:+.1f} ${s.net.sum()/days:+,.0f}/d")
        print("  " + " | ".join(out))
    # seconds-left split for the far states
far = df[df.dist >= E99]
for lo, hi in ((40, 61), (22, 40), (2, 22)):
    s = far[(far.t1 - far.m >= lo) & (far.t1 - far.m < hi)]
    for qlo, qhi in ((.5, .97), (.97, 1.01)):
        x = s[(s.bq >= qlo - 1e-12) & (s.bq < qhi - 1e-12)]
        if x.empty: print(f"  far, {lo}-{hi-1} s left, price {qlo}-{min(qhi,1)}: none"); continue
        g = x.groupby("t0").agg(net=("net", "sum"), z=("z", "sum"), w=("win", "min")); r, se, t = rc(g.net.values, g.z.values)
        print(f"  far, {lo}-{hi-1} s left, price {qlo:.2f}-{min(qhi,1):.2f}: mk {len(g)} (lost {int((g.w==0).sum())}) sh {x.z.sum():,.0f} net {100*r:+.2f}c t {t:+.1f}")
print("\n== tapes that stop before the end ==")
e = mk.assign(last=mk.tmax - mk.t0 - 300, absd=(mk.final - mk.ptb).abs())
early = e[e["last"] < -10]
print("  markets whose last tape row is more than 10 s before t1:", len(early), "; their |final - ptb| p10/p50:", np.round(np.nanpercentile(early.absd, [10, 50]), 1).tolist(), " vs all markets p50", round(float(np.nanmedian(e.absd)), 1),
      "; with gamma volume matching:", int(((early.shares - early.volume).abs() / early.volume < 1e-6).sum()), "of", int(early.volume.notna().sum()))
