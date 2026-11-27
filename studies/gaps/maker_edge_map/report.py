"""Tables and the decision rule of protocol.md from data/gaps_maker_edge/fills.parquet."""
import json, math, sys
import numpy as np, pandas as pd
from pmlab.stats import ratio_cluster

D = "/home/user/polymarket-lab/data/gaps_maker_edge"; O = "/home/user/polymarket-lab/studies/gaps/maker_edge_map/out"
F = pd.read_parquet(f"{D}/fills.parquet")
U = json.load(open(f"{D}/universe_counts.json"))["resolved"]
DAYS = {"early": 4, "late": 3}
FAMS = ["btc-5m", "btc-15m", "alt-updown-5m15m", "crypto-updown-long", "crypto-other", "mentions", "post-counts",
        "sports", "weather", "economics", "finance", "politics", "tech", "culture"]
SAMPLE = json.load(open(f"{D}/sample.json"))
NSAMP = pd.Series([(r["family"], r["half"]) for r in SAMPLE]).value_counts().to_dict()


def cell(g):
    """per-share and per-dollar markouts with market-clustered SE."""
    out = {"fills": len(g), "mkts": g.cid.nunique(), "shares": g.sh.sum(), "usd": (g.q * g.sh).sum()}
    for m in ("fin", "m30", "m300"):
        ok = g[np.isfinite(g[m])]
        if ok.empty:
            out[m] = out[m + "_se"] = out[m + "_usd"] = np.nan; out[m + "_cov"] = 0.0; continue
        by = ok.assign(num=ok[m] * ok.sh, den=ok.sh, dol=ok.q * ok.sh).groupby("cid")[["num", "den", "dol"]].sum()
        r, se, t = ratio_cluster(list(by.num), list(by.den))
        out[m] = 100 * r; out[m + "_se"] = 100 * se
        out[m + "_usd"] = 100 * by.num.sum() / by.dol.sum()   # percent of dollars
        out[m + "_cov"] = len(ok) / len(g)
    return pd.Series(out)


def table(df, keys):
    return df.groupby(keys, observed=True).apply(cell, include_groups=False).reset_index()


def fmt(T, keys):
    lines = []
    hdr = keys + ["mkts", "fills", "fin c/sh (±1.96se)", "fin %$", "m30 c/sh", "m300 c/sh"]
    lines.append("| " + " | ".join(hdr) + " |"); lines.append("|" + "---|" * len(hdr))
    for _, r in T.iterrows():
        def ci(m):
            if not np.isfinite(r[m]): return "n/a"
            return f"{r[m]:+.2f} ({r[m]-1.96*r[m+'_se']:+.2f}..{r[m]+1.96*r[m+'_se']:+.2f})" if np.isfinite(r[m + '_se']) else f"{r[m]:+.2f}"
        lines.append("| " + " | ".join([str(r[k]) for k in keys] + [str(int(r.mkts)), str(int(r.fills)), ci("fin"),
                     f"{r.fin_usd:+.2f}" if np.isfinite(r.fin_usd) else "n/a", ci("m30"), ci("m300")]) + " |")
    return "\n".join(lines)


rep = []
for var in ("V1", "V2", "V2o"):
    T = table(F[F["var"] == var], ["family", "half"])
    T["family"] = pd.Categorical(T.family, FAMS); T = T.sort_values(["family", "half"])
    T.to_csv(f"{O}/{var}_family.csv", index=False)
    rep.append(f"\n## {var} by family and half\n\n" + fmt(T, ["family", "half"]))
# price bucket and time-to-resolution, V2, both halves pooled and split
for dim in ("pb", "tb"):
    T = table(F[F["var"] == "V2"], ["family", "half", dim]); T.to_csv(f"{O}/V2_{dim}.csv", index=False)
    T1 = table(F[F["var"] == "V1"], ["family", dim]); T1.to_csv(f"{O}/V1_{dim}.csv", index=False)
    rep.append(f"\n## V1 by family x {dim} (both halves)\n\n" + fmt(T1, ["family", dim]))
