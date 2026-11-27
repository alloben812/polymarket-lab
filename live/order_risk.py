"""Durable local risk gate for passive BUY. No exchange API or credentials.

Reserve first, dispatch only after the one-time post claim, and retain the
reservation until authoritative exchange evidence provides the final outcome.
An ambiguous cancel keeps both its exposure and its no-resend state.

A ledger binds its mode and limits on creation. Reuse it across days and
restarts. Resetting/deleting a ledger discards its risk history and cannot
reconcile positions or orders left at the exchange.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from uuid import uuid4


ZERO = Decimal(0)
ONE = Decimal(1)
LIVE_MAX_ORDER_NOTIONAL = ONE
LIVE_MAX_TOTAL_EXPOSURE = Decimal(5)
LIVE_MAX_DAILY_RISK = Decimal(2)
TERMINAL = frozenset({"cancelled", "filled", "rejected"})
SCHEMA_VERSION = "1"


class RiskError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _amount(value, *, code: str = "invalid_number") -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise RiskError(code)
    try:
        amount = Decimal(str(value))
    except InvalidOperation as error:
        raise RiskError(code) from error
    if (
        not amount.is_finite() or not ZERO <= amount <= Decimal("1000000000000")
        or len(amount.as_tuple().digits) > 32 or amount.as_tuple().exponent < -24
    ):
        raise RiskError(code)
    return amount.copy_abs()


def _text(amount: Decimal) -> str:
    text = format(amount, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _id(value, *, code: str = "invalid_identifier") -> str:
    if not isinstance(value, str) or not value or len(value) > 200 or value.strip() != value:
        raise RiskError(code)
    if any(character.isspace() or ord(character) < 32 for character in value):
        raise RiskError(code)
    return value


def _day(now: datetime | None) -> str:
    instant = datetime.now(timezone.utc) if now is None else now
    if not isinstance(instant, datetime) or instant.utcoffset() is None:
        raise RiskError("invalid_utc_clock")
    return instant.astimezone(timezone.utc).date().isoformat()


@dataclass(frozen=True)
class RiskPolicy:
    allowlist: frozenset[tuple[str, str]] = field(default_factory=frozenset)
    max_order_notional: Decimal = LIVE_MAX_ORDER_NOTIONAL
    max_total_exposure: Decimal = LIVE_MAX_TOTAL_EXPOSURE
    max_daily_risk: Decimal = LIVE_MAX_DAILY_RISK

    def __post_init__(self) -> None:
        pairs = set()
        for pair in self.allowlist:
            if not isinstance(pair, (tuple, list)) or len(pair) != 2:
                raise RiskError("invalid_allowlist")
            pairs.add((_id(pair[0], code="invalid_allowlist").lower(), _id(pair[1], code="invalid_allowlist")))
        object.__setattr__(self, "allowlist", frozenset(pairs))
        for name in ("max_order_notional", "max_total_exposure", "max_daily_risk"):
            value = _amount(getattr(self, name), code="invalid_policy_limit")
            if value <= ZERO:
                raise RiskError("invalid_policy_limit")
            object.__setattr__(self, name, value)

    def serialized_limits(self) -> str:
        return json.dumps({
            "max_order_notional": _text(self.max_order_notional),
            "max_total_exposure": _text(self.max_total_exposure),
            "max_daily_risk": _text(self.max_daily_risk),
        }, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class RiskOrder:
    client_id: str
    condition_id: str
    token: str
    price: Decimal
    size: Decimal
    state: str
    external_id: str | None
    filled_size: Decimal
    filled_notional: Decimal
    submitted_utc_day: str
    post_claimed: bool

    @property
    def remaining(self) -> Decimal:
        return self.size - self.filled_size


@dataclass(frozen=True)
class Reservation:
    order: RiskOrder
    should_post: bool


@dataclass(frozen=True)
class Cancellation:
    order: RiskOrder
    should_cancel: bool


def _order(row: sqlite3.Row) -> RiskOrder:
    return RiskOrder(
        client_id=row["client_id"], condition_id=row["condition_id"], token=row["token"],
        price=Decimal(row["price"]), size=Decimal(row["size"]), state=row["state"],
        external_id=row["external_id"], filled_size=Decimal(row["filled_size"]),
        filled_notional=Decimal(row["filled_notional"]),
        submitted_utc_day=row["submitted_utc_day"], post_claimed=bool(row["post_claimed"]),
    )


class RiskLedger:
    """SQLite ledger. All order and limit transitions are serialized on disk."""

    def __init__(
        self, path: Path | str, *, mode: str, policy: RiskPolicy, stop_file: Path | str,
    ) -> None:
        if mode not in ("dry", "live"):
            raise RiskError("invalid_mode")
        if not isinstance(policy, RiskPolicy):
            raise RiskError("invalid_policy")
        if mode == "live" and (
            policy.max_order_notional > LIVE_MAX_ORDER_NOTIONAL
            or policy.max_total_exposure > LIVE_MAX_TOTAL_EXPOSURE
            or policy.max_daily_risk > LIVE_MAX_DAILY_RISK
        ):
            raise RiskError("live_limit_ceiling")
        if str(path) == ":memory:":
            raise RiskError("durable_path_required")
        self._path = Path(path).absolute()
        self._mode = mode
        self._policy = policy
        self._stop_file = Path(stop_file).absolute()
        self._ledger_id = None
        self._policy_json = policy.serialized_limits()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(descriptor)
        except FileExistsError:
            pass
        except OSError as error:
            raise RiskError("storage_unavailable") from error

        with self._transaction(write=True, initializing=True) as db:
            db.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            db.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    client_id TEXT PRIMARY KEY, condition_id TEXT NOT NULL, token TEXT NOT NULL,
                    price TEXT NOT NULL, size TEXT NOT NULL, state TEXT NOT NULL,
                    external_id TEXT UNIQUE, filled_size TEXT NOT NULL, filled_notional TEXT NOT NULL,
                    submitted_utc_day TEXT NOT NULL, post_claimed INTEGER NOT NULL,
                    actual_fill_size TEXT NOT NULL, actual_fill_cost TEXT NOT NULL
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS settlements (
                    condition_id TEXT PRIMARY KEY,
                    payout_json TEXT NOT NULL, utc_day TEXT NOT NULL,
                    filled_cost TEXT NOT NULL, payout TEXT NOT NULL, realized_loss TEXT NOT NULL
                )
            """)
            metadata = dict(db.execute("SELECT key, value FROM metadata"))
            if not metadata:
                if db.execute("SELECT 1 FROM orders LIMIT 1").fetchone() or db.execute(
                    "SELECT 1 FROM settlements LIMIT 1"
                ).fetchone():
                    raise RiskError("ledger_identity_missing")
                metadata = {
                    "schema_version": SCHEMA_VERSION,
                    "mode": mode,
                    "policy": self._policy_json,
                    "ledger_id": uuid4().hex,
                    "latest_utc_day": "",
                }
                db.executemany("INSERT INTO metadata (key, value) VALUES (?, ?)", metadata.items())
            self._migrate_legacy_limits(db, metadata)
            self._validate_identity(metadata)
            self._ledger_id = metadata["ledger_id"]

    @property
    def path(self) -> Path:
        return self._path

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def policy(self) -> RiskPolicy:
        return self._policy

    @property
    def stop_file(self) -> Path:
        return self._stop_file

    @contextmanager
    def _transaction(self, *, write: bool = False, initializing: bool = False):
        db = None
        try:
            db = sqlite3.connect(f"{self.path.as_uri()}?mode=rw", uri=True, timeout=5, isolation_level=None)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            if not initializing:
                self._validate_identity(dict(db.execute("SELECT key, value FROM metadata")))
            with localcontext() as context:
                context.prec = 96
                yield db
            db.commit()
        except sqlite3.IntegrityError as error:
            raise RiskError("storage_conflict") from error
        except sqlite3.Error as error:
            raise RiskError("storage_unavailable") from error
        finally:
            if db is not None:
                db.close()

    def _migrate_legacy_limits(self, db: sqlite3.Connection, metadata: dict) -> None:
        prior = metadata.get("policy")
        if (
            prior == self._policy_json or metadata.get("schema_version") != SCHEMA_VERSION
            or metadata.get("mode") != self.mode or not metadata.get("ledger_id")
        ):
            return
        try:
            legacy = json.loads(prior, parse_float=Decimal)
            expected = json.loads(self._policy_json)
            if not isinstance(legacy, dict) or legacy.keys() != (expected.keys() | {"allowlist"}):
                return
            pairs = legacy["allowlist"]
            if not isinstance(pairs, list):
                return
            RiskPolicy(allowlist=pairs)
            if any(_amount(legacy[name]) != _amount(value) for name, value in expected.items()):
                return
        except (TypeError, ValueError, RiskError):
            return

        # The old policy persisted the allowlist as well as the money caps.
        # BEGIN IMMEDIATE protects this metadata-only upgrade and all checks.
        db.execute("UPDATE metadata SET value = ? WHERE key = 'policy'", (self._policy_json,))
        metadata["policy"] = self._policy_json

    def _validate_identity(self, metadata: dict) -> None:
        if metadata.get("schema_version") != SCHEMA_VERSION:
            raise RiskError("ledger_schema_mismatch")
        if metadata.get("mode") != self.mode:
            raise RiskError("ledger_mode_mismatch")
        if metadata.get("policy") != self._policy_json:
            raise RiskError("ledger_policy_mismatch")
        if (
            not metadata.get("ledger_id") or "latest_utc_day" not in metadata
            or (self._ledger_id is not None and metadata["ledger_id"] != self._ledger_id)
        ):
            raise RiskError("ledger_identity_mismatch")

    def _stop_present(self) -> bool:
        try:
            os.lstat(self.stop_file)
        except FileNotFoundError:
            return False
        except OSError as error:
            raise RiskError("stop_unreadable") from error
        return True

    @staticmethod
    def _row(db: sqlite3.Connection, client_id: str) -> sqlite3.Row:
        row = db.execute("SELECT * FROM orders WHERE client_id = ?", (_id(client_id),)).fetchone()
        if row is None:
            raise RiskError("unknown_client_id")
        return row

    @staticmethod
    def _advance_day(db: sqlite3.Connection, day: str) -> None:
        previous = db.execute("SELECT value FROM metadata WHERE key = 'latest_utc_day'").fetchone()[0]
        if previous > day:
            raise RiskError("clock_regressed")
        if previous < day:
            db.execute("UPDATE metadata SET value = ? WHERE key = 'latest_utc_day'", (day,))

    @staticmethod
    def _totals(db: sqlite3.Connection, day: str) -> tuple[Decimal, Decimal]:
        exposures = ZERO
        for row in db.execute("""
            SELECT orders.* FROM orders LEFT JOIN settlements USING (condition_id)
            WHERE settlements.condition_id IS NULL
        """):
            item = _order(row)
            exposures += item.filled_notional
            if item.state not in TERMINAL:
                exposures += item.remaining * item.price
        spent = sum(
            (Decimal(row[0]) for row in db.execute(
                "SELECT realized_loss FROM settlements WHERE utc_day = ?", (day,)
            )),
            ZERO,
        )
        return exposures, spent

    def get(self, client_id: str) -> RiskOrder:
        with self._transaction() as db:
            return _order(self._row(db, client_id))

    def reserve(
        self, client_id: str, condition_id: str, token: str, price, size, *,
        tick_size, min_size, now: datetime | None = None, external_exposure_clear: bool = False,
    ) -> Reservation:
        client_id, condition_id, token = _id(client_id), _id(condition_id).lower(), _id(token)
        price, size = _amount(price), _amount(size)
        with self._transaction(write=True) as db:
            row = db.execute("SELECT * FROM orders WHERE client_id = ?", (client_id,)).fetchone()
            if row is not None:
                existing = _order(row)
                if (existing.condition_id, existing.token, existing.price, existing.size) != (
                    condition_id, token, price, size
                ):
                    raise RiskError("client_id_conflict")
                return Reservation(existing, False)

            if self._stop_present():
                raise RiskError("stop_active")
            if self.mode == "live" and external_exposure_clear is not True:
                raise RiskError("unmanaged_external_exposure")
            if (condition_id, token) not in self.policy.allowlist:
                raise RiskError("not_allowlisted")
            tick = _amount(tick_size, code="invalid_price_tick")
            minimum = _amount(min_size, code="invalid_order_size")
            if not ZERO < price < ONE or not ZERO < tick < ONE or price % tick:
                raise RiskError("invalid_price_tick")
            if not ZERO < minimum <= size:
                raise RiskError("invalid_order_size")
            if db.execute("SELECT 1 FROM settlements WHERE condition_id = ?", (condition_id,)).fetchone():
                raise RiskError("market_settled")

            day = _day(now)
            self._advance_day(db, day)
            spend = price * size
            committed, realized = self._totals(db, day)
            if spend > self.policy.max_order_notional:
                raise RiskError("order_limit")
            if self.mode == "live" and committed > ZERO:
                raise RiskError("live_outstanding_exposure")
            if committed + spend > self.policy.max_total_exposure:
                raise RiskError("aggregate_limit")
            if realized + committed + spend > self.policy.max_daily_risk:
                raise RiskError("daily_limit")

            db.execute("""
                INSERT INTO orders (
                    client_id, condition_id, token, price, size, state, external_id, filled_size,
                    filled_notional, submitted_utc_day, post_claimed, actual_fill_size, actual_fill_cost
                ) VALUES (?, ?, ?, ?, ?, 'reserved', NULL, '0', '0', ?, 0, '0', '0')
            """, (client_id, condition_id, token, _text(price), _text(size), day))
            return Reservation(_order(self._row(db, client_id)), True)

    def assert_post_allowed(self, client_id: str) -> RiskOrder:
        """Claim the sole post attempt, durably, immediately before dispatch."""
        with self._transaction(write=True) as db:
            item = _order(self._row(db, client_id))
            if item.state != "reserved" or item.post_claimed:
                raise RiskError("post_already_claimed")
            if self._stop_present():
                raise RiskError("stop_active")
            if (item.condition_id, item.token) not in self.policy.allowlist:
                raise RiskError("not_allowlisted")
            db.execute("UPDATE orders SET post_claimed = 1 WHERE client_id = ?", (item.client_id,))
            return _order(self._row(db, client_id))

    def reject_unsent(self, client_id: str) -> RiskOrder:
        """Release a reservation only before any dispatcher has claimed it."""
        with self._transaction(write=True) as db:
            item = _order(self._row(db, client_id))
            if item.post_claimed or item.external_id is not None:
                raise RiskError("post_may_have_been_sent")
            if item.state == "rejected":
                return item
            if item.state != "reserved":
                raise RiskError("invalid_post_transition")
            db.execute("UPDATE orders SET state = 'rejected' WHERE client_id = ?", (item.client_id,))
            return _order(self._row(db, client_id))

    @staticmethod
    def _external_id(db: sqlite3.Connection, item: RiskOrder, supplied: str | None) -> str | None:
        if supplied is None:
            return item.external_id
        supplied = _id(supplied)
        if item.external_id is not None and item.external_id != supplied:
            raise RiskError("external_id_conflict")
        row = db.execute("SELECT client_id FROM orders WHERE external_id = ?", (supplied,)).fetchone()
        if row is not None and row[0] != item.client_id:
            raise RiskError("external_id_conflict")
        return supplied

    def bind_accepted(self, client_id: str, external_id: str) -> RiskOrder:
        with self._transaction(write=True) as db:
            item = _order(self._row(db, client_id))
            accepted = self._external_id(db, item, _id(external_id))
            if item.external_id == accepted:
                return item
            if item.state not in ("reserved", "post_unknown") or not item.post_claimed:
                raise RiskError("invalid_post_transition")
            db.execute(
                "UPDATE orders SET state = 'open', external_id = ? WHERE client_id = ?",
                (accepted, item.client_id),
            )
            return _order(self._row(db, client_id))

    def mark_unknown(self, client_id: str, *, action: str) -> RiskOrder:
        if action not in ("post", "cancel"):
            raise RiskError("invalid_action")
        uncertain = "post_unknown" if action == "post" else "cancel_unknown"
        previous = "reserved" if action == "post" else "cancel_pending"
        with self._transaction(write=True) as db:
            item = _order(self._row(db, client_id))
            if item.state == uncertain:
                return item
            if item.state != previous or (action == "post" and not item.post_claimed):
                raise RiskError("invalid_unknown_transition")
            db.execute("UPDATE orders SET state = ? WHERE client_id = ?", (uncertain, item.client_id))
            return _order(self._row(db, client_id))

    def request_cancel(self, client_id: str) -> Cancellation:
        with self._transaction(write=True) as db:
            item = _order(self._row(db, client_id))
            if item.state != "open" or item.external_id is None:
                return Cancellation(item, False)
            db.execute("UPDATE orders SET state = 'cancel_pending' WHERE client_id = ?", (item.client_id,))
            return Cancellation(_order(self._row(db, client_id)), True)

    def reconcile(
        self, client_id: str, *, status: str, filled_size, filled_notional=None,
        external_id: str | None = None, verified: bool = False, reopen_cancel: bool = False,
    ) -> RiskOrder:
        """Apply trusted cumulative exchange state. Release only on definitive evidence.

        A missing order alone cannot prove rejection. An explicit later cancel
        may rearm a prior ambiguous cancellation on a fresh, verified open GET.
        """
        if verified is not True:
            raise RiskError("unverified_exchange_state")
        if status not in {"open", *TERMINAL} or (reopen_cancel is True and status != "open"):
            raise RiskError("invalid_exchange_state")
        filled = _amount(filled_size, code="invalid_fill")
        with self._transaction(write=True) as db:
            row = self._row(db, client_id)
            item = _order(row)
            bound = self._external_id(db, item, external_id)
            if status != "rejected" and bound is None:
                raise RiskError("missing_external_id")
            if (
                not item.filled_size <= filled <= item.size
                or (status == "filled" and filled != item.size)
                or (status == "open" and filled >= item.size)
                or (status == "rejected" and filled != ZERO)
            ):
                raise RiskError("invalid_fill")
            actual_size, actual_cost = Decimal(row["actual_fill_size"]), Decimal(row["actual_fill_cost"])
            if filled_notional is None:
                estimate = actual_cost + (filled - actual_size) * item.price
            else:
                estimate = _amount(filled_notional, code="invalid_fill_cost")
                if (
                    not actual_cost <= estimate <= actual_cost + (filled - actual_size) * item.price
                    or (filled > actual_size and estimate == actual_cost)
                ):
                    raise RiskError("invalid_fill_cost")
                actual_size, actual_cost = filled, estimate

            if item.state in TERMINAL:
                if (item.state, item.filled_size, item.filled_notional, item.external_id) == (
                    status, filled, estimate, bound
                ):
                    return item
                raise RiskError("terminal_state_conflict")
            if (
                status == "open" and item.state in ("cancel_pending", "cancel_unknown")
                and reopen_cancel is not True
            ):
                status = item.state

            db.execute("""
                UPDATE orders SET state = ?, external_id = ?, filled_size = ?, filled_notional = ?,
                    actual_fill_size = ?, actual_fill_cost = ? WHERE client_id = ?
            """, (
                status, bound, _text(filled), _text(estimate), _text(actual_size), _text(actual_cost),
                item.client_id,
            ))
            return _order(self._row(db, client_id))

    def settle_market(
        self, condition_id: str, payouts_by_token: dict, *,
        verified: bool = False, now: datetime | None = None,
    ) -> dict:
        """Close a binary market once all order reservations have definitive outcomes."""
        if verified is not True:
            raise RiskError("unverified_settlement")
        condition_id = _id(condition_id).lower()
        if not isinstance(payouts_by_token, dict) or len(payouts_by_token) != 2:
            raise RiskError("invalid_payout")
        payouts = {
            _id(token, code="invalid_payout"): _amount(value, code="invalid_payout")
            for token, value in payouts_by_token.items()
        }
        with self._transaction(write=True) as db:
            if any(value > ONE for value in payouts.values()) or sum(payouts.values()) != ONE:
                raise RiskError("invalid_payout")
            payout_json = json.dumps({token: _text(value) for token, value in payouts.items()}, sort_keys=True)
            previous = db.execute(
                "SELECT * FROM settlements WHERE condition_id = ?", (condition_id,)
            ).fetchone()
            if previous is not None:
                if previous["payout_json"] != payout_json:
                    raise RiskError("settlement_conflict")
                return self._settlement_record(previous)

            items = [
                _order(row) for row in db.execute("SELECT * FROM orders WHERE condition_id = ?", (condition_id,))
            ]
            if not items:
                raise RiskError("unknown_condition")
            if any(item.state not in TERMINAL for item in items):
                raise RiskError("unresolved_order")
            if any(item.token not in payouts for item in items):
                raise RiskError("invalid_payout")
            day = _day(now)
            self._advance_day(db, day)
            cost = sum((item.filled_notional for item in items), ZERO)
            payout = sum((item.filled_size * payouts[item.token] for item in items), ZERO)
            loss = max(ZERO, cost - payout)
            db.execute(
                "INSERT INTO settlements VALUES (?, ?, ?, ?, ?, ?)",
                (condition_id, payout_json, day, _text(cost), _text(payout), _text(loss)),
            )
            row = db.execute(
                "SELECT * FROM settlements WHERE condition_id = ?", (condition_id,)
            ).fetchone()
            return self._settlement_record(row)

    @staticmethod
    def _settlement_record(row: sqlite3.Row) -> dict:
        return {
            key: row[key] for key in ("condition_id", "utc_day", "filled_cost", "payout", "realized_loss")
        }

    def status(self, *, now: datetime | None = None) -> dict:
        day = _day(now)
        with self._transaction() as db:
            exposure, realized = self._totals(db, day)
            counts = dict(db.execute("SELECT state, COUNT(*) FROM orders GROUP BY state"))
            return {
                "mode": self.mode, "utc_day": day, "stop_file_present": self._stop_present(),
                "committed_exposure": _text(exposure), "realized_loss_today": _text(realized),
                "daily_at_risk": _text(exposure + realized),
                "available_daily_budget": _text(max(ZERO, self.policy.max_daily_risk - exposure - realized)),
                "counts": counts,
            }
