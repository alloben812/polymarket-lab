"""Step 8 (post hoc, added after s1-s7 had run; NOT part of the verdict).

Attack on the small-sample problem of the two rule-19 cells (crypto, politics): the SAME claim rules (16-18) applied to
every crypto and politics market of the universe that is NOT in the 5,000-market sample. Nothing else changes:
same bucket [0.95, 0.98), same window [endDate - 1 h, closedTime), same C-mid / C-cons / C-tape definitions, same
split date. Only one token's price history is fetched (token 0); the other is 1 - p, which the sample shows is exact
(the two 5-minute mids summed to 1.0000 at the 1st and 99th percentile on 111,625 paired buckets).

Usage: python3 s8_extend.py fetch | build
"""
import gzip
import json
import pickle
import sys
import time

from pmlab import dataapi
from pmlab.fees import fee_per_share
from common import DATA, EPS, T_SPLIT, read_jsonl, ts, write_jsonl

EXT = DATA / "ext"
EXT.mkdir(exist_ok=True)
FAMS = ("crypto", "politics")
CHUNK = 14 * 86400
LO, HI = 0.95, 0.98


def fee_rate(m):
    if m.get("feesEnabled") is False:
        return 0.0
    r = (m.get("feeSchedule") or {}).get("rate")
    return 0.05 if r is None else float(r)


def markets():
    uni = read_jsonl(DATA / "universe.jsonl.gz")
    s = {m["conditionId"] for m in read_jsonl(DATA / "sample.jsonl.gz")}
    out = [m for m in uni if m["conditionId"] not in s and m["family"] in FAMS
           and ts(m["closedTime"]) > ts(m["endDate"]) - 3600]
    out.sort(key=lambda m: m["conditionId"])
    return out


def fetch():
    ms = markets()
    print("markets", len(ms), flush=True)
    res_path = EXT / "resolutions.json"
    res = json.loads(res_path.read_text()) if res_path.exists() else {}
    todo = [m["conditionId"] for m in ms if m["conditionId"] not in res]
    for i in range(0, len(todo), 200):
        res.update(dataapi.resolutions(todo[i:i + 200]))
        res_path.write_text(json.dumps(res))
    print("resolutions", len(res), flush=True)
    hp = EXT / "hist.jsonl.gz"
    done = set()
    if hp.exists():
        with gzip.open(hp, "rt") as f:
            for line in f:
                try:
                    done.add(json.loads(line)["cid"])
                except ValueError:
                    pass
    t0 = time.time()
    n = 0
    with gzip.open(hp, "at") as f:
        for m in ms:
            if m["conditionId"] in done:
                continue
            end, closed = ts(m["endDate"]), ts(m["closedTime"])
            a, stop = end - 3600 - 900, closed + 300
            row = {"cid": m["conditionId"], "h": [], "err": None}
            try:
                while a < stop:
                    b = min(a + CHUNK, stop)
                    for r in dataapi.prices_history(m["clobTokenIds"][0], int(a), int(b), 300):
                        row["h"].append([r["timestamp"], r["price"], r.get("resolution_seconds")])
                    a = b
            except Exception as e:  # noqa: BLE001
                row["err"] = repr(e)[:300]
            f.write(json.dumps(row) + "\n")
            n += 1
            if n % 200 == 0:
                f.flush()
                print(f"hist {n} {time.time()-t0:.0f}s", flush=True)
    print("hist done", flush=True)


def build():
    ms = {m["conditionId"]: m for m in markets()}
    res = json.loads((EXT / "resolutions.json").read_text())
    panel, drops = [], {}
    with gzip.open(EXT / "hist.jsonl.gz", "rt") as f:
        for line in f:
            h = json.loads(line)
            m = ms[h["cid"]]
            end, closed = ts(m["endDate"]), ts(m["closedTime"])
            r = res.get(h["cid"])
            pay = None
            if r and r.get("resolved"):
                pay = [r["final"].get(o) for o in m["outcomes"]]
                if any(p is None for p in pay):
                    pay = None
            drop = "unresolved" if pay is None else ("error" if h["err"] else None)
            pts = sorted({(t, p) for t, p, rs in h["h"] if rs == 300 and t < closed})
            if not drop and not pts:
                drop = "no_prices"
            row = {"cid": h["cid"], "slug": m["slug"], "fam": m["family"], "event": m.get("event_slug") or m["slug"], "end": end,
                   "closed": closed, "late": closed >= T_SPLIT, "rate": fee_rate(m), "tokens": m["clobTokenIds"], "pay": pay,
                   "drop": drop, "claim": None}
            if drop:
                drops[drop] = drops.get(drop, 0) + 1
                panel.append(row)
                continue
            T = [t for t, _ in pts]
            P0 = {t: p for t, p in pts}
            for i, t in enumerate(T):
                if t < end - 3600:
                    continue
                p0 = P0[t]
                p1 = 1 - p0
                if abs(p0 - p1) < EPS:
                    continue
                k = 0 if p0 > p1 else 1
                pf = (p0, p1)[k]
                if LO - EPS <= pf < HI - EPS:
                    nxt = P0.get(t + 300) if t + 300 < closed else None
                    row["claim"] = {"t": t, "k": k, "p": pf, "pay": pay[k], "lock_h": (closed - t) / 3600,
                                    "p_next": None if nxt is None else (nxt, 1 - nxt)[k]}
                    break
            panel.append(row)
    pickle.dump(panel, open(EXT / "panel.pkl", "wb"))
    ent = [r for r in panel if r["claim"]]
    print("panel", len(panel), "drops", drops, "entries", len(ent))


