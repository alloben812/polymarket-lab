"""Markouts, lead/lag and market stories for one account on a sample of 20 of its markets (top 8 by turnover +
12 random with seed 7 among resolved markets with >= $200 turnover). Whole-market tapes from the data API.
Variant count: one definition of markout (last tape print at t+h, outcome-0 terms), horizons 10/60/300 s + final."""
import sys, json, random, collections, statistics as st
import lib
from pmlab import stats

name = sys.argv[1]; NS = int(sys.argv[2]) if len(sys.argv) > 2 else 20
F = lib.fills(name); M = lib.meta({f["condition_id"] for f in F}); R = lib.resol({f["condition_id"] for f in F})
W = lib.WALLETS[name].lower()
J = json.load(open(f"{lib.HERE}/{name}.json")); PM = {m["condition"]: m for m in J["_markets"]}
usd = lambda f: f["size"] * f["price"]
out = open(f"{lib.HERE}/out/a2_{name}.txt", "w")
def P(*a):
    s = " ".join(str(x) for x in a); print(s); out.write(s + "\n")

# ---- concentration of the window PnL
nets = sorted((m["net"] for m in PM.values() if m.get("resolved") and not m.get("incomplete") and m["turnover"] > 0), reverse=True)
tot = sum(nets); pos = sum(x for x in nets if x > 0)
ev = collections.defaultdict(float)
for m in PM.values():
    if m.get("resolved") and m["turnover"] > 0: ev["-".join(m["slug"].split("-")[:5] if m["slug"].split("-")[-1].startswith("game") else m["slug"].split("-"))[:40]] += m["net"]
evs = sorted(ev.values(), reverse=True)
P(f"## {name}: window net {tot:,.0f} over {len(nets)} markets / {len(evs)} matches; top5 markets {sum(nets[:5]):,.0f}, bottom5 {sum(nets[-5:]):,.0f}; win markets {sum(1 for x in nets if x>0)}/{len(nets)}; "
  f"net without best 5 matches {tot - sum(evs[:5]):,.0f}; match-level t {stats.mean_se(evs)[2] if len(evs)>2 else None}")

