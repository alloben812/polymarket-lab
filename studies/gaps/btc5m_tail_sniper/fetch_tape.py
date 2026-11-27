"""OOS-TAPE download (protocol 3.2): meta + whole-market tapes of BTC 5m windows 2026-08-22 .. 2026-08-31.

Four interleaved sub-grids ((t0/300) % 4 = 0, 2, 1, 3), round-robin over N worker processes. No outcome statistics.
Stops at the hard deadline given in the protocol (19:35 UTC). Usage: python3 fetch_tape.py N
"""
import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from pmlab import updown  # noqa: E402

START = 1787356800  # 2026-08-22 00:00 UTC
END = 1788220800    # 2026-09-01 00:00 UTC
DEADLINE = 1795808100  # 2026-11-27 19:35 UTC
DATA = ROOT / "data" / "gaps_btc5m_tail_sniper"
DATA.mkdir(parents=True, exist_ok=True)
LOG = DATA / "fetch_tape_status.jsonl"
ORDER = {0: 0, 2: 1, 1: 2, 3: 3}


def grid() -> list[int]:
    wins = updown.windows("5m", START, END)
    return sorted(wins, key=lambda t: (ORDER[(t // 300) % 4], t))


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
    with LOG.open("a") as log:
        for i, t0 in enumerate(mine):
            if time.time() > DEADLINE:
                print(k, "deadline", flush=True)
                return
            rec = one(t0)
            log.write(json.dumps(rec) + "\n")
            log.flush()
            if i % 50 == 0:
                print(k, i, len(mine), t0, rec.get("n"), rec.get("why"), time.strftime("%H:%M:%S"), flush=True)


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    done = set()
    if LOG.exists():
        for line in LOG.read_text().splitlines():
            r = json.loads(line)
            if r.get("ok") or r.get("why") in ("no_market", "unresolved"):
                done.add(r["t0"])
    todo = [t for t in grid() if t not in done]
    print("todo", len(todo), flush=True)
    ps = [mp.Process(target=worker, args=(k, n, todo)) for k in range(n)]
    for p in ps:
        p.start()
    for p in ps:
        p.join()
    print("finished", time.strftime("%H:%M:%S"), flush=True)


if __name__ == "__main__":
    main()
