"""Audit, independent recomputation of the F3 rule from raw caches (events_raw.json.gz, tapes, model_probs.csv).
Does not import the author's common.py / s09. Run: python3 -I a1_rule.py
Model probabilities are taken from model_probs.csv (checked separately by a2_model.py)."""
import gzip, json, csv, math, re, collections, datetime as dt, bisect, sys, random
from zoneinfo import ZoneInfo
R = "/home/user/polymarket-lab/data"
D = R + "/gaps_weather_fc"
TZ = {"nyc": "America/New_York", "atlanta": "America/New_York", "miami": "America/New_York", "chicago": "America/Chicago",
      "dallas": "America/Chicago", "houston": "America/Chicago", "austin": "America/Chicago", "denver": "America/Denver",
      "los-angeles": "America/Los_Angeles", "san-francisco": "America/Los_Angeles", "seattle": "America/Los_Angeles"}
MON = {m: i for i, m in enumerate("january february march april may june july august september october november december".split(), 1)}
LAG = int(sys.argv[1]) if len(sys.argv) > 1 else 3   # block lag: match time = block - LAG, must be >= decision

# ---- universe from the raw gamma dump
E = json.load(gzip.open(D + "/events_raw.json.gz"))
mk = collections.defaultdict(list); seen = set(); est_bad = 0
for e in E:
    m = re.fullmatch(r"highest-temperature-in-(.+)-on-([a-z]+)-(\d+)-2026", e["slug"])
    if not m or m.group(1) not in TZ: continue
    city = m.group(1); d = dt.date(2026, MON[m.group(2)], int(m.group(3)))
    if not (dt.date(2026, 9, 20) <= d <= dt.date(2026, 11, 25)): continue
    if (city, d) in seen: continue
    seen.add((city, d))
    z = ZoneInfo(TZ[city]); nd = d + dt.timedelta(days=1)
    tend = int(dt.datetime(nd.year, nd.month, nd.day, tzinfo=z).timestamp())
    tst = int(dt.datetime(d.year, d.month, d.day, tzinfo=z).timestamp())
    for x in e["markets"]:
        est = x.get("eventStartTime")
        if est and int(dt.datetime.fromisoformat(est.replace("Z", "+00:00")).timestamp()) != tst: est_bad += 1
        op = json.loads(x["outcomePrices"]); oc = json.loads(x["outcomes"]); assert oc == ["Yes", "No"]
        mk[(city, d.isoformat())].append(dict(c=x["conditionId"], b=x["groupItemTitle"], tend=tend, yes_gamma=float(op[0]),
                                                vol=float(x.get("volumeNum") or 0)))
print("city-days", len(mk), "markets", sum(len(v) for v in mk.values()), "eventStartTime != my local midnight:", est_bad)
# winners: data-api resolutions file AND gamma outcomePrices
wa = {r["condition"]: r["yes_final"] for r in csv.DictReader(open(D + "/winners.csv"))}
dis = 0; bad_ev = 0
for k, L in mk.items():
    ys = [float(wa[m["c"]]) for m in L]
    if sorted(ys) != [0.0] * (len(L) - 1) + [1.0]: bad_ev += 1
    for m, y in zip(L, ys):
        m["y"] = y; dis += (y != m["yes_gamma"])
print("events without exactly one winner:", bad_ev, "; winner disagreements data-api vs gamma outcomePrices:", dis)

# ---- model probabilities
P = {}
for r in csv.DictReader(open(D + "/model_probs.csv")):
    P[(r["condition"], int(r["slot"]), r["version"])] = float(r["prob"])

# ---- tapes: first buyable YES print
TP = {}
def tape(c):
    if c not in TP:
        try:
            rows = [json.loads(l) for l in gzip.open(f"{R}/tape/{c}.jsonl.gz", "rt")]
        except FileNotFoundError:
            TP[c] = None; return None
        b = []
        for r in rows:
            if r["o"] == "Yes" and r["s"] == "BUY": b.append((r["t"], r["p"], r["z"]))
            elif r["o"] == "No" and r["s"] == "SELL": b.append((r["t"], round(1 - r["p"], 6), r["z"]))
        b.sort(key=lambda x: x[0]); TP[c] = ([x[0] for x in b], b, sum(r["z"] for r in rows) / 1.0)
    return TP[c]

def first(c, t):
    T = tape(c)
    if T is None: return None
    ts, b, _ = T
    i = bisect.bisect_left(ts, t + LAG)
    return b[i] if i < len(b) and b[i][0] <= t + 3 * 3600 else None

