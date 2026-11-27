"""Reference prices: Binance 1-second closes (public dumps and the public mirror API) as a dense array."""
from __future__ import annotations

import datetime as dt
import io
import math
import urllib.request
import zipfile
from pathlib import Path

import numpy as np

from .http import ROOT, get_json

DUMPS = "https://data.binance.vision/data/spot/daily/klines/{sym}/1s/{sym}-1s-{day}.zip"
MIRROR = "https://data-api.binance.vision/api/v3/klines"
STORE = ROOT / "data" / "binance_1s"


def download_day(symbol: str, day: str, store: Path = STORE) -> Path | None:
    """Fetch one daily 1s-kline dump (available with about a day's delay). Returns the zip path or None."""
    store.mkdir(parents=True, exist_ok=True)
    path = store / f"{symbol}-1s-{day}.zip"
    if path.exists() and path.stat().st_size > 1000:
        return path
    url = DUMPS.format(sym=symbol, day=day)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=180) as r:
            blob = r.read()
    except Exception:  # noqa: BLE001 - not published yet or network error
        return None
    if len(blob) < 1000:
        return None
    path.write_bytes(blob)
    return path


def _read_zip(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with zipfile.ZipFile(path) as z:
        raw = z.read(z.namelist()[0]).decode()
    a = np.genfromtxt(io.StringIO(raw), delimiter=",", usecols=(0, 4))
    t = a[:, 0]
    t = np.where(t > 1e14, t / 1e6, t / 1e3).astype(np.int64)  # dumps are in microseconds since 2025
    return t, a[:, 1]


def _mirror_range(symbol: str, start: int, end: int) -> tuple[np.ndarray, np.ndarray]:
    """1s closes for [start, end) from the public mirror (1000 rows per call) - for days without a dump yet."""
    ts, px = [], []
    cur = start
    while cur < end:
        rows = get_json(MIRROR, {"symbol": symbol, "interval": "1s", "startTime": cur * 1000, "limit": 1000})
        if not rows:
            break
        for r in rows:
            sec = int(r[0]) // 1000
            if sec >= end:
                break
            ts.append(sec)
            px.append(float(r[4]))
        nxt = int(rows[-1][0]) // 1000 + 1
        if nxt <= cur:
            break
        cur = nxt
    return np.array(ts, dtype=np.int64), np.array(px, dtype=float)


class Px:
    """Dense per-second close series with O(1) TWAP and realised-volatility lookups."""

    def __init__(self, ts: np.ndarray, px: np.ndarray, max_gap: int = 120):
        order = np.argsort(ts)
        ts, px = ts[order], px[order]
        self.t_min, self.t_max = int(ts[0]), int(ts[-1])
        dense = np.full(self.t_max - self.t_min + 1, np.nan)
        dense[ts - self.t_min] = px
        idx = np.where(~np.isnan(dense), np.arange(len(dense)), 0)
        np.maximum.accumulate(idx, out=idx)
        gap = np.arange(len(dense)) - idx
        filled = dense[idx]
        filled[gap > max_gap] = np.nan  # do not bridge long holes (missing days)
        self.p = filled
        self.ok = ~np.isnan(filled)
        self.cs = np.concatenate([[0.0], np.cumsum(np.where(self.ok, filled, 0.0))])
        self.cok = np.concatenate([[0], np.cumsum(self.ok)])
        lr = np.diff(np.log(filled))
        lr[~np.isfinite(lr)] = 0.0
        self.csq = np.concatenate([[0.0, 0.0], np.cumsum(lr * lr)])  # csq[i+1] = sum of squared returns up to index i

    @classmethod
    def load(cls, symbol: str, days: list[str], store: Path = STORE, fetch: bool = True) -> "Px":
        """days: ['2026-11-21', ...] (UTC). Missing dumps are fetched; the current/previous day falls back to the mirror."""
        ts_all, px_all = [], []
        for day in days:
            path = store / f"{symbol}-1s-{day}.zip"
            if not path.exists() and fetch:
                path = download_day(symbol, day, store) or path
            if path.exists():
                t, p = _read_zip(path)
            elif fetch:
                d0 = int(dt.datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc).timestamp())
                t, p = _mirror_range(symbol, d0, d0 + 86400)
            else:
                continue
            if len(t):
                ts_all.append(t)
                px_all.append(p)
        if not ts_all:
            raise FileNotFoundError(f"no price data for {symbol} {days}")
        return cls(np.concatenate(ts_all), np.concatenate(px_all))

    def _i(self, t: float) -> int:
        return int(t) - self.t_min

    def price(self, t: float) -> float:
        i = self._i(t)
        return float(self.p[i]) if 0 <= i < len(self.p) else float("nan")

    def twap(self, t_end: float, lookback: int = 60) -> float:
        """Mean of the closes of seconds (t_end - lookback, t_end]."""
        j = self._i(t_end)
        i = j - lookback
        if i < -1 or j >= len(self.p):
            return float("nan")
        n = self.cok[j + 1] - self.cok[i + 1]
        if n < lookback * 0.8:
            return float("nan")
        return float((self.cs[j + 1] - self.cs[i + 1]) / n)

    def mean_between(self, t_from: float, t_to: float) -> float:
        """Mean of closes of seconds (t_from, t_to]; NaN when empty."""
        i, j = self._i(t_from), self._i(t_to)
        if j <= i or i < -1 or j >= len(self.p):
            return float("nan")
        n = self.cok[j + 1] - self.cok[i + 1]
        return float((self.cs[j + 1] - self.cs[i + 1]) / n) if n > 0 else float("nan")

    def sigma(self, t: float, lookback: int = 900) -> float:
        """Per-second log-return volatility over the `lookback` seconds ending at t."""
        j = self._i(t)
        i = j - lookback
        if i < 0 or j + 1 >= len(self.csq):
            return float("nan")
        return math.sqrt(max((self.csq[j + 1] - self.csq[i + 1]) / lookback, 1e-18))


def days_between(start_ts: int, end_ts: int) -> list[str]:
    d = dt.datetime.fromtimestamp(start_ts, dt.timezone.utc).date()
    last = dt.datetime.fromtimestamp(end_ts, dt.timezone.utc).date()
    out = []
    while d <= last:
        out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out
