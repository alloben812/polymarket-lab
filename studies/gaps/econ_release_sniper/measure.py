"""Part 1 of protocol.md: pool windows, early-print test, the 12 strategy cells, robustness of the primary.
Input: data/gaps_econ (markets.json, release_status.json, tapes/). Output: out/part1.json, out/part1.txt."""
import gzip, json, collections, random, sys, calendar, time

D = "/home/user/polymarket-lab/data/gaps_econ"
OUT = "/home/user/polymarket-lab/studies/gaps/econ_release_sniper/out"
FEE = 0.01
SPLIT = calendar.timegm(time.strptime("2026-10-15", "%Y-%m-%d"))
US_TYPES = {"Employment", "CPI", "PPI", "PCE", "GDP", "FOMC", "JOLTS", "ISM", "UMich"}

st = json.load(open(f"{D}/release_status.json"))
MK = [m for m in json.load(open(f"{D}/markets.json"))["markets"] if not st[m["release"]].startswith("DROPPED")]


def load(m):
    d = json.load(gzip.open(f"{D}/tapes/{m['cond']}.json.gz"))
    rows = []
    for ts, side, oi, o, p, z, w in d["rows"]:
        if o not in ("Yes", "No"):
            o = "Yes" if oi == 0 else "No"
        is_w = (o == m["winner"])
        wp = p if is_w else 1.0 - p
        wb = (side == "BUY" and is_w) or (side == "SELL" and not is_w)
        rows.append({"b": ts - m["T"], "wp": wp, "z": z, "w": w or "?", "wb": wb})
    rows.sort(key=lambda r: r["b"])
    return rows


def fee(p, q):
    return FEE * p * (1 - p) * q


tapes = {m["cond"]: load(m) for m in MK}
clusters = sorted({m["T"] for m in MK})
print("markets", len(MK), "clusters", len(clusters), file=sys.stderr)

# ---------------- pool windows
WIN = [("first block", None), ("m<=2s (b<=5)", 5), ("m<=5s (b<=8)", 8), ("m<=10s (b<=13)", 13), ("all after T", 10**9)]


def pool(markets):
    res = {}
    by_cluster = collections.defaultdict(list)
    for m in markets:
        by_cluster[m["T"]].append(m)
    for name, bmax in WIN:
        tot_d = tot_p = 0.0
        wal = collections.defaultdict(float)
        per_cl = []
        for T, ms in by_cluster.items():
            stale = [r for m in ms for r in tapes[m["cond"]] if r["b"] >= 0 and r["wb"] and r["wp"] < 0.95 - 1e-9]
            if bmax is None:
                if not stale:
                    per_cl.append(0.0); continue
                b0 = min(r["b"] for r in stale)
                sel = [r for r in stale if r["b"] == b0]
            else:
                sel = [r for r in stale if r["b"] <= bmax]
            dd = sum(r["z"] * r["wp"] for r in sel)
            pp = sum(r["z"] * (1 - r["wp"]) - fee(r["wp"], r["z"]) for r in sel)
            for r in sel:
                wal[r["w"]] += r["z"] * (1 - r["wp"]) - fee(r["wp"], r["z"])
            tot_d += dd; tot_p += pp; per_cl.append(pp)
        top = sorted(wal.values(), reverse=True)
        res[name] = {"stale_usd": tot_d, "profit_after_fee": tot_p, "wallets": len(wal),
                     "top3_share": (sum(top[:3]) / sum(top)) if top and sum(top) > 0 else None,
                     "clusters_with_any": sum(1 for x in per_cl if x > 0)}
    return res


def first_blocks(markets):
    """per cluster: block offset of the first stale print, wallets in it, $ in it"""
    by_cluster = collections.defaultdict(list)
    for m in markets:
        by_cluster[m["T"]].append(m)
    out = []
    for T, ms in sorted(by_cluster.items()):
        stale = [r for m in ms for r in tapes[m["cond"]] if r["b"] >= 0 and r["wb"] and r["wp"] < 0.95 - 1e-9]
        if not stale:
            out.append({"T": T, "rel": ms[0]["release"], "b0": None}); continue
        b0 = min(r["b"] for r in stale)
        sel = [r for r in stale if r["b"] == b0]
        out.append({"T": T, "rel": ms[0]["release"], "b0": b0, "usd": round(sum(r["z"] * r["wp"] for r in sel), 2),
                    "profit": round(sum(r["z"] * (1 - r["wp"]) for r in sel), 2), "wallets": len({r["w"] for r in sel})})
    return out


def early_test(markets):
    """winner-buyable vs loser-buyable dollars (cost in the bought token) by block offset band"""
    bands = [("b -60..-1", -60, -1), ("b 0..1", 0, 1), ("b 2", 2, 2), ("b 3..5", 3, 5), ("b 6..13", 6, 13)]
    res = {}
    for name, lo, hi in bands:
        wb = lb = 0.0; nwb = nlb = 0; wal = set()
        for m in markets:
            for r in tapes[m["cond"]]:
                if lo <= r["b"] <= hi:
                    if r["wb"] and r["wp"] < 0.95:
                        wb += r["z"] * r["wp"]; nwb += 1; wal.add(r["w"])
                    elif (not r["wb"]) and r["wp"] > 0.05:
                        lb += r["z"] * (1 - r["wp"]); nlb += 1
        res[name] = {"winner_buy_usd": round(wb, 2), "n_w": nwb, "loser_buy_usd": round(lb, 2), "n_l": nlb,
                     "wallets_w": sorted(wal)[:20]}
    return res