def tapes():
    """Whole-market tapes of every extension entry market (same 60,000-row cap as rule 20)."""
    panel = pickle.load(open(EXT / "panel.pkl", "rb"))
    td = DATA / "tapes"
    todo = [r["cid"] for r in panel if r["claim"] and not (td / f"{r['cid']}.json.gz").exists()]
    print("tapes to fetch", len(todo), flush=True)
    t0 = time.time()
    for i, cid in enumerate(todo):
        rows = [[r["timestamp"], r["side"], r["token_id"], r["price"], r["size"], r["proxy_wallet"]]
                for r in dataapi.iter_trades(condition=cid, max_rows=60000)]
        with gzip.open(td / f"{cid}.json.gz", "wt") as f:
            json.dump({"cid": cid, "capped": len(rows) >= 60000, "rows": rows}, f)
        if i % 50 == 0:
            print(f"tape {i+1}/{len(todo)} {time.time()-t0:.0f}s", flush=True)
    print("tapes done", flush=True)


def analyse():
    from collections import defaultdict
    from pmlab.stats import ratio_cluster, wilson
    from common import OUT
    panel = pickle.load(open(EXT / "panel.pkl", "rb"))
    ok = [r for r in panel if not r["drop"]]
    ent = [r for r in ok if r["claim"]]
    L = ["# Post-hoc extension (s8_extend.py): the claim on every crypto and politics market of the universe outside the 5,000 sample",
         "", f"Markets: {len(panel)}; dropped: { {d: sum(1 for r in panel if r['drop'] == d) for d in {r['drop'] for r in panel if r['drop']}} }; "
         f"analysed {len(ok)}; with a claim entry {len(ent)}.", ""]

    def cl(items):
        num, den = defaultdict(float), defaultdict(float)
        for ev, pr, sh in items:
            num[ev] += pr
            den[ev] += sh
        ev = list(num)
        return ratio_cluster([num[e] for e in ev], [den[e] for e in ev]) + (len(ev),)

    L += ["variant | category | period | markets | events | not-win | win % | Wilson 95% | mean price | net c/share | SE c | t (event) | mean lock-up h",
          "|".join(["---"] * 13)]
    for var in ("C-mid", "C-cons", "C-tape A1"):
        for fam in FAMS + ("both",):
            for per in ("early", "late", "both"):
                rs = [r for r in ent if (fam == "both" or r["fam"] == fam) and (per == "both" or r["late"] == (per == "late"))]
                items, prices, wins, locks = [], [], 0, []
                for r in rs:
                    c = r["claim"]
                    if var == "C-tape A1":
                        p_ = td_rows(r)
                        if p_ is None:
                            continue
                        pr, sh, cost = p_
                        items.append((r["event"], pr, sh))
                        prices.append(cost / sh)
                    else:
                        if var == "C-mid":
                            p = c["p"]
                        else:
                            if c["p_next"] is None:
                                continue
                            p = min(c["p_next"] + 0.005, 0.999)
                        f = fee_per_share(p, r["rate"])
                        items.append((r["event"], c["pay"] - p - f, 1.0))
                        prices.append(p + f)
                    wins += c["pay"] >= 1
                    locks.append(c["lock_h"])
                if not items:
                    continue
                m, se, t, nev = cl(items)
                lo, hi = wilson(wins, len(items))
                L.append(f"{var} | {fam} | {per} | {len(items)} | {nev} | {len(items)-wins} | {100*wins/len(items):.2f} | {100*lo:.1f}-{100*hi:.1f} | "
                         f"{sum(prices)/len(prices):.4f} | {100*m:+.2f} | {100*se:.2f} | {t:+.1f} | {sum(locks)/len(locks):.1f}")
    L.append("")
    L.append("Losing entry markets: " + ", ".join(f"{r['slug']} ({r['fam']}, entry {r['claim']['p']:.3f}, payoff {r['claim']['pay']})" for r in ent if r["claim"]["pay"] < 1))
    (OUT / "extension_tables.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


def td_rows(r):
    """C-tape A1 on one market: taker BUY rows on the entry-time favourite at [0.95, 0.98), block time in [t, closedTime]."""
    p = DATA / "tapes" / f"{r['cid']}.json.gz"
    if not p.exists():
        return None
    d = json.load(gzip.open(p, "rt"))
    c = r["claim"]
    tok = r["tokens"][c["k"]]
    pr = sh = cost = 0.0
    for t, side, tk, price, size, w in d["rows"]:
        if side == "BUY" and tk == tok and LO - EPS <= price < HI - EPS and c["t"] <= t <= r["closed"]:
            f = fee_per_share(price, r["rate"])
            pr += size * (c["pay"] - price - f)
            sh += size
            cost += size * (price + f)
    return (pr, sh, cost) if sh > 0 else None


if __name__ == "__main__":
    {"fetch": fetch, "build": build, "tapes": tapes, "analyse": analyse}[sys.argv[1]]()
