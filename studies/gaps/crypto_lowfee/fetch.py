"""Sequential, cached download of market metadata and tapes for the study universe. Safe to re-run."""
from __future__ import annotations

import json
import sys
import time

from common import BIG, OUT, REF, SERIES, T_START, name, series_windows
from pmlab import updown


def fetch(series, t0s, log):
    asset, dur = series
    ok = miss = fail = rows = 0
    for i, t0 in enumerate(t0s):
        try:
            m = updown.load_market(asset, dur, t0)
            if not m or m.get("up_won") is None or not m.get("condition"):
                miss += 1
                continue
            rows += len(updown.tape(m["condition"]))
            ok += 1
        except Exception as e:  # noqa: BLE001
            fail += 1
            log.write(f"FAIL {name(series)} {t0} {type(e).__name__}: {str(e)[:200]}\n")
            time.sleep(5)
        if (i + 1) % 100 == 0:
            log.write(f"{time.strftime('%H:%M:%S')} {name(series)} {i + 1}/{len(t0s)} ok={ok} miss={miss} fail={fail} rows={rows}\n")
            log.flush()
    log.write(f"{time.strftime('%H:%M:%S')} DONE {name(series)} n={len(t0s)} ok={ok} miss={miss} fail={fail} rows={rows}\n")
    log.flush()
    return {"series": name(series), "n": len(t0s), "ok": ok, "miss": miss, "fail": fail, "rows": rows}


def main():
    BIG.mkdir(parents=True, exist_ok=True)
    slice_only = len(sys.argv) > 1 and sys.argv[1] == "slice"
    with open(OUT / "fetch.log", "a") as log:
        log.write(f"--- start {time.strftime('%Y-%m-%d %H:%M:%S')} slice={slice_only}\n")
        # small slice first: first day of eth 5m and btc 15m
        day1 = lambda s: [t for t in series_windows(s) if t < T_START + 86400]  # noqa: E731
        res = [fetch(("eth", "5m"), day1(("eth", "5m")), log), fetch(("btc", "15m"), day1(("btc", "15m")), log)]
        if not slice_only:
            for s in SERIES + [REF]:
                res.append(fetch(s, series_windows(s), log))
        (OUT / "fetch_summary.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
