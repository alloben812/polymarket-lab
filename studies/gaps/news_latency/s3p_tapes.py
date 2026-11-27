"""Step 3 in parallel (Amendment 2): same per-market logic as s3_tapes.py (stop 25 h before the earliest candidate,
600,000-row cap), 3 workers, hard deadline. Usage: s3p_tapes.py <deadline epoch>"""
import gzip, json, sys, time
from concurrent.futures import ThreadPoolExecutor
from pmlab import dataapi
from common import *
from s3_tapes import MAX_ROWS


def one(cid, stop, deadline):
    path = TAPES / f"{cid}.jsonl.gz"
    meta = TAPES / f"{cid}.meta.json"
    if path.exists() and meta.exists() and json.load(open(meta))["stop"] <= stop:
        return "cached"
    if time.time() > deadline:
        return "deadline"
    rows, complete = [], True
    try:
        for r in dataapi.iter_trades(condition=cid):
            if r["timestamp"] < stop:
                break
            rows.append({"t": r["timestamp"], "s": r["side"], "i": r["outcome_index"], "z": float(r["size"]),
                         "p": float(r["price"]), "w": r.get("proxy_wallet"), "x": (r.get("transaction_hash") or "")[:18]})
            if len(rows) >= MAX_ROWS:
                complete = False
                break
            if time.time() > deadline + 600:      # one market may not run more than 10 min past the deadline
                return "deadline"
    except Exception as e:  # noqa: BLE001
        print("ERR", cid, str(e)[:200], file=sys.stderr, flush=True)
        return "error"
    rows.reverse()
    tmp = path.with_suffix(".tmp")
    with gzip.open(tmp, "wt") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    tmp.replace(path)
    json.dump({"stop": stop, "rows": len(rows), "reached_stop": complete}, open(meta, "w"))
    return "ok" if complete else "truncated"


def main():
    deadline = float(sys.argv[1])
    cands = json.load(open(OUT / "candidates.json"))
    first = {}
    for c in cands:
        first[c["c"]] = min(first.get(c["c"], 10**12), c["T_pre"])
    todo = sorted(first)
    t0 = time.time()
    res = {}
    with ThreadPoolExecutor(3) as ex:
        futs = {cid: ex.submit(one, cid, first[cid] - 90000, deadline) for cid in todo}
        for i, (cid, f) in enumerate(futs.items()):
            res[cid] = f.result()
            if i % 20 == 0:
                print(i, len(todo), round(time.time() - t0), flush=True)
    import collections
    print("done", collections.Counter(res.values()))
    json.dump(res, open(DATA / "s3p_status.json", "w"))


if __name__ == "__main__":
    main()
