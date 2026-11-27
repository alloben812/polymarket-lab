"""Is the book inside one ladder (same ticker, same period, strikes K1<K2<...) hedged?  For every ladder: net cost after
merges and fees, the WORST and BEST payoff over all outcomes consistent with strike ordering, and the realized payoff.
A ladder with worst >= cost is a locked (arbitrage-like) position; worst = 0 is a naked directional bet."""
import sys, re, json, collections, statistics
import fin
from pmlab import fees, stats

def rate(ts): return 0.05 if ts >= 1795219140 else 0.04
def strike(title):
    t = title.replace(",", "")
    m = re.search(r"hit \((HIGH|LOW)\) \$?([\d.]+)", t)
    if m: return ("hit" + m.group(1), float(m.group(2)))
    m = re.search(r"(?:close[sd]? above|above) \$?([\d.]+)", t)
    if m: return ("above", float(m.group(1)))
    m = re.search(r"close at \$?([\d.]+)-\$?([\d.]+)", t)
    if m: return ("range", float(m.group(1)))
    if "Up or Down" in t: return ("updown", 0.0)
    return (None, None)

def run(name, verbose=False):
    d = fin.load(name); meta = d["meta"]; res = d["res"]
    pos = collections.defaultdict(lambda: dict(sh=collections.Counter(), cash=0.0, usd=0.0, t0=None, t1=None, title=None, bought=collections.Counter(), paid=collections.Counter()))
    for f in sorted(d["fills"], key=lambda r: r["timestamp"]):
        c = f["condition_id"]; p = pos[c]; sz, px, t = float(f["size"]), float(f["price"]), int(f["timestamp"]); sgn = 1 if f["side"] == "BUY" else -1
        fee = fees.taker_fee(sz, px, rate(t)) if f["role"] == "T" else 0.0
        p["sh"][f["outcome"]] += sgn * sz; p["cash"] -= sgn * sz * px + fee; p["usd"] += sz * px; p["title"] = f["title"]
        p["t0"] = t if p["t0"] is None else min(p["t0"], t); p["t1"] = t if p["t1"] is None else max(p["t1"], t)
        if sgn > 0: p["bought"][f["outcome"]] += sz; p["paid"][f["outcome"]] += sz * px
    merged = collections.Counter(); 
    for e in d["inv"]:
        c = e.get("condition_id")
        if c in pos and e["type"] in ("MERGE", "SPLIT"):
            s = float(e["size"]) * (1 if e["type"] == "MERGE" else -1); merged[c] += s
            pos[c]["cash"] += s
            for o in ("Yes", "No", "Up", "Down"):
                if o in pos[c]["sh"] or (o in ("Yes", "No") and "Up" not in pos[c]["sh"] and "Down" not in pos[c]["sh"]) or (o in ("Up", "Down") and ("Up" in pos[c]["sh"] or "Down" in pos[c]["sh"])):
                    pos[c]["sh"][o] -= s
    # --- pairs inside ONE market (both outcomes bought)
    pair_sh = pair_profit = 0.0; npair = 0; tot_bought_usd = 0.0
    for c, p in pos.items():
        outs = list(p["bought"]); tot_bought_usd += sum(p["paid"].values())
        if len(outs) == 2:
            q = min(p["bought"].values()); a = sum(p["paid"][o] / p["bought"][o] for o in outs)
            pair_sh += q; pair_profit += q * (1 - a); npair += 1
    print(f"\n######## {name}: markets {len(pos)}, both outcomes bought in {npair}; paired shares {pair_sh:.0f}, locked pair profit before fee {pair_profit:.0f} (avg pair cost {1 - pair_profit / pair_sh if pair_sh else float('nan'):.3f}); merged shares {sum(merged.values()):.0f}; total bought ${tot_bought_usd:.0f}")
    # --- ladders
    L = collections.defaultdict(list)
    for c, p in pos.items():
        m = meta.get(c) or {}; ty, tk = fin.mtype(p["title"], m.get("slug")); kind, K = strike(p["title"] or "")
        if ty is None or kind is None or kind == "range": continue
        L[(tk, ty, kind, m.get("endDate"))].append((K, c))
    rows = []
    for key, items in L.items():
        items.sort(reverse=(key[2] == "hitLOW")); n = len(items)
        cost = -sum(pos[c]["cash"] for _, c in items)
        if any(v < -1e-3 for _, c in items for v in pos[c]["sh"].values()): continue      # inventory from before the window
        pays = []
        if key[2] == "updown":
            c = items[0][1]; pays = [pos[c]["sh"].get("Up", 0), pos[c]["sh"].get("Down", 0)]
        else:
            for j in range(n + 1):
                pays.append(sum(pos[c]["sh"].get("Yes", 0) if i < j else pos[c]["sh"].get("No", 0) for i, (_, c) in enumerate(items)))
        allres = all((res.get(c) or {}).get("resolved") for _, c in items)
        real = sum(v * ((res.get(c) or {}).get("final") or {}).get(o, 0) for _, c in items for o, v in pos[c]["sh"].items()) if allres else None
        rows.append(dict(key=key, n=n, cost=cost, worst=min(pays), best=max(pays), real=real, usd=sum(pos[c]["usd"] for _, c in items),
                         span=max(pos[c]["t1"] for _, c in items) - min(pos[c]["t0"] for _, c in items)))
    json.dump([{**r, "key": list(r["key"])} for r in rows], open(f"{fin.HERE}/cache/{name}_ladders.json", "w"))
    print(f"{'type':12}{'ladders':>8}{'mk/lad':>7}{'cost$':>9}{'worst$':>9}{'best$':>9}{'worst/cost':>11}{'locked%':>8}{'naked%':>7} | resolved: {'n':>4}{'cost':>8}{'real':>8}{'pnl':>8}{'pnl%':>7}{'t(lad)':>7}{'win%':>5}{'top3 share':>11}")
    by = collections.defaultdict(list)
    for r in rows: by[r["key"][1]].append(r)
    by["ALL"] = rows
    for ty, rs in sorted(by.items(), key=lambda kv: -sum(r["cost"] for r in kv[1])):
        cost = sum(r["cost"] for r in rs); worst = sum(r["worst"] for r in rs); best = sum(r["best"] for r in rs)
        locked = sum(r["cost"] for r in rs if r["worst"] >= r["cost"] - 0.01 and r["cost"] > 0) / cost if cost else 0
        naked = sum(r["cost"] for r in rs if r["worst"] <= 0.05 * r["cost"]) / cost if cost else 0
        rr = [r for r in rs if r["real"] is not None]; pn = [r["real"] - r["cost"] for r in rr]; rc = sum(r["cost"] for r in rr)
        t = stats.mean_se(pn)[2] if len(pn) > 2 else float("nan"); top3 = sum(sorted(pn, reverse=True)[:3]) / sum(pn) if pn and sum(pn) else float("nan")
        print(f"{ty:12}{len(rs):8}{statistics.mean(r['n'] for r in rs):7.1f}{cost:9.0f}{worst:9.0f}{best:9.0f}{worst / cost if cost else 0:11.2f}{locked:8.0%}{naked:7.0%} | {'':10}{len(rr):4}{rc:8.0f}{sum(r['real'] for r in rr):8.0f}{sum(pn):8.0f}{(sum(pn) / rc if rc else 0):7.1%}{t:7.1f}{(sum(1 for x in pn if x > 0) / len(pn) if pn else 0):5.0%}{top3:11.0%}")
    return rows

if __name__ == "__main__":
    for n in sys.argv[1:]: run(n)
