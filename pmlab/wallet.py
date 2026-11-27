"""Take a Polymarket account apart from public data: what it trades, how (maker/taker, buy/sell, when in a
market's life), and where its money comes from after fees.

  python3 -m pmlab.wallet <profile-name | 0xaddress> --days 7 [--end 2026-11-27] [--max-fills 150000] [--json out.json]

Accounting per market (condition) inside the window:
  cash  = sells - buys - splits + merges - estimated taker fees
  value = sum over outcomes of net shares * final price          (only for resolved markets)
  pnl   = cash + value
A market is "incomplete" when the wallet's net shares of an outcome go negative inside the window (it sold
inventory acquired earlier) or when it used neg-risk conversions; those are reported but left out of edge tables.
Roles: a fill present in the wallet's full feed but absent from its taker-only feed is a maker fill.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import sys
import time

from . import dataapi, fees, gamma, stats

EPS = 1e-6


def _ts(v) -> int | None:
    """Parse gamma time strings ('2026-11-27T14:25:00Z', '2026-11-27 14:50:16+00', ...) to epoch seconds."""
    if not v:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).strip().replace("Z", "+00:00").replace(" ", "T", 1)
    if s.endswith("+00"):
        s += ":00"
    try:
        d = dt.datetime.fromisoformat(s)
    except ValueError:
        try:
            d = dt.datetime.fromisoformat(s.split(".")[0] + "+00:00")
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return int(d.timestamp())


def fetch_fills(wallet: str, start: int, end: int, max_fills: int | None = None) -> tuple[list[dict], bool]:
    """All fills of `wallet` in [start, end], each with role 'T' (taker) or 'M' (maker). Returns (fills, truncated)."""
    keep = ("side", "token_id", "condition_id", "size", "price", "timestamp", "slug", "event_slug", "outcome", "title", "transaction_hash")
    full = [{k: r.get(k) for k in keep} for r in dataapi.iter_trades(user=wallet, start=start, end=end, taker_only=False, max_rows=max_fills)]
    truncated = max_fills is not None and len(full) >= max_fills
    lo = min((r["timestamp"] for r in full), default=start) if truncated else start
    taker = collections.Counter()
    for r in dataapi.iter_trades(user=wallet, start=lo, end=end, taker_only=True):
        taker[_key(r)] += 1
    for r in full:
        k = _key(r)
        if taker[k] > 0:
            taker[k] -= 1
            r["role"] = "T"
        else:
            r["role"] = "M"
    if truncated:  # the oldest second may be cut in the middle: drop it so both feeds cover the same span
        full = [r for r in full if r["timestamp"] > lo]
    return full, truncated


def _key(r: dict) -> tuple:
    return (r.get("transaction_hash"), r.get("token_id"), r.get("side"), round(float(r.get("price") or 0), 8), round(float(r.get("size") or 0), 6), r.get("timestamp"))


def fetch_inventory_events(wallet: str, start: int, end: int) -> list[dict]:
    return list(dataapi.iter_activity(wallet, types="SPLIT,MERGE,REDEEM,CONVERSION", start=start, end=end))


def market_rate_at(meta: dict | None, ts: int) -> float | None:
    """Best-known taker fee rate for a market at trade time."""
    slug = (meta or {}).get("slug") or ""
    if slug.startswith("btc-updown-5m-") or slug.startswith("btc-updown-15m-"):
        return fees.btc_updown_rate(ts)
    if meta is None:
        return None
    return fees.market_rate(meta)


def build_markets(fills: list[dict], inv: list[dict], meta: dict[str, dict], res: dict[str, dict]) -> list[dict]:
    by: dict[str, dict] = {}

    def rec(cond: str) -> dict:
        m = by.get(cond)
        if m is None:
            md = meta.get(cond)
            m = by[cond] = {
                "condition": cond, "slug": (md or {}).get("slug"), "family": gamma.family(md) if md else "unknown",
                "end": _ts((md or {}).get("endDate")), "start": _ts((md or {}).get("eventStartTime") or (md or {}).get("gameStartTime")),
                "closed_at": _ts((md or {}).get("closedTime")), "neg_risk": bool((md or {}).get("negRisk")),
                "meta_rate": fees.market_rate(md) if md else None,
                "sh": collections.defaultdict(float), "buy_usd": 0.0, "sell_usd": 0.0, "split_usd": 0.0, "merge_usd": 0.0,
                "fee": 0.0, "fee_unknown": False, "taker_usd": 0.0, "maker_usd": 0.0, "n_fills": 0, "first_ts": None, "last_ts": None,
                "min_sh": collections.defaultdict(float), "conversion": False, "redeem_usd": 0.0, "outcomes": set(),
            }
        return m

    events = [("F", r["timestamp"], r) for r in fills] + [("A", r.get("timestamp") or 0, r) for r in inv]
    events.sort(key=lambda e: e[1])
    for kind, ts, r in events:
        cond = r.get("condition_id")
        if not cond:
            continue
        m = rec(cond)
        if kind == "F":
            o, size, price = r["outcome"], float(r["size"]), float(r["price"])
            usd = size * price
            m["outcomes"].add(o)
            m["n_fills"] += 1
            m["first_ts"] = ts if m["first_ts"] is None else min(m["first_ts"], ts)
            m["last_ts"] = ts if m["last_ts"] is None else max(m["last_ts"], ts)
            if r["side"] == "BUY":
                m["sh"][o] += size
                m["buy_usd"] += usd
            else:
                m["sh"][o] -= size
                m["sell_usd"] += usd
            m["min_sh"][o] = min(m["min_sh"][o], m["sh"][o])
            if r["role"] == "T":
                m["taker_usd"] += usd
                rate = market_rate_at(meta.get(cond), ts)
                if rate is None:
                    m["fee_unknown"] = True
                else:
                    m["fee"] += size * fees.fee_per_share(price, rate)
            else:
                m["maker_usd"] += usd
        else:
            typ, size, usd = r.get("type"), float(r.get("size") or 0), float(r.get("usdc_size") or 0)
            if typ == "SPLIT":
                names = gamma.jfield((meta.get(cond) or {}).get("outcomes")) or ["Yes", "No"]
                for o in names:
                    m["sh"][o] += size
                m["split_usd"] += usd or size
            elif typ == "MERGE":
                names = gamma.jfield((meta.get(cond) or {}).get("outcomes")) or ["Yes", "No"]
                for o in names:
                    m["sh"][o] -= size
                    m["min_sh"][o] = min(m["min_sh"][o], m["sh"][o])
                m["merge_usd"] += usd or size
            elif typ == "REDEEM":
                m["redeem_usd"] += usd
            elif typ == "CONVERSION":
                m["conversion"] = True
    out = []
    for cond, m in by.items():
        rv = res.get(cond)
        m["resolved"] = bool(rv and rv.get("resolved"))
        m["incomplete"] = m["conversion"] or any(v < -1e-3 for v in m["min_sh"].values())
        m["cash"] = m["sell_usd"] - m["buy_usd"] - m["split_usd"] + m["merge_usd"]
        m["value"] = None
        if m["resolved"]:
            fin = rv.get("final") or {}
            m["final"] = fin
            m["value"] = sum(sh * float(fin.get(o) or 0.0) for o, sh in m["sh"].items())
            m["gross"] = m["cash"] + m["value"]
            m["net"] = m["gross"] - m["fee"]
        m["turnover"] = m["buy_usd"] + m["sell_usd"]
        m["sh"] = dict(m["sh"])
        m["outcomes"] = sorted(m["outcomes"])
        m.pop("min_sh")
        out.append(m)
    out.sort(key=lambda m: m["first_ts"] or 0)
    return out


def _bucket_price(p: float) -> str:
    for lo, hi in ((0, .05), (.05, .15), (.15, .30), (.30, .45), (.45, .55), (.55, .70), (.70, .85), (.85, .95), (.95, .99), (.99, 1.01)):
        if lo <= p < hi:
            return f"{lo:.2f}-{min(hi, 1.0):.2f}"
    return "?"


def _bucket_life(frac: float | None, secs_to_end: float | None, windowed: bool) -> str:
    """Where in a market's life a fill happened.

    Short recurring windows (crypto up/down) are bucketed by fraction of the window; everything else by time left
    until the scheduled end, because their "start" field is not a trading window.
    """
    if secs_to_end is None:
        return "no end time"
    if secs_to_end < 0:
        return "z after end (pre-resolution)"
    if windowed and frac is not None:
        if frac < 0:
            return "a before window"
        for lo, hi, name in ((0, .25, "b first quarter"), (.25, .5, "c second quarter"), (.5, .75, "d third quarter"), (.75, .95, "e 75-95% of window"), (.95, 1.01, "f last 5% of window")):
            if lo <= frac < hi:
                return name
        return "f last 5% of window"
    for lim, name in ((60, "y under 1 min to end"), (600, "x 1-10 min to end"), (3600, "w 10-60 min to end"), (6 * 3600, "v 1-6 h to end"),
                      (24 * 3600, "u 6-24 h to end"), (7 * 86400, "t 1-7 d to end")):
        if secs_to_end < lim:
            return name
    return "s over 7 d to end"


def profile(fills: list[dict], markets: list[dict], res: dict[str, dict]) -> dict:
    """Aggregate tables. Edge per share uses only resolved, complete markets."""
    mk = {m["condition"]: m for m in markets}
    usd = collections.Counter()
    for r in fills:
        u = r["size"] * r["price"]
        usd["total"] += u
        usd["role_" + r["role"]] += u
        usd["side_" + r["side"]] += u
    tot = usd["total"] or 1.0
    fam = collections.defaultdict(lambda: {"markets": 0, "turnover": 0.0, "gross": 0.0, "fee": 0.0, "net": 0.0, "taker_usd": 0.0, "resolved": 0, "incomplete": 0, "nets": []})
    for m in markets:
        f = fam[m["family"]]
        f["markets"] += 1
        f["turnover"] += m["turnover"]
        f["taker_usd"] += m["taker_usd"]
        if m["incomplete"]:
            f["incomplete"] += 1
        if m["resolved"] and not m["incomplete"]:
            f["resolved"] += 1
            f["gross"] += m["gross"]
            f["fee"] += m["fee"]
            f["net"] += m["net"]
            f["nets"].append(m["net"])
    fam_rows = []
    for name, f in sorted(fam.items(), key=lambda kv: -kv[1]["turnover"]):
        mean, se, t = stats.mean_se(f["nets"])
        fam_rows.append({"family": name, "markets": f["markets"], "resolved_complete": f["resolved"], "incomplete": f["incomplete"],
                         "turnover": round(f["turnover"]), "taker_share": round(f["taker_usd"] / f["turnover"], 3) if f["turnover"] else None,
                         "gross": round(f["gross"], 2), "fees_est": round(f["fee"], 2), "net": round(f["net"], 2),
                         "net_pct_turnover": round(f["net"] / f["turnover"] * 100, 2) if f["turnover"] else None,
                         "net_per_market": round(mean, 2) if mean == mean else None, "t_by_market": round(t, 2) if t == t else None})

    def edge_table(keyfn):
        agg = collections.defaultdict(lambda: {"fills": 0, "sh": 0.0, "usd": 0.0, "edge": 0.0, "fee": 0.0, "by_mkt_num": collections.defaultdict(float), "by_mkt_den": collections.defaultdict(float)})
        for r in fills:
            m = mk.get(r["condition_id"])
            if not m or not m["resolved"] or m["incomplete"]:
                continue
            fin = float((m.get("final") or {}).get(r["outcome"]) or 0.0)
            size, price = r["size"], r["price"]
            e = (fin - price) * size if r["side"] == "BUY" else (price - fin) * size
            fee = 0.0
            if r["role"] == "T":
                rate = market_rate_at({"slug": m["slug"], "feeSchedule": {"rate": m.get("meta_rate")}}, r["timestamp"])
                fee = size * fees.fee_per_share(price, rate) if rate is not None else 0.0
            for key in keyfn(r, m):
                a = agg[key]
                a["fills"] += 1
                a["sh"] += size
                a["usd"] += size * price
                a["edge"] += e
                a["fee"] += fee
                a["by_mkt_num"][m["condition"]] += e - fee
                a["by_mkt_den"][m["condition"]] += size
        rows = []
        for key, a in agg.items():
            conds = list(a["by_mkt_den"])
            _, se, t = stats.ratio_cluster([a["by_mkt_num"][c] for c in conds], [a["by_mkt_den"][c] for c in conds])
            rows.append({"key": key, "fills": a["fills"], "shares": round(a["sh"]), "usd": round(a["usd"]), "avg_px": round(a["usd"] / a["sh"], 4) if a["sh"] else None,
                         "edge_c_per_sh": round(a["edge"] / a["sh"] * 100, 3) if a["sh"] else None, "fee_c_per_sh": round(a["fee"] / a["sh"] * 100, 3) if a["sh"] else None,
                         "net_c_per_sh": round((a["edge"] - a["fee"]) / a["sh"] * 100, 3) if a["sh"] else None,
                         "se_c": round(se * 100, 3) if se == se else None, "t": round(t, 2) if (t == t and se > 1e-9 and len(conds) >= 5) else None, "markets": len(conds), "net_usd": round(a["edge"] - a["fee"], 2)})
        return sorted(rows, key=lambda r: str(r["key"]))

    def life_key(r, m):
        if m["end"] is None:
            return [("life", "no end time")]
        to_end = m["end"] - (r["timestamp"] - 3)  # block time runs ~3 s after the match
        frac = None
        windowed = "-updown-" in (m["family"] or "")
        if windowed and m["start"] is not None and m["end"] > m["start"]:
            frac = ((r["timestamp"] - 3) - m["start"]) / (m["end"] - m["start"])
        return [("life", _bucket_life(frac, to_end, windowed))]

    by_role_side = edge_table(lambda r, m: [(r["role"], r["side"])])
    by_price = edge_table(lambda r, m: [(r["role"], _bucket_price(r["price"]))])
    by_life = edge_table(lambda r, m: [(r["role"],) + life_key(r, m)[0]])
    resolved = [m for m in markets if m["resolved"] and not m["incomplete"]]
    nets = [m["net"] for m in resolved]
    mean, se, t = stats.mean_se(nets)
    both = sum(1 for m in markets if len([o for o, s in m["sh"].items() if abs(s) > EPS or o in m["outcomes"]]) >= 2 and len(m["outcomes"]) >= 2)
    summary = {
        "fills": len(fills), "markets": len(markets), "resolved_complete_markets": len(resolved),
        "incomplete_markets": sum(1 for m in markets if m["incomplete"]), "unresolved_markets": sum(1 for m in markets if not m["resolved"]),
        "turnover_usd": round(usd["total"]), "maker_share_usd": round(usd["role_M"] / tot, 3), "sell_share_usd": round(usd["side_SELL"] / tot, 3),
        "markets_with_both_outcomes_traded": both, "uses_split_merge": any(m["split_usd"] or m["merge_usd"] for m in markets),
        "gross": round(sum(m["gross"] for m in resolved), 2), "fees_est": round(sum(m["fee"] for m in resolved), 2), "net": round(sum(nets), 2),
        "fee_rate_unknown_markets": sum(1 for m in markets if m["fee_unknown"]),
        "net_per_market": round(mean, 3) if mean == mean else None, "t_by_market": round(t, 2) if t == t else None,
        "win_share_markets": round(sum(1 for x in nets if x > 0) / len(nets), 3) if nets else None,
        "median_market_turnover": round(sorted(m["turnover"] for m in markets)[len(markets) // 2], 2) if markets else None,
        "max_market_turnover": round(max((m["turnover"] for m in markets), default=0), 2),
        "avg_fill_usd": round(usd["total"] / len(fills), 2) if fills else None,
    }
    return {"summary": summary, "by_family": fam_rows, "by_role_side": by_role_side, "by_role_price": by_price, "by_role_life": by_life}


def api_window(wallet: str, start: int, end: int) -> dict | None:
    """What the API itself says the account made in the window (daily series; boundaries snap to UTC days)."""
    pts = dataapi.user_pnl(wallet, "all", "1d")
    if not pts:
        return None

    def at(ts):
        prior = [p for p in pts if p["timestamp"] <= ts]
        return prior[-1] if prior else {}
    a, b = at(start), at(end)
    keys = ("trade_pnl", "fees", "fees_refunded", "taker_rebate", "maker_rebate", "reward_income", "economic_pnl", "volume_usdc", "trade_count")
    d = {k: (b.get(k) or 0) - (a.get(k) or 0) for k in keys}
    d["net"] = d["economic_pnl"]  # the API's bottom line (includes refunds, yield, LP and combo PnL, unrealized)
    d["from"], d["to"] = a.get("timestamp"), b.get("timestamp")
    return d


def analyse(ref: str, start: int, end: int, max_fills: int | None = 150_000, verbose: bool = True) -> dict:
    name, wallet = gamma.resolve_profile(ref)
    t0 = time.time()
    fills, truncated = fetch_fills(wallet, start, end, max_fills)
    if verbose:
        sys.stderr.write(f"[{name}] fills {len(fills)}{' (TRUNCATED to the most recent)' if truncated else ''} in {time.time() - t0:.0f}s\n")
    if truncated and fills:
        start = min(r["timestamp"] for r in fills)
    inv = fetch_inventory_events(wallet, start, end)
    conds = sorted({r["condition_id"] for r in fills} | {r["condition_id"] for r in inv if r.get("condition_id")})
    meta = gamma.markets_by_condition(conds)
    res = dataapi.resolutions(conds)
    markets = build_markets(fills, inv, meta, res)
    out = profile(fills, markets, res)
    out["account"] = {"name": name, "wallet": wallet, "window_start": start, "window_end": end, "truncated": truncated,
                      "inventory_events": dict(collections.Counter(r.get("type") for r in inv))}
    out["api_window"] = api_window(wallet, start, end)
    out["_markets"] = markets
    out["_fills"] = fills
    return out


def _print_table(rows: list[dict], cols: list[str]) -> None:
    if not rows:
        print("  (none)")
        return
    widths = [max(len(c), *(len(str(r.get(c, ""))) for r in rows)) for c in cols]
    print("  " + "  ".join(c.ljust(w) for c, w in zip(cols, widths)))
    for r in rows:
        print("  " + "  ".join(str(r.get(c, "")).ljust(w) for c, w in zip(cols, widths)))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ref")
    ap.add_argument("--days", type=float, default=7.0)
    ap.add_argument("--end", default=None, help="UTC date YYYY-MM-DD (exclusive end); default now")
    ap.add_argument("--max-fills", type=int, default=150_000)
    ap.add_argument("--json", default=None, help="write the full result (tables + per-market rows) to this file")
    a = ap.parse_args(argv)
    end = int(dt.datetime.strptime(a.end, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc).timestamp()) if a.end else int(time.time())
    start = int(end - a.days * 86400)
    out = analyse(a.ref, start, end, a.max_fills)
    acc, s = out["account"], out["summary"]
    f = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d %H:%M")  # noqa: E731
    print(f"{acc['name']}  {acc['wallet']}  window {f(acc['window_start'])} .. {f(acc['window_end'])} UTC{'  [TRUNCATED: most recent fills only]' if acc['truncated'] else ''}")
    print("summary:", json.dumps(s))
    print("inventory events:", acc["inventory_events"])
    if out["api_window"]:
        w = out["api_window"]
        print(f"API says for the same days: gross {w['trade_pnl']:.0f}, fees {w['fees']:.0f}, refunded {w['fees_refunded']:.0f}, rebates {w['taker_rebate'] + w['maker_rebate'] + w['reward_income']:.0f}, kept {w['net']:.0f}, volume ${w['volume_usdc']:.0f}, fills {w['trade_count']:.0f}")
    print("\nby family:")
    _print_table(out["by_family"], ["family", "markets", "resolved_complete", "incomplete", "turnover", "taker_share", "gross", "fees_est", "net", "net_pct_turnover", "net_per_market", "t_by_market"])
    for title, key in (("by role and side (edge in cents per share, resolved markets)", "by_role_side"), ("by role and price", "by_role_price"), ("by role and point in the market's life", "by_role_life")):
        print(f"\n{title}:")
        _print_table(out[key], ["key", "fills", "shares", "usd", "avg_px", "edge_c_per_sh", "fee_c_per_sh", "net_c_per_sh", "se_c", "t", "markets", "net_usd"])
    if a.json:
        slim = {k: v for k, v in out.items() if k != "_fills"}
        for m in slim["_markets"]:
            m.pop("outcomes", None)
        with open(a.json, "w") as fh:
            json.dump(slim, fh)
        print(f"\nfull result written to {a.json}")


if __name__ == "__main__":
    main()
