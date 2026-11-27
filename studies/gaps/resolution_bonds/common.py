"""Shared helpers for the resolution-bonds study (see protocol.md)."""
from __future__ import annotations

import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "gaps_resolution_bonds"
OUT = Path(__file__).resolve().parent / "out"
DATA.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

SEED = 20261127
T_CLOSED_MIN = datetime(2026, 10, 20, tzinfo=timezone.utc).timestamp()
T_CLOSED_MAX = datetime(2026, 11, 25, tzinfo=timezone.utc).timestamp()
T_SPLIT = datetime(2026, 11, 13, tzinfo=timezone.utc).timestamp()
BUCKETS = [(0.80, 0.90), (0.90, 0.95), (0.95, 0.98), (0.98, 0.995), (0.995, 1.01)]
BUCKET_NAMES = ["0.80-0.90", "0.90-0.95", "0.95-0.98", "0.98-0.995", ">=0.995"]
EPS = 1e-9


def ts(s) -> float | None:
    """Parse the timestamp formats gamma uses ('2026-11-10T01:00:00Z', '2026-11-10 04:01:05.898905+00')."""
    if not s:
        return None
    s = str(s).strip().replace(" ", "T")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    if s.endswith("+00:00:00"):
        s = s[:-3]
    if s.endswith("+00"):
        s = s + ":00"
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.timestamp()


def iso(t: float) -> str:
    return datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


def bucket_of(p: float) -> int | None:
    for i, (lo, hi) in enumerate(BUCKETS):
        if lo - EPS <= p < hi - EPS:
            return i
    return None


def read_jsonl(path) -> list[dict]:
    op = gzip.open if str(path).endswith(".gz") else open
    with op(path, "rt") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path, rows) -> None:
    op = gzip.open if str(path).endswith(".gz") else open
    tmp = str(path) + ".tmp"
    with op(tmp, "wt") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    Path(tmp).replace(path)
