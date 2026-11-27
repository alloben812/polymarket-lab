"""Descriptive re-aggregations of what analyze.py already ran (no new rule variants):
  - M3 peak lag and M3b best lag per UTC day (is the block delay stable?)
  - the selected M4/M5 variants per day and pooled over all six days
"""
import numpy as np
import pandas as pd

from analyze import LAGS, apply_cap, corr_from, load, m3_stats, md_table
from common import OUT, REF, SERIES, name
from pmlab import stats

sel = pd.read_csv(OUT / "selected.csv")
parts, lagrows, dayrows, poolrows = [], [], [], []
for s in SERIES + [REF]:
    mk, f, g, dur = load(s, "")
    T0, G, U = g["t0"], g["G"], g["U"]
    S = m3_stats(G, U)
    day = mk.set_index("t0").day.reindex(T0).to_numpy()
    row = {"series": name(s)}
    for d in sorted(set(day)):
        c = corr_from(S[day == d])
        row[d[5:]] = f"{LAGS[int(np.argmax(c))]} ({c.max():.2f})"
    lagrows.append(row)
    if s == REF:
        continue
    fday = f.t0.map(mk.set_index("t0").day)
    for _, x in sel[sel.series == name(s)].iterrows():
        v = x.selected
        if x.family == "M4":
            D, thr = int(v[1]), float(v.split("thr")[1])
            base = f[(f.m >= f.t0 + 5) & (f.m <= f.t0 + dur - 5)]
            fup = base[f"fup_d{D}"].to_numpy()
            fo = np.where(base.eq_up, fup, 1 - fup)
            edge = fo - base.q.to_numpy() - (base.rate * base.q * (1 - base.q)).to_numpy()
            d = apply_cap(base[np.nan_to_num(edge, nan=-9.0) >= thr])
        else:
            margin, twobp = float(v[3:7]), v.endswith("_2bp")
            base = f[(f.m >= f.t0 + dur - 45) & (f.m <= f.t0 + dur - 2)]
            fup = base.fup_d1.to_numpy()
            eq = base.eq_up.to_numpy()
            fo = np.where(eq, fup, 1 - fup)
            cond = np.where(eq, fup >= 0.97, (1 - fup) >= 0.97) & (base.q.to_numpy() <= fo - margin)
            if twobp:
                cond &= np.nan_to_num(base.dev_m2.to_numpy(), nan=0.0) >= 0.0002
            d = apply_cap(base[cond])
        d = d.assign(net=d.sh * (d.won_eq - d.q) - d.sh * d.rate * d.q * (1 - d.q), day=d.t0.map(mk.set_index("t0").day))
        g2 = d.groupby("t0")[["net", "sh"]].sum()
        r, se, t = stats.ratio_cluster(g2.net.tolist(), g2.sh.tolist())
        perday = d.groupby("day").net.sum()
        m, sed, td = stats.mean_se(perday.tolist())
        poolrows.append({"series": name(s), "family": x.family, "variant": v, "markets": len(g2), "trades": len(d), "shares": g2.sh.sum(),
                         "net_c": 100 * r, "se_c": 100 * se, "t_mkt": t, "usd_per_day": d.net.sum() / 6, "days_positive": int((perday > 0).sum()),
                         "days": len(perday), "t_by_day": td})
        dr = {"series": name(s), "family": x.family, "variant": v}
        for dd, val in perday.items():
            dr[dd[5:]] = float(val)
        dayrows.append(dr)
L, Dy, P = pd.DataFrame(lagrows), pd.DataFrame(dayrows), pd.DataFrame(poolrows)
L.to_csv(OUT / "extra_m3_by_day.csv", index=False)
Dy.to_csv(OUT / "extra_selected_by_day.csv", index=False)
P.to_csv(OUT / "extra_selected_pooled.csv", index=False)
txt = "### M3 peak lag by UTC day: lag in seconds (peak correlation)\n\n" + md_table(L) + "\n\n### Selected variants, net dollars per day\n\n" + md_table(Dy) + \
      "\n\n### Selected variants pooled over all six days\n\n" + md_table(P) + "\n"
(OUT / "tables_extra.md").write_text(txt)
print(txt)