# ---- entries for all 24 cells
ENT = []; notape = 0
for (city, d), L in mk.items():
    for slot in (60, 36, 18, 6):
        t = L[0]["tend"] - slot * 3600
        fp = {m["c"]: first(m["c"], t) for m in L}
        for v in ("BEST", "AVG"):
            for g in (0.08, 0.15, 0.25):
                cand = []
                for m in L:
                    q = P.get((m["c"], slot, v))
                    if q is None: continue
                    e = fp[m["c"]]
                    if e is None: continue
                    p = e[1]
                    if q - p >= g - 1e-9 and 0.03 <= p <= 0.85: cand.append((q - p, m, e, q))
                cand.sort(key=lambda x: -x[0])
                for gap, m, e, q in cand[:3]:
                    p = e[1]; sh = 10 / p; fee = 0.01 * p * (1 - p) * sh
                    ENT.append(dict(city=city, d=d, slot=slot, v=v, g=g, c=m["c"], p=p, y=m["y"], sh=sh, q=q, size=e[2], ts=e[0],
                                    net=sh * (m["y"] - p) - fee, fee=fee, per="nov" if d >= "2026-11-01" else "tune"))

def clus(L, key=lambda e: (e["city"], e["d"]), num="net"):
    """ratio estimator sum(net)/sum(stake), SE clustered by key (linearised)."""
    if not L: return None
    g = collections.defaultdict(lambda: [0.0, 0.0])
    for e in L: a = g[key(e)]; a[0] += e[num]; a[1] += e.get("stake", 10.0)
    X = [a[0] for a in g.values()]; S = [a[1] for a in g.values()]; n = len(X)
    r = sum(X) / sum(S); sb = sum(S) / n
    if n < 2: return dict(n=len(L), k=n, ret=r, t=float("nan"), net=sum(X), stake=sum(S))
    var = sum((x - r * s) ** 2 for x, s in zip(X, S)) / (n - 1) / n / sb ** 2
    return dict(n=len(L), k=n, ret=r, se=math.sqrt(var), t=r / math.sqrt(var) if var > 0 else float("nan"), net=sum(X), stake=sum(S))

def show(lbl, s):
    if s is None: print(f"{lbl:46s} none"); return
    print(f"{lbl:46s} n={s['n']:4d} clusters={s['k']:4d} stake={s['stake']:7.0f} net={s['net']:+8.1f} ret={100*s['ret']:+6.1f}% t={s['t']:+.2f}")

print("\n== Selected cell AVG g0.15 60h")
for per in ("tune", "nov"):
    L = [e for e in ENT if e["v"] == "AVG" and e["g"] == 0.15 and e["slot"] == 60 and e["per"] == per]
    s = clus(L); show(f"{per} (city-day)", s); show(f"{per} (date)", clus(L, key=lambda e: e["d"]))
    if L: print("   c/share", round(100 * sum(e["net"] for e in L) / sum(e["sh"] for e in L), 2), "avg price", round(sum(e["p"] for e in L) / len(L), 3), "win", round(sum(e["y"] for e in L) / len(L), 3))
print("\n== Pooled variants and cells")
for per in ("tune", "nov"):
    for v in ("BEST", "AVG"):
        for g in (0.08, 0.15, 0.25):
            show(f"{per} {v} g{g} pooled", clus([e for e in ENT if e["v"] == v and e["g"] == g and e["per"] == per]))
cells = {}
for per in ("tune", "nov"):
    for v in ("BEST", "AVG"):
        for g in (0.08, 0.15, 0.25):
            for slot in (60, 36, 18, 6):
                cells[(per, v, g, slot)] = clus([e for e in ENT if e["v"] == v and e["g"] == g and e["per"] == per and e["slot"] == slot])
sel = max(((s["t"], k) for k, s in cells.items() if k[0] == "tune" and s and s["k"] >= 50 and not math.isnan(s["t"])))
print("selection on tune (max city-day t, >=50 city-days):", sel)
print("Nov cells: min/max ret, |t| max:", min(100*s["ret"] for k, s in cells.items() if k[0]=="nov" and s), max(100*s["ret"] for k, s in cells.items() if k[0]=="nov" and s),
      max(abs(s["t"]) for k, s in cells.items() if k[0]=="nov" and s and not math.isnan(s["t"])))
