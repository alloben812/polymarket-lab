import json, gzip, math, time
import numpy as np, pandas as pd
from pathlib import Path
D = Path("/home/user/polymarket-lab/data/gaps_levels")
E = pd.read_parquet("my_entries.parquet"); E["stake"] = 20.0
Pn = pd.read_parquet("my_panel.parquet")
P = Pn.set_index(["cond", "t"]).sort_index()
uni = {u["cond"]: u for u in json.load(open(D / "universe.json")) if u["grp"] == "euro"}
def rc(num, den):
    n = len(num); ds = den.sum(); r = num.sum() / ds
    if n < 2: return r, float("nan"), float("nan")
    res = num - r * den; se = math.sqrt(n / (n - 1) * (res ** 2).sum()) / ds
    return r, se, r / se
def line(e, label, by="cluster", pnl="pnl", stake="stake"):
    if len(e) == 0: print(f"{label}: 0 entries"); return
    c = e.groupby(by).agg(p=(pnl, "sum"), s=(stake, "sum")); r, se, t = rc(c.p.values, c.s.values)
    print(f"{label}: n {len(e)} mkts {e.cond.nunique()} clus {len(c)} stake {e[stake].sum():.0f} pnl {e[pnl].sum():+.1f} ret {r:+.3f} t {t:+.2f} win {e.won.mean():.2f} pe {e.pe.mean():.2f}")
# 1. is the gap still there at the entry bucket?
nx = P.reindex(list(zip(E.cond, E.t + 300)))
E["pf_next"] = nx.pf.values; E["gap_next"] = E.p1 - E.pf_next
E["still"] = (np.sign(E.gap_next) == np.sign(E.gap)) & (E.gap_next.abs() >= E.g)
E["edge_at_entry"] = np.where(E.side == "YES", E.pf_next, 1 - E.pf_next) - E.pe
tv = E[(E.g == 0.05) & (E.band == "48h-7d")]
print("== 1. gap at the entry bucket (tuned variant) ==")
for per in ("tune", "report"):
    for lab, X in (("paper", tv[tv.period == per]), ("confirmed", tv[(tv.period == per) & tv.conf_w0])):
        print(f"{per} {lab}: n {len(X)}; gap still >= 0.05 same sign at t+300: {X.still.mean():.2f}; model edge at the entry price <= 0: {(X.edge_at_entry <= 0).mean():.2f}; median edge {X.edge_at_entry.median():+.3f}")
    X = tv[(tv.period == per) & tv.conf_w0]
    line(X[X.still], f"  {per} confirmed, gap still there at entry"); line(X[~X.still], f"  {per} confirmed, gap gone at entry")
# 2. strict combinations for the report period
R = tv[(tv.period == "report")].copy(); cut = 1794762000
for nm in ("w0", "w300", "w300s"):
    X = R[R[f"conf_{nm}"]].copy(); X["frac"] = np.minimum(1.0, X[f"size_{nm}"] / X.shares); X["pc"] = X.pnl * X.frac; X["sc"] = 20 * X.frac
    line(X, f"report {nm} size-capped", pnl="pc", stake="sc"); Y = X[X.t >= cut]
    line(Y, f"report {nm}, entries after tune period ended"); line(Y, f"report {nm}, after tune period, size-capped", pnl="pc", stake="sc")
# 3. all nine variants, report, under the stricter fill evidence (prints after the entry-price bucket, size-capped)
print("\n== 3. nine variants, report period: (a) analyst confirmed, (b) w300 prints after entry-price bucket, (c) w300 size-capped ==")
for g in (0.05, 0.08, 0.12):
    for bn in ("2-12h", "12-48h", "48h-7d"):
        for per in ("tune", "report"):
            X = E[(E.period == per) & (E.g == g) & (E.band == bn)].copy()
            a = X[X.conf_w0]; b = X[X.conf_w300].copy(); b["frac"] = np.minimum(1.0, b.size_w300 / b.shares); b["pc"] = b.pnl * b.frac; b["sc"] = 20 * b.frac
            def tt(Z, pnl="pnl", st="stake"):
                if len(Z) < 2: return float("nan")
                c = Z.groupby("cluster").agg(p=(pnl, "sum"), s=(st, "sum")); return rc(c.p.values, c.s.values)[2]
            print(f"{per} g {g} {bn}: (a) n {len(a)} pnl {a.pnl.sum():+.0f} t {tt(a):+.2f} | (b) n {len(b)} pnl {b.pnl.sum():+.0f} t {tt(b):+.2f} | (c) stake {b.sc.sum():.0f} pnl {b.pc.sum():+.0f} t {tt(b,'pc','sc'):+.2f}")
