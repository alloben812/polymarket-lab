from decimal import Decimal

import pytest

from live import orders
from live.order_risk import RiskLedger, RiskPolicy
from live.orders import (
    DRY_CONDITION,
    DRY_TOKEN,
    DryVenue,
    OrderError,
    canary,
    cancel_known,
)


def setup(tmp_path, identity="test-canary"):
    ledger = RiskLedger(
        tmp_path / "test.sqlite3",
        mode="dry",
        policy=RiskPolicy(allowlist={(DRY_CONDITION, DRY_TOKEN)}),
        stop_file=tmp_path / "STOP",
    )
    venue = DryVenue(identity, Decimal(".05"), Decimal("5"))
    terms = (identity, DRY_CONDITION, DRY_TOKEN, venue.price, venue.size)
    return ledger, venue, terms


def test_default_cli_does_not_open_a_connection_or_import_private_sdk(
    tmp_path, monkeypatch, capsys
):
    import json
    import socket
    import sys

    monkeypatch.setattr(orders, "DRY_ROOT", tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("dry run touched a network or credential")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setitem(sys.modules, "live.order_sdk", None)
    monkeypatch.setattr(sys, "argv", ["orders"])
    orders.main()
    result = json.loads(capsys.readouterr().out)
    assert (result["mode"], result["state"], result["filled_size"]) == (
        "dry",
        "cancelled",
        "0",
    )
    assert Decimal(result["at_risk"]) == 0


def test_lost_post_response_never_reposts_on_retry_or_releases_reserve(tmp_path):
    ledger, venue, terms = setup(tmp_path)
    calls = []

    def unknown(*args, before_send, **kwargs):
        before_send()
        calls.append("post")
        raise TimeoutError("private transport detail")

    venue.submit_post_only = unknown
    with pytest.raises(OrderError, match="submission_unconfirmed"):
        canary(ledger, venue, *terms)
    with pytest.raises(OrderError, match="submission_unknown"):
        canary(ledger, venue, *terms)
    assert calls == ["post"]
    assert ledger.get(terms[0]).state == "post_unknown"
    assert Decimal(ledger.status()["committed_exposure"]) == Decimal(".25")


def test_stop_after_quote_before_post_releases_only_unsent_claim(tmp_path):
    ledger, venue, terms = setup(tmp_path)

    def stopped(*args, before_send, **kwargs):
        (tmp_path / "STOP").touch()
        before_send()
        pytest.fail("should not post")

    venue.submit_post_only = stopped
    with pytest.raises(OrderError, match="cancelled_before_submission"):
        canary(ledger, venue, *terms)
    assert ledger.get(terms[0]).state == "rejected"
    assert Decimal(ledger.status()["committed_exposure"]) == 0


def test_cancel_ack_alone_cannot_release_risk_and_recovery_can_cancel_with_stop(
    tmp_path,
):
    ledger, venue, terms = setup(tmp_path)
    original_lookup = venue.get_order

    def unknown(*args, **kwargs):
        raise TimeoutError("private transport detail")

    venue.get_order = unknown
    with pytest.raises(OrderError, match="cancellation_unconfirmed"):
        canary(ledger, venue, *terms)
    assert Decimal(ledger.status()["committed_exposure"]) == Decimal(".25")
    venue.get_order = original_lookup
    (tmp_path / "STOP").touch()
    assert cancel_known(ledger, venue, terms[0]).state == "cancelled"
    assert Decimal(ledger.status()["committed_exposure"]) == 0


def test_close_to_market_is_refused_before_any_private_call(tmp_path):
    ledger, venue, terms = setup(tmp_path)
    with pytest.raises(OrderError, match="too_near"):
        canary(ledger, venue, *terms[:3], Decimal(".48"), Decimal("5"))
    assert ledger.status()["counts"] == {}


def test_partial_cancellation_holds_entire_order_until_final_fill_is_confirmed(
    tmp_path,
):
    from dataclasses import replace

    ledger, venue, terms = setup(tmp_path)
    lookup = venue.get_order

    def pending(*args, **kwargs):
        return replace(
            lookup(*args, **kwargs), filled=Decimal(1), settlement_final=False
        )

    venue.get_order = pending
    with pytest.raises(OrderError, match="cancellation_unconfirmed"):
        canary(ledger, venue, *terms)
    assert Decimal(ledger.status()["committed_exposure"]) == Decimal(".25")
    venue.get_order = lambda *a, **kw: replace(lookup(*a, **kw), filled=Decimal(1))
    assert cancel_known(ledger, venue, terms[0]).filled_size == 1
    assert Decimal(ledger.status()["committed_exposure"]) == Decimal(".05")


def test_definitive_rejection_releases_only_when_sdk_recognizes_server_reply(tmp_path):
    from live.order_sdk import OrderError as SdkError

    ledger, venue, terms = setup(tmp_path)

    def rejected(*args, before_send, **kwargs):
        before_send()
        raise SdkError("order_rejected")

    venue.submit_post_only = rejected
    assert canary(ledger, venue, *terms).state == "rejected"
    assert Decimal(ledger.status()["committed_exposure"]) == 0
