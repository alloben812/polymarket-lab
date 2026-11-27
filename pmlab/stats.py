"""Small-sample-honest statistics: everything is aggregated per cluster (market or day) first."""
from __future__ import annotations

import math
import random
from typing import Iterable, Sequence


def mean_se(xs: Sequence[float]) -> tuple[float, float, float]:
    """mean, standard error, t-statistic of independent values (one value per cluster)."""
    n = len(xs)
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    m = sum(xs) / n
    if n == 1:
        return m, float("nan"), float("nan")
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    se = math.sqrt(var / n)
    return m, se, (m / se if se > 0 else float("nan"))


def ratio_cluster(num_by_cluster: Sequence[float], den_by_cluster: Sequence[float]) -> tuple[float, float, float]:
    """Ratio of sums (e.g. total profit / total shares) with a cluster-robust standard error (linearisation).

    Use this for "edge per share" or "return on turnover": clusters with more volume weigh more, and fills inside
    one market are not treated as independent.
    """
    n = len(num_by_cluster)
    den = sum(den_by_cluster)
    if n == 0 or den == 0:
        return float("nan"), float("nan"), float("nan")
    r = sum(num_by_cluster) / den
    if n == 1:
        return r, float("nan"), float("nan")
    resid = [a - r * b for a, b in zip(num_by_cluster, den_by_cluster)]
    var = n / (n - 1) * sum(e * e for e in resid) / (den * den)
    se = math.sqrt(var)
    return r, se, (r / se if se > 0 else float("nan"))


def bootstrap_sum_ci(cluster_values: Sequence[float], n_boot: int = 4000, alpha: float = 0.05, seed: int = 7) -> tuple[float, float]:
    """Percentile CI for the total, resampling clusters with replacement."""
    rng = random.Random(seed)
    n = len(cluster_values)
    if n == 0:
        return float("nan"), float("nan")
    sums = sorted(sum(cluster_values[rng.randrange(n)] for _ in range(n)) for _ in range(n_boot))
    return sums[int(alpha / 2 * n_boot)], sums[min(n_boot - 1, int((1 - alpha / 2) * n_boot))]


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson interval for a proportion."""
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return centre - half, centre + half


def max_drawdown(increments: Iterable[float]) -> float:
    peak = cum = dd = 0.0
    for x in increments:
        cum += x
        peak = max(peak, cum)
        dd = max(dd, peak - cum)
    return dd


def split_by_time(items: Sequence, key, frac: float = 0.67) -> tuple[list, list]:
    """Earlier `frac` of the items (by key) for tuning, the rest for reporting."""
    s = sorted(items, key=key)
    cut = int(len(s) * frac)
    return s[:cut], s[cut:]
