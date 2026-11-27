#!/usr/bin/env python3
"""Fetch resolved outcome per condition via /v2/tokens (10 conditions per call). Appends to a JSON cache."""
import json, sys, time, urllib.request, os
B="https://data-api.polymarket.com/v2"
def get(url,tries=6):
    for i in range(tries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
            with urllib.request.urlopen(req,timeout=60) as r: return json.loads(r.read())
        except Exception as e:
            sys.stderr.write(f"  retry {i+1}: {e}\n"); time.sleep(1.5*(i+1))
    raise SystemExit("failed "+url)
labeled, cache = sys.argv[1], sys.argv[2]
res = json.load(open(cache)) if os.path.exists(cache) else {}
conds = sorted({json.loads(l)['condition_id'] for l in open(labeled)})
todo = [c for c in conds if c not in res]
sys.stderr.write(f"conditions {len(conds)} todo {len(todo)}\n")
for i in range(0, len(todo), 10):
    chunk = todo[i:i+10]
    d = get(B + "/tokens?condition=" + ",".join(chunk))
    for t in d.get("data") or []:
        c = t["condition_id"]
        e = res.setdefault(c, {"slug": t.get("market_slug"), "resolved": t.get("resolved"), "final": {}})
        e["final"][t["outcome"]] = t.get("final_price")
        e["resolved"] = t.get("resolved")
    if (i // 10) % 40 == 0: sys.stderr.write(f"  {i}/{len(todo)}\n")
    time.sleep(0.03)
json.dump(res, open(cache, "w"))
r = [v for c, v in res.items() if c in set(conds)]
print("cached", len(res), "resolved", sum(1 for v in r if v["resolved"]), "of", len(r))
