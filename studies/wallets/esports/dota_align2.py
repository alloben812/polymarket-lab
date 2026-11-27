"""Dota 2, second pass. Wall clock of a game event = start_time + game time + pauses before it (OpenDota).
1  event study around won fights in 10 s bins, 700..1300 s after the event (where is the market's clock?)
2  net taker flow (buy fight winner minus buy fight loser) per bin: crowd and the studied accounts
3  'leak window' = from the REAL end of the game (start + duration + pauses + 90 s pre-game) to the moment the
   tape still priced the winner below 0.90: who buys the winner there? per wallet z-score against the prices paid."""
import json, os, collections, statistics as st, bisect, math
import lib
ACC = ["RITALINEWITHSNUS", "BLASTSLAM9WINNER", "DamwonChampions2027", "calculate10"]
mp = json.load(open(f"{lib.HERE}/out/od_map.json")); M = lib.meta(list(mp)); R = lib.resol(list(mp))
WL = {lib.WALLETS[n].lower(): n for n in ACC}
AF = {n: collections.defaultdict(list) for n in ACC}
for n in ACC:
    for f in lib.fills(n): AF[n][f["condition_id"]].append(f)
usd = lambda r: r["size"] * r["price"]
BINS = list(range(700, 1310, 10)); curve = collections.defaultdict(list); flow = collections.defaultdict(lambda: collections.Counter()); nev = 0
wal = collections.defaultdict(lambda: dict(n=0, wins=0, sp=0.0, var=0.0, pnl=0.0, usd=0.0)); leak_tot = collections.Counter(); accleak = collections.defaultdict(lambda: collections.Counter())
leaklen = []; endlag = []
for c, v in mp.items():
    d = json.load(open(f"{lib.HERE}/out/od_matches/{v['match_id']}.json")); T = lib.tape(c)
    if len(T) < 50: continue
    m = M[c]; tok0 = lib.gamma.jfield(m["clobTokenIds"])[0]; path = lib.Path(T, tok0); o0r = v["out0_is_radiant"]; S = d["start_time"]; dur = d["duration"]; rw = d["radiant_win"]
    pauses = sorted((p.get("time") or 0, p.get("duration") or 0) for p in (d.get("pauses") or []))
    pz = lambda g: sum(du for t, du in pauses if t < g)
    rad = lambda t: (lambda q: None if q is None else (q if o0r else 1 - q))(path.at(t))
    def raddir(r):
        is0 = r["token_id"] == tok0; buy = r["side"] == "BUY"; d0 = 1 if is0 == buy else -1
        return d0 if o0r else -d0
    # fights
    cl = []; cur = []
    for t, isr in d.get("kills") or []:
        if cur and t - cur[-1][0] > 12: cl.append(cur); cur = []
        cur.append((t, isr))
    if cur: cl.append(cur)
    events = []
    for g in cl:
        r = sum(1 for _, x in g if x); dd = len(g) - r
        if abs(r - dd) >= 3 and g[0][0] >= 600 and g[-1][0] <= dur - 300:
            w = S + g[-1][0] + pz(g[-1][0]); base = rad(w + 700)
            if base is None or not (0.12 <= base <= 0.88): continue
            events.append((w, 1 if r > dd else -1))
            for b in BINS:
                q = rad(w + b)
                if q is not None: curve[b].append((1 if r > dd else -1) * (q - base) * 100)
    nev += len(events)
    for r in T:
        who = WL.get((r.get("proxy_wallet") or "").lower(), "crowd"); rd = raddir(r)
        for w, sg in events:
            x = r["timestamp"] - w
            if 700 <= x < 1300: flow[who][int(x // 10) * 10] += usd(r) * (1 if rd == sg else -1)
    # leak window
    real_end = S + dur + pz(dur + 1) + 90
    wp = [(t, (p if o0r else 1 - p) if rw else 1 - (p if o0r else 1 - p)) for t, p in zip(path.t, path.p)]
    tl90 = None; t99 = None
    for t, p in reversed(wp):
        if p < 0.90: tl90 = t; break
        if p >= 0.99: t99 = t
    if t99: endlag.append(t99 - real_end)
    if not tl90 or tl90 <= real_end + 30: continue
    leaklen.append(tl90 - real_end); wsign = 1 if rw else -1
    per = collections.defaultdict(lambda: [0.0, 0.0, 0.0])   # wallet -> [net shares toward winner, usd, pnl]
    for r in T:
        if not (real_end <= r["timestamp"] <= tl90) or not (0.10 <= r["price"] <= 0.90): continue
        rd = raddir(r); tow = 1 if rd == wsign else -1; w = (r.get("proxy_wallet") or "").lower()
        # price paid for the side taken, in "winner" terms
        is0 = r["token_id"] == tok0; buy = r["side"] == "BUY"; ptok = r["price"]; pside = ptok if buy else 1 - ptok
        a = per[w]; a[0] += tow * r["size"]; a[1] += r["size"] * pside; a[2] += r["size"] * ((1 if tow == 1 else 0) - pside) - 0.05 * ptok * (1 - ptok) * r["size"]
        leak_tot["usd_winner" if tow == 1 else "usd_loser"] += r["size"] * pside
        leak_tot["pnl"] += r["size"] * ((1 if tow == 1 else 0) - pside)
    for w, (net, u, pnl) in per.items():
        if u < 100: continue
        sh = abs(net); p = min(0.95, max(0.05, u / max(sh, 1e-9))) if sh > 0 else 0.5
        a = wal[w]; a["n"] += 1; a["wins"] += 1 if net > 0 else 0; a["sp"] += p; a["var"] += p * (1 - p); a["pnl"] += pnl; a["usd"] += u
    for n in ACC:
        for r in AF[n].get(c, []):
            if real_end <= r["timestamp"] <= tl90 and 0.10 <= r["price"] <= 0.90:
                rd = raddir(r); accleak[n][(r["role"], "winner" if rd == wsign else "loser")] += usd(r)
def P(*a): print(*a, flush=True)
q = lambda v, p: sorted(v)[min(len(v) - 1, int(len(v) * p))]
P(f"events {nev}; end lag with pauses and 90 s pre-game: t99 - real_end p10 {q(endlag,.1)} p25 {q(endlag,.25)} median {q(endlag,.5)} p75 {q(endlag,.75)} p90 {q(endlag,.9)} (n {len(endlag)})")
P("1  price of the fight winner vs its price 700 s after the fight, cents (mean over events), by seconds after the fight:")
P("   " + " ".join(f"{b}:{st.mean(curve[b]):.1f}" for b in BINS if b % 30 == 0))
P("   fine, 900..1100: " + " ".join(f"{b}:{st.mean(curve[b]):.1f}" for b in BINS if 900 <= b <= 1100))
P("2  net taker $ (fight winner minus fight loser) by seconds after the fight:")
for who in ["crowd"] + ACC:
    f = flow[who]; P(f"   {who[:12]:12s} " + " ".join(f"{b}:{sum(f[x] for x in range(b, b + 30, 10)):,.0f}" for b in range(700, 1300, 30)))
P(f"3  leak window (real end -> last print of winner < 0.90): markets {len(leaklen)}, length median {q(leaklen,.5)} s p25 {q(leaklen,.25)} p75 {q(leaklen,.75)}; all taker $ at 0.10-0.90 in it: on winner {leak_tot['usd_winner']:,.0f}, on loser {leak_tot['usd_loser']:,.0f}, taker pnl before fees {leak_tot['pnl']:,.0f}")
rows = []
for w, a in wal.items():
    if a["n"] >= 6:
        z = (a["wins"] - a["sp"]) / math.sqrt(a["var"]) if a["var"] > 0 else 0; rows.append((z, w, a))
rows.sort(reverse=True)
P(f"   wallets with >= 6 leak-window markets: {len(rows)}; z = (wins - sum of prices paid) / sd.  Top 12 and bottom 4:")
for z, w, a in rows[:12] + rows[-4:]:
    P(f"   {w}  {WL.get(w, ''):12s} markets {a['n']:3d} right {a['wins']:3d} expected {a['sp']:5.1f} z {z:5.2f} usd {a['usd']:10,.0f} pnl_after_fee {a['pnl']:10,.0f}")
zs = [r[0] for r in rows]; P(f"   z distribution: mean {st.mean(zs):.2f} sd {st.pstdev(zs):.2f}; z > 2: {sum(1 for x in zs if x > 2)}; z > 3: {sum(1 for x in zs if x > 3)}; z < -2: {sum(1 for x in zs if x < -2)}")
json.dump([(z, w, a) for z, w, a in rows], open(f"{lib.HERE}/out/leak_wallets.json", "w"))
for n in ACC: P(f"   {n[:12]:12s} leak-window $: " + "  ".join(f"{k[0]}/{k[1]} {v:,.0f}" for k, v in sorted(accleak[n].items())))
