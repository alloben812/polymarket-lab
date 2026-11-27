"""Step 7: real asks from the L2 archive for a subset of jumps, compared with the tape rule (protocol section 9).
Run with: python3 -I s7_l2.py   (reads downloaded parquet files; nothing from them is executed)."""
import collections, json, random, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import l2lib

OUT = HERE / "out"
DELAYS = [10, 30, 120, 600]
CATS = {"geopolitics": ["geopolitics", "world", "politics", "elections"], "other politics": ["politics", "world", "geopolitics", "elections"],
        "elections": ["elections", "politics", "world", "geopolitics"]}


def load_rows(j, uni):
    """All L2 rows of the market from the hour(s) covering [t0 - 120 s, t0 + 1300 s]."""
    hours = sorted({(j["t0"] - 120) // 3600, (j["t0"] + 1300) // 3600})
    for cat in CATS[j["cat"]]:
        rows, ok = [], True
        for h in hours:
            p = l2lib.hour_file(h * 3600, cat)
            if p is None:
                ok = False
                break
            rows += l2lib.market_rows(p, j["c"])
        if ok and rows:
            return rows, cat
    return [], None


class Book:
    def __init__(self):
        self.bids, self.asks, self.ready = {}, {}, False

    def apply(self, r):
        if r["event_type"] == "book":
            self.bids = {float(x["price"]): float(x["size"]) for x in (r["bids"] or [])}
            self.asks = {float(x["price"]): float(x["size"]) for x in (r["asks"] or [])}
            self.ready = True
        elif r["event_type"] == "price_change" and self.ready:
            side = self.bids if r["side"] == "BUY" else self.asks
            p, s = float(r["price"]), float(r["size"])
            old = side.get(p, 0.0)
            if s <= 0:
                side.pop(p, None)
            else:
                side[p] = s
            return (r["side"], p, old, s)
        return None

    def f_asks(self, same):
        """Ask levels of the favoured outcome: this asset's asks, or the mirror of its bids."""
        if same:
            return sorted(self.asks.items())
        return sorted((round(1 - p, 4), s) for p, s in self.bids.items())


def sweep(levels, budget=200.0, pmax=0.90):
    spent = sh = 0.0
    for p, s in levels:
        if p > pmax or spent >= budget:
            break
        q = min(s, (budget - spent) / p)
        spent += q * p
        sh += q
    return spent, sh


def analyse(j, uni_tokens):
    rows, cat = load_rows(j, None)
    if not rows:
        return {"c": j["c"], "found": False}
    yes_tok, no_tok = uni_tokens[j["c"]]
    f_tok = yes_tok if j["dir"] > 0 else no_tok
    cnt = collections.Counter(r["asset"] for r in rows if r["event_type"] in ("book", "price_change"))
    main_asset = cnt.most_common(1)[0][0]
    same = main_asset == f_tok
    ev = sorted((r for r in rows if r["asset"] == main_asset and r["event_type"] in ("book", "price_change")),
                key=lambda r: (r["ms"], 0 if r["event_type"] == "book" else 1, r["row_ordinal"]))
    trades = sorted((r for r in rows if r["event_type"] == "last_trade_price"), key=lambda r: r["ms"])
    # exchange-time t0: first trade print with F-price >= pf_pre + 0.10 within +-60 s of the block-based t0
    def fpx(r):
        y = float(r["price"]) if r["asset"] == yes_tok else 1 - float(r["price"])
        return y if j["dir"] > 0 else 1 - y
    t0x = next((r["ms"] for r in trades if abs(r["ms"] / 1000 - j["t0"]) <= 60 and fpx(r) >= j["pf_pre"] + 0.10), None)
    out = {"c": j["c"], "found": True, "file_cat": cat, "t0_block_minus3": j["t0"], "t0_exchange_ms": t0x, "n_events": len(ev), "n_trades": len(trades)}
    if t0x is None:
        return out
    res = {}
    for d in DELAYS:
        a, b = t0x + d * 1000, t0x + (d + 600) * 1000
        book = Book()
        state_at_a = None
        ub_spent = ub_sh = 0.0
        min_ask, time_le90, last_ms, last_best = None, 0.0, None, None
        for r in ev:
            if r["ms"] > b:
                break
            if r["ms"] > a and state_at_a is None and book.ready:
                lv = book.f_asks(same)
                state_at_a = sweep(lv)
                ub_spent, ub_sh = state_at_a
                best = lv[0][0] if lv else None
                res_best_at_a = best
                last_ms, last_best = a, best
                min_ask = best
            ch = book.apply(r)
            if state_at_a is None:
                continue
            lv = book.f_asks(same)
            best = lv[0][0] if lv else None
            if last_best is not None and last_best <= 0.90:
                time_le90 += (min(r["ms"], b) - last_ms) / 1000
            last_ms, last_best = r["ms"], best
            if best is not None and (min_ask is None or best < min_ask):
                min_ask = best
            # upper bound: liquidity newly posted on the F-ask side at <= 0.90 after the first sweep
            if ch and ub_spent < 200:
                side, p, old, new = ch
                if (same and side == "SELL") or (not same and side == "BUY"):
                    pf = p if same else round(1 - p, 4)
                    if pf <= 0.90 and new > old:
                        q = min(new - old, (200 - ub_spent) / pf)
                        ub_spent += q * pf
                        ub_sh += q
        if state_at_a is None:
            res[d] = None
            continue
        if last_best is not None and last_best <= 0.90 and last_ms < b:
            time_le90 += (b - last_ms) / 1000
        res[d] = {"best_ask_at_start": res_best_at_a, "sweep_usd": state_at_a[0], "sweep_avg": state_at_a[0] / state_at_a[1] if state_at_a[1] else None,
                  "ub_usd": ub_spent, "ub_avg": ub_spent / ub_sh if ub_sh else None, "min_ask": min_ask, "sec_ask_le90": time_le90}
    out["delays"] = res
    return out


def main():
    import gzip
    jumps = json.load(open(OUT / "jumps.json"))
    labels = {}
    lp = OUT / "labels.csv"
    if lp.exists():
        import csv
        for r in csv.DictReader(open(lp)):
            labels[(r["c"], r["t0"])] = r["label"]
    pool = [j for j in jumps if j["status"] == "main" and labels.get((j["c"], str(j["t0"])), "unscheduled") == "unscheduled"]
    rng = random.Random(20261127)
    pick = pool if len(pool) <= 30 else rng.sample(pool, 30)
    tok = {}
    with gzip.open(HERE.parents[2] / "data" / "gaps_news" / "markets_all.jsonl.gz", "rt") as f:
        want = {j["c"] for j in pick}
        for line in f:
            m = json.loads(line)
            if m["conditionId"] in want:
                t = json.loads(m["clobTokenIds"])
                tok[m["conditionId"]] = (t[0], t[1])
    res = []
    for j in sorted(pick, key=lambda j: j["t0"]):
        r = analyse(j, tok)
        r["slug"] = j["slug"]
        res.append(r)
        print(j["t0_iso"], j["slug"][:50], {k: v for k, v in r.items() if k not in ("delays", "slug", "c")}, flush=True)
        for d, v in (r.get("delays") or {}).items():
            print("   d", d, v, flush=True)
    json.dump(res, open(OUT / "l2.json", "w"))


if __name__ == "__main__":
    main()
