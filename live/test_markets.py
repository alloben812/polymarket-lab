import json
from datetime import datetime, timezone

import pytest

from live import markets


def epoch(value):
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())


def utc_value(epoch_seconds):
    return datetime.fromtimestamp(epoch_seconds, timezone.utc).isoformat()


def market(slug, identifier, outcomes=("Yes", "No"), **fields):
    return {
        "slug": slug,
        "conditionId": f"0x{identifier:064x}",
        "active": True,
        "closed": False,
        "enableOrderBook": True,
        "acceptingOrders": True,
        "outcomes": json.dumps(outcomes),
        "clobTokenIds": json.dumps([str(identifier * 2), str(identifier * 2 + 1)]),
        "outcomePrices": '["0.505", "0.495"]',
        "orderPriceMinTickSize": 0.01,
        "orderMinSize": 5,
        "feesEnabled": True,
        "feeSchedule": {"rate": 0.05, "exponent": 1},
        **fields,
    }


def event(slug, rows, **fields):
    return {
        "slug": slug,
        "active": True,
        "closed": False,
        "markets": rows,
        **fields,
    }


def btc_event(slug):
    _, _, period, epoch_text = slug.split("-")
    minutes = int(period[:-1])
    start = int(epoch_text)
    start_value = utc_value(start)
    end_value = utc_value(start + minutes * 60)
    row = market(
        slug,
        start + minutes,
        ("Up", "Down"),
        eventStartTime=start_value,
        endDate=end_value,
    )
    return event(slug, [row], startTime=start_value, endDate=end_value)


def test_btc_rotation_preloads_the_following_window(monkeypatch):
    def fake_request(url, *args, **kwargs):
        assert "/events/slug/" in url
        return btc_event(url.rsplit("/", 1)[1])

    monkeypatch.setattr(markets, "get_json", fake_request)
    boundary = epoch("2026-11-27T18:00:00Z")
    config = {"btc_windows_minutes": [5, 15]}
    before = markets.discover(config, boundary - 1)
    after = markets.discover(config, boundary)

    for kind, width in (("btc5m", 300), ("btc15m", 900)):
        previous, preloaded = [row for row in before if row["kind"] == kind]
        current, next_row = [row for row in after if row["kind"] == kind]
        assert previous["end_ts"] == current["start_ts"] == boundary
        assert preloaded == current
        assert next_row["start_ts"] == boundary + width
        new_tokens = set(current["tokens"].values()) | set(next_row["tokens"].values())
        assert new_tokens.isdisjoint(previous["tokens"].values())
        assert set(current["tokens"]) == {"Up", "Down"}
        assert current["prices"] == {"Up": 0.505, "Down": 0.495}
        assert current["fee_rate"] == 0.05
        assert current["min_size"] == 5
        assert current["tick_size"] == 0.01


def test_weather_uses_local_day_and_excludes_closed_buckets(monkeypatch):
    slug = "highest-temperature-in-paris-on-march-29-2026"
    yesterday_utc = "2026-03-28T23:00:00Z"
    gamma_marker = "2026-03-29T12:00:00Z"
    first = market(
        f"{slug}-10c",
        1,
        eventStartTime=yesterday_utc,
        endDate=gamma_marker,
        feeSchedule={"rate": 0.01, "exponent": 1},
    )
    closed = market(f"{slug}-11c", 2, closed=True, acceptingOrders=False)
    paris = event(
        slug,
        [first, closed],
        eventDate="2026-03-29",
        tags=[{"slug": "daily-temperature"}],
    )

    def fake_gamma(category, path, params=None, *, optional=False):
        assert category == "weather"
        assert optional
        return paris if path == f"/events/slug/{slug}" else None

    monkeypatch.setattr(markets, "_gamma", fake_gamma)
    config = {"weather_cities": {"paris": "Europe/Paris", "london": "Europe/London"}}
    [bucket] = markets.discover(config, epoch("2026-03-29T18:00:00Z"))
    assert bucket["slug"] == first["slug"]
    assert bucket["start_ts"] == epoch(yesterday_utc)
    assert bucket["end_ts"] == epoch("2026-03-29T22:00:00Z")
    assert bucket["end_ts"] - bucket["start_ts"] == 23 * 3600
    assert bucket["fee_rate"] == 0.01


