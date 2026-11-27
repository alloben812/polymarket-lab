import importlib.util, os, datetime
here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("rc", os.path.join(here, "recompute.py")); rc = importlib.util.module_from_spec(spec); spec.loader.exec_module(rc)
res, legs, nm = rc.run()
out = ["net $/window at $10/leg, conservative, pooled 12 series, by UTC day (weekday): L=0.45 / 0.40 / 0.30 / 0.05"]
for d in range(6):
    a, b = rc.T0 + d * 86400, rc.T0 + (d + 1) * 86400
    row = []
    for L in rc.LV:
        v = [x for (s, l), vv in res.items() if l == L for x in vv if a <= x[0] < b]
        row.append(f"{sum(y for _, y in v)/len(v):+.2f}")
    out.append(f"{datetime.datetime.fromtimestamp(a, datetime.timezone.utc):%Y-%m-%d %a}: " + " / ".join(row) + f"  (n={len(v)})")
print("\n".join(out)); open(os.path.join(here, "byday_out.txt"), "w").write("\n".join(out) + "\n")
