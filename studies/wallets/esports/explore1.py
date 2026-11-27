import sys, json, collections, statistics as st
import lib
from pmlab import gamma
name = sys.argv[1]
F = lib.fills(name); M = lib.meta([f["condition_id"] for f in F])
if len(sys.argv) > 2:
    m = M[F[len(F)//2]["condition_id"]]
    print({k: (str(v)[:300]) for k, v in m.items() if k in ("slug","question","description","resolutionSource","endDate","gameStartTime","eventStartTime","closedTime","sportsMarketType","secondsDelay","feeSchedule","feeType","volumeNum","customLiveness","orderPriceMinTickSize","groupItemTitle","line","umaEndDate","startDate","createdAt","acceptingOrdersTimestamp","rewardsMinSize","rewardsMaxSpread","gameId","teamAID")})
    print(sorted(m.keys()))
usd = lambda f: f["size"]*f["price"]
tot = sum(usd(f) for f in F)
by = collections.defaultdict(lambda: [0, 0.0, set()])
tim = collections.defaultdict(float)
for f in F:
    m = M.get(f["condition_id"]) or {}
    k = (lib.game(m) or (f.get("slug") or "?").split("-")[0], lib.mtype(m), f["role"], f["side"])
    by[k][0] += 1; by[k][1] += usd(f); by[k][2].add(f["condition_id"])
    gs = lib.ts(m.get("gameStartTime") or m.get("eventStartTime")); ct = lib.ts(m.get("closedTime"))
    if gs is None: b = "no start"
    else:
        d = f["timestamp"] - gs
        b = "a >24h before" if d < -86400 else "b 1-24h before" if d < -3600 else "c 0-60m before" if d < 0 else "d 0-30m in" if d < 1800 else "e 30-90m in" if d < 5400 else "f 90m-3h in" if d < 10800 else "g >3h in"
    tim[(f["role"], b)] += usd(f)
print(f"== {name}: fills {len(F)}, usd {tot:,.0f}, markets {len(set(f['condition_id'] for f in F))}, events {len(set(f['event_slug'] for f in F))}")
for k, v in sorted(by.items(), key=lambda kv: -kv[1][1])[:14]:
    print(f"  {str(k):60s} fills {v[0]:6d} usd {v[1]:11,.0f} ({v[1]/tot*100:4.1f}%) mkts {len(v[2])}")
print("  timing vs gameStartTime (share of $):")
for k, v in sorted(tim.items()): print(f"    {k[0]} {k[1]:16s} {v/tot*100:5.1f}%")
# per-market sizing & concurrency
pm = collections.defaultdict(float)
for f in F:
    if f["side"] == "BUY": pm[f["condition_id"]] += usd(f)
v = sorted(pm.values())
print(f"  buy $ per market: median {st.median(v):,.0f} p90 {v[int(len(v)*.9)]:,.0f} max {v[-1]:,.0f}")
pe = collections.defaultdict(float)
for f in F:
    if f["side"] == "BUY": pe[f["event_slug"]] += usd(f)
v = sorted(pe.values()); print(f"  buy $ per event(match): median {st.median(v):,.0f} p90 {v[int(len(v)*.9)]:,.0f} max {v[-1]:,.0f}; events/day {len(pe)/14:.1f}")
# both sides
sides = collections.defaultdict(lambda: collections.defaultdict(lambda: [0.0, 0.0]))
for f in F:
    if f["side"] == "BUY":
        a = sides[f["condition_id"]][f["token_id"]]; a[0] += f["size"]; a[1] += usd(f)
both = [c for c, d in sides.items() if len(d) == 2]
pc = []; paired = 0
for c in both:
    (s1, u1), (s2, u2) = sides[c].values(); n = min(s1, s2); paired += n; pc.append((u1/s1 + u2/s2, n))
if pc:
    print(f"  bought both outcomes in {len(both)}/{len(sides)} markets; paired shares {paired:,.0f}; pair cost (share-weighted avg px sum) {sum(a*n for a,n in pc)/sum(n for a,n in pc):.4f}")
I = lib.inv(name); c = collections.Counter(e.get("type") for e in I); print("  inventory events", dict(c), "merge usd", round(sum(float(e.get("usdc_size") or e.get("size") or 0) for e in I if e.get("type")=="MERGE")))
