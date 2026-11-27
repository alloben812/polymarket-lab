"""Near-close lock-in: in close-day / updown-day markets, what did takers get in the last 30 minutes, and how much of it
was 'the outcome is practically decided, the quote is not'?  Model fair from the Yahoo 1-minute price at the fill."""
import json, os, math, collections
import fin, yh, ladder
from pmlab import fees, stats
exec(open("gap.py").read().split("os.makedirs")[0].split("def tape")[0])     # reuse universe U
PXc = {}
def px(tk):
    if tk not in PXc: PXc[tk] = yh.Px(tk)
    return PXc[tk]
R = []
for c, m in U.items():
    if m["ty"] not in ("close-day", "updown-day"): continue
    p = f"cache/tapes/{c}.json"
    if not os.path.exists(p): continue
    T_end = fin.ts(m["endDate"]); s = yh.session((T_end // 86400) * 86400)
    if not s: continue
    Tc = min(T_end, s[1]); P = px(m["tk"]); kind, K = ladder.strike(m["question"])
    if not P.ok: continue
    if m["ty"] == "updown-day": K, _ = P.prev_close(Tc - 3600)
    if not K: continue
    for r in json.load(open(p)):
        t = int(r["timestamp"]) - 3
        if not (Tc - 1800 <= t <= Tc): continue
        S, age = P.last(t)
        if S is None or age > 300: continue
        v = yh.var_left(t, Tc); fy = yh.phi(math.log(S / K) / (P.sig * math.sqrt(v))) if v > 0 else float(S > K)
        yes = r["outcome"] in ("Yes", "Up"); fair = fy if yes else 1 - fy; px_ = float(r["price"]); sz = float(r["size"]); sgn = 1 if r["side"] == "BUY" else -1
        won = (m["final"] or {}).get(r["outcome"]); 
        if won is None: continue
        fee = fees.fee_per_share(px_, 0.05)
        R.append(dict(c=c, q=m["question"], dt=Tc - t, fair=fair, px=px_, sz=sz, sgn=sgn, gain=(sgn * (won - px_) - fee) * sz, medge=sgn * (fair - px_) - fee, w=r["proxy_wallet"], z=abs(math.log(S / K)) / (P.sig * math.sqrt(v)) if v > 0 else 99))
print(f"taker fills in the last 30 min before the close: {len(R)} in {len({r['c'] for r in R})} markets, ${sum(r['px'] * r['sz'] for r in R):.0f}")
def line(lab, rs):
    byc = collections.defaultdict(float)
    for r in rs: byc[r["c"]] += r["gain"]
    usd = sum(r["px"] * r["sz"] for r in rs); g = sum(byc.values()); t = stats.mean_se(list(byc.values()))[2] if len(byc) > 2 else float("nan")
    print(f"  {lab:38} fills {len(rs):5} mkts {len(byc):4} usd {usd:8.0f} taker net ${g:8.0f} ({g / usd if usd else 0:6.1%}) t(mkt) {t:5.1f} losers {sum(1 for r in rs if r['gain'] < 0) / max(len(rs), 1):.0%}")
for lo, hi in ((300, 1800), (60, 300), (10, 60), (0, 10)):
    line(f"{lo}-{hi} s before close: all", [r for r in R if lo <= r["dt"] < hi])
    line(f"   model edge >= 3c after fee", [r for r in R if lo <= r["dt"] < hi and r["medge"] >= 0.03])
    line(f"   decided-ish: |z|>=2.5, with it", [r for r in R if lo <= r["dt"] < hi and r["z"] >= 2.5 and r["medge"] >= 0.01])
    line(f"   model edge <= -3c", [r for r in R if lo <= r["dt"] < hi and r["medge"] <= -0.03])
W = collections.defaultdict(lambda: [0, 0.0, 0.0])
for r in R:
    if r["dt"] < 300: W[r["w"]][0] += 1; W[r["w"]][1] += r["px"] * r["sz"]; W[r["w"]][2] += r["gain"]
known = {v: k for k, v in fin.WALLETS.items()}
print("  top taker wallets in the last 5 min (fills, usd, net):", [(known.get(w, w[:10]), a, round(b), round(g)) for w, (a, b, g) in sorted(W.items(), key=lambda kv: -kv[1][2])[:8]])
print("  bottom:", [(known.get(w, w[:10]), a, round(b), round(g)) for w, (a, b, g) in sorted(W.items(), key=lambda kv: kv[1][2])[:5]])
json.dump(R, open("cache/closewin_rows.json", "w"))
