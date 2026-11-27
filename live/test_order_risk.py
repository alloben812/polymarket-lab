import json
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from threading import Barrier

import pytest

from live.order_risk import RiskError, RiskLedger, RiskPolicy


D = Decimal
DAY_ONE = datetime(2026, 11, 27, 23, 59, 58, tzinfo=timezone.utc)
DAY_TWO = DAY_ONE + timedelta(seconds=5)
PAIRS = {("0xabc", "up"), ("0xabc", "down"), ("0xdef", "other")}


def ledger(tmp_path, *, mode="dry", name="risk.sqlite", **policy):
    return RiskLedger(
        tmp_path / name, mode=mode, stop_file=tmp_path / "STOP",
        policy=RiskPolicy(allowlist=PAIRS, **policy),
    )


def reserve(item, client_id="request", **fields):
    return item.reserve(client_id, **{
        "condition_id": "0xABC", "token": "up", "price": ".20", "size": "5",
        "tick_size": ".01", "min_size": "1", "now": DAY_ONE,
        **fields,
    })


def accepted(item, client_id="request", external_id="exchange-1", **fields):
    assert reserve(item, client_id, **fields).should_post
    assert item.assert_post_allowed(client_id).post_claimed
    return item.bind_accepted(client_id, external_id)


def test_allowlist_validates_pair_and_market_limits(tmp_path):
    item = ledger(tmp_path)
    with pytest.raises(RiskError, match="not_allowlisted"):
        reserve(item, token="other")
    with pytest.raises(RiskError, match="not_allowlisted"):
        reserve(item, condition_id="0xunknown")
    with pytest.raises(RiskError, match="invalid_price_tick"):
        reserve(item, price=".215")
    with pytest.raises(RiskError, match="invalid_price_tick"):
        reserve(item, price="1")
    with pytest.raises(RiskError, match="invalid_number"):
        reserve(item, price="NaN")
    with pytest.raises(RiskError, match="invalid_number"):
        reserve(item, size="Infinity")
    with pytest.raises(RiskError, match="invalid_order_size"):
        reserve(item, size="4", min_size="5")
    with pytest.raises(RiskError, match="order_limit"):
        reserve(item, size="5.00001")
    result = reserve(item, "valid")
    assert result.order.token == "up"
    assert result.order.condition_id == "0xabc"
    assert result.order.price == D(".2")
    assert result.order.size == D("5")
    assert result.order.remaining == D("5")


def test_mode_and_policy_persist_and_live_hard_caps_cannot_be_raised(tmp_path):
    dry = ledger(tmp_path, max_order_notional="3", max_total_exposure="9", max_daily_risk="7")
    reserve(dry, size="12")
    with pytest.raises(RiskError, match="ledger_mode_mismatch"):
        ledger(tmp_path, mode="live")
    with pytest.raises(RiskError, match="ledger_policy_mismatch"):
        ledger(tmp_path)
    for policy in ({"max_order_notional": "1.01"}, {"max_total_exposure": "5.01"}, {"max_daily_risk": "2.01"}):
        with pytest.raises(RiskError, match="live_limit_ceiling"):
            ledger(tmp_path, mode="live", name="live.sqlite", **policy)
    live_gate = ledger(tmp_path, mode="live", name="live.sqlite")
    with pytest.raises(RiskError, match="unmanaged_external_exposure"):
        reserve(live_gate)
    assert live_gate.status(now=DAY_ONE)["committed_exposure"] == "0"
    assert dry.status(now=DAY_ONE)["committed_exposure"] == "2.4"
    with pytest.raises(RiskError, match="ledger_mode_mismatch"):
        ledger(tmp_path, name="live.sqlite")


def test_stop_blocks_reserve_and_final_claim_but_cancellation_still_works(tmp_path):
    item = ledger(tmp_path)
    accepted(item, "known")
    reserve(item, "unclaimed")
    (tmp_path / "STOP").touch()
    assert item.status(now=DAY_ONE)["stop_file_present"] is True
    with pytest.raises(RiskError, match="stop_active"):
        reserve(item, "new")
    with pytest.raises(RiskError, match="stop_active"):
        item.assert_post_allowed("unclaimed")
    assert item.reject_unsent("unclaimed").state == "rejected"
    assert item.reject_unsent("unclaimed").state == "rejected"
    chosen = item.request_cancel("known")
    assert chosen.should_cancel and chosen.order.external_id == "exchange-1"
    assert item.status(now=DAY_ONE)["committed_exposure"] == "1"


