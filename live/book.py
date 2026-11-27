"""Replay recorded Polymarket L2 books in recorder receipt order.

An exchange timestamp is a millisecond clock, with legal ties and no sequence
counter. A snapshot anchors the book, and absolute level updates apply in log
order. Hashes carry no continuity guarantee. Coverage is evidence from this
recording, conditional on the feed delivering all updates between observations.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Iterator

Level = tuple[Decimal, Decimal]
Record = dict


@dataclass(frozen=True)
class Trade:
    price: Decimal
    size: Decimal | None
    side: str | None
    recv_ns: int
    exchange_ms: int


@dataclass(frozen=True)
class BookQuote:
    token: str
    status: str
    session: str | None = None
    bids: tuple[Level, ...] = ()
    asks: tuple[Level, ...] = ()
    snapshot_recv_ns: int | None = None
    book_recv_ns: int | None = None
    book_exchange_ms: int | None = None
    observed_recv_ns: int | None = None
    last_trade: Trade | None = None
    snapshot_source: str | None = None
    reason: str | None = None


@dataclass
class _TokenBook:
    session: str
    status: str = "missing_snapshot"
    paused: bool = False
    bids: dict[Decimal, Decimal] = field(default_factory=dict)
    asks: dict[Decimal, Decimal] = field(default_factory=dict)
    snapshot_recv_ns: int | None = None
    book_recv_ns: int | None = None
    exchange_ms: int | None = None
    last_trade: Trade | None = None
    snapshot_source: str | None = None
    reason: str | None = None

    def invalidate(self, status: str, reason: str | None = None) -> None:
        self.status = status
        self.reason = reason
        self.bids.clear()
        self.asks.clear()
        self.snapshot_recv_ns = None
        self.book_recv_ns = None
        self.last_trade = None
        self.snapshot_source = None


def _decimal(value: str | int | Decimal) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError("expected decimal string")
    result = Decimal(value)
    if not result.is_finite():
        raise ValueError("expected finite decimal")
    return result


def _price(value: str) -> Decimal:
    result = _decimal(value)
    if not 0 <= result <= 1:
        raise ValueError("price outside [0, 1]")
    return result


def _size(value: str) -> Decimal:
    result = _decimal(value)
    if result < 0:
        raise ValueError("negative size")
    return result


def _exchange_ms(payload: Record) -> int:
    value = payload.get("timestamp")
    if isinstance(value, str) and value.isascii() and value.isdecimal():
        return int(value)
    if type(value) is int and value >= 0:
        return value
    raise ValueError("missing or invalid exchange timestamp")


def _levels(rows: list[Record]) -> dict[Decimal, Decimal]:
    if not isinstance(rows, list):
        raise ValueError("expected a list of levels")
    levels = {}
    seen = set()
    for row in rows:
        price = _price(row["price"])
        size = _size(row["size"])
        if price in seen:
            raise ValueError("duplicate price in full snapshot")
        seen.add(price)
        if size:
            levels[price] = size
    return levels


def _crossed(bid: Decimal | None, ask: Decimal | None) -> bool:
    return bid is not None and ask is not None and bid >= ask


def _matches_best(value: str | None, actual: Decimal | None, empty: int) -> bool:
    # The raw feed uses bid 0 / ask 1 as sentinels for an empty side.
    return value is None or _price(value) == (empty if actual is None else actual)


class BookReplay:
    """Apply log records in receipt order and query the current token state."""

    def __init__(self) -> None:
        self._books: dict[str, _TokenBook] = {}
        self._announced: set[str] = set()
        self._market_tokens: dict[str, set[str]] = {}
        self._session_tokens: dict[str, set[str]] = defaultdict(set)
        self._closed_sessions: set[str] = set()
        self._observed: dict[str, int] = {}
        self._recv_ns: int | None = None

    def _bind(self, token: str, session: str) -> _TokenBook:
        old = self._books.get(token)
        if old is not None:
            self._session_tokens[old.session].discard(token)
        state = self._books[token] = _TokenBook(session)
        self._session_tokens[session].add(token)
        return state

    def _state(self, token: str, session: str) -> _TokenBook | None:
        state = self._books.get(token)
        if state is None:
            return self._bind(token, session)
        if state.session == session and not state.paused:
            return state
        return None

    def apply(self, record: Record) -> set[str]:
        """Update levels and return IDs whose book, trade or availability changed."""
        kind, recv_ns, session = record["kind"], record["recv_ns"], record["session"]
        if self._recv_ns is not None and recv_ns < self._recv_ns:
            raise ValueError("recorder recv_ns regressed")
        self._recv_ns = recv_ns
        if kind == "market":
            market = record["market"]
            tokens = set(market["tokens"].values())
            self._announced.update(tokens)
            condition = market.get("condition_id")
            if isinstance(condition, str) and condition:
                self._market_tokens[condition.lower()] = tokens
            return set()
        if kind in {"connected", "gap", "stop"}:
            return self._boundary(kind, record)
        if session in self._closed_sessions:
            return set()
        if kind == "heartbeat" and record.get("status") == "pong":
            self._observed[session] = recv_ns
        if kind == "ws":
            source = record.get("source", "ws")
            if source != "rest_checkpoint":
                self._observed[session] = recv_ns
            return self._apply_ws(session, recv_ns, record["payload"], source)
        return set()

    def _boundary(self, kind: str, record: Record) -> set[str]:
        session = record["session"]
        explicit = record.get("tokens", [])
        affected = explicit or self._session_tokens[session]
        targets = {token for token in affected if self.status_for(token) != "resolved"}
        if kind == "connected":
            if session in self._closed_sessions:
                raise ValueError(f"closed session ID reused: {session}")
            for token in targets:
                self._bind(token, session)
            return targets
        if kind == "stop" and not explicit:
            self._closed_sessions.add(session)
        reason = record.get("reason")
        status = "stopped" if kind == "stop" else "gap"
        if kind == "gap" and reason == "unsubscribed":
            status = "unsubscribed"
        changed = set()
        for token in targets:
            state = self._books.get(token)
            if state is None:
                state = self._bind(token, session)
            if state.session == session:
                state.invalidate(status, reason)
                state.paused = state.paused or status in {"stopped", "unsubscribed"}
                changed.add(token)
        return changed

    def _apply_ws(self, session: str, recv_ns: int, payload: Record, source: str) -> set[str]:
        event_type = payload.get("event_type")
        if source == "rest_checkpoint":
            event_type = "book"
        if event_type == "market_resolved":
            return self._resolve(session, payload)
        if event_type == "price_change":
            grouped: dict[str, list[Record]] = defaultdict(list)
            try:
                rows = payload["price_changes"]
                if not isinstance(rows, list) or not rows:
                    raise ValueError("missing price changes")
                for row in rows:
                    token = row["asset_id"]
                    if not isinstance(token, str) or not token:
                        raise ValueError("missing changed token ID")
                    grouped[token].append(row)
            except (KeyError, TypeError, ValueError):
                return self._invalidate_session(session, "malformed price_change batch")
            changed = set()
            for token, changes in grouped.items():
                state = self._state(token, session)
                if state is not None:
                    self._update(state, payload, changes, recv_ns)
                    changed.add(token)
            return changed
        if event_type not in {"book", "last_trade_price", "best_bid_ask"}:
            return set()
        token = payload.get("asset_id")
        if not isinstance(token, str) or not token:
            if event_type == "book":
                return self._invalidate_session(session, "malformed snapshot token ID")
            return set()
        state = self._state(token, session)
        if state is None:
            return set()
        if event_type == "book":
            self._update(state, payload, None, recv_ns, source)
        elif event_type == "last_trade_price":
            self._trade(state, payload, recv_ns)
        elif not self._check_best(state, payload):
            return set()
        return {token}

    def _resolve(self, session: str, payload: Record) -> set[str]:
        asset_ids = payload.get("assets_ids")
        tokens = (
            {token for token in asset_ids if isinstance(token, str) and token}
            if isinstance(asset_ids, list) else set()
        )
        condition = payload.get("market") or payload.get("condition_id")
        if isinstance(condition, str):
            tokens.update(self._market_tokens.get(condition.lower(), set()))
        changed = set()
        for token in tokens:
            state = self._books.get(token)
            if state is None:
                state = self._bind(token, session)
            if state.status != "resolved":
                state.invalidate("resolved")
                state.paused = True
                changed.add(token)
        return changed

    def _invalidate_session(self, session: str, reason: str) -> set[str]:
        changed = set()
        for token in self._session_tokens[session]:
            state = self._books[token]
            if not state.paused:
                state.invalidate("invalid_book", reason)
                changed.add(token)
        return changed

    def _update(
        self,
        state: _TokenBook,
        payload: Record,
        changes: list[Record] | None,
        recv_ns: int,
        source: str = "ws",
    ) -> None:
        try:
            exchange_ms = _exchange_ms(payload)
            if state.exchange_ms is not None and exchange_ms < state.exchange_ms:
                if changes is None or state.status == "ok":
                    state.invalidate("out_of_order", "exchange timestamp regressed")
                return
            state.exchange_ms = exchange_ms
            if changes is not None and state.status != "ok":
                return
            if changes is None:
                state.bids = _levels(payload["bids"])
                state.asks = _levels(payload["asks"])
            else:
                for change in changes:
                    side = {"BUY": state.bids, "SELL": state.asks}[change["side"]]
                    price, size = _price(change["price"]), _size(change["size"])
                    if size:
                        side[price] = size
                    else:
                        side.pop(price, None)
            bid, ask = max(state.bids, default=None), min(state.asks, default=None)
            if _crossed(bid, ask):
                state.invalidate("book_mismatch", "crossed book")
                return
            if changes is not None:
                # Hints can describe the final batch state, even on its first row.
                last = changes[-1]
                if not (
                    _matches_best(last.get("best_bid"), bid, 0)
                    and _matches_best(last.get("best_ask"), ask, 1)
                ):
                    state.invalidate("book_mismatch", "best bid/ask disagrees with the batch")
                    return
        except (KeyError, TypeError, ValueError, InvalidOperation) as error:
            state.invalidate("invalid_book", str(error))
            return
        if changes is None:
            state.snapshot_recv_ns = recv_ns
            state.snapshot_source = source
        state.status = "ok"
        state.reason = None
        state.book_recv_ns = recv_ns

    @staticmethod
    def _check_best(state: _TokenBook, payload: Record) -> bool:
        if state.status != "ok":
            return False
        try:
            exchange_ms = _exchange_ms(payload)
            if exchange_ms < state.exchange_ms:
                return False
            agrees = _matches_best(
                payload.get("best_bid"), max(state.bids, default=None), 0
            ) and _matches_best(
                payload.get("best_ask"), min(state.asks, default=None), 1
            )
        except (TypeError, ValueError, InvalidOperation):
            return False
        if agrees:
            return False
        # A top-of-book update has no quantities or deeper levels. A full
        # snapshot at least this recent is needed before quoting depth again.
        state.exchange_ms = exchange_ms
        state.invalidate("book_mismatch", "best_bid_ask disagrees with the book")
        return True

    @staticmethod
    def _trade(state: _TokenBook, payload: Record, recv_ns: int) -> None:
        if state.status != "ok":
            return
        try:
            exchange_ms = _exchange_ms(payload)
            if state.last_trade is not None and exchange_ms < state.last_trade.exchange_ms:
                return
            size = payload.get("size")
            side = payload.get("side")
            if side not in {None, "BUY", "SELL"}:
                raise ValueError("unknown trade side")
            state.last_trade = Trade(
                _price(payload["price"]), _size(size) if size is not None else None,
                side, recv_ns, exchange_ms,
            )
        except (KeyError, TypeError, ValueError, InvalidOperation):
            # A trade message carries no level updates.
            return

    def status_for(self, token: str) -> str:
        """Return availability without copying or sorting price levels."""
        state = self._books.get(token)
        if state is not None:
            return state.status
        return "missing_snapshot" if token in self._announced else "unknown_token"

    def quote(self, token: str, *, depth: int | None = None) -> BookQuote:
        """Copy best-first levels. In an unavailable quote, exchange time is a watermark."""
        if depth is not None and depth < 1:
            raise ValueError("depth must be positive")
        state = self._books.get(token)
        if state is None:
            return BookQuote(token, self.status_for(token))
        if state.status != "ok":
            return BookQuote(
                token, state.status, state.session,
                book_exchange_ms=state.exchange_ms, reason=state.reason,
            )
        observed = max(self._observed.get(state.session, 0), state.book_recv_ns)
        return BookQuote(
            token, "ok", state.session,
            tuple(sorted(state.bids.items(), reverse=True)[:depth]),
            tuple(sorted(state.asks.items())[:depth]),
            state.snapshot_recv_ns, state.book_recv_ns, state.exchange_ms,
            observed, state.last_trade, state.snapshot_source,
        )


def iter_records(paths: Iterable[Path | str]) -> Iterator[Record]:
    """Read gzip JSONL segments in the supplied order (plain JSONL for fixtures)."""
    previous_ns = -1
    run_ordinals: dict[Path, int | None] = {}
    for path in map(Path, paths):
        run = path.resolve().parent
        opener = gzip.open if path.name.endswith((".gz", ".gz.open")) else open
        with opener(path, "rt", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                try:
                    record = json.loads(line)
                    recv_ns = record["recv_ns"]
                    session = record["session"]
                    kind = record["kind"]
                    if type(recv_ns) is not int or recv_ns < max(previous_ns, 0):
                        raise ValueError("invalid or decreasing recv_ns")
                    if not isinstance(kind, str) or not kind or not isinstance(session, str):
                        raise ValueError("invalid record kind or session")
                    if kind in {"ws", "connected", "heartbeat"} and not session:
                        raise ValueError("missing market session")
                    if kind == "ws" and not isinstance(record.get("payload"), dict):
                        raise ValueError("expected a WebSocket payload object")
                    if kind == "gap":
                        _gap_start(record)
                    ordinal = record.get("ordinal")
                    if "ordinal" in record and (type(ordinal) is not int or ordinal < 1):
                        raise ValueError("invalid recorder ordinal")
                    if run in run_ordinals:
                        last_ordinal = run_ordinals[run]
                        if (ordinal is None) != (last_ordinal is None):
                            raise ValueError("recorder ordinal missing from part of the run")
                        if ordinal is not None and ordinal != last_ordinal + 1:
                            raise ValueError(
                                f"missing or reordered log records: expected ordinal "
                                f"{last_ordinal + 1}, found {ordinal}"
                            )
                    run_ordinals[run] = ordinal
                except (KeyError, TypeError, ValueError) as error:
                    raise ValueError(f"{path}:{line_number}: {error}") from error
                previous_ns = recv_ns
                yield record

def _gap_start(record: Record) -> int:
    recv_ns = record["recv_ns"]
    since_ns = record.get("since_ns", recv_ns)
    if type(since_ns) is not int or not 0 <= since_ns <= recv_ns:
        raise ValueError("gap since_ns must be between zero and recv_ns")
    # The recorder already proved receipt at since_ns. A gap first observed
    # at its boundary (e.g. unsubscribe) begins at that boundary instead.
    if record.get("reason") == "unsubscribed":
        return since_ns
    return min(since_ns + 1, recv_ns)


def _evidence(record: Record) -> bool:
    return (record["kind"] == "ws" and record.get("source") != "rest_checkpoint") or (
        record["kind"] == "heartbeat" and record.get("status") == "pong"
    )


def replay_as_of(
    paths: Iterable[Path | str], token: str, recv_ns: int, *, depth: int | None = None
) -> BookQuote:
    """Reconstruct a historically covered book using no levels after recv_ns."""
    if recv_ns < 0:
        raise ValueError("recv_ns must be nonnegative")
    replay = BookReplay()
    quote = None
    through = -1
    stopped = False
    for record in iter_records(paths):
        if record["recv_ns"] <= recv_ns:
            replay.apply(record)
            continue
        if quote is None:
            quote = replay.quote(token, depth=depth)
            if quote.status != "ok":
                return quote
            through = quote.observed_recv_ns
        if record["session"] != quote.session:
            continue
        if record["kind"] == "gap":
            targets = record.get("tokens", [])
            if (not targets or token in targets) and _gap_start(record) <= recv_ns:
                status = "unsubscribed" if record.get("reason") == "unsubscribed" else "gap"
                return BookQuote(token, status, quote.session, reason=record.get("reason"))
        if record["kind"] == "stop" and not record.get("tokens"):
            stopped = True
        if not stopped and _evidence(record):
            through = max(through, record["recv_ns"])
    if quote is None:
        quote = replay.quote(token, depth=depth)
        through = quote.observed_recv_ns
    if quote.status == "ok" and through < recv_ns:
        return BookQuote(token, "unobserved_tail", quote.session)
    return quote


@dataclass(frozen=True)
class Gap:
    session: str
    start_ns: int
    detected_ns: int
    reason: str | None


@dataclass(frozen=True)
class TokenCoverage:
    covered_ns: int
    intervals: tuple[tuple[int, int], ...]
    explicit_gaps: tuple[Gap, ...]
    status_changes: dict[str, int]


@dataclass(frozen=True)
class Coverage:
    from_ns: int | None
    to_ns: int | None
    window_ns: int
    records: int
    tokens: dict[str, TokenCoverage]


def _subtract_gaps(
    start: int, end: int, gaps: Iterable[Gap]
) -> Iterator[tuple[int, int]]:
    for gap in gaps:
        if gap.start_ns >= gap.detected_ns or gap.detected_ns <= start:
            continue
        if gap.start_ns > end:
            break
        if start < gap.start_ns:
            yield start, gap.start_ns - 1
        # The boundary itself is handled by ordinary recorder order.
        start = max(start, gap.detected_ns)
        if start > end:
            return
    if start <= end:
        yield start, end


def coverage(
    records: Iterable[Record],
    *,
    tokens: Iterable[str] | None = None,
    from_ns: int | None = None,
    to_ns: int | None = None,
) -> Coverage:
    """Return closed intervals of covered receipt time, with recorded gaps."""
    if any(value is not None and value < 0 for value in (from_ns, to_ns)):
        raise ValueError("coverage bounds must be nonnegative")
    if from_ns is not None and to_ns is not None and from_ns > to_ns:
        raise ValueError("from_ns must not exceed to_ns")
    requested = set(tokens) if tokens is not None else None
    replay = BookReplay()
    active: dict[str, tuple[int, str, int]] = {}
    periods: dict[str, list[tuple[int, int, str, int]]] = defaultdict(list)
    gaps: dict[str, list[tuple[Gap, set[str]]]] = defaultdict(list)
    token_sessions: dict[str, set[str]] = defaultdict(set)
    statuses: dict[str, Counter] = defaultdict(Counter)
    last_status: dict[str, str] = {}
    first = last = None
    count = 0

    for record in records:
        recv_ns = record["recv_ns"]
        if first is None:
            first = recv_ns
        last = recv_ns
        count += 1
        if record["kind"] == "gap":
            session = record["session"]
            gap = Gap(session, _gap_start(record), recv_ns, record.get("reason"))
            gaps[session].append((gap, set(record.get("tokens", []))))
        for token in replay.apply(record):
            if requested is not None and token not in requested:
                continue
            state = replay._books[token]
            token_sessions[token].add(state.session)
            if state.status != last_status.get(token):
                if (from_ns is None or from_ns <= recv_ns) and (to_ns is None or recv_ns <= to_ns):
                    statuses[token][state.status] += 1
                last_status[token] = state.status
            if state.status == "ok":
                start, session, book_end = active.get(token, (recv_ns, state.session, recv_ns))
                active[token] = (start, session, max(book_end, state.book_recv_ns))
            elif token in active:
                start, session, book_end = active.pop(token)
                periods[token].append((start, recv_ns - 1, session, book_end))

    for token, (start, session, book_end) in active.items():
        periods[token].append((start, last, session, book_end))
    start_ns = first if from_ns is None else from_ns
    end_ns = last if to_ns is None else to_ns
    window_ns = (
        max(0, end_ns - start_ns + 1) if start_ns is not None and end_ns is not None else 0
    )
    tracked = set(replay._books) | replay._announced if requested is None else requested
    reports = {}
    for token in sorted(tracked):
        covered = []
        by_session = {
            session: sorted(
                (gap for gap, targets in gaps[session] if not targets or token in targets),
                key=lambda gap: gap.start_ns,
            )
            for session in token_sessions[token]
        }
        token_gaps = sorted(
            (gap for session_gaps in by_session.values() for gap in session_gaps),
            key=lambda gap: (gap.start_ns, gap.detected_ns, gap.session),
        )
        if window_ns:
            for start, end, session, book_end in periods[token]:
                observed = max(replay._observed.get(session, 0), book_end)
                left, right = max(start_ns, start), min(end_ns, end, observed)
                if left <= right:
                    for lo, hi in _subtract_gaps(left, right, by_session[session]):
                        if covered and covered[-1][1] + 1 >= lo:
                            covered[-1] = covered[-1][0], max(covered[-1][1], hi)
                        else:
                            covered.append((lo, hi))
        reports[token] = TokenCoverage(
            sum(end - start + 1 for start, end in covered),
            tuple(covered),
            tuple(
                gap for gap in token_gaps
                if window_ns and gap.start_ns <= end_ns and gap.detected_ns >= start_ns
            ),
            dict(statuses[token]),
        )
    return Coverage(start_ns, end_ns, window_ns, count, reports)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    as_of = commands.add_parser("as-of", help="show covered L2 levels at a receipt timestamp")
    as_of.add_argument("files", nargs="+", type=Path, help="JSONL segments, oldest first")
    as_of.add_argument("--token", required=True)
    as_of.add_argument("--recv-ns", type=int, required=True)
    as_of.add_argument("--depth", type=int)
    check = commands.add_parser("coverage", help="measure covered receipt intervals and gaps")
    check.add_argument("files", nargs="+", type=Path, help="JSONL segments, oldest first")
    check.add_argument("--token", action="append", help="repeat for each token to report")
    check.add_argument("--from-ns", type=int)
    check.add_argument("--to-ns", type=int)
    args = parser.parse_args()
    try:
        if args.command == "as-of":
            result = replay_as_of(args.files, args.token, args.recv_ns, depth=args.depth)
        else:
            result = coverage(
                iter_records(args.files), tokens=args.token,
                from_ns=args.from_ns, to_ns=args.to_ns,
            )
    except (OSError, EOFError, ValueError) as error:
        print(f"book replay: {error}", file=sys.stderr)
        return 2
    print(json.dumps(asdict(result), default=str, indent=2))
    return int(isinstance(result, BookQuote) and result.status != "ok")


if __name__ == "__main__":
    raise SystemExit(main())
