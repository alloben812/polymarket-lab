"""Time split of late_pool.py for the buckets that looked positive (written after seeing late_pool.txt; tune = 21-24 Nov, report = 25-26 Nov).
Rule fixed here before running: resting buyer at >= 0.99, fill matched in the last 30 s of the window or after its end."""
import json, gzip, collections, glob, statistics
from pmlab import stats
from pmlab.http import ROOT
T_REPORT = 1795564800
agg = collections.defaultdict(lambda: collections.defaultdict(lambda: [0.0, 0.0, 0.0, 0])); sizes = collections.defaultdict(list); nmk = collections.Counter()
for f in glob.glob(str(ROOT / "data" / "updown_meta" / "*" / "*" / "*.json")):
    m = json.load(open(f)); tp = ROOT / "data" / "tape" / f"{m['condition']}.jsonl.gz"
    if m.get("up_won") is None or not tp.exists(): continue
    ser = f"{m['asset']}-{m['dur']}"; per = "tune 21-24" if m["t0"] < T_REPORT else "report 25-26"; win = "Up" if m["up_won"] else "Down"; nmk[(ser, per)] += 1
    for line in gzip.open(tp, "rt"):
        r = json.loads(line)
        if r["s"] == "SELL": o, p = r["o"], r["p"]
        else: o, p = ("Down" if r["o"] == "Up" else "Up"), 1 - r["p"]
        if p < 0.99 or p >= 1: continue
        left = m["t1"] - (r["t"] - 3)
        if left > 30: continue
        b = "last 30 s" if left > 0 else "after end"
        a = agg[(ser, b, per)][m["condition"]]; won = 1.0 if o == win else 0.0
        a[0] += r["z"] * (won - p); a[1] += r["z"]; a[2] += r["z"] * p; a[3] += 0 if won else 1
        sizes[(ser, b)].append(r["z"] * p)
print(f"{'series':8} {'when':10} {'period':13} {'mkts in period':>14} {'mkts w/ fills':>13} {'usd':>11} {'c/share':>8} {'se':>6} {'lost mkts':>9} {'pnl$':>8} {'pnl$/day':>8}")
for k in sorted(agg):
    v = agg[k]; e, se, t = stats.ratio_cluster([x[0] for x in v.values()], [x[1] for x in v.values()]); usd = sum(x[2] for x in v.values()); days = 4 if k[2].startswith("tune") else 2
    print(f"{k[0]:8} {k[1]:10} {k[2]:13} {nmk[(k[0], k[2])]:14} {len(v):13} {usd:11,.0f} {100*e:8.3f} {100*se if se==se else float('nan'):6.3f} {sum(1 for x in v.values() if x[3]):9} {sum(x[0] for x in v.values()):8,.0f} {sum(x[0] for x in v.values())/days:8,.0f}")
print("\nfill size (usd) of the taker sells that hit those bids:")
for k in sorted(sizes):
    s = sorted(sizes[k]); print(f"   {k[0]:8} {k[1]:10} n={len(s):6} median {statistics.median(s):8.1f}  p25 {s[len(s)//4]:7.1f}  p75 {s[3*len(s)//4]:8.1f}  share of usd in fills under $50: {sum(x for x in s if x < 50)/sum(s):.3f}")
