"""Tables for results.md (markdown on stdout). Statistical unit = release second (cluster)."""
import json, collections, statistics as st, calendar, time
from pmlab import stats
import lib

M = json.load(open(f"{lib.D}/measures.json"))
SPLIT = calendar.timegm(time.strptime("2026-10-15", "%Y-%m-%d"))
TYPES = ["Employment", "CPI", "PPI", "PCE", "GDP", "FOMC", "JOLTS", "ISM", "UMich", "Central bank (non-US)", "Inflation (non-US)", "GDP (non-US)"]
SIZES = [(5e3, 2e4, "5K-20K"), (2e4, 1e5, "20K-100K"), (1e5, 1e6, "100K-1M"), (1e6, 1e12, ">1M")]
BN = ["0-5s", "5-30s", "30s-2m", "2-10m", "later"]
DL = ["5", "30", "120", "600"]


def size(m):
    return next(n for lo, hi, n in SIZES if lo <= m["vol"] < hi)


def med(xs):
    xs = [x for x in xs if x is not None]
    return st.median(xs) if xs else None


def f(x, nd=0):
    return "-" if x is None else (f"{x:,.{nd}f}")


def nrel(ms):
    return len({m["T"] for m in ms})


print("## Entry\n")
print(f"markets measured: {len(M)}; Polymarket-release ids: {len({m['release'] for m in M})}; release seconds (clusters): {nrel(M)}; "
      f"early part {nrel([m for m in M if m['T'] < SPLIT])} clusters / {sum(m['T'] < SPLIT for m in M)} markets, reporting part {nrel([m for m in M if m['T'] >= SPLIT])} clusters / {sum(m['T'] >= SPLIT for m in M)} markets")
print(f"flagged (judgement / late) markets: {sum(bool(m['flag']) for m in M)}; markets with no print after T: {sum(m['n_post'] == 0 for m in M)}; with no print before T: {sum(m['e1'] is None for m in M)}\n")

print("## E1 — winner's last traded price before the release\n")
print("| type | releases | markets | median E1 | E1 < 0.50 | 0.50-0.90 | >= 0.90 | median age of that print, s |\n|---|---|---|---|---|---|---|---|")
for grp in TYPES + ["ALL"]:
    ms = [m for m in M if grp == "ALL" or m["type"] == grp]
    e = [m["e1"] for m in ms if m["e1"] is not None]
    if not ms: continue
    print(f"| {grp} | {nrel(ms)} | {len(ms)} | {f(med(e), 3)} | {sum(x < 0.5 for x in e)} | {sum(0.5 <= x < 0.9 for x in e)} | {sum(x >= 0.9 for x in e)} | {f(med([m['e1_age'] for m in ms]))} |")

print("\n## E2 — seconds from the release to the first print of the winner at >= 0.90 / 0.95 / 0.99\n")
print("Markets that were still uncertain (E1 < 0.90). 'never' = no such print before the tape ended.\n")
hdr = "| group | releases | markets | med to 0.90 | med to 0.95 | med to 0.99 | p75 to 0.95 | reached 0.95 within 5 s / 30 s / 2 min | never 0.95 | never 0.99 |\n|---|---|---|---|---|---|---|---|---|---|"


def e2row(name, ms):
    ms = [m for m in ms if m["e1"] is not None and m["e1"] < 0.90]
    if not ms:
        return
    t95 = [m["e2"]["0.95"] for m in ms]
    ok = sorted(x for x in t95 if x is not None)
    p75 = ok[int(0.75 * (len(ok) - 1))] if ok else None
    print(f"| {name} | {nrel(ms)} | {len(ms)} | {f(med([m['e2']['0.9'] for m in ms]))} | {f(med(t95))} | {f(med([m['e2']['0.99'] for m in ms]))} | {f(p75)} | "
          f"{sum(x <= 5 for x in ok)} / {sum(x <= 30 for x in ok)} / {sum(x <= 120 for x in ok)} | {sum(x is None for x in t95)} | {sum(m['e2']['0.99'] is None for m in ms)} |")


print(hdr)
for grp in TYPES:
    e2row(grp, [m for m in M if m["type"] == grp])
for lo, hi, n in SIZES:
    e2row("size " + n, [m for m in M if lo <= m["vol"] < hi])
e2row("ALL", M)
# per release: median over its uncertain markets, then median over releases
per = collections.defaultdict(list)
for m in M:
    if m["e1"] is not None and m["e1"] < 0.90 and m["e2"]["0.95"] is not None:
        per[m["T"]].append(m["e2"]["0.95"])
pr = sorted(st.median(v) for v in per.values())
print(f"\nPer release (median over its uncertain markets that reached 0.95): {len(pr)} releases, median {st.median(pr):.0f} s, "
      f"quartiles {pr[len(pr)//4]:.0f} / {pr[3*len(pr)//4]:.0f} s, max {pr[-1]:.0f} s; releases with median <= 5 s: {sum(x <= 5 for x in pr)}, <= 30 s: {sum(x <= 30 for x in pr)}")

