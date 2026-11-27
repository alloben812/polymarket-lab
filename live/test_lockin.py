from dataclasses import dataclass, field
from decimal import Decimal
import json

import pytest

from live.book import BookReplay
from live.lockin import Lockin, SECOND_NS

START = 1_795_803_600
END = START + 300
MATCH = END - 42
UP, DOWN = "201", "202"
CONDITION = "0x" + "ab" * 32
SLUG = f"btc-updown-5m-{START}"


@dataclass
class Scenario:
    book: BookReplay = field(default_factory=BookReplay)
    strategy: Lockin = field(default_factory=Lockin)
    rows: list[dict] = field(default_factory=list)

    def row(self, kind, second, millisecond=0, **extra):
        row = {
            "kind": kind,
            "recv_ns": second * SECOND_NS + millisecond * 1_000_000,
            "session": "session",
            "ordinal": len(self.rows) + 1,
            **extra,
        }
        self.rows.append(row)
        self.book.apply(row)
        return self.strategy.observe(row, self.book)

    def market(self, **options):
        return self.row(
            "market",
            START - 60,
            market={
                "kind": "btc5m",
                "slug": SLUG,
                "condition_id": CONDITION,
                "tokens": {"Up": UP, "Down": DOWN},
                "start_ts": START,
                "end_ts": END,
                "fee_rate": 0.05,
                "min_size": 5,
                "tick_size": 0.01,
                **options,
            },
        )

    def reference(self, bars, second=MATCH - 1, millisecond=0):
        return self.row("reference", second, millisecond, symbol="BTCUSDT", bars=bars)

    def bars(self, move=100, skip=None, through=MATCH - 2):
        return self.reference(
            [
                (opened, str(60_000 + (move if opened > START else 0)))
                for opened in range(MATCH - 920, through + 1)
                if opened != skip
            ]
        )

    def snapshot(
        self,
        token=UP,
        price="0.93",
        size="250",
        second=MATCH - 1,
        millisecond=100,
        **options,
    ):
        return self.row(
            "ws",
            second,
            millisecond,
            payload={
                "event_type": "book",
                "asset_id": token,
                "market": CONDITION,
                "timestamp": str(second * 1000 + millisecond),
                "bids": [{"price": "0.01", "size": "500"}],
                "asks": [] if price is None else [{"price": price, "size": size}],
                **options,
            },
        )

    def trade(
        self,
        token=UP,
        *,
        side="BUY",
        price="0.95",
        size="150",
        event_time=MATCH,
        recv_time=MATCH,
        recv_ms=50,
        exchange_ms=0,
        source="websocket",
        transaction=None,
    ):
        return self.row(
            "ws",
            recv_time,
            recv_ms,
            source=source,
            payload={
                "event_type": "last_trade_price",
                "asset_id": token,
                "market": CONDITION,
                "side": side,
                "price": price,
                "size": size,
                "timestamp": str(event_time * 1000 + exchange_ms),
                "transaction_hash": transaction,
            },
        )


def start(*, move=100, skip=None, through=MATCH - 2, price="0.93", size="250"):
    scenario = Scenario()
    assert scenario.market() == []
    assert scenario.bars(move=move, skip=skip, through=through) == []
    assert scenario.snapshot(price=price, size=size) == []
    return scenario


def test_limit_uses_covered_ask_and_caps_print_size():
    scenario = start()
    [decision] = scenario.trade()

    assert decision["action"] == "intent"
    assert decision["reason"] == "rule_met"
    assert (decision["side"], decision["style"]) == ("BUY", "taker")
    assert (decision["token"], decision["outcome"], decision["slug"]) == (
        UP,
        "Up",
        SLUG,
    )
    assert (decision["price"], decision["size"]) == ("0.93", "100")
    assert Decimal(decision["market"]["fee_rate"]) == Decimal(".05")
    assert Decimal(decision["market"]["min_size"]) == 5
    assert Decimal(decision["market"]["tick_size"]) == Decimal(".01")
    assert decision["market"]["end_ts"] == END

    snapshot = decision["snapshot"]
    assert snapshot["trade_price"] == snapshot["candidate_price"] == "0.95"
    assert snapshot["ask_price"] == "0.93"
    assert snapshot["trade_size"] == "150"
    assert snapshot["ask_size"] == "250"
    assert snapshot["model_open_s"] == MATCH - 2
    assert snapshot["model_closed_s"] == MATCH - 1
    assert snapshot["basis_distance"] == pytest.approx(100)
    assert snapshot["fee_per_share"] == pytest.approx(0.05 * 0.93 * 0.07)
    assert "transaction_hash" not in json.dumps(decision, allow_nan=False)


