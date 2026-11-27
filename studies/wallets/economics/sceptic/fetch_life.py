"""Fetch whole-life fills (with maker/taker role) and activity rows for a wallet; cache as pickle in data/econ_tapes/sceptic_*."""
import sys, pickle, os, time, json, collections
from pmlab import wallet as W, dataapi
from pmlab.http import get_json
label, addr, start = sys.argv[1], sys.argv[2], int(sys.argv[3])
END = 1795824000  # 2026-11-28 00:00 UTC
out = f"/home/user/polymarket-lab/data/econ_tapes/sceptic_{label}.pkl"
if not os.path.exists(out):
    fills, trunc = W.fetch_fills(addr, start, END, 200000)
    act = list(dataapi.iter_activity(addr, start=start, end=END))
    try: pos = get_json(dataapi.DATA + "/positions", {"user": addr, "limit": 1000})
    except Exception as e: pos = {"error": str(e)}
    pickle.dump({"fills": fills, "act": act, "pos": pos, "trunc": trunc}, open(out, "wb"))
d = pickle.load(open(out, "rb"))
print(label, "fills", len(d["fills"]), "trunc", d["trunc"], "activity rows", len(d["act"]), collections.Counter(r.get("type") for r in d["act"]))
print("activity sample", json.dumps(d["act"][0])[:600])
for t in ("REDEEM", "REWARD", "MAKER_REBATE"):
    r = next((r for r in d["act"] if r.get("type") == t), None)
    if r: print(t, json.dumps(r)[:500])
p = d["pos"]; print("positions:", type(p), (list(p.keys()) if isinstance(p, dict) else len(p)))
rows = p.get("data") if isinstance(p, dict) else p
if rows: print(len(rows), json.dumps(rows[0])[:900]); print(p.get("pagination"))
