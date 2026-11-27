"""The recorder can recover a fresh snapshot after an unexpected socket close."""

import asyncio
from contextlib import asynccontextmanager
import json
from unittest.mock import patch

from live.book import iter_records
from live.journal import Journal
from live.record import Recorder


def test_reconnect_records_unknown_interval(tmp_path):
    async def exercise():
        journal = Journal(tmp_path)
        rec = Recorder(journal, {})
        rec.catalog["m"] = {"end_ts": 9999999999, "tokens": {"Up": "1"}}
        rec.discovered.set()
        second = asyncio.Event()
        tokens = []

        class Fake:
            def __init__(self, n):
                self.n = n
                self.calls = 0

            async def send(self, message):
                if message != "PING":
                    tokens.append(json.loads(message)["assets_ids"])

            async def recv(self):
                self.calls += 1
                if self.calls == 1:
                    return json.dumps(
                        {
                            "event_type": "book",
                            "asset_id": "1",
                            "timestamp": str(self.n),
                            "bids": [{"price": "0.4", "size": "10"}],
                            "asks": [{"price": "0.6", "size": str(10 * self.n)}],
                        }
                    )
                if self.n == 1:
                    raise ConnectionResetError()
                second.set()
                await asyncio.Future()

        @asynccontextmanager
        async def dial(*args, **kwargs):
            yield Fake(len(tokens) + 1)

        with patch("live.record.connect", dial):
            job = asyncio.create_task(rec.market_socket())
            await asyncio.wait_for(second.wait(), timeout=4)
            job.cancel()
            await asyncio.gather(job, return_exceptions=True)
        journal.seal()
        rows = list(iter_records(sorted(journal.run.glob("*.gz"))))
        assert [r["kind"] for r in rows] == [
            "connected",
            "ws",
            "gap",
            "connected",
            "ws",
        ]
        assert rows[1]["recv_ns"] == rows[2]["since_ns"]
        assert rows[1]["session"] != rows[-1]["session"]
        assert tokens == [["1"], ["1"]]
        assert rec.replay.quote("1").asks[0][1] == 20

    asyncio.run(exercise())


def test_watchdog_marks_previous_wall_time_after_buffered_receive(tmp_path):
    from unittest.mock import AsyncMock
    from live import record

    async def test():
        journal = Journal(tmp_path)
        rec = Recorder(journal, {})
        rec.session = "s"
        rec.active = {"a"}
        rec.last_seen = 1011_000_000_000
        gaps = []
        rec.gap = lambda reason, tokens, since: gaps.append((reason, since))
        rec.status = lambda state: None

        class Halt(BaseException):
            pass

        with (
            patch.object(record, "time") as clock,
            patch.object(record.asyncio, "sleep", AsyncMock(side_effect=[None, Halt])),
        ):
            clock.time.side_effect = [1000.0, 1011.0]
            clock.monotonic.side_effect = [100.0, 100.0, 111.0]
            clock.time_ns.side_effect = [1000_000_000_000, 1011_000_000_000]
            try:
                await rec.watchdog()
            except Halt:
                pass
        assert gaps == [("local_clock_or_processing_pause", 1000_000_000_000)]

    asyncio.run(test())


def test_long_span_without_pongs_cannot_certify_recording():
    from live.validate import inspect

    rows = [
        ("connected", 1, {"tokens": ["1"]}),
        (
            "ws",
            2,
            {
                "source": "websocket",
                "payload": {"event_type": "book", "asset_id": "1", "market": "c"},
            },
        ),
        (
            "ws",
            3,
            {
                "source": "websocket",
                "payload": {
                    "event_type": "price_change",
                    "market": "c",
                    "price_changes": [{"asset_id": "1"}],
                },
            },
        ),
        (
            "ws",
            7203,
            {
                "source": "websocket",
                "payload": {
                    "event_type": "last_trade_price",
                    "asset_id": "1",
                    "market": "c",
                },
            },
        ),
        ("stop", 7204, {"reason": "duration"}),
    ]
    report = inspect(
        dict(kind=k, recv_ns=t * 10**9, session="s", ordinal=n, **f)
        for n, (k, t, f) in enumerate(rows, 1)
    )
    assert report["observed_seconds"] == 7201
    assert (
        report["errors"]["no_heartbeat"]
        and report["errors"]["unaccounted_pong_gap_over_20s"]
    )
    assert report["errors"]["reference_does_not_cover_capture"]
    assert report["errors"]["missing_complete_btc5m_window"] > 0
