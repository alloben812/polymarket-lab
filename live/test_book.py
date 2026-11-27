import gzip
import json
from decimal import Decimal
from pathlib import Path

import pytest

from live.book import BookReplay, coverage, iter_records, replay_as_of


D = Decimal
FIXTURE = Path(__file__).with_name("fixtures") / "polymarket-btc5m.jsonl"


def event(kind, ns, session="s1", **fields):
    return {"kind": kind, "session": session, "recv_ns": ns, **fields}


def snapshot(ns, exchange=None, token="up", session="s1", bids=None, asks=None, **fields):
    return event(
        "ws", ns, session,
        payload={
            "event_type": "book", "asset_id": token,
            "timestamp": str(ns if exchange is None else exchange),
            "bids": bids if bids is not None else [{"price": "0.4", "size": "10"}],
            "asks": asks if asks is not None else [{"price": "0.6", "size": "5"}],
        },
        **fields,
    )


def row(side, price, size, token="up", **fields):
    return {"asset_id": token, "side": side, "price": price, "size": size, **fields}


def change(ns, *rows, exchange=None, session="s1"):
    return event(
        "ws", ns, session,
        payload={
            "event_type": "price_change",
            "timestamp": str(ns if exchange is None else exchange),
            "price_changes": rows if isinstance(rows, list) else list(rows),
        },
    )


def trade(ns, exchange, price="0.6"):
    return event("ws", ns, payload={
        "event_type": "last_trade_price", "asset_id": "up", "timestamp": str(exchange),
        "price": price, "side": "BUY", "size": "3", "hash": "another-opaque-hash",
    })


def recording(path, records):
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record) + "\n")
    return path


def test_rebuild_from_real_public_fixture():
    # Captured on the public CLOB market socket, BTC 5m market 1795801500.
    # The expected levels are read from the recorded snapshots and verified
    # against the individual price_change sizes, independent of the replayer.
    up = "39274577525333704354298672663289203911278289669631471418591315480555362982491"
    down = "8707235643276270421921547026439079844993760361385723732898132467502294536748"
    up_quote = replay_as_of([FIXTURE], up, 1795801511553579000, depth=3)
    down_quote = replay_as_of([FIXTURE], down, 1795801511553579000, depth=3)
    assert up_quote.status == down_quote.status == "ok"
    assert up_quote.bids == ((D("0.60"), D("443.07")), (D("0.59"), D("264.28")), (D("0.58"), D("139.5")))
    assert up_quote.asks == ((D("0.62"), D("30")), (D("0.63"), D("35")), (D("0.64"), D("40")))
    assert down_quote.bids == ((D("0.38"), D("30")), (D("0.37"), D("35")), (D("0.36"), D("40")))
    assert down_quote.asks == ((D("0.40"), D("443.07")), (D("0.41"), D("264.28")), (D("0.42"), D("139.5")))
    assert up_quote.book_exchange_ms == 1795801511566

    before_trade = replay_as_of([FIXTURE], up, 1795801511563939000)
    after_trade = replay_as_of([FIXTURE], up, 1795801511585613000)
    assert before_trade.bids == after_trade.bids
    assert before_trade.asks == after_trade.asks
    assert before_trade.last_trade is None
    assert after_trade.last_trade.price == D("0.61")
    assert after_trade.last_trade.size == D("18.75")
    assert after_trade.last_trade.exchange_ms == 1795801511610
    assert after_trade.book_exchange_ms == 1795801511574
    assert after_trade.observed_recv_ns == 1795801511585613000

    report = coverage(iter_records([FIXTURE]))
    assert report.records == 25
    assert report.tokens[up].status_changes["out_of_order"] == 1
    assert report.tokens[up].status_changes["book_mismatch"] == 1


def test_receipt_order_keeps_batch_atomic_and_applies_absolute_sizes():
    replay = BookReplay()
    replay.apply(snapshot(1))
    replay.apply(snapshot(2, token="down"))
    replay.apply(change(
        3,
        row("BUY", "0.4", "8", best_bid="0.5"),
        row("SELL", "0.6", "0", "down", best_bid="0.4", best_ask="1"),
        row("BUY", "0.5", "2", best_bid="0.5", best_ask="0.6"),
    ))
    assert replay.quote("up").bids == ((D("0.5"), D("2")), (D("0.4"), D("8")))
    assert replay.quote("down").asks == ()
    replay.apply(change(4, row("BUY", "0.5", "0"), exchange=3))
    assert replay.quote("up", depth=1).bids == ((D("0.4"), D("8")),)
    replay.apply(trade(5, 8))
    replay.apply(trade(6, 7, price="0.3"))
    assert replay.quote("up").last_trade.price == D("0.6")
    assert replay.quote("up").book_exchange_ms == 3
    assert replay.quote("up").observed_recv_ns == 6


