"""Sceptic's independent rule engine (own model values from a1_extract.py) + attacks. Diagnostics, not new tradable variants."""
import math, pickle, sys
import numpy as np, pandas as pd

X = pickle.load(open(sys.argv[1], "rb")); MOD = X["models"]
Y = pickle.load(open(sys.argv[1] + ".df", "rb")); mk, pr = Y["mk"], Y["pr"]
SPLIT = 1795564800; START = 1795219200; RATE = 0.05; E99 = 18.629401876966732
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 300); pd.set_option("display.float_format", "{:.3f}".format)
pr = pr.sort_values(["t0", "seq"]).reset_index(drop=True)
pr["b_up"] = np.where(pr.is_buy, pr.o_up, ~pr.o_up); pr["bq"] = np.where(pr.is_buy, pr.p, 1 - pr.p)
RUNS = 0


def rc(num, den):
    n = len(num); D = den.sum(); r = num.sum() / D
    if n < 2: return r, float("nan"), float("nan")
    e = num - r * den; se = math.sqrt(n / (n - 1) * (e ** 2).sum()) / D
    return r, se, r / se if se > 0 else float("nan")


def attach(df, t, pre=""):
    v = [MOD.get((a, b), (np.nan, np.nan, np.nan)) for a, b in zip(df.t0.values, t.values)]
    f_up = np.array([x[0] for x in v]); ea = np.array([x[1] for x in v]); k = np.array([x[2] for x in v])
    df[pre + "fav_up"] = f_up >= 0.5; df[pre + "f"] = np.where(f_up >= 0.5, f_up, 1 - f_up); df[pre + "dist"] = np.abs(ea - k); df[pre + "nan"] = np.isnan(f_up)
    return df


def run(L, floor, margin, D, excl, lag=3, e99=E99, count=True):
    global RUNS
    if count: RUNS += 1
    df = pr.copy(); df["m"] = df.bt - lag
    df = df[(df.m >= df.t1 - L) & (df.m <= df.t1 - 2)].copy()
    df = attach(df, df.m - D - 1)
    ok = (~df.nan) & (df.b_up == df.fav_up) & (df.f >= floor) & (df.bq <= df.f - margin + 1e-9) & (df.bq >= 0.5) & (df.z >= 5)
    if excl: ok &= df.dist >= e99
    return size_it(df[ok].copy())


def size_it(e):
    size = np.zeros(len(e)); cur, rem = None, 0.0
    for i, (t0, z) in enumerate(zip(e.t0.values, e.z.values)):
        if t0 != cur: cur, rem = t0, 500.0
        if rem < 5: continue
        s = min(z, 100.0, rem); size[i] = s; rem -= s
    e["size"] = size; e = e[e["size"] > 0].copy()
    e["win"] = (e.b_up == e.up_won).astype(float); e["fee"] = RATE * e.bq * (1 - e.bq); e["net"] = e["size"] * (e.win - e.bq - e.fee)
    return e


def summ(e, days, label):
    if e.empty: return f"{label}: no trades"
    g = e.groupby("t0").agg(net=("net", "sum"), sh=("size", "sum"), w=("win", "min"))
    r, se, t = rc(g.net.values, g.sh.values)
    return (f"{label}: trades {len(e)} mkts {len(g)} sh {e['size'].sum():,.0f} avgq {(e['size']*e.bq).sum()/e['size'].sum():.3f} win(tr) {e.win.mean():.3f} "
            f"mkts with any losing fill {int((g.w == 0).sum())} net {100*r:+.2f}c t {t:.1f} net$ {e.net.sum():+.0f} $/day {e.net.sum()/days:+.0f}")


def periods(e, label):
    print("  " + summ(e[e.t0 < SPLIT], 4, label + " TUNE  ")); print("  " + summ(e[e.t0 >= SPLIT], 2, label + " REPORT"))


print("== 1. Reproduction with my own extract/model (compare with results.md T3/T4) ==")
keep = {}
for nm, (L, fl, mg, D) in {"judged L60 f.99 m.02 D1": (60, .99, .02, 1), "widest L60 f.97 m.02 D1": (60, .97, .02, 1), "L60 f.99 m.02 D2": (60, .99, .02, 2),
                           "L60 f.97 m.02 D2": (60, .97, .02, 2), "L60 f.97 m.04 D2": (60, .97, .04, 2), "L30 f.97 m.02 D1": (30, .97, .02, 1), "L15 f.97 m.02 D1": (15, .97, .02, 1)}.items():
    for ex in (True, False):
        e = run(L, fl, mg, D, ex); keep[(nm, ex)] = e; periods(e, f"{nm} excl {'ON ' if ex else 'OFF'}")
J, W = keep[("judged L60 f.99 m.02 D1", True)], keep[("widest L60 f.97 m.02 D1", True)]
print("  distinct markets judged/widest:", J.t0.nunique(), W.t0.nunique(), " judged subset of widest:", set(J.t0) <= set(W.t0))