def test_dangling_stop_sentinel_blocks_placements(tmp_path):
    item = ledger(tmp_path)
    (tmp_path / "STOP").symlink_to("missing")
    with pytest.raises(RiskError, match="stop_active"):
        reserve(item)


def test_retry_and_restart_never_authorize_post_twice(tmp_path):
    item = ledger(tmp_path)
    assert reserve(item).should_post is True
    assert item.assert_post_allowed("request").post_claimed
    with pytest.raises(RiskError, match="post_may_have_been_sent"):
        item.reject_unsent("request")
    assert item.mark_unknown("request", action="post").state == "post_unknown"
    restarted = ledger(tmp_path)
    assert reserve(restarted, price="0.2000").should_post is False
    with pytest.raises(RiskError, match="post_already_claimed"):
        restarted.assert_post_allowed("request")
    with pytest.raises(RiskError, match="client_id_conflict"):
        reserve(restarted, price=".19")
    assert restarted.request_cancel("request").should_cancel is False
    with pytest.raises(RiskError, match="unknown_client_id"):
        restarted.get("other")
    with pytest.raises(RiskError, match="unverified_exchange_state"):
        restarted.reconcile("request", status="rejected", filled_size=0)
    assert restarted.status(now=DAY_ONE)["daily_at_risk"] == "1"
    assert restarted.reconcile("request", status="rejected", filled_size=0, verified=True).state == "rejected"
    assert restarted.status(now=DAY_ONE)["daily_at_risk"] == "0"


def test_partial_fill_and_ambiguous_cancel_keep_correct_reserve(tmp_path):
    item = ledger(tmp_path)
    accepted(item)
    part = item.reconcile("request", status="open", filled_size="2", filled_notional=".36", verified=True)
    assert part.filled_size == D("2") and part.filled_notional == D(".36")
    assert item.status(now=DAY_ONE)["committed_exposure"] == "0.96"
    assert item.request_cancel("request").should_cancel
    assert item.mark_unknown("request", action="cancel").state == "cancel_unknown"
    restarted = ledger(tmp_path)
    snapshot = restarted.reconcile("request", status="open", filled_size="3", verified=True)
    assert snapshot.state == "cancel_unknown"
    assert snapshot.filled_notional == D(".56")
    assert restarted.request_cancel("request").should_cancel is False
    assert restarted.status(now=DAY_ONE)["committed_exposure"] == "0.96"
    with pytest.raises(RiskError, match="external_id_conflict"):
        restarted.reconcile("request", status="cancelled", filled_size=3, external_id="other", verified=True)
    with pytest.raises(RiskError, match="invalid_fill"):
        restarted.reconcile("request", status="cancelled", filled_size=2, verified=True)
    final = restarted.reconcile("request", status="cancelled", filled_size=3, filled_notional=".55", verified=True)
    assert final.filled_notional == D(".55")
    assert restarted.status(now=DAY_ONE)["committed_exposure"] == "0.55"
    assert restarted.reconcile("request", status="cancelled", filled_size=3, verified=True) == final
    with pytest.raises(RiskError, match="terminal_state_conflict"):
        restarted.reconcile("request", status="open", filled_size=3, verified=True, reopen_cancel=True)


def test_new_manual_cancel_requires_positive_open_confirmation(tmp_path):
    item = ledger(tmp_path)
    accepted(item)
    assert item.request_cancel("request").should_cancel
    item.mark_unknown("request", action="cancel")
    assert item.request_cancel("request").should_cancel is False
    checked = item.reconcile(
        "request", status="open", filled_size=0, external_id="exchange-1", verified=True, reopen_cancel=True,
    )
    assert checked.state == "open"
    assert item.request_cancel("request").should_cancel
    assert item.request_cancel("request").should_cancel is False


def test_aggregate_cap_counts_reserved_unknown_and_filled_orders(tmp_path):
    item = ledger(tmp_path, max_total_exposure="1.5", max_daily_risk="5")
    accepted(item, "first")
    item.reconcile("first", status="filled", filled_size=5, verified=True)
    reserve(item, "second", price=".10")
    item.assert_post_allowed("second")
    item.mark_unknown("second", action="post")
    assert item.status(now=DAY_ONE)["committed_exposure"] == "1.5"
    with pytest.raises(RiskError, match="aggregate_limit"):
        reserve(item, "third", price=".01")
    with pytest.raises(RiskError, match="unresolved_order"):
        item.settle_market("0xabc", {"up": 0, "down": 1}, verified=True, now=DAY_ONE)


