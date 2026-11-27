"""Shared helpers for the news_latency study (see protocol.md)."""
from __future__ import annotations
import datetime as dt
import gzip
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "gaps_news"
DATA.mkdir(parents=True, exist_ok=True)
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)
PH = DATA / "ph"
PH.mkdir(exist_ok=True)
TAPES = DATA / "tapes"
TAPES.mkdir(exist_ok=True)


def ts(s: str) -> int:
    return int(dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp())


def iso(t: float) -> str:
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


W0, W1 = ts("2026-09-01"), ts("2026-11-26")          # T_pre must fall in [W0, W1)
SPLIT = ts("2026-10-14")                              # first half < SPLIT <= second half
FETCH0, FETCH1 = ts("2026-08-31"), ts("2026-11-27")
ERA300 = ts("2026-09-27")                             # 300 s buckets requested from here (served from this day on 2026-11-27)
S60 = ts("2026-11-20")                                # 60 s buckets requested from here

INC = {"politics", "geopolitics", "world", "world-affairs", "elections", "global-elections", "world-elections",
       "breaking-news", "middle-east"}
EXC = {"tweets-markets", "elon-tweets", "mention-markets", "sports", "games", "esports", "crypto-prices", "up-or-down",
       "hit-price", "multi-strikes", "weather"}
_WORDS = re.compile(r"(^|-)(say|said|mention|mentions|tweet|tweets|post|posts)(-|$)")
ELECT = {"elections", "global-elections", "world-elections", "midterms", "primaries"}


def parse_time(s: str | None) -> int | None:
    if not s:
        return None
    s = s.replace(" ", "T").replace("Z", "+00:00")
    if re.search(r"[+-]\d\d$", s):
        s += ":00"
    try:
        d = dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return int(d.timestamp())


def load_all_markets() -> list[dict]:
    with gzip.open(DATA / "markets_all.jsonl.gz", "rt") as f:
        return [json.loads(l) for l in f]


def in_universe(m: dict) -> bool:
    tags = set(m.get("tags") or [])
    try:
        outs = json.loads(m["outcomes"]) if isinstance(m["outcomes"], str) else m["outcomes"]
        toks = json.loads(m["clobTokenIds"]) if isinstance(m["clobTokenIds"], str) else m["clobTokenIds"]
    except (TypeError, ValueError):
        return False
    if not outs or len(outs) != 2 or not toks or len(toks) != 2:
        return False
    if not (tags & INC) or (tags & EXC) or _WORDS.search(m.get("slug") or ""):
        return False
    start = parse_time(m.get("startDate") or m.get("createdAt"))
    if start is None or start >= W1:
        return False
    if m.get("closed"):
        ct = parse_time(m.get("closedTime"))
        if ct is None or ct < W0:
            return False
    return True


def universe() -> list[dict]:
    return [m for m in load_all_markets() if in_universe(m)]


def category(m: dict) -> str:
    tags = set(m.get("tags") or [])
    if m.get("feeType") == "politics_elections_fees" or tags & ELECT:
        return "elections"
    if "geopolitics" in tags or (m.get("feeType") == "zero_fees" and tags & {"world", "middle-east", "world-affairs"}):
        return "geopolitics"
    return "other politics"


def fee_rate(m: dict) -> float:
    fs = m.get("feeSchedule") or {}
    if fs.get("rate") is not None:
        return float(fs["rate"])
    return {"geopolitics": 0.0, "elections": 0.05, "other politics": 0.01}[category(m)]


def tokens(m: dict) -> tuple[str, str]:
    t = json.loads(m["clobTokenIds"]) if isinstance(m["clobTokenIds"], str) else m["clobTokenIds"]
    return t[0], t[1]


def outcomes(m: dict) -> tuple[str, str]:
    o = json.loads(m["outcomes"]) if isinstance(m["outcomes"], str) else m["outcomes"]
    return o[0], o[1]
