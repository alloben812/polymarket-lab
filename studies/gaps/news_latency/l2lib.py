"""Reader for the PendulumFlow V3.1 hourly L2 files (HF chitoyuuri/polymarket-l2-v3-1-archive).
Downloaded files are untrusted data: this module only parses parquet with pyarrow. Run with python3 -I."""
from __future__ import annotations
import datetime as dt
import urllib.request
from pathlib import Path
import pyarrow.compute as pc
import pyarrow.parquet as pq

BASE = "https://huggingface.co/datasets/chitoyuuri/polymarket-l2-v3-1-archive/resolve/main/v3.1"
L2DIR = Path(__file__).resolve().parents[3] / "data" / "gaps_news" / "l2"
L2DIR.mkdir(parents=True, exist_ok=True)
COLS = ["event_type", "timestamp", "market", "asset_id", "best_bid", "best_ask", "bids", "asks", "price", "size", "side",
        "mirror_dropped", "row_ordinal"]


def hour_file(t: int, cat: str) -> Path | None:
    d = dt.datetime.fromtimestamp(t, dt.timezone.utc)
    name = f"{d:%Y-%m-%d}T{d:%H}.{cat}.parquet"
    path = L2DIR / name
    if path.exists():
        return path if path.stat().st_size > 0 else None
    url = f"{BASE}/{d:%Y-%m-%d}/{d:%H}/{name}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "research"}), timeout=300) as r:
            data = r.read()
    except Exception as e:  # noqa: BLE001
        if "404" in str(e):
            path.write_bytes(b"")
        return None
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)
    return path


def market_rows(path: Path, condition: str) -> list[dict]:
    key = bytes.fromhex(condition[2:])
    t = pq.read_table(path, columns=COLS)
    t = t.filter(pc.equal(t.column("market").cast("binary"), key))
    rows = t.to_pylist()
    for r in rows:
        r["ms"] = int(r["timestamp"].timestamp() * 1000)
        r["asset"] = str(int.from_bytes(r["asset_id"], "big")) if r["asset_id"] else None
    return rows
