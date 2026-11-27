"""Stage 2: M1, M2, M3, proxy check, model diagnostic, M4, M5 exactly as fixed in protocol.md.

Usage: python3 analyze.py [--suffix _day1] [series ...]    -> out/<suffix>*.csv and out/tables<suffix>.md
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from common import BIG, EXPECTED_RATE, OUT, REF, SERIES, name
from pmlab import stats

DELAYS = (0, 1, 2, 5)
THRS = (0.01, 0.02, 0.04)
MARGINS = (0.03, 0.05, 0.08)
LAGS = list(range(-5, 31))
CAP, CLIP = 300.0, 50.0
NDAYS = {"tune": 4, "report": 2, "all": 6}
RNG = np.random.default_rng(7)


# ---------------------------------------------------------------- helpers

def md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(fmt(r[c]) for c in cols) + " |")
    return "\n".join(lines)


def fmt(v) -> str:
    if isinstance(v, (float, np.floating)):
        if v != v:
            return "-"
        a = abs(v)
        if a >= 1000:
            return f"{v:,.0f}"
        if a >= 100:
            return f"{v:.1f}"
        return f"{v:.3f}".rstrip("0").rstrip(".") if a < 10 else f"{v:.2f}"
    if isinstance(v, (int, np.integer)):
        return f"{int(v):,}"
    return str(v)


def cluster_cell(df: pd.DataFrame, num: str = "net_usd", den: str = "z") -> dict:
    """Share-weighted ratio with clusters = markets (t0)."""
    if not len(df):
        return {"fills": 0, "markets": 0}
    g = df.groupby("t0")[["usd", "gross_usd", "fee_usd", "net_usd", "z"]].sum()
    r, se, t = stats.ratio_cluster(g[num].tolist(), g[den].tolist())
    r2, se2, t2 = stats.ratio_cluster(g["net_usd"].tolist(), g["usd"].tolist())
    return {"fills": len(df), "markets": len(g), "shares": g["z"].sum(), "usd": g["usd"].sum(),
            "gross_c": 100 * g["gross_usd"].sum() / g["z"].sum(), "fee_c": 100 * g["fee_usd"].sum() / g["z"].sum(),
            "net_c": 100 * r, "se_c": 100 * se, "t": t, "net_pct": 100 * r2, "t_pct": t2, "net_usd": g["net_usd"].sum()}


def load(series, suffix):
    tag = name(series) + suffix
    mk = pd.read_parquet(BIG / f"{tag}_markets.parquet")
    f = pd.read_parquet(BIG / f"{tag}_fills.parquet")
    g = np.load(BIG / f"{tag}_grid.npz")
    dur = int(mk.t1.iloc[0] - mk.t0.iloc[0])
    f["usd"] = f.p * f.z
    f["gross_usd"] = f.gross * f.z
    f["fee_usd"] = f.rate * f.p * (1 - f.p) * f.z
    f["net_usd"] = f.gross_usd - f.fee_usd
    per = mk.set_index("t0").period
    f["period"] = f.t0.map(per)
    rel = (f.m - f.t0) / dur
    f["tb"] = np.select([rel < 0, rel < 0.25, rel < 0.5, rel < 0.75, rel < 1.0], ["pre", "Q1", "Q2", "Q3", "Q4"], "post")
    edges = [0, 0.10, 0.30, 0.50, 0.70, 0.90, 1.0001]
    labels = ["0-0.10", "0.10-0.30", "0.30-0.50", "0.50-0.70", "0.70-0.90", "0.90-1"]
    f["qb"] = pd.cut(f.q, edges, right=False, labels=labels).astype(str)
    return mk, f, g, dur


# ---------------------------------------------------------------- M1

def m1(series, mk, f, dur):
    ok = mk[mk.found & mk.resolved.fillna(False).astype(bool)] if "resolved" in mk else mk[mk.found]
    inw = f[(f.m >= f.t0) & (f.m < f.t0 + dur)]
    per_mkt = f.groupby("t0").usd.sum().reindex(ok.t0, fill_value=0.0)
    day = mk.set_index("t0").day
    per_day = f.groupby(f.t0.map(day)).usd.sum()
    wal = f.groupby("w").usd.sum().sort_values(ascending=False)
    gaps = inw.sort_values(["t0", "t"]).groupby("t0").t.apply(lambda s: np.median(np.diff(s.to_numpy())) if len(s) > 1 else np.nan)
    secs = inw.groupby("t0").t.nunique()
    scale = 1.0
    if series == REF:  # 300 of 1726 windows: per-day figures are extrapolated
        scale = 1726 / len(mk)
    return {
        "series": name(series), "windows": len(mk), "found": int(mk.found.sum()), "resolved": len(ok),
        "mkts_with_trade": int((per_mkt > 0).sum()), "mkts_trade_in_window": int(inw.t0.nunique()),
        "fills": len(f), "taker_usd_total": f.usd.sum() * scale, "usd_per_day_median": per_day.median() * scale,
        "usd_per_day_mean": f.usd.sum() * scale / 6, "usd_per_market_median": per_mkt.median(),
        "in_window_usd_share": inw.usd.sum() / f.usd.sum(), "fills_per_market_in_window": len(inw) / max(len(ok), 1),
        "fill_shares_median": f.z.median(), "fill_usd_median": f.usd.median(), "fills_lt5sh_share": (f.z < 5).mean(),
        "wallets": int(f.w.nunique()), "top5_usd_share": wal.head(5).sum() / wal.sum(),
        "gap_s_median": gaps.median(), "seconds_with_fill_share": secs.sum() / (len(ok) * dur),
        "extrapolated": series == REF,
    }


# ---------------------------------------------------------------- M2

def m2(series, f):
    rows = []
    s = name(series)
    for per in ("all", "tune", "report"):
        d = f if per == "all" else f[f.period == per]
        rows.append({"series": s, "cut": "period", "cell": per, **cluster_cell(d)})
    for tb in ("pre", "Q1", "Q2", "Q3", "Q4", "post"):
        rows.append({"series": s, "cut": "time", "cell": tb, **cluster_cell(f[f.tb == tb])})
    for qb in ["0-0.10", "0.10-0.30", "0.30-0.50", "0.50-0.70", "0.70-0.90", "0.90-1"]:
        rows.append({"series": s, "cut": "price(eq.buy)", "cell": qb, **cluster_cell(f[f.qb == qb])})
    for side, lab in ((True, "BUY"), (False, "SELL")):
        rows.append({"series": s, "cut": "side", "cell": lab, **cluster_cell(f[f.buy == side])})
    return rows


def m2_sanity(series, f):
    mid = f[(f.q >= 0.45) & (f.q <= 0.55)]
    g = mid.assign(w=mid.won_eq * mid.z).groupby("t0")[["w", "z"]].sum()
    r, se, _ = stats.ratio_cluster(g.w.tolist(), g.z.tolist())
    dec = f.assign(b=np.floor(f.q * 10).clip(0, 9) / 10, qz=f.q * f.z, wz=f.won_eq * f.z).groupby("b")[["qz", "wz", "z"]].sum()
    cal = {f"{b:.1f}": (round(x.qz / x.z, 3), round(x.wz / x.z, 3)) for b, x in dec.iterrows()}
    return {"series": name(series), "mid_fills": len(mid), "mid_markets": len(g), "mid_mean_q": float(np.average(mid.q, weights=mid.z)),
            "mid_win": r, "mid_se": se, "calibration(q,win)": json.dumps(cal)}


# ---------------------------------------------------------------- M3

def m3_stats(G, U):
    """Per-market sufficient statistics [n_mkt, n_lag, 6] of (x = dF(s), y = dU(s + L))."""
    n, dur = G.shape
    F = np.full((n, dur + 1), np.nan)
    F[:, 1:] = G                      # F(s) = G(s - 1)
    dF = np.full((n, dur + 1), np.nan)
    dF[:, 1:] = F[:, 1:] - F[:, :-1]
    dU = np.full((n, dur + 1), np.nan)
    dU[:, 1:] = U[:, 1:] - U[:, :-1]
    S = np.zeros((n, len(LAGS), 6))
    for k, L in enumerate(LAGS):
        a, b = max(0, -L), min(dur + 1, dur + 1 - L)
        x, y = dF[:, a:b], dU[:, a + L:b + L]
        ok = np.isfinite(x) & np.isfinite(y)
        x0, y0 = np.where(ok, x, 0.0), np.where(ok, y, 0.0)
        S[:, k] = np.stack([ok.sum(1), x0.sum(1), y0.sum(1), (x0 * y0).sum(1), (x0 * x0).sum(1), (y0 * y0).sum(1)], axis=1)
    return S


def corr_from(S):
    s = S.sum(0)
    n, sx, sy, sxy, sxx, syy = (s[:, i] for i in range(6))
    cov = sxy - sx * sy / n
    return cov / np.sqrt((sxx - sx * sx / n) * (syy - sy * sy / n))


def lag_summary(c):
    lags = np.array(LAGS)
    pos = np.clip(c, 0, None)
    cum = np.cumsum(pos)
    half = int(lags[np.searchsorted(cum, 0.5 * cum[-1])]) if cum[-1] > 0 else None
    return {"peak_lag": int(lags[np.argmax(c)]), "peak_corr": float(c.max()),
            "mean_lag_pos": float((lags * pos).sum() / pos.sum()) if pos.sum() > 0 else float("nan"), "half_lag": half}


def m3(series, mk, g, f, dur):
    T0, G, U = g["t0"], g["G"], g["U"]
    S = m3_stats(G, U)
    per = mk.set_index("t0").period.reindex(T0).to_numpy()
    out, curves = [], {}
    for cut in ("all", "tune", "report"):
        sel = np.ones(len(T0), bool) if cut == "all" else per == cut
        if sel.sum() < 2:
            continue
        c = corr_from(S[sel])
        curves[cut] = c
        row = {"series": name(series), "period": cut, "markets": int(sel.sum()), "pairs_lag0": int(S[sel][:, LAGS.index(0), 0].sum()), **lag_summary(c)}
        idx = np.where(sel)[0]
        peaks = [LAGS[int(np.argmax(corr_from(S[RNG.choice(idx, len(idx))])))] for _ in range(300)]
        row["peak_lo90"], row["peak_hi90"] = int(np.quantile(peaks, 0.05)), int(np.quantile(peaks, 0.95))
        out.append(row)
    # M3b: level fit. Per (market, block second) size-weighted implied Up price u vs F(s - L) = G(s - L - 1).
    up_imp = np.where(f.tok_up, f.p, 1 - f.p)
    d = pd.DataFrame({"t0": f.t0.to_numpy(), "i": (f.t - f.t0).to_numpy(), "uz": up_imp * f.z.to_numpy(), "z": f.z.to_numpy()})
    d = d[(d.i >= 35) & (d.i <= dur - 5)].groupby(["t0", "i"], sort=False)[["uz", "z"]].sum().reset_index()
    d["u"] = d.uz / d.z
    d = d[(d.u >= 0.05) & (d.u <= 0.95)]
    pos = {t: k for k, t in enumerate(T0)}
    row_idx = d.t0.map(pos).to_numpy()
    ii = d.i.to_numpy()
    sq = np.zeros((len(T0), len(LAGS)))
    for k, L in enumerate(LAGS):
        e = d.u.to_numpy() - G[row_idx, ii - L - 1]
        e = np.where(np.isfinite(e), e, 0.0)
        np.add.at(sq[:, k], row_idx, e * e)
    cnt = np.bincount(row_idx, minlength=len(T0)).astype(float)
    rms = np.sqrt(sq.sum(0) / cnt.sum())
    idx = np.where(cnt > 0)[0]
    best = [LAGS[int(np.argmin(sq[b].sum(0)))] for b in (RNG.choice(idx, len(idx)) for _ in range(300))]
    lvl = {"series": name(series), "obs": int(cnt.sum()), "markets": int((cnt > 0).sum()), "best_lag": LAGS[int(np.argmin(rms))],
           "rms_best": float(rms.min()), "rms_lag0": float(rms[LAGS.index(0)]), "rms_lag3": float(rms[LAGS.index(3)]), "rms_lag10": float(rms[LAGS.index(10)]),
           "rms_lag30": float(rms[LAGS.index(30)]), "best_lo90": int(np.quantile(best, 0.05)), "best_hi90": int(np.quantile(best, 0.95))}
    return out, curves, lvl, rms


# ---------------------------------------------------------------- proxy check and model diagnostic

def proxy(series, mk):
    ok = mk[mk.found & mk.resolved.fillna(False).astype(bool)]
    d = ok.dropna(subset=["ptb", "final", "b_twap0", "b_twap1"])
    bp = ((d.b_twap1 - d.final) - (d.b_twap0 - d.ptb)) / d.ptb * 1e4
    wrong = (d.b_twap1 >= d.b_twap0) != d.up_won.astype(bool)
    lo, hi = stats.wilson(int(wrong.sum()), len(d))
    move = (d.final / d.ptb - 1).abs() * 1e4
    q = np.quantile(bp, [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
    off = ((ok.final >= ok.ptb) != ok.up_won.astype(bool)) & ok.final.notna() & ok.ptb.notna()
    return {"series": name(series), "resolved": len(ok), "n": len(d), "missing": len(ok) - len(d), "mean_bp": bp.mean(), "sd_bp": bp.std(), "mean_abs_bp": bp.abs().mean(),
            "p1": q[0], "p5": q[1], "p25": q[2], "p50": q[3], "p75": q[4], "p95": q[5], "p99": q[6],
            "wrong": int(wrong.sum()), "wrong_share": wrong.mean(), "wrong_lo": lo, "wrong_hi": hi,
            "missed_move_bp_median": move[wrong].median() if wrong.any() else float("nan"), "missed_move_bp_max": move[wrong].max() if wrong.any() else float("nan"),
            "official_move_bp_median": move.median(), "share_move_lt_2bp": (move < 2).mean(),
            "official_vs_upwon_mismatch": int(off.sum()), "basis_bp_median": ((d.b_twap0 / d.ptb - 1) * 1e4).median()}


def diag(series, mk, g, dur):
    T0, G, U = g["t0"], g["G"], g["U"]
    uw = mk.set_index("t0").up_won.astype(float).reindex(T0).to_numpy()
    rows, pool = [], []
    for lab, i in (("25%", dur // 4), ("50%", dur // 2), ("75%", 3 * dur // 4), ("t1-30", dur - 30)):
        gg, uu = G[:, i], U[:, min(i + 3, dur)]
        ok = np.isfinite(gg) & np.isfinite(uu)
        rows.append({"series": name(series), "at": lab, "markets": int(ok.sum()), "brier_model": float(np.mean((gg[ok] - uw[ok]) ** 2)),
                     "brier_tape": float(np.mean((uu[ok] - uw[ok]) ** 2)), "corr_model_tape": float(np.corrcoef(gg[ok], uu[ok])[0, 1]),
                     "mean_abs_diff": float(np.mean(np.abs(gg[ok] - uu[ok])))})
        pool.append(pd.DataFrame({"g": gg[np.isfinite(gg)], "w": uw[np.isfinite(gg)]}))
    p = pd.concat(pool)
    edges = [0, 0.03, 0.10, 0.30, 0.50, 0.70, 0.90, 0.97, 1.0001]
    p["b"] = pd.cut(p.g, edges, right=False)
    cal = p.groupby("b", observed=True).agg(n=("g", "size"), mean_model=("g", "mean"), up_freq=("w", "mean")).reset_index()
    cal.insert(0, "series", name(series))
    cal["b"] = cal.b.astype(str)
    return rows, cal


# ---------------------------------------------------------------- M4 / M5

def apply_cap(d: pd.DataFrame) -> pd.DataFrame:
    """d: selected prints in tape order. Adds `take` = shares bought under the 50-share clip and 300-share side cap."""
    sz = np.minimum(d.z.to_numpy(), CLIP)
    d = d.assign(sz=sz)
    cum = d.groupby(["t0", "eq_up"], sort=False).sz.cumsum().to_numpy()
    take = np.clip(CAP - (cum - sz), 0.0, sz)
    d = d.assign(sh=take)
    return d[d.sh > 0]


def rule_rows(series, family, variant, d, extra=None):
    """Per-period result rows for the selected, capped prints d."""
    rows = []
    cost = d.sh * d.q
    fee = d.sh * d.rate * d.q * (1 - d.q)
    gross = d.sh * (d.won_eq - d.q)
    d = d.assign(cost=cost, fee=fee, grossd=gross, net=gross - fee, wz=d.sh * d.won_eq)
    for per in ("tune", "report"):
        x = d[d.period == per]
        row = {"series": name(series), "family": family, "variant": variant, "period": per, "trades": len(x), "markets": int(x.t0.nunique())}
        if extra:
            row.update(extra)
        if len(x):
            g = x.groupby("t0")[["net", "sh", "cost", "grossd", "fee"]].sum()
            r, se, t = stats.ratio_cluster(g.net.tolist(), g["sh"].tolist())
            r2, _, t2 = stats.ratio_cluster(g.net.tolist(), g.cost.tolist())
            row.update(shares=g["sh"].sum(), usd=g.cost.sum(), gross_c=100 * g.grossd.sum() / g["sh"].sum(), fee_c=100 * g.fee.sum() / g["sh"].sum(),
                       net_c=100 * r, se_c=100 * se, t=t, net_pct=100 * r2, t_pct=t2, usd_per_day=g.net.sum() / NDAYS[per],
                       net_usd=g.net.sum(), avg_price=g.cost.sum() / g["sh"].sum())
            pos = x.groupby(["t0", "eq_up"]).won_eq.first()
            k, n = int(pos.sum()), len(pos)
            lo, hi = stats.wilson(k, n)
            row.update(positions=n, win_rate=k / n, win_lo=lo, win_hi=hi, win_rate_shares=x.wz.sum() / x["sh"].sum())
        rows.append(row)
    return rows


def m4(series, f, dur):
    base = f[(f.m >= f.t0 + 5) & (f.m <= f.t0 + dur - 5)]
    rows, skipped = [], {}
    fee = base.rate * base.q * (1 - base.q)
    for D in DELAYS:
        fup = base[f"fup_d{D}"].to_numpy()
        skipped[D] = int(np.isnan(fup).sum())
        fo = np.where(base.eq_up, fup, 1 - fup)
        edge = fo - base.q.to_numpy() - fee.to_numpy()
        for thr in THRS:
            sel = base[np.nan_to_num(edge, nan=-9.0) >= thr]
            rows += rule_rows(series, "M4", f"D{D}_thr{thr:.2f}", apply_cap(sel), {"D": D, "thr": thr})
    return rows, {"series": name(series), "prints_considered": len(base), **{f"no_fair_D{d}": v for d, v in skipped.items()}}


def m5(series, f, dur):
    base = f[(f.m >= f.t0 + dur - 45) & (f.m <= f.t0 + dur - 2)]
    fup = base.fup_d1.to_numpy()           # G(m - 2): data up to m - 1
    fav_up, fav_dn = fup >= 0.97, (1 - fup) >= 0.97
    eq = base.eq_up.to_numpy()
    fo = np.where(eq, fup, 1 - fup)
    in_fav = np.where(eq, fav_up, fav_dn)
    rows = []
    for margin in MARGINS:
        for twobp in (False, True):
            cond = in_fav & (base.q.to_numpy() <= fo - margin)
            if twobp:
                cond &= np.nan_to_num(base.dev_m2.to_numpy(), nan=0.0) >= 0.0002
            rows += rule_rows(series, "M5", f"mrg{margin:.2f}" + ("_2bp" if twobp else ""), apply_cap(base[cond]), {"margin": margin, "twobp": twobp})
    info = {"series": name(series), "prints_last45": len(base), "no_fair": int(np.isnan(fup).sum()), "prints_in_favoured_side": int(in_fav.sum()),
            "favoured_prints_mean_q": float(base.q.to_numpy()[in_fav].mean()) if in_fav.any() else float("nan"),
            "favoured_prints_mean_f": float(fo[in_fav].mean()) if in_fav.any() else float("nan")}
    return rows, info


def select(rules: pd.DataFrame) -> pd.DataFrame:
    """Per series and family: variant with the highest tuning t among those with >= 30 tuning markets."""
    out = []
    for (s, fam), d in rules.groupby(["series", "family"], sort=False):
        tune = d[d.period == "tune"]
        elig = tune[tune.markets >= 30]
        pick = elig.sort_values("t", ascending=False).iloc[0] if len(elig) and elig.t.notna().any() else tune.sort_values("markets", ascending=False).iloc[0]
        rep = d[(d.period == "report") & (d.variant == pick.variant)].iloc[0]
        out.append({"series": s, "family": fam, "selected": pick.variant, "eligible_variants": len(elig),
                    "tune_markets": pick.markets, "tune_trades": pick.trades, "tune_net_c": pick.get("net_c"), "tune_t": pick.get("t"), "tune_usd_day": pick.get("usd_per_day"),
                    "rep_markets": rep.markets, "rep_trades": rep.trades, "rep_net_c": rep.get("net_c"), "rep_se_c": rep.get("se_c"), "rep_t": rep.get("t"),
                    "rep_net_pct": rep.get("net_pct"), "rep_usd_day": rep.get("usd_per_day"), "rep_win": rep.get("win_rate")})
    return pd.DataFrame(out)


# ---------------------------------------------------------------- main

def main():
    args = sys.argv[1:]
    suffix = ""
    if "--suffix" in args:
        i = args.index("--suffix")
        suffix = args[i + 1]
        args = args[:i] + args[i + 2:]
    todo = [s for s in SERIES + [REF] if not args or name(s) in args]
    T = {k: [] for k in ("m1", "m2", "m2s", "m3", "m3b", "proxy", "diag", "cal", "rules", "m4info", "m5info", "meta")}
    curves, rmses = {}, {}
    for s in todo:
        mk, f, g, dur = load(s, suffix)
        meta = {"series": name(s), "fee_rate_meta": json.dumps({str(k): int(v) for k, v in mk.fee_rate_meta.value_counts(dropna=False).items()}),
                "expected_rate": EXPECTED_RATE[s], "twap_lookback": json.dumps({str(k): int(v) for k, v in mk.twap_lookback.value_counts(dropna=False).items()}),
                "g_nan_seconds": int(mk.g_nan.fillna(0).sum()), "up_share": float(mk.up_won.dropna().astype(float).mean()),
                "tune_markets": int((mk.period == "tune").sum()), "report_markets": int((mk.period == "report").sum())}
        T["meta"].append(meta)
        T["m1"].append(m1(s, mk, f, dur))
        T["m2"] += m2(s, f)
        T["m2s"].append(m2_sanity(s, f))
        rows, cv, lvl, rms = m3(s, mk, g, f, dur)
        T["m3"] += rows
        T["m3b"].append(lvl)
        curves[name(s)], rmses[name(s)] = cv, rms
        T["proxy"].append(proxy(s, mk))
        drows, cal = diag(s, mk, g, dur)
        T["diag"] += drows
        T["cal"].append(cal)
        if s != REF:
            r4, i4 = m4(s, f, dur)
            r5, i5 = m5(s, f, dur)
            T["rules"] += r4 + r5
            T["m4info"].append(i4)
            T["m5info"].append(i5)
        print("done", name(s), flush=True)
    D = {k: (pd.concat(v, ignore_index=True) if k == "cal" else pd.DataFrame(v)) for k, v in T.items() if len(v)}
    for k, d in D.items():
        d.to_csv(OUT / f"{k}{suffix}.csv", index=False)
    cur = pd.DataFrame({"lag": LAGS, **{f"{s}": c["all"] for s, c in curves.items()}})
    cur.to_csv(OUT / f"m3_curves{suffix}.csv", index=False)
    cur_tr = pd.DataFrame({"lag": LAGS, **{f"{s}_{p}": c[p] for s, c in curves.items() for p in ("tune", "report") if p in c}})
    cur_tr.to_csv(OUT / f"m3_curves_periods{suffix}.csv", index=False)
    rm = pd.DataFrame({"lag": LAGS, **rmses})
    rm.to_csv(OUT / f"m3b_rms{suffix}.csv", index=False)
    parts = []

    def add(title, df):
        parts.append(f"### {title}\n\n{md_table(df)}\n")

    add("meta", D["meta"])
    add("M1", D["m1"])
    m2c = ["series", "cut", "cell", "fills", "markets", "shares", "usd", "gross_c", "fee_c", "net_c", "se_c", "t", "net_pct", "net_usd"]
    add("M2", D["m2"][m2c])
    add("M2 sanity", D["m2s"])
    add("M3 lag summary", D["m3"])
    add("M3 correlation by lag (all days)", cur)
    add("M3 correlation by lag (tune / report)", cur_tr)
    add("M3b level fit", D["m3b"])
    add("M3b RMS by lag", rm)
    add("Proxy check", D["proxy"])
    add("Model diagnostic", D["diag"])
    add("Model calibration (pooled over 25/50/75% and t1-30)", D["cal"])
    if "rules" in D:
        r = D["rules"]
        cols = ["series", "variant", "period", "trades", "markets", "shares", "usd", "avg_price", "gross_c", "fee_c", "net_c", "se_c", "t", "net_pct", "usd_per_day"]
        add("M4 all variants", r[r.family == "M4"][cols])
        add("M4 info", D["m4info"])
        cols5 = ["series", "variant", "period", "trades", "markets", "positions", "win_rate", "win_lo", "win_hi", "win_rate_shares", "shares", "usd", "avg_price", "net_c", "se_c", "t", "net_pct", "usd_per_day"]
        add("M5 all variants", r[r.family == "M5"].reindex(columns=cols5))
        add("M5 info", D["m5info"])
        sel = select(r)
        sel.to_csv(OUT / f"selected{suffix}.csv", index=False)
        add("Selected variants (tuned on 21-24 Nov, reported on 25-26 Nov)", sel)
    (OUT / f"tables{suffix}.md").write_text("\n".join(parts))
    print("wrote", OUT / f"tables{suffix}.md")


if __name__ == "__main__":
    main()
