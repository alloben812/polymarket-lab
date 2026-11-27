"""Step 9 (descriptive, added after s4): denominator for B-d. Markets in which some outcome had a usable mid >= 0.95
in [endDate - 24 h, closedTime), and the share of them in which that outcome did not pay 1, by family and by
period; sports/start split by whether the first >= 0.95 bucket was before the scheduled start (endDate) or after."""
import gzip, json, pickle
from collections import defaultdict
from common import DATA, EPS, OUT
from pmlab.stats import wilson

panel = {r["cid"]: r for r in pickle.load(open(DATA / "panel.pkl", "rb"))}
agg = defaultdict(lambda: [0, 0])
with gzip.open(DATA / "hist.jsonl.gz", "rt") as f:
    for line in f:
        h = json.loads(line)
        r = panel[h["cid"]]
        if r["drop"]:
            continue
        hit = {}  # outcome k -> first time its mid (own or mirrored) >= 0.95
        for k in (0, 1):
            for t, p, rs in h["h"][k]:
                if rs != 300 or t >= r["closed"] or t < r["end"] - 86400:
                    continue
                for kk, pp in ((k, p), (1 - k, 1 - p)):
                    if pp >= 0.95 - EPS and (kk not in hit or t < hit[kk]):
                        hit[kk] = t
        if not hit:
            continue
        lost = any(r["pay"][k] < 1 for k in hit)
        first = min(hit.values())
        rows = [r["fam"], "ALL"]
        if r["sub"]:
            rows.append(r["sub"])
            if r["sub"] == "sports/start":
                rows.append("sports/start, first >= 0.95 before start" if first < r["end"] else "sports/start, first >= 0.95 in play")
        for c in rows:
            for per in ("late" if r["late"] else "early", "both"):
                agg[(c, per)][0] += 1
                agg[(c, per)][1] += lost
L = ["# B-d denominator: how often an outcome seen at >= 0.95 (mid) failed to pay 1", "",
     "category | period | markets with an outcome >= 0.95 | of which it did not pay 1 | % | Wilson 95%", "|".join(["---"] * 6)]
for (c, per), (n, k) in sorted(agg.items()):
    lo, hi = wilson(k, n)
    L.append(f"{c} | {per} | {n} | {k} | {100*k/n:.2f} | {100*lo:.1f}-{100*hi:.1f}")
(OUT / "losers_rate.md").write_text("\n".join(L) + "\n")
print("\n".join(L))
