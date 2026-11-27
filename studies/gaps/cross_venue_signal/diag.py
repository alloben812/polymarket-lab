"""Post-hoc diagnostics (after the protocol run; NOT protocol variants except the one marked V7, which is counted
as an extra post-hoc variant and cannot change the verdict). Writes out/diag.txt."""
import statistics as st, math
from collections import defaultdict, Counter
from datetime import datetime, timezone
import analyze as A

ms, _ = A.load()
ms.sort(key=lambda m: m["k"])
split = ms[len(ms)//2]["k"]
L = []
P = lambda *a: L.append(" ".join(str(x) for x in a))
d = lambda t: datetime.fromtimestamp(t, timezone.utc).strftime("%a %Y-%m-%d %H:%M")
P("matches by kick-off weekday (UTC):", dict(Counter(datetime.fromtimestamp(m['k'], timezone.utc).strftime('%a') for m in ms)))
for sig in ("S1", "S2"):
    gaps, usd, anyp, nm = [], [], 0, 0
    for m in ms:
        pf, _ = A.fair(m, sig == "S2")
        E = A.e1_time(m["k"]) if sig == "S1" else m["k"] - 1800
        if not pf or E is None or m["k"] - E > 96*3600:
            continue
        nm += 1
        cs = A.candidates(m, E, pf)
        if cs:
            anyp += 1
        usd.append(sum(c[3]*c[4] for c in cs))
        gaps += [(c[5]-c[3], c[3]*c[4], c[3]) for c in cs]
    g = [x[0] for x in gaps]
    P(f"\n{sig}: {nm} matches, {anyp} with >=1 taker BUY print in the 30-min window; taker BUY $ per match in window: "
      f"median {st.median(usd):.0f}, mean {st.mean(usd):.0f}, total {sum(usd):.0f}")
    P(f"   prints {len(g)}; fair - price: median {st.median(g)*100:+.2f} pts, p10 {sorted(g)[len(g)//10]*100:+.2f}, "
      f"p90 {sorted(g)[9*len(g)//10]*100:+.2f}, p99 {sorted(g)[99*len(g)//100]*100:+.2f}")
    for X in (0.0, 0.01, 0.02, 0.03, 0.05):
        sub = [x for x in gaps if x[0] >= X]
        P(f"   gap >= {X*100:.0f} pts: {len(sub)} prints ({len(sub)/len(g)*100:.2f}%), ${sum(x[1] for x in sub):.0f}")
    ne = [x for x in gaps if x[0] - 0.05*x[2]*(1-x[2]) > 0]
    P(f"   fair - price - fee > 0: {len(ne)} prints ({len(ne)/len(g)*100:.2f}%), ${sum(x[1] for x in ne):.0f}")
# the 12 protocol trades
P("\nAll protocol trades (X=0.03; X=0.05 is a subset):")
for sig in ("S1", "S2"):
    tr, _ = A.run(ms, sig, 0.03)
    for t in tr:
        P(f"  {sig} {d(t['k'])} {t['event']} {t['role']}-{t['o']} p {t['p']:.3f} fair {t['fair']:.3f} size ${t['size']*t['p']:.1f} "
          f"lag {t['lag']}s win {t['win']} src {t['src']}")
# V7 (post-hoc, counted): first print with fair - price - fee > 0, at E2 with S2 and at E1 with S1
P("\nV7 post-hoc (NOT in protocol): first taker BUY print with fair - price - fee > 0, one per match")
for sig in ("S1", "S2"):
    for part, sub in (("early", [m for m in ms if m["k"] < split]), ("late", [m for m in ms if m["k"] >= split])):
        trs = []
        for m in sub:
            pf, _ = A.fair(m, sig == "S2")
            E = A.e1_time(m["k"]) if sig == "S1" else m["k"] - 1800
            if not pf or E is None or m["k"] - E > 96*3600:
                continue
            q = [c for c in A.candidates(m, E, pf) if c[5] - c[3] - A.fee(c[3]) > 0]
            if q:
                t, r, o, p, z, f, w = q[0]
                pnl = (1.0 if w else 0.0) - p - A.fee(p)
                trs.append(dict(ret=pnl/p, pnl=pnl, p=p, f=f, k=m["k"], usd=min(10, z*p)))
        s = A.summary([t["ret"] for t in trs])
        exp = st.mean([(t["f"] - t["p"] - A.fee(t["p"]))/t["p"] for t in trs]) if trs else float('nan')
        P(f"  {sig} {part}: {A.fmt(s)}; expected ret/$ by the signal {exp*100:+.2f}%; c/sh {st.mean([t['pnl'] for t in trs])*100:+.2f}; "
          f"avg price {st.mean([t['p'] for t in trs]):.3f}; day-cl se {A.day_se(trs)*100:.2f}; $ at <=10/trade {sum(t['usd'] for t in trs):.0f}")
open(A.OUT / "diag.txt", "w").write("\n".join(L) + "\n")
print("\n".join(L))

# who leads: does the bookmaker close move toward Polymarket's price at E1? (post-hoc)
xs, y_bk, y_pm = [], [], []
for m in ms:
    p1, _ = A.fair(m, False); p2, _ = A.fair(m, True); E1 = A.e1_time(m["k"])
    if not p1 or not p2 or E1 is None or m["k"] - E1 > 96*3600:
        continue
    a = [A.last_yes(m, r, E1) for r in "HDA"]; b = [A.last_yes(m, r, m["k"] - 1800) for r in "HDA"]
    if any(v is None or v <= 0 for v in a + b):
        continue
    a = [v/sum(a) for v in a]; b = [v/sum(b) for v in b]
    for i in range(3):
        xs.append(a[i] - p1[i]); y_bk.append(p2[i] - p1[i]); y_pm.append(b[i] - a[i])
sxx = sum(x*x for x in xs)
P(f"\nWho leads (post-hoc, n={len(xs)} outcomes): with g = PM(E1) - S1, the bookmaker close moves S2 - S1 = "
  f"{sum(x*y for x,y in zip(xs,y_bk))/sxx:.3f} x g toward Polymarket, Polymarket moves PM(E2) - PM(E1) = "
  f"{sum(x*y for x,y in zip(xs,y_pm))/sxx:.3f} x g (negative = toward the bookmaker)")
big = [(x, yb, yp) for x, yb, yp in zip(xs, y_bk, y_pm) if abs(x) >= 0.02]
P(f"   outcomes with |g| >= 2 pts: {len(big)}; bookmaker moved toward PM in {sum(1 for x,yb,_ in big if yb*x>0)}, "
  f"PM moved toward bookmaker in {sum(1 for x,_,yp in big if yp*x<0)}")
open(A.OUT / "diag.txt", "w").write("\n".join(L) + "\n")
print("\n".join(L[-2:]))
