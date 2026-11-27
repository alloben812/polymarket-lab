"""Shared helpers for the BTC 5m lock-in study (see protocol.md)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from pmlab import fair, px as pxmod, updown  # noqa: E402

START = 1795219200  # 2026-11-21 00:00 UTC
END = START + 6 * 86400
SPLIT = 1795564800  # 2026-11-25 00:00 UTC: tuning before, reporting from here
RATE = 0.05
DATA = ROOT / "data" / "gaps_btc5m_lockin"
OUT = Path(__file__).resolve().parent / "out"
SLICE = int(os.environ.get("LOCKIN_SLICE", "0"))  # smoke test on the first N windows: separate extract and output dirs
EXTRACT = DATA / (f"slice{SLICE}" if SLICE else "full")
if SLICE:
    OUT = OUT / f"slice{SLICE}"
DAYS = ["2026-11-20", "2026-11-21", "2026-11-22", "2026-11-23", "2026-11-24", "2026-11-25", "2026-11-26", "2026-11-27"]


def all_windows() -> list[int]:
    w = updown.windows("5m", START, END)
    return w[:SLICE] if SLICE else w


def load_px() -> pxmod.Px:
    return pxmod.Px.load("BTCUSDT", DAYS)


def meta(t0: int) -> dict | None:
    """Cached metadata only (fetch.py did the downloading)."""
    p = updown.META_DIR / "btc" / "5m" / f"{t0}.json"
    return json.loads(p.read_text()) if p.exists() else None


def fee(q):
    return RATE * q * (1.0 - q)


def expected_avg(px: pxmod.Px, t: int, t0: int, dur: int = 300, lookback: int = 60) -> float:
    """E[settlement average] at model time t, same expressions as pmlab.fair.fair_up (protocol item 12)."""
    s = px.price(t)
    t_avg0, t_end = t0 + dur - lookback, t0 + dur
    if t <= t_avg0:
        return s
    e, r = t - t_avg0, t_end - t
    so_far = px.mean_between(t_avg0, t)
    if so_far != so_far:
        so_far = s
    return (e / lookback) * so_far + (r / lookback) * s


def model_at(px: pxmod.Px, t: int, t0: int) -> tuple[float, float, float]:
    """(P(Up), expected settlement average, K) at model time t; K is the Binance start TWAP."""
    k = px.twap(t0, 60)
    return fair.fair_up(px, t, t0), expected_avg(px, t, t0), k
