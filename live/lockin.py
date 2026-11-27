"""Receipt-ordered paper signals for the judged BTC 5m lock-in variant.

The rule uses a 60-second entry window, P(favourite) >= .99, a .02 margin,
D = 1 second of information delay, and the study's fixed E99 in dollars.
A public print generates a candidate, using BUY on its own outcome and SELL
on the complement. It never supplies an executable price or depth. A paper
intent requires a covered, fresh ask and uses at most its displayed size,
the print size, and 100 shares. The paper executor enforces the 500-share
market cap against its pending and executed quantities. Identical and mirrored
messages from the same transaction are considered once. Without a transaction
identifier, distinct fills with identical economic details and exchange time
can be merged.
"""

from __future__ import annotations

from collections import deque
from decimal import Decimal, InvalidOperation
from math import isfinite

import numpy as np

from pmlab.fair import fair_up
from pmlab.fees import fee_per_share
from pmlab.px import Px

from .book import BookReplay
from .settlement import confirmed_payouts

SECOND_NS = 1_000_000_000
MILLISECOND_NS = 1_000_000
WINDOW = 60
DELAY = 1
FLOOR = 0.99
MARGIN = 0.02
E99 = 18.629401876966732
VOL_LOOKBACK = 900
PER_PRINT_CAP = Decimal(100)
MARKET_CAP = 500
MIN_PRICE = Decimal("0.50")
MAX_AGE_NS = 2 * SECOND_NS
CLOCK_TOLERANCE_NS = 100 * MILLISECOND_NS


def _decimal(value) -> Decimal:
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("nonfinite decimal")
    return result


def _exchange_ms(payload: dict) -> int:
    value = payload.get("timestamp")
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and value.isascii() and value.isdecimal():
        return int(value)
    raise ValueError("invalid exchange timestamp")


def _fresh(recv_ns: int, timestamp_ns: int) -> bool:
    return -CLOCK_TOLERANCE_NS <= recv_ns - timestamp_ns <= MAX_AGE_NS


