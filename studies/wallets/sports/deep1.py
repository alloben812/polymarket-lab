"""Per-account profile by sport, market type and time relative to the game start (gamma gameStartTime)."""
import sys, collections, statistics as st, json
import lib
from pmlab import stats

DAYS = {"forecastication4": 14, "soforth": 14, "0x9f15613e": 14, "0x66e7ce01": 10, "0xd9e0aaca": 4, "dashattacker": 14, "0x99f0d31f": 14}

def sport(slug):
    return (slug or "?").split("-")[0]

def tb(dt_):
    if dt_ is None: return "?"
    if dt_ < -86400: return "a >24h before start"
    if dt_ < -3600: return "b 1-24h before"
    if dt_ < -300: return "c 5-60m before"
    if dt_ < 0: return "d 0-5m before"
    if dt_ < 3600: return "e 0-1h after start"
    if dt_ < 3 * 3600: return "f 1-3h after start"
    return "g >3h after start"

def run(name):
    F = lib.fills(name, DAYS[name])
    M = lib.meta([r["condition_id"] for r in F])
    R = lib.resol([r["condition_id"] for r in F])
    print(f"\n===== {name}: {len(F)} fills, {len(set(r['condition_id'] for r in F))} markets, {len(set(r['event_slug'] for r in F))} events")
    def final(r):
        rv = R.get(r["condition_id"])
        if not rv or not rv.get("resolved"): return None
        return float((rv.get("final") or {}).get(r["outcome"]) or 0.0)
    def table(keyfn, title, top=14):
        agg = collections.defaultdict(lambda: {"n": 0, "usd": 0.0, "sh": 0.0, "pnl": 0.0, "mk": set(), "fee": 0.0, "per": collections.defaultdict(lambda: [0.0, 0.0])})
        for r in F:
            m = M.get(r["condition_id"]) or {}
            k = keyfn(r, m); a = agg[k]
            a["n"] += 1; a["usd"] += r["size"] * r["price"]; a["mk"].add(r["condition_id"])
            fp = final(r)
            if fp is None: continue
            sgn = 1 if r["side"] == "BUY" else -1
            fee = r["size"] * 0.05 * r["price"] * (1 - r["price"]) if r["role"] == "T" else 0.0
            pnl = sgn * r["size"] * (fp - r["price"]) - fee
            a["sh"] += r["size"]; a["pnl"] += pnl; a["fee"] += fee
            ev = r["event_slug"]; a["per"][ev][0] += pnl; a["per"][ev][1] += r["size"]
        print(f"-- {title}")
        print(f"   {'key':38s} {'fills':>6s} {'mkts':>5s} {'usd':>10s} {'net$':>9s} {'net c/sh':>8s} {'t(event)':>8s} {'events':>6s}")
        for k, a in sorted(agg.items(), key=lambda kv: -kv[1]["usd"])[:top] if "sport" in title or "type" in title else sorted(agg.items()):
            num = [v[0] for v in a["per"].values()]; den = [v[1] for v in a["per"].values()]
            t = None
            if len(num) > 3 and sum(den) > 0:
                try:
                    e, se = stats.ratio_cluster(num, den)[:2]; t = e / se if se else None
                except Exception: t = None
            print(f"   {str(k):38s} {a['n']:6d} {len(a['mk']):5d} {a['usd']:10.0f} {a['pnl']:9.0f} {100*a['pnl']/a['sh'] if a['sh'] else 0:8.2f} {t if t is None else round(t,2)!s:>8s} {len(a['per']):6d}")
    table(lambda r, m: sport(r["slug"]), "by sport (slug prefix)")
    table(lambda r, m: (m.get("sportsMarketType") or "?"), "by market type")
    def k_time(r, m):
        gs = lib.ts(m.get("gameStartTime") or m.get("eventStartTime"))
        return (r["role"], tb(None if gs is None else r["timestamp"] - gs))
    table(k_time, "by role and time relative to game start")
    table(lambda r, m: (r["role"], r["side"]), "by role, side")
    # sizing / concurrency
    usd = sorted(r["size"] * r["price"] for r in F)
    per_m = collections.defaultdict(float); per_e = collections.defaultdict(float)
    for r in F:
        per_m[r["condition_id"]] += r["size"] * r["price"] * (1 if r["side"] == "BUY" else -1); per_e[r["event_slug"]] += r["size"] * r["price"]
    pm = sorted(abs(v) for v in per_m.values()); pe = sorted(per_e.values())
    q = lambda a, p: a[min(len(a) - 1, int(p * len(a)))]
    print(f"-- fill $: median {q(usd,.5):.0f} p90 {q(usd,.9):.0f} max {usd[-1]:.0f} | net $ per market: median {q(pm,.5):.0f} p90 {q(pm,.9):.0f} max {pm[-1]:.0f} | $ per event: median {q(pe,.5):.0f} p90 {q(pe,.9):.0f} max {pe[-1]:.0f}")
    days = collections.defaultdict(set)
    for r in F: days[r["timestamp"] // 86400].add(r["event_slug"])
    print("-- events traded per day:", sorted(len(v) for v in days.values()))
    sd = collections.Counter((M.get(r["condition_id"]) or {}).get("secondsDelay") for r in F)
    print("-- secondsDelay of fills:", dict(sd))
    json.dump({"n": len(F)}, open(f"{lib.HERE}/out/{name}_deep1.json", "w"))

for n in sys.argv[1:]:
    run(n)
