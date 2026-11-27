"""Shared definitions for the pair-accumulation study (see protocol.md)."""
from __future__ import annotations

import json
from pathlib import Path

from pmlab import gamma, updown
from pmlab.http import ROOT

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
BIG = ROOT / "data" / "gaps_pair_accumulation"
T_START = 1795219200            # 2026-11-21 00:00 UTC
T_END = T_START + 6 * 86400     # 2026-11-27 00:00 UTC (exclusive)
T_SPLIT = T_START + 4 * 86400   # 2026-11-25 00:00 UTC: early = before, late = from here
DUR = {"5m": 300, "15m": 900, "1h": 3600}
# (asset, dur, grid): grid = keep only windows with t0 % grid == 0 (1 = every window)
SERIES = [("btc", "5m", 1), ("eth", "5m", 1), ("sol", "5m", 1200), ("xrp", "5m", 1200),
          ("btc", "15m", 1), ("eth", "15m", 1), ("sol", "15m", 1), ("xrp", "15m", 1),
          ("btc", "1h", 1), ("eth", "1h", 1), ("sol", "1h", 1), ("xrp", "1h", 1)]
LEVELS = [0.45, 0.40, 0.30, 0.05]
NOTIONAL = 10.0  # USD per leg; shares per leg = NOTIONAL / L


def name(s):
    return f"{s[0]}-{s[1]}"


def windows(s):
    asset, dur, grid = s
    step = DUR[dur]
    return [t for t in range(T_START, T_END, step) if t % grid == 0]


def load_market(asset: str, dur: str, t0: int) -> dict | None:
    """Like pmlab.updown.load_market but also for 1h windows (same slug pattern, same cache layout)."""
    if dur in updown.DURATION:
        return updown.load_market(asset, dur, t0)
    path = updown.META_DIR / asset / dur / f"{t0}.json"
    if path.exists():
        return json.loads(path.read_text())
    s = f"{asset}-updown-{dur}-{t0}"
    ev = gamma.event_by_slug(s)
    if not ev or not ev.get("markets"):
        return None
    m = ev["markets"][0]
    names = gamma.jfield(m.get("outcomes")) or []
    tokens = gamma.jfield(m.get("clobTokenIds")) or []
    prices = gamma.jfield(m.get("outcomePrices")) or []
    md = ev.get("eventMetadata") or {}
    cfg = m.get("cryptoMarketConfig") or {}
    out = {"slug": s, "asset": asset, "dur": dur, "t0": t0, "t1": t0 + DUR[dur], "condition": m.get("conditionId"),
           "tokens": dict(zip(names, tokens)), "closed": bool(m.get("closed")),
           "price_to_beat": md.get("priceToBeat"), "final_price": md.get("finalPrice"),
           "fee_rate": (m.get("feeSchedule") or {}).get("rate"), "fee_type": m.get("feeType"),
           "twap_lookback": cfg.get("twapLookbackSeconds"), "volume": m.get("volumeNum"),
           "tick": m.get("orderPriceMinTickSize"), "up_won": None}
    if out["closed"] and len(prices) == len(names) == 2:
        try:
            pr = dict(zip(names, (float(x) for x in prices)))
            if {round(v) for v in pr.values()} == {0, 1}:
                out["up_won"] = pr.get("Up") == 1.0
        except (TypeError, ValueError):
            pass
    if out["closed"] and out["up_won"] is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out))
    return out
