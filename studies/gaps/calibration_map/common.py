"""Shared helpers for the calibration-map study (see protocol.md)."""
from __future__ import annotations

import gzip
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "gaps_calibration_map"
OUT = Path(__file__).resolve().parent / "out"
DATA.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

SEED = 20261127
P_START = datetime(2026, 8, 29, tzinfo=timezone.utc).timestamp()
P_END = datetime(2026, 11, 27, tzinfo=timezone.utc).timestamp()
FINE_FROM = datetime(2026, 9, 28, tzinfo=timezone.utc).timestamp()
T_SPLIT = datetime(2026, 10, 28, tzinfo=timezone.utc).timestamp()
HORIZONS = [("24h", 86400), ("6h", 21600), ("1h", 3600), ("10m", 600)]
BUCKETS = [(0.50, 0.60), (0.60, 0.70), (0.70, 0.80), (0.80, 0.90), (0.90, 0.95), (0.95, 0.98), (0.98, 0.995 + 1e-9)]
BNAMES = ["0.50-0.60", "0.60-0.70", "0.70-0.80", "0.80-0.90", "0.90-0.95", "0.95-0.98", "0.98-0.995"]
CAPS = {"updown-15m": 1400, "updown-1h": 900, "updown-4h": 600, "crypto-level": 1000, "crypto-hit": 400,
        "weather-temp": 1400, "weather-other": 200, "mentions": 700, "counters": 400, "esports": 400,
        "sports-ml": 1200, "sports-line": 800, "sports-other": 300, "finance": 500, "economics": 300,
        "politics": 500, "other": 400}


def ts(s) -> float | None:
    if not s:
        return None
    s = str(s).strip().replace(" ", "T")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    if s.endswith("+00"):
        s = s + ":00"
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.timestamp()


_UD = re.compile(r"^([a-z0-9]+)-updown-(\d+[mh])-(\d{9,})$")
_SAY = re.compile(r"(^|-)(say|said|says|mention|mentions)(-|$)")
_ESP = {"esports", "counter-strike-2", "dota-2", "valorant", "league-of-legends", "lol", "cs2"}
_COMMOD = {"xau", "wti", "xag", "brent", "spx", "ndx"}


def classify(m: dict) -> tuple[str | None, float, float | None]:
    """-> (family or None if excluded, fee rate, anchor ts)."""
    slug = m.get("slug") or ""
    tags = set(m.get("tags") or [])
    fam0 = m.get("family")
    end = ts(m.get("endDate"))
    u = _UD.match(slug)
    if u:
        asset, dur = u.group(1), u.group(2)
        if dur == "5m":
            return None, 0.0, end
        if asset in _COMMOD or fam0 == "finance" or "finance" in tags:
            return "finance", 0.05, end
        if dur == "15m":
            return "updown-15m", (0.05 if asset == "btc" else 0.01), end
        if dur == "1h":
            return "updown-1h", 0.01, end
        if dur == "4h":
            return "updown-4h", 0.01, end
        return "crypto-level", 0.01, end
    if fam0 == "crypto":
        if "hit-price" in tags or re.search(r"(^|-)(reach|dip|hit)(-|$)", slug):
            return "crypto-hit", 0.01, end
        return "crypto-level", 0.01, end
    if slug.startswith("highest-temperature-in") or slug.startswith("lowest-temperature-in"):
        est = ts(m.get("eventStartTime"))
        return "weather-temp", 0.01, (est + 86400 if est else end)
    if fam0 == "weather":
        return "weather-other", 0.01, end
    if any("mention" in t for t in tags) or _SAY.search(slug):
        return "mentions", 0.01, end
    if "tweets" in slug or "-posts-" in slug or "truth-social-post" in slug:
        return "counters", 0.01, end
    gst = ts(m.get("gameStartTime"))
    if tags & _ESP:
        return "esports", 0.05, (gst or end)
    if fam0 == "sports":
        smt = m.get("sportsMarketType")
        if smt in (None, "", "moneyline"):
            return "sports-ml", 0.05, (gst or end)
        if smt in ("spreads", "totals"):
            return "sports-line", 0.05, (gst or end)
        return "sports-other", 0.05, (gst or end)
    if fam0 == "finance":
        return "finance", 0.05, end
    if fam0 == "economics":
        return "economics", 0.01, end
    if fam0 == "politics":
        if "geopolitics" in tags:
            return "politics", 0.0, end
        if any("election" in t for t in tags):
            return "politics", 0.05, end
        return "politics", 0.01, end
    return "other", (0.01 if fam0 == "culture" else 0.05), end


def bucket_of(p: float) -> int | None:
    for i, (lo, hi) in enumerate(BUCKETS):
        if lo <= p < hi:
            return i
    return None


def slip(q: float) -> float:
    return 0.01 if 0.10 <= q <= 0.90 else 0.005


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
