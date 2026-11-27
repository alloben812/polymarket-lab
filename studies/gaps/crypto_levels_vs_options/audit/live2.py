import json, gzip, random, time
import numpy as np, pandas as pd
from pathlib import Path
from pmlab.http import get_json
from pmlab import dataapi, gamma
D = Path("/home/user/polymarket-lab/data/gaps_levels")
iso = lambda t: time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(t))
uni = {u["cond"]: u for u in json.load(open(D / "universe.json")) if u["grp"] == "euro"}
E = pd.read_parquet("my_entries.parquet")
tv = E[(E.g == 0.05) & (E.band == "48h-7d") & E.conf_w0]
rep = sorted(tv[tv.period == "report"].cond.unique()); tun = sorted(tv[tv.period == "tune"].cond.unique())
rng = random.Random(7)
others = rng.sample(sorted(set(uni) - set(rep) - set(tun)), 20)
print("re-download: report-confirmed markets", len(rep), "tune-confirmed", len(tun), "random others", len(others))
# A. raw trade row: fields
r = get_json("https://data-api.polymarket.com/v2/trades", {"condition": rep[0], "limit": 3})
print("raw trade row keys:", sorted(r["data"][0].keys())); print(r["data"][0])
# B. fresh tapes and price histories vs cache
bad_t = bad_p = 0; tot_rows = 0; diffs = []
for c in rep + tun + others:
    u = uni[c]
    fresh = sorted((x["timestamp"], x["side"], x["outcome"], float(x["size"]), float(x["price"])) for x in dataapi.iter_trades(condition=c))
    cached = sorted(tuple(x) for x in json.load(gzip.open(D / "tape" / f"{c}.json.gz", "rt"))) if (D / "tape" / f"{c}.json.gz").exists() else None
    tot_rows += len(fresh)
    if cached is not None and fresh != cached: bad_t += 1; diffs.append(("tape", u["slug"], len(fresh), len(cached)))
    ph = dataapi.prices_history(u["yes"], u["start"] - 600, u["T"] + 600, 300)
    f2 = sorted({(x["timestamp"], x["resolution_seconds"]): (x["timestamp"], x["price"], x["resolution_seconds"]) for x in ph}.values())
    c2 = sorted(tuple(x) for x in json.load(open(D / "ph" / f"{c}.json")))
    if f2 != c2: bad_p += 1; diffs.append(("ph", u["slug"], len(f2), len(c2)))
    notional = sum(z * p for _, _, _, z, p in fresh); sh = sum(z for _, _, _, z, p in fresh)
    if c in rep[:6]: print(f"  {u['slug']}: tape rows {len(fresh)} first {iso(fresh[0][0])} last {iso(fresh[-1][0])} start {iso(u['start'])} T {iso(u['T'])} tape$ {notional:.0f} shares {sh:.0f} volumeNum {u['vol']:.0f}; ph points {len(f2)}")
print("markets re-downloaded", len(rep + tun + others), "tape rows", tot_rows, "| tapes differing from cache", bad_t, "| price histories differing", bad_p); print(diffs[:10])
# C. bucket label alignment: 60 s vs 300 s series for report markets that resolved 25-26 Nov (1-minute data kept >= 7 days)
late = [c for c in rep if uni[c]["date"] >= "2026-11-25"][:3]
for c in late:
    u = uni[c]; a = u["T"] - 3 * 86400; b = u["T"] - 2 * 86400
    p5 = {x["timestamp"]: x["price"] for x in dataapi.prices_history(u["yes"], a, b, 300)}
    p1 = {x["timestamp"]: x["price"] for x in dataapi.prices_history(u["yes"], a - 600, b + 600, 60)}
    out = {}
    for off in (-300, -240, -60, 0, 60, 240, 300):
        d = [abs(p5[t] - p1[t + off]) for t in p5 if t + off in p1]
        out[off] = (round(float(np.mean(d)), 5), len(d)) if d else None
    print(u["slug"], "5m pts", len(p5), "1m pts", len(p1), "mean |p5(t) - p1(t+off)|:", out)
    json.dump({"p5": p5, "p1": p1}, open(f"align_{c[:10]}.json", "w"))
# D. rules text of one market
m = get_json("https://gamma-api.polymarket.com/markets", {"slug": uni[rep[0]]["slug"], "closed": "true"})[0]
print(m["description"][:900]); print({k: m.get(k) for k in ("startDate", "endDate", "closedTime", "feeSchedule", "feeType", "feesEnabled", "volumeNum", "orderPriceMinTickSize", "orderMinSize", "umaResolutionStatus", "createdAt", "acceptingOrdersTimestamp")})