print("\n## E3 — dollars traded after the release at prices more than 5 cents short of the outcome\n")
print("(a) taker bought the winner below 0.95 or sold the loser above 0.05. Cells: dollars that changed hands / gap dollars (shares x (1 - winner price)).\n")
print("| group | releases | markets | " + " | ".join(BN) + " | total (a) | (b) wrong-side takers, total |\n|---|---|---|" + "---|" * (len(BN) + 2))


def e3row(name, ms):
    if not ms: return
    cells = []
    for b in BN:
        cells.append(f"{sum(m['e3']['a'][b][0] for m in ms):,.0f} / {sum(m['e3']['a'][b][1] for m in ms):,.0f}")
    ta = (sum(m['e3']['a'][b][0] for m in ms for b in BN), sum(m['e3']['a'][b][1] for m in ms for b in BN))
    tb = (sum(m['e3']['b'][b][0] for m in ms for b in BN), sum(m['e3']['b'][b][1] for m in ms for b in BN))
    print(f"| {name} | {nrel(ms)} | {len(ms)} | " + " | ".join(cells) + f" | {ta[0]:,.0f} / {ta[1]:,.0f} | {tb[0]:,.0f} / {tb[1]:,.0f} |")


for grp in TYPES:
    e3row(grp, [m for m in M if m["type"] == grp])
for lo, hi, n in SIZES:
    e3row("size " + n, [m for m in M if lo <= m["vol"] < hi])
e3row("ALL", M)
e3row("early part", [m for m in M if m["T"] < SPLIT]); e3row("reporting part", [m for m in M if m["T"] >= SPLIT])
tb = {b: (sum(m['e3']['b'][b][0] for m in M), sum(m['e3']['b'][b][1] for m in M)) for b in BN}
print("\n(b) by time bucket, all markets: " + "; ".join(f"{b}: {v[0]:,.0f} / {v[1]:,.0f}" for b, v in tb.items()))
W = collections.defaultdict(float); perrel = collections.defaultdict(lambda: collections.defaultdict(float))
for m in M:
    for w, g in m["e3_wallets"].items():
        W[w] += g; perrel[m["T"]][w] += g
tot = sum(W.values()); top = sorted(W.items(), key=lambda kv: -kv[1])
print(f"\nWallets on side (a): {len(W)} distinct takers over the study; gap dollars {tot:,.0f}; top three take {sum(v for _, v in top[:3]) / tot:.1%}, top ten {sum(v for _, v in top[:10]) / tot:.1%}.")
print("Top ten (gap dollars, number of releases they appear in): " + "; ".join(f"{w[:8]} {v:,.0f} ({sum(1 for t in perrel if w in perrel[t])})" for w, v in top[:10]))
sh = []; cnt = []
for t, d in perrel.items():
    s = sum(d.values())
    if s > 0:
        sh.append(sum(sorted(d.values(), reverse=True)[:3]) / s); cnt.append(len(d))
print(f"Per release with any (a) trade ({len(sh)} releases): median number of taker wallets {st.median(cnt):.0f}, median top-three share {st.median(sh):.0%}.")
# first-5-seconds wallets
print("\n## E4 — taker starting at release + d, winner bought at every later print <= 0.97, max $500 per market, fee 0.01\n")


def e4stats(ms, d):
    cl = collections.defaultdict(lambda: [0.0, 0.0]); mk_net = []; mk_cost = []
    for m in ms:
        x = m["e4"][d]; cl[m["T"]][0] += x["net"]; cl[m["T"]][1] += x["cost"]; mk_net.append(x["net"]); mk_cost.append(x["cost"])
    net = [v[0] for v in cl.values()]; cost = [v[1] for v in cl.values()]
    sh = sum(m["e4"][d]["shares"] for m in ms); c = sum(cost)
    r, se, t = stats.ratio_cluster(net, cost); mu, mse, mt = stats.mean_se(net)
    rm, sem, tm = stats.ratio_cluster(mk_net, mk_cost)
    return {"rel": len(cl), "rel_f": sum(1 for v in cl.values() if v[1] > 0), "mk": len(ms), "mk_f": sum(1 for m in ms if m["e4"][d]["n"]), "cost": c, "shares": sh,
            "avg": c / sh if sh else None, "fee": sum(m["e4"][d]["fee"] for m in ms), "net": sum(net), "roi": r, "t_roi": t, "mean": mu, "se": mse, "t_mean": mt, "t_mk": tm,
            "pos": sum(1 for x in net if x > 0), "neg": sum(1 for x in net if x < 0)}


H = "| set | d | releases (with fills) | markets (with fills) | cost $ | shares | avg price | fees $ | net $ | net / cost | t (by release) | mean net per release $ (se) | t | t if clustered by market |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"