def test_taker_sell_maps_to_opposite_outcome_and_caps_at_covered_size():
    scenario = start(size="31.75")
    [decision] = scenario.trade(DOWN, side="SELL", price="0.06", size="80")
    assert decision["action"] == "intent"
    assert (decision["token"], decision["outcome"]) == (UP, "Up")
    assert (decision["price"], decision["size"]) == ("0.93", "31.75")
    assert decision["snapshot"]["trade_price"] == "0.06"
    assert decision["snapshot"]["candidate_price"] == "0.94"


@pytest.mark.parametrize(
    ("options", "trade", "reason"),
    [
        ({}, {"token": DOWN}, "unfavored_outcome"),
        ({"move": 0}, {}, "probability_below_floor"),
        ({"move": 10}, {}, "basis_filter"),
        ({}, {"price": "0.99"}, "print_above_model_ceiling"),
        ({}, {"price": "0.49"}, "price_below_floor"),
        ({}, {"size": "4.99"}, "print_below_minimum"),
        ({"price": "0.96"}, {}, "ask_above_trade_limit"),
        ({"price": "0.933"}, {}, "ask_off_tick"),
        ({"price": None}, {}, "no_ask"),
        ({"size": "3.99"}, {}, "size_below_minimum"),
        ({"skip": MATCH - 3}, {}, "reference_gap"),
        ({"through": MATCH - 3}, {}, "reference_late"),
    ],
)
def test_rejections_are_explained(options, trade, reason):
    scenario = start(**options)
    [decision] = scenario.trade(**trade)
    assert decision["action"] == "skip"
    assert decision["reason"] == reason


def test_uses_receipt_order_for_late_and_unclosed_binance_candles():
    scenario = start(through=MATCH - 3)
    [first] = scenario.trade()
    assert first["reason"] == "reference_late"

    # A later receipt can change a later decision, never the earlier one. The
    # malformed future candle below could reverse the model if read early.
    assert (
        scenario.reference(
            [(MATCH - 2, "60100"), (MATCH - 1, "20000"), (MATCH, "20000")],
            MATCH,
            70,
        )
        == []
    )
    [second] = scenario.trade(recv_ms=100, exchange_ms=1)
    assert second["action"] == "intent"
    assert second["snapshot"]["reference_recv_ns"] == MATCH * SECOND_NS + 70_000_000
    assert second["snapshot"]["reference_latest_open_s"] == MATCH - 1
    assert second["snapshot"]["model_open_s"] == MATCH - 2

    replay = BookReplay()
    lockin = Lockin()
    decisions = []
    for row in scenario.rows:
        replay.apply(row)
        decisions.extend(lockin.observe(row, replay))
    assert decisions == [first, second]


def test_books_without_prints_do_not_make_decisions_and_gaps_block_stale_levels():
    scenario = start()
    assert (
        scenario.row(
            "ws",
            MATCH - 1,
            200,
            source="websocket",
            payload={
                "event_type": "price_change",
                "market": CONDITION,
                "timestamp": str((MATCH - 1) * 1000 + 200),
                "price_changes": [
                    {
                        "asset_id": UP,
                        "side": "SELL",
                        "price": "0.93",
                        "size": "200",
                        "best_bid": "0.01",
                        "best_ask": "0.93",
                    }
                ],
            },
        )
        == []
    )
    assert scenario.row("gap", MATCH - 1, 250, tokens=[UP], reason="lost") == []
    [decision] = scenario.trade()
    assert decision["reason"] == "book_unavailable"
    assert decision["snapshot"]["book_status"] == "gap"


def test_declines_stale_anchor_and_honors_tick_update():
    scenario = Scenario()
    scenario.market()
    scenario.snapshot(second=MATCH - 4)
    scenario.bars()
    [stale] = scenario.trade()
    assert stale["reason"] == "book_stale"

    scenario.snapshot(price="0.932", second=MATCH, millisecond=150)
    scenario.row(
        "ws",
        MATCH,
        160,
        payload={
            "event_type": "tick_size_change",
            "asset_id": UP,
            "new_tick_size": "0.001",
            "timestamp": str(MATCH * 1000 + 160),
        },
    )
    [current] = scenario.trade(recv_ms=180, exchange_ms=1)
    assert current["action"] == "intent"
    assert current["tick_size"] == "0.001"
    assert current["price"] == "0.932"


