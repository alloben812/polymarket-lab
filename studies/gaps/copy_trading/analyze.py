"""Step 3: simulate the 6 copy variants + reference on the sampled entries (protocol.md), write out/ tables."""
import collections
import gzip
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from pmlab import gamma
from pmlab.fees import market_rate, fee_per_share
from pmlab.stats import ratio_cluster

ROOT = Path("/home/user/polymarket-lab")
OUT = ROOT / "studies/gaps/copy_trading/out"
CACHE = ROOT / "data/gaps_copy"
LAG = 3
SIZE = 10.0
DELAYS = [10, 60, 300]
FALLBACK = {"sports": .05, "finance": .05, "tech": .05, "crypto": .01, "weather": .01, "economics": .01, "culture": .01,
            "mentions": .01, "politics": .05, "other": .05}


def load(p):
    try:
        return json.load(gzip.open(p, "rt"))
    except Exception:
        return None


def category(m):
    if not m:
        return "unknown"
    tags = gamma.tag_slugs(m)
    slug = m.get("slug") or ""
    if any("mention" in t for t in tags):
        return "mentions"
    f = gamma.family(m)
    if "updown" in f:
        return "crypto-updown"
    if any(t in ("esports",) for t in tags):
        return "esports"
    return f


def rate_of(m, cat):
    r = market_rate(m) if m else None
    if r is not None:
        return r
    if cat == "crypto-updown":
        return .05 if ("btc" in (m or {}).get("slug", "") and ("5m" in m["slug"] or "15m" in m["slug"])) else .01
    return FALLBACK.get(cat, .05)


def blocks(rows, want, side_fn):
    """Group per block time the rows that give evidence for `want`: list of (T, vwap, shares) ascending."""
    by = collections.OrderedDict()
    for r in rows:
        px = side_fn(r, want)
        if px is None:
            continue
        b = by.setdefault(r["t"], [0.0, 0.0])
        b[0] += px * r["z"]
        b[1] += r["z"]
    return [(t, v / z, z) for t, (v, z) in by.items() if z > 0]


def buy_px(r, x):
    if r["s"] == "BUY" and r["o"] == x:
        return r["p"]
    if r["s"] == "SELL" and r["o"] != x:
        return 1 - r["p"]
    return None


def sell_px(r, x):
    if r["s"] == "SELL" and r["o"] == x:
        return r["p"]
    if r["s"] == "BUY" and r["o"] != x:
        return 1 - r["p"]
    return None


def first_block(bl, lo, hi):
    for t, v, z in bl:
        if lo <= t - LAG <= hi:
            return t, v, z
        if t - LAG > hi:
            return None
    return None


