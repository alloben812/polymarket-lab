"""Post-hoc timing check, stage A (run with python3 -I: it only reads third-party parquet files).

usage: python3 -I ws_extract.py <dir with hourly trade parquet files> <json list of condition ids> <output parquet>
Source: HF dataset ithiria894/polymarket-l2-orderbook, data/crypto_updown/trades/2026-11-2x/HH.parquet (CC BY 4.0):
WebSocket trade events with the exchange timestamp in ms.
"""
import glob
import json
import sys

import pandas as pd
import pyarrow.parquet as pq

src, cond_file, out = sys.argv[1], sys.argv[2], sys.argv[3]
conds = set(json.load(open(cond_file)))
parts = []
for f in sorted(glob.glob(src + "/*.parquet")):
    df = pq.read_table(f, columns=["asset_id", "ev_ts", "market", "price", "side", "size", "recv_ts"]).to_pandas()
    df = df[df.market.isin(conds)]
    if len(df):
        df["price"] = df.price.astype(float)
        df["size"] = df["size"].astype(float)
        parts.append(df)
df = pd.concat(parts).drop_duplicates(["asset_id", "ev_ts", "price", "side", "size"]).sort_values(["market", "ev_ts"])
df.to_parquet(out)
print("rows", len(df), "markets", df.market.nunique(), "ev_ts range", df.ev_ts.min(), df.ev_ts.max())
