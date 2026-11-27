import json
from decimal import Decimal

import pytest

from live.book import BookReplay
from live.execution import MS, PaperExecution
from pmlab.fees import taker_fee


D = Decimal
BASE_MS = 1_795_800_000_000


class Replay:
    def __init__(self, **params):
        self.book = BookReplay()
        self.exec = PaperExecution(**params)
        self.ordinal = 0

    def row(self, ms, kind="ws", session="s", **fields):
        self.ordinal += 1
        row = {
            "kind": kind, "session": session, "recv_ns": (BASE_MS + ms) * MS,
            "ordinal": self.ordinal, **fields,
        }
        self.book.apply(row)
        return row, self.exec.observe(row, self.book)

    def book_row(self, ms, *, bid="0.40", ask="0.55", size="20", token="up",
                 exchange=None, extras=(), source="websocket"):
        return self.row(ms, source=source, payload={
            "event_type": "book", "asset_id": token,
            "timestamp": str(BASE_MS + (ms if exchange is None else exchange)),
            "bids": [{"price": bid, "size": size}],
            "asks": [{"price": price, "size": amount} for price, amount in ((ask, size), *extras)],
        })

    def trade_row(
        self, ms, *, side="SELL", price="0.45", size="8", token="up", exchange=None,
        tx_hash=None,
    ):
        return self.row(ms, payload={
            "event_type": "last_trade_price", "asset_id": token,
            "timestamp": str(BASE_MS + (ms if exchange is None else exchange)),
            "side": side, "price": price, "size": size, "transaction_hash": tx_hash,
        })[1]

    def market(self):
        return self.row(0, "market", market={
            "slug": "btc5", "condition_id": "0xbtc",
            "tokens": {"Up": "up", "Down": "down"},
            "end_ts": BASE_MS // 1000 + 180,
        })

    def resolve(self, ms, payouts, **fields):
        return self.row(ms, "resolution", **{
            "slug": "btc5", "source": "gamma", "condition_id": "0xbtc",
            "payouts": payouts, **fields,
        })

    def intent(self, row, **fields):
        intent = {
            "token": "up", "slug": "btc5", "outcome": "Up", "side": "BUY",
            "style": "taker", "price": "0.60", "size": "10", "fee_rate": "0.05",
            "min_size": "5", "tick_size": "0.01", "end_ts": BASE_MS // 1000 + 180,
            **fields,
        }
        return self.exec.submit(intent, row, self.book)


def fills(records):
    return [record for record in records if record["kind"] == "fill"]


def test_taker_waits_once_and_walks_only_real_allowed_depth():
    r = Replay()
    signal, _ = r.book_row(10, ask="0.53")
    submitted = r.intent(signal, size="14")[0]
    assert submitted["kind"] == "submitted"
    assert submitted["ready_ns"] == signal["recv_ns"] + 1000 * MS
    _, before = r.book_row(1009, ask="0.52")
    assert before == []
    row, events = r.book_row(1010, ask="0.54", size="3", extras=(("0.56", "4"), ("0.61", "10")))
    observed = fills(events)
    assert [(D(fill["price"]), D(fill["size"])) for fill in observed] == [
        (D("0.54"), D("3")), (D("0.56"), D("4")),
    ]
    assert [D(fill["fee"]) for fill in observed] == [
        D(str(taker_fee(3, 0.54, 0.05))), D(str(taker_fee(4, 0.56, 0.05))),
    ]
    assert events[-1]["reason"] == "ioc_remainder"
    assert observed[0]["intent_id"] == submitted["intent_id"]
    assert observed[0]["signal_ordinal"] == signal["ordinal"]
    assert observed[0]["signal_recv_ns"] == signal["recv_ns"]
    assert observed[0]["evidence_ordinal"] == row["ordinal"]
    assert observed[0]["book_source"] == "websocket"
    assert r.book_row(1030, ask="0.50")[1] == []
    json.dumps(observed, allow_nan=False)


def test_old_exchange_snapshot_and_rest_checkpoint_cannot_execute_a_taker():
    r = Replay(max_book_age_ms=300, max_taker_wait_ms=500)
    signal, _ = r.book_row(10)
    r.intent(signal)
    assert r.book_row(1010, exchange=900)[1] == []
    assert r.book_row(1020, source="rest_checkpoint")[1] == []
    assert r.row(1100, "heartbeat", status="pong")[1] == []
    assert r.book_row(1511)[1][0]["reason"] == "arrival_not_observed"

    r2 = Replay(max_book_age_ms=100)
    signal, _ = r2.book_row(10)
    reference, _ = r2.row(120, "reference")
    assert r2.intent(reference)[0]["reason"] == "book_unavailable_or_stale"
    assert r2.intent(signal)[0]["kind"] == "submitted"