def main():
    sel = {s["wallet"]: s for s in json.load(open(OUT / "selected.json"))}
    summ = json.load(open(CACHE / "entry_summary.json"))
    sample = json.load(open(CACHE / "sample.json"))
    meta = json.load(open(CACHE / "meta.json"))
    res = json.load(open(CACHE / "resolutions.json"))
    # wallet type from the early window
    wtype = {}
    for s in summ:
        if s["win"] == "early":
            # deviation 2 (results.md): both feeds are capped at 4,000 newest rows, so compare them on the common span
            raw = load(CACHE / f"buys_early_{s['wallet']}.json.gz") or {"full": [], "taker": []}
            t0 = max(min((r["t"] for r in raw["full"]), default=0), min((r["t"] for r in raw["taker"]), default=0))
            fu = sum(r["z"] * r["p"] for r in raw["full"] if r["t"] >= t0)
            tu = sum(r["z"] * r["p"] for r in raw["taker"] if r["t"] >= t0)
            sh = min(1.0, tu / fu) if fu > 0 else None
            wtype[s["wallet"]] = "unknown" if sh is None else ("taker-style" if sh >= .6 else "maker-style" if sh <= .4 else "mixed")
            sel[s["wallet"]]["taker_share_early"] = sh
    trades = []
    skipped = collections.Counter()
    tape_cache = {}
    for e in sample:
        c, w, x, tb = e["c"], e["wallet"], e["o"], e["t"]
        tp_path = CACHE / "tape" / f"{c}.json.gz"
        wm_path = CACHE / "wm" / f"{w}_{c}.json.gz"
        if not tp_path.exists() or not wm_path.exists():
            skipped["not fetched"] += 1
            continue
        if c not in tape_cache:
            tape_cache.clear() if len(tape_cache) > 200 else None
            tape_cache[c] = load(tp_path)
        tp = tape_cache[c]
        if tp is None:
            skipped["not fetched"] += 1
            tape_cache.pop(c)
            continue
        if not (tp["complete"] or (tp["oldest"] is not None and tp["oldest"] <= tb - 60)):
            skipped["tape cap (not evaluable)"] += 1
            continue
        rows = sorted(tp["rows"], key=lambda r: r["t"])
        m = meta.get(c)
        cat = category(m)
        rate = rate_of(m, cat)
        rz = res.get(c) or {}
        outs = list((rz.get("tokens") or {}).keys())
        if x not in outs and outs:
            skipped["outcome mismatch"] += 1
            continue
        resolved = bool(rz.get("resolved"))
        final = (rz.get("final") or {}).get(x) if resolved else None
        if resolved and final is None:
            resolved = False
        last = None
        for r in reversed(rows):
            p = buy_px(r, x)
            if p is None:
                p = sell_px(r, x)
            if p is not None:
                last = p
                break
        payoff = float(final) if resolved else last
        if payoff is None:
            skipped["no payoff"] += 1
            continue
        etype = "TAKER" if any(r["t"] == tb and r["w"] == w and r["o"] == x and r["s"] == "BUY" for r in rows) else "MAKER"
        bb = blocks(rows, x, buy_px)
        sb = blocks(rows, x, sell_px)
        wm = sorted(load(wm_path) or [], key=lambda r: r["t"])
        cb = cs = 0.0
        tc = None
        for r in wm:
            if r["tok"] != e["tok"] or r["t"] < tb:
                continue
            if r["s"] == "BUY":
                cb += r["z"]
            else:
                cs += r["z"]
                if cb > 0 and cs >= 0.5 * cb:
                    tc = r["t"]
                    break
        closed_ts = None
        if m:
            for k in ("closedTime", "endDate"):
                if m.get(k):
                    try:
                        closed_ts = datetime.fromisoformat(str(m[k]).replace("Z", "+00:00").replace(" ", "T")).timestamp()
                        break
                    except Exception:
                        pass
        base = {"wallet": w, "win": e["win"], "c": c, "tok": e["tok"], "tb": tb, "day": tb // 86400, "cat": cat, "rate": rate,
                "etype": etype, "wtype": wtype.get(w, "unknown"), "resolved": resolved, "payoff": payoff,
                "wallet_px": e["p"], "wallet_closed": tc is not None, "hold_h": ((closed_ts - tb) / 3600) if closed_ts else None,
                "slug": e.get("slug")}
        # reference: wallet's own price
        p0 = e["p"]
        if 0 < p0 < 1:
            q = SIZE / p0
            fee = q * fee_per_share(p0, rate) if etype == "TAKER" else 0.0
            cost = q * p0 + fee
            trades.append({**base, "variant": "ref_wallet_price", "filled": True, "cost": cost, "net": q * payoff - cost, "px": p0,
                           "lag_s": 0})
        for d in DELAYS:
            fb = first_block(bb, tb + d, tb + d + 30)
            if fb is None:
                for ex in ("hold", "mirror"):
                    trades.append({**base, "variant": f"d{d}_{ex}", "filled": False})
                continue
            T, v, z = fb
            if not (0 < v < 1):
                for ex in ("hold", "mirror"):
                    trades.append({**base, "variant": f"d{d}_{ex}", "filled": False})
                continue
            q = min(SIZE / v, z)
            if q * v < 1.0:
                for ex in ("hold", "mirror"):
                    trades.append({**base, "variant": f"d{d}_{ex}", "filled": False, "too_small": True})
                continue
            cost = q * v + q * fee_per_share(v, rate)
            hold_net = q * payoff - cost
            trades.append({**base, "variant": f"d{d}_hold", "filled": True, "cost": cost, "net": hold_net, "px": v, "q": q,
                           "lag_s": T - LAG - tb, "slip": v - p0})
            mir_net, sold = hold_net, 0.0
            if tc is not None:
                sbk = first_block(sb, max(tc + d, T - LAG), max(tc + d, T - LAG) + 30)
                if sbk is not None:
                    _, sv, sz = sbk
                    sold = min(q, sz)
                    proceeds = sold * sv - sold * fee_per_share(sv, rate)
                    mir_net = proceeds + (q - sold) * payoff - cost
            trades.append({**base, "variant": f"d{d}_mirror", "filled": True, "cost": cost, "net": mir_net, "px": v, "q": q,
                           "lag_s": T - LAG - tb, "sold": sold, "slip": v - p0})
    json.dump(trades, gzip.open(CACHE / "trades.json.gz", "wt"))
    json.dump(sel, open(OUT / "selected_typed.json", "w"), indent=1)
    print("skipped", dict(skipped))
    print("sim rows", len(trades))


if __name__ == "__main__":
    main()
