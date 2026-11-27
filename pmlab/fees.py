"""Polymarket taker fees and rebate tiers.

fee per share = rate * p * (1 - p); makers pay nothing. Rates in force since 2026-11-20 23:59 UTC are in CURRENT.
History is only partly known: the BTC 5-minute rate was 0.07 before that date (measured from one account's real
charges in Jul, Sep and Oct 2026). For any other market/date, calibrate from real charges with implied_rate().
"""
from __future__ import annotations

FEE_CHANGE_TS = 1795219140  # 2026-11-20 23:59:00 UTC

CURRENT = {
    "crypto_btc_5m_15m": 0.05, "crypto_other": 0.01, "sports": 0.05, "finance": 0.05, "tech": 0.05,
    "politics_elections": 0.05, "politics_other": 0.01, "economics": 0.01, "culture": 0.01, "weather": 0.01,
    "mentions": 0.01, "geopolitics": 0.0, "combos": 0.05, "other": 0.05,
}

TAKER_TIERS = [(75e6, 0.60, "Onyx"), (10e6, 0.50, "Obsidian"), (4e6, 0.40, "Diamond"), (1e6, 0.25, "Platinum"), (2e5, 0.10, "Gold"), (0.0, 0.0, "None")]
MAKER_TIERS = [(10e6, 0.15), (4e6, 0.10), (1e6, 0.07), (2e5, 0.03), (0.0, 0.0)]


def fee_per_share(price: float, rate: float) -> float:
    return rate * price * (1.0 - price)


def taker_fee(shares: float, price: float, rate: float) -> float:
    """Fee in USDC for a taker fill. The exchange rounds to 5 decimals."""
    return round(shares * fee_per_share(price, rate), 5)


def market_rate(market: dict) -> float | None:
    """Fee rate recorded on a gamma market object (reliable for markets that traded after FEE_CHANGE_TS)."""
    if market.get("feesEnabled") is False:
        return 0.0
    fs = market.get("feeSchedule") or {}
    rate = fs.get("rate")
    return float(rate) if rate is not None else None


def btc_updown_rate(ts: int) -> float:
    """BTC 5m (and, by the docs, 15m) up/down rate at trade time `ts`."""
    return 0.05 if ts >= FEE_CHANGE_TS else 0.07


def implied_rate(fees_charged: float, taker_fills: list[tuple[float, float]]) -> float | None:
    """Back out the rate from actual charges: fees / sum(shares * p * (1-p)) over the taker fills (shares, price)."""
    base = sum(s * p * (1.0 - p) for s, p in taker_fills)
    return abs(fees_charged) / base if base > 0 else None


def taker_rebate_rate(weighted_volume_30d: float) -> float:
    return next(r for thr, r, _ in TAKER_TIERS if weighted_volume_30d >= thr)


def maker_rebate_rate(maker_weighted_volume_30d: float) -> float:
    return next(r for thr, r in MAKER_TIERS if maker_weighted_volume_30d >= thr)


def taker_weighted_volume(shares: float, price: float) -> float:
    """Taker tier volume: trade dollars times (1 - price)."""
    return shares * price * (1.0 - price)


maker_weighted_volume = taker_weighted_volume  # same expression: shares * p * (1 - p)