# ---------------- strategy cells
def sim_market(m, a, B, scen, lag=3, order="cheap"):
    rows = tapes[m["cond"]]
    lo, hi = a + lag, a + lag + 2
    win = [r for r in rows if lo <= r["b"] <= hi and r["wb"] and r["wp"] <= 0.95 + 1e-9]
    if not win:
        return 0.0, 0.0, 0.0
    k = len({r["w"] for r in win})
    win.sort(key=lambda r: r["wp"], reverse=(order == "dear"))
    budget = B; sh = cost = fe = 0.0
    for r in win:
        avail = r["z"] if scen == "U" else r["z"] / (k + 1)
        q = min(avail, budget / r["wp"])
        if q <= 1e-12:
            break
        sh += q; cost += q * r["wp"]; fe += fee(r["wp"], q); budget -= q * r["wp"]
    return sh - cost - fe, cost, fe


def run_cell(markets, a, B, scen, **kw):
    per = collections.defaultdict(float); cost = 0.0; nm = 0; permk = {}
    for m in markets:
        n, c, f = sim_market(m, a, B, scen, **kw)
        per[m["T"]] += n; cost += c; nm += (c > 0); permk[m["cond"]] = n
    return per, cost, nm, permk


def summarize(per_cluster_dict, cl_list, days):
    v = [per_cluster_dict.get(T, 0.0) for T in cl_list]
    n = len(v); tot = sum(v); mean = tot / n if n else 0
    se = (sum((x - mean) ** 2 for x in v) / (n - 1) / n) ** 0.5 if n > 1 else 0
    rnd = random.Random(1)
    bs = sorted(sum(v[rnd.randrange(n)] for _ in range(n)) for _ in range(10000)) if n else [0]
    return {"clusters": n, "with_fills": sum(1 for x in v if x > 1e-9), "total": tot, "mean": mean, "se": se,
            "t": mean / se if se > 0 else None, "ci95_total": (bs[250], bs[9750]),
            "per_month": tot / days * 30.4, "ci95_month": (bs[250] / days * 30.4, bs[9750] / days * 30.4)}


mech = [m for m in MK if not m["flag"]]
early_cl = [T for T in clusters if T < SPLIT]; late_cl = [T for T in clusters if T >= SPLIT]
D_ALL, D_EARLY, D_LATE = 87.0, 44.0, 43.0  # calendar days 2026-09-01..11-26 as in econ_release_lag (early 09-01..10-14)
us_cl = sorted({m["T"] for m in mech if m["type"] in US_TYPES})

R = {"n_markets": len(MK), "n_mech": len(mech), "clusters": len(clusters), "early": len(early_cl), "late": len(late_cl)}
R["pool_all"] = pool(MK); R["pool_mech"] = pool(mech)
R["pool_mech_late"] = pool([m for m in mech if m["T"] >= SPLIT])
R["pool_mech_us"] = pool([m for m in mech if m["type"] in US_TYPES])
R["first_blocks"] = first_blocks(MK)
R["early_test_all"] = early_test(MK)
R["early_test_mech"] = early_test(mech)

cells = []
for a in (1, 3):
    for B in (20, 50, 200):
        for scen in ("U", "S"):
            per, cost, nm, permk = run_cell(mech, a, B, scen)
            c = {"a": a, "B": B, "scen": scen, "markets_with_fill": nm, "cost": cost,
                 "all": summarize(per, clusters, D_ALL), "early": summarize(per, early_cl, D_EARLY),
                 "late": summarize(per, late_cl, D_LATE), "us_only_all": summarize(per, us_cl, D_ALL)}
            c["n_orders_filled_late"] = sum(1 for m in mech if m["T"] >= SPLIT and permk[m["cond"]] != 0)
            c["net_per_filled_order"] = (c["all"]["total"] / nm) if nm else None
            cells.append(c)
R["cells"] = cells

# robustness of the primary (A1, B=50, S) -- protocol section 8
rob = {}
per, cost, nm, permk = run_cell(mech, 1, 50, "S")
late_vals = {T: per.get(T, 0.0) for T in late_cl}
best = max(late_vals, key=late_vals.get)
rob["late_without_best_cluster"] = summarize({T: v for T, v in late_vals.items() if T != best}, [T for T in late_cl if T != best], D_LATE)
top10 = set(sorted(permk, key=permk.get, reverse=True)[:10])
per2 = collections.defaultdict(float)
for m in mech:
    if m["cond"] not in top10:
        per2[m["T"]] += permk[m["cond"]]
rob["all_without_top10_markets"] = summarize(per2, clusters, D_ALL)
for lag in (2, 4):
    p_, *_ = run_cell(mech, 1, 50, "S", lag=lag)
    rob[f"lag{lag}_late"] = summarize(p_, late_cl, D_LATE)
p_, *_ = run_cell(mech, 1, 50, "S", order="dear")
rob["dearest_first_late"] = summarize(p_, late_cl, D_LATE)
rob["best_late_cluster"] = [next(m["release"] for m in mech if m["T"] == best), late_vals[best]]
R["robust_primary"] = rob

# where the primary money sits
top = sorted(((v, c) for c, v in permk.items() if v), reverse=True)[:12]
cm = {m["cond"]: m for m in mech}
R["primary_top_markets"] = [[cm[c]["release"], cm[c]["title"][:40], round(v, 2)] for v, c in top]
json.dump(R, open(f"{OUT}/part1.json", "w"), indent=1, default=str)
print("ok")
