"""Append-only market tape. Each sealed minute contains complete gzip members."""

import gzip
import json
import os
import time
import uuid
from collections import Counter
from datetime import datetime, timezone


def atomic_json(path, value):
    tmp = path.with_suffix(".tmp")
    with tmp.open("w") as f:
        json.dump(value, f, separators=(",", ":"), allow_nan=False)
    os.replace(tmp, path)


class Journal:
    def __init__(self, root):
        root.mkdir(parents=True, exist_ok=True)
        self.run = (
            root / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:6]}"
        )
        self.run.mkdir()
        self.counts = Counter()
        self.types = Counter()
        self.start = time.time_ns()
        self.previous_ns = 0
        self.chunk = bytearray()
        self.file = None
        self.minute = None
        self.ordinal = 0
        self.last_flush = time.monotonic()
        self.listener = None

    def put(self, kind, session="", **fields):
        observed = time.time_ns()
        # Local receipt order is authoritative. A wall-clock correction is also
        # detected against monotonic time in the recorder's watchdog.
        stamp = max(self.previous_ns + 1, observed)
        self.previous_ns = stamp
        self.ordinal += 1
        row = dict(
            kind=kind, recv_ns=stamp, session=session, ordinal=self.ordinal, **fields
        )
        minute = stamp // 60_000_000_000
        if minute != self.minute:
            self.seal()
            self.minute = minute
            self.path = self.run / f"{minute:012d}.jsonl.gz.open"
            self.file = self.path.open("xb")
        self.chunk.extend(
            json.dumps(row, separators=(",", ":"), allow_nan=False).encode() + b"\n"
        )
        self.counts[kind] += 1
        if kind == "ws":
            self.types[row["payload"].get("event_type", "other")] += 1
        if len(self.chunk) >= 256 * 1024 or time.monotonic() - self.last_flush >= 1:
            self.flush()
        if self.listener:
            self.listener(row)
        return row

    def flush(self):
        if self.chunk:
            self.file.write(gzip.compress(self.chunk, compresslevel=1, mtime=0))
            self.file.flush()
            self.chunk.clear()
        self.last_flush = time.monotonic()

    def seal(self):
        if self.file:
            self.flush()
            os.fsync(self.file.fileno())
            self.file.close()
            self.path.rename(self.path.with_suffix(""))
            self.file = None
