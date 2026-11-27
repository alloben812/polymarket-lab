import sys
sys.path.insert(0, ".")
from recompute import *
bad=0
for e in sample:
    t = L(C + f"tape/{e['c']}.json.gz")
    if not (t["complete"] or (t["oldest"] is not None and t["oldest"] <= e["t"] - 60)): bad += 1
print("entries with tape not reaching tb-60:", bad)
for e in late:
    rz = res.get(e["c"]) or {}; fin = (rz.get("final") or {}).get(e["o"])
    if not (rz.get("resolved") and fin is not None): continue
    tp = L(C + f"tape/{e['c']}.json.gz")["rows"]
    last = max(tp, key=lambda r: r["t"]); px = last["p"] if last["o"] == e["o"] else 1 - last["p"]
    if abs(px - float(fin)) > 0.5: print(e["slug"], e["o"], "final", fin, "last px", round(px,3), "entry px", e["p"], res[e["c"]]["final"], len(tp))
