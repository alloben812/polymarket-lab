"""Shared constants and loaders for the low-fee crypto up/down lag study (see protocol.md)."""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from pmlab import updown  # noqa: E402
from pmlab.http import get_json  # noqa: E402
from pmlab.px import MIRROR, Px  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
BIG = ROOT / "data" / "gaps_crypto_lowfee"

T_START = 1795219200   # 2026-11-21 00:00:00 UTC
T_LAST = 1795736700    # 2026-11-26 23:45:00 UTC (last window start, inclusive)
T_REPORT = 1795564800  # 2026-11-25 00:00:00 UTC
DAYS = ["2026-11-20", "2026-11-21", "2026-11-22", "2026-11-23", "2026-11-24", "2026-11-25", "2026-11-26"]
T_NEXT_DAY = 1795737600  # 2026-11-27 00:00:00 UTC

SERIES = [("eth", "5m"), ("eth", "15m"), ("sol", "15m"), ("xrp", "15m"), ("btc", "15m")]
REF = ("btc", "5m")
EXPECTED_RATE = {("eth", "5m"): 0.01, ("eth", "15m"): 0.01, ("sol", "15m"): 0.01, ("xrp", "15m"): 0.01,
                 ("btc", "15m"): 0.05, ("btc", "5m"): 0.05}


def name(series: tuple[str, str]) -> str:
    return f"{series[0]}-{series[1]}"


def grid(dur: str) -> list[int]:
    return [t for t in updown.windows(dur, T_START, T_LAST + 1) if t <= T_LAST]


def series_windows(series: tuple[str, str]) -> list[int]:
    g = grid(series[1])
    if series == REF:
        n = len(g)
        return sorted({g[round(i * (n - 1) / 299)] for i in range(300)})
    return g


def period(t0: int) -> str:
    return "tune" if t0 < T_REPORT else "report"


def day_of(t0: int) -> str:
    return dt.datetime.fromtimestamp(t0, dt.timezone.utc).strftime("%Y-%m-%d")


def load_px(symbol: str) -> Px:
    """Dumps for 20-26 Nov plus the first 180 s of 27 Nov from the mirror (cached), as one dense series."""
    base = Px.load(symbol, DAYS)
    ok = base.ok
    ts = (np.arange(len(base.p)) + base.t_min)[ok]
    p = base.p[ok]
    rows = get_json(MIRROR, {"symbol": symbol, "interval": "1s", "startTime": T_NEXT_DAY * 1000, "limit": 180}, cache=True)
    t2 = np.array([int(r[0]) // 1000 for r in rows], dtype=np.int64)
    p2 = np.array([float(r[4]) for r in rows])
    keep = t2 > ts[-1]
    return Px(np.concatenate([ts, t2[keep]]), np.concatenate([p, p2[keep]]))
