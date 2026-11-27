from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace as NS
from unittest.mock import Mock, call

import pytest

from live import order_sdk as sdk


TOKEN = "101"
CONDITION = "0x" + "11" * 32
ORDER_ID = "0x" + "22" * 32
WALLET = "0x" + "33" * 20
TIME = 1_795_811_300
PRIVATE_NOISE = "private-mock-noise"
BOOK = sdk.PublicBook(
    TOKEN,
    CONDITION,
    Decimal(".53"),
    Decimal(".54"),
    Decimal(5),
    Decimal(".01"),
    TIME * 1000,
)


def page(items=(), cursor=None, *, limit=False):
    return NS(
        items=items,
        limit_reached=limit,
        has_more=cursor is not None,
        next_cursor=cursor,
    )


def clear_client():
    client = Mock(wallet=WALLET)
    client.get_closed_only_mode.return_value = False
    client.list_wallet_open_orders.return_value = [page()]
    client.list_positions.return_value = [page()]
    client.list_activity.return_value = [page()]
    client.list_account_trades.return_value = [page()]
    return client


def write_fake_secret(path):
    path.write_text(
        json.dumps(
            {
                "session_private_key": "00" * 32,
                "session_signer": "0x" + "44" * 20,
                "deposit_wallet": WALLET,
                "api_key": "fake-key",
                "api_secret": "fake-secret",
                "api_passphrase": "fake-passphrase",
            }
        )
    )
    path.chmod(0o600)


def test_reads_only_private_owned_regular_files(tmp_path, monkeypatch):
    root = tmp_path.resolve()
    plain = root / "private"
    write_fake_secret(plain)
    assert sdk._read_credentials(plain)["api_key"] == "fake-key"

    symlink = root / "key-link"
    symlink.symlink_to(plain)
    folder_link = root / "folder-link"
    folder_link.symlink_to(root, target_is_directory=True)
    fifo = root / "pipe"
    os.mkfifo(fifo, 0o600)
    for rejected in (symlink, folder_link / "private", fifo, root, Path("relative")):
        with pytest.raises(sdk.OrderError, match="credential_file"):
            sdk._read_credentials(rejected)
    link = root / "hard-link"
    link.hardlink_to(plain)
    with pytest.raises(sdk.OrderError, match="credential_file"):
        sdk._read_credentials(plain)
    link.unlink()
    sibling = root / "sibling"
    sibling.mkdir()
    (sibling / ".git").write_text("gitdir: synthetic worktree")
    git_key = sibling / "private"
    write_fake_secret(git_key)
    with pytest.raises(sdk.OrderError, match="credential_file"):
        sdk._read_credentials(git_key)
    plain.chmod(0o640)
    with pytest.raises(sdk.OrderError, match="credential_file"):
        sdk._read_credentials(plain)
    plain.chmod(0o600)
    monkeypatch.setattr(sdk, "_REPO", root)
    with pytest.raises(sdk.OrderError, match="credential_file"):
        sdk._read_credentials(plain)


def test_wrong_owner_and_bad_content_are_redacted(tmp_path, monkeypatch):
    secret = tmp_path.resolve() / PRIVATE_NOISE
    write_fake_secret(secret)
    uid = os.geteuid()
    with monkeypatch.context() as patch:
        patch.setattr(sdk.os, "geteuid", lambda: uid + 1)
        with pytest.raises(sdk.OrderError) as caught:
            sdk._read_credentials(secret)
    assert str(caught.value) == "credential_file"
    secret.write_text(PRIVATE_NOISE)
    with pytest.raises(sdk.OrderError) as caught:
        sdk._read_credentials(secret)
    assert str(caught.value) == "credential_file"


def book_model(**changes):
    return NS(
        asset_id=TOKEN,
        condition_id=CONDITION,
        min_order_size=Decimal(5),
        tick_size=Decimal(".01"),
        timestamp=datetime.fromtimestamp(TIME, timezone.utc),
        bids=[NS(price=Decimal(".51"), size=12), NS(price=Decimal(".53"), size=5)],
        asks=[NS(price=Decimal(".60"), size=8), NS(price=Decimal(".54"), size=5)],
        **{
            key: value
            for key, value in changes.items()
            if key
            not in {
                "asset_id",
                "condition_id",
                "min_order_size",
                "tick_size",
                "timestamp",
                "bids",
                "asks",
            }
        },
    )


