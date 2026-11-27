"""Exploratory in-window calibration for late updown-15m (200 random markets, 300 s buckets). Not pre-registered; descriptive."""
import json, collections, math
rs = [json.loads(l) for l in open("inwindow.jsonl")]
def ev(off, lag):
    out = []
    for r in rs:
        o = r["anchor"] - off
        c = [(t, p) for t, p in r["pts"] if t <= o - lag]
        if not c: continue
        t, p0 = c[-1]
        if t < o - 900: continue
        fav = 0 if p0 >= 0.5 else 1
        pf = max(p0, 1 - p0)
        if pf > 0.995: continue
        w = r["win"][fav]
        s = 0.01 if 0.10 <= pf <= 0.90 else 0.005
        e = pf + s
        out.append((pf, w, w - pf, w - e - r["rate"] * e * (1 - e)))
    return out
for off, name in ((600, "5 min into window (10 min left)"), (300, "10 min into window (5 min left)")):
    for lag in (0, 300):
        o = ev(off, lag)
        print(name, "lag", lag, "n", len(o), "mean fav price %.3f" % (sum(x[0] for x in o)/len(o)), "win %.3f" % (sum(x[1] for x in o)/len(o)),
              "gross %+.2fc" % (100*sum(x[2] for x in o)/len(o)), "net %+.2fc" % (100*sum(x[3] for x in o)/len(o)))
        for lo, hi in ((0.5, 0.7), (0.7, 0.9), (0.9, 0.995)):
            s = [x for x in o if lo <= x[0] < hi]
            if s: print("   ", lo, hi, "n", len(s), "price %.3f win %.3f gross %+.1fc net %+.1fc" % (sum(x[0] for x in s)/len(s), sum(x[1] for x in s)/len(s), 100*sum(x[2] for x in s)/len(s), 100*sum(x[3] for x in s)/len(s)))
