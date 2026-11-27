"""Shared constants and helpers for the BTC 5m tails study (see protocol.md)."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from pmlab import fees, stats  # noqa: E402

START = 1788220800  # 2026-09-01 00:00 UTC
END = 1795737600    # 2026-11-27 00:00 UTC
OCT1 = 1790812800   # 2026-10-01 00:00 UTC
NOV1 = 1793491200   # 2026-11-01 00:00 UTC
DATA = ROOT / "data" / "gaps_btc5m_tails"
OUT = Path(__file__).resolve().parent / "out"
VEGA7 = "0x6ba25c9f2fe6e9e5dd47983b629c00cd59958d0e"

TAIL_BANDS = [("<=0.015", 0.0, 0.015), ("0.015-0.03", 0.015, 0.03), ("0.03-0.05", 0.03, 0.05), ("0.05-0.10", 0.05, 0.10)]
FAV_BANDS = [(">=0.985", 0.985, 1.0), ("0.97-0.985", 0.97, 0.985), ("0.95-0.97", 0.95, 0.97)]  # mirrors of the first three
TIME_BANDS = ["300-180", "180-75", "75-45", "45-15", "15-0", "after"]
MONTHS = ["Sep", "Oct", "Nov"]


def month_of(t0):
    t0 = np.asarray(t0)
    return np.where(t0 < OCT1, "Sep", np.where(t0 < NOV1, "Oct", "Nov"))


def time_band(e):
    """e = seconds into the window (match time - t0). Bands are in seconds LEFT = 300 - e, left-open right-closed."""
    left = 300 - np.asarray(e)
    out = np.full(left.shape, "pre", dtype=object)
    out[(left > 180) & (left <= 300)] = "300-180"
    out[(left > 75) & (left <= 180)] = "180-75"
    out[(left > 45) & (left <= 75)] = "75-45"
    out[(left > 15) & (left <= 45)] = "45-15"
    out[(left > 0) & (left <= 15)] = "15-0"
    out[left <= 0] = "after"
    return out


def tail_band(p):
    p = np.asarray(p)
    out = np.full(p.shape, "", dtype=object)
    for name, lo, hi in TAIL_BANDS:
        out[(p > lo) & (p <= hi)] = name
    return out


def fav_band(p):
    p = np.asarray(p)
    out = np.full(p.shape, "", dtype=object)
    for name, lo, hi in FAV_BANDS:
        out[(p >= lo) & (p < hi)] = name
    return out


def fee_rate(block_ts):
    """Vectorised pmlab.fees.btc_updown_rate."""
    return np.where(np.asarray(block_ts) >= fees.FEE_CHANGE_TS, 0.05, 0.07)


def add_money(df: pd.DataFrame) -> pd.DataFrame:
    """Adds stake, fee and net dollars of buying the whole print. Needs columns p, z, hit, bt (block time)."""
    df = df.copy()
    df["stake"] = df["z"] * df["p"]
    df["fee"] = df["z"] * fee_rate(df["bt"].to_numpy()) * df["p"] * (1.0 - df["p"])
    df["net"] = df["z"] * df["hit"].astype(float) - df["stake"] - df["fee"]
    return df


def cell_stats(df: pd.DataFrame) -> dict:
    """Statistics of one cell. df: prints with t0, side, p, z, hit, stake, fee, net. Clusters = markets (t0)."""
    if len(df) == 0:
        return {"prints": 0}
    g = df.groupby("t0").agg(net=("net", "sum"), z=("z", "sum"), stake=("stake", "sum"))
    nps, nps_se, nps_t = stats.ratio_cluster(g["net"].tolist(), g["z"].tolist())
    ros, ros_se, ros_t = stats.ratio_cluster(g["net"].tolist(), g["stake"].tolist())
    u = df.groupby(["t0", "side"]).agg(hit=("hit", "first"), z=("z", "sum"), stake=("stake", "sum"), fee=("fee", "sum"))
    n, k = len(u), int(u["hit"].sum())
    lo, hi = stats.wilson(k, n)
    be = float(((u["stake"] + u["fee"]) / u["z"]).mean())  # equal-weight break-even probability of the units
    zb = (k - n * be) / np.sqrt(n * be * (1 - be)) if n and 0 < be < 1 else float("nan")
    pb = binom_tail(k, n, be) if n and 0 < be < 1 else float("nan")
    shares, stake = float(df["z"].sum()), float(df["stake"].sum())
    return {
        "prints": len(df), "markets": int(g.shape[0]), "units": n, "hits": k, "hit_rate": k / n, "wil_lo": lo, "wil_hi": hi,
        "breakeven": be, "z_binom": float(zb), "p_binom": pb, "shares": shares, "dollars": stake, "avg_price": stake / shares,
        "sw_hit": float((df["z"] * df["hit"]).sum() / shares), "net_ps": nps, "net_ps_se": nps_se, "t": nps_t,
        "ros": ros, "ros_t": ros_t, "net_dollars": float(df["net"].sum()),
    }


def binom_tail(k: int, n: int, p: float) -> float:
    """Exact one-sided binomial tail in the direction of the deviation: P(X >= k) if k > n p else P(X <= k)."""
    import math
    logs = [math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * math.log(p) + (n - i) * math.log(1 - p) for i in range(n + 1)]
    pm = [math.exp(x) for x in logs]
    return float(sum(pm[k:]) if k > n * p else sum(pm[: k + 1]))


def load_status() -> dict:
    done = {}
    p = DATA / "fetch_status.jsonl"
    for line in p.read_text().splitlines():
        r = json.loads(line)
        done[r["t0"]] = r
    return done
