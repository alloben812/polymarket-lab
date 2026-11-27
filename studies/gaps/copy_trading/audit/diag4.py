import sys
sys.path.insert(0, ".")
from recompute import *
from diag import ref, agg, k
wk = lambda e: ((e["t"] // 86400 + 4) % 7) in (6, 0)  # Sat=6, Sun=0
import datetime
print("sanity Sat?", datetime.datetime.utcfromtimestamp(1795219200).strftime("%a"), ((1795219200 // 86400 + 4) % 7))
for d in (10, 300):
    rows, _ = evaluate(d)
    for name, f in (("weekend", wk), ("weekday", lambda e: not wk(e))):
        sub = [r for r in rows if f(r["e"])]
        summarize(sub, f"d{d} {name}")
        fs = {k(r["e"]) for r in sub if r["filled"]}
        agg([ref[x] for x in ref if x in fs], f"    REF same filled entries {name}")
agg([r for r in ref.values() if wk(r["e"])], "REF weekend all")
agg([r for r in ref.values() if not wk(r["e"])], "REF weekday all")
