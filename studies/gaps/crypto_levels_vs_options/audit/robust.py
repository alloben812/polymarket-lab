import json, gzip, math, time
import numpy as np, pandas as pd
from pathlib import Path
D = Path("/home/user/polymarket-lab/data/gaps_levels")
iso = lambda t: time.strftime("%m-%d %H:%M", time.gmtime(t))
E = pd.read_parquet("my_entries.parquet"); E["stake"] = 20.0
P = pd.read_parquet("my_panel.parquet").set_index(["cond", "t"]).sort_index()
def rc(num, den):
    n = len(num); ds = den.sum(); r = num.sum() / ds
    if n < 2: return r, float("nan"), float("nan")
    res = num - r * den; se = math.sqrt(n / (n - 1) * (res ** 2).sum()) / ds
    return r, se, r / se
def line(e, label, by="cluster", pnl="pnl", stake="stake"):
    if len(e) == 0: print(f"{label}: 0 entries"); return
    c = e.groupby(by).agg(p=(pnl, "sum"), s=(stake, "sum")); r, se, t = rc(c.p.values, c.s.values)
    print(f"{label}: n {len(e)} mkts {e.cond.nunique()} clus {len(c)} stake {e[stake].sum():.0f} pnl {e[pnl].sum():+.1f} ret {r:+.3f} t {t:+.2f} win {e.won.mean():.2f} pe {e.pe.mean():.2f}")
tv = E[(E.g == 0.05) & (E.band == "48h-7d")].copy()
R = tv[(tv.period == "report") & tv.conf_w0].copy(); Tn = tv[(tv.period == "tune") & tv.conf_w0].copy()
print("== A. tuned variant, tape-confirmed =="); line(Tn, "tune  analyst window (t,t+600]"); line(R, "report analyst window (t,t+600]")
for nm in ("w300s", "w300"):
    for per in ("tune", "report"):
        line(tv[(tv.period == per) & tv[f"conf_{nm}"]], f"{per} prints only after the entry-price bucket [{nm}]")
print("first qualifying print before t+300 only (confirmed by w0 but not by w300s): report", int((R.conf_w0 & ~R.conf_w300s).sum()), "of", len(R), "pnl", round(R[~R.conf_w300s].pnl.sum(), 1))
# size cap
for per, X in (("tune", Tn), ("report", R)):
    X["frac"] = np.minimum(1.0, X.size_w0 / X.shares); X["pnl_cap"] = X.pnl * X.frac; X["stake_cap"] = 20 * X.frac
    line(X, f"{per} size-capped at tape size", pnl="pnl_cap", stake="stake_cap")
    line(X[X.frac >= 1 - 1e-9], f"{per} full-size only")
    print(f"   median tape size at <= pe: {X.size_w0.median():.1f} shares vs entry {X.shares.median():.1f}; filled stake share {X.stake_cap.sum()/X.stake.sum():.2f}")
# fee 0.07
for per, X in (("tune", Tn), ("report", R)):
    f7 = X.shares * 0.07 * X.pe * (1 - X.pe); print(f"{per}: fee at 0.01 = {X.fee.sum():.2f}; at 0.07 = {f7.sum():.2f}; pnl at 0.07 = {X.pnl.sum() + X.fee.sum() - f7.sum():+.1f}")
# by-hand recomputation of 3 entries
for r in R.head(3).itertuples():
    sh = 20 / r.pe; fee = sh * 0.01 * r.pe * (1 - r.pe); pn = (sh if r.won else 0) - 20 - fee
    print(f"   hand: {r.slug} {r.side} pe {r.pe:.3f} shares {sh:.3f} fee {fee:.4f} won {r.won} pnl {pn:+.3f} (table {r.pnl:+.3f})")
