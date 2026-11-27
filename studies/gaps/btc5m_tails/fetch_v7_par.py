"""Parallel cache warmer for fetch_v7.py (plumbing only): loads official metadata of Vega7's BTC 5m windows in
N processes so that fetch_v7.py then runs from the cache. No statistics. Usage: python3 fetch_v7_par.py N"""
import json
import multiprocessing as mp
import sys

from common import DATA, END, START
from pmlab import updown


def worker(k, n, t0s):
    for i, t0 in enumerate(t0s[k::n]):
        try:
            updown.load_market("btc", "5m", t0)
        except Exception as e:  # noqa: BLE001
            print("error", t0, repr(e)[:100], flush=True)
        if i % 300 == 0:
            print("w", k, i, flush=True)
    print("w", k, "done", flush=True)


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    fills = json.loads((DATA / "vega7_fills.json").read_text())
    t0s = sorted({int(f["slug"].rsplit("-", 1)[1]) for f in fills if (f.get("slug") or "").startswith("btc-updown-5m-")})
    t0s = [t for t in t0s if START <= t < END and t % 1200 != 0]
    ps = [mp.Process(target=worker, args=(k, n, t0s)) for k in range(n)]
    [p.start() for p in ps]
    [p.join() for p in ps]