print("\n== 2. Sensitivity to the information delay D (model uses Binance closed by m-D; real match is about m+0.9) : six days, exclusion ON ==")
for nm, (fl, mg) in {"judged": (.99, .02), "widest": (.97, .02)}.items():
    for D in (-3, -2, -1, 0, 1, 2, 3, 5, 8, 12):
        e = run(60, fl, mg, D, True)
        tag = "LOOK-AHEAD" if D <= -2 else ("~at real match" if D == -1 else "")
        print("  " + summ(e, 6, f"{nm} D={D:+d} {tag}"))
print("  block lag 2 instead of 3 (m = block - 2, closer to the measured 2.09 s), D=1:")
for nm, (fl, mg) in {"judged": (.99, .02), "widest": (.97, .02)}.items():
    periods(run(60, fl, mg, 1, True, lag=2), f"{nm} lag2")

print("\n== 3. Was the signal still true at the (approximate) real match? fresh model = Binance second closing at m+1 ==")
for nm, e, fl in (("judged", J, .99), ("widest", W, .97)):
    e = attach(e.copy(), e.m, "x")
    fresh = (~e.xnan) & (e.xfav_up == e.b_up) & (e.xf >= fl) & (e.bq <= e.xf - .02 + 1e-9) & (e.xdist >= E99)
    e["xfs"] = np.where(e.xfav_up == e.b_up, e.xf, 1 - e.xf)  # fresh model probability of the side we bought
    for lab, s in (("signal STILL true", e[fresh]), ("signal GONE     ", e[~fresh])):
        print("  " + summ(s, 6, f"{nm} {lab}") + f" | fresh model prob of bought side: mean {np.average(s.xfs, weights=s['size']):.3f} min {s.xfs.min():.3f}; stale f {np.average(s.f, weights=s['size']):.3f}; "
              f"mean (fresh prob - price - fee) {100*np.average(s.xfs - s.bq - s.fee, weights=s['size']):+.2f}c; fresh dist<E99: {np.average(s.xdist < E99, weights=s['size']):.2f}")
    periods(e[fresh], f"{nm} signal still true")
    keep[(nm, "fresh")] = e[fresh]

print("\n== 4. Fills: bursts, later blocks, print type, takers ==")
for nm, e in (("judged", J), ("widest", W)):
    first = e.groupby("t0").bt.transform("min")
    later = e[e.bt > first]; later2 = e[e.bt >= first + 3]
    g = e.groupby("t0").agg(nb=("bt", "nunique"), sh=("size", "sum"))
    print(f"  {nm}: markets with all fills in ONE block {int((g.nb == 1).sum())} of {len(g)}; shares in the first qualifying block {e[e.bt == first]['size'].sum()/e['size'].sum():.2f}")
    print("  " + summ(later, 6, f"{nm} only prints in a LATER block than the first qualifying one"))
    print("  " + summ(later2, 6, f"{nm} only prints >= 3 s after the first qualifying block"))
    print(f"    from taker BUY rows {e[e.is_buy]['size'].sum()/e['size'].sum():.2f} of shares, from taker SELL rows of the other side {e[~e.is_buy]['size'].sum()/e['size'].sum():.2f}; "
          f"print size z: median {e.z.median():.1f}, share of our size from prints < 20 sh {e[e.z < 20]['size'].sum()/e['size'].sum():.2f}; wallets {e.w.nunique()}, top10 {e.groupby('w').z.sum().nlargest(10).sum()/e.z.sum():.2f} of print size")
    # all liquidity printed at rule prices in those bursts vs what the rule took
    print(f"    full printed size of the traded prints {e.z.sum():,.0f} sh vs taken {e['size'].sum():,.0f}; markets at the 500 cap {int((g.sh >= 499.99).sum())}")
    # mirror twins (same block, same size, complementary price, opposite row type) inside the traded set
    k1 = set(zip(e[e.is_buy].t0, e[e.is_buy].bt, e[e.is_buy].z.round(4), e[e.is_buy].bq.round(4)))
    tw = sum(1 for a in zip(e[~e.is_buy].t0, e[~e.is_buy].bt, e[~e.is_buy].z.round(4), e[~e.is_buy].bq.round(4)) if a in k1)
    print(f"    SELL-derived prints with a BUY twin (same block, size, price): {tw} of {int((~e.is_buy).sum())}; exact duplicate traded rows: {int(e.duplicated(subset=['t0','bt','is_buy','o_up','p','z','w']).sum())} of {len(e)}")

