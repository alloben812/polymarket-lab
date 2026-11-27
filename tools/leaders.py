#!/usr/bin/env python3
"""Who makes money in a Polymarket category, and do they look systematic?

  python3 tools/leaders.py weather [--top 60] [--json out.json]

Merges the category's month and week PnL boards and the month volume board, then asks the Data API for each
account's all-time decomposition. Columns:
  cat_month / cat_week  PnL inside this category for the period (leaderboard number, before fees)
  kept_all              all-time economic PnL across ALL categories (after fees, with rebates)
  reb%                  share of kept_all that is rebates/rewards (high = needs volume tiers)
  fills, mkts           all-time fills and distinct markets;  $/fill = average fill size
  m-2 m-1 m0            what the account kept in each of the last three calendar months (all categories)
Systematic accounts show many markets, many small fills and positive months; whales show few markets and huge
fills. Sorting is by category month PnL.
"""
import argparse
import collections
import datetime as dt
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pmlab import dataapi  # noqa: E402


def monthly_kept(wallet: str) -> list[tuple[str, float]]:
    pts = dataapi.user_pnl(wallet, "all", "1d")
    last = collections.OrderedDict()
    for q in pts:
        last[dt.datetime.fromtimestamp(q["timestamp"], dt.timezone.utc).strftime("%Y-%m")] = q
    out, prev = [], {}
    for m, q in last.items():
        kept = (q.get("economic_pnl") or 0) - (prev.get("economic_pnl") or 0)
        out.append((m, kept))
        prev = q
    return out


def describe(row: dict) -> dict:
    w = row["wallet"]
    try:
        st = dataapi.user_stats(w)
        p = st.get("all_time_pnl") or {}
        g = lambda k: p.get(k) or 0.0  # noqa: E731
        reb = g("taker_rebate") + g("maker_rebate") + g("reward_income")
        row.update(kept_all=g("economic_pnl"), gross_all=g("trade_pnl"), fees_all=g("fees"), rebates_all=reb,
                   fills=int(g("trade_count")), mkts=st.get("trades") or 0, volume_usdc=g("volume_usdc"),
                   months=monthly_kept(w)[-3:])
    except Exception as e:  # noqa: BLE001 - keep the board even if one account fails
        row["error"] = str(e)[:80]
    return row


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("category")
    ap.add_argument("--top", type=int, default=60)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    rows: dict[str, dict] = {}
    for period, sort, field in (("month", "PNL", "cat_month"), ("week", "PNL", "cat_week"), ("month", "VOLUME", "cat_month_vol")):
        for r in dataapi.leaderboard(a.category, period, sort, a.top):
            w = r.get("user_id")
            if not w:
                continue
            e = rows.setdefault(w, {"wallet": w, "name": r.get("user_name") or w[:10]})
            e[field] = r.get("volume") if sort == "VOLUME" else r.get("pnl")
            if sort == "PNL":
                e.setdefault("cat_month_vol", None)
                e[field + "_volume"] = r.get("volume")
    with ThreadPoolExecutor(6) as ex:
        out = list(ex.map(describe, rows.values()))
    out.sort(key=lambda r: -(r.get("cat_month") or -1e18))
    if a.json:
        with open(a.json, "w") as f:
            json.dump(out, f)
    n = lambda v, w=10: (f"{v:>{w},.0f}" if isinstance(v, (int, float)) else " " * (w - 1) + "-")  # noqa: E731
    print(f"category={a.category}  accounts={len(out)}  (sorted by category month PnL)")
    print(f"{'name':24s} {'cat_month':>10s} {'cat_week':>10s} {'kept_all':>11s} {'reb%':>5s} {'fills':>9s} {'mkts':>7s} {'$/fill':>7s} {'fills/mkt':>9s}  last three months kept (all categories)   wallet")
    for r in out:
        if "error" in r:
            print(f"{r['name'][:24]:24s} {n(r.get('cat_month'))} {n(r.get('cat_week'))}  [stats failed: {r['error']}]  {r['wallet']}")
            continue
        kept = r.get("kept_all") or 0.0
        rebp = f"{(r.get('rebates_all') or 0) / kept * 100:4.0f}%" if kept > 0 else "   - "
        fills, mkts = r.get("fills") or 0, r.get("mkts") or 0
        per_fill = (r.get("volume_usdc") or 0) / fills if fills else 0
        months = "  ".join(f"{m[2:]}:{k:>9,.0f}" for m, k in (r.get("months") or []))
        print(f"{r['name'][:24]:24s} {n(r.get('cat_month'))} {n(r.get('cat_week'))} {n(kept, 11)} {rebp} {fills:>9,d} {mkts:>7,d} {per_fill:>7,.0f} {(fills / mkts if mkts else 0):>9.1f}  {months}   {r['wallet']}")


if __name__ == "__main__":
    main()
