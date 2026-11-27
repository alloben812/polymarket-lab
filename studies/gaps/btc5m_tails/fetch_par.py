"""Parallel driver for fetch.py (plumbing only, added by the second researcher to fit the time budget).

Same grid, same download order, same per-window record as fetch.py; windows still missing are split round-robin
over N worker processes (each process has its own pmlab.http throttle). No outcome statistics are computed.
Usage: python3 studies/gaps/btc5m_tails/fetch_par.py N
"""
import json
import multiprocessing as mp
import sys
import time

import fetch
from pmlab import updown


def one(t0: int) -> dict:
    rec = {"t0": t0, "ok": False}
    try:
        m = updown.load_market("btc", "5m", t0)
        if m is None or m.get("up_won") is None or not m.get("condition"):
            rec["why"] = "no_market" if m is None else "unresolved"
        else:
            try:
                rows = updown.tape(m["condition"])
            except (EOFError, OSError, ValueError) as e:
                rec["cache_err"] = repr(e)[:120]
                time.sleep(2)
                rows = updown.tape(m["condition"], cache=False)
            rec.update(ok=True, n=len(rows), condition=m["condition"])
    except Exception as e:  # noqa: BLE001
        rec["why"] = repr(e)[:200]
    return rec


def worker(k: int, n: int, todo: list[int]) -> None:
    mine = todo[k::n]
    t_start = time.time()
    with fetch.LOG.open("a") as log:
        for i, t0 in enumerate(mine):
            rec = one(t0)
            log.write(json.dumps(rec) + "\n")
            log.flush()
            if i % 100 == 0:
                print("w", k, i, len(mine), t0, rec.get("n"), rec.get("why"), f"{time.time() - t_start:.0f}s", flush=True)
    print("w", k, "done", f"{time.time() - t_start:.0f}s", flush=True)


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    done = {}
    for line in fetch.LOG.read_text().splitlines():
        r = json.loads(line)
        done[r["t0"]] = r
    todo = [t for t in fetch.grid() if not (t in done and done[t].get("ok"))]
    # keep the interleaved order: the round-robin split preserves it, so prefixes stay even sub-grids
    print("todo", len(todo), flush=True)
    ps = [mp.Process(target=worker, args=(k, n, todo)) for k in range(n)]
    for p in ps:
        p.start()
    for p in ps:
        p.join()


if __name__ == "__main__":
    main()
