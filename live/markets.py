"""Discover the public Polymarket markets configured in markets.json.

BTC uses the half-open windows [start_ts, end_ts) containing now and immediately
following it. Weather uses each configured station's local calendar day and
tracks all open buckets for its daily high. Tennis uses Gamma's event date in
the New York calendar, prioritizes live matches and then scheduled start times,
and selects the main winner market. Its end_ts is Gamma's advertised market
expiry, which can be about a week after a match. Slug overrides add exact
market slugs or, if absent as a market, all open order books of an exact event.

Prices and limits are Gamma snapshots. The recorder's books and tick changes
supply execution prices and current ticks. All timestamps are UTC Unix seconds.
discover_groups returns successes and failures independently so callers can
preserve the last successful result for a failing category while retrying.
discover raises a DiscoveryError when any configured category fails.
"""

from __future__ import annotations

import re
from calendar import month_name
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta, timezone
from math import isfinite
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pmlab.gamma import GAMMA, jfield, tag_slugs
from pmlab.http import HttpError, get_json

_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_CONDITION = re.compile(r"0x[0-9A-Fa-f]{64}")
_TOKEN = re.compile(r"[1-9][0-9]{0,77}")
_BTC_WINDOWS = {5, 15}
_TENNIS_ZONE = ZoneInfo("America/New_York")


class DiscoveryError(RuntimeError):
    def __init__(self, category: str, detail: str):
        self.category = category
        super().__init__(f"{category}: {detail}")


def _gamma(category: str, path: str, params: dict | None = None, *, optional=False):
    try:
        return get_json(GAMMA + path, params, tries=1, timeout=5)
    except HttpError as exc:
        if optional and exc.code == 404:
            return None
        raise DiscoveryError(category, f"Gamma HTTP {exc.code} at {path}") from None
    except (OSError, RuntimeError, ValueError):
        raise DiscoveryError(category, f"Gamma request failed at {path}") from None


def _slug(value) -> bool:
    return isinstance(value, str) and _SLUG.fullmatch(value) is not None


def _exact(category: str, resource: str, slug: str, *, optional=False) -> dict | None:
    row = _gamma(category, f"/{resource}/slug/{slug}", optional=optional)
    if row is None and optional:
        return None
    if not isinstance(row, dict) or row.get("slug") != slug:
        raise DiscoveryError(
            category, f"Gamma returned an unexpected {resource} slug for {slug}"
        )
    return row


def _open(row: dict, category: str, *, market=False) -> bool:
    required = (
        ("active", "closed", "enableOrderBook", "acceptingOrders")
        if market
        else ("active", "closed")
    )
    if any(type(row.get(field)) is not bool for field in required):
        raise DiscoveryError(
            category, f"{row.get('slug', '<missing slug>')}: missing activity flags"
        )
    return (
        row["active"]
        and not row["closed"]
        and row.get("archived") is not True
        and (not market or row["enableOrderBook"] and row["acceptingOrders"])
    )


def _objects(value, category: str, field: str) -> list[dict]:
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise DiscoveryError(category, f"Gamma {field} is not an object list")
    return value


def _timestamp(value) -> int:
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        raise ValueError("expected a timestamp with a time zone")
    return int(timestamp.timestamp())


def _number(value) -> float:
    if type(value) not in (str, int, float):
        raise ValueError("expected a number")
    result = float(value)
    if not isfinite(result):
        raise ValueError("expected a finite number")
    return result


