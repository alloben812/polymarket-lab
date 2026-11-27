"""Crypto "Up or Down" recurring markets: enumerate windows, load official metadata, cache market tapes.

Slugs are `<asset>-updown-<5m|15m>-<start_epoch>` (asset in btc, eth, sol, xrp, doge, hype). The gamma event carries
`eventMetadata {priceToBeat, finalPrice}`: the official Chainlink values at the start and end of the window.

Tape semantics used by the lab (see NOTES.md): every tape row is a fill seen from the taker's side, stamped with the
block time, which runs about 2-3 s after the match. A row tells us what liquidity existed at the match time:
  taker BOUGHT outcome X at p  -> an ask for X at <= p existed (equivalently a bid for the other outcome at >= 1-p)
  taker SOLD   outcome X at p  -> a bid for X at >= p existed (equivalently the other outcome was offered at <= 1-p)
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Iterator

from . import dataapi, gamma
from .http import ROOT

SYMBOL = {"btc": "BTCUSDT", "eth": "ETHUSDT", "sol": "SOLUSDT", "xrp": "XRPUSDT", "doge": "DOGEUSDT"}
DURATION = {"5m": 300, "15m": 900}
BLOCK_LAG = 3  # seconds between the match and the on-chain timestamp (best alignment on BTC 5m, Sep-Nov 2026)
TAPE_DIR = ROOT / "data" / "tape"
META_DIR = ROOT / "data" / "updown_meta"


def slug(asset: str, dur: str, t0: int) -> str:
    return f"{asset}-updown-{dur}-{t0}"


def windows(dur: str, start_ts: int, end_ts: int) -> list[int]:
    step = DURATION[dur]
    first = (start_ts + step - 1) // step * step
    return list(range(first, end_ts, step))


def load_market(asset: str, dur: str, t0: int, cache: bool = True) -> dict | None:
    """Official facts about one window, or None when the market does not exist or is not resolved yet."""
    s = slug(asset, dur, t0)
    path = META_DIR / asset / dur / f"{t0}.json"
    if cache and path.exists():
        return json.loads(path.read_text())
    ev = gamma.event_by_slug(s)
    if not ev or not ev.get("markets"):
        return None
    m = ev["markets"][0]
    names, tokens, prices = gamma.jfield(m.get("outcomes")) or [], gamma.jfield(m.get("clobTokenIds")) or [], gamma.jfield(m.get("outcomePrices")) or []
    md = ev.get("eventMetadata") or {}
    cfg = m.get("cryptoMarketConfig") or {}
    out = {
        "slug": s, "asset": asset, "dur": dur, "t0": t0, "t1": t0 + DURATION[dur], "condition": m.get("conditionId"),
        "tokens": dict(zip(names, tokens)), "closed": bool(m.get("closed")),
        "price_to_beat": md.get("priceToBeat"), "final_price": md.get("finalPrice"),
        "fee_rate": (m.get("feeSchedule") or {}).get("rate"), "fee_type": m.get("feeType"),
        "twap_lookback": cfg.get("twapLookbackSeconds"), "volume": m.get("volumeNum"), "tick": m.get("orderPriceMinTickSize"),
    }
    out["up_won"] = None
    if out["closed"] and len(prices) == len(names) == 2:
        try:
            pr = dict(zip(names, (float(x) for x in prices)))
            if {round(v) for v in pr.values()} == {0, 1}:
                out["up_won"] = pr.get("Up") == 1.0
        except (TypeError, ValueError):
            pass
    if cache and out["closed"] and out["up_won"] is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out))
    return out


def tape(condition: str, cache: bool = True) -> list[dict]:
    """Whole-market tape, oldest first: rows {t, s (BUY|SELL), o (outcome), z (shares), p (price), w (taker wallet)}.

    Cache only tapes of markets that have finished trading (call this for resolved markets)."""
    path = TAPE_DIR / f"{condition}.jsonl.gz"
    if cache and path.exists():
        with gzip.open(path, "rt") as f:
            return [json.loads(line) for line in f]
    rows = [{"t": r["timestamp"], "s": r["side"], "o": r["outcome"], "z": float(r["size"]), "p": float(r["price"]), "w": r.get("proxy_wallet")}
            for r in dataapi.iter_trades(condition=condition)]
    rows.sort(key=lambda r: r["t"])
    if cache:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with gzip.open(tmp, "wt") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        tmp.replace(path)
    return rows


def other(outcome: str) -> str:
    return "Down" if outcome == "Up" else "Up"


def buyable(rows: list[dict], lag: int = BLOCK_LAG) -> Iterator[tuple[int, str, float, float]]:
    """(match_time, outcome, price, size): at that moment `outcome` could be BOUGHT at `price` for at least `size`."""
    for r in rows:
        if r["s"] == "BUY":
            yield r["t"] - lag, r["o"], r["p"], r["z"]
        else:
            yield r["t"] - lag, other(r["o"]), 1.0 - r["p"], r["z"]


def sellable(rows: list[dict], lag: int = BLOCK_LAG) -> Iterator[tuple[int, str, float, float]]:
    """(match_time, outcome, price, size): a resting BID for `outcome` above `price` would have been hit first."""
    for r in rows:
        if r["s"] == "SELL":
            yield r["t"] - lag, r["o"], r["p"], r["z"]
        else:
            yield r["t"] - lag, other(r["o"]), 1.0 - r["p"], r["z"]