def test_sdk_book_parses_valid_public_metadata(monkeypatch):
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=None)
    client.get_order_book.return_value = book_model()
    monkeypatch.setitem(
        sys.modules, "polymarket", NS(PublicClient=Mock(return_value=client))
    )
    monkeypatch.setattr(sdk.time, "time_ns", lambda: TIME * 1_000_000_000)
    assert sdk._public_book(TOKEN, CONDITION) == BOOK
    client.get_order_book.assert_called_once_with(asset_id=TOKEN)


@pytest.mark.parametrize(
    "attribute,value",
    [
        ("asset_id", "202"),
        ("condition_id", "0x" + "44" * 32),
        ("min_order_size", 0),
        ("tick_size", 0),
        ("timestamp", None),
        ("timestamp", datetime.fromtimestamp(TIME - 11, timezone.utc)),
        ("asks", []),
        ("bids", [NS(price=Decimal(".60"), size=5)]),
    ],
)
def test_public_book_refuses_uncertain_identity_limits_or_freshness(
    monkeypatch, attribute, value
):
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=None)
    book = book_model()
    setattr(book, attribute, value)
    client.get_order_book.return_value = book
    monkeypatch.setitem(
        sys.modules, "polymarket", NS(PublicClient=Mock(return_value=client))
    )
    monkeypatch.setattr(sdk.time, "time_ns", lambda: TIME * 1_000_000_000)
    with pytest.raises(sdk.OrderError, match="book_unavailable"):
        sdk._public_book(TOKEN, CONDITION)


def test_public_checks_never_receive_a_key_path_and_invalid_order_stops_before_sdk(
    monkeypatch,
):
    invoke = Mock(
        return_value={
            "token": TOKEN,
            "condition_id": CONDITION,
            "best_bid": ".53",
            "best_ask": ".54",
            "min_size": "5",
            "tick_size": ".01",
            "timestamp_ms": TIME * 1000,
        }
    )
    monkeypatch.setattr(sdk, "_invoke", invoke)
    monkeypatch.setattr(
        sdk, "_public_json", lambda _: {"blocked": False, "ip": PRIVATE_NOISE}
    )
    adapter = sdk.OrderSDK(Path("/") / PRIVATE_NOISE)
    assert adapter.geo_allowed() is True
    assert adapter.verify_book(TOKEN, CONDITION) == BOOK
    invoke.assert_called_once_with(
        None, {"operation": "book", "token": TOKEN, "condition_id": CONDITION}
    )
    for price, size in [(".54", "5"), (".535", "5"), (".53", "4"), (".53", "5.005")]:
        invoke.reset_mock()
        with pytest.raises(sdk.OrderError, match="invalid_order"):
            adapter.submit_post_only(
                TOKEN, price, size, condition_id=CONDITION, before_send=lambda: None
            )
        assert all(call.args[0] is None for call in invoke.call_args_list)


def test_geoblock_requires_a_boolean_and_redacts_transport_errors(monkeypatch):
    monkeypatch.setattr(
        sdk, "_public_json", lambda _: {"blocked": True, "ip": PRIVATE_NOISE}
    )
    assert sdk.geo_allowed() is False
    monkeypatch.setattr(sdk, "_public_json", Mock(side_effect=OSError(PRIVATE_NOISE)))
    with pytest.raises(sdk.OrderError, match="^geo_unavailable$"):
        sdk.geo_allowed()
    monkeypatch.setattr(sdk, "_public_json", lambda _: {"blocked": "false"})
    with pytest.raises(sdk.OrderError, match="^geo_unavailable$"):
        sdk.geo_allowed()


