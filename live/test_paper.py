from decimal import Decimal

from live.paper import Daily


def test_daily_result_allows_partial_sales_and_utc_settlement():
    ledger = Daily()
    ledger.markets["m"] = dict(condition_id="c", tokens={"Up": "u", "Down": "d"})
    base = dict(token="u", slug="m", outcome="Up", book_session="s")
    ledger.fill(dict(base, size="10", price=".60", fee=".12", side="BUY", recv_ns=1))
    ledger.fill(dict(base, size="4", price=".70", fee=".04", side="SELL", recv_ns=2))
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
    gap = dict(
        session="s", since_ns=8, recv_ns=10, tokens=["u"], reason="rest_book_disagrees"
    )
    assert not ledger.gap(dict(gap, session="other"))
    assert not ledger.gap(dict(gap, tokens=["d"]))
    assert not ledger.gap(dict(gap, since_ns=9))
    assert ledger.gap(gap)[0]["fill_id"] == "one"
    day = ledger.summary()["utc_days"]["1970-01-01"]
    assert day["realized_net"] is None and day["accounting"].startswith("withheld")
