"""Verify a sealed capture independently of the recorder's status counters."""

import argparse
from collections import Counter
import json
from pathlib import Path

from .book import coverage, iter_records

BILLION = 1_000_000_000


def _scan(rows, markets, report):
    counts, events, gaps, bad, categories = (Counter() for _ in range(5))
    tokens, sessions, heartbeats = {}, {}, {}
    last_reference = None
    anchored = set()
    subscribed = set()
    market_events = Counter()
    first_reference = None
    last_audit = None
    audit_count = 0
    first_ws = last_ws = last_recv = None
    candle_count = 0
    largest_gap = 0
    reanchors = Counter()
    max_feed_lag_ms = 0
    previous = None
    stop = None
    for r in rows:
        kind, now, session = r["kind"], r["recv_ns"], r["session"]
        ordinal = r["ordinal"]
        if ordinal != (1 if previous is None else previous + 1):
            bad["missing_local_records"] += 1
        if stop is not None:
            bad["records_after_stop"] += 1
        previous = ordinal
        counts[kind] += 1
        last_recv = now
        if kind == "market":
            m = r["market"]
            markets[m["slug"]] = m
            categories[m["kind"]] += 1
            for token in m["tokens"].values():
                if token in tokens and tokens[token] != m["condition_id"]:
                    bad["conflicting_token"] += 1
                tokens[token] = m["condition_id"]
        elif kind == "connected":
            active = sessions.setdefault(session, set())
            active.update(r["tokens"])
            subscribed.update(r["tokens"])
            if any(t not in tokens for t in r["tokens"]):
                bad["unannounced_subscription"] += 1
            heartbeats.setdefault(session, now)
        elif kind == "gap":
            gaps[r["reason"]] += 1
            if r["since_ns"] > now:
                bad["invalid_gap_bounds"] += 1
            if r["reason"].startswith("socket_"):
                sessions.pop(session, None)
                heartbeats.pop(session, None)
            if r["reason"] == "unsubscribed":
                sessions.get(session, set()).difference_update(r["tokens"])
        elif kind == "heartbeat":
            if r.get("status") != "pong":
                bad["invalid_heartbeat"] += 1
            prior = heartbeats.get(session, now)
            largest_gap = max(largest_gap, now - prior)
            if now - prior > 20 * BILLION:
                bad["unaccounted_pong_gap_over_20s"] += 1
            heartbeats[session] = now
        elif kind == "audit":
            audit_count += 1
            last_audit = now
        elif kind == "ws":
            payload = r["payload"]
            name = payload["event_type"]
            events[name] += 1
            if name == "book":
                reanchors[r.get("source", "websocket")] += 1
                anchored.add(payload["asset_id"])
            if r.get("source") != "rest_checkpoint":
                first_ws = now if first_ws is None else first_ws
                last_ws = now
                if payload.get("timestamp"):
                    max_feed_lag_ms = max(
                        max_feed_lag_ms, now // 1_000_000 - int(payload["timestamp"])
                    )
            ids = (
                [v["asset_id"] for v in payload["price_changes"]]
                if name == "price_change"
                else [payload.get("asset_id")]
            )
            if any(t and t not in sessions.get(session, set()) for t in ids):
                bad["unsubscribed_market_event"] += 1
            if payload.get("market"):
                market_events[payload["market"]] += 1
            if any(t and tokens.get(t) != payload.get("market") for t in ids):
                bad["wrong_market_event"] += 1
        elif kind == "reference":
            if r["bars"] and first_reference is None:
                first_reference = r["bars"][0][0]
            for sec, price in r["bars"]:
                if last_reference is not None and sec != last_reference + 1:
                    bad["nonconsecutive_reference"] += 1
                if float(price) <= 0 or (sec + 1) * BILLION > now:
                    bad["invalid_or_future_candle"] += 1
                last_reference = sec
                candle_count += 1
        elif kind == "stop":
            stop = r.get("reason")
            for start in heartbeats.values():
                delta = now - start
                largest_gap = max(largest_gap, delta)
                if delta > 20 * BILLION:
                    bad["unaccounted_pong_gap_over_20s"] += 1
        yield r
    if first_ws and last_ws:
        observed = last_ws - first_ws
        if observed > 20 * BILLION and not counts["heartbeat"]:
            bad["no_heartbeat"] += 1
        if (
            not first_reference
            or not last_reference
            or first_reference > first_ws // BILLION
            or last_ws // BILLION - last_reference > 10
        ):
            bad["reference_does_not_cover_capture"] += 1
        if observed > 30 * BILLION and (
            not audit_count or last_ws - (last_audit or 0) > 40 * BILLION
        ):
            bad["no_recent_independent_audit"] += 1
        for t in subscribed - anchored:
            bad["subscribed_token_without_book"] += 1
        for tf, dur in [("btc5m", 300), ("btc15m", 900)]:
            starts = {m["start_ts"] for m in markets.values() if m["kind"] == tf}
            first = (first_ws + dur * BILLION - 1) // (dur * BILLION) * dur
            for start in range(first, last_ws // BILLION - dur + 1, dur):
                if start in starts:
                    m = next(
                        m
                        for m in markets.values()
                        if m["kind"] == tf and m["start_ts"] == start
                    )
                    if (
                        not set(m["tokens"].values()).issubset(anchored & subscribed)
                        or not market_events[m["condition_id"]]
                    ):
                        bad["no_books_" + tf + "_window"] += 1
                else:
                    bad["missing_complete_" + tf + "_window"] += 1
    report.update(
        {
            "records": sum(counts.values()),
            "counts": dict(counts),
            "events": dict(events),
            "token_count": len(tokens),
            "markets_by_kind": dict(categories),
            "gap_reasons": dict(gaps),
            "first_ws_ns": first_ws,
            "last_ws_ns": last_ws,
            "last_recv_ns": last_recv,
            "observed_seconds": round((last_ws - first_ws) / BILLION, 3)
            if last_ws and first_ws
            else 0,
            "max_pong_spacing_s": round(largest_gap / BILLION, 3),
            "max_ws_message_age_ms": max_feed_lag_ms,
            "full_book_anchors": dict(reanchors),
            "binance_seconds": candle_count,
            "subscribed_tokens": len(subscribed),
            "anchored_tokens": len(anchored),
            "stop": stop,
            "errors": dict(bad),
        }
    )


def inspect(rows):
    """Check ordering and measure usable depth inside each complete BTC window."""
    markets, report = {}, {}
    books = coverage(_scan(rows, markets, report))
    complete = []
    first, last = report["first_ws_ns"], report["last_ws_ns"]
    errors = Counter(report["errors"])
    for m in markets.values():
        if m["kind"] not in ("btc5m", "btc15m"):
            continue
        start, end = m["start_ts"] * BILLION, m["end_ts"] * BILLION
        if first is None or first > start or last < end:
            continue
        per_side = {}
        for side, token in m["tokens"].items():
            times = books.tokens[token].intervals
            known = sum(max(0, min(b + 1, end) - max(a, start)) for a, b in times)
            per_side[side] = round(100 * known / (end - start), 3)
            if not known:
                errors["no_in_window_depth_" + m["kind"]] += 1
        complete.append({"slug": m["slug"], "known_depth_pct": per_side})
    report["complete_btc_windows"] = complete
    report["errors"] = dict(errors)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run", type=Path)
    p.add_argument("--minimum-seconds", type=int, default=0)
    args = p.parse_args()
    files = sorted(args.run.glob("*.jsonl.gz"))
    report = inspect(iter_records(files))
    print(json.dumps(report, indent=2))
    if (
        not files
        or report["errors"]
        or report["observed_seconds"] < args.minimum_seconds
        or report["stop"] != "duration"
        or not {"book", "price_change", "last_trade_price"}.issubset(report["events"])
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
