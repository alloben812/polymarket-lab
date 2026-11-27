"""Third batch: who really took the cheap prints, pie under both clocks, D=0 by period, tape completeness of the traded markets."""
import importlib.util, io, contextlib, sys
import numpy as np, pandas as pd
spec = importlib.util.spec_from_file_location("a3", "a3_rules.py"); a3 = importlib.util.module_from_spec(spec)
with contextlib.redirect_stdout(io.StringIO()):
    spec.loader.exec_module(a3)
run, attach, summ, pr, mk, keep, E99, SPLIT, START, RATE = a3.run, a3.attach, a3.summ, a3.pr, a3.mk, a3.keep, a3.E99, a3.SPLIT, a3.START, a3.RATE
W = keep[("widest L60 f.97 m.02 D1", True)]; n0 = a3.RUNS
print("== E. Real takers of the qualifying prints (widest, D=1, no caps) ==")
df = pr.copy(); df["m"] = df.bt - 3
df = df[(df.m >= df.t1 - 60) & (df.m <= df.t1 - 2) & (df.bq >= .5)].copy(); df = attach(df, df.m - 2, "s"); df = attach(df, df.m, "x")
cs = (df.b_up == df.sfav_up) & (df.sf >= .97) & (df.bq <= df.sf - .02 + 1e-9) & (df.sdist >= E99)
cx = (df.b_up == df.xfav_up) & (df.xf >= .97) & (df.bq <= df.xf - .02 + 1e-9) & (df.xdist >= E99)
for lab, sel in (("stale clock (the study's rule)", cs), ("both clocks", cs & cx)):
    e = df[sel].copy(); e["win"] = (e.b_up == e.up_won).astype(float); e["net"] = e.z * (e.win - e.bq - RATE * e.bq * (1 - e.bq))
    w = e.groupby("w").agg(sh=("z", "sum"), net=("net", "sum"), mk=("t0", "nunique"), n=("z", "count")).sort_values("mk", ascending=False)
    print(f"  {lab}: pie {e.z.sum():,.0f} sh, ${e.net.sum():,.0f} in six days (${e.net.sum()/6:.0f}/day; tune ${e[e.t0<SPLIT].net.sum()/4:.0f}/day, report ${e[e.t0>=SPLIT].net.sum()/2:.0f}/day), {e.t0.nunique()} markets, {len(w)} wallets")
    print("    five most frequent wallets (markets, prints, shares, net $ six days):", [(int(r.mk), int(r.n), round(r.sh), round(r.net, 1)) for r in w.head(5).itertuples()])
    print(f"    five richest wallets net $: {np.round(w.net.nlargest(5).values, 1).tolist()} ; share of pie dollars taken by the top wallet {w.net.max()/e.net.sum():.1%}, by the top 10 {w.net.nlargest(10).sum()/e.net.sum():.1%}")
print("\n== F. Tightest legitimate alignment (D=0: Binance second closing at m; real match about 0.9 s later) by period ==")
for nm, fl in (("judged", .99), ("widest", .97)):
    e = run(60, fl, .02, 0, True)
    print("  " + summ(e[e.t0 < SPLIT], 4, f"{nm} D=0 TUNE  ")); print("  " + summ(e[e.t0 >= SPLIT], 2, f"{nm} D=0 REPORT"))
print("\n== G. Tape completeness for the traded markets ==")
x = mk[mk.t0.isin(W.t0.unique())]
print("  traded markets (widest):", len(x), " with gamma volume to compare:", int(x.volume.notna().sum()), " matching:", int(((x.shares - x.volume).abs() / x.volume < 1e-6).sum()),
      " no-volume markets: last tape row minus t1 min", int((x[x.volume.isna()].tmax - x[x.volume.isna()].t0 - 300).min()) if x.volume.isna().any() else None)
nv = mk[mk.volume.isna()]
print("  all 153 no-volume markets: rows min/median", int(nv.n.min()), int(nv.n.median()), " last row minus t1 min", int((nv.tmax - nv.t0 - 300).min()), " shares median", round(nv.shares.median()), "vs", round(mk[mk.volume.notna()].shares.median()))
print("  rows with block time in the last 60 s per market: min", int(pr[(pr.bt - 3 >= pr.t1 - 60) & (pr.bt - 3 < pr.t1)].groupby('t0').size().reindex(mk.t0, fill_value=0).min()))
print("extra runs:", a3.RUNS - n0)
