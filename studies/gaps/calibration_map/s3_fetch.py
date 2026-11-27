"""Step 3: prices-history for token 0 of every sampled market, random order, stop at 19:35 UTC (protocol)."""
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from pmlab import dataapi
from common import DATA, FINE_FROM, read_jsonl

STOP = datetime(2026, 11, 27, 19, 35, tzinfo=timezone.utc).timestamp()
OUTF = DATA / "ph.jsonl"
lock = threading.Lock()


def one(m):
    if time.time() > STOP:
        return "stopped"
    b = 300 if m["anchor"] >= FINE_FROM else 1800
    a = int(m["anchor"])
    try:
        h = dataapi.prices_history(m["tokens"][0], a - 25 * 3600, a, b)
        pts = [[int(x["timestamp"]), float(x["price"])] for x in h]
        rec = {"cid": m["cid"], "b": b, "pts": pts}
        st = "ok"
    except Exception as e:  # noqa
        rec = {"cid": m["cid"], "b": b, "err": str(e)[:200]}
        st = "err"
    with lock:
        with open(OUTF, "a") as f:
            f.write(json.dumps(rec) + "\n")
    return st


def main():
    done = set()
    if OUTF.exists():
        for line in open(OUTF):
            try:
                done.add(json.loads(line)["cid"])
            except Exception:  # noqa
                pass
    todo = [m for m in read_jsonl(DATA / "sample.jsonl.gz") if m["cid"] not in done]
    print("todo", len(todo), "done", len(done), flush=True)
    t0 = time.time()
    n = {"ok": 0, "err": 0, "stopped": 0}
    with ThreadPoolExecutor(2) as ex:
        for i, st in enumerate(ex.map(one, todo)):
            n[st] += 1
            if i % 250 == 0:
                print(i, n, f"{time.time()-t0:.0f}s", flush=True)
    print("final", n, flush=True)


if __name__ == "__main__":
    main()
