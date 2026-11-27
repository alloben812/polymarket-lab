"""Fetch 30-min YES price history around the local day for every temperature market in out/mk.json -> out/px.json {cond: [[t,p],...]}"""
import json, sys, time
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, "/home/user/polymarket-lab")
from pmlab import dataapi
MK = json.load(open("out/mk.json")); M = json.load(open("out/markets.json"))
todo = [(c, M[c]["res"]["tokens"]["Yes"], d["est"]) for c, d in MK.items() if d["ok"] and d["kind"] == "hi" and d["final"] is not None and M[c].get("res")]
def one(x):
    c, tok, est = x
    for a in range(3):
        try:
            pts = dataapi.prices_history(tok, est - 50 * 3600, est + 30 * 3600, 1800)
            return c, [[q.get("timestamp") or q.get("t"), q.get("price") or q.get("p")] for q in pts], (pts[0] if pts else None)
        except Exception as e:
            err = str(e)[:100]; time.sleep(2)
    return c, None, err
out = {}; n = 0
with ThreadPoolExecutor(4) as ex:
    for c, pts, sample in ex.map(one, todo):
        out[c] = pts; n += 1
        if n in (1, 2) or n % 500 == 0: print(n, len(todo), sample, flush=True)
json.dump(out, open("out/px.json", "w")); print("done", sum(1 for v in out.values() if v))
