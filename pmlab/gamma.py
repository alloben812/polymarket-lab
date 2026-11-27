"""Gamma API (market and event metadata). Public, read-only."""
from __future__ import annotations

import json
import re
from typing import Iterator

from .http import get_json

GAMMA = "https://gamma-api.polymarket.com"


def jfield(v):
    """Gamma returns some list fields (outcomes, clobTokenIds, outcomePrices) as JSON strings."""
    if isinstance(v, str):
        try:
            return json.loads(v)
        except ValueError:
            return v
    return v


def market_by_slug(slug: str, cache: bool = False) -> dict | None:
    for closed in ("true", "false"):
        rows = get_json(f"{GAMMA}/markets", {"slug": slug, "closed": closed, "include_tag": "true"}, cache=cache and closed == "true")
        if rows:
            return rows[0]
    return None


def event_by_slug(slug: str, cache: bool = False) -> dict | None:
    for closed in ("true", "false"):
        rows = get_json(f"{GAMMA}/events", {"slug": slug, "closed": closed}, cache=cache and closed == "true")
        if rows:
            return rows[0]
    return None


def markets_by_condition(condition_ids: list[str], cache: bool = True, batch: int = 20) -> dict[str, dict]:
    """condition id -> market metadata (with tags). Looks in closed and open markets."""
    out: dict[str, dict] = {}
    ids = list(dict.fromkeys(condition_ids))
    for i in range(0, len(ids), batch):
        chunk = ids[i:i + batch]
        for closed in ("true", "false"):
            want = [c for c in chunk if c not in out]
            if not want:
                break
            params = [("condition_ids", c) for c in want] + [("include_tag", "true"), ("closed", closed), ("limit", str(len(want)))]
            rows = get_json(f"{GAMMA}/markets", params, cache=cache and closed == "true")
            for m in rows or []:
                out[m["conditionId"]] = m
    return out


def iter_markets(max_pages: int = 10_000, **filters) -> Iterator[dict]:
    """Keyset walk over /markets/keyset. Example: iter_markets(closed="true", end_date_min="2026-11-01T00:00:00Z")."""
    params = {"limit": 500, **filters}
    cursor = None
    for _ in range(max_pages):
        d = get_json(f"{GAMMA}/markets/keyset", {**params, "after_cursor": cursor})
        rows = d.get("markets") or []
        yield from rows
        cursor = d.get("next_cursor")
        if not cursor or not rows:
            return


def iter_events(max_pages: int = 10_000, **filters) -> Iterator[dict]:
    """Keyset walk over /events/keyset. Example: iter_events(closed="true", tag_slug="weather")."""
    params = {"limit": 100, **filters}
    cursor = None
    for _ in range(max_pages):
        d = get_json(f"{GAMMA}/events/keyset", {**params, "after_cursor": cursor})
        rows = d.get("events") or []
        yield from rows
        cursor = d.get("next_cursor")
        if not cursor or not rows:
            return


def resolve_profile(ref: str) -> tuple[str, str]:
    """Profile name or 0x address -> (display name, proxy wallet)."""
    if ref.lower().startswith("0x") and len(ref) == 42:
        return ref, ref.lower()
    d = get_json(f"{GAMMA}/public-search", {"q": ref, "search_profiles": "true", "limit_per_type": 10})
    profs = d.get("profiles") or []
    exact = [p for p in profs if (p.get("name") or "").lower() == ref.lower()]
    pick = (exact or profs or [None])[0]
    if not pick:
        raise LookupError(f"profile not found: {ref}")
    return pick.get("name"), pick.get("proxyWallet")


def tag_slugs(market: dict) -> list[str]:
    return [t.get("slug") for t in (market.get("tags") or []) if t.get("slug")]


_UPDOWN = re.compile(r"^([a-z0-9]+)-updown-(\d+[mh])-(\d{9,})$")
_CATEGORY_TAGS = [  # first match wins; order matters
    ("crypto", {"crypto", "crypto-prices", "bitcoin", "ethereum", "solana", "xrp"}),
    ("sports", {"sports", "nba", "nfl", "soccer", "mlb", "nhl", "tennis", "ufc", "esports", "cricket", "golf", "f1"}),
    ("weather", {"weather"}),
    ("economics", {"economics", "economy", "fed", "macro-indicators", "inflation", "fed-rates"}),
    ("finance", {"finance", "stocks", "earnings", "equities", "indices", "commodities"}),
    ("mentions", {"mentions"}),
    ("politics", {"politics", "elections", "geopolitics", "world"}),
    ("tech", {"tech", "ai", "big-tech"}),
    ("culture", {"culture", "pop-culture", "movies", "music"}),
]


def family(market: dict) -> str:
    """Short label for grouping markets: recurring crypto series by name, otherwise a coarse category."""
    slug = market.get("slug") or ""
    m = _UPDOWN.match(slug)
    if m:
        return f"{m.group(1)}-updown-{m.group(2)}"
    tags = set(tag_slugs(market))
    for name, keys in _CATEGORY_TAGS:
        if tags & keys:
            return name
    return "other"


def updown_start(slug: str) -> int | None:
    m = _UPDOWN.match(slug or "")
    return int(m.group(3)) if m else None
