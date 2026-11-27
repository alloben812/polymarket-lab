from decimal import Decimal

from live.paper import Daily


def test_daily_result_allows_partial_sales_and_utc_settlement():
    ledger = Daily()
    ledger.markets["m"] = dict(condition_id="c", tokens={"Up": "u", "Down": "d"})
    base = dict(token="u", slug="m", outcome="Up", book_session="s")
    ledger.fill(
        dict(
            base,
            fill_id="buy",
            size="10",
            price=".60",
            fee=".12",
            side="BUY",
            recv_ns=1,
        )
    )
    ledger.fill(
        dict(
            base,
            fill_id="sell",
            size="4",
            price=".70",
            fee=".04",
            side="SELL",
            recv_ns=2,
        )
    )
    row = dict(
        source="gamma",
        recv_ns=86_400_000_000_000,
        slug="m",
        condition_id="c",
        payouts={"Up": 1, "Down": 0},
    )
    assert ledger.resolve(dict(row, condition_id="other")) == []
    [payment] = ledger.resolve(row)
    assert Decimal(payment["net"]) == Decimal("2.328")
    assert ledger.resolve(row) == []
    summary = ledger.summary()
    first, second = summary["utc_days"].values()
    assert first["fills"] == 2 and Decimal(first["realized_net"]) == Decimal(".312")
    assert Decimal(second["net_cents_per_closed_share"]) == Decimal("38.8")
    assert summary["open_positions"] == {}


def test_late_gap_withholds_results_for_affected_paper_cash():
    ledger = Daily()
    ledger.fill(
        dict(
            fill_id="one",
            token="u",
            slug="m",
            outcome="Up",
            book_session="s",
            size="5",
            price=".8",
            fee=".04",
            side="BUY",
            recv_ns=9,
        )
    )
    ledger.invalidate("one")
    day = ledger.summary()["utc_days"]["1970-01-01"]
    assert day["realized_net"] is None and day["accounting"].startswith("withheld")


def test_positive_path_is_deterministic_from_signal_to_official_settlement(tmp_path):
    import json

    from live.paper import Paper, utc_day
    from live.test_lockin import CONDITION, END, MATCH, SLUG, start

    s = start()
    s.trade(size="10")
    s.snapshot(second=MATCH + 1, millisecond=200, price=".92", size="10")
    s.row(
        "resolution",
        END + 30,
        source="gamma",
        slug=SLUG,
        condition_id=CONDITION,
        payouts={"Up": 1, "Down": 0},
    )
    s.row("stop", END + 31, reason="duration")
    for name in ("one", "two"):
        engine = Paper(tmp_path / name, 1000, "200")
        try:
            for row in s.rows:
                engine.observe(row)
        finally:
            engine.close()
    for name in ("daily.json", "decisions.jsonl"):
        assert (tmp_path / "one" / name).read_bytes() == (
            tmp_path / "two" / name
        ).read_bytes()
    result = json.loads((tmp_path / "one/daily.json").read_text())
    day = result["utc_days"][utc_day(END * 10**9)]
    assert (day["intents"], day["fills"], day["settled_lots"]) == (1, 1, 1)
    assert Decimal(day["fees"]) == Decimal(".03680")
    assert Decimal(day["realized_net"]) == Decimal(".76320")
    assert result["open_positions"] == {}
