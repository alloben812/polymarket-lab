"""Step 3: whole-market tapes of candidate markets, newest first, stopped 25 hours before the earliest candidate.
(The API ignores start/end for condition tapes and its cursor is signed, so the walk always starts at the end.)"""
import gzip, json, sys, time
from pmlab import dataapi
from common import *

MAX_ROWS = 600_000


def main():
    cands = json.load(open(OUT / "candidates.json"))
    first = {}
    for c in cands:
        first[c["c"]] = min(first.get(c["c"], 10**12), c["T_pre"])
    todo = sorted(first)
    t_start = time.time()
    for i, cid in enumerate(todo):
        path = TAPES / f"{cid}.jsonl.gz"
        meta = TAPES / f"{cid}.meta.json"
        stop = first[cid] - 90000          # 25 h before the earliest candidate (Amendment 1 needs 24 h)
        if path.exists() and meta.exists() and json.load(open(meta))["stop"] <= stop:
            continue
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
        except Exception as e:  # noqa: BLE001
            print("ERR", cid, str(e)[:200], file=sys.stderr, flush=True)
            continue
        rows.reverse()                      # oldest first, API order kept inside one block
        tmp = path.with_suffix(".tmp")
        with gzip.open(tmp, "wt") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        tmp.replace(path)
        json.dump({"stop": stop, "rows": len(rows), "reached_stop": complete}, open(meta, "w"))
        if i % 20 == 0:
            print(i, len(todo), len(rows), round(time.time() - t_start), file=sys.stderr, flush=True)
    print("done", len(todo))


if __name__ == "__main__":
    main()
