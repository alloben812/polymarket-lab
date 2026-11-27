"""Audit step 5: W4 (who takes the cheap side and how fast), W3 lag and the rule from t_public, day-bootstrap of
the hindsight reporting line, secondsDelay on class A moneylines."""
import sys, json, gzip, statistics, random, collections, datetime as dt, math
sys.path.insert(0, "/home/user/polymarket-lab/studies/gaps/tennis_walkover/audit")
import a4_hindsight as H
from a3_rule import rule, E
A, TF, S, cut = H.A, H.TF, H.S, H.cut
# --- W4: buyable < 0.45 within [t_first, t_first + 1800] over all markets
pr_all = []; firsts = collections.Counter(); nev = 0
for r in A:
    t0 = TF[r["slug"]]
    if t0 is None: continue
    ps = [(x[0] - t0, x[3], x[4], x[5]) for m, pr, ref in S[r["slug"]].values() for x in pr if 0 <= x[0] - t0 <= 1800 and x[3] < 0.45 - E]
    if not ps: continue
    nev += 1; pr_all += ps
    tmin = min(p[0] for p in ps)
    for w in {p[3] for p in ps if p[0] == tmin}: firsts[w] += 1
usd = sum(p[1] * p[2] for p in pr_all); usd2 = sum(p[1] * p[2] for p in pr_all if p[0] <= 2)
byw = collections.Counter()
for p in pr_all: byw[p[3]] += p[1] * p[2]
print(f"W4: events {nev}, dollars {usd:,.0f}, share in first 2 s {usd2/usd:.3f}, takers {len(byw)}, top3 {sum(v for _,v in byw.most_common(3))/usd:.2f}, distinct first wallets {len(firsts)}")
# --- W3
pub = [p for p in json.load(open("/home/user/polymarket-lab/studies/gaps/tennis_walkover/out/public_times.json")) if p.get("t_public") and p.get("precision") in ("second", "minute")]
lags = [TF[p["slug"]] - p["t_public"] for p in pub if TF.get(p["slug"]) is not None]
print("W3: notices", len(pub), "with t_first", len(lags), "median t_first - t_public", statistics.median(lags), "book first in", sum(1 for x in lags if x < 0))
prec = collections.Counter(p["precision"] for p in pub); src = collections.Counter(str(p.get("source"))[:20] for p in pub); print("  precision", dict(prec), "sources", dict(src))
bys = {r["slug"]: r for r in A}
for d in (10, 60, 300, 900):
    nets = []
    for p in pub:
        streams = [(pr, m["fin"]) for m, pr, ref in S[p["slug"]].values() if pr]
        n, c, sh, f = rule(streams, [p["t_public"] + d]); nets.append((n, sh > 0, p["slug"]))
    v = [x[0] for x in nets]; se = statistics.stdev(v) / math.sqrt(len(v))
    print(f"  from t_public d={d}: net {sum(v):.0f}, fills {sum(x[1] for x in nets)}, t {statistics.mean(v)/se:.2f}, best event {max(v):.0f}, w/o best {sum(v)-max(v):.0f}")
# --- day bootstrap of the hindsight reporting d=10 line
rows = [x for x in H.run(10) if x[0]["closed"] >= cut]
byday = collections.defaultdict(float)
for x in rows: byday[dt.datetime.fromtimestamp(x[0]["closed"], dt.timezone.utc).date()] += x[1]
dv = list(byday.values()); random.seed(1)
bs = sorted(sum(random.choice(dv) for _ in dv) for _ in range(5000))
print(f"hindsight REPORT d=10 by-day bootstrap: days {len(dv)}, total {sum(dv):.0f}, 95% [{bs[125]:.0f}, {bs[4875]:.0f}], days positive {sum(1 for v in dv if v>0)}, negative {sum(1 for v in dv if v<0)}")
# --- fee spot check on three filled events (hand formula)
k = 0
for x in rows:
    if x[3] > 0 and k < 3:
        k += 1; print(f"  {x[0]['slug']}: shares {x[3]:.1f} cost {x[2]:.2f} net {x[1]:.2f} -> avg p {x[2]/x[3]:.3f}, payoff at 0.5 {0.5*x[3]:.2f}, implied fee {0.5*x[3]-x[2]-x[1]:.3f} vs 0.05*p*(1-p)*shares at avg p {0.05*(x[2]/x[3])*(1-x[2]/x[3])*x[3]:.3f}")
# --- secondsDelay
sd = collections.Counter()
for line in gzip.open("/home/user/polymarket-lab/data/gaps_tennis_wo/events.jsonl.gz", "rt"):
    e = json.loads(line)
    if e["slug"] in bys:
        for m in e["markets"]:
            if m["conditionId"] == bys[e["slug"]]["cid"]: sd[m.get("secondsDelay")] += 1
print("secondsDelay on class A moneylines", dict(sd))