def _market(
    raw: dict,
    event_slug: str,
    kind: str,
    start_ts: int,
    end_ts: int,
    *,
    expected_outcomes: set[str] | None = None,
) -> dict:
    slug = raw.get("slug")
    condition = raw.get("conditionId")
    if (
        not _slug(slug)
        or not isinstance(condition, str)
        or not _CONDITION.fullmatch(condition)
    ):
        raise DiscoveryError(kind, f"{event_slug}: invalid market slug or condition ID")

    outcomes = jfield(raw.get("outcomes"))
    token_ids = jfield(raw.get("clobTokenIds"))
    quotes = jfield(raw.get("outcomePrices"))
    if (
        not isinstance(outcomes, list)
        or len(outcomes) != 2
        or any(
            not isinstance(outcome, str) or not outcome.strip() for outcome in outcomes
        )
        or len(set(outcomes)) != 2
        or expected_outcomes is not None
        and set(outcomes) != expected_outcomes
    ):
        raise DiscoveryError(kind, f"{slug}: unexpected outcomes")
    if (
        not isinstance(token_ids, list)
        or len(token_ids) != len(outcomes)
        or any(
            not isinstance(token, str)
            or not _TOKEN.fullmatch(token)
            or int(token).bit_length() > 256
            for token in token_ids
        )
        or len(set(token_ids)) != len(token_ids)
    ):
        raise DiscoveryError(kind, f"{slug}: invalid outcome token IDs")

    try:
        if not isinstance(quotes, list) or len(quotes) != len(outcomes):
            raise ValueError("missing outcome prices")
        prices = [_number(quote) for quote in quotes]
        if not all(0 <= price <= 1 for price in prices):
            raise ValueError("outcome price outside [0, 1]")
        min_size = _number(raw.get("orderMinSize"))
        tick = _number(raw.get("orderPriceMinTickSize"))
        if min_size <= 0 or not 0 < tick < 1:
            raise ValueError("invalid order size or tick")
        # Gamma's schedule is the coefficient for rate * p * (1 - p).
        fee = 0.0
        if raw.get("feesEnabled") is not False:
            schedule = raw.get("feeSchedule")
            if not isinstance(schedule, dict) or _number(schedule.get("exponent")) != 1:
                raise ValueError("missing or unsupported fee schedule")
            fee = _number(schedule.get("rate"))
            if not 0 <= fee <= 1:
                raise ValueError("fee rate outside [0, 1]")
        if end_ts <= start_ts:
            raise ValueError("end must be after start")
    except (TypeError, ValueError) as exc:
        raise DiscoveryError(kind, f"{slug}: {exc}") from None

    return {
        "slug": slug,
        "event_slug": event_slug,
        "condition_id": condition.lower(),
        "tokens": dict(zip(outcomes, token_ids)),
        "kind": kind,
        "start_ts": start_ts,
        "end_ts": end_ts,
        "fee_rate": fee,
        "min_size": min_size,
        "tick_size": tick,
        "prices": dict(zip(outcomes, prices)),
    }


def _event_times(raw: dict, category: str, start, end) -> tuple[int, int]:
    try:
        return _timestamp(start), _timestamp(end)
    except (AttributeError, OSError, OverflowError, TypeError, ValueError):
        raise DiscoveryError(
            category, f"{raw.get('slug')}: invalid event times"
        ) from None


def _btc(minutes: int, start: int) -> list[dict]:
    kind = f"btc{minutes}m"
    slug = f"btc-updown-{minutes}m-{start}"
    event = _exact(kind, "events", slug)
    if not _open(event, kind):
        raise DiscoveryError(kind, f"{slug}: window is inactive")
    markets = _objects(event.get("markets"), kind, "markets")
    if len(markets) != 1 or markets[0].get("slug") != slug:
        raise DiscoveryError(kind, f"{slug}: expected one market with the same slug")
    raw = markets[0]
    if not _open(raw, kind, market=True):
        raise DiscoveryError(kind, f"{slug}: window is unavailable for recording")
    expected = (start, start + minutes * 60)
    if (
        _event_times(event, kind, event.get("startTime"), event.get("endDate"))
        != expected
        or _event_times(raw, kind, raw.get("eventStartTime"), raw.get("endDate"))
        != expected
    ):
        raise DiscoveryError(
            kind, f"{slug}: dates disagree with the BTC window in its slug"
        )
    return [_market(raw, slug, kind, *expected, expected_outcomes={"Up", "Down"})]


def _midnight(day: date, zone: ZoneInfo) -> datetime:
    return datetime.combine(day, time.min, tzinfo=zone)


