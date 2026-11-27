"""Shared helpers for the tennis walkover study (see protocol.md)."""
from __future__ import annotations

import bisect
import datetime as dt
import gzip
import hashlib
import json
import math
import statistics
from pathlib import Path

DATA = Path("/home/user/polymarket-lab/data/gaps_tennis_wo")
HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

P0 = dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc).timestamp()
P1 = dt.datetime(2026, 11, 25, 23, 59, 59, tzinfo=dt.timezone.utc).timestamp()
PERIOD_DAYS = 86
MONTHS = PERIOD_DAYS / 30.44
LAG = 3
FEE = 0.05
DELAYS = [10, 60, 300, 900]
WINDOW = 1800
BUDGET = 300.0
PMAX = 0.46


def ts(s) -> float | None:
    """gamma time string -> epoch seconds (several formats occur)."""
    if not s:
        return None
    s = str(s).strip().replace(" ", "T")
    if s.endswith("+00:00:00"):
        s = s[:-9] + "+00:00"
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    if s.endswith("+00"):
        s = s + ":00"
    # trim fractional seconds to 6 digits
    if "." in s:
        head, rest = s.split(".", 1)
        frac = ""
        i = 0
        while i < len(rest) and rest[i].isdigit():
            frac += rest[i]
            i += 1
        s = head + "." + frac[:6].ljust(6, "0") + rest[i:]
    try:
        d = dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.timestamp()


def iso(t) -> str:
    return "" if t is None else dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def jf(v):
    if isinstance(v, str):
        try:
            return json.loads(v)
        except ValueError:
            return None
    return v


def load_events():
    with gzip.open(DATA / "events.jsonl.gz", "rt") as f:
        for line in f:
            yield json.loads(line)


def final_prices(m) -> tuple[float, float] | None:
    pr = jf(m.get("outcomePrices"))
    if not pr or len(pr) != 2:
        return None
    try:
        return float(pr[0]), float(pr[1])
    except (TypeError, ValueError):
        return None


def sample_hash(cid: str) -> int:
    return int(hashlib.sha1(cid.encode()).hexdigest(), 16)


def fee_ps(p: float) -> float:
    return FEE * p * (1.0 - p)


# ---------------------------------------------------------------- tape -> prints

def prints(tape: list[dict], outcomes: list[str]) -> list[dict]:
    """Tape rows -> prints with match time, price in outcome[0] terms and what was buyable.

    t: match time (block - 3); a: price of outcome[0]; bo/bp: buyable outcome index and price; z: shares; w: taker;
    s: taker side; oi: outcome index of the row; p: row price."""
    out = []
    for r in tape:
        try:
            oi = outcomes.index(r["o"])
        except ValueError:
            continue
        p = r["p"]
        a = p if oi == 0 else 1.0 - p
        if r["s"] == "BUY":
            bo, bp = oi, p
        else:
            bo, bp = 1 - oi, 1.0 - p
        out.append({"t": r["t"] - LAG, "a": a, "bo": bo, "bp": bp, "z": r["z"], "w": r.get("w"), "s": r["s"], "oi": oi, "p": p})
    out.sort(key=lambda x: x["t"])
    return out


def add_reference(pr: list[dict]) -> None:
    """Protocol 2.2: R_i = median of a_j over prints in [t_i - 6 h, t_i - 120 s]; fallback last 3 prints <= t_i - 120 s."""
    times = [x["t"] for x in pr]
    for i, x in enumerate(pr):
        hi = bisect.bisect_right(times, x["t"] - 120)  # prints [0, hi) have t <= t_i - 120
        lo = bisect.bisect_left(times, x["t"] - 6 * 3600)
        win = [pr[j]["a"] for j in range(lo, hi)]
        if len(win) < 3:
            win = [pr[j]["a"] for j in range(max(0, hi - 3), hi)]
        if not win:
            x["R"] = None
            x["move"] = False
            continue
        R = statistics.median(win)
        x["R"] = R
        und = 0 if R < 0.5 else 1
        r = min(R, 1.0 - R)
        xx = x["a"] if und == 0 else 1.0 - x["a"]
        x["und"] = und
        x["r"] = r
        x["x"] = xx
        x["move"] = (r <= 0.45 + 1e-9) and (xx >= r + 0.05 - 1e-9)


def hindsight_t_first(pr: list[dict]) -> dict | None:
    """Protocol 2.3: earliest move print i such that all later prints keep the underdog (as of i) >= r_i + 0.03,
    at most two strays tolerated."""
    n = len(pr)
    for i, x in enumerate(pr):
        if not x.get("move"):
            continue
        und, r = x["und"], x["r"]
        strays = 0
        ok = True
        for j in range(i + 1, n):
            xx = pr[j]["a"] if und == 0 else 1.0 - pr[j]["a"]
            if xx < r + 0.03 - 1e-9:
                strays += 1
                if strays > 2:
                    ok = False
                    break
        if ok:
            return {"i": i, "t": x["t"], "und": und, "r": r, "fav": 1.0 - r, "x": x["x"], "strays": strays}
    return None


def episodes(pr: list[dict]) -> list[int]:
    """Protocol 2.6: indices of move prints with no other move print in the previous 30 minutes."""
    out = []
    last_move_t = None
    for i, x in enumerate(pr):
        if x.get("move"):
            if last_move_t is None or x["t"] - last_move_t > 1800:
                out.append(i)
            last_move_t = x["t"]
    return out


def run_rule(streams: list[tuple[list[dict], tuple[float, float]]], starts: list[float], budget: float = BUDGET) -> dict:
    """Rule 2.5. streams: [(prints, final prices (outcome0, outcome1))]; starts: window start times (already t0 + d).
    One budget across all windows and streams. Returns totals and the fills."""
    evs = []
    for k, (pr, fin) in enumerate(streams):
        for idx, x in enumerate(pr):
            if x["bp"] <= PMAX + 1e-9 and any(s <= x["t"] <= s + WINDOW for s in starts):
                evs.append((x["t"], k, idx, x, fin))
    evs.sort(key=lambda e: (e[0], e[1], e[2]))
    left = budget
    shares = cost = fees = payoff = 0.0
    fills = []
    for t, k, idx, x, fin in evs:
        if left <= 1e-9:
            break
        p = x["bp"]
        unit = p + fee_ps(p)
        q = min(x["z"], left / unit)
        if q <= 0:
            continue
        left -= q * unit
        shares += q
        cost += q * p
        fees += q * fee_ps(p)
        payoff += q * fin[x["bo"]]
        fills.append((t, k, p, q, x["w"]))
    return {"shares": shares, "cost": cost, "fees": fees, "payoff": payoff, "net": payoff - cost - fees, "fills": fills}
