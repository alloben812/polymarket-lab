"""Shared helpers for the crypto-levels-vs-options study."""
import datetime as dt, gzip, json, math, re
from pathlib import Path
import numpy as np
from pmlab.http import ROOT, get_json
from pmlab import gamma, dataapi

DATA = ROOT / "data" / "gaps_levels"
HERE = Path(__file__).resolve().parent
EURO_SERIES = {"btc-multi-strikes-weekly": ("BTC", "daily"), "ethereum-multi-strikes-weekly": ("ETH", "daily"),
               "bitcoin-multi-strikes-hourly": ("BTC", "hourly"), "ethereum-multi-strikes-hourly": ("ETH", "hourly")}
OT_SERIES = {"bitcoin-hit-price-daily": ("BTC", "daily"), "bitcoin-hit-price-weekly": ("BTC", "weekly"),
             "bitcoin-hit-price-monthly": ("BTC", "monthly"), "ethereum-hit-price-daily": ("ETH", "daily"),
             "ethereum-hit-price-weekly": ("ETH", "weekly"), "ethereum-hit-price-monthly": ("ETH", "monthly")}
WIN0, WIN1 = "2026-10-27T00:00:00Z", "2026-11-26T23:59:59Z"
TUNE_LAST = "2026-11-15"
YEAR = 365 * 86400.0


def ts(s: str) -> int:
    s = s.replace("Z", "+00:00").replace(" ", "T")
    if re.search(r"\+00$", s):
        s += ":00"
    return int(dt.datetime.fromisoformat(s).timestamp())


def iso(t: float) -> str:
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ncdf(x):
    x = np.asarray(x, dtype=float)
    from math import erf
    return 0.5 * (1.0 + np.vectorize(erf)(x / math.sqrt(2.0)))


def load_universe():
    return json.load(open(DATA / "universe.json"))


class Minute:
    """Dense Binance 1-minute series: close/high/low by candle open time."""
    def __init__(self, sym):
        a = np.load(DATA / f"{sym}_1m.npy")  # cols: open_time_s, open, high, low, close
        t0, t1 = int(a[0, 0]), int(a[-1, 0])
        n = (t1 - t0) // 60 + 1
        self.t0, self.n = t0, n
        for j, name in ((2, "high"), (3, "low"), (4, "close")):
            d = np.full(n, np.nan)
            d[((a[:, 0] - t0) // 60).astype(int)] = a[:, j]
            setattr(self, name, d)
        # last valid close index (for <=5 minute staleness)
        idx = np.where(~np.isnan(self.close), np.arange(n), -10**9)
        self.last = np.maximum.accumulate(idx)
        lr = np.diff(np.log(self.close))
        ok = np.isfinite(lr)
        self.csq = np.concatenate([[0.0], np.cumsum(np.where(ok, lr * lr, 0.0))])  # csq[i] = sum lr[0..i-1]
        self.cok = np.concatenate([[0], np.cumsum(ok)])

    def spot(self, t):
        """close of the last candle that ended at or before t (vectorised); NaN if >5 min stale."""
        t = np.asarray(t, dtype=np.int64)
        i = (t - self.t0) // 60 - 1  # candle opening at floor(t/60)*60-60 ends at <= t
        out = np.full(t.shape, np.nan)
        good = (i >= 0) & (i < self.n)
        ii = np.clip(i, 0, self.n - 1)
        li = self.last[ii]
        good &= (ii - li) <= 5
        out[good] = self.close[np.clip(li[good], 0, self.n - 1)]
        return out

    def rv(self, t, minutes=1440, min_ok=1300):
        """annualised realised vol from 1-minute log returns over the `minutes` ending at t."""
        t = np.asarray(t, dtype=np.int64)
        i = (t - self.t0) // 60 - 1  # index of last finished candle
        j0 = i - minutes
        out = np.full(t.shape, np.nan)
        good = (j0 >= 0) & (i < self.n)
        i2, j2 = np.clip(i, 0, self.n - 1), np.clip(j0, 0, self.n - 1)
        s = self.csq[i2] - self.csq[j2]
        k = self.cok[i2] - self.cok[j2]
        good &= k >= min_ok
        out[good] = np.sqrt(s[good] / k[good] * 1440 * 365)
        return out


class Dvol:
    def __init__(self, cur):
        a = np.load(DATA / f"dvol_{cur}.npy")  # cols: open_time_s, close
        self.t = a[:, 0].astype(np.int64)
        self.c = a[:, 1]

    def at(self, t):
        t = np.asarray(t, dtype=np.int64)
        i = np.searchsorted(self.t + 3600, t, side="right") - 1  # last candle with end <= t
        out = np.full(t.shape, np.nan)
        good = i >= 0
        ii = np.clip(i, 0, len(self.t) - 1)
        good &= (t - (self.t[ii] + 3600)) <= 6 * 3600
        out[good] = self.c[ii[good]] / 100.0
        return out


def p_above(S, K, sig, tau_s):
    v = sig * sig * np.maximum(tau_s, 1e-9) / YEAR
    return ncdf((np.log(S / K) - v / 2) / np.sqrt(v))


def p_touch(S, K, sig, tau_s, up):
    v = sig * sig * np.maximum(tau_s, 1e-9) / YEAR
    sv = np.sqrt(v)
    b = np.abs(np.log(K / S))
    if up:
        return ncdf((-b - v / 2) / sv) + (S / K) * ncdf((-b + v / 2) / sv)
    return ncdf((-b + v / 2) / sv) + (S / K) * ncdf((-b - v / 2) / sv)
