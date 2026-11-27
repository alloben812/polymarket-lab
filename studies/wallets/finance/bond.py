"""High-price ('bond') buyers: what do they buy at >= 0.90, was the outcome already decided, how long is the money tied up,
and how often does it lose?  21-day window; per-market accounting, fee in."""
import sys, json, collections, math, statistics, datetime as dt
import fin, yh, ladder, model
from pmlab import fees, stats
def run(name):
    d = fin.load(name); meta = d["meta"]; res = d["res"]
    mrows = {(r["cond"], r["t"], r["px"], r["sz"]): r for r in model.rows_for(name)}
    M = collections.defaultdict(lambda: dict(usd=0.0, sh=0.0, cash=0.0, n=0, t=[], fair=[], dec=0.0, mk=0.0, z=[]))
    ft = collections.Counter()
    for f in d["fills"]:
        px, sz, t = float(f["price"]), float(f["size"]), int(f["timestamp"]); m = meta.get(f["condition_id"]) or {}
        ft[m.get("feeType")] += px * sz
        if f["side"] != "BUY" or px < 0.90: continue
        fam = "finance" if "finance" in str(m.get("feeType")) or fin.mtype(f["title"])[0] else None
        if not fam: continue
        ty = fin.mtype(f["title"], f["slug"])[0] or "fin-other(news/ipo/ceo)"
        rate = (m.get("feeSchedule") or {}).get("rate") or 0.05
        fee = fees.taker_fee(sz, px, rate if t >= 1795219140 else 0.04) if f["role"] == "T" else 0
        k = (f["condition_id"], f["outcome"], ty); r = M[k]; r["usd"] += px * sz; r["sh"] += sz; r["cash"] -= px * sz + fee; r["n"] += 1; r["t"].append(t); r["mk"] += px * sz if f["role"] == "M" else 0; r["title"] = f["title"]
        mr = mrows.get((f["condition_id"], t - 3, px, sz))
        if mr and mr["age"] is not None and mr["age"] <= 900:
            r["fair"].append((mr["fair"], px * sz)); r["dec"] += px * sz if mr["decided"] else 0
    print(f"\n######## {name}: turnover by gamma feeType: { {k: round(v) for k, v in ft.most_common(8)} }")
    print(f"{'type':26}{'mkts':>5}{'usd':>9}{'px':>7}{'mk%':>5} | {'res':>4}{'lost':>5}{'net$':>8}{'net%':>7}{'t':>6} | {'hrs to close med':>16}{'p90':>6}{'ann%':>7} | model: usd covered, fair>=.99, decided(touched/after close), fair<.95")
    T = collections.defaultdict(list)
    for k, r in M.items(): T[k[2]].append((k, r))
    losers = []
    for ty, items in sorted(T.items(), key=lambda kv: -sum(r["usd"] for _, r in kv[1])):
        usd = sum(r["usd"] for _, r in items); sh = sum(r["sh"] for _, r in items); pn = []; hrs = []; den = []; nl = 0
        cov = f99 = dec = f95 = 0.0
        for (c, o, _), r in items:
            rs = res.get(c) or {}; m = meta.get(c) or {}
            for fv, u in r["fair"]:
                cov += u; f99 += u if fv >= 0.99 else 0; f95 += u if fv < 0.95 else 0
            dec += r["dec"]
            end = fin.ts(m.get("closedTime")) or fin.ts(m.get("endDate"))
            if end: hrs.append(max(0.0, (end - statistics.mean(r["t"])) / 3600))
            if rs.get("resolved") and (rs.get("final") or {}).get(o) is not None:
                g = r["cash"] + r["sh"] * rs["final"][o]; pn.append(g); den.append(r["usd"])
                if g < -0.5: nl += 1; losers.append((g, r["title"], o, r["usd"] / r["sh"], r["usd"]))
        net = sum(pn); t = stats.mean_se(pn)[2] if len(pn) > 2 else float("nan"); hm = statistics.median(hrs) if hrs else float("nan")
        ann = (net / sum(den)) / (max(statistics.mean(hrs), 1) / 8760) if den and hrs else float("nan")
        print(f"{ty:26}{len(items):5}{usd:9.0f}{usd / sh:7.4f}{sum(r['mk'] for _, r in items) / usd:5.0%} | {len(pn):4}{nl:5}{net:8.0f}{(net / sum(den) if den else 0):7.2%}{t:6.1f} | {hm:16.1f}{(sorted(hrs)[int(.9 * len(hrs))] if hrs else 0):6.0f}{ann:7.0%} | {cov:8.0f} {f99 / cov if cov else 0:5.0%} {dec / cov if cov else 0:5.0%} {f95 / cov if cov else 0:5.0%}")
    print("  losing markets:", [(round(g), t[:70], o, round(p, 3), round(u)) for g, t, o, p, u in sorted(losers)[:8]])
if __name__ == "__main__":
    for n in sys.argv[1:]: run(n)
