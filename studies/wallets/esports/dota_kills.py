"""Dota 2: what does the taker bot react to, and how far ahead of the crowd is it?
Pooled histogram of (fill time - wall time of each kill by the BOUGHT team) for lags 880..1100 s (the broadcast delay
found in dota_align2), 5 s bins, against the placebo (kills by the OTHER team). A sharp excess = event-driven with a
fixed latency; the bin of the excess for the account vs the crowd = its lead."""
import json, collections, bisect, lib
ACC = ["RITALINEWITHSNUS", "BLASTSLAM9WINNER", "DamwonChampions2027", "calculate10"]
mp = json.load(open(f"{lib.HERE}/out/od_map.json")); M = lib.meta(list(mp))
WL = {lib.WALLETS[n].lower(): n for n in ACC}
AF = {n: collections.defaultdict(list) for n in ACC}
for n in ACC:
    for f in lib.fills(n): AF[n][f["condition_id"]].append(f)
LO, HI, BW = 880, 1100, 5
H = collections.defaultdict(lambda: collections.Counter()); tot = collections.Counter()
for c, v in mp.items():
    d = json.load(open(f"{lib.HERE}/out/od_matches/{v['match_id']}.json")); T = lib.tape(c)
    if len(T) < 50: continue
    tok0 = lib.gamma.jfield(M[c]["clobTokenIds"])[0]; o0r = v["out0_is_radiant"]; S = d["start_time"]
    pauses = sorted((p.get("time") or 0, p.get("duration") or 0) for p in (d.get("pauses") or []))
    pz = lambda g: sum(du for t, du in pauses if t < g)
    kr = sorted(S + t + pz(t) for t, isr in d.get("kills") or [] if isr and t > 300); kd = sorted(S + t + pz(t) for t, isr in d.get("kills") or [] if not isr and t > 300)
    def add(key, t, rd, w):
        tot[key] += w
        for lab, ks in (("same", kr if rd == 1 else kd), ("opp", kd if rd == 1 else kr)):
            i = bisect.bisect_left(ks, t - HI); j = bisect.bisect_right(ks, t - LO)
            for k in ks[i:j]: H[(key, lab)][int((t - k - LO) // BW)] += w
    def raddir(r):
        is0 = r["token_id"] == tok0; buy = r["side"] == "BUY"; d0 = 1 if is0 == buy else -1
        return d0 if o0r else -d0
    for r in T:
        if (r.get("proxy_wallet") or "").lower() in WL or not (0.1 <= r["price"] <= 0.9): continue
        add("crowd_T", r["timestamp"], raddir(r), r["size"] * r["price"])
    for n in ACC:
        for r in AF[n].get(c, []):
            if 0.1 <= r["price"] <= 0.9: add(f"{n[:8]}_{r['role']}", r["timestamp"], raddir(r), r["size"] * r["price"])
nb = (HI - LO) // BW
print("ratio same/opp of $-weighted kill counts per 5 s lag bin (1.00 = no relation); lag = fill block time - kill wall time; block time is ~2 s after the match")
print("lag      " + " ".join(f"{LO + b * BW:5d}" for b in range(0, nb, 2)))
for key in sorted(tot):
    s, o = H[(key, "same")], H[(key, "opp")]
    r10 = [(s[b] + s[b + 1]) / max(1e-9, o[b] + o[b + 1]) for b in range(0, nb, 2)]
    print(f"{key:11s}" + " ".join(f"{x:5.2f}" for x in r10) + f"   total$ {tot[key]:,.0f}")
for key in ("RITALINE_T", "crowd_T", "BLASTSLA_T", "DamwonCh_T", "calculat_M", "BLASTSLA_M"):
    s, o = H[(key, "same")], H[(key, "opp")]
    ex = [s[b] - o[b] for b in range(nb)]; tp = sum(x for x in ex if x > 0) or 1
    cum = 0; med = None
    for b in range(nb):
        cum += max(0, ex[b])
        if med is None and cum >= tp / 2: med = LO + b * BW
    pk = max(range(nb), key=lambda b: ex[b])
    print(f"{key:11s} excess (same - opp) peak bin {LO + pk * BW}-{LO + pk * BW + BW} s, median of positive excess {med} s, fine 940..1040: " + " ".join(f"{LO + b * BW}:{(s[b]) / max(1e-9, o[b]):.2f}" for b in range((940 - LO) // BW, (1040 - LO) // BW)))
