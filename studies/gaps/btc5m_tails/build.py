"""Step 2: cached tapes -> one table of buyable prints (all prices) + one table of markets. No statistics.

Usage: python3 studies/gaps/btc5m_tails/build.py [max_markets]   (max_markets: first N in download order, for the sanity slice)
"""
import sys
import time

import numpy as np
import pandas as pd

from common import DATA, VEGA7, load_status
from pmlab import updown


def main() -> None:
    status = load_status()
    ok = [r for r in status.values() if r.get("ok")]
    tag = "full"
    if len(sys.argv) > 1:
        ok = ok[: int(sys.argv[1])]
        tag = "slice"
    cols = {k: [] for k in ("t0", "bt", "e", "side", "p", "z", "src", "hit", "v7")}
    mk = []
    t_start = time.time()
    for i, r in enumerate(ok):
        t0 = r["t0"]
        m = updown.load_market("btc", "5m", t0)
        rows = updown.tape(m["condition"])
        up = bool(m["up_won"])
        shares = 0.0
        n_bad = 0
        for row, (mt, o, p, z) in zip(rows, updown.buyable(rows)):
            shares += row["z"]
            p = round(p, 6)
            if not (z > 0 and 0.0 < p < 1.0):
                n_bad += 1
                continue
            s = 1 if o == "Up" else 0
            cols["t0"].append(t0); cols["bt"].append(row["t"]); cols["e"].append(mt - t0); cols["side"].append(s)
            cols["p"].append(p); cols["z"].append(z); cols["src"].append(1 if row["s"] == "BUY" else 0)
            cols["hit"].append((s == 1) == up); cols["v7"].append(row.get("w") == VEGA7)
        mk.append({"t0": t0, "condition": m["condition"], "up_won": up, "ptb": m.get("price_to_beat"), "final": m.get("final_price"),
                   "volume": m.get("volume"), "rows": len(rows), "tape_shares": shares, "bad_rows": n_bad,
                   "first_rel": rows[0]["t"] - t0 if rows else None, "last_rel": rows[-1]["t"] - t0 if rows else None})
        if i % 500 == 0:
            print(i, len(ok), f"{time.time() - t_start:.0f}s", flush=True)
    df = pd.DataFrame({
        "t0": np.array(cols["t0"], dtype=np.int64), "bt": np.array(cols["bt"], dtype=np.int64), "e": np.array(cols["e"], dtype=np.int32),
        "side": np.array(cols["side"], dtype=np.int8), "p": np.array(cols["p"], dtype=np.float64), "z": np.array(cols["z"], dtype=np.float64),
        "src": np.array(cols["src"], dtype=np.int8), "hit": np.array(cols["hit"], dtype=bool), "v7": np.array(cols["v7"], dtype=bool)})
    df.to_parquet(DATA / f"prints_{tag}.parquet", index=False)
    pd.DataFrame(mk).to_parquet(DATA / f"markets_{tag}.parquet", index=False)
    print("markets", len(mk), "prints", len(df), "not ok", len(status) - len([r for r in status.values() if r.get('ok')]), f"{time.time() - t_start:.0f}s")


if __name__ == "__main__":
    main()
