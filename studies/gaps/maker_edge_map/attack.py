"""Attacks on the cells that passed the protocol rule (post-hoc, labelled as such in results.md).
A. Out of sample: markets 26-100 of the same sha1 order (never seen by the protocol run), same frozen V2 rule.
B. Loss rate by market vs the break-even loss rate.  C. Capital lock-up and return per day.  D. Concentration.
E. Extension map: all families, V1/V2/V2o, K <= 100 per half."""
import json
import numpy as np, pandas as pd
from pmlab.stats import ratio_cluster, wilson

D = "/home/user/polymarket-lab/data/gaps_maker_edge"; O = "/home/user/polymarket-lab/studies/gaps/maker_edge_map/out"
F25 = pd.read_parquet(f"{D}/fills.parquet"); FX = pd.read_parquet(f"{D}/fills_ext.parquet")
seen = set(F25.cid.unique()) | {r["conditionId"] for r in json.load(open(f"{D}/sample_K25.json"))}
NEW = FX[~FX.cid.isin(seen)]
SX = json.load(open(f"{D}/sample_ext.json"))
nmk = pd.Series([(r["family"], r["half"]) for r in SX if r["conditionId"] not in seen]).value_counts().to_dict()
U = json.load(open(f"{D}/universe_counts.json"))["resolved"]
PASS = [("crypto-other", ">=.95"), ("culture", ">=.95"), ("post-counts", ">=.95")]
out = []


def stat(g, m="fin"):
    ok = g[np.isfinite(g[m])]
    if ok.empty: return (np.nan, np.nan, 0)
    by = ok.assign(num=ok[m] * ok.sh, den=ok.sh).groupby("cid")[["num", "den"]].sum()
    r, se, t = ratio_cluster(list(by.num), list(by.den))
    return 100 * r, 100 * se, len(by)


def cellrow(g, label):
    f, fse, n = stat(g); a, ase, _ = stat(g, "m30"); b, bse, _ = stat(g, "m300")
    lose = g[g.fin < -0.5].cid.nunique()
    lo, hi = wilson(lose, n) if n else (np.nan, np.nan)
    qb = (g.q * g.sh).sum() / g.sh.sum() if len(g) else np.nan
    by = g.assign(num=g.fin * g.sh).groupby("cid").num.sum()
    best = by.max() if len(by) else np.nan
    wo = (by.sum() - best) / (g.sh.sum() - g[g.cid == by.idxmax()].sh.sum()) * 100 if len(by) > 1 else np.nan
    ttr = g.ttr.median() / 3600 if len(g) else np.nan
    return (f"| {label} | {n} | {len(g)} | {qb:.3f} | {f:+.2f} ± {1.96*fse:.2f} | {a:+.2f} ± {1.96*ase:.2f} | {b:+.2f} ± {1.96*bse:.2f} | "
            f"{lose} ({100*lo:.1f}-{100*hi:.1f}%) | {100*(1-qb):.1f}% | {ttr:.1f} | {wo:+.2f} |")


HDR = ("| cell | mkts | fills | avg price | fin c/sh ±95% | m30 | m300 | markets with a losing fill (Wilson 95%) | "
       "break-even loss rate ~ 1-price | median hours to resolution | fin without best market |\n|---|---|---|---|---|---|---|---|---|---|---|")
out.append("## A. Passing cells on NEW markets (markets 26-100 of the sha1 order per half), V2 conservative\n\n" + HDR)
for fam, pb in PASS:
    for h in ("early", "late", "both"):
        g = NEW[(NEW["var"] == "V2") & (NEW.family == fam) & (NEW.pb == pb) & ((NEW.half == h) if h != "both" else True)]
        out.append(cellrow(g, f"{fam} {pb} {h}"))
for fam, pb in PASS:
    g = NEW[(NEW["var"] == "V2o") & (NEW.family == fam) & (NEW.pb == pb)]
    out.append(cellrow(g, f"{fam} {pb} both, V2o optimistic"))
g = NEW[(NEW["var"] == "V2") & (NEW.pb == ">=.95")]
out.append(cellrow(g, "ALL families >=.95 both (V2)"))
out.append("\n## B. >=.95 maker fills by family, all markets of the extension (K <= 100 per half; includes the protocol sample)\n\n" + HDR)
for v in ("V2", "V1"):
    for fam in sorted(FX.family.unique()):
        g = FX[(FX["var"] == v) & (FX.family == fam) & (FX.pb == ">=.95")]
        if len(g): out.append(cellrow(g, f"{v} {fam}"))
# losing markets listed for the passing families
L = FX[(FX["var"].isin(["V1", "V2"])) & (FX.pb == ">=.95") & (FX.fin < -0.5) & FX.family.isin([p[0] for p in PASS])]
meta = {r["conditionId"]: r for r in SX}
out.append("\n## Losing >=.95 maker fills in the passing families (extension)\n")
for cid, g in L.groupby("cid"):
    r = meta[cid]
    out.append(f"- {r['family']} {r['half']} `{r['slug']}`: {g['var'].value_counts().to_dict()} fills, {g.sh.sum():.0f} shares at avg {g.q.mean():.3f}, payout {r['payout']}")
# E. Extension map
rows = []
for v in ("V1", "V2", "V2o"):
    for (fam, h), g in FX[FX["var"] == v].groupby(["family", "half"]):
        f, fse, n = stat(g); a, ase, _ = stat(g, "m30"); b, bse, _ = stat(g, "m300")
        usd = (g.q * g.sh).sum(); finusd = (g.fin * g.sh).sum() / usd * 100
        ns = sum(1 for r in SX if r["family"] == fam and r["half"] == h)
        fd = len(g) / ns * U[f"{fam}|{h}"] / (4 if h == "early" else 3)
        rows.append(dict(var=v, family=fam, half=h, mkts=n, fills=len(g), fin=f, fin_ci=1.96 * fse, fin_pct_usd=finusd,
                         m30=a, m30_ci=1.96 * ase, m300=b, m300_ci=1.96 * bse, fills_per_day_family=fd))
E = pd.DataFrame(rows); E.to_csv(f"{O}/extension_map.csv", index=False)
out.append("\n## E. Extension map (K <= 100 markets per family and half), c/share, ±95% CI clustered by market\n")
out.append("| var | family | half | mkts | fills | fin | fin %$ | m30 | m300 | fills/day (family) |\n|---|---|---|---|---|---|---|---|---|---|")
for _, r in E.sort_values(["var", "family", "half"]).iterrows():
    out.append(f"| {r['var']} | {r.family} | {r.half} | {r.mkts} | {r.fills} | {r.fin:+.2f} ± {r.fin_ci:.2f} | {r.fin_pct_usd:+.1f} | "
               f"{r.m30:+.2f} ± {r.m30_ci:.2f} | {r.m300:+.2f} ± {r.m300_ci:.2f} | {r.fills_per_day_family:.0f} |")
open(f"{O}/attack.md", "w").write("\n".join(out))
print("\n".join(out))
