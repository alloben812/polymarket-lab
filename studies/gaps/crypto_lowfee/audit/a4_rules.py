"""Audit stage 4: M4 / M5 rebuilt from raw with my own code; sensitivity to the assumed block lag; robustness
(drop best/worst day, drop top/bottom ten markets); auditor's exploratory 'jump' rule.
Usage: python3 -I a4_rules.py <scratch_dir>"""
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


ana = pd.read_csv(f"{OUTA}/rules.csv") if __import__("os").path.exists(f"{OUTA}/rules.csv") else None
SEL4 = {"eth-5m": (0, 0.02), "eth-15m": (0, 0.01), "sol-15m": (0, 0.02), "xrp-15m": (2, 0.01), "btc-15m": (0, 0.04)}
allrows = []
for name in NAMES[:5]:
    for BL in (3, 2, 1):
        d, G, dev, dur = prints(name, BL)
        for D in (0, 1, 2, 5):
            for thr in (0.01, 0.02, 0.04):
                x = capped(m4_sel(d, G, dur, D, thr))
                for per in ("tune", "report"):
                    allrows.append({"series": name, "BL": BL, "family": "M4", "variant": f"D{D}_thr{thr:.2f}", "period": per, **summ(x, per)})
                if BL == 3 and (D, thr) == SEL4[name]:
                    print(f"\n##### {name} selected M4 D{D}_thr{thr:.2f} (block lag 3 as in the study)")
                    for per in ("tune", "report"):
                        print("  ", per, summ(x, per))
                    a = x.groupby("t0")[["net", "sh"]].sum(); r, se, t = rc(a.net, a.sh)
                    print("   pooled 6 days: net c/sh %.2f se %.2f t %.2f mkts %d | per day $: %s" % (100 * r, 100 * se, t, len(a), x.groupby("day").net.sum().round(0).to_dict()))
                    xr = x[x.per == "report"]; a = xr.groupby("t0")[["net", "sh"]].sum()
                    top = a.net.sort_values()
                    for lab, keep in (("drop 10 best mkts", top.index[:-10]), ("drop 10 worst mkts", top.index[10:])):
                        r, se, t = rc(a.net[keep], a.sh[keep]); print("   report, %s: net c/sh %.2f t %.2f $/day %.0f" % (lab, 100 * r, t, a.net[keep].sum() / 2))
                    print("   report: share of net $ from 10 best mkts %.0f, 10 worst %.0f, total %.0f | underdog (q<0.5) share of shares %.2f | prints <5 sh: %.2f of trades | full print size uncapped: %s" % (
                        top[-10:].sum(), top[:10].sum(), top.sum(), xr.sh[xr.q < 0.5].sum() / xr.sh.sum(), (xr.z < 5).mean(),
                        summ(m4_sel(d, G, dur, D, thr).assign(sh=lambda v: v.z).assign(net=lambda v: v.sh * (v.won - v.q) - v.sh * v.rate * v.q * (1 - v.q), cost=lambda v: v.sh * v.q), "report")))
        for margin in (0.03, 0.05, 0.08):
            for twobp in (False, True):
                x = capped(m5_sel(d, G, dev, dur, margin, twobp))
                for per in ("tune", "report"):
                    allrows.append({"series": name, "BL": BL, "family": "M5", "variant": f"mrg{margin:.2f}" + ("_2bp" if twobp else ""), "period": per, **summ(x, per)})
R = pd.DataFrame(allrows)
R.to_csv(f"{S}/audit_rules.csv", index=False)
# compare with the analyst's table
if ana is not None:
    mine = R[R.BL == 3].merge(ana[["series", "variant", "period", "trades", "markets", "net_c", "t", "usd_per_day"]], on=["series", "variant", "period"], suffixes=("", "_a"))
    print("\n== comparison with analyst rules.csv (block lag 3): rows %d, trades equal %d, max |net_c diff| %.4f, max |t diff| %.4f, max |$ per day diff| %.3f" % (
        len(mine), int((mine.trades == mine.trades_a).sum()), (mine.net_c - mine.net_c_a).abs().max(), (mine.t - mine.t_a).abs().max(), (mine.usd_day - mine.usd_per_day).abs().max()))
rep = R[R.period == "report"]
print("\n== reporting period, by assumed block lag: variants positive with t>2 and >=100 markets / t range of M4 per series")
for BL in (3, 2, 1):
    x = rep[rep.BL == BL]
    hit = x[(x.t > 2) & (x.net_c > 0) & (x.mkts >= 100)]
    print(f"BL={BL}: positive t>2 on >=100 mkts: {len(hit)} of {len(x)}", "|", "; ".join(f"{s} M4 t {v.t.min():+.1f}..{v.t.max():+.1f}, c/sh {v.net_c.min():+.2f}..{v.net_c.max():+.2f}" for s, v in x[x.family == "M4"].groupby("series", sort=False)))
    if len(hit): print(hit.to_string(index=False))
print("\n== M4 by delay, share-weighted over thresholds is not recomputed; net c/sh of thr0.02 by D, tune | report, per block lag")
for name in NAMES[:5]:
    for BL in (3, 2, 1):
        x = R[(R.series == name) & (R.BL == BL) & (R.family == "M4") & R.variant.str.endswith("thr0.02")]
        print(name, f"BL={BL}", "tune:", " ".join(f"D{v[1]}={n:+.2f}({t:+.1f})" for v, n, t in zip(x[x.period == 'tune'].variant, x[x.period == 'tune'].net_c, x[x.period == 'tune'].t)),
              "| report:", " ".join(f"D{v[1]}={n:+.2f}({t:+.1f})" for v, n, t in zip(x[x.period == 'report'].variant, x[x.period == 'report'].net_c, x[x.period == 'report'].t)))
print("\n== M5 (block lag 3) all rows")
print(R[(R.family == "M5") & (R.BL == 3)].pivot_table(index=["series", "variant"], columns="period", values=["trades", "mkts", "net_c", "t", "usd_day"], sort=False).to_string())

# auditor's exploratory rule: buy in the direction of a recent Binance-driven jump of the fair value (stale-quote hitter)
print("\n== auditor's 'jump' rule (not in the protocol): buy side whose fair value rose >= x over the last k s, f up to m; 50/300 sizing")
jr = []
for name in NAMES:
    for BL in (3, 2):
        d, G, dev, dur = prints(name, BL)
        b = d[(d.m >= d.t0 + 15) & (d.m <= d.t0 + dur - 5)]
        for k in (3, 10):
            now = look(G, b.r.to_numpy(), (b.m - 1 - b.t0).to_numpy(), dur); old = look(G, b.r.to_numpy(), (b.m - 1 - k - b.t0).to_numpy(), dur)
            jump = np.where(b.eq_up, now - old, old - now)
            for xthr in (0.03, 0.06):
                x = capped(b[np.nan_to_num(jump, nan=-9.0) >= xthr])
                jr.append({"series": name, "BL": BL, "k": k, "x": xthr, **{f"{p}_{kk}": vv for p in ("tune", "report") for kk, vv in summ(x, p).items() if kk in ("mkts", "trades", "net_c", "t", "usd_day", "avg_q")}})
print(pd.DataFrame(jr).to_string(index=False))