for k, s in sorted(cells.items(), key=lambda kv: str(kv[0])):
    if s and not math.isnan(s["t"]) and abs(s["t"]) > 1.5: show(f"  |t|>1.5 cell {k}", s)

# ---- robustness of the tuning selected cell: drop best day, best 10 markets
print("\n== Robustness")
for per in ("tune", "nov"):
    L = [e for e in ENT if e["v"] == "AVG" and e["g"] == 0.15 and e["slot"] == 60 and e["per"] == per]
    byd = collections.defaultdict(float)
    for e in L: byd[e["d"]] += e["net"]
    bd = max(byd, key=byd.get); show(f"{per} sel. without best day {bd}", clus([e for e in L if e["d"] != bd]))
    top = set(sorted({e["c"] for e in L}, key=lambda c: -sum(e["net"] for e in L if e["c"] == c))[:10])
    show(f"{per} sel. without 10 best markets", clus([e for e in L if e["c"] not in top]))
    # size capped: shares = min(10/p, print size)
    Lc = [dict(e, stake=min(e["sh"], e["size"]) * e["p"], net=min(e["sh"], e["size"]) * (e["y"] - e["p"] - 0.01 * e["p"] * (1 - e["p"]))) for e in L]
    show(f"{per} sel. size-capped to print", clus(Lc))
    # fee at the time: 0.05 before 2026-11-20 23:59, 0 on 10-20..31, else 0.01
    def rate(ts):
        if ts >= 1795219140: return 0.01
        if 1792454400 <= ts < 1793491200: return 0.0
        return 0.05
    La = [dict(e, net=e["sh"] * (e["y"] - e["p"] - rate(e["ts"]) * e["p"] * (1 - e["p"]))) for e in L]
    show(f"{per} sel. fee charged at the time", clus(La))
    show(f"{per} sel. zero fee", clus([dict(e, net=e["sh"] * (e["y"] - e["p"])) for e in L]))

# ---- blind comparison: same slot, same price band, same 3-per-city-day cap, no signal (random buckets)
print("\n== Blind rule (no model): 60h, first print, 0.03-0.85, up to 3 random buckets per city-day; 200 draws")
rng = random.Random(7)
for per in ("tune", "nov"):
    rets = []; allb = []
    for (city, d), L in mk.items():
        if (d >= "2026-11-01") != (per == "nov"): continue
        t = L[0]["tend"] - 60 * 3600
        c = [(m, first(m["c"], t)) for m in L]
        c = [(m, e) for m, e in c if e and 0.03 <= e[1] <= 0.85]
        allb.append((city, d, c))
    for it in range(200):
        En = []
        for city, d, c in allb:
            for m, e in rng.sample(c, min(3, len(c))):
                p = e[1]; sh = 10 / p
                En.append(dict(city=city, d=d, net=sh * (m["y"] - p) - 0.01 * p * (1 - p) * sh))
        rets.append(clus(En)["ret"])
    rets.sort(); print(f"{per}: blind return median {100*rets[100]:+.1f}%, 5-95% [{100*rets[10]:+.1f}, {100*rets[190]:+.1f}] (tapes exist only for model-likely buckets)")

# ---- tape completeness for traded markets
rat = []
for c in {e["c"] for e in ENT}:
    m = next(x for L in mk.values() for x in L if x["c"] == c) if False else None
vol = {m["c"]: m["vol"] for L in mk.values() for m in L}
for c in {e["c"] for e in ENT}:
    if vol[c] >= 50: rat.append(TP[c][2] / vol[c])
rat.sort(); print("\ntape shares / gamma volumeNum on traded markets: n", len(rat), "p1", round(rat[len(rat)//100], 3), "median", round(rat[len(rat)//2], 3), "p99", round(rat[-len(rat)//100], 3))

# ---- compare with author's entries.csv
A = collections.Counter((r["city"], r["date"], r["slot"], r["v"], r["g"], r["c"]) for r in csv.DictReader(open(D + "/entries.csv")))
M_ = collections.Counter((e["city"], e["d"], str(e["slot"]), e["v"], str(e["g"]), e["c"]) for e in ENT)
print("entries mine", sum(M_.values()), "author", sum(A.values()), "only mine", sum((M_ - A).values()), "only author", sum((A - M_).values()))
json.dump([dict(e) for e in ENT], open("/tmp/claude-0/-home-user/05556429-066d-541b-b886-b8da26bcc648/scratchpad/ent_audit.json", "w"))
