"""Second batch of attacks: timing knife-edge, stale-vs-fresh decomposition, size of the whole pie, cross-check with the analyst's trade file."""
import importlib.util, math, pickle, sys
import numpy as np, pandas as pd
sys.argv = [sys.argv[0], sys.argv[1]]
import io, contextlib
spec = importlib.util.spec_from_file_location("a3", "a3_rules.py")
a3 = importlib.util.module_from_spec(spec)
with contextlib.redirect_stdout(io.StringIO()):
    spec.loader.exec_module(a3)   # re-runs a3 silently; gives run(), attach(), summ(), pr, mk, keep
run, attach, summ, pr, mk, keep, E99, SPLIT, START, RATE = a3.run, a3.attach, a3.summ, a3.pr, a3.mk, a3.keep, a3.E99, a3.SPLIT, a3.START, a3.RATE
J, W = keep[("judged L60 f.99 m.02 D1", True)], keep[("widest L60 f.97 m.02 D1", True)]
n0 = a3.RUNS

print("== A. Losing fills when the alignment moves by one second (exclusion ON, six days) ==")
for nm, fl in (("judged", .99), ("widest", .97)):
    for D, lag in ((-1, 3), (0, 3), (1, 3), (2, 3), (3, 3), (0, 2), (1, 2), (2, 2)):
        e = run(60, fl, .02, D, True, lag=lag); lost = e[e.win == 0]
        g = lost.groupby("t0").agg(tr=("size", "count"), sh=("size", "sum"), net=("net", "sum"), q=("bq", "mean"), f=("f", "mean"), dist=("dist", "mean"), left=("m", "min"))
        g["left"] = g.index + 300 - g.left
        mk_net = e.groupby("t0").net.sum()
        print(f"  {nm} lag {lag} D {D:+d}: markets {e.t0.nunique()} net$ {e.net.sum():+.0f} c/sh {100*e.net.sum()/e['size'].sum():+.2f}; losing fills in {len(g)} market(s):",
              [(int(t), f"{r.sh:.0f} sh", f"${r.net:.0f}", f"q {r.q:.3f}", f"f {r.f:.3f}", f"dist {r.dist:.0f}", f"{int(r.left)} s left", "day Nov %d" % ((t - START) // 86400 + 21)) for t, r in g.iterrows()],
              f"markets with net < 0: {int((mk_net < 0).sum())}")

print("\n== B. Stale model (D=1: Binance closed by m-1) vs fresh model (closed by m+1 ~ real match): which prints look cheap under which clock ==")
for nm, fl in (("judged", .99), ("widest", .97)):
    df = pr.copy(); df["m"] = df.bt - 3
    df = df[(df.m >= df.t1 - 60) & (df.m <= df.t1 - 2) & (df.z >= 5) & (df.bq >= .5)].copy()
    df = attach(df, df.m - 2, "s"); df = attach(df, df.m, "x")
    cs = (df.b_up == df.sfav_up) & (df.sf >= fl) & (df.bq <= df.sf - .02 + 1e-9) & (df.sdist >= E99)
    cx = (df.b_up == df.xfav_up) & (df.xf >= fl) & (df.bq <= df.xf - .02 + 1e-9) & (df.xdist >= E99)
    for lab, sel in (("cheap under BOTH clocks", cs & cx), ("cheap only under the STALE clock (signal gone by the match)", cs & ~cx), ("cheap only under the FRESH clock (needs <1 s reaction)", ~cs & cx)):
        e = a3.size_it(df[sel].copy())
        print("  " + summ(e, 6, f"{nm} {lab}"))
        print("      tune: " + summ(e[e.t0 < SPLIT], 4, "") + "\n      report: " + summ(e[e.t0 >= SPLIT], 2, ""))
        if len(e):
            sign = np.where(e.b_up, 1, -1)
            mv = (a3.X["models"] and np.array([a3.MOD[(a, b)][1] for a, b in zip(e.t0, e.m)]) - np.array([a3.MOD[(a, b)][1] for a, b in zip(e.t0, e.m - 2)])) * sign
            g = e.groupby("t0").agg(nb=("bt", "nunique"))
            print(f"      change of the expected average in the favoured direction between the two clocks, USD: p10/p50/p90 {np.round(np.percentile(mv, [10, 50, 90]), 1).tolist()}; markets with fills in >1 block {int((g.nb > 1).sum())} of {len(g)}; seconds left p10/50/90 {np.percentile(e.t1 - e.m, [10, 50, 90]).tolist()}")

print("\n== C. The whole pie: every print that satisfied the rule, no size caps, no 5-share minimum (what ALL real takers together got) ==")
for nm, fl in (("judged", .99), ("widest", .97)):
    df = pr.copy(); df["m"] = df.bt - 3
    df = df[(df.m >= df.t1 - 60) & (df.m <= df.t1 - 2) & (df.bq >= .5)].copy(); df = attach(df, df.m - 2)
    e = df[(df.b_up == df.fav_up) & (df.f >= fl) & (df.bq <= df.f - .02 + 1e-9) & (df.dist >= E99)].copy()
    e["win"] = (e.b_up == e.up_won).astype(float); e["net"] = e.z * (e.win - e.bq - RATE * e.bq * (1 - e.bq))
    w = e.groupby("w").agg(sh=("z", "sum"), net=("net", "sum"), mk=("t0", "nunique")).sort_values("net", ascending=False)
    T = e if nm == "judged" else e
    mine = (J if nm == "judged" else W)
    print(f"  {nm}: pie {e.z.sum():,.0f} sh in {e.t0.nunique()} markets, net ${e.net.sum():,.0f} in six days = ${e.net.sum()/6:,.0f}/day for ALL takers; the rule's assumed take {mine['size'].sum():,.0f} sh = {mine['size'].sum()/e.z.sum():.0%} of shares, ${mine.net.sum():,.0f} = {mine.net.sum()/e.net.sum():.0%} of the dollars")
    print(f"      wallets {len(w)}; best wallet: ${w.net.iloc[0]:.0f} in six days (${w.net.iloc[0]/6:.1f}/day, {int(w.mk.iloc[0])} markets); 10th best ${w.net.iloc[9]:.0f}; median wallet ${w.net.median():.2f}; wallets present in >= 10 of the markets: {int((w.mk >= 10).sum())}; in >= 5: {int((w.mk >= 5).sum())}")
    per_mkt = e.groupby("t0").z.sum()
    print(f"      printed cheap size per market: p10/p50/p90 {np.round(np.percentile(per_mkt, [10, 50, 90]), 0).tolist()} sh; markets with < 100 sh: {int((per_mkt < 100).sum())}; tune pie ${e[e.t0 < SPLIT].net.sum()/4:.0f}/day, report pie ${e[e.t0 >= SPLIT].net.sum()/2:.0f}/day")

print("\n== D. Cross-check with the analyst's trade file ==")
tr = pd.read_parquet("/home/user/polymarket-lab/data/gaps_btc5m_lockin/full/trades_all_variants.parquet")
for v, e in (("L60_f0.99_m0.02_D1_excl", J), ("L60_f0.97_m0.02_D1_excl", W)):
    a = tr[tr.variant == v]; ka = dict(zip(zip(a.t0, a.seq), a["size"])); kb = dict(zip(zip(e.t0, e.seq), e["size"]))
    print(f"  {v}: analyst rows {len(a)}, mine {len(e)}, same (market, tape row) keys: {set(ka) == set(kb)}, max |size diff| {max(abs(ka[k] - kb[k]) for k in ka if k in kb):.6f}, net diff ${a.net.sum() - e.net.sum():.4f}")
g = tr.groupby(["variant", "t0"])["size"].sum()
print(f"  analyst file: variants {tr.variant.nunique()}, max shares per (variant, market) {g.max():.3f}, max size per fill {tr['size'].max():.3f}, min print size {tr.z.min():.3f}, min price {tr.bq.min():.3f}, any fill larger than its print: {bool((tr['size'] > tr.z + 1e-9).any())}, duplicate (variant, market, tape row): {int(tr.duplicated(['variant', 't0', 'seq']).sum())}")
print("  tapes with row count multiple of 1000:", mk[mk.n % 1000 == 0][["t0", "n", "shares", "volume"]].to_dict("records"))
print("\nextra diagnostic runs in this script:", a3.RUNS - n0)
