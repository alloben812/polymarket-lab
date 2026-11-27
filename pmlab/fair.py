"""Fair probability of "Up" for a crypto up/down market.

Settlement (since 2026-08-14 for 5m; 15m and 4h use the same idea): Up when the L-second TWAP at the end of the
window >= the L-second TWAP at its start (the "price to beat", K). We model the log price as a driftless Brownian
motion with per-second volatility sigma:

  before the averaging window (t <= T - L):  A ~ N(S_t, (sigma S)^2 * (tau1 + L/3)),  tau1 = (T - L) - t
  inside it (elapsed e, remaining r = L - e):  A = (e/L) * mean_so_far + (r/L) * mean_future,
                                               mean_future ~ N(S_t, (sigma S)^2 * r/3)

P(Up) = Phi((E[A] - K) / sd[A]).  The last-minute branch is the "lock-in": with 20 s left, two thirds of the
settlement average is already fixed.

`sigma_mult` widens trailing realised volatility; 1.3 gave good calibration on 3,287 BTC 5m markets (Jul-Nov 2026).
The inputs here are Binance closes, while the official values come from Chainlink: the proxy calls the outcome
correctly in about 96.5% of BTC 5m markets and the misses are all moves below ~1 bp, so never trust the model when
the gap to K is that small. Pass the official K (gamma eventMetadata.priceToBeat, rescaled by the basis) when you
have it.
"""
from __future__ import annotations

import math

from .px import Px


def ncdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def fair_up(px: Px, t: float, t0: int, dur: int = 300, lookback: int = 60, k: float | None = None,
            sigma: float | None = None, sigma_mult: float = 1.3, vol_lookback: int = 900) -> float:
    """P(Up) at time t for the window [t0, t0 + dur]. Returns NaN when inputs are missing."""
    if k is None:
        k = px.twap(t0, lookback)
    s = px.price(t)
    if sigma is None:
        sigma = px.sigma(t, vol_lookback)
    if not (k == k and s == s and sigma == sigma):
        return float("nan")
    sigma *= sigma_mult
    t_avg0, t_end = t0 + dur - lookback, t0 + dur
    if t >= t_end:
        a = px.twap(t_end, lookback)
        return float("nan") if a != a else (1.0 if a >= k else 0.0)
    if t <= t_avg0:
        mean = s
        var = (sigma * s) ** 2 * ((t_avg0 - t) + lookback / 3.0)
    else:
        e, r = t - t_avg0, t_end - t
        so_far = px.mean_between(t_avg0, t)
        if so_far != so_far:
            so_far = s
        mean = (e / lookback) * so_far + (r / lookback) * s
        var = ((r / lookback) * sigma * s) ** 2 * (r / 3.0)
    sd = math.sqrt(max(var, 1e-12))
    return ncdf((mean - k) / sd)


def gap_in_sigmas(px: Px, t: float, t0: int, dur: int = 300, lookback: int = 60, k: float | None = None,
                  sigma_mult: float = 1.3) -> float:
    """(E[A] - K) / sd[A]: how many standard deviations the expected settlement average is from the strike."""
    p = fair_up(px, t, t0, dur, lookback, k, sigma_mult=sigma_mult)
    if p != p or p <= 0.0 or p >= 1.0:
        return float("nan") if p != p else (8.0 if p >= 1.0 else -8.0)
    # inverse normal CDF by bisection (no scipy here)
    lo, hi = -8.0, 8.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if ncdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2
