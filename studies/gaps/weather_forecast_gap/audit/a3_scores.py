"""Audit: market vs model log score (F2) from the raw price histories, tape coverage, and where rule buys win.
Run: python3 -I a3_scores.py"""
import csv, gzip, json, math, bisect, collections, os, statistics
D = "/home/user/polymarket-lab/data/gaps_weather_fc"; S = "/tmp/claude-0/-home-user/05556429-066d-541b-b886-b8da26bcc648/scratchpad"
MK = collections.defaultdict(list)
for r in csv.DictReader(open(D + "/markets.csv")): MK[(r["city"], r["date"])].append(r)
W = {r["condition"]: float(r["yes_final"]) for r in csv.DictReader(open(D + "/winners.csv"))}
P = {(r["condition"], int(r["slot"]), r["version"]): float(r["prob"]) for r in csv.DictReader(open(D + "/model_probs.csv"))}
PX = {}; res = collections.Counter()
for line in gzip.open(D + "/prices.jsonl.gz", "rt"):
    try: o = json.loads(line)
    except ValueError: res["bad line"] += 1; continue
    PX[o["c"]] = ([p[0] for p in o["pts"]], [p[1] for p in o["pts"]]); res[o["res"]] += 1
print("price histories", len(PX), dict(res))
def px(c, t, lagback=0):
    if c not in PX: return None
    ts, ps = PX[c]; i = bisect.bisect_right(ts, t - lagback) - 1
    return ps[i] if i >= 0 and t - ts[i] <= 6 * 3600 else None
def mse(x):
    n = len(x); m = sum(x) / n; s = statistics.stdev(x) / math.sqrt(n); return m, m / s
for lagback in (0, 1800):
    print(f"\nNovember log score (floor 0.01), market price = last history point <= t - {lagback}s; diff = model AVG - market (positive = market better)")
    for slot in (60, 36, 18, 6):
        dl = []; lm = []; lk = []; byd = collections.defaultdict(list); sums = []
        for (city, d), L in MK.items():
            if d < "2026-11-01": continue
            t = int(L[0]["t_end"]) - slot * 3600
            pp = [px(m["condition"], t, lagback) for m in L]
            if any(p is None for p in pp): continue
            s = sum(pp); w = [i for i, m in enumerate(L) if W[m["condition"]] == 1.0][0]
            a = -math.log(max(pp[w] / s, 0.01)); b = -math.log(max(P[(L[w]["condition"], slot, "AVG")], 0.01))
            lk.append(a); lm.append(b); dl.append(b - a); byd[d].append(b - a); sums.append(s)
        m, t1 = mse(dl); _, t2 = mse([statistics.mean(v) for v in byd.values()])
        print(f"  {slot:2d}h city-days {len(dl)} model {statistics.mean(lm):.3f} market {statistics.mean(lk):.3f} diff {m:+.3f} t(city-day) {t1:.1f} t(date) {t2:.1f} mean price sum {statistics.mean(sums):.2f}")
# tape coverage of rule-reachable buckets
need = {c for (c, s, v), p in P.items() if p >= 0.11}
have = {c for c in need if os.path.exists(f"/home/user/polymarket-lab/data/tape/{c}.jsonl.gz")}
print(f"\nbuckets with model prob >= 0.11 somewhere: {len(need)}; with tape file: {len(have)}")
# where rule buys win (unique bucket x slot, all variants together), from my own entries (a1)
E = json.load(open(S + "/ent_audit.json")); u = {}
for e in E: u[(e["c"], e["slot"])] = e
for per in ("tune", "nov"):
    L = [e for e in u.values() if e["per"] == per]
    print(f"{per}: unique bought bucket-slots {len(L)}; mean model prob {statistics.mean(e['q'] for e in L):.3f}; mean price {statistics.mean(e['p'] for e in L):.3f}; win rate {statistics.mean(e['y'] for e in L):.3f}")