class Lockin:
    def __init__(self):
        self._markets: dict[str, tuple[dict, str]] = {}
        self._markets_by_slug: dict[str, dict] = {}
        self._closed: set[str] = set()
        self._ticks: dict[str, tuple[int, Decimal]] = {}
        self._bars: dict[int, tuple[float, int]] = {}
        self._latest_open: int | None = None
        self._print_order: deque[tuple[int, tuple[str, int, Decimal, Decimal]]] = (
            deque()
        )
        self._prints: dict[tuple[str, int, Decimal, Decimal], set[str | None]] = {}

    def _reference(self, row: dict) -> None:
        if row.get("symbol") != "BTCUSDT":
            return
        recv_ns = row["recv_ns"]
        cutoff = recv_ns // SECOND_NS - 1200
        self._bars = {ts: bar for ts, bar in self._bars.items() if ts >= cutoff}
        for opened, close in row["bars"]:
            if (
                type(opened) is not int
                or opened < cutoff
                or (opened + 1) * SECOND_NS > recv_ns
            ):
                continue
            try:
                price = float(close)
            except (TypeError, ValueError, OverflowError):
                continue
            if isfinite(price) and price > 0:
                self._bars.setdefault(opened, (price, recv_ns))
        self._latest_open = max(self._bars, default=None)

    def _model(
        self, market: dict, start: int, recv_ns: int, snapshot: dict
    ) -> str | None:
        t0 = market["start_ts"]
        t1 = market["end_ts"]
        model_t = start - DELAY - 1
        history_start = min(t0 - WINDOW + 1, model_t - VOL_LOOKBACK)
        snapshot.update(
            model_open_s=model_t,
            model_closed_s=model_t + 1,
            reference_latest_open_s=self._latest_open,
        )
        latest = self._bars.get(model_t)
        if latest is None or latest[1] > recv_ns:
            return "reference_late"
        times = range(history_start, model_t + 1)
        prices = []
        for second in times:
            bar = self._bars.get(second)
            if bar is None or bar[1] > recv_ns:
                snapshot["reference_missing_open_s"] = second
                return "reference_gap"
            prices.append(bar[0])
        px = Px(np.asarray(times, dtype=np.int64), np.asarray(prices), max_gap=0)
        strike = px.twap(t0, WINDOW)
        p_up = fair_up(px, model_t, t0, k=strike)
        expected = px.price(model_t)
        averaging_start = t1 - WINDOW
        if model_t > averaging_start:
            elapsed = model_t - averaging_start
            remaining = t1 - model_t
            expected = (elapsed / WINDOW) * px.mean_between(
                averaging_start, model_t
            ) + (remaining / WINDOW) * expected
        if not all(isfinite(value) for value in (p_up, expected, strike)):
            return "reference_invalid"
        favored = "Up" if p_up >= 0.5 else "Down"
        fair = max(p_up, 1 - p_up)
        snapshot.update(
            p_up=p_up,
            favored_outcome=favored,
            fair=fair,
            model_ceiling=fair - MARGIN,
            strike=strike,
            expected_average=expected,
            basis_distance=abs(expected - strike),
            reference_recv_ns=latest[1],
        )
        return None

    def _tick(self, token: str, payload: dict, field: str) -> None:
        if token not in self._markets or field not in payload:
            return
        try:
            timestamp = _exchange_ms(payload)
            value = _decimal(payload[field])
        except (InvalidOperation, ValueError):
            return
        if 0 < value < 1 and (
            token not in self._ticks or timestamp >= self._ticks[token][0]
        ):
            self._ticks[token] = timestamp, value

    def observe(self, row: dict, book: BookReplay) -> list[dict]:
        """Inspect one journal row already applied to the replay book."""
        kind = row["kind"]
        if kind == "market":
            market = row["market"]
            start, end = market.get("start_ts"), market.get("end_ts")
            if (
                market.get("kind") == "btc5m"
                and type(start) is int
                and end == start + 300
                and market.get("slug") == f"btc-updown-5m-{start}"
                and set(market["tokens"]) == {"Up", "Down"}
            ):
                self._markets_by_slug[market["slug"]] = market
                for outcome, token in market["tokens"].items():
                    self._markets[token] = (market, outcome)
            return []
        if kind == "reference":
            self._reference(row)
            return []
        if kind == "resolution":
            market = self._markets_by_slug.get(row.get("slug"))
            if market is not None and confirmed_payouts(row, market) is not None:
                self._closed.add(market["slug"])
            return []
        if kind != "ws":
            return []

        payload = row["payload"]
        event = payload.get("event_type")
        if event == "market_resolved":
            for asset in payload.get("assets_ids") or []:
                if isinstance(asset, str) and asset in self._markets:
                    self._closed.add(self._markets[asset][0]["slug"])
            return []

        token = payload.get("asset_id")
        if not isinstance(token, str) or token not in self._markets:
            return []
        if event == "tick_size_change":
            self._tick(token, payload, "new_tick_size")
        elif event == "book":
            quote = book.quote(token, depth=1)
            if quote.status == "ok" and quote.snapshot_recv_ns == row["recv_ns"]:
                self._tick(token, payload, "tick_size")
        elif event == "last_trade_price" and row.get("source") in {
            None,
            "ws",
            "websocket",
        }:
            return self._candidate(row, book, token)
        return []

    def _duplicate(
        self,
        token: str,
        exchange_ms: int,
        price: Decimal,
        size: Decimal,
        recv_ns: int,
        transaction: str | None,
    ) -> bool:
        # A mirror BUY/SELL representation of a print shares its buyable
        # outcome, price and absolute size. One transaction can emit both.
        cutoff = recv_ns - MAX_AGE_NS - CLOCK_TOLERANCE_NS
        while self._print_order and self._print_order[0][0] < cutoff:
            _, expired = self._print_order.popleft()
            self._prints.pop(expired)
        key = (token, exchange_ms, price, size)
        transactions = self._prints.get(key)
        if transactions is None:
            self._prints[key] = {transaction}
            self._print_order.append((recv_ns, key))
            return False
        if transaction is None or transaction in transactions:
            return True
        if None in transactions:
            # Match the first known transaction to the prior unidentified print.
            transactions.remove(None)
            transactions.add(transaction)
            return True
        transactions.add(transaction)
        return False

    def _candidate(self, row: dict, book: BookReplay, traded_token: str) -> list[dict]:
        payload = row["payload"]
        recv_ns = row["recv_ns"]
        market, outcome = self._markets[traded_token]
        end = market["end_ts"]
        floor_ns = (end - WINDOW) * SECOND_NS
        limit_ns = (end - 2) * SECOND_NS
        if recv_ns < floor_ns:
            return []

        side = payload.get("side")
        if side == "SELL":
            outcome = "Down" if outcome == "Up" else "Up"
        token = market["tokens"][outcome]
        snapshot = {
            "trade_side": side if isinstance(side, str) else None,
            "trade_price": None,
            "candidate_price": None,
            "ask_price": None,
            "ask_size": None,
        }
        decision = {
            "action": "skip",
            "token": token,
            "slug": market["slug"],
            "outcome": outcome,
            "snapshot": snapshot,
            "recv_ns": recv_ns,
        }

        def skip(reason: str) -> list[dict]:
            decision["reason"] = reason
            return [decision]

        try:
            exchange_ms = _exchange_ms(payload)
            price = _decimal(payload.get("price"))
            size = _decimal(payload.get("size"))
            if side not in ("BUY", "SELL") or not 0 <= price <= 1 or size <= 0:
                raise ValueError("invalid trade fields")
        except (InvalidOperation, ValueError):
            return skip("invalid_trade")

        candidate_price = price if side == "BUY" else 1 - price
        trade_ns = exchange_ms * MILLISECOND_NS
        snapshot.update(
            trade_exchange_ms=exchange_ms,
            trade_price=str(price),
            trade_size=str(size),
            candidate_price=str(candidate_price),
        )
        if (
            market["slug"] in self._closed
            or recv_ns >= end * SECOND_NS
            or book.status_for(token) == "resolved"
        ):
            return skip("market_closed")
        if not floor_ns <= trade_ns <= limit_ns or recv_ns > limit_ns:
            return skip("outside_entry_window")
        if not _fresh(recv_ns, trade_ns):
            return skip("stale_trade")
        if payload.get("market") not in (None, market.get("condition_id")):
            return skip("wrong_market")

        quote = book.quote(token, depth=1)
        snapshot.update(
            book_status=quote.status,
            book_recv_ns=quote.book_recv_ns,
            book_exchange_ms=quote.book_exchange_ms,
            book_source=quote.snapshot_source,
        )
        if quote.asks:
            ask, depth = quote.asks[0]
            snapshot.update(ask_price=str(ask), ask_size=str(depth))
        transaction = payload.get("transaction_hash")
        transaction = (
            transaction.lower()
            if isinstance(transaction, str) and transaction
            else None
        )
        if self._duplicate(
            token, exchange_ms, candidate_price, size, recv_ns, transaction
        ):
            return skip("duplicate_print")
        if candidate_price < MIN_PRICE:
            return skip("price_below_floor")
        if size < 5:
            return skip("print_below_minimum")

        model_error = self._model(market, trade_ns // SECOND_NS, recv_ns, snapshot)
        if model_error is not None:
            return skip(model_error)
        if outcome != snapshot["favored_outcome"]:
            return skip("unfavored_outcome")
        if snapshot["fair"] < FLOOR:
            return skip("probability_below_floor")
        if snapshot["basis_distance"] < E99:
            return skip("basis_filter")
        if float(candidate_price) > snapshot["model_ceiling"] + 1e-9:
            return skip("print_above_model_ceiling")
        if quote.status != "ok" or quote.session != row["session"]:
            return skip("book_unavailable")
        if (
            quote.book_recv_ns is None
            or not 0 <= recv_ns - quote.book_recv_ns <= MAX_AGE_NS
            or quote.book_exchange_ms is None
            or not _fresh(recv_ns, quote.book_exchange_ms * MILLISECOND_NS)
        ):
            return skip("book_stale")
        if not quote.asks:
            return skip("no_ask")
        if ask <= 0 or ask > candidate_price:
            return skip("ask_above_trade_limit")

        try:
            fee_rate = _decimal(market.get("fee_rate"))
            minimum = max(Decimal(5), _decimal(market.get("min_size")))
            tick = (
                self._ticks[token][1]
                if token in self._ticks
                else _decimal(market.get("tick_size"))
            )
            if (
                not 0 <= fee_rate <= 1
                or not 0 < tick < 1
                or _decimal(market.get("min_size")) <= 0
            ):
                raise ValueError("invalid market limits")
            if ask % tick != 0:
                return skip("ask_off_tick")
        except (InvalidOperation, ValueError):
            return skip("unknown_market_limits")

        requested = min(size, depth, PER_PRINT_CAP)
        if requested < minimum:
            return skip("size_below_minimum")

        fee = fee_per_share(float(ask), float(fee_rate))
        snapshot.update(
            fee_per_share=fee,
            expected_net_per_share=snapshot["fair"] - float(ask) - fee,
        )
        parameters = {
            "fee_rate": str(fee_rate),
            "min_size": str(market["min_size"]),
            "tick_size": str(tick),
            "end_ts": end,
        }
        decision.update(
            action="intent",
            reason="rule_met",
            side="BUY",
            style="taker",
            price=str(ask),
            size=str(requested),
            market={**market, **parameters},
            **parameters,
        )
        return [decision]
