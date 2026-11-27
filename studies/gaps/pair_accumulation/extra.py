"""Post-hoc DESCRIPTIVE tables (not trading rules, written after seeing analyze.py output). Writes out/extra.md.

1. Where the loss comes from: net per share of filled legs by the fraction of the window elapsed at the fill.
2. Pooled net per window by day (each level, conservative).
3. Pair and single-leg contributions, pooled by duration.
4. Placement skips by level; median shares printed through L within 10 s of the first through print."""
from __future__ import annotations

import numpy as np
import pandas as pd

from analyze import cl_mean, windows_table
from common import BIG, DUR, LEVELS, OUT

legs = pd.read_parquet(BIG / "legs_main.parquet")
lines = ["# Post-hoc descriptive tables (extra.py)", ""]

W, D = windows_table(legs, "cons")
D["frac"] = D["tf"] / D["dur"].map(DUR)
D["ppsh"] = np.where(D.filled, D.won.astype(float) - D.L, np.nan)
D["hour"] = D.t0 // 3600
bins = [0, 0.5, 0.8, 0.95, 1.0001]
labs = ["0-50%", "50-80%", "80-95%", "95-100%"]
D["fb"] = pd.cut(D.frac, bins, labels=labs, right=False)
lines += ["## 1. Filled legs (conservative): net c/share by share of the window elapsed at the fill", "",
          "| dur | L | " + " | ".join(f"{b}: legs, win rate, net c/sh (t)" for b in labs) + " |", "|---|---|" + "---|" * 4]
for dur in ("5m", "15m", "1h"):
    for L in LEVELS:
        x = D[(D.dur == dur) & (D.L == L) & D.filled]
        cells = []
        for b in labs:
            y = x[x.fb == b]
            if len(y) < 2:
                cells.append(f"{len(y)}")
                continue
            m, se = cl_mean(y.ppsh, y.hour)
            cells.append(f"{len(y)}, {y.won.mean():.3f}, {100 * m:+.1f} ({m / se if se else float('nan'):+.1f})")
        lines.append(f"| {dur} | {L:.2f} | " + " | ".join(cells) + " |")
lines.append("")

lines += ["## 2. Pooled net $/window by day (conservative, all 12 series)", "",
          "| L | " + " | ".join(str(pd.to_datetime(d * 86400, unit='s').date()) for d in sorted(W.day.unique())) + " |",
          "|---|" + "---|" * W.day.nunique()]
for L in LEVELS:
    w = W[W.L == L]
    lines.append(f"| {L:.2f} | " + " | ".join(f"{w[w.day == d].net.mean():+.2f}" for d in sorted(W.day.unique())) + " |")
lines.append("")

lines += ["## 3. Contribution of completed pairs and single legs, $ per window (conservative)", "",
          "| dur | L | windows | pairs (share) | pair $ per window | single-leg windows (share) | single-leg $ per window | total $ per window |",
          "|---|---|---|---|---|---|---|---|"]
W["dur"] = W.series.str.split("-").str[1]
for dur in ("5m", "15m", "1h"):
    for L in LEVELS:
        w = W[(W.dur == dur) & (W.L == L)]
        n = len(w)
        p, s = w[w.nf == 2], w[w.nf == 1]
        lines.append(f"| {dur} | {L:.2f} | {n} | {len(p)} ({len(p) / n:.0%}) | {p.net.sum() / n:+.2f} | {len(s)} ({len(s) / n:.0%}) | "
                     f"{s.net.sum() / n:+.2f} | {w.net.mean():+.2f} |")
lines.append("")

lines += ["## 4. Placement skips and through-size", "", "| L | legs | skipped (ask already <= L in the 30 s before t0) | "
          "filled legs (cons) | median shares through L in 10 s | p25 |", "|---|---|---|---|---|---|"]
for L in LEVELS:
    x = legs[legs.L == L]
    f = D[(D.L == L) & D.filled]
    cap = x.loc[x.placeable & x.t_cons.notna(), "cap_sh"]
    lines.append(f"| {L:.2f} | {len(x)} | {(~x.placeable).sum()} | {len(f)} | {cap.median():.0f} | {cap.quantile(0.25):.0f} |")
lines.append("")
(OUT / "extra.md").write_text("\n".join(lines))
print("\n".join(lines))
