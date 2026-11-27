"""Steps 4-5: price histories (300 s, YES and NO) and whole-market tapes for every bucket. Sequential, cached.
Usage: s5_fetch.py [slug-substring ...]  (no args = everything)"""
import gzip, json, os, sys, time
sys.path.insert(0, "/home/user/polymarket-lab")
sys.path.insert(0, "/home/user/polymarket-lab/studies/gaps/weather_observation_gap")
from pmlab import dataapi
from common import *

os.makedirs(DATA + "/px", exist_ok=True); os.makedirs(DATA + "/tape", exist_ok=True)
M = load_markets()
if len(sys.argv) > 1:
    M = [e for e in M if any(a in e["slug"] for a in sys.argv[1:])]
t_start = time.time(); n = 0; fails = []
for k, e in enumerate(M):
    for b in e["buckets"]:
        c = b["cond"]
        pp = f"{DATA}/px/{c}.json.gz"
        if not os.path.exists(pp):
            try:
                d = {}
                for side in ("yes", "no"):
                    ph = dataapi.prices_history(b[side], e["day0"] - 6 * 3600, e["closed_ts"] + 600, 300)
                    d[side] = [[p["timestamp"], p["price"], p.get("resolution_seconds")] for p in ph]
                with gzip.open(pp + ".tmp", "wt") as f:
                    json.dump(d, f)
                os.replace(pp + ".tmp", pp)
            except Exception as ex:
                fails.append(("px", e["slug"], b["title"], str(ex)[:200])); print("FAIL px", e["slug"], b["title"], str(ex)[:200], flush=True)
        tp = f"{DATA}/tape/{c}.jsonl.gz"
        if not os.path.exists(tp):
            try:
                rows = [{"t": r["timestamp"], "s": r["side"], "o": r["outcome"], "z": float(r["size"]), "p": float(r["price"]), "w": r.get("proxy_wallet"), "h": r.get("transaction_hash")}
                        for r in dataapi.iter_trades(condition=c)]
                rows.sort(key=lambda r: r["t"])
                with gzip.open(tp + ".tmp", "wt") as f:
                    for r in rows:
                        f.write(json.dumps(r) + "\n")
                os.replace(tp + ".tmp", tp)
            except Exception as ex:
                fails.append(("tape", e["slug"], b["title"], str(ex)[:200])); print("FAIL tape", e["slug"], b["title"], str(ex)[:200], flush=True)
        n += 1
    if k % 10 == 0:
        print(k, len(M), e["slug"], round(time.time() - t_start), "s", flush=True)
print("done", n, "markets", round(time.time() - t_start), "s; fails", len(fails))
json.dump(fails, open(DATA + "/fetch_fails.json", "w"))