def test_account_check_traverses_all_signers_and_pages():
    client = clear_client()
    sdk._clear_wallet(client)
    client.list_wallet_open_orders.assert_called_once_with()
    assert client.list_positions.call_args_list == [
        call(user=WALLET, include_archived=True, full_history=True),
        call(user=WALLET, status="CLOSED", full_history=True),
    ]

    client.list_positions.return_value = [
        page((), "second"),
        page((NS(wallet=WALLET, current_size="0.01"),)),
    ]
    with pytest.raises(sdk.OrderError, match="account_nonempty"):
        sdk._clear_wallet(client)

    client.list_wallet_open_orders.return_value = [page((), "second"), page((NS(),))]
    with pytest.raises(sdk.OrderError, match="account_nonempty"):
        sdk._clear_wallet(client)


@pytest.mark.parametrize("orders", [[page(limit=True)], [page((), "unfinished")], []])
def test_incomplete_account_check_fails_closed(orders):
    client = clear_client()
    client.list_wallet_open_orders.return_value = orders
    with pytest.raises(sdk.OrderError, match="account_check_unavailable"):
        sdk._clear_wallet(client)


def request(operation="submit", **extra):
    return {
        "operation": operation,
        "token": TOKEN,
        "condition_id": CONDITION,
        "price": ".53",
        "size": "5",
        **extra,
    }


def test_prepare_post_only_gtd_then_only_post_after_worker_permission(monkeypatch):
    client = clear_client()
    client.create_limit_order.return_value = NS(
        side="BUY",
        post_only=True,
        order_type="GTD",
        expiration=TIME + 185,
        token_id=TOKEN,
        signature_type=3,
        maker=WALLET,
        taker_amount=5_000_000,
        maker_amount=2_650_000,
    )
    client.post_order.return_value = NS(ok=True, status="live", order_id=ORDER_ID)
    monkeypatch.setattr(sdk, "_public_book", Mock(return_value=BOOK))
    monkeypatch.setattr(sdk.time, "time", lambda: TIME)
    gate = sdk._NetworkGate()
    stream = BytesIO(b'{"event":"send"}\n')
    monkeypatch.setattr(sdk, "_write", Mock())
    assert sdk._worker_action(client, gate, stream, request()) == ORDER_ID
    client.create_limit_order.assert_called_once_with(
        asset_id=TOKEN,
        side="BUY",
        price=Decimal(".53"),
        size=Decimal(5),
        post_only=True,
        expiration=TIME + 185,
    )
    sdk._write.assert_called_once_with(stream, {"event": "ready"})
    client.post_order.assert_called_once_with(client.create_limit_order.return_value)
    assert gate.mutation == "POST"

    client.post_order.reset_mock()
    with pytest.raises(sdk.OrderError, match="permission_denied"):
        sdk._worker_action(
            client, sdk._NetworkGate(), BytesIO(b'{"event":"deny"}\n'), request()
        )
    client.post_order.assert_not_called()

    client.post_order.side_effect = OSError(PRIVATE_NOISE)
    with pytest.raises(sdk.OrderUncertain, match="^order_uncertain$"):
        sdk._worker_action(
            client, sdk._NetworkGate(), BytesIO(b'{"event":"send"}\n'), request()
        )


def test_worker_egress_allows_only_the_single_approved_mutation():
    gate = sdk._NetworkGate()
    gate.allow("GET", "https", "clob.polymarket.com", "/book", None)
    for method, host, path in [
        ("POST", "clob.polymarket.com", "/auth/api-key"),
        ("POST", "relayer-v2.polymarket.com", "/submit"),
        ("GET", "unknown.example", "/book"),
        ("POST", "clob.polymarket.com", "/order"),
    ]:
        with pytest.raises(sdk.OrderError):
            gate.allow(method, "https", host, path, None)
    gate.mutation = "POST"
    with pytest.raises(sdk.OrderError):
        gate.allow("GET", "https", "clob.polymarket.com", "/book", None)
    gate.allow("POST", "https", "clob.polymarket.com", "/order", None)
    with pytest.raises(sdk.OrderError):
        gate.allow("POST", "https", "clob.polymarket.com", "/order", None)