print("\n== B. concentration (report, confirmed, tuned) ==")
c = R.groupby("cluster").pnl.sum().sort_values(ascending=False); dts = R.groupby("date").pnl.sum().sort_values(ascending=False); mk = R.groupby("slug").pnl.sum().sort_values(ascending=False)
print("top clusters:", c.head(3).round(1).to_dict(), "| top dates:", dts.head(3).round(1).to_dict())
line(R[R.cluster != c.index[0]], "drop best cluster"); line(R[R.date != dts.index[0]], "drop best resolution date")
line(R[~R.slug.isin(mk.index[:10])], "drop best 10 markets"); line(R[~R.slug.isin(mk.index[:10]) & (R.date != dts.index[0])], "drop best date and best 10 markets (of the rest)")
print("top-10 markets pnl", round(mk.head(10).sum(), 1), "; losing entries", int((~R.won).sum()), "pnl of losers", round(R[~R.won].pnl.sum(), 1))
R["entry_day"] = pd.to_datetime(R.t, unit="s").dt.strftime("%Y-%m-%d"); R["week"] = pd.to_datetime(R.date).dt.isocalendar().week.astype(int)
line(R, "cluster = resolution date (BTC+ETH together)", by="date"); line(R, "cluster = entry calendar day", by="entry_day"); line(R, "cluster = resolution ISO week", by="week")
print("entry-day pnl:", R.groupby("entry_day").agg(n=("pnl", "size"), pnl=("pnl", "sum")).round(1).to_dict("index"))
cut = 1794762000  # 2026-11-15 17:00 UTC = last tune resolution
print("report entries signalled before the last tune market resolved (15 Nov 17:00 UTC):", int((R.t < cut).sum()), "pnl", round(R[R.t < cut].pnl.sum(), 1), "| after:", int((R.t >= cut).sum()), "pnl", round(R[R.t >= cut].pnl.sum(), 1))
line(R[R.t >= cut], "report, entries strictly after the tune period ended")
print("by side:", R.groupby("side").agg(n=("pnl", "size"), pnl=("pnl", "sum"), win=("won", "mean"), pe=("pe", "mean")).round(2).to_dict("index"))
print("\n== C. how much is direction? model-expected vs realised, and mark-to-market net of the model ==")
for per, X in (("tune", Tn), ("report", R)):
    pside = np.where(X.side == "YES", X.pf, 1 - X.pf)
    exp = (20 / X.pe) * (pside - X.pe) - X.fee
    print(f"{per}: realised {X.pnl.sum():+.1f}; expected if the model is exactly right {exp.sum():+.1f} (mean edge per share {np.mean(pside - X.pe):+.3f}); expected if the MARKET mid is right {(-(20/X.pe)*0.01 - X.fee).sum():+.1f}")
def mtm(X, hours):
    out = []
    for r in X.itertuples():
        row = {}
        for h in hours:
            k = (r.cond, r.t + 300 + h * 3600)
            if k in P.index:
                q = P.loc[k]; p0 = P.loc[(r.cond, r.t + 300)]
                sgn = 1 if r.side == "YES" else -1
                dm = sgn * (q.pm - p0.pm); df = sgn * (q.pf - p0.pf)
                row[f"mkt{h}"] = dm - 0.01; row[f"net{h}"] = dm - df - 0.01
        out.append(row)
    return pd.DataFrame(out, index=X.index)
allc = E[E.conf_w0].drop_duplicates(["cond", "t", "side"]).copy()
for label, X in (("tuned report (43)", R), ("tuned tune (32)", Tn), ("all distinct confirmed, 48h-7d band", allc[allc.tau_h >= 48]), ("all distinct confirmed, all bands", allc)):
    M = mtm(X, (1, 4, 12, 24)); sh = 20 / X.pe
    s = []
    for h in (1, 4, 12, 24):
        ok = M[f"net{h}"].notna()
        cl = pd.DataFrame({"c": X.cluster[ok], "v": (M[f"net{h}"] * sh)[ok], "raw": (M[f"mkt{h}"] * sh)[ok]}).groupby("c").sum()
        m = cl.v.mean(); se = cl.v.std(ddof=1) / math.sqrt(len(cl)) if len(cl) > 1 else float("nan")
        s.append(f"+{h}h: n {int(ok.sum())} exit-at-mid pnl ${cl.raw.sum():+.0f}, net of model move ${cl.v.sum():+.0f} ({M[f'net{h}'][ok].mean()*100:+.2f} c/share, t {m/se:+.2f})")
    print(label, "|", " ; ".join(s))
print("\n== D. listing of the 43 ==")
R2 = R.sort_values("t")
for r in R2.itertuples():
    print(f"{iso(r.t)} {r.slug.replace('bitcoin-above-','B').replace('ethereum-above-','E').replace('-on-november-',' N').replace('-2026','')} {r.side} tau {r.tau_h:5.1f}h pm {r.pm:.3f} model {r.pf:.3f} gap {r.gap:+.3f} pe {r.pe:.3f} tape sz {r.size_w0:7.1f}/{r.shares:5.1f} vwap {r.vwap_w0:.3f} w300s {int(r.conf_w300s)} won {int(r.won)} pnl {r.pnl:+6.1f}")
R.to_parquet("R43.parquet")
