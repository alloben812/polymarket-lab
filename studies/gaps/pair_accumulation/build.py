"""Per market, per level, per outcome: placement check and first fill times under both scenarios (protocol 3-4).

Writes data/gaps_pair_accumulation/legs.parquet (main universe) and legs_hist.parquet (BTC 5m Sep 1 - Nov 20 grid),
plus sanity tables in out/sanity.json.  Usage: python3 build.py [main|hist|all]"""
from __future__ import annotations

import gzip
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

from common import BIG, DUR, LEVELS, OUT, SERIES, T_SPLIT, T_START, load_market, name, windows
from pmlab import updown

EPS = 1e-9


def read_tape(cond):
    p = updown.TAPE_DIR / f"{cond}.jsonl.gz"
    if not p.exists():
        return None
    with gzip.open(p, "rt") as f:
        return [json.loads(x) for x in f]


def one(args):
    asset, dur, t0 = args
    m = load_market(asset, dur, t0)
    if not m or m.get("up_won") is None or not m.get("condition"):
        return {"status": "missing", "asset": asset, "dur": dur, "t0": t0}, []
    rows = read_tape(m["condition"])
    if rows is None:
        return {"status": "no_tape", "asset": asset, "dur": dur, "t0": t0}, []
    t1 = t0 + DUR[dur]
    won = {"Up": bool(m["up_won"]), "Down": not m["up_won"]}
    sell = [(t, o, p, z) for t, o, p, z in updown.sellable(rows)]
    buy = [(t, o, p, z) for t, o, p, z in updown.buyable(rows)]
    inwin = [x for x in sell if t0 <= x[0] < t1]
    # sanity: equal-share win rate of buyable prints at 0.45-0.55 inside the window
    sz = sum(z for t, o, p, z in buy if t0 <= t < t1 and 0.45 <= p <= 0.55)
    sw = sum(z for t, o, p, z in buy if t0 <= t < t1 and 0.45 <= p <= 0.55 and won[o])
    mk = {"status": "ok", "asset": asset, "dur": dur, "t0": t0, "series": f"{asset}-{dur}", "up_won": m["up_won"],
          "n_rows": len(rows), "n_inwin": len(inwin), "tape_shares": sum(r["z"] for r in rows),
          "volume": m.get("volume"), "mid_sh": sz, "mid_win_sh": sw, "late": t0 >= T_SPLIT}
    legs = []
    for L in LEVELS:
        for X in ("Up", "Down"):
            pre = [p for t, o, p, z in buy if o == X and t0 - 30 <= t < t0]
            placeable = not any(p <= L + EPS for p in pre)
            rec = {"asset": asset, "dur": dur, "series": f"{asset}-{dur}", "t0": t0, "late": t0 >= T_SPLIT,
                   "L": L, "X": X, "won": won[X], "placeable": placeable}
            for scen, cond in (("cons", lambda p: p < L - EPS), ("opt", lambda p: p <= L + EPS)):
                ft = next((t for t, o, p, z in inwin if o == X and cond(p)), None)
                rec[f"t_{scen}"] = None if ft is None else ft - t0
            # capacity: shares printed strictly through L within 10 s after the first through print
            if rec["t_cons"] is not None:
                ft = rec["t_cons"] + t0
                rec["cap_sh"] = sum(z for t, o, p, z in inwin if o == X and p < L - EPS and ft <= t < ft + 10)
            else:
                rec["cap_sh"] = None
            legs.append(rec)
    return mk, legs


def run(tasks, tag):
    with ProcessPoolExecutor(4) as ex:
        res = list(ex.map(one, tasks, chunksize=16))
    mks = pd.DataFrame([r[0] for r in res])
    legs = pd.DataFrame([x for r in res for x in r[1]])
    mks.to_parquet(BIG / f"markets_{tag}.parquet")
    legs.to_parquet(BIG / f"legs_{tag}.parquet")
    print(tag, "markets", len(mks), mks.status.value_counts().to_dict(), "legs", len(legs))
    return mks, legs


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("main", "all"):
        tasks = [(s[0], s[1], t) for s in SERIES for t in windows(s)]
        run(tasks, "main")
    if what in ("hist", "all"):
        t_sep = 1788220800  # 2026-09-01 00:00 UTC
        tasks = [("btc", "5m", t) for t in range(t_sep, T_START, 300) if t % 1200 == 0
                 and (updown.META_DIR / "btc" / "5m" / f"{t}.json").exists()]
        run(tasks, "hist")


if __name__ == "__main__":
    main()
