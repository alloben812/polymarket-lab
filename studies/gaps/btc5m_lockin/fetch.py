"""Step 1: metadata + whole-market tapes for all BTC 5m windows of 21-26 Nov 2026. Sequential, throttled, resumable.

No outcome statistics here. Usage: python3 studies/gaps/btc5m_lockin/fetch.py [max_windows]
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from pmlab import updown  # noqa: E402

START = 1795219200  # 2026-11-21 00:00 UTC
END = START + 6 * 86400
OUT = Path(__file__).resolve().parents[3] / "data" / "gaps_btc5m_lockin"
OUT.mkdir(parents=True, exist_ok=True)
LOG = OUT / "fetch_status.jsonl"


def main() -> None:
    wins = updown.windows("5m", START, END)
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
                    rows = None
                    for attempt in range(3):
                        try:
                            rows = updown.tape(m["condition"])
                            break
                        except (EOFError, OSError, ValueError) as e:  # damaged cache file from a concurrent writer
                            rec["cache_err"] = repr(e)[:120]
                            time.sleep(2)
                            rows = updown.tape(m["condition"], cache=False)
                            break
                    rec.update(ok=True, n=len(rows), condition=m["condition"])
            except Exception as e:  # noqa: BLE001
                rec["why"] = repr(e)[:200]
            log.write(json.dumps(rec) + "\n")
            log.flush()
            if i % 50 == 0:
                print(i, t0, rec.get("n"), rec.get("why"), f"{time.time() - t_start:.0f}s", flush=True)
    print("done", f"{time.time() - t_start:.0f}s")


if __name__ == "__main__":
    main()
