"""Audit stage 7: taker fee actually charged (activity usdc_size - size*price) against the metadata rate, sample of real fills.
Uses pmlab.dataapi (public, read-only). Usage: python3 a7_fee_check.py"""
import gzip, json, random, sys
sys.path.insert(0, "/home/user/polymarket-lab")
from pmlab import dataapi
ROOT = "/home/user/polymarket-lab"
random.seed(11)
PLAN = {("xrp", "15m"): 14, ("sol", "15m"): 10, ("eth", "15m"): 6, ("eth", "5m"): 6, ("btc", "15m"): 4}
T_START = 1795219200
for (asset, dur), n in PLAN.items():
    step = 300 if dur == "5m" else 900
    out, tries = [], 0
    while len(out) < n and tries < 4 * n:
        tries += 1
        t0 = T_START + step * random.randrange(6 * 86400 // step - 1)
        m = json.load(open(f"{ROOT}/data/updown_meta/{asset}/{dur}/{t0}.json"))
        rows = [json.loads(l) for l in gzip.open(f"{ROOT}/data/tape/{m['condition']}.jsonl.gz", "rt")]
        cand = [r for r in rows if 0.2 < r["p"] < 0.8 and r["z"] >= 20 and r["t"] >= t0]
        if not cand:
            continue
        r = random.choice(cand)
        acts = [a for a in dataapi.iter_activity(r["w"], start=r["t"] - 2, end=r["t"] + 2) if a.get("type") == "TRADE" and a.get("condition_id") == m["condition"]]
        for a in acts:
            sz, pr, usd = float(a["size"]), float(a["price"]), float(a["usdc_size"])
            if abs(sz - r["z"]) > 1e-6 or a["side"] != r["s"]:
                continue
            fee = (usd - sz * pr) if a["side"] == "BUY" else (sz * pr - usd)
            out.append((t0, a["side"], round(sz, 2), round(pr, 4), round(fee, 5), round(fee / (sz * pr * (1 - pr)), 4), len(acts)))
            break
    rates = sorted(x[5] for x in out)
    print(f"{asset}-{dur}: n={len(out)} implied rates {rates}")
    for x in out:
        if abs(x[5] - (0.05 if asset == 'btc' else 0.01)) > 0.0015:
            print("    odd:", x)
