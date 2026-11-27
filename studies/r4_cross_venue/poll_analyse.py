import json, statistics as st, math, collections
rows = []; metas = {}; errs = 0
for l in open("/home/user/polymarket-lab/data/r4/poll15m.jsonl"):
    d = json.loads(l)
    if "meta" in d: metas[d["meta"]["t0"]] = d["meta"]; continue
    if "err" in d: errs += 1; continue
    if d["pm_bid"] is None or d["pm_ask"] is None: continue
    rows.append(d)
print("polls", len(rows), "errors", errs, "span s", round(rows[-1]["t_pm"] - rows[0]["t_pm"]), "windows", {t: (m["k"], m.get("ptb"), m.get("k_strike"), m.get("k_title")) for t, m in metas.items()})
byw = collections.defaultdict(list)
for r in rows: byw[r["t0"]].append(r)
PF, KF = 0.05, 0.07
allcost = []; alld = []
for t0, rs in sorted(byw.items()):
    # make sure the Kalshi market is the same window: ticker HHMM = close time
    d = [((r["pm_bid"] + r["pm_ask"]) / 2) - ((r["k_bid"] + r["k_ask"]) / 2) for r in rs]
    costA = [r["pm_ask"] + PF * r["pm_ask"] * (1 - r["pm_ask"]) + (1 - r["k_bid"]) + KF * r["k_bid"] * (1 - r["k_bid"]) for r in rs]   # PM Up + Kalshi No
    costB = [r["k_ask"] + KF * r["k_ask"] * (1 - r["k_ask"]) + (1 - r["pm_bid"]) + PF * r["pm_bid"] * (1 - r["pm_bid"]) for r in rs]   # Kalshi Yes + PM Down
    rawA = [r["pm_ask"] + 1 - r["k_bid"] for r in rs]; rawB = [r["k_ask"] + 1 - r["pm_bid"] for r in rs]
    mn = [min(a, b) for a, b in zip(costA, costB)]; rw = [min(a, b) for a, b in zip(rawA, rawB)]
    allcost += mn; alld += d
    print(f"window {t0} ({rs[0]['k']}): n={len(rs)} PM-K mid diff mean {st.mean(d):+.4f} median {st.median(d):+.4f} sd {st.pstdev(d):.4f} min {min(d):+.3f} max {max(d):+.3f} | raw cost<1: {sum(x < 1 for x in rw)}/{len(rs)}; net cost<1: {sum(x < 1 for x in mn)}/{len(rs)}; best net {min(mn):.4f}; median PM spread {st.median(r['pm_ask']-r['pm_bid'] for r in rs):.3f} K spread {st.median(r['k_ask']-r['k_bid'] for r in rs):.3f}")
    # lead-lag on poll-to-poll mid changes
    pm = [(r["pm_bid"] + r["pm_ask"]) / 2 for r in rs]; k = [(r["k_bid"] + r["k_ask"]) / 2 for r in rs]
    dp = [pm[i] - pm[i-1] for i in range(1, len(pm))]; dk = [k[i] - k[i-1] for i in range(1, len(k))]
    def corr(x, y):
        if len(x) < 20: return float("nan")
        mx, my = st.mean(x), st.mean(y); sx = math.sqrt(sum((a-mx)**2 for a in x)); sy = math.sqrt(sum((b-my)**2 for b in y))
        return sum((a-mx)*(b-my) for a, b in zip(x, y)) / (sx*sy) if sx and sy else float("nan")
    out = []
    for L in range(-3, 4):
        if L >= 0: x, y = dp[:len(dp)-L] if L else dp, dk[L:]
        else: x, y = dp[-L:], dk[:len(dk)+L]
        out.append(f"L{L:+d}:{corr(x, y):+.2f}")
    dt_ = st.median(rs[i]["t_pm"] - rs[i-1]["t_pm"] for i in range(1, len(rs)))
    print(f"    corr(dPM(t), dK(t+L polls)), poll spacing {dt_:.1f}s: " + " ".join(out) + "   (L>0 = PM first)")
print("overall: polls", len(alld), "mean diff", round(st.mean(alld), 4), "mean |diff|", round(st.mean(abs(x) for x in alld), 4), "share |diff|>=0.03:", round(sum(abs(x) >= 0.03 for x in alld) / len(alld), 3), "share net<1:", round(sum(x < 1 for x in allcost) / len(allcost), 4))