def _weather(city: str, zone: ZoneInfo, now: int) -> list[dict]:
    kind = "weather"
    day = datetime.fromtimestamp(now, zone).date()
    slug = f"highest-temperature-in-{city}-on-{month_name[day.month].lower()}-{day.day}-{day.year}"
    event = _exact(kind, "events", slug, optional=True)
    if event is None or not _open(event, kind):
        return []
    # The Gamma endDate is a noon UTC date marker. The weather rules use local days.
    start = int(_midnight(day, zone).timestamp())
    end = int(_midnight(day + timedelta(days=1), zone).timestamp())
    if event.get(
        "eventDate"
    ) != day.isoformat() or "daily-temperature" not in tag_slugs(event):
        raise DiscoveryError(kind, f"{slug}: unexpected weather day or event type")

    markets = []
    for raw in _objects(event.get("markets"), kind, "markets"):
        if not _open(raw, kind, market=True):
            continue
        if not _slug(raw.get("slug")) or not raw["slug"].startswith(slug + "-"):
            raise DiscoveryError(kind, f"{slug}: invalid temperature bucket slug")
        gamma_start, _ = _event_times(
            raw, kind, raw.get("eventStartTime"), raw.get("endDate")
        )
        if gamma_start != start:
            raise DiscoveryError(
                kind, f"{raw['slug']}: station midnight disagrees with Gamma"
            )
        markets.append(
            _market(raw, slug, kind, start, end, expected_outcomes={"Yes", "No"})
        )
    return markets


def _tennis(limit: int, now: int) -> list[dict]:
    kind = "tennis"
    day = datetime.fromtimestamp(now, _TENNIS_ZONE).date()
    # Gamma advertises market expiry up to a week after kick-off; use eventDate
    # and the games tag to distinguish today's fixtures from those expiry dates.
    params = {
        "tag_slug": "tennis",
        "closed": "false",
        "active": "true",
        "archived": "false",
        "order": "endDate,id",
        "ascending": "true",
        "limit": 50,
        "end_date_min": _midnight(day, _TENNIS_ZONE)
        .astimezone(timezone.utc)
        .isoformat(),
        "end_date_max": _midnight(day + timedelta(days=9), _TENNIS_ZONE)
        .astimezone(timezone.utc)
        .isoformat(),
    }
    matches = []
    seen_cursors = set()
    while True:
        response = _gamma(kind, "/events/keyset", params)
        if not isinstance(response, dict):
            raise DiscoveryError(kind, "Gamma returned an invalid event page")
        for event in _objects(response.get("events"), kind, "events"):
            if (
                event.get("eventDate") != day.isoformat()
                or event.get("ended") is True
                or not {"tennis", "games"} <= set(tag_slugs(event))
                or not _open(event, kind)
            ):
                continue
            slug = event.get("slug")
            if not _slug(slug):
                raise DiscoveryError(kind, "Gamma returned an unexpected fixture slug")
            for raw in _objects(event.get("markets"), kind, "markets"):
                if (
                    raw.get("slug") != slug
                    or raw.get("sportsMarketType") != "moneyline"
                ):
                    continue
                if not _open(raw, kind, market=True):
                    continue
                times = _event_times(
                    raw, kind, raw.get("gameStartTime"), raw.get("endDate")
                )
                if times[1] > now:
                    matches.append(
                        (
                            event.get("live") is not True,
                            _market(raw, slug, kind, *times),
                        )
                    )
        cursor = response.get("next_cursor")
        if cursor is None:
            break
        if not isinstance(cursor, str) or not cursor or cursor in seen_cursors:
            raise DiscoveryError(kind, "Gamma returned an invalid pagination cursor")
        seen_cursors.add(cursor)
        params["after_cursor"] = cursor
    matches.sort(key=lambda entry: (entry[0], entry[1]["start_ts"], entry[1]["slug"]))
    return [market for _, market in matches[:limit]]


def _override(slug: str) -> list[dict]:
    kind = "override"
    raw = _exact(kind, "markets", slug, optional=True)
    if raw is None:
        event = _exact(kind, "events", slug)
        if not _open(event, kind):
            return []
        rows = _objects(event.get("markets"), kind, "markets")
        event_slug = slug
    else:
        rows = [raw]
        parents = _objects(raw.get("events", []), kind, "events")
        event_slug = parents[0].get("slug") if parents else slug
        if not _slug(event_slug):
            raise DiscoveryError(kind, f"{slug}: invalid parent event slug")

    markets = []
    for raw in rows:
        if _open(raw, kind, market=True):
            times = _event_times(
                raw,
                kind,
                raw.get("eventStartTime")
                or raw.get("gameStartTime")
                or raw.get("startDate"),
                raw.get("endDate"),
            )
            markets.append(_market(raw, event_slug, kind, *times))
    return markets


