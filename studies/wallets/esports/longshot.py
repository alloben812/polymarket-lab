"""Whole-market tapes already cached (sampled markets of the seven accounts + all mapped Dota game markets):
what did the MAKER side of every taker fill earn, by the price the maker paid? (maker buys X at q when a taker sells
X at q or buys the other outcome at 1-q). Clustered by match (event). No fees for makers; taker fee shown for the
mirror trade. Not a random sample of esports markets: say so wherever this is quoted."""
import glob, gzip, json, collections, os, lib
from pmlab import stats
conds = {}
for n in lib.WALLETS:
    F = lib.fills(n)
    for f in F: conds[f["condition_id"]] = f["event_slug"]
M = lib.meta(list(conds)); R = lib.resol(list(conds))
B = [(0.0, 0.03), (0.03, 0.08), (0.08, 0.15), (0.15, 0.30), (0.30, 0.50), (0.50, 0.70), (0.70, 0.85), (0.85, 0.92), (0.92, 0.97), (0.97, 0.99), (0.99, 1.001)]
acc = collections.defaultdict(lambda: collections.defaultdict(lambda: [0.0, 0.0])); nm = collections.Counter(); sd = collections.Counter()
half = {}
for c, ev in conds.items():
    p = f"{lib.HERE}/fills/tape_{c[:14]}.json.gz"
    if not os.path.exists(p): continue
    m = M.get(c) or {}; r = R.get(c) or {}
    if not r.get("resolved"): continue
    game = (m.get("slug") or "").split("-")[0]; outs = lib.gamma.jfield(m.get("outcomes")) or []; toks = lib.gamma.jfield(m.get("clobTokenIds")) or []
    if len(outs) != 2 or game not in ("dota2", "cs2", "lol"): continue
    fin = {toks[i]: float(r["final"].get(outs[i]) or 0) for i in range(2)}; other = {toks[0]: toks[1], toks[1]: toks[0]}
    T = lib.tape(c); nm[game] += 1; sd[(game, m.get("secondsDelay"))] += 1
    gs = lib.ts(m.get("gameStartTime")) or 0; wk = "wk1" if gs < lib.END - 7 * 86400 else "wk2"
    for x in T:
        if x["side"] == "BUY": mt, q = other[x["token_id"]], 1 - x["price"]      # maker ends up long the other outcome at 1-p
        else: mt, q = x["token_id"], x["price"]
        b = next(f"{lo:.2f}-{min(hi,1):.2f}" for lo, hi in B if lo <= q < hi)
        for key in ((game, b), ("all", b), (game, "ALL"), ("all", "ALL"), ("all_" + wk, b), ("all_" + wk, "ALL")):
            a = acc[key][ev]; a[0] += (fin[mt] - q) * 100 * x["size"]; a[1] += x["size"]
        for key in (("takerfee", b), ("takerfee", "ALL")):
            a = acc[key][ev]; a[0] += 5 * x["price"] * (1 - x["price"]) * x["size"]; a[1] += x["size"]
print("tapes used", dict(nm), "secondsDelay", dict(sd))
print("maker-side edge to settlement, cents per share (ratio, se, t by match), matches, shares; last column = taker fee c/share on those fills")
for g in ("all", "dota2", "cs2", "lol", "all_wk1", "all_wk2"):
    for b in [f"{lo:.2f}-{min(hi,1):.2f}" for lo, hi in B] + ["ALL"]:
        d = acc.get((g, b))
        if not d or len(d) < 5: continue
        num = [a[0] for a in d.values()]; den = [a[1] for a in d.values()]; r, se, t = stats.ratio_cluster(num, den)
        f = acc[("takerfee", b)]; fee = sum(a[0] for a in f.values()) / sum(a[1] for a in f.values())
        if g in ("all", "dota2", "cs2") or b in ("0.85-0.92", "0.92-0.97", "0.97-0.99", "ALL"):
            print(f"  {g:8s} {b:10s} {r:7.2f} {se:6.2f} {t:6.2f}  n {len(num):3d}  {sum(den):13,.0f}  usd_pnl {sum(num)/100:11,.0f}  fee {fee:.2f}")
