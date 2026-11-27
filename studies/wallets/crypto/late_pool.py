"""Population check of 'bid for the near-certain outcome late / after the end' on every cached up/down tape
(not one account): what did the RESTING BUYER earn when a taker sold an outcome at >= 0.95?  Clusters = markets."""
import json, gzip, collections, glob, os
from pmlab import stats
from pmlab.http import ROOT
rows = collections.defaultdict(lambda: collections.defaultdict(lambda: [0.0, 0.0, 0.0, 0]))   # (series, bucket) -> market -> [pnl, shares, usd, lost]
nm = collections.Counter(); span = {}
for f in glob.glob(str(ROOT / "data" / "updown_meta" / "*" / "*" / "*.json")):
    m = json.load(open(f))
    tp = ROOT / "data" / "tape" / f"{m['condition']}.jsonl.gz"
    if m.get("up_won") is None or not tp.exists(): continue
    ser = f"{m['asset']}-{m['dur']}"; nm[ser] += 1; t1 = m["t1"]
    span[ser] = (min(span.get(ser, (9e18, 0))[0], m["t0"]), max(span.get(ser, (9e18, 0))[1], m["t0"]))
    win = "Up" if m["up_won"] else "Down"
    for line in gzip.open(tp, "rt"):
        r = json.loads(line)
        # resting buyer of outcome X at price p: taker SOLD X at p, or taker BOUGHT the other outcome at 1-p
        if r["s"] == "SELL": o, p = r["o"], r["p"]
        else: o, p = ("Down" if r["o"] == "Up" else "Up"), 1 - r["p"]
        if p < 0.95 or p >= 1: continue
        left = t1 - (r["t"] - 3)
        b = "a 120-300s left" if left > 120 else "b 60-120s" if left > 60 else "c 30-60s" if left > 30 else "d 10-30s" if left > 10 else "e 0-10s" if left > 0 else "f after end 0-30s" if left > -30 else "g after end >30s"
        pb = "0.95-0.99" if p < 0.99 else "0.99-1.00"
        a = rows[(ser, pb, b)][m["condition"]]
        won = 1.0 if o == win else 0.0
        a[0] += r["z"] * (won - p); a[1] += r["z"]; a[2] += r["z"] * p; a[3] += 0 if won else 1
print("markets with tape:", dict(nm)); print("span (window starts, epoch):", span)
print(f"{'series':8} {'price':10} {'when':20} {'mkts':>5} {'usd':>11} {'c/share':>8} {'se':>6} {'t':>6} {'lost mkts':>9} {'pnl$':>9} {'pnl % of usd':>12}")
for k in sorted(rows):
    v = rows[k]; num = [x[0] for x in v.values()]; den = [x[1] for x in v.values()]
    e, se, t = stats.ratio_cluster(num, den); usd = sum(x[2] for x in v.values())
    if usd < 2000: continue
    print(f"{k[0]:8} {k[1]:10} {k[2]:20} {len(v):5} {usd:11,.0f} {100*e:8.3f} {100*se if se==se else float('nan'):6.3f} {t if t==t else float('nan'):6.2f} {sum(1 for x in v.values() if x[3]):9} {sum(num):9,.0f} {100*sum(num)/usd:12.3f}")