def order_model(**changes):
    return NS(
        **{
            "id": ORDER_ID,
            "asset_id": TOKEN,
            "condition_id": CONDITION,
            "maker_address": WALLET,
            "side": "BUY",
            "order_type": "GTD",
            "expires_at": datetime.fromtimestamp(TIME + 185, timezone.utc),
            "price": Decimal(".53"),
            "original_size": Decimal(5),
            "size_matched": Decimal(0),
            "status": "LIVE",
            **changes,
        }
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("condition_id", "another"),
        ("asset_id", "another"),
        ("side", "SELL"),
        ("maker_address", "another"),
        ("original_size", "6"),
        ("price", ".54"),
        ("size_matched", "6"),
        ("status", "UNKNOWN"),
        ("status", "MATCHED"),
        ("order_type", "GTC"),
    ],
)
def test_get_order_refuses_to_reconcile_wrong_or_indeterminate_state(field, value):
    client = clear_client()
    client.get_order.return_value = order_model(**{field: value})
    with pytest.raises(sdk.OrderUncertain, match="^order_uncertain$"):
        sdk._order_snapshot(client, request("get", order_id=ORDER_ID))


def test_partial_cancel_preserves_matched_quantity_and_needs_confirmation():
    client = clear_client()
    client.get_order.return_value = order_model(status="CANCELED", size_matched=2)
    args = request("get", order_id=ORDER_ID)
    state = sdk._order_snapshot(client, args)
    assert (
        state["status"],
        state["filled"],
        state["terminal"],
        state["settlement_final"],
    ) == ("cancelled", "2", True, False)
    maker = NS(
        order_id=ORDER_ID,
        asset_id=TOKEN,
        maker_address=WALLET,
        side="BUY",
        price=".53",
        matched_amount=2,
    )
    trade = NS(
        id="mock-trade",
        condition_id=CONDITION,
        status="CONFIRMED",
        maker_orders=(maker,),
    )
    client.list_account_trades.return_value = [page((trade,))]
    assert sdk._order_snapshot(client, args)["settlement_final"] is True


def test_cancel_ack_is_not_an_order_snapshot():
    client = clear_client()
    client.cancel_order.return_value = NS(canceled=(ORDER_ID,), not_canceled={})
    assert (
        sdk._worker_action(
            client, sdk._NetworkGate(), BytesIO(), request("cancel", order_id=ORDER_ID)
        )
        is None
    )
    client.cancel_order.return_value = NS(
        canceled=(), not_canceled={ORDER_ID: PRIVATE_NOISE}
    )
    with pytest.raises(sdk.OrderUncertain, match="^order_uncertain$"):
        sdk._worker_action(
            client, sdk._NetworkGate(), BytesIO(), request("cancel", order_id=ORDER_ID)
        )


def test_mock_worker_cannot_leak_stdout_or_send_after_callback_denial(
    tmp_path, monkeypatch, capfd
):
    executable = tmp_path / "mock_worker.py"
    executable.write_text(f"""
import json, os, socket, sys
from pathlib import Path
with socket.socket(fileno=int(sys.argv[-1])) as sock, sock.makefile("rwb") as wire:
    request = json.loads(wire.readline())
    print({PRIVATE_NOISE!r}, flush=True)
    os.write(2, {PRIVATE_NOISE.encode()!r})
    wire.write(b'{{"event":"ready"}}\\n')
    wire.flush()
    if wire.readline() == b'{{"event":"send"}}\\n':
        Path(request["key_file"]).touch()
        wire.write(b'{{"event":"ok","result":"{ORDER_ID}"}}\\n')
        wire.flush()
""")
    monkeypatch.setattr(sdk, "__file__", str(executable))
    marker = tmp_path / "fake-post"
    with pytest.raises(ValueError, match="deny"):
        sdk._invoke(
            marker, request(), lambda: (_ for _ in ()).throw(ValueError("deny"))
        )
    assert not marker.exists()
    assert sdk._invoke(marker, request(), lambda: None) == ORDER_ID
    assert marker.exists()
    assert PRIVATE_NOISE not in "".join(capfd.readouterr())


