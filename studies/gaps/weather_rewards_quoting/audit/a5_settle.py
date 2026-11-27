"""Audit step 5: settlement cross-check. (a) gamma outcomePrices for 40 random markets vs meta final_yes;
(b) each event must have exactly one YES winner among its markets in meta (only when all buckets are in the study)."""
import json, random, collections, sys
sys.path.insert(0, "/home/user/polymarket-lab")
from pmlab.http import get_json
from pmlab.gamma import jfield
meta = json.load(open("/home/user/polymarket-lab/data/gaps_weather_rewards/meta.json"))
random.seed(7)
pick = random.sample(sorted(meta), 40)
bad = 0
for c in pick:
    g = get_json("https://gamma-api.polymarket.com/markets", {"slug": meta[c]["slug"], "closed": "true"})
    g = g[0] if isinstance(g, list) and g else {}
    op = jfield(g.get("outcomePrices")); oc = jfield(g.get("outcomes"))
    y = float(op[oc.index("Yes")]) if op and oc else None
    if y is None or abs(y - float(meta[c]["final_yes"])) > 1e-6:
        bad += 1; print("MISMATCH", meta[c]["slug"], y, meta[c]["final_yes"])
print("gamma check", len(pick), "mismatches", bad)
ev = collections.defaultdict(list)
for c, v in meta.items():
    ev[v["event"]].append(float(v["final_yes"]))
cnt = collections.Counter(sum(x) for x in ev.values())
print("events", len(ev), "YES winners per event (study markets only):", dict(cnt))
