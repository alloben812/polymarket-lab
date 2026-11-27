"""L3 rule simulation. Usage: l3.py euro pa|pb   or   l3.py ot pa.  Writes entries_<grp>_<pcol>.parquet"""
import sys, math
import numpy as np, pandas as pd
from common import *
from pmlab.stats import ratio_cluster, mean_se
from pmlab.fees import fee_per_share
GS = (0.05, 0.08, 0.12); BANDS = (("2-12h", 2 * 3600, 12 * 3600), ("12-48h", 12 * 3600, 48 * 3600), ("48h-7d", 48 * 3600, 168 * 3600 + 1))
STAKE, RATE, LOCK = 20.0, 0.01, 12 * 3600

def simulate(grp, pcol):
    P = pd.read_parquet(DATA / f"panel_{grp}.parquet").dropna(subset=["S", pcol]); meta = pd.read_parquet(DATA / f"meta_{grp}.parquet").set_index("m")
    rows = []
    for m, d in P.groupby("m"):
        d = d.sort_values("t")
        t = d.t.values; pm = d.pm.values; pf = d[pcol].values; tau = d.tau.values
        gap = pm - pf
        nxt = {int(a): b for a, b in zip(t, pm)}
        u = meta.loc[m]
        for g in GS:
            for bn, lo, hi in BANDS:
                idx = np.where((np.abs(gap) >= g) & (tau >= lo) & (tau < hi))[0]
                last = -10**12
                for i in idx:
                    ti = int(t[i])
                    if ti - last < LOCK: continue
                    p1 = nxt.get(ti + 300)
                    if p1 is None: continue
                    yes = gap[i] < 0
                    pe = (p1 if yes else 1 - p1) + 0.01
                    if not (0.01 <= pe <= 0.99): continue
                    last = ti
                    sh = STAKE / pe
                    win = (u.yes_won == yes)
                    fee = sh * fee_per_share(pe, RATE)
                    rows.append((m, g, bn, ti, "YES" if yes else "NO", gap[i], pf[i], pm[i], p1, pe, sh, fee, bool(win), sh * ((1.0 if win else 0.0) - pe) - fee, tau[i] / 3600))
    E = pd.DataFrame(rows, columns=["m", "g", "band", "t", "side", "gap", "model", "pm", "pm_next", "pe", "shares", "fee", "win", "pnl", "tau_h"])
    E = E.merge(meta[["cond", "slug", "cluster", "period", "asset", "date", "yes", "no", "freq"]], left_on="m", right_index=True)
    E.to_parquet(DATA / f"entries_{grp}_{pcol}.parquet")
    return E

def table(E, title, days={"tune": 20, "report": 11}):
    print(f"\n### {title}")
    print("period | g | band | entries | markets | clusters | stake $ | PnL $ | return on stake | se | t | win rate | mean entry px | mean |gap| | YES share | $/day | t of per-cluster mean PnL")
    out = {}
    for per in ("tune", "report"):
        for g in GS:
            for bn, _, _ in BANDS:
                e = E[(E.period == per) & (E.g == g) & (E.band == bn)]
                if len(e) == 0:
                    print(f"{per} | {g} | {bn} | 0 | 0 | 0 | 0 | 0 | - | - | - | - | - | - | - | 0 | -"); out[(per, g, bn)] = (0, float("nan"), 0, 0.0); continue
                c = e.groupby("cluster").agg(pnl=("pnl", "sum"), n=("pnl", "size"))
                r, se, t = ratio_cluster(list(c.pnl), list(c.n * STAKE))
                _, _, t2 = mean_se(list(c.pnl))
                out[(per, g, bn)] = (len(e), t, e.m.nunique(), e.pnl.sum())
                print(f"{per} | {g} | {bn} | {len(e)} | {e.m.nunique()} | {len(c)} | {len(e)*STAKE:.0f} | {e.pnl.sum():+.1f} | {r:+.4f} | {se:.4f} | {t:+.2f} | {e.win.mean():.3f} | {e.pe.mean():.3f} | {e.gap.abs().mean():.3f} | {(e.side=='YES').mean():.2f} | {e.pnl.sum()/days[per]:+.2f} | {t2:+.2f}")
    cand = {k: v for k, v in out.items() if k[0] == "tune" and v[0] >= 30 and v[1] == v[1]}
    if cand:
        best = max(cand, key=lambda k: cand[k][1])
        rep = out[("report", best[1], best[2])]
        print(f"tuned variant (highest tune t, >=30 entries): g={best[1]} band={best[2]} tune t={cand[best][1]:+.2f}; report: entries {rep[0]}, markets {rep[2]}, PnL {rep[3]:+.1f}, t {rep[1]:+.2f}")
    return out

if __name__ == "__main__":
    grp, pcol = sys.argv[1], sys.argv[2]
    E = simulate(grp, pcol)
    table(E, f"L3 {grp} model {pcol}: all entries (mid of next bucket + 1 cent)")
    print("\nby side (all 9 variants pooled, descriptive):")
    print(E.groupby(["period", "side"]).agg(n=("pnl", "size"), pnl=("pnl", "sum"), win=("win", "mean"), pe=("pe", "mean")).round(3).to_string())
    print("fee total $%.2f on stake $%.0f; fee formula check max abs err %.2e" % (E.fee.sum(), len(E) * STAKE, (E.fee - E.shares * 0.01 * E.pe * (1 - E.pe)).abs().max()))
