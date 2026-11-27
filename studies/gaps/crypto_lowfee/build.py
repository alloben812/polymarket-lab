"""Stage 1: per series, turn cached metadata + tapes + Binance prices into flat tables under data/gaps_crypto_lowfee/.

  <series>_markets.parquet  one row per window on the grid (found/resolved flags, official values, Binance twaps)
  <series>_fills.parquet    one row per tape row with the equivalent-buy form and the fair-value lookups
  <series>_grid.npz         per-market per-second arrays: G (fair value), U (last trade-implied Up price, block time)
Usage: python3 build.py [series ...] [--day1]   (series like eth-5m; default all six)
"""
from __future__ import annotations

import json
import sys
import time

import numpy as np
import pandas as pd

from common import BIG, EXPECTED_RATE, REF, SERIES, T_START, load_px, name, period, day_of, series_windows
from pmlab import updown
from pmlab.fair import fair_up

DELAYS = (0, 1, 2, 5)


def cached_market(asset, dur, t0):
    path = updown.META_DIR / asset / dur / f"{t0}.json"
    return json.loads(path.read_text()) if path.exists() else None


def cached_tape(cond):
    path = updown.TAPE_DIR / f"{cond}.jsonl.gz"
    return updown.tape(cond) if path.exists() else None


def build(series, day1=False):
    asset, dur_s = series
    dur = updown.DURATION[dur_s]
    px = load_px(updown.SYMBOL[asset])
    t0s = series_windows(series)
    if day1:
        t0s = [t for t in t0s if t < T_START + 86400]
    mrows, frames, G_all, U_all, dev_all = [], [], {}, {}, {}
    dropped = 0
    for t0 in t0s:
        t1 = t0 + dur
        m = cached_market(asset, dur_s, t0)
        row = {"t0": t0, "t1": t1, "day": day_of(t0), "period": period(t0), "found": m is not None}
        if m is None:
            mrows.append(row)
            continue
        rate = m.get("fee_rate")
        row.update(resolved=m.get("up_won") is not None, condition=m.get("condition"), up_won=m.get("up_won"),
                   ptb=m.get("price_to_beat"), final=m.get("final_price"), fee_rate_meta=rate,
                   rate=float(rate) if rate is not None else EXPECTED_RATE[series], twap_lookback=m.get("twap_lookback"),
                   volume=m.get("volume"), b_twap0=px.twap(t0, 60), b_twap1=px.twap(t1, 60))
        tp = cached_tape(m["condition"]) if m.get("condition") and m.get("up_won") is not None else None
        row["has_tape_file"] = tp is not None
        if tp is None:
            mrows.append(row)
            continue
        # fair value grid: G[i] = fair_up(px, t0 + i), i = 0..dur-1 (information up to t0 + i + 1)
        G = np.array([fair_up(px, s, t0, dur, 60) for s in range(t0, t1)])
        # expected settlement average deviation from the strike, last 60 s only: dev[i] at s = t1 - 60 + i
        k = px.twap(t0, 60)
        dev = np.full(60, np.nan)
        for i in range(1, 60):
            s = t1 - 60 + i
            e, r = s - (t1 - 60), t1 - s
            so_far = px.mean_between(t1 - 60, s)
            ea = (e / 60) * so_far + (r / 60) * px.price(s)
            dev[i] = abs(ea - k) / k
        row["g_nan"] = int(np.isnan(G).sum())
        if tp:
            df = pd.DataFrame(tp)
            n0 = len(df)
            df = df[(df.p > 0) & (df.p < 1) & (df.z > 0)].reset_index(drop=True)
            dropped += n0 - len(df)
        else:
            df = pd.DataFrame(columns=["t", "s", "o", "z", "p", "w"])
        row["n_fills"] = len(df)
        # U grid on block time s = t0..t1: size-weighted implied Up price of the latest second with rows (t >= t0)
        U = np.full(dur + 1, np.nan)
        if len(df):
            t = df.t.to_numpy(np.int64)
            buy = (df.s == "BUY").to_numpy()
            tok_up = (df.o == "Up").to_numpy()
            p = df.p.to_numpy(float)
            z = df.z.to_numpy(float)
            up_imp = np.where(tok_up, p, 1.0 - p)
            inw = (t >= t0) & (t <= t1)
            if inw.any():
                sec = t[inw] - t0
                num = np.bincount(sec, weights=(up_imp * z)[inw], minlength=dur + 1)
                den = np.bincount(sec, weights=z[inw], minlength=dur + 1)
                has = den > 0
                val = np.where(has, num / np.where(has, den, 1.0), np.nan)
                idx = np.where(has, np.arange(dur + 1), -1)
                np.maximum.accumulate(idx, out=idx)
                U = np.where(idx >= 0, val[np.maximum(idx, 0)], np.nan)
            mt = t - updown.BLOCK_LAG
            eq_up = np.where(buy, tok_up, ~tok_up)
            q = np.where(buy, p, 1.0 - p)
            up_won = bool(m["up_won"])
            won_eq = np.where(eq_up, up_won, not up_won).astype(float)
            tok_won = np.where(tok_up, up_won, not up_won).astype(float)
            gross = np.where(buy, tok_won - p, p - tok_won)
            out = pd.DataFrame({"t0": t0, "t": t, "m": mt, "buy": buy, "tok_up": tok_up, "z": z, "p": p, "w": df.w.fillna("").to_numpy(),
                                "eq_up": eq_up, "q": q, "won_eq": won_eq, "gross": gross, "rate": row["rate"]})

            def look(x):
                i = x - t0
                ok = (i >= 0) & (i < dur)
                return np.where(ok, G[np.clip(i, 0, dur - 1)], np.nan)

            for d in DELAYS:
                out[f"fup_d{d}"] = look(mt - d - 1)
            j = (mt - 2) - (t1 - 60)
            okj = (j >= 1) & (j < 60)
            out["dev_m2"] = np.where(okj, dev[np.clip(j, 0, 59)], np.nan)
            frames.append(out)
        G_all[str(t0)] = G
        U_all[str(t0)] = U
        mrows.append(row)
    BIG.mkdir(parents=True, exist_ok=True)
    tag = name(series) + ("_day1" if day1 else "")
    mk = pd.DataFrame(mrows)
    mk.to_parquet(BIG / f"{tag}_markets.parquet")
    fills = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    fills.to_parquet(BIG / f"{tag}_fills.parquet")
    keys = list(G_all)
    np.savez_compressed(BIG / f"{tag}_grid.npz", t0=np.array([int(k) for k in keys]),
                        G=np.array([G_all[k] for k in keys]), U=np.array([U_all[k] for k in keys]))
    return {"series": tag, "windows": len(t0s), "found": int(mk.found.sum()), "with_tape_file": int(mk.get("has_tape_file", pd.Series(dtype=bool)).fillna(False).sum()),
            "fills": len(fills), "dropped_rows": dropped}


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    day1 = "--day1" in sys.argv
    todo = [s for s in SERIES + [REF] if not args or name(s) in args]
    for s in todo:
        t = time.time()
        print(build(s, day1), round(time.time() - t, 1), "s", flush=True)