def test_liquidity_is_shared_and_absolute_size_does_not_refill_it():
    r = Replay(latency_ms=1)
    submit_row, _ = r.book_row(1, size="10")
    r.intent(submit_row, size="6", fee_rate="0")
    r.intent(submit_row, size="6", fee_rate="0")
    row, events = r.book_row(2, size="10")
    assert [D(fill["size"]) for fill in fills(events)] == [D("6"), D("4")]
    r.intent(row, size="5", fee_rate="0")
    row, events = r.book_row(3, size="10")
    assert fills(events) == []
    r.intent(row, size="5", fee_rate="0")
    _, events = r.book_row(4, size="13")
    assert [D(fill["size"]) for fill in fills(events)] == [D("3")]


def test_passive_requires_fresh_opposite_print_through_limit_and_consumes_it_once():
    r = Replay(latency_ms=1000)
    signal, _ = r.book_row(10, ask="0.60")
    r.intent(signal, style="passive", price="0.50", size="5")
    r.intent(signal, style="passive", price="0.50", size="5")
    assert r.trade_row(1010) == []
    assert [event["kind"] for event in r.book_row(1020, ask="0.60")[1]] == ["resting", "resting"]
    assert r.trade_row(1021, price="0.50") == []
    assert r.trade_row(1022, price="0.45", side="BUY") == []
    assert r.trade_row(1023, exchange=1019) == []
    events = r.trade_row(1030, exchange=1030, size="7")
    assert [(D(fill["price"]), D(fill["size"]), D(fill["fee"])) for fill in fills(events)] == [
        (D("0.50"), D("5"), D("0")), (D("0.50"), D("2"), D("0")),
    ]
    assert events[0]["observed_price"] == "0.45"
    assert r.trade_row(1031, exchange=1030, size="7") == []
    assert r.trade_row(1040, exchange=1040, size="4")[0]["size"] == "3"


