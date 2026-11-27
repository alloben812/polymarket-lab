"""Audit a2: crypto one-trade-per-market on the tape, own code, plus attacks (give-up window, +1 tick, size,
no-print entries, day clustering, without best day, weekend, asset, type)."""
import gzip, json, math, pickle, re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import importlib.util
spec = importlib.util.spec_from_file_location("a1", Path(__file__).with_name("a1_recompute.py"))
D = Path("/home/user/polymarket-lab/data/gaps_resolution_bonds"); OUT = Path(__file__).resolve().parent
E = [e for e in pickle.load(open(OUT / "a1_entries.pkl", "rb")) if e["fam"] == "crypto"]
fee = lambda p, r: r * p * (1 - p)
def ct(vals, cl):
    s, n = defaultdict(float), defaultdict(int)
    for v, c in zip(vals, cl): s[c] += v; n[c] += 1
    N, G = len(vals), len(s); m = sum(vals) / N
    if G < 2: return m, float("nan"), float("nan")
    se = math.sqrt(sum((s[c] - m * n[c]) ** 2 for c in s) * G / (G - 1)) / N
    return m, se, m / se if se else float("inf")
def wil(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h
def day(t): return datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d")
def wkend(t): return datetime.fromtimestamp(t, tz=timezone.utc).weekday() >= 5
def ctype(s):
    if "up-or-down-on" in s: return "updown daily"
    if "up-or-down" in s: return "updown hourly"
    if "above" in s or "less-than" in s: return "above"
    if "between" in s: return "range"
    if "dip" in s or "reach" in s or "hit" in s: return "dip/reach"
    return "other"
def asset(s):
    for a in ("bitcoin", "ethereum", "solana", "xrp"):
        if a in s: return a
    return "other"
tok_match = 0; notape = 0
for e in E:
    p = D / "tapes" / f"{e['cid']}.json.gz"
    if not p.exists(): e["rows"] = None; notape += 1; continue
    d = json.load(gzip.open(p, "rt"))
    e["capped"] = d["capped"]
    toks = set(r[2] for r in d["rows"])
    tok_match += e["tok"] in toks
    e["rows"] = sorted((r[0], r[3], r[4]) for r in d["rows"] if r[1] == "BUY" and r[2] == e["tok"])
    e["allrows"] = len(d["rows"])
print("crypto entries", len(E), "no tape", notape, "tape contains fav token", tok_match, "capped", sum(e.get("capped", False) for e in E))
L = []
def first(e, D_, W=None, minusd=0):
    if not e["rows"]: return None
    for t, p, sz in e["rows"]:
        if t < e["t"] + D_ or t > e["closed"]: continue
        if W is not None and t > e["t"] + W: return None
        if 0.95 - 1e-9 <= p < 0.98 - 1e-9 and p * sz >= minusd: return t, p, sz
    return None
def report(name, sel, tick=0.0, extra=None):
    g = []
    for e in sel:
        f = first(e, **(extra or {"D_": 10}))
        if f is None: continue
        p = min(f[1] + tick, 0.999); c = p + fee(p, e["rate"])
        g.append((e, 10 * (e["pay"] - c) / c, c))
    if not g: L.append(f"{name} | 0"); return g
    k = sum(x[0]["pay"] < 1 for x in g); lo, hi = wil(k, len(g))
    mev = ct([x[1] for x in g], [x[0]["ev"] for x in g]); mday = ct([x[1] for x in g], [day(x[0]["closed"]) for x in g])
    be = 100 * (1 - sum(x[2] for x in g) / len(g))
    L.append(f"{name} | {len(g)} | {k} | {100*k/len(g):.2f} ({100*lo:.1f}-{100*hi:.1f}) | {be:.2f} | {mev[0]:+.3f} | {mev[2]:+.1f} | {mday[2]:+.1f}")
    return g
L.append("variant | markets | lost | loss % (Wilson) | break-even % | net per 10 USD | t event | t day")
for per in ("both", "early", "late"):
    s = [e for e in E if per == "both" or e["late"] == (per == "late")]
    g = report(f"10s first print, {per}", s)
G10 = report("10s, both (kept)", E)
report("10s +1 tick (0.01) on the print price", E, tick=0.01)
report("10s +2 ticks", E, tick=0.02)
report("60s first print", E, extra={"D_": 60})
report("300s first print", E, extra={"D_": 300})
report("live-like: print within 10-60 s of trigger", E, extra={"D_": 10, "W": 60})
report("live-like: print within 10-300 s of trigger", E, extra={"D_": 10, "W": 300})
report("first print >=10s with >=10 USD in that print", E, extra={"D_": 10, "minusd": 10})
report("13s (block-3s => match >= t+10)", E, extra={"D_": 13})
for ty in ("updown hourly", "updown daily", "above", "range", "dip/reach"):
    report(f"type {ty}", [e for e in E if ctype(e["slug"]) == ty])
for a in ("bitcoin", "ethereum", "solana", "xrp"):
    report(f"asset {a}", [e for e in E if asset(e["slug"]) == a])
report("weekend (closed Sat/Sun UTC)", [e for e in E if wkend(e["closed"])])
report("weekday", [e for e in E if not wkend(e["closed"])])
CH = datetime(2026, 11, 18, tzinfo=timezone.utc).timestamp()
report("hourly updown before 18 Nov (Binance)", [e for e in E if ctype(e["slug"]) == "updown hourly" and e["closed"] < CH])
report("hourly updown from 18 Nov (Chainlink)", [e for e in E if ctype(e["slug"]) == "updown hourly" and e["closed"] >= CH])
report("non-hourly crypto", [e for e in E if ctype(e["slug"]) != "updown hourly"])
# no-print entries
nop = [e for e in E if first(e, 10) is None]
L.append(f"entries without a qualifying print: {len(nop)}, lost {sum(e['pay']<1 for e in nop)}; all entries {len(E)}, lost {sum(e['pay']<1 for e in E)}")
# robustness: without best day, without 10 best markets, leave-one-day-out min
byday = defaultdict(list)
for x in G10: byday[day(x[0]["closed"])].append(x[1])
tot = sum(x[1] for x in G10); n = len(G10)
best = max(byday, key=lambda d: sum(byday[d]))
L.append(f"without best day {best}: mean {(tot-sum(byday[best]))/(n-len(byday[best])):+.3f} per 10 USD on {n-len(byday[best])}")
srt = sorted(x[1] for x in G10)
L.append(f"without 10 best markets: {sum(srt[:-10])/(n-10):+.3f}; days {len(byday)}; worst day sum {min(sum(v) for v in byday.values()):+.2f} USD")
# loss-rate needed to kill: how many more losses until mean <= 0
L.append(f"mean win +{sum(x[1] for x in G10 if x[0]['pay']>=1)/sum(1 for x in G10 if x[0]['pay']>=1):.3f}, mean loss {sum(x[1] for x in G10 if x[0]['pay']<1)/max(1,sum(1 for x in G10 if x[0]['pay']<1)):.2f}")
# delay distribution from trigger to first print
dl = sorted(first(e, 10)[0] - e["t"] for e in E if first(e, 10))
L.append(f"delay trigger->first print (block time) s: median {dl[len(dl)//2]}, p75 {dl[3*len(dl)//4]}, p90 {dl[9*len(dl)//10]}, share > 300 s {sum(x>300 for x in dl)/len(dl):.2f}")
L.append("losers (10 s): " + "; ".join(f"{x[0]['slug']} p={first(x[0],10)[1]:.3f} t-trig {first(x[0],10)[0]-x[0]['t']}s, {(x[0]['closed']-first(x[0],10)[0])/60:.0f} min to close" for x in G10 if x[0]["pay"] < 1))
L.append("trades per day (10s variant): %.1f over %d days" % (len(G10) / 36, 36))
print("\n".join(L)); (OUT / "a2_out.txt").write_text("\n".join(L) + "\n")
pickle.dump([(x[0]["cid"], x[0]["slug"], x[0]["closed"], x[0]["pay"], first(x[0], 10)) for x in G10], open(OUT / "a2_g10.pkl", "wb"))
