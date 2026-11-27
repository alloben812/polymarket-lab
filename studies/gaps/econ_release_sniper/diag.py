"""Diagnostics (not variants): stale dollars by block second, earliest prints, who is first, F1-type check on the
primary window, primary by release type and by release (late part). Output: out/diag.json"""
import json, collections
import measure as M  # reuses loaded tapes (measure.py recomputes part1.json; deterministic)

mech = [m for m in M.MK if not m["flag"]]
BLS_BEA = {"Employment", "CPI", "PPI", "PCE", "GDP", "JOLTS"}
out = {}
# stale gap-after-fee dollars by block second 0..20, three groups
hist = {g: collections.defaultdict(float) for g in ("BLS/BEA", "FOMC", "ISM/UMich", "non-US")}
for m in mech:
    g = "BLS/BEA" if m["type"] in BLS_BEA else "FOMC" if m["type"] == "FOMC" else "ISM/UMich" if m["type"] in ("ISM", "UMich") else "non-US"
    for r in M.tapes[m["cond"]]:
        if 0 <= r["b"] <= 20 and r["wb"] and r["wp"] < 0.95:
            hist[g][r["b"]] += r["z"] * (1 - r["wp"]) - M.fee(r["wp"], r["z"])
out["profit_by_block_second"] = {g: {b: round(v[b], 1) for b in range(21)} for g, v in hist.items()}
# earliest stale prints b<=2 (match before ~T+0.9 even with the shortest lag)
early = []
for m in M.MK:
    for r in M.tapes[m["cond"]]:
        if 0 <= r["b"] <= 2 and r["wb"] and r["wp"] < 0.95:
            early.append([m["release"], m["title"][:30], r["b"], round(r["wp"], 3), round(r["z"], 1), r["w"][:10], bool(m["flag"])])
out["stale_prints_b0_2"] = early
# who is first: wallets with stale prints at b 3..5 (mech), profit
wal = collections.defaultdict(lambda: [0.0, set()])
for m in mech:
    for r in M.tapes[m["cond"]]:
        if 3 <= r["b"] <= 5 and r["wb"] and r["wp"] < 0.95:
            wal[r["w"]][0] += r["z"] * (1 - r["wp"]); wal[r["w"]][1].add(m["T"])
out["first_wave_wallets_b3_5"] = sorted([[w[:10], round(v[0], 1), len(v[1])] for w, v in wal.items()], key=lambda x: -x[1])[:12]
# F1 check on the primary window (A1: b 4..6): stale prints priced >= 5c below an EARLIER post-T winner print
tot = below = 0.0
for m in mech:
    rows = [r for r in M.tapes[m["cond"]] if r["b"] >= 0]
    for r in rows:
        if 4 <= r["b"] <= 6 and r["wb"] and r["wp"] <= 0.95:
            usd = r["z"] * (1 - r["wp"])
            tot += usd
            prev = [q["wp"] for q in rows if q["b"] < r["b"]]
            if prev and r["wp"] <= max(prev) - 0.05:
                below += usd
out["primary_window_gap_usd"] = round(tot, 1)
out["primary_window_gap_usd_below_an_earlier_post_T_print_by_5c"] = round(below, 1)
# primary by type and by release, both fill scenarios
by_t = collections.defaultdict(lambda: {"U": 0.0, "S": 0.0, "orders": 0, "releases": set()})
by_r = collections.defaultdict(lambda: {"U": 0.0, "S": 0.0})
for m in mech:
    for sc in ("U", "S"):
        n, c, f = M.sim_market(m, 1, 50, sc)
        by_t[m["type"]][sc] += n; by_r[(m["when"], m["release"])][sc] += n
        if sc == "S" and c > 0:
            by_t[m["type"]]["orders"] += 1
    by_t[m["type"]]["releases"].add(m["T"])
out["primary_by_type"] = {t: {"U": round(v["U"], 1), "S": round(v["S"], 1), "orders_filled": v["orders"], "releases": len(v["releases"])} for t, v in by_t.items()}
out["primary_by_release"] = [[k[0], k[1], round(v["U"], 1), round(v["S"], 1)] for k, v in sorted(by_r.items())]
json.dump(out, open(f"{M.OUT}/diag.json", "w"), indent=0)
print(json.dumps(out, indent=0)[:6000])
