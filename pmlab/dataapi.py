"""Data API v2 (trades, activity, PnL, leaderboards, resolutions, price history). Public, read-only."""
from __future__ import annotations

from typing import Iterator

from .http import get_json

DATA = "https://data-api.polymarket.com/v2"


def _walk(path: str, params: dict, max_rows: int | None = None) -> Iterator[dict]:
    """Follow next_cursor. The anchor params (user/condition/window) are re-sent with every cursor."""
    first = {k: v for k, v in params.items() if v is not None}
    anchor = {k: v for k, v in first.items() if k != "limit"}
    cursor = None
    n = 0
    while True:
        d = get_json(f"{DATA}/{path}", {**anchor, "cursor": cursor} if cursor else first)
        rows = d.get("data") or []
        for r in rows:
            yield r
            n += 1
            if max_rows is not None and n >= max_rows:
                return
        cursor = (d.get("pagination") or {}).get("next_cursor")
        if not cursor or not rows:
            return


def iter_trades(user: str | None = None, condition: str | None = None, start: int | None = None, end: int | None = None,
                taker_only: bool | None = None, side: str | None = None, max_rows: int | None = None) -> Iterator[dict]:
    """Fills, newest first. With `user`: that wallet's fills inside [start, end] (epoch seconds);
    taker_only=False adds its maker fills. With `condition`: the whole market tape, one row per fill on the
    taker side (start/end are ignored by the API for this shape)."""
    params = {"user": user, "condition": condition, "start": start, "end": end, "side": side, "limit": 1000,
              "taker_only": None if taker_only is None else str(taker_only).lower()}
    return _walk("trades", params, max_rows)


def iter_activity(user: str, types: str | None = None, start: int | None = None, end: int | None = None,
                  max_rows: int | None = None) -> Iterator[dict]:
    """Account activity: TRADE, SPLIT, MERGE, REDEEM, CONVERSION, REWARD, MAKER_REBATE, TAKER_REBATE, ..."""
    return _walk("activity", {"user": user, "type": types, "start": start, "end": end, "limit": 1000}, max_rows)


def user_stats(wallet: str) -> dict:
    return get_json(f"{DATA}/user-stats", {"user": wallet}).get("data") or {}


def user_pnl(wallet: str, interval: str = "all", fidelity: str = "1d") -> list[dict]:
    d = get_json(f"{DATA}/user-pnl", {"user": wallet, "interval": interval, "fidelity": fidelity}).get("data") or {}
    return sorted(d.get("points") or [], key=lambda p: p["timestamp"])


def leaderboard(category: str = "overall", time_period: str = "month", sort_by: str = "PNL", n: int = 100) -> list[dict]:
    rows: list[dict] = []
    for r in _walk("leaderboard", {"category": category, "time_period": time_period, "sort_by": sort_by, "limit": min(n, 100)}, n):
        rows.append(r)
    return rows


def resolutions(condition_ids: list[str], cache: bool = True) -> dict[str, dict]:
    """condition id -> {"resolved": bool, "final": {outcome: 1.0|0.0|...}, "slug": str, "tokens": {outcome: token_id}}."""
    out: dict[str, dict] = {}
    ids = list(dict.fromkeys(condition_ids))
    for i in range(0, len(ids), 10):
        chunk = ids[i:i + 10]
        d = get_json(f"{DATA}/tokens", {"condition": ",".join(chunk)})
        fresh: dict[str, dict] = {}
        for t in d.get("data") or []:
            e = fresh.setdefault(t["condition_id"], {"resolved": bool(t.get("resolved")), "final": {}, "slug": t.get("market_slug"), "tokens": {}})
            e["final"][t["outcome"]] = t.get("final_price")
            e["tokens"][t["outcome"]] = t.get("token_id")
            e["resolved"] = e["resolved"] and bool(t.get("resolved"))
        out.update(fresh)
    return out


def prices_history(token_id: str, start: int, end: int, bucket_seconds: int = 60) -> list[dict]:
    """Price points for one outcome token. Fine grains expire: 60 s >= 7 days, 300 s >= 60 days, 1800 s >= 90 days."""
    return list(_walk("prices-history", {"token_id": token_id, "start": start, "end": end, "bucket_seconds": bucket_seconds, "limit": 10000}))