print("\n== 5. Price path around the burst (favoured side, all buyable prints of that side, size-weighted) ==")
for nm, e in (("judged", J), ("widest", W)):
    rows = []
    for t0, x in e.groupby("t0"):
        b0 = x.bt.min(); side = x.b_up.iloc[0]; a = pr[(pr.t0 == t0) & (pr.b_up == side)]
        def vw(s): return np.average(s.bq, weights=s.z) if len(s) and s.z.sum() > 0 else np.nan
        rows.append((t0, vw(x), vw(a[(a.bt < b0) & (a.bt >= b0 - 6)]), vw(a[a.bt == b0]), vw(a[(a.bt > b0) & (a.bt <= b0 + 4)]), vw(a[(a.bt > b0 + 4) & (a.bt <= b0 + 10)]),
                     a[(a.bt > b0) & (a.bt <= b0 + 4)].bq.min(), a[a.bt == b0].z.sum(), a[(a.bt == b0) & (a.bq >= 0.98)].z.sum()))
    r = pd.DataFrame(rows, columns=["t0", "paid", "pre6", "blk", "post4", "post10", "min_post4", "blk_sh", "blk_sh_98"])
    print(f"  {nm}: median price paid {r.paid.median():.3f}; favoured-side VWAP 6 s before {r.pre6.median():.3f} (n {r.pre6.notna().sum()}), in the burst block {r.blk.median():.3f}, 1-4 s after {r.post4.median():.3f} (n {r.post4.notna().sum()}), 5-10 s after {r.post10.median():.3f}")
    print(f"    markets where the VWAP 6 s BEFORE the burst was already <= price paid + 0.01: {int((r.pre6 <= r.paid + 0.01).sum())}; markets where 1-4 s AFTER it is still <= paid + 0.01: {int((r.post4 <= r.paid + 0.01).sum())}; "
          f"markets where some print 1-4 s after is <= paid: {int((r.min_post4 <= r.paid).sum())}; share of same-block same-side volume printed at >= 0.98: {r.blk_sh_98.sum()/r.blk_sh.sum():.2f}")

print("\n== 6. Statistics: by day, drop best day, drop best ten markets ==")
for nm, e in (("judged", J), ("widest", W), ("widest signal-still-true", keep[("widest", "fresh")])):
    e = e.assign(day=(e.t0 - START) // 86400 + 21)
    bd = e.groupby("day").agg(mk=("t0", "nunique"), sh=("size", "sum"), net=("net", "sum"))
    print(f"  {nm} by day:", {int(d): (int(r.mk), round(r.sh), round(r.net)) for d, r in bd.iterrows()})
    best = bd.net.idxmax(); x = e[e.day != best]
    print("  " + summ(x, 5, f"{nm} without best day (Nov {best})"))
    g = e.groupby("t0").net.sum().sort_values(ascending=False)
    x = e[~e.t0.isin(g.index[:10])]
    print("  " + summ(x, 6, f"{nm} without the ten best markets") + f" | top-10 markets = {g.iloc[:10].sum()/g.sum():.0%} of net$; median market net ${g.median():.2f}; markets with net < $5: {int((g < 5).sum())}")
    gg = e.groupby("t0").agg(net=("net", "sum"), cost=("size", lambda s: 0)).net
    hrs = e.groupby((e.t0 // 3600)).t0.nunique()
    print(f"    distinct hours with a trade {len(hrs)} for {e.t0.nunique()} markets; max markets in one hour {int(hrs.max())}; one loss at the cap would cost about ${500*0.945+500*RATE*0.945*0.055:.0f} vs total net ${e.net.sum():.0f}")

print("\n== 7. E99 sensitivity (widest, D=1, six days) and the unfiltered losers ==")
for th in (0, 5, 10, 15, 18.63, 20.46, 25, 30):
    print("  " + summ(run(60, .97, .02, 1, True, e99=th), 6, f"|EA-K| >= {th:5.2f}"))
e = keep[("widest L60 f.97 m.02 D1", False)]; lost = e[e.win == 0]
print(lost.groupby("t0").agg(tr=("size", "count"), sh=("size", "sum"), net=("net", "sum"), q=("bq", "mean"), f=("f", "mean"), dist=("dist", "mean"), left=("m", lambda s: 0)).drop(columns="left").to_string())

print("\n== 8. Hand check of accounting (raw tape row -> our numbers) ==")
s = J.sample(6, random_state=3)
for r in s.itertuples():
    print(f"  t0 {r.t0} block {r.bt} (t1{r.bt - r.t1:+d}) raw {'BUY' if r.is_buy else 'SELL'} {'Up' if r.o_up else 'Down'} p={r.p:.4f} z={r.z:.3f} -> buy {'Up' if r.b_up else 'Down'} at {r.bq:.4f} size {r.size:.3f}; "
          f"model f {r.f:.4f} dist {r.dist:.1f}; up_won {r.up_won}; fee/sh {RATE*r.bq*(1-r.bq):.5f}; net {r.net:.4f} = {r.size:.3f}*({int(r.win)}-{r.bq:.4f}-{RATE*r.bq*(1-r.bq):.5f})")
print("\ndiagnostic runs executed by this script:", RUNS)
pickle.dump({k: v for k, v in keep.items()}, open(sys.argv[1] + ".trades", "wb"))
