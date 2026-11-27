"""Download (cached) metadata and whole-market tapes for the series not yet in data/. Safe to re-run.

Usage: python3 fetch.py [workers]   (default 3 workers; pmlab.http throttles per host)"""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from common import BIG, SERIES, load_market, name, windows
from pmlab import updown


def one(s, t0):
    for attempt in range(3):
        try:
            m = load_market(s[0], s[1], t0)
            if not m or m.get("up_won") is None or not m.get("condition"):
                return "miss", 0
            return "ok", len(updown.tape(m["condition"]))
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__}: {str(e)[:150]}"
            time.sleep(5 * (attempt + 1))
    return "fail:" + err, 0


def main():
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    BIG.mkdir(parents=True, exist_ok=True)
    summary = []
    with open(BIG / "fetch.log", "a") as log, ThreadPoolExecutor(workers) as ex:
        for s in SERIES:
            t0s = windows(s)
            res = list(ex.map(lambda t: one(s, t), t0s))
            ok = sum(r[0] == "ok" for r in res)
            miss = sum(r[0] == "miss" for r in res)
            fails = [(t, r[0]) for t, r in zip(t0s, res) if r[0].startswith("fail")]
            rows = sum(r[1] for r in res)
            line = {"series": name(s), "n": len(t0s), "ok": ok, "miss": miss, "fail": len(fails), "rows": rows}
            summary.append(line)
            log.write(f"{time.strftime('%H:%M:%S')} {json.dumps(line)} {fails[:3]}\n")
            log.flush()
    (BIG / "fetch_summary.json").write_text(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
