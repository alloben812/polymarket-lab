"""Model yardstick for equity/ETF/index price markets: at each fill, a plain lognormal fair value from the Yahoo 1-minute
price (proxy for Pyth), the 60-day daily sigma and the variance-time left; barrier (reflection) formula for 'hit' markets
with the running RTH extreme. Three fair values per fill:
  fair      with the reference price at the fill (bar closed <= fill time - 3 s)
  fair_10m  with the reference price 10 minutes earlier
  fair_pc   with the last regular-session close (same time left)  -> isolates the overnight / pre-market move
Edge for the account = fair - price (buy) or price - fair (sell), in cents per share, minus the taker fee."""
import sys, json, math, collections, datetime as dt
import fin, yh, ladder
from pmlab import fees, stats

SKIP = {"WTI", "XAUUSD", "XAGUSD", "NG", "DXY", "NIK"}
PX = {}
def px(tk):
    if tk not in PX: PX[tk] = yh.Px(tk)
    return PX[tk]
def rate(ts): return 0.05 if ts >= 1795219140 else 0.04
def sess(t):
    s = yh.session((t // 86400) * 86400); h = (t % 86400) / 3600
    if s and s[0] <= t < s[1]: return "RTH"
    if s and s[0] - 5.5 * 3600 <= t < s[0]: return "pre"
    if s and s[1] <= t < s[1] + 4 * 3600: return "post"
    return "night/wkend"

def fair_yes(p, ty, kind, K, t, T, a, S):
    sig = p.sig; v = yh.var_left(t, T)
    if ty.startswith("hit"):
        hi = kind == "hitHIGH"; ext = p.extreme(a, t, hi)
        if ext is not None and ((ext >= K) if hi else (ext <= K)): return 1.0, True
        if (S >= K) if hi else (S <= K):       # beyond the strike outside RTH: not counted yet, but nearly sure at the open
            return (0.97 if v > 0 else 0.0), False
        if v <= 0: return 0.0, False
        return min(1.0, 2 * yh.phi(-abs(math.log(K / S)) / (sig * math.sqrt(v)))), False
    if v <= 0: return (1.0 if S > K else 0.0), True
    return yh.phi(math.log(S / K) / (sig * math.sqrt(v))), False

def rows_for(name):
    d = fin.load(name); meta = d["meta"]; res = d["res"]; out = []
    for f in d["fills"]:
        ty, tk = fin.mtype(f["title"], f["slug"]); kind, K = ladder.strike(f["title"] or "")
        if ty not in ("close-day", "close-week", "close-month", "updown-day", "hit-week", "hit-month") or kind in (None, "range") or tk in SKIP or not tk: continue
        p = px(tk)
        if not p.ok: continue
        m = meta.get(f["condition_id"]) or {}; T = fin.ts(m.get("endDate")); t = int(f["timestamp"]) - 3
        if not T: continue
        sT = yh.session((T // 86400) * 86400)
        if sT: T = min(T, sT[1])
        S, age = p.last(t)
        if S is None: continue
        a = fin.ts(m.get("startDate")) or (T - 7 * 86400)
        if ty == "hit-week": a = max(a, ((T // 86400) * 86400) - dt.datetime.fromtimestamp(T, dt.timezone.utc).weekday() * 86400)
        if ty == "updown-day":
            K, _ = p.prev_close(T - 3600)
            if not K: continue
        pc, pct = p.prev_close(t); S10, _ = p.last(t - 600)
        fy, dec = fair_yes(p, ty, kind, K, t, T, a, S)
        fy10, _ = fair_yes(p, ty, kind, K, t, T, a, S10 or S)
        fypc, _ = fair_yes(p, ty, kind, K, t, T, a, pc or S)
        yes = f["outcome"] in ("Yes", "Up"); g = lambda x: x if yes else 1 - x
        sz, prc = float(f["size"]), float(f["price"]); sgn = 1 if f["side"] == "BUY" else -1
        fee = fees.fee_per_share(prc, rate(t)) if f["role"] == "T" else 0.0
        fin_ = ((res.get(f["condition_id"]) or {}).get("final") or {}).get(f["outcome"]) if (res.get(f["condition_id"]) or {}).get("resolved") else None
        out.append(dict(name=name, cond=f["condition_id"], title=f["title"], out=f["outcome"], side=f["side"], role=f["role"], sz=sz, px=prc, t=t, T=T, ty=ty, tk=tk, K=K, S=S, age=age,
                        sess=sess(t), fair=g(fy), fair10=g(fy10), fairpc=g(fypc), decided=dec, sgn=sgn, fee=fee, final=fin_, move_pc=(S / pc - 1) if pc else None, sig=p.sig))
    return out

def table(rows, keyfn, title):
    print(f"\n{title}\n{'key':34}{'fills':>6}{'mkts':>5}{'usd':>9}{'px':>6}{'fair':>6} | {'edge@fill':>9}{'edge@-10m':>10}{'edge@prevclose':>15}{'fee':>6} | {'realized':>9}{'se':>6}{'t':>6}{'n_res':>6} | decided%")
    G = collections.defaultdict(list)
    for r in rows: G[keyfn(r)].append(r)
    for k, rs in sorted(G.items(), key=lambda kv: str(kv[0])):
        sh = sum(r["sz"] for r in rs); usd = sum(r["sz"] * r["px"] for r in rs)
        e = lambda fld: 100 * sum(r["sgn"] * (r[fld] - r["px"]) * r["sz"] for r in rs) / sh
        fee = 100 * sum(r["fee"] * r["sz"] for r in rs) / sh
        rr = [r for r in rs if r["final"] is not None]; byc = collections.defaultdict(lambda: [0.0, 0.0])
        for r in rr: byc[r["cond"]][0] += (r["sgn"] * (r["final"] - r["px"]) - r["fee"]) * r["sz"]; byc[r["cond"]][1] += r["sz"]
        if len(byc) > 2: est, se, t = stats.ratio_cluster([v[0] for v in byc.values()], [v[1] for v in byc.values()])
        else: est = se = t = float("nan")
        dec = sum(r["sz"] * r["px"] for r in rs if r["decided"]) / usd if usd else 0
        print(f"{str(k)[:34]:34}{len(rs):6}{len({r['cond'] for r in rs}):5}{usd:9.0f}{usd / sh:6.3f}{sum(r['fair'] * r['sz'] for r in rs) / sh:6.3f} | {e('fair'):9.2f}{e('fair10'):10.2f}{e('fairpc'):15.2f}{fee:6.2f} | {100 * est:9.2f}{100 * se:6.2f}{t:6.1f}{len(rr):6} | {dec:.1%}")

if __name__ == "__main__":
    names = sys.argv[1:]; allr = []
    for n in names:
        rs = rows_for(n); json.dump(rs, open(f"{fin.HERE}/cache/{n}_model.json", "w")); allr += rs
        fresh = [r for r in rs if r["age"] is not None and r["age"] <= 900]
        print(f"\n################ {n}: fills with a model value {len(rs)}, with a reference bar <= 15 min old {len(fresh)}")
        table(fresh, lambda r: (r["role"], r["side"]), "by role and side (cents per share; realized is net of fee, clustered by market)")
        table(fresh, lambda r: (r["role"], r["sess"]), "by role and session")
        table(fresh, lambda r: (r["ty"],), "by market type")
        table([r for r in fresh if r["side"] == "BUY"], lambda r: ("BUY px " + ("<0.15" if r["px"] < .15 else "0.15-0.45" if r["px"] < .45 else "0.45-0.70" if r["px"] < .7 else ">=0.70"), r["role"]), "buys by price and role")
    # calibration of the yardstick on every fill of every account passed (one observation per market: first fill)
    seen = {}
    for r in sorted(allr, key=lambda r: r["t"]):
        if r["final"] is None or r["age"] is None or r["age"] > 900 or r["final"] not in (0, 1, 0.0, 1.0): continue
        seen.setdefault((r["cond"], r["out"]), r)
    print("\nCALIBRATION of the model (first fill per market/outcome, resolved): fair bucket -> n, mean fair, win rate, mean price paid")
    B = collections.defaultdict(list)
    for r in seen.values(): B[min(int(r["fair"] * 10), 9)].append(r)
    for b in sorted(B):
        rs = B[b]; print(f"  {b / 10:.1f}-{b / 10 + .1:.1f}  n={len(rs):4}  fair={sum(r['fair'] for r in rs) / len(rs):.3f}  won={sum(r['final'] for r in rs) / len(rs):.3f}  price={sum(r['px'] for r in rs) / len(rs):.3f}")
