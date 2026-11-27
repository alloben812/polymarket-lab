"""Shared rule code for the tail-sniper study (protocol.md section 2). No thresholds live anywhere else."""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from pmlab import fair, stats  # noqa: E402

DATA = ROOT / "data" / "gaps_btc5m_tail_sniper"
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)

DIST_CUT = 2.61       # published lowest-tercile cut of dist (btc5m_tails out/full/t3.md, pooled cell)
MV_CUT = 0.00122      # published top-tercile cut of mv30 toward the tail, bp
CAPS = {"Z1": 0.015, "Z2": 0.05}
BOOK_DELAYS = [0.0, 0.15, 0.5, 1.0, 2.0, 5.0]
TAPE_DELAYS = [1.0, 2.0, 5.0]
TAPE_WIN = 2.0        # tape fill interval [tau + d, tau + d + 2)
BUDGET = 5.0          # $ of stake per ticket
MIN_SHARES = 5.0


def signals(P, t0: int, dur: int) -> list[tuple[int, str, float, float, bool]]:
    """[(T, tail, dist, mv30, signal)] for decision seconds T with dur-75 <= T-t0 < dur-15. tail in {'Up','Down',''}."""
    out = []
    for T in range(t0 + dur - 75, t0 + dur - 15):
        g = fair.gap_in_sigmas(P, T, t0, dur, 60)
        a, b = P.price(T), P.price(T - 30)
        if g != g or g == 0 or not (a == a and b == b and b > 0):
            out.append((T, "", float("nan"), float("nan"), False))
            continue
        tail = "Down" if g > 0 else "Up"
        mv_up = (a / b - 1.0) * 1e4
        mv = -mv_up if tail == "Down" else mv_up
        dist = abs(g)
        out.append((T, tail, dist, mv, bool(dist < DIST_CUT and mv >= MV_CUT)))
    return out


def fee(shares, p, rate):
    return shares * rate * p * (1.0 - p)


def summarise(t: pd.DataFrame, days: float, rate_col: str = "rate") -> dict:
    """t: one row per filled ticket with columns t0, day, shares, stake, hit, and a fee-rate column."""
    n = len(t)
    if n == 0:
        return {"tickets": 0}
    f = fee(t.shares, t.stake / t.shares, t[rate_col])
    net = t.shares * t.hit.astype(float) - t.stake - f
    k = int(t.hit.sum())
    lo, hi = stats.wilson(k, n)
    be = float(((t.stake + f) / t.shares).mean())
    pb = binom_upper(k, n, be)
    m, se = float(net.mean()), float(net.std(ddof=1) / math.sqrt(n)) if n > 1 else float("nan")
    # day-cluster bootstrap of total net
    rng = np.random.default_rng(7)
    byday = net.groupby(t.day).sum()
    dn = byday.to_numpy()
    if len(dn) > 1:
        bs = np.array([rng.choice(dn, len(dn), replace=True).sum() for _ in range(2000)])
        blo, bhi = np.percentile(bs, [2.5, 97.5])
    else:
        blo = bhi = float("nan")
    best3 = float(net.sort_values(ascending=False).iloc[3:].sum())
    no_best_day = float(net.sum() - byday.max())
    return {
        "tickets": n, "hits": k, "hit_rate": k / n, "wil_lo": lo, "wil_hi": hi, "breakeven": be, "p_binom": pb,
        "shares": float(t.shares.sum()), "stake": float(t.stake.sum()), "avg_price": float(t.stake.sum() / t.shares.sum()),
        "fees": float(f.sum()), "net": float(net.sum()), "net_per_ticket": m, "npt_lo": m - 1.96 * se, "npt_hi": m + 1.96 * se,
        "ros": float(net.sum() / t.stake.sum()), "boot_lo": float(blo), "boot_hi": float(bhi),
        "tickets_per_day": n / days, "net_per_day": float(net.sum()) / days, "net_wo_best3": best3,
        "net_wo_best_day": no_best_day,
    }


def binom_upper(k: int, n: int, p: float) -> float:
    """P(X >= k), X ~ Bin(n, p)."""
    if n == 0 or not (0 < p < 1):
        return float("nan")
    s = 0.0
    for i in range(k, n + 1):
        s += math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * math.log(p) + (n - i) * math.log(1 - p))
    return min(1.0, s)