# weekend cut (descriptive), V1 and V2, early half only has weekend days (Nov 21-22)
T = table(F[F["var"].isin(["V1", "V2"])], ["var", "family", "wkend"]); T.to_csv(f"{O}/wkend.csv", index=False)
rep.append("\n## Weekend (Sat/Sun UTC) vs weekday, V1 and V2, both halves\n\n" + fmt(T, ["var", "family", "wkend"]))

# family labels per protocol
lab = []
V2F = pd.read_csv(f"{O}/V2_family.csv")
for _, r in V2F.iterrows():
    lo = lambda m: r[m] - 1.96 * r[m + "_se"]; hi = lambda m: r[m] + 1.96 * r[m + "_se"]
    if lo("fin") > 0 and lo("m300") > 0: L = "paid"
    elif (hi("m30") < 0 or hi("m300") < 0) and not lo("fin") > 0: L = "picked off"
    else: L = "unclear"
    lab.append((r.family, r.half, L))
rep.append("\n## Family labels (V2 rule)\n\n" + "\n".join(f"- {a} {b}: {c}" for a, b, c in lab))

# candidate cells: early V2 family x pb with fin > 0, t >= 2, >= 8 markets
V2pb = pd.read_csv(f"{O}/V2_pb.csv")
E = V2pb[V2pb.half == "early"]
cand = E[(E.fin > 0) & (E.fin / E.fin_se >= 2) & (E.mkts >= 8)]
rep.append("\n## Candidate cells chosen on EARLY (V2, family x price bucket)\n\n" + (fmt(cand, ["family", "pb"]) if len(cand) else "none"))
Lt = V2pb[V2pb.half == "late"].set_index(["family", "pb"])
res = []
for _, c in cand.iterrows():
    k = (c.family, c.pb)
    if k not in Lt.index:
        res.append(f"- {k}: no late fills -> FAIL"); continue
    l = Lt.loc[k]
    fills_per_mkt = l.fills / NSAMP.get((c.family, "late"), np.nan)
    fills_day = fills_per_mkt * U[f"{c.family}|late"] / DAYS["late"]
    usd_day = fills_day * 10.0 * l.fin_usd / 100
    ok = (l.fin > 0) and (l.fin / l.fin_se >= 2) and (l.mkts >= 8) and (usd_day >= 1)
    res.append(f"- {k}: late fin {l.fin:+.2f} c/sh (se {l.fin_se:.2f}, t {l.fin/l.fin_se:+.2f}), {int(l.mkts)} mkts, {int(l.fills)} fills, "
               f"{l.fin_usd:+.2f}% of $, fills/day in family ~{fills_day:.0f}, $/day at $10 clips {usd_day:+.1f} -> {'PASS' if ok else 'FAIL'}")
rep.append("\n## Late check of candidates\n\n" + ("\n".join(res) if res else "no candidates"))

# opportunities per day and $ per day at $10 clips, V2, per family, late
rows = []
V2L = V2F[V2F.half == "late"]
for _, r in V2L.iterrows():
    n = NSAMP.get((r.family, "late"), np.nan)
    fd = r.fills / n * U[f"{r.family}|late"] / 3
    rows.append(f"| {r.family} | {U[f'{r.family}|late']} | {r.fills/n:.1f} | {fd:.0f} | {r.fin_usd:+.2f} | {fd*10*r.fin_usd/100:+.1f} |")
rep.append("\n## V2 late: fills per market, fills per day in the family (scaled to all resolved markets with volume >= $1K), "
           "$ per day at $10 clips if every fill were taken\n\n| family | markets in universe (late, 3 days) | fills/market | fills/day | fin % of $ | $/day |\n|---|---|---|---|---|---|\n" + "\n".join(rows))
open(f"{O}/report.md", "w").write("\n".join(rep))
print("\n".join(rep))
