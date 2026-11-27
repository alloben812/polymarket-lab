"""Public market recorder. Run 'python -m live.record record|status' from the repository."""

import argparse
import asyncio
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path
import signal
import shutil
import time
from uuid import uuid4

from websockets.asyncio.client import connect

from .book import BookReplay
from .doctor import WS
from .journal import Journal, atomic_json
from .markets import discover_groups
from .reference import get_json, reference_btc, resolutions

HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = HERE.parent / "data/live"


class Recorder:
    def __init__(self, journal, config):
        self.log = journal
        self.config = config
        self.catalog = {}
        self.groups = {}
        self.session = ""
        self.active = set()
        self.last_seen = 0
        self.last_pong = 0
        self.last_change = {}
        self.confirmed = {}
        self.audit_counts = Counter()
        self.reasons = Counter()
        self.replay = BookReplay()
        self.resolved = set()
        self.pending = {}
        self.discovered = asyncio.Event()
        self.stop = asyncio.Event()
        self.watch_sessions = set()
        self.since = time.monotonic()
        self.status_detail = ""
        self.expected = {}
        self.end_reason = "interrupted"

    def emit(self, kind, *, session=None, **fields):
        row = self.log.put(kind, self.session if session is None else session, **fields)
        self.replay.apply(row)
        return row["recv_ns"]

    def gap(self, reason, tokens, since=None, *, session=None):
        self.reasons[reason] += 1
        self.emit(
            "gap",
            session=session,
            tokens=sorted(tokens),
            reason=reason,
            since_ns=since or self.last_seen or time.time_ns(),
        )

    async def discovery(self):
        while True:
            try:
                updates, errors = await asyncio.to_thread(
                    discover_groups, self.config, int(time.time())
                )
                self.groups.update(updates)
                current = {}
                for key in sorted(self.groups, key=lambda group: group == "override"):
                    for m in self.groups[key]:
                        slug = m["slug"]
                        if (
                            slug in current
                            and current[slug]["condition_id"] != m["condition_id"]
                        ):
                            raise ValueError("conflicting identities for market slug")
                        current.setdefault(slug, m)
                for slug, m in current.items():
                    if slug not in self.catalog:
                        self.emit("market", market=m)
                        self.pending[slug] = m
                self.catalog = current
                self.expected = dict(Counter(m["kind"] for m in current.values()))
                self.status_detail = ",".join(sorted(errors))
                for group in errors:
                    self.emit(
                        "discovery_error", group=group, reason="public_discovery_failed"
                    )
                if not current:
                    raise ValueError("empty universe")
                self.discovered.set()
            except Exception as err:
                self.status_detail = type(err).__name__
                self.emit("discovery_error", reason=type(err).__name__)
            await asyncio.sleep(20 if self.status_detail else 40)

    def wanted(self):
        now = time.time()
        return {
            token
            for m in self.catalog.values()
            if not m.get("end_ts") or m["end_ts"] > now
            for token in m["tokens"].values()
        }

    async def market_socket(self):
        await self.discovered.wait()
        retry = 1
        while True:
            self.session = uuid4().hex[:12]
            self.watch_sessions.add(self.session)
            self.active = set()
            try:
                async with connect(
                    WS,
                    open_timeout=10,
                    close_timeout=2,
                    max_size=16 * 1024 * 1024,
                    max_queue=128,
                    ping_interval=None,
                ) as socket:
                    self.active = self.wanted()
                    if not self.active:
                        raise ValueError("no valid markets")
                    await socket.send(
                        json.dumps(
                            {
                                "assets_ids": sorted(self.active),
                                "type": "market",
                                "custom_feature_enabled": True,
                            }
                        )
                    )
                    self.last_seen = self.emit("connected", tokens=sorted(self.active))
                    self.last_pong = 0
                    last_ping = time.monotonic()
                    waiting_pong = False
                    next_rotation = time.monotonic() + 3
                    while True:
                        tick = time.monotonic()
                        if tick - last_ping >= 8:
                            if waiting_pong:
                                raise TimeoutError("no market pong")
                            await socket.send("PING")
                            last_ping, waiting_pong = tick, True
                        if tick >= next_rotation:
                            next_rotation = tick + 2
                            wanted = self.wanted()
                            for op, tokens in [
                                ("unsubscribe", self.active - wanted),
                                ("subscribe", wanted - self.active),
                            ]:
                                if not tokens:
                                    continue
                                await socket.send(
                                    json.dumps(
                                        {
                                            "operation": op,
                                            "assets_ids": sorted(tokens),
                                            "custom_feature_enabled": True,
                                        }
                                    )
                                )
                                if op == "subscribe":
                                    self.active.update(tokens)
                                    self.emit("connected", tokens=sorted(tokens))
                                else:
                                    self.gap("unsubscribed", tokens, time.time_ns())
                                    self.active.difference_update(tokens)
                        try:
                            raw = await asyncio.wait_for(socket.recv(), timeout=1)
                        except TimeoutError:
                            continue
                        if raw == "PONG":
                            self.last_seen = self.emit("heartbeat", status="pong")
                            self.last_pong = self.last_seen
                            waiting_pong, retry = False, 1
                            continue
                        if raw == "PING":
                            await socket.send("PONG")
                            continue
                        events = json.loads(raw)
                        for e in events if isinstance(events, list) else [events]:
                            typ = e.get("event_type")
                            if typ in (
                                "book",
                                "last_trade_price",
                                "best_bid_ask",
                                "tick_size_change",
                            ):
                                if e.get("asset_id") not in self.active:
                                    continue
                            elif typ == "price_change":
                                changes = [
                                    c
                                    for c in e["price_changes"]
                                    if c["asset_id"] in self.active
                                ]
                                if not changes:
                                    continue
                                e = {**e, "price_changes": changes}
                            elif typ == "market_resolved":
                                condition = e.get("market") or e.get("condition_id")
                                if not self.active.intersection(
                                    e.get("assets_ids", [])
                                ) and not any(
                                    m["condition_id"] == condition
                                    and self.active.intersection(m["tokens"].values())
                                    for m in self.catalog.values()
                                ):
                                    continue
                            else:
                                continue
                            self.last_seen = self.emit(
                                "ws", source="websocket", payload=e
                            )
                            if typ == "book":
                                self.last_change[e["asset_id"]] = self.last_seen
                                if self.replay.status_for(e["asset_id"]) == "ok":
                                    self.confirmed[e["asset_id"]] = self.last_seen
                            elif typ == "price_change":
                                for c in e["price_changes"]:
                                    self.last_change[c["asset_id"]] = self.last_seen
                            elif typ == "best_bid_ask":
                                self.last_change[e["asset_id"]] = self.last_seen
            except Exception as err:
                self.gap("socket_" + type(err).__name__, self.active)
                self.active.clear()
                await asyncio.sleep(retry)
                retry = min(20, retry * 2)

    async def audit(self):
        # Compare independent REST state only when no WS mutation for this token
        # was processed during the request. Moving books cannot be verified this way.
        while True:
            await asyncio.sleep(12)
            tokens = sorted(self.active)
            session = self.session
            if not tokens:
                continue
            start = time.time_ns()
            try:
                replies = await asyncio.to_thread(
                    get_json,
                    "https://clob.polymarket.com/books",
                    [{"token_id": t} for t in tokens],
                )
                counts = Counter()
                for reply in replies:
                    t = reply["asset_id"]
                    if (
                        t not in self.active
                        or self.session != session
                        or self.last_change.get(t, 0) >= start
                    ):
                        counts["changed_during_request"] += 1
                        continue
                    q = self.replay.quote(t)
                    exch = int(reply["timestamp"])
                    if q.book_exchange_ms is not None and exch < q.book_exchange_ms:
                        counts["older_rest"] += 1
                        continue

                    def levels(side, reverse):
                        return tuple(
                            sorted(
                                (
                                    (Decimal(v["price"]), Decimal(v["size"]))
                                    for v in reply[side]
                                    if Decimal(v["size"]) > 0
                                ),
                                reverse=reverse,
                            )
                        )

                    if (
                        q.status == "ok"
                        and q.bids == levels("bids", True)
                        and q.asks == levels("asks", False)
                    ):
                        counts["matched"] += 1
                        self.confirmed[t] = start
                    else:
                        if q.status == "ok":
                            self.gap(
                                "rest_book_disagrees", [t], self.confirmed.get(t, start)
                            )
                            counts["disagreed"] += 1
                        checkpoint = self.emit(
                            "ws",
                            source="rest_checkpoint",
                            payload={**reply, "event_type": "book"},
                        )
                        if self.replay.status_for(t) == "ok":
                            self.confirmed[t] = checkpoint
                            if q.status != "ok":
                                counts["recovered_unknown"] += 1
                        else:
                            counts["checkpoint_rejected"] += 1
                self.audit_counts.update(counts)
                self.emit(
                    "audit",
                    counts=dict(counts),
                    requested=len(tokens),
                    returned=len(replies),
                )
            except Exception as err:
                self.emit("audit_error", reason=type(err).__name__)

    def status(self, state):
        info = {
            "run": self.log.run.name,
            "state": state,
            "start_ns": self.log.start,
            "updated_ns": time.time_ns(),
            "elapsed_s": round(time.monotonic() - self.since, 2),
            "counts": dict(self.log.counts),
            "ws_events": dict(self.log.types),
            "categories": self.expected,
            "active_tokens": len(self.active),
            "last_pong_ns": self.last_pong,
            "gap_reasons": dict(self.reasons),
            "rest_audit": dict(self.audit_counts),
            "discovery_error": self.status_detail,
        }
        atomic_json(self.log.run / "status.json", info)
        return info

    async def watchdog(self):
        prev = time.time() - time.monotonic()
        last = time.monotonic()
        previous_wall_ns = time.time_ns()
        self.watch_sessions.add(self.session)
        while True:
            await asyncio.sleep(3)
            now = time.monotonic()
            difference = time.time() - now
            if now - last > 10 or abs(difference - prev) > 0.25:
                # A rotation or a reconnect may run first after the Mac wakes.
                # An empty token list covers the entire session at the earlier time.
                for session in sorted(self.watch_sessions | {self.session}):
                    if session:
                        self.gap(
                            "local_clock_or_processing_pause",
                            [],
                            min(previous_wall_ns, self.last_seen or previous_wall_ns),
                            session=session,
                        )
            self.watch_sessions = {self.session}
            prev, last = difference, now
            previous_wall_ns = time.time_ns()
            self.log.flush()
            if shutil.disk_usage(self.log.run).free < 2 * 1024**3:
                self.end_reason = "low_disk_space"
                self.stop.set()
            self.status("running")

    async def run(self, duration):
        self.status("starting")
        work = [
            asyncio.create_task(fn)
            for fn in [
                self.discovery(),
                self.market_socket(),
                self.audit(),
                self.watchdog(),
                reference_btc(self.log),
                resolutions(self.log, self.resolved, self.pending),
            ]
        ]
        waiter = asyncio.create_task(self.stop.wait())
        normal = False
        try:
            done, _ = await asyncio.wait(
                [*work, waiter], timeout=duration, return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                if task is not waiter:
                    task.result()
                    raise RuntimeError("recorder worker unexpectedly finished")
            normal = not done
        except Exception as err:
            self.end_reason = "failed_" + type(err).__name__
            raise
        finally:
            for task in [*work, waiter]:
                task.cancel()
            await asyncio.gather(*work, waiter, return_exceptions=True)
            self.emit(
                "stop",
                tokens=sorted(self.active),
                reason="duration" if normal else self.end_reason,
            )
            self.log.seal()
            self.status("complete" if normal else self.end_reason)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    rec = sub.add_parser("record")
    rec.add_argument("--config", type=Path, default=HERE / "markets.json")
    rec.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    rec.add_argument("--seconds", type=int, default=7200)
    st = sub.add_parser("status")
    st.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = p.parse_args()
    if args.cmd == "status":
        files = sorted(args.root.glob("*/status.json"))
        if not files:
            p.error("no capture status")
        info = json.loads(files[-1].read_text())
        if (
            info["state"] in ("starting", "running")
            and time.time_ns() - info["updated_ns"] > 20_000_000_000
        ):
            info["state"] = "stale"
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return
    if args.seconds <= 0:
        p.error("seconds must be positive")
    recorder = Recorder(Journal(args.root), json.loads(args.config.read_text()))

    async def record():
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, recorder.stop.set)
        await recorder.run(args.seconds)

    asyncio.run(record())


if __name__ == "__main__":
    main()