def test_realized_loss_is_once_per_utc_day_and_exposure_survives_rollover(tmp_path):
    item = ledger(tmp_path)
    accepted(item, "losing", price=".15")
    item.reconcile("losing", status="filled", filled_size=5, filled_notional=".74", verified=True)
    accepted(item, "held", external_id="exchange-2", condition_id="0xdef", token="other", price=".15")
    settlement = item.settle_market("0xabc", {"up": 0, "down": 1}, verified=True, now=DAY_ONE)
    assert settlement["realized_loss"] == "0.74"
    assert item.status(now=DAY_ONE)["daily_at_risk"] == "1.49"
    with pytest.raises(RiskError, match="daily_limit"):
        reserve(item, "over", condition_id="0xdef", token="other", price=".15")
    with pytest.raises(RiskError, match="market_settled"):
        reserve(item, "closed")
    reopened = ledger(tmp_path)
    assert reopened.settle_market("0xabc", {"up": "0.0", "down": "1.0"}, verified=True, now=DAY_TWO) == settlement
    assert reopened.status(now=DAY_TWO)["daily_at_risk"] == "0.75"
    assert reopened.status(now=DAY_ONE)["realized_loss_today"] == "0.74"
    assert reserve(reopened, "next", condition_id="0xdef", token="other", now=DAY_TWO).should_post
    with pytest.raises(RiskError, match="clock_regressed"):
        reserve(reopened, "clock", condition_id="0xdef", token="other", now=DAY_ONE)
    assert reopened.request_cancel("held").should_cancel
    assert reopened.status(now=DAY_TWO)["committed_exposure"] == "1.75"
    json.dumps(reopened.status(now=DAY_TWO))


def test_settlement_requires_verified_binary_payout_and_stable_cumulative_amounts(tmp_path):
    item = ledger(tmp_path)
    accepted(item)
    with pytest.raises(RiskError, match="invalid_fill_cost"):
        item.reconcile("request", status="open", filled_size=2, filled_notional=".41", verified=True)
    item.reconcile("request", status="filled", filled_size=5, filled_notional=".90", verified=True)
    with pytest.raises(RiskError, match="unverified_settlement"):
        item.settle_market("0xabc", {"up": 1, "down": 0}, now=DAY_ONE)
    with pytest.raises(RiskError, match="invalid_payout"):
        item.settle_market("0xabc", {"up": 1, "down": 1}, verified=True, now=DAY_ONE)
    closed = item.settle_market("0xabc", {"up": ".5", "down": ".5"}, verified=True, now=DAY_ONE)
    assert closed["payout"] == "2.5"
    assert closed["realized_loss"] == "0"
    assert item.status(now=DAY_ONE)["committed_exposure"] == "0"
    with pytest.raises(RiskError, match="settlement_conflict"):
        item.settle_market("0xabc", {"up": 0, "down": 1}, verified=True, now=DAY_ONE)


def test_sqlite_serializes_concurrent_reservations_and_single_post_claim(tmp_path):
    first = ledger(tmp_path, max_total_exposure="1", max_daily_risk="3")
    second = ledger(tmp_path, max_total_exposure="1", max_daily_risk="3")

    def race(action, left, right):
        barrier = Barrier(2)

        def run(item, identifier):
            barrier.wait(timeout=2)
            try:
                return action(item, identifier)
            except RiskError as error:
                return error.code

        with ThreadPoolExecutor(max_workers=2) as workers:
            a = workers.submit(run, first, left)
            b = workers.submit(run, second, right)
            return [a.result(), b.result()]

    results = race(lambda item, identifier: reserve(item, identifier).should_post, "same", "same")
    assert sorted(results) == [False, True]
    results = race(lambda item, identifier: item.assert_post_allowed(identifier).post_claimed, "same", "same")
    assert results.count(True) == results.count("post_already_claimed") == 1
    results = race(lambda item, identifier: reserve(item, identifier).should_post, "new1", "new2")
    assert results == ["aggregate_limit", "aggregate_limit"]


def test_unclaimed_rejection_and_claim_are_atomic(tmp_path):
    item = ledger(tmp_path)
    reserve(item)
    item.reject_unsent("request")
    with pytest.raises(RiskError, match="post_already_claimed"):
        item.assert_post_allowed("request")
    assert reserve(item).should_post is False
    assert item.status(now=DAY_ONE)["committed_exposure"] == "0"


