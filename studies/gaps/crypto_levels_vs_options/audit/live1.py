import json, gzip, random, time
import numpy as np, pandas as pd
from pathlib import Path
from pmlab.http import get_json
from pmlab import dataapi
D = Path("/home/user/polymarket-lab/data/gaps_levels")
iso = lambda t: time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(t))
# 1. Binance spot-check: fresh klines for 6 random start points per symbol, 1000 minutes each
rng = random.Random(1)
for sym in ("BTCUSDT", "ETHUSDT"):
    a = np.load(D / f"{sym}_1m.npy"); t0, t1 = int(a[0, 0]), int(a[-1, 0])
    ot = a[:, 0].astype("int64"); print(sym, "rows", len(a), "expected", (t1 - t0) // 60 + 1, "dups", len(ot) - len(set(ot.tolist())), "max step", int(np.diff(ot).max()), iso(t0), iso(t1))
    cached = dict(zip(ot.tolist(), a[:, 4].tolist())); hi = dict(zip(ot.tolist(), a[:, 2].tolist()))
    nbad = n = 0
    for _ in range(6):
        s = rng.randrange(t0, t1 - 60000) // 60 * 60
        rows = get_json("https://data-api.binance.vision/api/v3/klines", {"symbol": sym, "interval": "1m", "startTime": s * 1000, "limit": 1000})
        for r in rows:
            k = int(r[0]) // 1000; n += 1
            if k not in cached or abs(cached[k] - float(r[4])) > 1e-9 or abs(hi[k] - float(r[2])) > 1e-9: nbad += 1
    print("  fresh vs cached 1m candles:", n, "checked,", nbad, "differ")
# 2. Deribit DVOL timestamp convention: hourly row stamp X -> is close the value at X+3600 (stamp = open) or at X (stamp = end)?
for cur in ("BTC", "ETH"):
    d = np.load(D / f"dvol_{cur}.npy"); print(cur, "dvol rows", len(d), "max step h", np.diff(d[:, 0]).max() / 3600, iso(d[0, 0]), iso(d[-1, 0]))
    X = int(d[len(d) // 2, 0])
    h = get_json("https://www.deribit.com/api/v2/public/get_volatility_index_data", {"currency": cur, "start_timestamp": X * 1000, "end_timestamp": (X + 2 * 3600) * 1000, "resolution": 3600})["result"]["data"]
    m = get_json("https://www.deribit.com/api/v2/public/get_volatility_index_data", {"currency": cur, "start_timestamp": (X - 120) * 1000, "end_timestamp": (X + 3700) * 1000, "resolution": 60})["result"]["data"]
    mm = {int(r[0]) // 1000: r for r in m}
    hr = [r for r in h if int(r[0]) // 1000 == X][0]
    print("  hourly row", iso(X), "open", hr[1], "close", hr[4], "| cached close", float(d[d[:, 0] == X][0, 1]))
    for off in (-60, 0, 3540, 3600):
        if X + off in mm: print("    1-min row at X%+d: open %s close %s" % (off, mm[X + off][1], mm[X + off][4]))