# 4. liquidity used twice in the pooled 'all distinct confirmed' set
d = E[E.conf_w0].drop_duplicates(["cond", "t", "side"]).sort_values(["cond", "side", "t"])
dt = d.groupby(["cond", "side"]).t.diff()
print("\npooled distinct confirmed entries:", len(d), "; with another confirmed entry of the same market+side within 600 s (same prints):", int((dt <= 600).sum()), "; within 12 h:", int((dt < 12 * 3600).sum()))
# 5. placebo: blind side, same band, same tape rule, no gap condition
print("\n== 5. placebo: buy one side blindly in the 48h-7d band whenever the tape confirms (no gap condition), one per market per 12 h ==")
rows = []
for c, g in Pn.groupby("cond"):
    u = uni[c]; p = D / "tape" / f"{c}.json.gz"
    if u["freq"] != "daily" or not p.exists(): continue
    tp = json.load(gzip.open(p, "rt"))
    if not tp: continue
    mt = np.array([x[0] - 3 for x in tp]); 
    bpY = np.array([x[4] if (x[1] == "BUY" and x[2] == "Yes") else (1 - x[4] if (x[1] == "SELL" and x[2] == "No") else np.inf) for x in tp])
    bpN = np.array([x[4] if (x[1] == "BUY" and x[2] == "No") else (1 - x[4] if (x[1] == "SELL" and x[2] == "Yes") else np.inf) for x in tp])
    g = g.sort_values("t"); tt_ = g.t.values; pm = g.pm.values; pf = g.pf.values; tau = g.tau.values / 3600
    nxt = dict(zip(tt_.tolist(), zip(pm.tolist(), pf.tolist())))
    for side, bp in (("YES", bpY), ("NO", bpN)):
        last = -10**12
        for t, h in zip(tt_, tau):
            if h < 48 or h > 168 or t - last < 12 * 3600: continue
            q = nxt.get(int(t) + 300)
            if q is None: continue
            pe = (q[0] if side == "YES" else 1 - q[0]) + 0.01
            if pe < 0.01 or pe > 0.99: continue
            i, j = np.searchsorted(mt, t, side="right"), np.searchsorted(mt, t + 600, side="right")
            if j <= i or bp[i:j].min() > pe + 1e-9: continue
            last = t; sh = 20 / pe; won = (u["yes_won"] == (side == "YES")); fee = sh * 0.01 * pe * (1 - pe)
            pside = q[1] if side == "YES" else 1 - q[1]
            rows.append((c, u["asset"] + "_" + u["date"], "tune" if u["date"] <= "2026-11-15" else "report", side, int(t), pe, won, (sh if won else 0) - 20 - fee, 20.0, pside - pe))
B = pd.DataFrame(rows, columns=["cond", "cluster", "period", "side", "t", "pe", "won", "pnl", "stake", "edge"])
B.to_parquet("placebo.parquet")
for per in ("tune", "report"):
    for side in ("NO", "YES"):
        for lo, hi in ((0.01, 0.99), (0.10, 0.90), (0.10, 0.50), (0.50, 0.90)):
            line(B[(B.period == per) & (B.side == side) & (B.pe >= lo) & (B.pe <= hi)], f"blind {side} {per} pe {lo}-{hi}")
print("signal entries for comparison (tuned, confirmed):")
for per in ("tune", "report"):
    for side in ("NO", "YES"):
        X = tv[(tv.period == per) & tv.conf_w0 & (tv.side == side)]
        for lo, hi in ((0.01, 0.99), (0.10, 0.90), (0.10, 0.50), (0.50, 0.90)):
            line(X[(X.pe >= lo) & (X.pe <= hi)], f"signal {side} {per} pe {lo}-{hi}")