def _unique(markets) -> list[dict]:
    by_condition = {}
    for market in markets:
        old = by_condition.setdefault(market["condition_id"], market)
        if old["slug"] != market["slug"] or old["tokens"] != market["tokens"]:
            raise DiscoveryError(
                market["kind"], f"{market['slug']}: conflicting condition ID"
            )
    return list(by_condition.values())


def _discover_groups(
    config: dict, now: int
) -> tuple[dict[str, list[dict]], dict[str, DiscoveryError]]:
    if not isinstance(config, dict):
        raise DiscoveryError("config", "config must be an object")
    windows = config.get("btc_windows_minutes", [])
    cities = config.get("weather_cities", {})
    tennis_limit = config.get("tennis_limit", 0)
    overrides = config.get("slug_overrides", [])
    if not isinstance(windows, list) or any(
        type(m) is not int or m not in _BTC_WINDOWS for m in windows
    ):
        raise DiscoveryError(
            "config", "btc_windows_minutes must be a list of 5 and/or 15"
        )
    if not isinstance(cities, dict) or any(
        not _slug(city) or not isinstance(zone, str) for city, zone in cities.items()
    ):
        raise DiscoveryError(
            "config", "weather_cities must map city slugs to IANA time zones"
        )
    if type(tennis_limit) is not int or tennis_limit < 0:
        raise DiscoveryError("config", "tennis_limit must be a nonnegative integer")
    if not isinstance(overrides, list) or any(not _slug(slug) for slug in overrides):
        raise DiscoveryError("config", "slug_overrides must be a list of exact slugs")
    if type(now) is not int:
        raise DiscoveryError("config", "now must be integer Unix seconds")

    try:
        zones = {city: ZoneInfo(name) for city, name in cities.items()}
    except (ValueError, ZoneInfoNotFoundError):
        raise DiscoveryError(
            "config", "weather_cities contains an invalid IANA time zone"
        ) from None

    groups = {}
    errors = {}
    # Each BTC group publishes both of its windows together. Other configured
    # groups may still refresh if one group cannot produce a complete result.
    with ThreadPoolExecutor(max_workers=6) as pool:
        jobs = {}
        for minutes in dict.fromkeys(windows):
            width = minutes * 60
            start = now // width * width
            jobs[f"btc{minutes}m"] = [
                pool.submit(_btc, minutes, boundary)
                for boundary in (start, start + width)
            ]
        if zones:
            jobs["weather"] = [
                pool.submit(_weather, city, zone, now) for city, zone in zones.items()
            ]
        if tennis_limit:
            jobs["tennis"] = [pool.submit(_tennis, tennis_limit, now)]
        if overrides:
            jobs["override"] = [
                pool.submit(_override, slug) for slug in dict.fromkeys(overrides)
            ]

        for kind, futures in jobs.items():
            try:
                groups[kind] = _unique(
                    market for future in futures for market in future.result()
                )
            except DiscoveryError as exc:
                errors[kind] = exc
            except (AttributeError, KeyError, TypeError, ValueError, OverflowError):
                errors[kind] = DiscoveryError(kind, "invalid Gamma market metadata")
    return groups, errors


def discover_groups(
    config: dict, now: int
) -> tuple[dict[str, list[dict]], dict[str, str]]:
    """Return successful category snapshots and categorized failure messages.

    Enabled successful categories are present even when empty. Failed categories
    appear only in the error map. Disabled categories appear in neither map.
    Overrides are independent and may overlap an automatic category.
    """
    groups, errors = _discover_groups(config, now)
    return groups, {kind: str(error) for kind, error in errors.items()}


def discover(config: dict, now: int) -> list[dict]:
    """Return unique configured markets or raise on any discovery failure."""
    groups, errors = _discover_groups(config, now)
    if errors:
        raise next(iter(errors.values()))
    return _unique(market for markets in groups.values() for market in markets)
