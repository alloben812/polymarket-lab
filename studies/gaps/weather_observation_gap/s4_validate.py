"""Step 3b: validate the settlement rule: daily max of routine reports -> bucket vs official winner."""
import sys, json, collections, datetime as dt
sys.path.insert(0, "/home/user/polymarket-lab/studies/gaps/weather_observation_gap")
from common import *

M = load_markets()
obs3, obs4 = {}, {}
for e in M:
    if e["icao"] not in obs3:
        obs3[e["icao"]] = load_obs(e["icao"], 3); obs4[e["icao"]] = load_obs(e["icao"], 4)
tot = collections.Counter(); hit = collections.Counter(); misses = []
notg = collections.Counter(); fewrep = []
for e in M:
    rep = [r for r in obs3[e["icao"]] if e["day0"] <= r["t"] < e["day1"] and r["f"] is not None]
    notg[e["icao"]] += sum(1 for r in rep if not r["tg"])
    if len(rep) < 20:
        fewrep.append((e["slug"], len(rep)))
    bk = [(b["lo"], b["hi"]) for b in e["buckets"]]
    win = next(i for i, b in enumerate(e["buckets"]) if b["won"])
    mx = max((r["f"] for r in rep), default=None)
    pred = bucket_index(bk, mx) if mx is not None else None
    month = "Oct" if e["date"] < "2026-11-01" else "Nov"
    for k in ("all", "regime:" + e["regime"], "city:" + e["city"], "month:" + month):
        tot[k] += 1; hit[k] += int(pred == win)
    e["pred"] = pred; e["win"] = win; e["mx"] = mx
    if pred != win:
        sp = [r for r in obs4[e["icao"]] if e["day0"] <= r["t"] < e["day1"] and r["f"] is not None]
        spmx = max((r["f"] for r in sp), default=None)
        top = sorted(rep, key=lambda r: -r["c10"])[:3]
        # neighbours just outside the local day
        edge = [r for r in obs3[e["icao"]] if (e["day0"] - 3700 <= r["t"] < e["day0"] or e["day1"] <= r["t"] < e["day1"] + 3700) and r["f"] is not None]
        misses.append({"slug": e["slug"], "regime": e["regime"], "icao": e["icao"], "n_routine": len(rep), "my_max_f": mx, "my_bucket": e["buckets"][pred]["title"] if pred is not None else None,
                       "official": e["buckets"][win]["title"], "special_max_f": spmx, "n_special": len(sp),
                       "top_routine": [(iso(r["t"]), r["c10"] / 10, r["f"]) for r in top],
                       "special_top": [(iso(r["t"]), r["c10"] / 10, r["f"]) for r in sorted(sp, key=lambda r: -r["c10"])[:2]],
                       "edge_reports": [(iso(r["t"]), r["c10"] / 10, r["f"]) for r in edge]})
for k in sorted(tot):
    print(f"{k:22s} {hit[k]:4d}/{tot[k]:4d} = {hit[k]/tot[k]:.3f}")
print("routine reports without T-group per station:", dict(notg))
print("city-days with < 20 routine reports:", fewrep)
print("misses:", len(misses))
for m in misses:
    print(json.dumps(m))
json.dump({"misses": misses, "few": fewrep}, open(DATA + "/validation.json", "w"), indent=1)
