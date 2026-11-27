"""Owner-attended post-only canary. The default execution path is local and dry."""

import argparse
from dataclasses import dataclass
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
from uuid import uuid4

from .order_risk import RiskError, RiskLedger, RiskPolicy


DRY_CONDITION = "0x" + "11" * 32
DRY_TOKEN = "101"
DRY_ROOT = Path(__file__).resolve().parents[1] / "data/live/orders"
LIVE_ROOT = Path.home() / ".local/state/polymarket-lab/canary"
LIVE_ALLOWLIST = LIVE_ROOT / "allowlist.json"


class OrderError(Exception):
    """Only fixed, public error codes reach the console."""


@dataclass(frozen=True)
class DryBook:
    best_bid: Decimal = Decimal("0.49")
    best_ask: Decimal = Decimal("0.51")
    min_size: Decimal = Decimal("5")
    tick_size: Decimal = Decimal("0.01")


@dataclass(frozen=True)
class DryOrderState:
    order_id: str
    token: str
    condition_id: str
    price: Decimal
    size: Decimal
    filled: Decimal
    status: str
    terminal: bool
    settlement_final: bool
    side: str = "BUY"


class DryVenue:
    """No signer, wallet or transport. The database holds the simulated lifecycle."""

    def __init__(self, client_id, price, size):
        self.id = "0x" + hashlib.sha256(("dry/" + client_id).encode()).hexdigest()
        self.price = price
        self.size = size
        self.cancelled = False

    def geo_allowed(self):
        return True

    def assert_clear_for_canary(self):
        pass

    def verify_book(self, token, condition_id):
        if (condition_id, token) != (DRY_CONDITION, DRY_TOKEN):
            raise OrderError("dry_fixture_unknown_market")
        return DryBook()

    def submit_post_only(self, token, price, size, *, condition_id, before_send):
        before_send()
        return self.id

    def cancel(self, order_id):
        if order_id != self.id:
            raise OrderError("unknown_dry_order")
        self.cancelled = True

    def get_order(self, order_id, *, token, condition_id, price, size):
        if self.id != order_id:
            raise OrderError("unknown_dry_order")
        return DryOrderState(
            self.id,
            token,
            condition_id,
            self.price,
            self.size,
            Decimal(0),
            "cancelled" if self.cancelled else "open",
            self.cancelled,
            self.cancelled,
        )


def check_book(book, price, size):
    if not price.is_finite() or not size.is_finite() or not 0 < price < 1 or size <= 0:
        raise OrderError("invalid_price_or_size")
    if book.tick_size <= 0 or price % book.tick_size or size < book.min_size:
        raise OrderError("invalid_tick_or_minimum")
    if (
        book.best_bid is None
        or book.best_ask is None
        or not 0 < book.best_bid < book.best_ask <= 1
    ):
        raise OrderError("no_two_sided_book")
    # This command is exclusively a distant post-only buy-and-cancel canary.
    if book.best_bid - price < max(Decimal("0.05"), 5 * book.tick_size):
        raise OrderError("canary_too_near_market")


def reconcile(ledger, venue, order, *, reopen_cancel=False):
    seen = venue.get_order(
        order.external_id,
        token=order.token,
        condition_id=order.condition_id,
        price=order.price,
        size=order.size,
    )
    if (
        seen.order_id != order.external_id
        or seen.token != order.token
        or seen.condition_id != order.condition_id
        or seen.side != "BUY"
        or seen.size != order.size
        or seen.price != order.price
    ):
        raise OrderError("exchange_order_terms_disagree")
    if seen.terminal and seen.settlement_final is not True:
        raise OrderError("exchange_settlement_unconfirmed")
    if seen.status not in {"open", "filled", "cancelled", "rejected"} or (
        seen.terminal != (seen.status != "open")
    ):
        raise OrderError("unconfirmed_exchange_state")
    ledger.reconcile(
        order.client_id,
        status=seen.status,
        filled_size=seen.filled,
        external_id=order.external_id,
        verified=True,
        reopen_cancel=reopen_cancel and seen.status == "open",
    )
    return ledger.get(order.client_id)