def test_snapshot_required_and_regression_waits_for_fresh_snapshot():
    replay = BookReplay()
    replay.apply(event("market", 1, market={"tokens": {"Up": "up", "Down": "down"}}))
    assert replay.quote("up").status == "missing_snapshot"
    assert replay.quote("other").status == "unknown_token"
    replay.apply(change(2, row("BUY", "0.5", "2"), exchange=12))
    assert replay.quote("up").bids == ()
    replay.apply(snapshot(3, exchange=11))
    assert replay.status_for("up") == "out_of_order"
    assert replay.quote("up").book_exchange_ms == 12
    replay.apply(snapshot(4, exchange=13))
    assert replay.quote("up").status == "ok"
    replay.apply(change(5, row("BUY", "0.5", "20"), exchange=12))
    replay.apply(change(6, row("BUY", "0.5", "10"), exchange=14))
    assert replay.quote("up").status == "out_of_order"
    assert replay.quote("up").book_exchange_ms == 14
    assert replay.quote("up").bids == ()
    replay.apply(snapshot(7, exchange=15))
    assert replay.quote("up").bids == ((D("0.4"), D("10")),)


def test_token_scoped_boundaries_and_new_session_ignore_old_frames():
    replay = BookReplay()
    replay.apply(event("connected", 1, tokens=["up", "down"]))
    replay.apply(snapshot(2))
    replay.apply(snapshot(3, token="down"))
    replay.apply(event("market", 4, market={"tokens": {"Up": "next-up"}}))
    assert replay.quote("up").status == "ok"
    replay.apply(event("gap", 5, tokens=["up"], reason="unsubscribed"))
    replay.apply(snapshot(6))
    assert replay.quote("up").status == "unsubscribed"
    assert replay.quote("down").status == "ok"
    replay.apply(event("connected", 7, "s2", tokens=["up"]))
    replay.apply(snapshot(8))
    assert replay.quote("up").status == "missing_snapshot"
    replay.apply(snapshot(9, session="s2"))
    replay.apply(event("stop", 10, tokens=[]))
    assert replay.quote("up").status == "ok"
    assert replay.quote("up").session == "s2"
    assert replay.quote("down").status == "stopped"
    replay.apply(snapshot(11, token="down"))
    assert replay.quote("down").status == "stopped"


def test_retroactive_gap_and_pong_bounded_silence_split_across_gzip_segments(tmp_path):
    first = recording(tmp_path / "001.jsonl.gz", [
        event("connected", 10, tokens=["up", "down", "unused"]),
        snapshot(11), snapshot(12, token="down"),
        event("heartbeat", 100, status="pong"),
        event("reference", 110),
        event("heartbeat", 120, status="ping"),
    ])
    second = recording(tmp_path / "002.jsonl.gz", [
        event("gap", 150, since_ns=100, tokens=["up"], reason="transport"),
        change(155, row("BUY", "0.5", "20")),
        snapshot(160, source="rest_checkpoint"),
        event("heartbeat", 200, status="pong"),
        event("heartbeat", 220, status="ping"),
        event("stop", 250, tokens=[]),
    ])
    paths = [first, second]
    assert replay_as_of(paths, "up", 99).status == "ok"
    assert replay_as_of(paths, "up", 100).status == "ok"
    assert replay_as_of(paths, "up", 101).status == "gap"
    assert replay_as_of(paths, "up", 120).status == "gap"
    assert replay_as_of(paths, "up", 156).status == "gap"
    recovered = replay_as_of(paths, "up", 160)
    assert recovered.status == "ok"
    assert recovered.snapshot_source == "rest_checkpoint"
    assert replay_as_of(paths, "down", 150).status == "ok"
    assert replay_as_of(paths, "unused", 180).status == "missing_snapshot"
    assert replay_as_of(paths, "up", 201).status == "unobserved_tail"
    assert replay_as_of(paths, "up", 250).status == "stopped"

    report = coverage(iter_records(paths), from_ns=90, to_ns=225)
    assert report.records == 12
    assert report.window_ns == 136
    assert report.tokens["up"].intervals == ((90, 100), (160, 200))
    assert report.tokens["up"].covered_ns == 52
    assert report.tokens["up"].explicit_gaps[0].start_ns == 101
    assert report.tokens["down"].intervals == ((90, 200),)
    assert report.tokens["unused"].intervals == ()


