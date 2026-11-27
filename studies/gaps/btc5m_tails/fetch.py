"""Step 1: metadata + whole-market tapes for every 4th BTC 5m window, 2026-09-01 .. 2026-11-26 (UTC).

Sequential, throttled by pmlab.http, resumable. No outcome statistics are computed here.
Order of download is interleaved (t0 % 4800 == 0 first, then 2400, 1200, 3600) so that any prefix of the
download is itself an evenly spaced sample of the period.
Usage: python3 studies/gaps/btc5m_tails/fetch.py [max_windows]
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from pmlab import updown  # noqa: E402

START = 1788220800  # 2026-09-01 00:00 UTC
END = 1795737600    # 2026-11-27 00:00 UTC (last window starts 2026-11-26 23:40)
OUT = ROOT / "data" / "gaps_btc5m_tails"
OUT.mkdir(parents=True, exist_ok=True)
LOG = OUT / "fetch_status.jsonl"


def grid() -> list[int]:
    wins = [t for t in updown.windows("5m", START, END) if t % 1200 == 0]
    order = {0: 0, 2400: 1, 1200: 2, 3600: 3}
    return sorted(wins, key=lambda t: (order[t % 4800], t))


def main() -> None:
    wins = grid()
    if len(sys.argv) > 1:
        wins = wins[: int(sys.argv[1])]
    done = {}
    if LOG.exists():
        for line in LOG.read_text().splitlines():
            r = json.loads(line)
            done[r["t0"]] = r
    t_start = time.time()
    with LOG.open("a") as log:
        for i, t0 in enumerate(wins):
            if t0 in done and done[t0].get("ok"):
                continue
            rec = {"t0": t0, "ok": False}
            try:
                m = updown.load_market("btc", "5m", t0)
                if m is None or m.get("up_won") is None or not m.get("condition"):
                    rec["why"] = "no_market" if m is None else "unresolved"
                else:
                    try:
                        rows = updown.tape(m["condition"])
                    except (EOFError, OSError, ValueError) as e:  # damaged cache file from a concurrent writer
                        rec["cache_err"] = repr(e)[:120]
                        time.sleep(2)
                        rows = updown.tape(m["condition"], cache=False)
                    rec.update(ok=True, n=len(rows), condition=m["condition"])
            except Exception as e:  # noqa: BLE001
                rec["why"] = repr(e)[:200]
            log.write(json.dumps(rec) + "\n")
            log.flush()
            if i % 100 == 0:
                print(i, t0, rec.get("n"), rec.get("why"), f"{time.time() - t_start:.0f}s", flush=True)
    print("done", f"{time.time() - t_start:.0f}s", flush=True)


if __name__ == "__main__":
    main()