def cancel_known(ledger, venue, client_id):
    order = ledger.get(client_id)
    if order is None:
        raise OrderError("unknown_request")
    if order.state in {"cancelled", "filled", "rejected"}:
        return order
    if not order.external_id:
        raise OrderError("submission_unknown_reservation_retained")
    for attempt_number in range(2):
        attempt = ledger.request_cancel(client_id)
        if attempt.should_cancel:
            try:
                venue.cancel(order.external_id)
            except BaseException:
                ledger.mark_unknown(client_id, action="cancel")
        try:
            order = reconcile(ledger, venue, order, reopen_cancel=attempt_number == 0)
        except Exception:
            ledger.mark_unknown(client_id, action="cancel")
            raise OrderError("cancellation_unconfirmed_reservation_retained") from None
        if order.state in {"cancelled", "filled", "rejected"}:
            return order
    raise OrderError("order_still_open_reservation_retained")


def lookup(ledger, client_id):
    try:
        return ledger.get(client_id)
    except RiskError as error:
        if error.code != "unknown_client_id":
            raise
        return None


def canary(ledger, venue, client_id, condition, token, price, size):
    # A retry may only inspect or cancel its own earlier order.
    old = lookup(ledger, client_id)
    if old is not None:
        if (condition, token, price, size) != (
            old.condition_id,
            old.token,
            old.price,
            old.size,
        ):
            raise OrderError("request_id_reused_with_different_terms")
        return cancel_known(ledger, venue, client_id)
    if (condition.lower(), token) not in ledger.policy.allowlist:
        raise OrderError("market_not_allowlisted")
    if venue.geo_allowed() is not True:
        raise OrderError("geoblock_or_unverified_location")
    book = venue.verify_book(token, condition)
    check_book(book, price, size)
    venue.assert_clear_for_canary()
    claim = ledger.reserve(
        client_id,
        condition,
        token,
        price,
        size,
        tick_size=book.tick_size,
        min_size=book.min_size,
        external_exposure_clear=True,
    )
    if not claim.should_post:
        return cancel_known(ledger, venue, client_id)

    post_claimed = False

    def before_send():
        nonlocal post_claimed
        check_book(venue.verify_book(token, condition), price, size)
        if (
            ledger.mode == "live"
            and (condition.lower(), token) not in load_live_allowlist()
        ):
            raise OrderError("market_not_allowlisted")
        ledger.assert_post_allowed(client_id)
        post_claimed = True

    try:
        external_id = venue.submit_post_only(
            token, price, size, condition_id=condition, before_send=before_send
        )
    except BaseException as error:
        if not post_claimed:
            ledger.reject_unsent(client_id)
            raise OrderError("cancelled_before_submission") from None
        if getattr(error, "code", None) == "order_rejected":
            from .order_sdk import OrderError as SdkError

            if isinstance(error, SdkError):
                return ledger.reconcile(
                    client_id, status="rejected", filled_size=0, verified=True
                )
        ledger.mark_unknown(client_id, action="post")
        raise OrderError("submission_unconfirmed_reservation_retained") from None
    try:
        ledger.bind_accepted(client_id, external_id)
    except BaseException:
        # We know the remote ID. Attempt to remove our own canary even on disk failure.
        try:
            venue.cancel(external_id)
        except BaseException:
            pass
        raise OrderError("remote_order_requires_owner_reconciliation") from None
    return cancel_known(ledger, venue, client_id)


def load_live_allowlist():
    fd = os.open(LIVE_ALLOWLIST, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "r") as config:
        meta = os.fstat(config.fileno())
        if (
            not stat.S_ISREG(meta.st_mode)
            or meta.st_uid != os.getuid()
            or meta.st_mode & 0o077
        ):
            raise OrderError("allowlist_must_be_owner_controlled")
        entries = json.load(config)
    if not isinstance(entries, list):
        raise OrderError("invalid_allowlist")
    return {(item["condition_id"].lower(), item["token"]) for item in entries}


