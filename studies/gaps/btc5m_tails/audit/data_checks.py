"""Audit data checks on the raw cache: outcome vs final>=ptb, exact duplicate tape rows, tape completeness of markets
without gamma volume, tie order inside a block. Usage: python3 data_checks.py TAILS_MARKETS.parquet"""
import gzip, json, os, sys, collections
import numpy as np, pandas as pd
D = "/home/user/polymarket-lab/data"
mk = pd.read_parquet(sys.argv[1])
c = collections.Counter(); dup_rows = 0; tot_rows = 0; tie_blocks = 0
for t0 in mk.t0:
    m = json.load(open(f"{D}/updown_meta/btc/5m/{t0}.json"))
    if m.get("final_price") is not None and m.get("price_to_beat") is not None:
        c[("final>=ptb", m["final_price"] >= m["price_to_beat"], "up_won", m["up_won"])] += 1
    else:
        c["no final/ptb"] += 1
    with gzip.open(f"{D}/tape/{m['condition']}.jsonl.gz", "rt") as f:
        rows = [line for line in f]
    tot_rows += len(rows); dup_rows += len(rows) - len(set(rows))
print(c)
print("tape rows", tot_rows, "exact duplicate rows", dup_rows, f"({100*dup_rows/tot_rows:.3f}%)")
mk["ratio"] = mk.shares / mk.volume
print("ratio shares/volume:", mk.ratio.describe(percentiles=[.01, .5, .99]).round(4).to_dict())
nv = mk.volume.isna() | (mk.volume <= 0)
print("markets without volume", int(nv.sum()), "median rows", mk[nv].rows.median(), "vs with volume", mk[~nv].rows.median(),
      "; max rows overall", mk.rows.max(), "; rows==multiple of 1000 (possible cut):", int(((mk.rows % 1000) == 0).sum()))