def test_flat_wallet_with_activity_or_unproven_history_is_blocked(monkeypatch):
    monkeypatch.setattr(sdk.time, "time", lambda: TIME)
    midnight = TIME // 86_400 * 86_400
    at = datetime.fromtimestamp(TIME - 1, timezone.utc)
    yesterday = datetime.fromtimestamp(midnight - 1, timezone.utc)
    client = clear_client()
    client.list_positions.return_value = [
        page((NS(wallet=WALLET, current_size=0, last_event_at=yesterday),))
    ]
    client.list_activity.return_value = [
        page((), "next"),
        page((NS(wallet=WALLET, timestamp=at, type="DEPOSIT", amount="5"),)),
    ]
    sdk._clear_wallet(client)
    client.list_activity.assert_called_once_with(user=WALLET, start=midnight)
    client.list_account_trades.assert_called_once_with(after=str(midnight))

    for event_type in ("TRADE", "REDEEM", "WITHDRAWAL", "unknown"):
        client.list_activity.return_value = [
            page((NS(wallet=WALLET, timestamp=at, type=event_type),))
        ]
        with pytest.raises(sdk.OrderError, match="account_nonempty"):
            sdk._clear_wallet(client)
    client.list_activity.return_value = [page()]
    client.list_positions.return_value = [
        page((NS(wallet=WALLET, current_size=0, last_event_at=at),))
    ]
    with pytest.raises(sdk.OrderError, match="account_nonempty"):
        sdk._clear_wallet(client)
    client.list_positions.return_value = [
        page((NS(wallet=WALLET, current_size=0, last_event_at=None),))
    ]
    with pytest.raises(sdk.OrderError, match="account_check_unavailable"):
        sdk._clear_wallet(client)
    client.list_positions.return_value = [page()]
    client.list_account_trades.return_value = [page((NS(),))]
    with pytest.raises(sdk.OrderError, match="account_nonempty"):
        sdk._clear_wallet(client)


@pytest.mark.parametrize("order_status", ["CANCELED", "CANCELED_MARKET_RESOLVED"])
def test_pinned_models_parse_real_wire_aliases_without_credentials(order_status):
    pytest.importorskip("polymarket")
    from importlib.metadata import version

    from polymarket.models.clob.account import ClobTrade, OpenOrder

    assert version("polymarket-client") == sdk.SDK_VERSION
    order = OpenOrder.parse_response(
        {
            "id": ORDER_ID,
            "market": CONDITION,
            "asset_id": TOKEN,
            "owner": "mock",
            "maker_address": WALLET,
            "side": "BUY",
            "price": ".53",
            "original_size": "5",
            "size_matched": "2",
            "outcome": "Up",
            "order_type": "GTD",
            "status": order_status,
            "created_at": TIME,
            "expiration": str(TIME + 185),
        }
    )
    trade = ClobTrade.parse_response(
        {
            "id": "mock-trade",
            "market": CONDITION,
            "asset_id": TOKEN,
            "owner": "mock",
            "maker_address": WALLET,
            "taker_order_id": "0x" + "77" * 32,
            "side": "SELL",
            "trader_side": "MAKER",
            "price": ".53",
            "size": "2",
            "outcome": "Up",
            "status": "TRADE_STATUS_CONFIRMED",
            "fee_rate_bps": "0",
            "bucket_index": 0,
            "match_time": str(TIME + 1),
            "last_update": str(TIME + 2),
            "maker_orders": [
                {
                    "order_id": ORDER_ID,
                    "asset_id": TOKEN,
                    "maker_address": WALLET,
                    "owner": "mock",
                    "side": "BUY",
                    "price": ".53",
                    "matched_amount": "2",
                    "outcome": "Up",
                }
            ],
        }
    )
    client = clear_client()
    client.get_order.return_value = order
    client.list_account_trades.return_value = [page((trade,))]
    state = sdk._order_snapshot(client, request("get", order_id=ORDER_ID))
    assert state["status"] == "cancelled"
    assert state["filled"] == "2"
    assert state["settlement_final"] is True
