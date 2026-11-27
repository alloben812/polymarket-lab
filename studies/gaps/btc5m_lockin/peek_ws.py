"""Peek at the downloaded exchange-timestamped trade files (untrusted data: run with python3 -I)."""
import glob
import sys

import pyarrow.parquet as pq

d = sys.argv[1]
fs = sorted(glob.glob(d + "/*.parquet"))
t = pq.read_table(fs[len(fs) // 2])
print(fs[len(fs) // 2], t.num_rows, t.schema)
df = t.to_pandas()
print(df.head(5).to_string())
print(df.capture.value_counts().head(), df.side.value_counts())
print("recv-ev ms", ((df.recv_ts * 1000 - df.ev_ts)).describe())
print("distinct markets", df.market.nunique(), "assets", df.asset_id.nunique())
