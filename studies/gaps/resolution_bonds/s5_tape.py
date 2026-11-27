"""Step 5: B-c tape sample (rules 19-20) and download of the tapes. Resumable; one market at a time."""
import gzip
import json
import pickle
import random
import time

from pmlab import dataapi
from common import DATA, OUT, SEED

TAPES = DATA / "tapes"
TAPES.mkdir(exist_ok=True)
CAP = 60000
N = 300


def main():
    panel = pickle.load(open(DATA / "panel.pkl", "rb"))
    claim = pickle.load(open(DATA / "claim.pkl", "rb"))
    fams = sorted({r["fam"] for r in panel})
    early = {f: claim.get(("C-mid", f, "early")) for f in fams}
    elig = {f: s for f, s in early.items() if s and s["n"] >= 30}
    best = [f for f, s in elig.items() if s["net"] > 0]
    rule = "positive early C-mid net, >= 30 entries"
    if len(best) < 2:
        best = [f for f, _ in sorted(elig.items(), key=lambda kv: -kv[1]["net"])[:3]]
        rule = "fallback: top three by early C-mid net among categories with >= 30 entries"
    print("early C-mid by family:", {f: (s["n"], round(100 * s["net"], 2)) for f, s in early.items() if s})
    print("best-looking categories:", best, "|", rule)
    pool = {f: sorted(r["cid"] for r in panel if not r["drop"] and r["claim"] and r["fam"] == f) for f in best}
    rng = random.Random(SEED)
    for f in pool:
        rng.shuffle(pool[f])
    chosen = {f: [] for f in best}
    left = N
    while left > 0 and any(len(chosen[f]) < len(pool[f]) for f in best):
        open_f = [f for f in best if len(chosen[f]) < len(pool[f])]
        q = max(1, left // len(open_f))
        for f in open_f:
            take = pool[f][len(chosen[f]):len(chosen[f]) + min(q, left)]
            chosen[f] += take
            left -= len(take)
            if left <= 0:
                break
    print("pool", {f: len(v) for f, v in pool.items()}, "chosen", {f: len(v) for f, v in chosen.items()})
    sel = {"rule": rule, "best": best, "pool": {f: len(v) for f, v in pool.items()}, "chosen": chosen}
    (DATA / "tape_sample.json").write_text(json.dumps(sel))
    todo = [c for f in best for c in chosen[f]]
    t0 = time.time()
    for i, cid in enumerate(todo):
        path = TAPES / f"{cid}.json.gz"
        if path.exists():
            continue
        rows = []
        for r in dataapi.iter_trades(condition=cid, max_rows=CAP):
            rows.append([r["timestamp"], r["side"], r["token_id"], r["price"], r["size"], r["proxy_wallet"]])
        with gzip.open(path, "wt") as f:
            json.dump({"cid": cid, "capped": len(rows) >= CAP, "rows": rows}, f)
        if i % 20 == 0:
            print(f"tape {i+1}/{len(todo)} rows {len(rows)} {time.time()-t0:.0f}s", flush=True)
    print("done")


if __name__ == "__main__":
    main()
