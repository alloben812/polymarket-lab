"""Calibrate the real weather taker-fee rate per day: API daily fee charge / sum(shares*p*(1-p)) of the wallet's taker fills that day."""
import json, sys, collections, datetime as dt
sys.path.insert(0, "/home/user/polymarket-lab")
from pmlab import dataapi, gamma
F = json.load(open("out/fills.json")); M = json.load(open("out/markets.json"))
for a in ["WrongBy1Degree", "HighTempTation", "haiwenxiang"]:
    _, w = gamma.resolve_profile(a)
    pts = dataapi.user_pnl(w, "all", "1d")
    day = lambda ts: dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%m-%d")
    cum = {day(q["timestamp"]): q.get("fees") or 0 for q in pts}
    keys = sorted(cum); fee_day = {k: cum[k] - cum[keys[i - 1]] for i, k in enumerate(keys) if i}
    base = collections.Counter()
    for r in F[a]:
        if r["role"] == "T" and "temperature" in (r["slug"] or ""):
            base[day(r["timestamp"])] += r["size"] * r["price"] * (1 - r["price"])
    print(a, "sample point keys:", list(pts[-1].keys()))
    print("  day: api_fee / base = implied rate   | ", "  ".join(f"{k}:{-fee_day.get(k,0):.1f}/{base[k]:.0f}={(-fee_day.get(k,0)/base[k] if base[k] else 0):.3f}" for k in sorted(base)))