def e4row(name, ms, d):
    if not ms: return
    s = e4stats(ms, d)
    print(f"| {name} | {d} s | {s['rel']} ({s['rel_f']}) | {s['mk']} ({s['mk_f']}) | {s['cost']:,.0f} | {s['shares']:,.0f} | {f(s['avg'], 3)} | {s['fee']:,.2f} | {s['net']:,.0f} | "
          f"{f(s['roi'] * 100 if s['roi'] == s['roi'] else None, 1)}% | {f(s['t_roi'] if s['t_roi'] == s['t_roi'] else None, 2)} | {s['mean']:,.1f} ({f(s['se'], 1)}) | {f(s['t_mean'] if s['t_mean'] == s['t_mean'] else None, 2)} | {f(s['t_mk'] if s['t_mk'] == s['t_mk'] else None, 2)} |")


print(H)
for d in DL:
    e4row("ALL", M, d)
for d in DL:
    e4row("early part (before 2026-10-15)", [m for m in M if m["T"] < SPLIT], d)
for d in DL:
    e4row("REPORTING part (from 2026-10-15)", [m for m in M if m["T"] >= SPLIT], d)
for d in DL:
    e4row("mechanical mapping only (unflagged)", [m for m in M if not m["flag"]], d)
for d in DL:
    e4row("flagged (judgement / late)", [m for m in M if m["flag"]], d)
print("\nBy release type:\n"); print(H)
for grp in TYPES:
    for d in ("5", "30"):
        e4row(grp, [m for m in M if m["type"] == grp], d)
print("\nBy market size:\n"); print(H)
for lo, hi, n in SIZES:
    for d in ("5", "30"):
        e4row("size " + n, [m for m in M if lo <= m["vol"] < hi], d)
print("\nUS official calendar (tier A) vs the rest:\n"); print(H)
for d in ("5", "30"):
    e4row("tier A (BLS, BEA, Fed)", [m for m in M if m["tier"] == "A"], d)
    e4row("tier B (others)", [m for m in M if m["tier"] == "B"], d)
print("\nDollars per calendar day (ALL: 87 days; reporting part: 43 days):")
for d in DL:
    a = sum(m["e4"][d]["net"] for m in M); b = sum(m["e4"][d]["net"] for m in M if m["T"] >= SPLIT)
    print(f"- d = {d} s: {a / 87:.2f} $/day over the whole period, {b / 43:.2f} $/day in the reporting part")
print("\nWhere the d = 5 s and d = 30 s profit sits (per release, top ten by net):")
for d in ("5", "30"):
    cl = collections.defaultdict(lambda: [0.0, 0.0, set(), 10**9, 0])
    for m in M:
        x = m["e4"][d]; c = cl[(m["T"], m["when"])]; c[0] += x["net"]; c[1] += x["cost"]; c[2].add(m["release"])
        if x["n"]: c[3] = min(c[3], x["first"]); c[4] = max(c[4], x["last"])
    top = sorted(cl.items(), key=lambda kv: -kv[1][0]); tot = sum(v[0] for v in cl.values())
    print(f"\nd = {d} s, total {tot:,.0f}; top three releases = {sum(v[0] for _, v in top[:3]) / tot:.0%} of it")
    for (T, when), v in [kv for kv in top if kv[1][1] > 0][:10]:
        print(f"- {when} {'+'.join(sorted(v[2]))}: net {v[0]:,.0f} on cost {v[1]:,.0f}, fills from +{v[3]} s to +{v[4]} s")
print("\nE4 fills by the offset of the fill (all markets), share of net profit:")
# recompute per-fill buckets for d = 5
import math
for d in (5, 30):
    bk = collections.Counter(); bc = collections.Counter()
    for m0 in lib.markets():
        mm = next((x for x in M if x["cond"] == m0["cond"]), None)
        if mm is None: continue
        rows, _ = lib.tape(m0); budget = 500.0
        for r in rows:
            if r["off"] < d or not r["buyable"] or r["wp"] > 0.97 + 1e-9: continue
            q = min(r["z"], budget / r["wp"])
            if q <= 1e-9: break
            budget -= q * r["wp"]
            b = "<10s" if r["off"] < 10 else "10-30s" if r["off"] < 30 else "30s-2m" if r["off"] < 120 else "2-10m" if r["off"] < 600 else "10m-1h" if r["off"] < 3600 else ">1h"
            bk[b] += q * (1 - r["wp"]) - lib.FEE * r["wp"] * (1 - r["wp"]) * q; bc[b] += q * r["wp"]
    print(f"- d = {d} s: " + "; ".join(f"{b}: net {bk[b]:,.0f} on cost {bc[b]:,.0f}" for b in ("<10s", "10-30s", "30s-2m", "2-10m", "10m-1h", ">1h")))
