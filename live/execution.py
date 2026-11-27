"""Causal paper execution on the recorded public feed, with no network access.

Call observe after applying a recorder row to BookReplay, before submitting
decisions made from that row. A taker gets one IOC attempt on fresh depth after
arrival. A passive order must first be able to rest on fresh depth and then
receive a later, opposite-side trade strictly through its limit. No rebates.

A retrospectively recorded gap emits fill_tainted for prior dependent fills.
For an offline cash path, replay with those gap boundaries inserted at their
effective receipt times before computing daily results.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_DOWN

from pmlab.fees import fee_per_share, taker_fee

from .book import BookQuote, BookReplay
from .settlement import confirmed_payouts

MS = 1_000_000
SECOND = 1_000_000_000
ZERO = Decimal(0)
ONE = Decimal(1)
SHARE_PRECISION = Decimal("0.000001")
FEE_ROUNDING_HEADROOM = Decimal("0.00001")


def _decimal(value) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError("missing numeric value")
    number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError("expected a finite number")
    return number


def _text(number: Decimal) -> str:
    return format(number, "f")


def _taker_fee(price: Decimal, size: Decimal, rate: Decimal) -> Decimal:
    if not rate:
        return ZERO
    return _decimal(taker_fee(float(size), float(price), float(rate)))


def _affordable_size(cash: Decimal, size: Decimal, price: Decimal, rate: Decimal) -> Decimal:
    if size * price + _taker_fee(price, size, rate) <= cash:
        return size
    fee_unit = _decimal(fee_per_share(float(price), float(rate))) if rate else ZERO
    headroom = FEE_ROUNDING_HEADROOM if fee_unit else ZERO
    capacity = max(ZERO, (cash - headroom) / (price + fee_unit))
    return min(size, capacity.quantize(SHARE_PRECISION, rounding=ROUND_DOWN))


@dataclass
class _Order:
    intent_id: str
    token: str
    slug: str
    outcome: str
    side: str
    style: str
    limit: Decimal
    remaining: Decimal
    fee_rate: Decimal
    signal_ns: int
    signal_ordinal: int | None
    signal_exchange_ms: int
    ready_ns: int
    exchange_ready_ns: int
    execute_by_ns: int
    expires_ns: int
    session: str
    rested_ns: int | None = None
    rested_exchange_ms: int | None = None


@dataclass
class _MarketTotals:
    shares_bought: Decimal = ZERO
    shares_sold: Decimal = ZERO
    buy_notional: Decimal = ZERO
    sell_notional: Decimal = ZERO
    fees: Decimal = ZERO


@dataclass
class _Level:
    displayed: Decimal | None
    available: Decimal

    def refresh(self, size: Decimal) -> None:
        # Reductions consume available depth first. A repeated absolute size
        # or snapshot does not replenish already consumed paper liquidity.
        self.available = max(ZERO, self.available + size - (self.displayed or ZERO))
        self.displayed = size


class PaperExecution:
    """An isolated paper account. Dollar amounts and shares use Decimal."""

    def __init__(
        self,
        *,
        initial_cash: str | int | Decimal = "200",
        latency_ms: int = 1000,
        max_book_age_ms: int = 1500,
        max_trade_age_ms: int = 1000,
        max_taker_wait_ms: int = 1000,
        max_clock_skew_ms: int = 250,
    ) -> None:
        timing = (latency_ms, max_book_age_ms, max_trade_age_ms, max_taker_wait_ms, max_clock_skew_ms)
        if any(type(value) is not int or value < 0 for value in timing):
            raise ValueError("timings must be nonnegative integer milliseconds")
        self.initial_cash = _decimal(initial_cash)
        if self.initial_cash < ZERO:
            raise ValueError("initial cash must be nonnegative")
        self.cash = self.initial_cash
        self.latency_ns = latency_ms * MS
        self.max_book_age_ns = max_book_age_ms * MS
        self.max_trade_age_ns = max_trade_age_ms * MS
        self.max_taker_wait_ns = max_taker_wait_ms * MS
        self.max_clock_skew_ns = max_clock_skew_ms * MS
        self._orders: dict[str, _Order] = {}
        self._positions: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
        self._outcomes: dict[tuple[str, str], str] = {}
        self._market_totals: dict[str, _MarketTotals] = defaultdict(_MarketTotals)
        self._market_ends: dict[str, int] = {}
        self._markets: dict[str, dict] = {}
        self._settled: set[str] = set()
        self._mirrors: dict[str, str] = {}
        self._depth: dict[str, dict[tuple[str, Decimal], _Level]] = {}
        self._prints: dict[tuple, set[str | None]] = {}
        self._print_receipts: deque[tuple[int, tuple]] = deque()
        self._fills: list[dict] = []
        self._tainted: set[str] = set()
        self._intent_seq = self._fill_seq = 0
        self._last_observation: tuple[int, int | None] | None = None

    def _record(self, kind: str, order: _Order, row: dict, **fields) -> dict:
        return {
            "kind": kind, "recv_ns": row["recv_ns"], "ordinal": row.get("ordinal"),
            "intent_id": order.intent_id, "token": order.token, "slug": order.slug,
            "outcome": order.outcome, "side": order.side, "style": order.style,
            "limit_price": _text(order.limit), "signal_ordinal": order.signal_ordinal,
            "signal_recv_ns": order.signal_ns, "signal_exchange_ms": order.signal_exchange_ms,
            "book_session": order.session, "execute_by_ns": order.execute_by_ns,
            **fields,
        }

    def submit(self, intent: dict, row: dict, book: BookReplay) -> list[dict]:
        """Submit a simulated order at the receipt time of a recorded signal."""
        self._intent_seq += 1
        intent_id = f"intent-{self._intent_seq}"
        now = row["recv_ns"]
        try:
            token, slug, outcome = (intent[key] for key in ("token", "slug", "outcome"))
            side, style = intent["side"], intent["style"]
            price, requested, fee_rate, minimum, tick = (
                _decimal(intent[key]) for key in ("price", "size", "fee_rate", "min_size", "tick_size")
            )
            expires = _decimal(intent["end_ts"]) * SECOND
            if not all(isinstance(value, str) and value for value in (token, slug, outcome)):
                raise ValueError("invalid_market")
            if side not in ("BUY", "SELL") or style not in ("taker", "passive"):
                raise ValueError("invalid_order_type")
            if not (ZERO < price < ONE and ZERO < tick < ONE and price % tick == ZERO):
                raise ValueError("invalid_price_tick")
            if not (ZERO < minimum <= requested and ZERO <= fee_rate <= ONE):
                raise ValueError("invalid_size_or_fee")
            if expires != expires.to_integral_value() or now + self.latency_ns >= expires:
                raise ValueError("expired_before_arrival")
            deadline = intent.get("execute_by_ns", int(expires) - 1)
            if type(deadline) is not int or deadline < 0:
                raise ValueError("invalid_execution_deadline")
            deadline = min(deadline, int(expires) - 1)
            if now + self.latency_ns > deadline:
                raise ValueError("arrival_after_deadline")
            if slug in self._settled:
                raise ValueError("resolved")
            market = self._markets.get(slug)
            if (
                self._market_ends.get(slug, expires) != expires
                or (market is not None and market["end_ts"] * SECOND != expires)
            ):
                raise ValueError("inconsistent_market_expiry")
            if (
                self._outcomes.get((slug, token), outcome) != outcome
                or (market is not None and market["tokens"].get(outcome) != token)
            ):
                raise ValueError("inconsistent_outcome")
            quote = book.quote(token, depth=1)
            if not self._fresh_book(quote, now):
                raise ValueError("book_unavailable_or_stale")
            signal_exchange_ms = self._signal_exchange_ms(intent, row, quote)
            exchange_ready_ns = signal_exchange_ms * MS + self.latency_ns
            if exchange_ready_ns > deadline:
                raise ValueError("arrival_after_deadline")

            size = min(requested, Decimal(100))
            if side == "BUY":
                reserved = sum(
                    order.remaining for order in self._orders.values()
                    if order.slug == slug and order.side == "BUY"
                )
                size = min(size, Decimal(500) - self._market_totals[slug].shares_bought - reserved)
                if size < minimum:
                    raise ValueError("market_cap")
                rate = fee_rate if style == "taker" else ZERO
                free_cash = self._unreserved_cash()
                if minimum * price + _taker_fee(price, minimum, rate) > free_cash:
                    raise ValueError("insufficient_cash")
                size = max(minimum, _affordable_size(free_cash, size, price, rate))
            else:
                reserved = sum(
                    order.remaining for order in self._orders.values()
                    if order.slug == slug and order.token == token and order.side == "SELL"
                )
                size = min(size, self._positions[slug, token] - reserved)
            if size < minimum:
                raise ValueError("insufficient_position" if side == "SELL" else "market_cap")
        except (KeyError, ValueError, InvalidOperation, TypeError) as error:
            return [{
                "kind": "rejected", "recv_ns": now, "ordinal": row.get("ordinal"),
                "intent_id": intent_id,
                **{
                    key: intent[key] if isinstance(intent.get(key), str) else None
                    for key in ("token", "slug", "outcome", "side", "style")
                },
                "signal_ordinal": row.get("ordinal"), "signal_recv_ns": now,
                "reason": str(error),
            }]

        order = _Order(
            intent_id, token, slug, outcome, side, style, price, size, fee_rate,
            now, row.get("ordinal"), signal_exchange_ms, now + self.latency_ns,
            exchange_ready_ns, deadline, int(expires), quote.session,
        )
        self._market_ends[slug] = order.expires_ns
        self._outcomes[slug, token] = outcome
        self._orders[intent_id] = order
        return [self._record(
            "submitted", order, row, price=_text(price), size=_text(size),
            requested_size=_text(requested), ready_ns=order.ready_ns,
            exchange_ready_ns=order.exchange_ready_ns, expires_ns=order.expires_ns,
        )]

    @staticmethod
    def _signal_exchange_ms(intent: dict, row: dict, quote: BookQuote) -> int:
        stamps = [quote.book_exchange_ms]
        payload = row.get("payload")
        snapshot = intent.get("snapshot")
        raw_stamps = (
            payload.get("timestamp") if isinstance(payload, dict) else None,
            snapshot.get("trade_exchange_ms") if isinstance(snapshot, dict) else None,
        )
        for stamp in raw_stamps:
            if type(stamp) is int and stamp >= 0:
                stamps.append(stamp)
            elif isinstance(stamp, str) and stamp.isascii() and stamp.isdecimal():
                stamps.append(int(stamp))
        return max(stamps)

    def _fresh_book(self, quote: BookQuote, now: int) -> bool:
        return (
            quote.status == "ok"
            and quote.session is not None
            and quote.book_recv_ns is not None
            and quote.book_exchange_ms is not None
            and 0 <= now - quote.book_recv_ns <= self.max_book_age_ns
            and -self.max_clock_skew_ns <= now - quote.book_exchange_ms * MS <= self.max_book_age_ns
        )

    @staticmethod
    def _changed_depth(payload: dict) -> set[str]:
        if payload.get("event_type") == "book":
            return {payload.get("asset_id")}
        if payload.get("event_type") == "price_change":
            changes = payload.get("price_changes")
            if isinstance(changes, (list, tuple)):
                return {
                    change["asset_id"] for change in changes
                    if isinstance(change, dict) and isinstance(change.get("asset_id"), str)
                }
        return set()

    def observe(self, row: dict, book: BookReplay) -> list[dict]:
        """Consume a row already applied to the book and return lifecycle records."""
        now, kind = row["recv_ns"], row["kind"]
        observation = (now, row.get("ordinal"))
        if self._last_observation is not None and now < self._last_observation[0]:
            raise ValueError("paper observations must follow recorder time")
        if observation == self._last_observation and observation[1] is not None:
            return []
        self._last_observation = observation
        output: list[dict] = []
        if kind == "market":
            market = row["market"]
            outcomes = market["tokens"]
            slug, condition = market.get("slug"), market.get("condition_id")
            if (
                isinstance(slug, str) and isinstance(condition, str) and condition
                and type(market.get("end_ts")) is int
            ):
                self._markets.setdefault(slug, {**market, "tokens": dict(outcomes)})
            tokens = list(outcomes.values())
            if len(tokens) == 2:
                self._mirrors[tokens[0]] = tokens[1]
                self._mirrors[tokens[1]] = tokens[0]
        elif kind == "gap":
            output.extend(self._mark_gap(row))
        elif kind == "resolution":
            output.extend(self._settle(row))

        payload = row.get("payload", {}) if kind == "ws" else {}
        depth_tokens = self._changed_depth(payload)
        trade_token = payload.get("asset_id") if payload.get("event_type") == "last_trade_price" else None
        quotes = {}
        for token in depth_tokens & self._depth.keys():
            quote = quotes[token] = book.quote(token)
            if quote.status == "ok" and quote.book_recv_ns == now:
                self._refresh_levels(token, quote)
        if not self._orders and trade_token is None:
            return output

        print_remaining = ZERO
        for intent_id, order in list(self._orders.items()):
            status = book.status_for(order.token)
            if now >= order.expires_ns or order.slug in self._settled:
                output.append(self._close(order, row, "expired" if order.slug not in self._settled else "resolved"))
                continue
            if now > order.execute_by_ns:
                output.append(self._close(order, row, "execution_deadline"))
                continue
            if status != "ok":
                output.append(self._close(order, row, status))
                continue
            if now < order.ready_ns:
                continue
            if order.rested_ns is None and now > order.ready_ns + self.max_taker_wait_ns:
                output.append(self._close(order, row, "arrival_not_observed"))
                continue
            if order.token not in depth_tokens and order.token != trade_token:
                continue
            if order.token not in quotes:
                quotes[order.token] = book.quote(order.token)
            quote = quotes[order.token]
            if quote.session != order.session:
                output.append(self._close(order, row, "subscription_changed"))
                continue
            if not self._fresh_book(quote, now):
                continue
            if order.rested_ns is None:
                if (
                    order.token not in depth_tokens or row.get("source") == "rest_checkpoint"
                    or quote.book_recv_ns != now
                    or not max(order.ready_ns, order.exchange_ready_ns)
                    <= quote.book_exchange_ms * MS <= order.execute_by_ns
                ):
                    continue
                if order.style == "taker":
                    output.extend(self._take(order, row, quote))
                    continue
                best_opposite = quote.asks if order.side == "BUY" else quote.bids
                if best_opposite and self._inside_limit(order, best_opposite[0][0]):
                    output.append(self._close(order, row, "post_only_would_cross"))
                    continue
                order.rested_ns = now
                order.rested_exchange_ms = quote.book_exchange_ms
                output.append(self._record(
                    "resting", order, row, remaining=_text(order.remaining),
                    rested_exchange_ms=order.rested_exchange_ms,
                ))
                continue
            if order.token != trade_token:
                continue
            trade = quote.last_trade
            if (
                trade is None or trade.recv_ns != now
                or trade.side != ("SELL" if order.side == "BUY" else "BUY")
                or not self._inside_limit(order, trade.price, strict=True)
                or trade.exchange_ms <= order.rested_exchange_ms
                or not order.rested_ns <= trade.exchange_ms * MS <= order.execute_by_ns
            ):
                continue
            if print_remaining == ZERO:
                print_remaining = self._fresh_print(row, payload)
            size = min(order.remaining, print_remaining)
            if size > ZERO:
                fill = self._fill(order, row, quote, order.limit, size, observed_price=trade.price)
                if fill is not None:
                    output.append(fill)
                    print_remaining -= _decimal(fill["size"])
                    if not order.remaining:
                        del self._orders[intent_id]
        # Record a print even if no order could take it in this observation.
        if trade_token is not None and not print_remaining:
            self._fresh_print(row, payload)
        return output

    @staticmethod
    def _inside_limit(order: _Order, price: Decimal, *, strict: bool = False) -> bool:
        distance = order.limit - price if order.side == "BUY" else price - order.limit
        return distance > ZERO if strict else distance >= ZERO

    def _refresh_levels(self, token: str, quote: BookQuote) -> None:
        bids, asks = dict(quote.bids), dict(quote.asks)
        for (side, price), level in self._depth[token].items():
            depth = asks if side == "BUY" else bids
            level.refresh(depth.get(price, ZERO))

    def _take(self, order: _Order, row: dict, quote: BookQuote) -> list[dict]:
        output = []
        displayed_levels = quote.asks if order.side == "BUY" else quote.bids
        depth = self._depth.setdefault(order.token, {})
        for price, displayed in displayed_levels:
            if not order.remaining or not self._inside_limit(order, price):
                break
            key = (order.side, price)
            level = depth.get(key)
            if level is not None and level.displayed is None:
                level.refresh(displayed)
            size = min(order.remaining, level.available if level is not None else displayed)
            if size <= ZERO:
                continue
            fill = self._fill(order, row, quote, price, size)
            if fill is None:
                break
            output.append(fill)
            used = _decimal(fill["size"])
            if level is None:
                level = depth[key] = _Level(displayed, displayed)
            level.available -= used
            self._debit_mirror(order, price, used)
        if order.remaining:
            output.append(self._close(order, row, "ioc_remainder"))
        else:
            del self._orders[order.intent_id]
        return output

    def _debit_mirror(self, order: _Order, price: Decimal, size: Decimal) -> None:
        mirror = self._mirrors.get(order.token)
        if mirror is None:
            return
        key = ("SELL" if order.side == "BUY" else "BUY", ONE - price)
        depth = self._depth.setdefault(mirror, {})
        level = depth.setdefault(key, _Level(None, ZERO))
        level.available -= size
        if level.displayed is not None:
            level.available = max(ZERO, level.available)

    def _fresh_print(self, row: dict, payload: dict) -> Decimal:
        now = row["recv_ns"]
        cutoff = now - self.max_trade_age_ns - self.max_clock_skew_ns
        while self._print_receipts and self._print_receipts[0][0] < cutoff:
            _, old = self._print_receipts.popleft()
            self._prints.pop(old, None)
        try:
            token, side = payload["asset_id"], payload["side"]
            exchange_ms = int(payload["timestamp"])
            price, size = _decimal(payload["price"]), _decimal(payload["size"])
            if side not in ("BUY", "SELL") or not ZERO < price < ONE or size <= ZERO:
                return ZERO
            if not -self.max_clock_skew_ns <= now - exchange_ms * MS <= self.max_trade_age_ns:
                return ZERO
            mirror = self._mirrors.get(token)
            if mirror is not None and mirror < token:
                token, side, price = mirror, "SELL" if side == "BUY" else "BUY", ONE - price
            # A print without a unique exchange ID is deduplicated by the
            # public economic fields, including across mirrored outcomes.
            raw_hash = payload.get("transaction_hash")
            tx_hash = raw_hash.lower() if isinstance(raw_hash, str) and raw_hash else None
            key = (token, side, exchange_ms, price, size)
        except (KeyError, TypeError, ValueError, InvalidOperation):
            return ZERO
        transactions = self._prints.get(key)
        if transactions is None:
            self._prints[key] = {tx_hash}
            self._print_receipts.append((now, key))
            return size
        if tx_hash is None or tx_hash in transactions:
            return ZERO
        if None in transactions:
            # The first identified copy accounts for the earlier unidentified
            # print. Other distinct transactions can then be counted.
            transactions.remove(None)
            transactions.add(tx_hash)
            return ZERO
        transactions.add(tx_hash)
        return size

    @staticmethod
    def _fee(order: _Order, price: Decimal, size: Decimal) -> Decimal:
        return _taker_fee(price, size, order.fee_rate) if order.style == "taker" else ZERO

    def _unreserved_cash(self, exclude: str | None = None) -> Decimal:
        reserved = sum(
            order.remaining * order.limit + self._fee(order, order.limit, order.remaining)
            for order in self._orders.values()
            if order.side == "BUY" and order.intent_id != exclude
        )
        return max(ZERO, self.cash - reserved)

    def _fill(
        self, order: _Order, row: dict, quote: BookQuote, price: Decimal,
        size: Decimal, *, observed_price: Decimal | None = None,
    ) -> dict | None:
        if size <= ZERO:
            return None
        position = (order.slug, order.token)
        if order.side == "BUY":
            free_cash = self._unreserved_cash(exclude=order.intent_id)
            rate = order.fee_rate if order.style == "taker" else ZERO
            size = _affordable_size(free_cash, size, price, rate)
        else:
            size = min(size, self._positions[position])
        if size <= ZERO:
            return None

        at_value = size * price
        fee = self._fee(order, price, size)
        totals = self._market_totals[order.slug]
        if order.side == "BUY":
            debit = at_value + fee
            if debit > free_cash:
                return None
            self.cash -= debit
            self._positions[position] += size
            totals.shares_bought += size
            totals.buy_notional += at_value
        else:
            self.cash += at_value - fee
            self._positions[position] -= size
            totals.shares_sold += size
            totals.sell_notional += at_value
        order.remaining -= size
        totals.fees += fee
        self._fill_seq += 1
        fill = self._record(
            "fill", order, row, fill_id=f"fill-{self._fill_seq}", price=_text(price),
            size=_text(size), fee=_text(fee), remaining=_text(order.remaining),
            cash=_text(self.cash), evidence_ordinal=row.get("ordinal"),
            book_recv_ns=quote.book_recv_ns, snapshot_recv_ns=quote.snapshot_recv_ns,
            book_exchange_ms=quote.book_exchange_ms, book_source=quote.snapshot_source,
            observed_price=_text(observed_price) if observed_price is not None else None,
        )
        self._fills.append(fill)
        return fill

    def _close(self, order: _Order, row: dict, reason: str) -> dict:
        del self._orders[order.intent_id]
        return self._record("closed", order, row, reason=reason, remaining=_text(order.remaining))

    def _mark_gap(self, row: dict) -> list[dict]:
        now = row["recv_ns"]
        since = row.get("since_ns", now)
        if since >= now:
            return []
        tokens = set(row.get("tokens", ()))
        labels = []
        for fill in self._fills:
            if (
                fill["fill_id"] not in self._tainted
                and fill["book_session"] == row["session"]
                and (not tokens or fill["token"] in tokens)
                and (since < fill["recv_ns"] <= now or since < fill["signal_recv_ns"] <= now)
            ):
                self._tainted.add(fill["fill_id"])
                labels.append({
                    "kind": "fill_tainted", "recv_ns": now, "ordinal": row.get("ordinal"),
                    "fill_id": fill["fill_id"], "intent_id": fill["intent_id"],
                    "slug": fill["slug"], "token": fill["token"], "since_ns": since,
                    "reason": row.get("reason"),
                })
        return labels

    def _settle(self, row: dict) -> list[dict]:
        slug = row.get("slug")
        if not isinstance(slug, str) or slug in self._settled:
            return []
        payouts = confirmed_payouts(row, self._markets.get(slug))
        if payouts is None:
            return []
        positions = {
            token: quantity for (market, token), quantity in self._positions.items()
            if market == slug and quantity > ZERO
        }
        if any(self._outcomes[slug, token] not in payouts for token in positions):
            return []
        self._settled.add(slug)
        totals = self._market_totals.get(slug)
        if totals is None or not totals.shares_bought:
            return []

        payout = sum(
            (quantity * payouts[self._outcomes[slug, token]] for token, quantity in positions.items()),
            ZERO,
        )
        for token in positions:
            del self._positions[slug, token]
        self.cash += payout
        gross = payout + totals.sell_notional
        cost = totals.buy_notional + totals.fees
        return [{
            "kind": "settlement", "recv_ns": row["recv_ns"], "ordinal": row.get("ordinal"),
            "slug": slug, "gross": _text(gross), "payout": _text(payout), "cost": _text(cost),
            "net": _text(gross - cost), "fees": _text(totals.fees),
            "shares_bought": _text(totals.shares_bought), "shares_sold": _text(totals.shares_sold),
            "cash": _text(self.cash),
        }]
