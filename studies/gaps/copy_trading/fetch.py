"""Step 2: entries, samples, per-entry wallet fills in the market, market tapes, resolutions, gamma metadata.

Follows protocol.md 'Entries and sample'. Raw caches in data/gaps_copy/ (not in git).
"""
import gzip
import json
import random
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pmlab.http import get_json
from pmlab import gamma, dataapi

D = "https://data-api.polymarket.com/v2"
ROOT = Path("/home/user/polymarket-lab")
OUT = ROOT / "studies/gaps/copy_trading/out"
CACHE = ROOT / "data/gaps_copy"
WIN = {"early": (1794009600, 1795219200, 15), "late": (1795219200, 1795651200, 25)}
CAP_ROWS = 4000
CAP_PAGES = 25


def walk(params, max_rows):
    rows, cursor = [], None
    anchor = {k: v for k, v in params.items() if k != "limit"}
    while True:
        d = get_json(f"{D}/trades", {**anchor, "cursor": cursor} if cursor else params)
        page = d.get("data") or []
        rows += page
        cursor = (d.get("pagination") or {}).get("next_cursor")
        if not cursor or not page or len(rows) >= max_rows:
            return rows[:max_rows], bool(cursor) and len(rows) >= max_rows


def wallet_window(w, win):
    p = CACHE / f"buys_{win}_{w}.json.gz"
    if p.exists():
        return json.load(gzip.open(p, "rt"))
    a, b, _ = WIN[win]
    full, capped = walk({"user": w, "taker_only": "false", "side": "BUY", "start": a, "end": b - 1, "limit": 1000}, CAP_ROWS)
    tk, tcap = walk({"user": w, "taker_only": "true", "side": "BUY", "start": a, "end": b - 1, "limit": 1000}, CAP_ROWS) if win == "early" else ([], False)
    obj = {"full": [slim(r) for r in full], "capped": capped, "taker": [slim(r) for r in tk], "tcapped": tcap}
    json.dump(obj, gzip.open(p, "wt"))
    return obj


def slim(r):
    return {"t": r["timestamp"], "s": r["side"], "o": r["outcome"], "z": float(r["size"]), "p": float(r["price"]),
            "tok": r["token_id"], "c": r["condition_id"], "h": r.get("transaction_hash"), "slug": r.get("slug"),
            "w": r.get("proxy_wallet")}


def wallet_market(w, c):
    p = CACHE / "wm" / f"{w}_{c}.json.gz"
    if p.exists():
        return json.load(gzip.open(p, "rt"))
    rows, _ = walk({"user": w, "condition": c, "taker_only": "false", "limit": 1000}, 20000)
    obj = [slim(r) for r in rows]
    p.parent.mkdir(exist_ok=True)
    json.dump(obj, gzip.open(p, "wt"))
    return obj


def tape(c, tmin):
    """Whole-market tape newest->oldest until older than tmin or CAP_PAGES pages. Cached with its reach."""
    p = CACHE / "tape" / f"{c}.json.gz"
    if p.exists():
        obj = json.load(gzip.open(p, "rt"))
        if obj["complete"] or obj["oldest"] <= tmin or obj["pages"] >= CAP_PAGES:
            return obj
    rows, cursor, pages = [], None, 0
    params = {"condition": c, "limit": 1000}
    complete = False
    while pages < CAP_PAGES:
        d = get_json(f"{D}/trades", {"condition": c, "cursor": cursor} if cursor else params)
        page = d.get("data") or []
        pages += 1
        rows += [{"t": r["timestamp"], "s": r["side"], "o": r["outcome"], "z": float(r["size"]), "p": float(r["price"]),
                  "w": (r.get("proxy_wallet") or "").lower()} for r in page]
        cursor = (d.get("pagination") or {}).get("next_cursor")
        if not cursor or not page:
            complete = True
            break
        if rows and rows[-1]["t"] < tmin:
            break
    obj = {"rows": rows, "complete": complete, "oldest": rows[-1]["t"] if rows else None, "pages": pages}
    p.parent.mkdir(exist_ok=True)
    json.dump(obj, gzip.open(p, "wt"))
    return obj


def entries_of(obj):
    first = {}
    for r in sorted(obj["full"], key=lambda r: (r["t"], r["tok"])):
        if r["s"] == "BUY" and r["tok"] not in first:
            first[r["tok"]] = r
    return sorted(first.values(), key=lambda r: (r["t"], r["tok"]))


def main():
    sel = json.load(open(OUT / "selected.json"))
    wallets = [s["wallet"] for s in sel]
    jobs = [(w, win) for w in wallets for win in WIN]
    with ThreadPoolExecutor(4) as ex:
        res = dict(zip(jobs, ex.map(lambda j: wallet_window(*j), jobs)))
    print("wallet windows fetched", flush=True)
    rng = random.Random(20261127)
    sample, summary = [], []
    for w in wallets:
        for win in WIN:
            obj = res[(w, win)]
            ents = entries_of(obj)
            a, b, k = WIN[win]
            span0 = min((r["t"] for r in obj["full"]), default=b) if obj["capped"] else a
            summary.append({"wallet": w, "win": win, "fills": len(obj["full"]), "capped": obj["capped"], "entries": len(ents),
                            "span0": span0, "span1": b, "entry_days": [r["t"] // 86400 for r in ents],
                            "buy_usd": sum(r["z"] * r["p"] for r in obj["full"]),
                            "taker_buy_usd": sum(r["z"] * r["p"] for r in obj["taker"]), "tcapped": obj["tcapped"]})
            pick = rng.sample(ents, min(k, len(ents))) if ents else []
            for r in pick:
                sample.append({"wallet": w, "win": win, **r})
    json.dump(summary, open(CACHE / "entry_summary.json", "w"))
    json.dump(sample, open(CACHE / "sample.json", "w"))
    print("sample", len(sample), flush=True)
    conds = sorted({s["c"] for s in sample})
    meta = gamma.markets_by_condition(conds)
    json.dump(meta, open(CACHE / "meta.json", "w"))
    print("meta", len(meta), flush=True)

    def per_entry(s):
        try:
            wm = wallet_market(s["wallet"], s["c"])
            tp = tape(s["c"], s["t"] - 60)
            return True
        except Exception as e:
            print("ERR", s["c"], e, flush=True)
            return False

    done = 0
    with ThreadPoolExecutor(4) as ex:
        for ok in ex.map(per_entry, sample):
            done += 1
            if done % 100 == 0:
                print("entries done", done, flush=True)
    res_ = dataapi.resolutions(conds, cache=False)
    json.dump(res_, open(CACHE / "resolutions.json", "w"))
    print("resolutions", len(res_), flush=True)


if __name__ == "__main__":
    main()
