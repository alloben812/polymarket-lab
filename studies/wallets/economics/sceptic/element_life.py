"""Sceptic: TheElement115 whole life (joined 2026-07-21). Independent timing test that does not use the analyst's
schedule table: seconds past the nearest earlier quarter hour for every fill. Per-market P&L at final prices."""
import pickle, collections, datetime as dt, math, json
from pmlab import dataapi
P = "/home/user/polymarket-lab/data/econ_tapes/sceptic_%s.pkl"
d = pickle.load(open(P % "TheElement115", "rb")); fills = sorted(d["fills"], key=lambda f: f["timestamp"])
f_ = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%m-%d %H:%M:%S")
print("fills", len(fills), "roles", collections.Counter(f["role"] for f in fills), "sides", collections.Counter(f["side"] for f in fills))
res = dataapi.resolutions(sorted({f["condition_id"] for f in fills}))
rows = []
for f in fills:
    usd = f["size"] * f["price"]; q = f["timestamp"] % 900
    r = res.get(f["condition_id"]) or {}
    fin = float(r["final"].get(f["outcome"]) or 0) if r.get("resolved") else None
    rows.append((f, usd, q, fin))
big = [x for x in rows if x[1] >= 20]; small = [x for x in rows if x[1] < 20]
def dist(xs, lab):
    b = collections.Counter("0-5" if q < 6 else "6-20" if q <= 20 else "21-40" if q <= 40 else "41-120" if q <= 120 else ">120" for _, _, q, _ in xs)
    print(f"  {lab}: n={len(xs)} usd={sum(x[1] for x in xs):.0f} seconds past :00/:15/:30/:45 -> {dict(b)}")
dist(big, "fills >= $20"); dist(small, "fills < $20")
for per, lo, hi in (("Jul-Aug (outside the analyst's window)", 0, 1788134400), ("Sep-Nov", 1788134400, 2e9)):
    xs = [x for x in big if lo <= x[0]["timestamp"] < hi]; dist(xs, per + " >= $20")
print("  fills >= $20 more than 40 s past a quarter hour:")
for f, usd, q, fin in big:
    if q > 40: print(f"     {f_(f['timestamp'])} q={q:4d}s {f['side']} {f['outcome']} px={f['price']:.3f} usd={usd:7.0f} final={fin} {f['slug'][:60]}")
print("  small fills sample:", [(f_(f["timestamp"]), f["side"], round(f["price"], 3), round(usd, 1), f["slug"][:25]) for f, usd, q, fin in small[:6]])
# per-market P&L with fee 0.04 before 11-21, 0.01 after
mk = collections.defaultdict(lambda: [0.0, 0.0, None, 0, None])
for f, usd, q, fin in rows:
    if fin is None: continue
    s = 1 if f["side"] == "BUY" else -1
    rate = 0.04 if f["timestamp"] < 1795305600 else 0.01
    pnl = s * (fin - f["price"]) * f["size"] - rate * f["size"] * f["price"] * (1 - f["price"])
    m = mk[f["condition_id"]]; m[0] += pnl; m[1] += usd; m[2] = f["slug"]; m[3] = f["timestamp"]; m[4] = f.get("event_slug")
xs = sorted(mk.values(), key=lambda m: -m[0]); pn = [m[0] for m in xs]
t_ = lambda v: (sum(v) / len(v)) / math.sqrt(sum((x - sum(v) / len(v)) ** 2 for x in v) / (len(v) - 1) / len(v))
print(f"\nper market at final, fee 0.04 before 11-21: markets {len(xs)}, P&L {sum(pn):.0f} on ${sum(m[1] for m in xs):.0f}, positive {sum(1 for x in pn if x > 0)}, t {t_(pn):.2f}; top3 {sum(pn[:3]):.0f}; rest {sum(pn[3:]):.0f} (t {t_(pn[3:]):.2f}); losers {sum(1 for x in pn if x < -5)} worth {sum(x for x in pn if x < -5):.0f}")
for m in xs[:5]: print(f"    top {f_(m[3])} {m[2][:62]:62} {m[0]:7.0f} on {m[1]:6.0f}")
for m in xs[-5:]: print(f"    worst {f_(m[3])} {m[2][:60]:60} {m[0]:7.0f} on {m[1]:6.0f}")
days = collections.defaultdict(float)
for m in xs: days[f_(m[3])[:5]] += m[0]
ds = sorted(days.values(), reverse=True)
print(f"by release day: {len(ds)} days, positive {sum(1 for x in ds if x > 0)}, top3 days {sum(ds[:3]):.0f} of {sum(ds):.0f}, t by day {t_(ds):.2f}, t without top3 {t_(ds[3:]):.2f}")
bym = collections.defaultdict(lambda: [0.0, 0.0, 0])
for m in xs: k = f_(m[3])[:2]; bym[k][0] += m[0]; bym[k][1] += m[1]; bym[k][2] += 1
print("by month:", {k: (round(v[0]), round(v[1]), v[2]) for k, v in sorted(bym.items())})
pb = collections.defaultdict(lambda: [0.0, 0.0])
for f, usd, q, fin in big:
    if fin is None or f["side"] != "BUY": continue
    k = "<0.80" if f["price"] < 0.8 else "0.80-0.95" if f["price"] < 0.95 else ">=0.95"
    pb[k][0] += usd; pb[k][1] += (fin - f["price"]) * f["size"]
print("buys by price paid (usd, edge before fee):", {k: (round(v[0]), round(v[1])) for k, v in pb.items()})
# same operator? compare with road2million fills in the same second and market
r2 = pickle.load(open(P % "road2million", "rb"))["fills"]
r2 = [f for f in r2 if f["timestamp"] >= 1784000000]
mine = collections.defaultdict(list)
for f in fills: mine[f["condition_id"]].append(f)
same = [(f["timestamp"] - min(mine[f["condition_id"]], key=lambda g: abs(g["timestamp"] - f["timestamp"]))["timestamp"]) for f in r2 if f["condition_id"] in mine]
r2big = [f for f in r2 if f["size"] * f["price"] >= 20]
print(f"\nroad2million since 07-13: fills {len(r2)} (>= $20: {len(r2big)}); in markets TheElement115 also traded: {len(same)}; time difference s: {dict(collections.Counter('same block' if x == 0 else '1-3 s' if abs(x) <= 3 else '4-15 s' if abs(x) <= 15 else 'more' for x in same))}")
print("   seconds past quarter hour, road2million >= $20:", dict(collections.Counter("0-20" if f["timestamp"] % 900 <= 20 else "21-40" if f["timestamp"] % 900 <= 40 else ">40" for f in r2big)))
