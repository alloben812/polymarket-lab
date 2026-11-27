"""H4 (protocol addendum 2): calibration of YES prices at fixed points of the station's local day, all temperature markets in the set."""
import json, bisect, collections, datetime as dt
MK = json.load(open("out/mk.json")); PX = json.load(open("out/px.json"))
SPLIT = dt.datetime(2026, 11, 20, tzinfo=dt.timezone.utc).timestamp()
bands = [0.02, 0.10, 0.20, 0.35, 0.50, 0.65, 0.80, 0.98]
def at(pts, t):
    ts = [p[0] for p in pts]; i = bisect.bisect_right(ts, t) - 1
    return pts[i][1] if i >= 0 and t - pts[i][0] <= 6 * 3600 else None
def tstat(d):
    v = list(d.values()); n = len(v)
    if n < 3: return float("nan")
    mu = sum(v) / n; se = (sum((x - mu) ** 2 for x in v) / (n - 1) / n) ** 0.5
    return mu / se if se else float("nan")
for label, off in (("local midnight -24h", -24), ("local midnight", 0), ("local 09:00", 9), ("local 13:00", 13)):
    print(f"\n== YES price at {label} vs outcome")
    for half in ("all", "<=Nov19", ">=Nov20"):
        tab = collections.defaultdict(lambda: [0, 0.0, 0.0, collections.Counter()])
        for c, pts in PX.items():
            d = MK[c]
            if not pts or (half == "<=Nov19") != (d["est"] < SPLIT) and half != "all": continue
            p = at(pts, d["est"] + off * 3600)
            if p is None or not (bands[0] <= p < bands[-1]): continue
            b = bisect.bisect_right(bands, p) - 1; y = float(d["final"]["Yes"]); a = tab[b]
            a[0] += 1; a[1] += p; a[2] += y; a[3][d["event"]] += (p - y)
        print(f"  [{half}] " + " | ".join(f"{bands[b]:.2f}-{bands[b+1]:.2f}: n={a[0]} px={a[1]/a[0]:.3f} hit={a[2]/a[0]:.3f} over={100*(a[1]-a[2])/a[0]:+.1f}c t={tstat(a[3]):.1f}" for b, a in sorted(tab.items())))
print("\n== H4 rule: at local midnight buy NO where 0.20 <= YES < 0.60, pay (1-YES)+0.02, fee 0.01*p*(1-p), hold to settlement")
for half in ("<=Nov19", ">=Nov20", "all"):
    ev = collections.Counter(); cost = 0.0; n = 0
    for c, pts in PX.items():
        d = MK[c]
        if not pts or (half == "<=Nov19") != (d["est"] < SPLIT) and half != "all": continue
        p = at(pts, d["est"])
        if p is None or not (0.20 <= p < 0.60): continue
        pno = 1 - p + 0.02; y = float(d["final"]["Yes"]); pnl = (1 - y) - pno - 0.01 * pno * (1 - pno)
        ev[d["event"]] += pnl; cost += pno; n += 1
    print(f"  [{half}] markets {n}, events {len(ev)}, profit per share-set ${sum(ev.values()):.1f} on cost ${cost:.1f} = {100*sum(ev.values())/max(cost,1e-9):+.2f}% ; t by event {tstat(ev):.2f}")