def test_allowlist_rotation_leaves_status_and_cancel_available_under_stop(tmp_path):
    original = ledger(tmp_path)
    accepted(original, "open")
    reserve(original, "unclaimed")
    reopened = RiskLedger(
        original.path, mode="dry", policy=RiskPolicy(), stop_file=original.stop_file,
    )
    with pytest.raises(RiskError, match="not_allowlisted"):
        reopened.assert_post_allowed("unclaimed")
    with pytest.raises(RiskError, match="not_allowlisted"):
        reserve(reopened, "new")
    reopened.stop_file.touch()
    assert reopened.status(now=DAY_ONE)["stop_file_present"]
    assert reopened.get("open").external_id == "exchange-1"
    assert reopened.request_cancel("open").should_cancel
    assert reopened.reject_unsent("unclaimed").state == "rejected"


def test_live_canary_allows_only_one_outstanding_reservation_or_position(tmp_path):
    first = ledger(tmp_path, mode="live")
    second = ledger(tmp_path, mode="live")
    barrier = Barrier(2)

    def worker(item, identifier):
        barrier.wait(timeout=2)
        try:
            return reserve(item, identifier, external_exposure_clear=True)
        except RiskError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as workers:
        a = workers.submit(worker, first, "one")
        b = workers.submit(worker, second, "two")
        outcomes = [a.result(), b.result()]
    assert outcomes.count("live_outstanding_exposure") == 1
    chosen = next(result.order.client_id for result in outcomes if not isinstance(result, str))
    first.assert_post_allowed(chosen)
    first.bind_accepted(chosen, "exchange-1")
    first.request_cancel(chosen)
    first.reconcile(chosen, status="cancelled", filled_size="1", verified=True)
    with pytest.raises(RiskError, match="live_outstanding_exposure"):
        reserve(second, "after-partial", external_exposure_clear=True)
    first.settle_market("0xabc", {"up": 1, "down": 0}, verified=True, now=DAY_ONE)
    assert reserve(
        second, "after-settlement", condition_id="0xdef", token="other", external_exposure_clear=True,
    ).should_post


def test_dry_cli_migrates_only_legacy_allowlist_metadata(tmp_path, monkeypatch, capsys):
    from live import orders

    item = ledger(tmp_path, name="orders.sqlite3")
    accepted(item, "partially-filled")
    item.reconcile("partially-filled", status="open", filled_size="2", filled_notional=".36", verified=True)
    accepted(item, "closed", external_id="exchange-2", condition_id="0xdef", token="other", price=".10")
    item.reconcile("closed", status="filled", filled_size="5", verified=True)
    item.settle_market("0xdef", {"other": 0, "counterpart": 1}, verified=True, now=DAY_ONE)
    legacy = json.loads(item.policy.serialized_limits())
    legacy["allowlist"] = sorted(PAIRS)
    old_encoded = json.dumps(legacy, sort_keys=True, separators=(",", ":"))
    with sqlite3.connect(item.path) as db:
        db.execute("UPDATE metadata SET value = ? WHERE key = 'policy'", (old_encoded,))
        before_meta = dict(db.execute("SELECT key, value FROM metadata"))
        before_orders = db.execute("SELECT * FROM orders ORDER BY client_id").fetchall()
        before_settlements = db.execute("SELECT * FROM settlements").fetchall()

    monkeypatch.setattr(orders, "DRY_ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["orders", "status"])
    orders.main()
    status = json.loads(capsys.readouterr().out)
    assert status["mode"] == "dry" and status["committed_exposure"] == "0.96"
    assert status["counts"] == {"filled": 1, "open": 1}
    with sqlite3.connect(item.path) as db:
        after_meta = dict(db.execute("SELECT key, value FROM metadata"))
        assert after_meta == {**before_meta, "policy": item.policy.serialized_limits()}
        assert db.execute("SELECT * FROM orders ORDER BY client_id").fetchall() == before_orders
        assert db.execute("SELECT * FROM settlements").fetchall() == before_settlements


@pytest.mark.parametrize("change", [{"max_daily_risk": "2.000000001"}, {"anything_else": "ignored?"}])
def test_legacy_metadata_does_not_migrate_if_policy_also_changed(tmp_path, change):
    item = ledger(tmp_path)
    legacy = json.loads(item.policy.serialized_limits())
    legacy.update({"allowlist": sorted(PAIRS), **change})
    encoded = json.dumps(legacy)
    with sqlite3.connect(item.path) as db:
        db.execute("UPDATE metadata SET value = ? WHERE key = 'policy'", (encoded,))
    with pytest.raises(RiskError, match="ledger_policy_mismatch"):
        ledger(tmp_path)
    with sqlite3.connect(item.path) as db:
        assert db.execute("SELECT value FROM metadata WHERE key = 'policy'").fetchone()[0] == encoded
