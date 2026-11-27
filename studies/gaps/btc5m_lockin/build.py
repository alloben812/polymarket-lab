"""Step 1b: compact extract from the cached tapes: market table, last-minute prints, model values per second.

No outcome statistics. Output under data/gaps_btc5m_lockin/full/: markets.parquet, prints.parquet, model.parquet.
"""
import json

import numpy as np
import pandas as pd

from common import DATA, EXTRACT, all_windows, load_px, meta, model_at
from pmlab import updown

px = load_px()
status = {}
for line in (DATA / "fetch_status.jsonl").read_text().splitlines():
    r = json.loads(line)
    status[r["t0"]] = r

mk, pr, md = [], [], []
for t0 in all_windows():
    t1 = t0 + 300
    st = status.get(t0)
    m = meta(t0)
    rec = {"t0": t0, "usable": False, "why": None}
    if st is None or not st.get("ok") or m is None:
        rec["why"] = (st or {}).get("why", "not_fetched")
        mk.append(rec)
        continue
    rows = updown.tape(m["condition"])
    rec.update(condition=m["condition"], up_won=m["up_won"], ptb=m["price_to_beat"], final=m["final_price"],
               fee_rate=m["fee_rate"], volume=m["volume"], n_rows=len(rows),
               n_after_end=sum(1 for r in rows if r["t"] - 3 >= t1),
               k_bin=px.twap(t0, 60), a_bin=px.twap(t1, 60))
    if not rows:
        rec["why"] = "empty_tape"
        mk.append(rec)
        continue
    rec["usable"] = True
    mk.append(rec)
    buy = list(updown.buyable(rows))
    for seq, (r, b) in enumerate(zip(rows, buy)):
        mt = r["t"] - 3
        assert b[0] == mt
        if t1 - 60 <= mt < t1:
            pr.append((t0, seq, r["t"], mt, r["s"] == "BUY", r["o"] == "Up", r["p"], r["z"], b[1] == "Up", b[2]))
    for t in range(t1 - 63, t1 - 3):
        f, ea, k = model_at(px, t, t0)
        md.append((t0, t, f, ea, k))

mk = pd.DataFrame(mk)
pr = pd.DataFrame(pr, columns=["t0", "seq", "bt", "m", "is_buy", "o_up", "p", "z", "b_up", "bq"])
md = pd.DataFrame(md, columns=["t0", "t", "f_up", "ea", "k"])
EXTRACT.mkdir(parents=True, exist_ok=True)
mk.to_parquet(EXTRACT / "markets.parquet")
pr.to_parquet(EXTRACT / "prints.parquet")
md.to_parquet(EXTRACT / "model.parquet")
print("markets", len(mk), "usable", int(mk.usable.sum()), "why:", mk.why.value_counts(dropna=True).to_dict())
print("prints", len(pr), "model rows", len(md), "model NaN", int(md.f_up.isna().sum()))
print("tape rows total", int(mk.n_rows.sum()), "rows with match time >= t1:", int(mk.n_after_end.sum()))