def test_rest_checkpoints_do_not_prove_websocket_continuity_for_other_tokens(tmp_path):
    paths = [recording(tmp_path / "logs.jsonl.gz", [
        snapshot(10, token="down"),
        snapshot(20, source="rest_checkpoint"),
        event("reference", 25),
    ])]
    assert replay_as_of(paths, "up", 20).status == "ok"
    assert replay_as_of(paths, "up", 21).status == "unobserved_tail"
    assert replay_as_of(paths, "down", 20).status == "unobserved_tail"
    assert coverage(iter_records(paths)).tokens["down"].intervals == ((10, 10),)


def test_malformed_updates_clear_levels_and_do_not_partially_update_other_tokens():
    replay = BookReplay()
    replay.apply(snapshot(1))
    replay.apply(snapshot(2, token="down"))
    replay.apply(change(3, row("BUY", "0.5", "2"), row("SELL", "0.7", "-1")))
    assert replay.quote("up").status == "invalid_book"
    assert replay.quote("up").asks == replay.quote("up").bids == ()
    assert replay.quote("down").status == "ok"
    replay.apply(change(4, {"price": "0.55", "size": "2"}))
    assert replay.quote("down").status == "invalid_book"


def test_equal_receipt_timestamp_respects_record_order(tmp_path):
    records = [
        snapshot(1),
        event("gap", 20, since_ns=1, tokens=[], reason="transport"),
        snapshot(20),
    ]
    paths = [recording(tmp_path / "logs.jsonl.gz", records)]
    assert replay_as_of(paths, "up", 20).status == "ok"
    assert coverage(iter_records(paths)).tokens["up"].intervals == ((1, 1), (20, 20))


def test_rejects_logs_with_decreasing_receipt_time(tmp_path):
    path = recording(tmp_path / "logs.jsonl.gz", [snapshot(9), snapshot(8)])
    with pytest.raises(ValueError, match=r"logs.jsonl.gz:2:.*recv_ns"):
        list(iter_records([path]))


def test_retroactive_gap_is_scoped_to_old_session_even_after_new_connection(tmp_path):
    records = [
        snapshot(10),
        event("heartbeat", 15, status="pong"),
        event("stop", 20, tokens=[]),
        event("connected", 25, "s2", tokens=["up"]),
        snapshot(26, session="s2"),
        event("heartbeat", 40, "s2", status="pong"),
        event("gap", 45, since_ns=12, tokens=[], reason="late_audit"),
    ]
    path = recording(tmp_path / "logs.jsonl.gz", records)
    assert replay_as_of([path], "up", 12).status == "ok"
    assert replay_as_of([path], "up", 14).status == "gap"
    assert replay_as_of([path], "up", 30).status == "ok"
    assert coverage(iter_records([path])).tokens["up"].intervals == ((10, 12), (26, 40))


def test_missing_segment_with_ordinals_fails_closed(tmp_path):
    first = recording(tmp_path / "001.jsonl.gz", [
        snapshot(10, ordinal=21),
        event("reference", 15, "", ordinal=22),
    ])
    last = recording(tmp_path / "003.jsonl.gz.open", [
        event("heartbeat", 30, status="pong", ordinal=27),
    ])
    assert list(iter_records([last]))[0]["ordinal"] == 27
    assert replay_as_of([first], "up", 10).status == "ok"
    with pytest.raises(ValueError, match="expected ordinal 23, found 27"):
        replay_as_of([first, last], "up", 25)
    with pytest.raises(ValueError, match="missing or reordered log records"):
        coverage(iter_records([first, last]))


def test_independent_run_directories_restart_ordinals(tmp_path):
    for run in ("first", "second"):
        (tmp_path / run).mkdir()
    first = recording(tmp_path / "first" / "001.jsonl.gz", [snapshot(10, ordinal=25)])
    second = recording(
        tmp_path / "second" / "001.jsonl.gz", [snapshot(20, session="s2", ordinal=1)]
    )
    assert len(list(iter_records([first, second]))) == 2


def best_bid_ask(ns, exchange, *, token="up", bid, ask):
    return event("ws", ns, payload={
        "event_type": "best_bid_ask", "asset_id": token, "timestamp": str(exchange),
        "best_bid": bid, "best_ask": ask,
    })