# ---- concurrency: distinct matches with fills per active hour
hr = collections.defaultdict(set)
for f in F: hr[f["timestamp"] // 3600].add(f["event_slug"])
v = sorted(len(s) for s in hr.values()); P(f"matches worked per active hour: median {st.median(v)}, p90 {v[int(len(v)*.9)]}, max {v[-1]}; active hours {len(v)} of 336")

# ---- sample
byc = collections.defaultdict(list)
for f in F: byc[f["condition_id"]].append(f)
elig = [c for c, fs in byc.items() if (R.get(c) or {}).get("resolved") and sum(usd(f) for f in fs) >= 200 and len(lib.gamma.jfield((M.get(c) or {}).get("clobTokenIds")) or []) == 2
        and (M.get(c) or {}).get("slug", "").split("-")[0] in ("dota2", "cs2", "lol", "val")]
elig.sort(key=lambda c: -sum(usd(f) for f in byc[c]))
random.seed(7); sample = elig[:8] + random.sample(elig[8:], min(NS - 8, max(0, len(elig) - 8)))
P(f"eligible esports markets {len(elig)}, sampled {len(sample)}")

H = (10, 60, 300)
acc = collections.defaultdict(lambda: collections.defaultdict(lambda: [0.0, 0.0]))   # key -> market -> [num, den]
def add(key, c, mo, sh): a = acc[key][c]; a[0] += mo * sh; a[1] += sh
stories = []
for c in sample:
    m = M[c]; toks = lib.gamma.jfield(m["clobTokenIds"]); outs = lib.gamma.jfield(m["outcomes"]); tok0 = toks[0]
    T = lib.tape(c); path = lib.Path(T, tok0)
    fin0 = float(R[c]["final"].get(outs[0]) or 0)
    gs = lib.ts(m.get("gameStartTime")); ct = lib.ts(m.get("closedTime"))
    # "decided" proxy: first print of the winner at >= 0.99 that is never followed by a print below 0.95
    win_p = [(t, p if fin0 == 1 else 1 - p) for t, p in zip(path.t, path.p)]
    t99 = None
    for i in range(len(win_p) - 1, -1, -1):
        if win_p[i][1] < 0.95: break
        if win_p[i][1] >= 0.99: t99 = win_p[i][0]
    def dirp(r):
        is0 = r["token_id"] == tok0; buy = r["side"] == "BUY"
        return (1 if is0 == buy else -1), (r["price"] if is0 else 1 - r["price"])
    def marks(r, key):
        d, p0 = dirp(r); t = r["timestamp"]
        for h in H:
            q = path.at(t + h)
            if q is not None: add((key, f"mo{h}"), c, d * (q - p0) * 100, r["size"])
        q = path.at(t - 30)
        if q is not None: add((key, "pre30"), c, d * (p0 - q) * 100, r["size"])
        add((key, "final"), c, d * (fin0 - p0) * 100, r["size"])
    mine = byc[c]
    for r in mine: marks(r, "acct_" + r["role"])
    for r in T:
        if (r.get("proxy_wallet") or "").lower() != W: marks(r, "other_takers")
    # lead/lag for the account's taker fills: other takers' same-direction $ in the 10 s before vs after
    for r in mine:
        if r["role"] != "T": continue
        d, p0 = dirp(r); t = r["timestamp"]; b = a = 0.0
        for x in T:
            if abs(x["timestamp"] - t) > 12 or (x.get("proxy_wallet") or "").lower() == W: continue
            dx, _ = dirp(x)
            if dx != d: continue
            if t - 12 <= x["timestamp"] < t - 1: b += x["size"] * x["price"]
            elif t + 1 < x["timestamp"] <= t + 12: a += x["size"] * x["price"]
        add(("lead", "same_dir_usd_before"), c, b, 1); add(("lead", "same_dir_usd_after"), c, a, 1)
    # story line
    b = collections.defaultdict(lambda: [0.0, 0.0]); s = collections.defaultdict(lambda: [0.0, 0.0])
    for r in mine:
        (b if r["side"] == "BUY" else s)[r["outcome"]][0] += r["size"]; (b if r["side"] == "BUY" else s)[r["outcome"]][1] += usd(r)
    after = sum(usd(r) for r in mine if t99 and r["timestamp"] >= t99); hi = sum(usd(r) for r in mine if r["price"] >= 0.95 and r["side"] == "BUY")
    pm = PM.get(c, {})
    stories.append(dict(slug=m["slug"], type=lib.mtype(m), start=lib.iso(gs), first=round((mine[0]["timestamp"] - gs) / 60) if gs else None, last=round((mine[-1]["timestamp"] - gs) / 60) if gs else None,
        t99=round((t99 - gs) / 60) if (t99 and gs) else None, closed=round((ct - gs) / 60) if (ct and gs) else None, n=len(mine), tape=len(T),
        buys={k: f"{v[0]:,.0f}@{v[1]/v[0]:.3f}" for k, v in b.items()}, sells={k: f"{v[0]:,.0f}@{v[1]/v[0]:.3f}" for k, v in s.items()},
        merge=round(pm.get("merge_usd", 0)), winner=outs[0] if fin0 == 1 else outs[1], usd_after_t99=round(after), buy_usd_ge95=round(hi), net=round(pm.get("net", 0)), vol=round(float(m.get("volumeNum") or 0))))
P("markouts, cents per share, share-weighted, clustered by market (ratio, se, t), n markets:")
for key in sorted(acc):
    d = acc[key]; num = [v[0] for v in d.values()]; den = [v[1] for v in d.values()]
    if len(num) < 3: continue
    r, se, t = stats.ratio_cluster(num, den)
    P(f"  {key[0]:13s} {key[1]:20s} {r:8.2f}  se {se:6.2f}  t {t:6.2f}  n {len(num)}  shares {sum(den):,.0f}")
P("stories (minutes are relative to gamma gameStartTime; t99 = first print of the winner >= 0.99 that held):")
for s_ in stories: P("  " + json.dumps(s_))
