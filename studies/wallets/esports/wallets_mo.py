"""Per-wallet taker statistics on the cached whole-market tapes: who is early? (10 s markout, c/share, by wallet)
and who trades in the 12 s BEFORE the RITALINE bot's episodes in the same direction. Also the bot's best/worst
episodes with the kills around them (feed clock = OpenDota clock + 990 s)."""
import json, os, collections, bisect, lib
from pmlab import stats
conds = {}
for n in lib.WALLETS:
    for f in lib.fills(n): conds[f["condition_id"]] = f["event_slug"]
M = lib.meta(list(conds)); R = lib.resol(list(conds)); NAME = {v.lower(): k for k, v in lib.WALLETS.items()}
try:
    for r in json.load(open(f"{lib.HERE}/leaders_top60.json")): NAME.setdefault(r["wallet"].lower(), r["name"])
except Exception: pass
W = collections.defaultdict(lambda: collections.defaultdict(lambda: [0.0, 0.0, 0.0, 0.0, 0.0]))   # game -> wallet -> [sh, mo10*sh, final*sh, usd, fee]
WM = collections.defaultdict(lambda: collections.defaultdict(set))
E = json.load(open(f"{lib.HERE}/out/ritaline_episodes.json")); EP = collections.defaultdict(list)
for e in E: EP[e["c"]].append(e)
pre = collections.defaultdict(lambda: [0, 0.0])
for c, ev in conds.items():
    p = f"{lib.HERE}/fills/tape_{c[:14]}.json.gz"
    if not os.path.exists(p): continue
    m = M.get(c) or {}; r = R.get(c) or {}; game = (m.get("slug") or "").split("-")[0]
    outs = lib.gamma.jfield(m.get("outcomes")) or []; toks = lib.gamma.jfield(m.get("clobTokenIds")) or []
    if not r.get("resolved") or len(outs) != 2 or game not in ("dota2", "cs2"): continue
    tok0 = toks[0]; fin0 = float(r["final"].get(outs[0]) or 0); T = lib.tape(c); path = lib.Path(T, tok0)
    for x in T:
        is0 = x["token_id"] == tok0; buy = x["side"] == "BUY"; d0 = 1 if is0 == buy else -1; p0 = x["price"] if is0 else 1 - x["price"]
        if not (0.05 <= x["price"] <= 0.95): continue
        q = path.at(x["timestamp"] + 10); w = (x.get("proxy_wallet") or "").lower(); a = W[game][w]
        a[0] += x["size"]; a[1] += d0 * ((q if q is not None else p0) - p0) * 100 * x["size"]; a[2] += d0 * (fin0 - p0) * 100 * x["size"]; a[3] += x["size"] * x["price"]; a[4] += 5 * x["price"] * (1 - x["price"]) * x["size"]
        WM[game][w].add(ev)
    for e in EP.get(c, []):
        seen = set()
        for x in T:
            if e["t0"] - 12 <= x["timestamp"] < e["t0"] - 1:
                is0 = x["token_id"] == tok0; buy = x["side"] == "BUY"; d0 = 1 if is0 == buy else -1
                ed = 1 if (e["px"] is not None and ((path.at(e["t0"]) or 0) >= 0)) else 1
                w = (x.get("proxy_wallet") or "").lower()
                # direction of the episode in outcome-0 terms: sign of fin-based field is not stored, use price move
                seen.add((w, d0)); pre[(w, d0 == (1 if e["mo10"] is None or True else 1))][1] += x["size"] * x["price"]
        for w, d0 in seen: pre[(w, True)][0] += 1
for game in ("dota2", "cs2"):
    rows = [(a[1] / 100, w, a) for w, a in W[game].items() if a[3] >= 50000 and len(WM[game][w]) >= 8]
    rows.sort(reverse=True); tot = sum(a[3] for a in W[game].values())
    print(f"== {game}: taker wallets {len(W[game])}, taker $ at 0.05-0.95 {tot:,.0f}; wallets with >= $50K and >= 8 matches: {len(rows)}. Top 10 by dollars gained 10 s after the fill, then bottom 3:")
    for g, w, a in rows[:10] + rows[-3:]:
        print(f"   {w} {NAME.get(w, '')[:18]:18s} matches {len(WM[game][w]):3d} usd {a[3]:11,.0f} mo10 {a[1]/a[0]:6.2f} c  final {a[2]/a[0]:6.2f} c  fee {a[4]/a[0]:.2f} c  net_to_final_after_fee ${(a[2]-a[4])/100:10,.0f}")
    pos = sum(1 for g, w, a in rows if a[1] / a[0] > a[4] / a[0]); print(f"   wallets whose 10 s markout exceeds their fee: {pos}/{len(rows)}; whose final edge exceeds fee: {sum(1 for g, w, a in rows if a[2] > a[4])}/{len(rows)}")
top = sorted(((v[0], w) for (w, _), v in pre.items()), reverse=True)[:8]
print("wallets most often taking in the 12 s before a RITALINE episode (episodes, name):", [(n, w[:10], NAME.get(w, "")) for n, w in top], "of", len(E))
# stories of episodes
mp = json.load(open(f"{lib.HERE}/out/od_map.json"))
E2 = sorted([e for e in E if e["usd"] >= 800 and e["mo60"] is not None], key=lambda e: -e["mo60"] * e["sh"])
for e in E2[:5] + E2[-3:]:
    v = mp[e["c"]]; d = json.load(open(f"{lib.HERE}/out/od_matches/{v['match_id']}.json")); g = e["t0"] - d["start_time"] - 990
    ks = [(t, "R" if isr else "D") for t, isr in d["kills"] if g - 90 <= t <= g + 30]
    print(f"   {e['slug'][6:34]:28s} {lib.iso(e['t0'])} feed-min {g/60:5.1f} ${e['usd']:6,.0f} at {e['pxavg']:.3f} (pre5 {e['pre5']:+.1f}c) -> +10s {e['mo10']:+.1f}c +60s {e['mo60']:+.1f}c final {e['fin']:+.0f}c | others before/after ${e['others_before']:,.0f}/${e['others_after']:,.0f} | kills in feed window [-90,+30]s: {' '.join(f'{int(t-g)}{s}' for t, s in ks)} | radiant={v['radiant']}")
