"""Validate an official Gamma payout against the market announced on this tape."""

from decimal import Decimal, InvalidOperation


def confirmed_payouts(row, market):
    if not market or row.get("kind") != "resolution" or row.get("source") != "gamma":
        return None
    if row.get("slug") != market.get("slug") or row.get("condition_id") != market.get(
        "condition_id"
    ):
        return None
    if (
        not market.get("condition_id")
        or row["recv_ns"] < market["end_ts"] * 1_000_000_000
    ):
        return None
    raw = row.get("payouts")
    if not isinstance(raw, dict) or len(raw) != 2 or set(raw) != set(market["tokens"]):
        return None
    try:
        payouts = {outcome: Decimal(str(value)) for outcome, value in raw.items()}
        if (
            all(v.is_finite() and 0 <= v <= 1 for v in payouts.values())
            and sum(payouts.values()) == 1
        ):
            return payouts
    except (ValueError, InvalidOperation):
        pass
    return None