def owner_present(args):
    if not (sys.stdin.isatty() and sys.stderr.isatty()):
        raise OrderError("owner_terminal_required")
    if args.cmd == "cancel":
        confirm = f"CANCEL {args.request_id}"
    else:
        confirm = f"BUY {args.size} @ {args.price} {args.condition} {args.token}"
    print("Подтвердите параметры в локальном терминале:", file=sys.stderr)
    print(confirm, file=sys.stderr)
    if input().strip() != confirm:
        raise OrderError("owner_confirmation_mismatch")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "cmd", nargs="?", choices=["canary", "cancel", "status"], default="canary"
    )
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--key-file", type=Path)
    parser.add_argument("--condition")
    parser.add_argument("--token")
    parser.add_argument("--price", type=Decimal)
    parser.add_argument("--size", type=Decimal)
    parser.add_argument("--request-id")
    args = parser.parse_args()
    try:
        if args.live:
            root = LIVE_ROOT
            if args.cmd == "status":
                pairs = set()
            elif args.cmd == "cancel":
                pairs = set()
            else:
                pairs = load_live_allowlist()
            if args.cmd != "status":
                if not args.key_file or not args.request_id:
                    raise OrderError("live_action_requires_key_file_and_request_id")
                if args.cmd == "canary" and any(
                    item is None
                    for item in (args.condition, args.token, args.price, args.size)
                ):
                    raise OrderError("live_canary_requires_all_owner_parameters")
                owner_present(args)
        else:
            root = DRY_ROOT
            if args.key_file:
                raise OrderError("dry_mode_has_no_credentials")
            pairs = {(DRY_CONDITION, DRY_TOKEN)}
            if args.cmd == "cancel" and not args.request_id:
                raise OrderError("cancel_requires_request_id")
            args.condition = DRY_CONDITION if args.condition is None else args.condition
            args.token = DRY_TOKEN if args.token is None else args.token
            args.price = Decimal("0.05") if args.price is None else args.price
            args.size = Decimal("5") if args.size is None else args.size
            args.request_id = args.request_id or uuid4().hex

        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if args.live:
            meta = root.lstat()
            if (
                not stat.S_ISDIR(meta.st_mode)
                or meta.st_uid != os.getuid()
                or meta.st_mode & 0o077
            ):
                raise OrderError("live_state_directory_must_be_private")
        ledger = RiskLedger(
            root / "orders.sqlite3",
            mode="live" if args.live else "dry",
            policy=RiskPolicy(allowlist=pairs),
            stop_file=root / "STOP",
        )
        if args.cmd == "status":
            print(json.dumps(ledger.status(), sort_keys=True))
            return
        if args.live:
            from .order_sdk import OrderSDK

            venue = OrderSDK(args.key_file)
        else:
            old = lookup(ledger, args.request_id)
            venue = DryVenue(
                args.request_id,
                old.price if old else args.price,
                old.size if old else args.size,
            )
        order = (
            cancel_known(ledger, venue, args.request_id)
            if args.cmd == "cancel"
            else canary(
                ledger,
                venue,
                args.request_id,
                args.condition,
                args.token,
                args.price,
                args.size,
            )
        )
        print(
            json.dumps(
                {
                    "mode": "live" if args.live else "dry",
                    "request_id": order.client_id,
                    "state": order.state,
                    "filled_size": str(order.filled_size),
                    "at_risk": ledger.status()["committed_exposure"],
                },
                sort_keys=True,
            )
        )
    except (RiskError, OrderError) as err:
        code = err.code if isinstance(err, RiskError) else str(err)
        parser.exit(2, f"{code}\n")
    except Exception:
        parser.exit(2, "order_check_failed\n")


if __name__ == "__main__":
    main()