def fixture(slug, identifier, start, *, day="2026-11-27", live=False, ended=False):
    row = market(
        slug,
        identifier,
        ("Player A", "Player B"),
        sportsMarketType="moneyline",
        gameStartTime=start,
        endDate="2026-12-04T17:00:00Z",
    )
    prop = {
        **row,
        "slug": f"{slug}-set-1-winner",
        "sportsMarketType": "tennis_set_winner",
    }
    return event(
        slug,
        [row, prop],
        eventDate=day,
        live=live,
        ended=ended,
        tags=[{"slug": "tennis"}, {"slug": "games"}],
    )


def test_tennis_pages_filter_futures_and_use_polymarket_event_day(monkeypatch):
    next_match = fixture("atp-c-d-2026-11-27", 4, "2026-11-27 19:00:00+00")
    live_match = fixture("atp-a-b-2026-11-27", 5, "2026-11-27 17:00:00+00", live=True)
    finished = fixture("atp-e-f-2026-11-27", 6, "2026-11-27 16:00:00+00", ended=True)
    utc_next_day = fixture("atp-g-h-2026-11-28", 7, "2026-11-28 00:30:00+00")
    tomorrow = fixture(
        "atp-i-j-2026-11-28", 8, "2026-11-28 15:30:00+00", day="2026-11-28"
    )
    future = event(
        "2026-davis-cup-winner", [], eventDate="2026-11-27", tags=[{"slug": "tennis"}]
    )

    def fake_gamma(category, path, params, *, optional=False):
        assert category == "tennis"
        assert path == "/events/keyset"
        assert params["tag_slug"] == "tennis"
        assert params["end_date_min"] == "2026-11-27T05:00:00+00:00"
        if "after_cursor" not in params:
            return {
                "events": [future, finished, next_match],
                "next_cursor": "next-page",
            }
        assert params["after_cursor"] == "next-page"
        return {"events": [tomorrow, utc_next_day, live_match]}

    monkeypatch.setattr(markets, "_gamma", fake_gamma)
    now = epoch("2026-11-27T17:50:00Z")
    found = markets.discover({"tennis_limit": 3}, now)
    assert [row["slug"] for row in found] == [
        live_match["slug"],
        next_match["slug"],
        utc_next_day["slug"],
    ]
    assert found[2]["start_ts"] == epoch("2026-11-28T00:30:00Z")
    assert found[2]["end_ts"] == epoch("2026-12-04T17:00:00Z")
    assert set(found[2]["tokens"]) == {"Player A", "Player B"}
    assert markets.discover({"tennis_limit": 1}, now) == found[:1]


def test_overrides_add_a_market_or_event_and_deduplicate(monkeypatch):
    first = market(
        "event-first",
        10,
        events=[{"slug": "event"}],
        startDate="2026-11-27T00:00:00Z",
        endDate="2026-11-28T00:00:00Z",
        feesEnabled=False,
        feeSchedule=None,
    )
    second = {**first, **market("event-second", 11, closed=True)}
    first["outcomes"] = ["Yes", "No"]
    first["outcomePrices"] = [0.505, 0.495]

    def fake_gamma(category, path, params=None, *, optional=False):
        return {
            "/markets/slug/event-first": first,
            "/markets/slug/event": None,
            "/events/slug/event": event("event", [first, second]),
        }[path]

    monkeypatch.setattr(markets, "_gamma", fake_gamma)
    [found] = markets.discover(
        {"slug_overrides": ["event-first", "event"]}, epoch("2026-11-27T18:00:00Z")
    )
    assert found["slug"] == "event-first"
    assert found["event_slug"] == "event"
    assert found["fee_rate"] == 0.0