def test_ws_market_resolution_prevents_intent_before_nominal_expiry():
    scenario = start()
    scenario.row(
        "ws",
        MATCH,
        25,
        source="websocket",
        payload={
            "event_type": "market_resolved",
            "market": CONDITION,
            "assets_ids": [UP, DOWN],
        },
    )
    [resolved] = scenario.trade()
    assert resolved["reason"] == "market_closed"


def gamma_resolution(**changes):
    return {
        "slug": SLUG,
        "condition_id": CONDITION,
        "source": "gamma",
        "payouts": {"Up": 1, "Down": 0},
        **changes,
    }


def test_early_gamma_resolution_does_not_close_market():
    scenario = start()
    scenario.row("resolution", MATCH, 25, **gamma_resolution())
    [decision] = scenario.trade()
    assert decision["action"] == "intent"


@pytest.mark.parametrize(
    ("changes", "closed"),
    [
        ({}, True),
        ({"source": "unverified"}, False),
        ({"condition_id": "0x" + "cd" * 32}, False),
        ({"payouts": {"Up": 1}}, False),
        ({"payouts": {"Up": 0.8, "Down": 0.8}}, False),
    ],
)
def test_gamma_resolution_after_expiry_checks_market_and_payouts(changes, closed):
    scenario = start()
    scenario.row("resolution", END, 25, **gamma_resolution(**changes))
    # After expiry all trades are independently rejected by their time gate.
    assert (SLUG in scenario.strategy._closed) is closed


def test_late_receipt_prevents_intent():
    scenario = start()
    [late] = scenario.trade(event_time=END - 2, recv_time=END - 2, recv_ms=1)
    assert late["reason"] == "outside_entry_window"
    [closed] = scenario.trade(event_time=END - 1, recv_time=END, recv_ms=1)
    assert closed["reason"] == "market_closed"


def test_btc15m_and_replayed_rest_trade_are_outside_strategy():
    scenario = Scenario()
    scenario.market(kind="btc15m")
    assert scenario.trade() == []
    scenario = start()
    assert scenario.trade(source="rest_checkpoint") == []


def test_identical_and_mirrored_prints_cannot_repeat_an_intent():
    scenario = start()
    [first] = scenario.trade(price="0.95", size="40")
    [repeat] = scenario.trade(price="0.950", size="40.00", recv_ms=60)
    [mirror] = scenario.trade(DOWN, side="SELL", price="0.050", size="40", recv_ms=70)
    [different_size] = scenario.trade(price="0.95", size="41", recv_ms=80)
    [different_time] = scenario.trade(
        DOWN, side="SELL", price="0.05", size="40", exchange_ms=1, recv_ms=90
    )

    assert (
        first["action"]
        == different_size["action"]
        == different_time["action"]
        == "intent"
    )
    assert repeat["reason"] == mirror["reason"] == "duplicate_print"
    assert mirror["outcome"] == "Up"
    assert mirror["snapshot"]["candidate_price"] == "0.950"


def test_duplicate_after_reference_arrival_does_not_reopen_decision():
    scenario = start(through=MATCH - 3)
    [first] = scenario.trade()
    assert first["reason"] == "reference_late"
    scenario.reference([(MATCH - 2, "60100")], MATCH, 70)
    [duplicate] = scenario.trade(recv_ms=80)
    assert duplicate["reason"] == "duplicate_print"


def test_equal_trades_from_distinct_transactions_are_kept():
    scenario = start()
    one, two = "0x" + "01" * 32, "0x" + "02" * 32
    [first] = scenario.trade(transaction=one)
    [mirror] = scenario.trade(
        DOWN, side="SELL", price="0.05", transaction=one.upper(), recv_ms=60
    )
    [second] = scenario.trade(transaction=two, recv_ms=70)
    [unknown] = scenario.trade(transaction=None, recv_ms=80)
    assert first["action"] == second["action"] == "intent"
    assert mirror["reason"] == unknown["reason"] == "duplicate_print"
    data = json.dumps([first, mirror, second, unknown], allow_nan=False)
    assert one not in data and two not in data


def test_first_unidentified_print_can_match_one_later_known_transaction():
    scenario = start()
    [first] = scenario.trade()
    [duplicate] = scenario.trade(transaction="0x" + "01" * 32, recv_ms=60)
    [new] = scenario.trade(transaction="0x" + "02" * 32, recv_ms=70)
    assert first["action"] == new["action"] == "intent"
    assert duplicate["reason"] == "duplicate_print"