def test_conflicting_bbo_invalidates_mirrored_books_until_fresh_snapshot(tmp_path):
    # Public smoke recording ordinals 212-215. BBO for Down (213) and Up
    # (214) arrived ahead of the corresponding two-token L2 delta (215).
    up_before = [{"price": "0.48", "size": "18"}]
    down_before = [{"price": "0.52", "size": "18"}]
    records = [
        snapshot(10, exchange=1795801698602, bids=up_before,
                 asks=[{"price": "0.50", "size": "40"}]),
        snapshot(11, exchange=1795801698602, token="down",
                 bids=[{"price": "0.50", "size": "40"}], asks=down_before),
        change(
            12,
            row("BUY", "0.43", "49", "down", best_bid="0.50", best_ask="0.52"),
            row("SELL", "0.57", "49", "up", best_bid="0.48", best_ask="0.50"),
            exchange=1795801698617,
        ),
        best_bid_ask(13, 1795801698626, token="down", bid="0.50", ask="0.51"),
        best_bid_ask(14, 1795801698626, token="up", bid="0.49", ask="0.50"),
        change(
            15,
            row("SELL", "0.51", "30", "down", best_bid="0.50", best_ask="0.51"),
            row("BUY", "0.49", "30", "up", best_bid="0.49", best_ask="0.50"),
            exchange=1795801698618,
        ),
        snapshot(16, exchange=1795801698625, bids=up_before,
                 asks=[{"price": "0.50", "size": "40"}]),
        snapshot(17, exchange=1795801698626, bids=[{"price": "0.49", "size": "30"}],
                 asks=[{"price": "0.50", "size": "40"}]),
    ]
    path = recording(tmp_path / "log.jsonl.gz", records)
    assert replay_as_of([path], "down", 12).asks[0][0] == D("0.52")
    down = replay_as_of([path], "down", 13)
    assert down.status == "book_mismatch"
    assert down.bids == down.asks == ()
    assert replay_as_of([path], "up", 13).bids[0][0] == D("0.48")
    up = replay_as_of([path], "up", 14)
    assert up.status == "book_mismatch"
    assert up.bids == up.asks == ()
    assert up.book_exchange_ms == 1795801698626
    assert replay_as_of([path], "up", 15).status == "book_mismatch"
    assert replay_as_of([path], "up", 16).status == "out_of_order"
    assert replay_as_of([path], "up", 17).bids[0] == (D("0.49"), D("30"))
    report = coverage(iter_records([path]))
    assert report.tokens["up"].intervals == ((10, 13), (17, 17))
    assert report.tokens["down"].intervals == ((11, 12),)


def test_older_bbo_and_matching_bbo_leave_book_clock_and_depth_intact():
    replay = BookReplay()
    replay.apply(snapshot(1, exchange=20))
    initial = replay.quote("up")
    assert replay.apply(best_bid_ask(2, 19, bid="0.35", ask="0.65")) == set()
    assert replay.apply(best_bid_ask(3, 21, bid="0.40", ask="0.60")) == set()
    now = replay.quote("up")
    assert now.status == "ok"
    assert (now.bids, now.asks) == (initial.bids, initial.asks)
    assert now.book_exchange_ms == 20
    assert now.book_recv_ns == 1
    assert now.observed_recv_ns == 3

    replay.apply(best_bid_ask(4, 20, bid="0.45", ask="0.60"))
    assert replay.status_for("up") == "book_mismatch"


def test_market_resolution_is_terminal_across_sessions_and_rest(tmp_path):
    records = [
        event("market", 1, "", market={
            "condition_id": "0x123", "tokens": {"Up": "up", "Down": "down"},
        }),
        event("connected", 2, tokens=["up", "down"]),
        snapshot(3), snapshot(4, token="down"),
        event("ws", 5, payload={
            "event_type": "market_resolved", "market": "0x123", "assets_ids": ["up"],
        }),
        snapshot(6, token="down", source="rest_checkpoint"),
        snapshot(7),
        event("connected", 8, "s2", tokens=["up", "down"]),
        snapshot(9, session="s2", source="rest_checkpoint"),
        snapshot(10, token="down", session="s2"),
        event("gap", 11, "s2", tokens=["up"], reason="unsubscribed"),
        event("stop", 12, tokens=[]),
    ]
    path = recording(tmp_path / "log.jsonl.gz", records)

    for token in ("up", "down"):
        assert replay_as_of([path], token, 4).status == "ok"
        for cutoff in (5, 7, 8, 10, 12):
            quote = replay_as_of([path], token, cutoff)
            assert quote.status == "resolved"
            assert quote.bids == quote.asks == ()
    report = coverage(iter_records([path]))
    assert report.tokens["up"].intervals == ((3, 4),)
    assert report.tokens["down"].intervals == ((4, 4),)
    assert report.tokens["up"].status_changes["resolved"] == 1
    assert report.tokens["down"].status_changes["resolved"] == 1