@pytest.mark.parametrize(
    ("changes", "error"),
    [
        ({"conditionId": "0xabcd"}, "condition ID"),
        ({"clobTokenIds": '["2", "2"]'}, "token IDs"),
        ({"clobTokenIds": "[2,3]"}, "token IDs"),
        ({"outcomes": '["Yes", "Yes"]'}, "outcomes"),
        ({"outcomePrices": '["0", "NaN"]'}, "finite"),
        ({"outcomePrices": '["1.01", "0"]'}, "outside"),
        ({"orderMinSize": 0}, "size or tick"),
        ({"orderPriceMinTickSize": 1}, "size or tick"),
        ({"feeSchedule": None}, "fee schedule"),
    ],
)
def test_invalid_market_metadata_raises(monkeypatch, changes, error):
    raw = market(
        "some-market",
        17,
        startDate="2026-11-27T00:00:00Z",
        endDate="2026-11-28T00:00:00Z",
        **changes,
    )
    monkeypatch.setattr(markets, "_gamma", lambda *args, **kwargs: raw)
    with pytest.raises(markets.DiscoveryError, match=error):
        markets.discover({"slug_overrides": ["some-market"]}, 0)


def test_temporary_network_failure_raises_and_the_next_attempt_recovers(monkeypatch):
    match = fixture("atp-a-b-2026-11-27", 18, "2026-11-27T19:00:00Z")
    failures = iter([True, False])

    def fake_request(url, *args, **kwargs):
        if url.endswith("/events/keyset"):
            if next(failures):
                raise markets.HttpError(503, url, "private response details")
            return {"events": [match]}
        slug = url.rsplit("/", 1)[1]
        return market(
            slug, 20, startDate="2026-11-27T00:00:00Z", endDate="2026-11-28T00:00:00Z"
        )

    monkeypatch.setattr(markets, "get_json", fake_request)
    config = {"tennis_limit": 10, "slug_overrides": ["another-market"]}
    now = epoch("2026-11-27T18:00:00Z")
    with pytest.raises(markets.DiscoveryError, match="Gamma HTTP 503") as caught:
        markets.discover(config, now)
    assert caught.value.category == "tennis"
    assert "private response details" not in str(caught.value)
    assert [row["slug"] for row in markets.discover(config, now)] == [
        match["slug"],
        "another-market",
    ]


def test_tennis_503_does_not_block_btc_group_rotation(monkeypatch):
    tennis_responses = iter([200, 503, 200])
    match = fixture("atp-a-b-2026-11-27", 21, "2026-11-27T19:00:00Z")

    def fake_request(url, *args, **kwargs):
        if url.endswith("/events/keyset"):
            status = next(tennis_responses)
            if status == 503:
                raise markets.HttpError(status, url, "response details")
            return {"events": [match]}
        slug = url.rsplit("/", 1)[1]
        if "temperature" in slug:
            raise markets.HttpError(404, url, "")
        return btc_event(slug)

    monkeypatch.setattr(markets, "get_json", fake_request)
    config = {
        "btc_windows_minutes": [5, 15],
        "tennis_limit": 10,
        "weather_cities": {"london": "Europe/London"},
    }
    boundary = epoch("2026-11-27T18:00:00Z")
    before, errors = markets.discover_groups(config, boundary - 1)
    assert errors == {}
    assert set(before) == {"btc5m", "btc15m", "weather", "tennis"}
    assert before["weather"] == []

    after, errors = markets.discover_groups(config, boundary)
    assert set(errors) == {"tennis"}
    assert "HTTP 503" in errors["tennis"]
    assert "response details" not in errors["tennis"]
    assert set(after) == {"btc5m", "btc15m", "weather"}
    for kind, width in (("btc5m", 300), ("btc15m", 900)):
        expired, preloaded = before[kind]
        current, upcoming = after[kind]
        assert current == preloaded
        assert upcoming["start_ts"] == boundary + width
        assert set(expired["tokens"].values()).isdisjoint(
            token for row in after[kind] for token in row["tokens"].values()
        )

    recovered, errors = markets.discover_groups(config, boundary + 1)
    assert errors == {}
    assert recovered["tennis"] == before["tennis"]


def test_missing_btc_window_fails_with_the_missing_slug(monkeypatch):
    def error(url, *args, **kwargs):
        raise markets.HttpError(404, url, "")

    monkeypatch.setattr(markets, "get_json", error)
    now = epoch("2026-11-27T18:00:00Z")
    with pytest.raises(markets.DiscoveryError, match=f"btc-updown-5m-{now}") as caught:
        markets.discover({"btc_windows_minutes": [5]}, now)
    assert caught.value.category == "btc5m"