def test_outage_and_expiry_close_orders_and_late_gap_labels_previous_fill():
    r = Replay(latency_ms=10)
    signal, _ = r.book_row(1)
    r.intent(signal, fee_rate="0")
    _, events = r.book_row(11)
    filled = fills(events)[0]
    signal, _ = r.book_row(12)
    r.intent(signal)
    _, events = r.row(
        15, "gap", tokens=["up"], since_ns=(BASE_MS + 5) * MS, reason="missing_data",
    )
    assert any(e["kind"] == "fill_tainted" and e["fill_id"] == filled["fill_id"] for e in events)
    assert any(e["kind"] == "closed" and e["reason"] == "gap" for e in events)
    assert fills(r.book_row(30)[1]) == []

    signal, _ = r.book_row(980)
    r.intent(signal, end_ts=BASE_MS // 1000 + 180, price="0.50", style="passive")
    assert r.book_row(990, ask="0.60")[1][0]["kind"] == "resting"
    assert not fills(r.trade_row(1600, exchange=989))
    assert not fills(r.trade_row(180_000))
    assert not fills(r.trade_row(180_010))


def test_cash_and_long_inventory_protect_partial_fills_and_settlement():
    r = Replay(initial_cash="4", latency_ms=10)
    r.market()
    row, _ = r.book_row(1, ask="0.50")
    denied = r.intent(row, side="SELL")
    assert denied[0]["reason"] == "insufficient_position"
    accepted = r.intent(row, fee_rate="0", size="10", price="0.50")
    assert D(accepted[0]["size"]) == D("8")
    assert r.intent(row, fee_rate="0", size="10")[0]["reason"] == "insufficient_cash"
    row, events = r.book_row(11, ask="0.50")
    assert [D(fill["size"]) for fill in fills(events)] == [D("8")]
    assert r.exec.cash == D("0")

    r.intent(row, side="SELL", price="0.39", size="6", fee_rate="0")
    assert r.intent(row, side="SELL", price="0.39", size="5", fee_rate="0")[0]["reason"] == "insufficient_position"
    _, events = r.book_row(21, ask="0.50")
    assert fills(events)[0]["size"] == "6"
    assert r.exec.cash == D("2.40")
    payouts = {"Up": "0.75", "Down": "0.25"}
    assert r.resolve(179_999, payouts)[1] == []
    assert r.resolve(180_000, payouts, source="untrusted")[1] == []
    assert r.resolve(180_001, payouts, condition_id="0xother")[1] == []
    assert r.resolve(180_002, {"Up": 1})[1] == []
    assert r.resolve(180_003, {"Up": "0.75", "Other": "0.25"})[1] == []
    _, [settlement] = r.resolve(180_004, payouts)
    assert D(settlement["gross"]) == D("3.9")
    assert D(settlement["payout"]) == D("1.5")
    assert D(settlement["cost"]) == D("4")
    assert D(settlement["net"]) == D("-0.1")
    assert r.exec.cash == D("3.9")
    assert r.resolve(180_005, {"Up": "1", "Down": "0"})[1] == []


def test_research_caps_per_intent_and_across_both_outcomes():
    r = Replay(initial_cash="1000", latency_ms=1)
    r.market()
    events = []
    order_ms = 1
    for idx in range(5):
        token = "up" if idx % 2 == 0 else "down"
        outcome = token.capitalize()
        row, _ = r.book_row(order_ms, ask="0.55", size="1", token=token)
        submitted = r.intent(row, token=token, outcome=outcome, size="150")[0]
        assert submitted["size"] == "100"
        row, lifecycle = r.book_row(order_ms + 1, ask="0.55", size="101", token=token)
        events.extend(lifecycle)
        order_ms += 2
    assert sum(D(fill["size"]) for fill in fills(events)) == D("500")
    assert r.intent(row, size="10")[0]["reason"] == "market_cap"


@pytest.mark.parametrize("delay_ms", [0, 1000])
def test_replay_is_deterministic(delay_ms):
    def run():
        r = Replay(latency_ms=delay_ms)
        r.market()
        row, start = r.book_row(1)
        out = start + r.intent(row)
        out.extend(r.book_row(2 + delay_ms)[1])
        out.extend(r.resolve(180_000, {"Up": 1, "Down": 0})[1])
        return json.dumps(out, sort_keys=True)

    assert run() == run()


def test_cash_at_submit_must_cover_executable_minimum_with_fees():
    r = Replay(initial_cash="2.50", latency_ms=10)
    row, _ = r.book_row(1, ask="0.51")
    assert r.intent(row, price="0.50", size="5")[0]["reason"] == "insufficient_cash"
    assert r.intent(row, price="0.50", size="5", style="passive")[0]["kind"] == "submitted"
    assert r.intent(row, price="0.50", size="5", style="passive")[0]["reason"] == "insufficient_cash"
    r.book_row(11, ask="0.51")
    assert D(fills(r.trade_row(12, size="1"))[0]["size"]) == D("1")


def test_economically_identical_prints_in_distinct_transactions_are_independent():
    r = Replay(latency_ms=1)
    row, _ = r.book_row(1, ask="0.55")
    r.intent(row, style="passive", price="0.50", size="10")
    r.book_row(2, ask="0.55")
    first = fills(r.trade_row(3, size="3", tx_hash="0xAA"))
    duplicate = fills(r.trade_row(4, size="3", exchange=3, tx_hash="0xaa"))
    other_trade = fills(r.trade_row(5, size="3", exchange=3, tx_hash="0xBB"))
    different_size = fills(r.trade_row(6, size="2", exchange=3, tx_hash="0xBB"))
    assert [f["size"] for f in first + duplicate + other_trade + different_size] == ["3", "3", "2"]
    assert all("transaction_hash" not in fill for fill in first + other_trade + different_size)


def test_mirrored_batch_shares_one_pool_and_cannot_create_negative_fills():
    r = Replay(latency_ms=1)
    r.market()
    down, _ = r.book_row(1, bid="0.30", ask="0.40", size="10", token="down")
    r.intent(down, token="down", outcome="Down", price="0.40", fee_rate="0")
    assert fills(r.book_row(2, bid="0.30", ask="0.40", size="10", token="down")[1])[0]["size"] == "10"

    up, _ = r.book_row(3, bid="0.60", ask="0.70", size="10")
    r.intent(up, price="0.70", fee_rate="0")
    r.intent(up, token="down", outcome="Down", side="SELL", price="0.30", fee_rate="0")
    _, events = r.row(4, payload={
        "event_type": "price_change", "timestamp": str(BASE_MS + 4),
        "price_changes": [
            {"asset_id": "up", "side": "SELL", "price": "0.70", "size": "10"},
            {"asset_id": "down", "side": "BUY", "price": "0.30", "size": "10"},
        ],
    })
    assert [(fill["token"], fill["side"], fill["size"]) for fill in fills(events)] == [("up", "BUY", "10")]
    assert r.exec.cash == D("189")
    assert r.exec._positions["btc5", "down"] == D("10")


@pytest.mark.parametrize("first_hash, second_hash", [(None, "0xAA"), ("0xAA", None)])
def test_missing_and_present_transaction_hash_are_the_same_print(first_hash, second_hash):
    r = Replay(latency_ms=1)
    row, _ = r.book_row(1, ask="0.55")
    r.intent(row, style="passive", price="0.50", size="10")
    r.book_row(2, ask="0.55")
    assert [f["size"] for f in fills(r.trade_row(3, size="3", tx_hash=first_hash))] == ["3"]
    assert fills(r.trade_row(4, size="3", exchange=3, tx_hash=second_hash)) == []
    assert fills(r.trade_row(5, size="3", exchange=3, tx_hash="0xaa")) == []
    assert [f["size"] for f in fills(r.trade_row(6, size="3", exchange=3, tx_hash="0xbb"))] == ["3"]


def test_passive_trade_has_to_be_after_both_receipt_and_exchange_placement():
    r = Replay(latency_ms=10)
    signal, _ = r.book_row(100, ask="0.55")
    r.intent(signal, style="passive", price="0.50", size="10")
    [placed] = r.book_row(110, ask="0.55", exchange=140)[1]
    assert placed["rested_exchange_ms"] == BASE_MS + 140
    assert fills(r.trade_row(120, exchange=125)) == []
    assert fills(r.trade_row(130, exchange=140)) == []
    fill = fills(r.trade_row(141, exchange=141))[0]
    assert fill["size"] == "8"


@pytest.mark.parametrize("style", ["taker", "passive"])
@pytest.mark.parametrize("latest_source", ["book", "event", "strategy_snapshot"])
def test_latency_respected_on_both_local_and_exchange_clocks(style, latest_source):
    r = Replay(latency_ms=1000)
    signal, _ = r.book_row(100, ask="0.55", exchange=140 if latest_source == "book" else 100)
    if latest_source == "event":
        signal, _ = r.row(100, payload={
            "event_type": "last_trade_price", "asset_id": "up", "timestamp": str(BASE_MS + 140),
            "price": "0.55", "size": "5", "side": "BUY",
        })
    params = {"snapshot": {"trade_exchange_ms": BASE_MS + 140}} if latest_source == "strategy_snapshot" else {}
    price = "0.60" if style == "taker" else "0.50"
    [accepted] = r.intent(signal, style=style, price=price, **params)
    assert accepted["kind"] == "submitted"
    assert accepted["ready_ns"] == (BASE_MS + 1100) * MS
    assert accepted["exchange_ready_ns"] == (BASE_MS + 1140) * MS
    assert r.book_row(1100, exchange=1101)[1] == []
    _, events = r.book_row(1140, exchange=1140)
    assert [event["kind"] for event in events] == ["fill" if style == "taker" else "resting"]


def test_reaching_exchange_deadline_cannot_skip_local_latency():
    r = Replay(latency_ms=1000)
    signal, _ = r.book_row(100, exchange=60)
    [accepted] = r.intent(signal)
    assert accepted["exchange_ready_ns"] == (BASE_MS + 1060) * MS
    assert r.book_row(1095, exchange=1100)[1] == []
    assert fills(r.book_row(1100, exchange=1101)[1])


def test_lockin_deadline_rejects_t_minus_two_signal_that_would_fill_at_t_minus_985ms():
    r = Replay(latency_ms=1000)
    signal, _ = r.book_row(178_000)
    [result] = r.intent(signal, execute_by_ns=(BASE_MS + 178_000) * MS)
    assert result["kind"] == "rejected"
    assert result["reason"] == "arrival_after_deadline"
    assert fills(r.book_row(179_015)[1]) == []


def test_execution_deadline_is_inclusive_and_separate_from_official_expiry():
    r = Replay(latency_ms=10)
    r.market()
    signal, _ = r.book_row(100, exchange=100)
    deadline = (BASE_MS + 110) * MS
    assert r.intent(signal, execute_by_ns=deadline)[0]["kind"] == "submitted"
    [fill] = r.book_row(110, exchange=110)[1]
    assert fill["kind"] == "fill"
    assert fill["execute_by_ns"] == deadline
    assert r.resolve(111, {"Up": 1, "Down": 0})[1] == []
    assert r.resolve(180_000, {"Up": 1, "Down": 0})[1][0]["kind"] == "settlement"


def test_deadline_filters_exchange_time_for_taker_and_passive():
    deadline = (BASE_MS + 130) * MS
    taker = Replay(latency_ms=10)
    row, _ = taker.book_row(100)
    assert taker.intent(row, execute_by_ns=deadline)[0]["kind"] == "submitted"
    assert fills(taker.book_row(120, exchange=131)[1]) == []
    assert taker.book_row(131, exchange=132)[1][0]["reason"] == "execution_deadline"

    passive = Replay(latency_ms=10)
    row, _ = passive.book_row(100)
    passive.intent(row, style="passive", price="0.50", execute_by_ns=deadline)
    assert passive.book_row(110)[1][0]["kind"] == "resting"
    assert fills(passive.trade_row(120, exchange=131)) == []
