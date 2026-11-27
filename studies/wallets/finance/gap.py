import sys, json, os, collections, time
import fin, yh, ladder
from pmlab import dataapi, fees
from concurrent.futures import ThreadPoolExecutor
NAMES = ["grasstoucher69", "thanksforplayin", "superstonksbro", "PippiTrader", "C03B", "CoinTrick", "Hauchn"]
SKIP = {"WTI", "XAUUSD", "XAGUSD", "NG", "DXY", "NIK", "SPX", "RUT", "DJIA"}
U = {}
for n in NAMES:
    d = fin.load(n)
    for c, m in d["meta"].items():
        ty, tk = fin.mtype(m.get("question"), m.get("slug")); r = d["res"].get(c) or {}
        if ty and tk and tk not in SKIP and r.get("resolved"): U[c] = dict(m, ty=ty, tk=tk, final=r.get("final"))
print("universe resolved price markets:", collections.Counter(m["ty"] for m in U.values()))
def tape(c):
    p = f"{fin.HERE}/cache/tapes/{c}.json"
    if os.path.exists(p): return json.load(open(p))
    rows = [{k: r.get(k) for k in ("side", "outcome", "price", "size", "timestamp", "proxy_wallet", "transaction_hash")} for r in dataapi.iter_trades(condition=c)]
    json.dump(rows, open(p, "w")); return rows
os.makedirs(f"{fin.HERE}/cache/tapes", exist_ok=True)
hit = [c for c, m in U.items() if m["ty"] in ("hit-week", "hit-month") and (m["final"] or {}).get("Yes") == 1.0]
cl = [c for c, m in U.items() if m["ty"] in ("close-day", "updown-day")]
print("G1 hit markets resolved Yes:", len(hit), " G2 close/updown markets:", len(cl))
with ThreadPoolExecutor(5) as ex: T = dict(zip(hit + cl, ex.map(tape, hit + cl)))
PXc = {}
def px(tk):
    if tk not in PXc: PXc[tk] = yh.Px(tk)
    return PXc[tk]
import datetime as dt
# ---------------- G1
B = collections.Counter(); D = collections.Counter(); W = collections.Counter(); n_touch = 0; no_touch = 0; ex_rows = []; before = [0, 0.0]
lag_first99 = []
for c in hit:
    m = U[c]; kind, K = ladder.strike(m["question"]); hi = kind == "hitHIGH"
    if kind not in ("hitHIGH", "hitLOW") or not K: continue
    T_end = fin.ts(m["endDate"]); a = fin.ts(m["startDate"]) or T_end - 7 * 86400
    if m["ty"] == "hit-week": a = max(a, (T_end // 86400) * 86400 - dt.datetime.fromtimestamp(T_end, dt.timezone.utc).weekday() * 86400)
    tt = px(m["tk"]).first_touch(a, T_end, K * (1.001 if hi else 0.999), hi)
    if not tt: no_touch += 1; continue
    n_touch += 1; rows = sorted(T[c], key=lambda r: r["timestamp"]); f99 = None
    for r in rows:
        t = int(r["timestamp"]) - 3; p = float(r["price"]); s = float(r["size"]); yes = r["outcome"] == "Yes"
        win_buy = r["side"] == "BUY" and yes and p <= 0.97; lose_sell = r["side"] == "SELL" and (not yes) and p >= 0.03
        if t < tt:
            continue
        if f99 is None and ((yes and p >= 0.99) or ((not yes) and p <= 0.01)): f99 = t - tt
        if win_buy or lose_sell:
            g = ((1 - p) if win_buy else p) * s - fees.taker_fee(s, p, 0.05); dl = t - tt
            b = "0-10s" if dl < 10 else "10-60s" if dl < 60 else "1-5m" if dl < 300 else "5-60m" if dl < 3600 else ">1h"
            B[b] += g; D[b] += 1; W[r["proxy_wallet"]] += g
            ex_rows.append((g, m["question"], dl, p, s, r["proxy_wallet"][:10]))
    if f99 is not None: lag_first99.append(f99)
print(f"\nG1: {n_touch} hit markets with a clear Yahoo touch ({no_touch} resolved Yes without a 10 bp Yahoo touch - Pyth/Yahoo mismatch or touch before our bars)")
tot = sum(B.values())
for b in ("0-10s", "10-60s", "1-5m", "5-60m", ">1h"): print(f"   delay {b:7} takes {D[b]:5}  locked net ${B[b]:9.0f}  {B[b] / tot if tot else 0:.0%}")
print(f"   total ${tot:.0f} over {n_touch} markets = ${tot / max(n_touch, 1):.1f} per market; median delay touch -> first print >=0.99: {sorted(lag_first99)[len(lag_first99) // 2] if lag_first99 else None} s (n={len(lag_first99)})")
print("   top wallets:", [(w[:10], round(v)) for w, v in W.most_common(8)])
known = {v: k for k, v in fin.WALLETS.items()}
print("   studied accounts:", {known[w]: round(v) for w, v in W.items() if w in known})
for g, q, dl, p, s, w in sorted(ex_rows, reverse=True)[:12]: print(f"     ${g:7.0f}  delay {dl:7d}s  px {p:.3f} x {s:8.0f}  {w}  {q}")
json.dump(ex_rows, open(f"{fin.HERE}/cache/g1_rows.json", "w"))
# ---------------- G2
after = collections.Counter(); last5 = collections.Counter(); nmk = 0; A = []; W2 = collections.Counter()
for c in cl:
    m = U[c]; T_end = fin.ts(m["endDate"]); s = yh.session((T_end // 86400) * 86400)
    if not s: continue
    Tc = min(T_end, s[1]); nmk += 1; fin_ = m["final"] or {}
    for r in T[c]:
        t = int(r["timestamp"]) - 3; p = float(r["price"]); sz = float(r["size"]); won = fin_.get(r["outcome"]) == 1.0
        gain = ((1 - p) if won else -p) * sz * (1 if r["side"] == "BUY" else -1) - fees.taker_fee(sz, p, 0.05)
        if t > Tc + 5:
            after["n"] += 1; after["usd"] += p * sz; after["gain"] += gain; A.append((gain, t - Tc, p, sz, r["side"], r["outcome"], won, m["question"], r["proxy_wallet"][:10])); W2[r["proxy_wallet"]] += gain
        elif t > Tc - 300:
            last5["n"] += 1; last5["usd"] += p * sz; last5["gain"] += gain
            if 0.03 < p < 0.97: last5["n_mid"] += 1
print(f"\nG2: {nmk} close/updown markets. Trades after the session close: n={after['n']} usd=${after['usd']:.0f} taker gain net of fee ${after['gain']:.0f}; last 5 min before close: n={last5['n']} usd=${last5['usd']:.0f} taker gain ${last5['gain']:.0f} (prints at 0.03-0.97: {last5['n_mid']})")
print("   top wallets after close:", [(w[:10], round(v)) for w, v in W2.most_common(6)], {known[w]: round(v) for w, v in W2.items() if w in known})
for g, dl, p, sz, sd, o, won, q, w in sorted(A, reverse=True)[:10]: print(f"     ${g:7.0f}  +{dl:6d}s  {sd} {o} px {p:.3f} x {sz:8.0f} won={won} {w} {q}")
dl = sorted(a[1] for a in A); print("   delays after close (s):", dl[:5], "median", dl[len(dl) // 2] if dl else None, "max", dl[-1] if dl else None)
