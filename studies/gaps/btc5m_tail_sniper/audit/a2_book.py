"""Independent audit step 2: replay the raw L2 events for the signal markets, build tickets (cap x delay) with own code.
Usage: python3 -I a2_book.py DAY  -> writes scratchpad/ev_DAY.pkl (events of signal markets in rel seconds 150..300)."""
import sys, pickle
import numpy as np, pandas as pd, pyarrow as pa, pyarrow.parquet as pq, pyarrow.compute as pc
R = "/home/user/polymarket-lab/"
SP = "/tmp/claude-0/-home-user/05556429-066d-541b-b886-b8da26bcc648/scratchpad/"
day = sys.argv[1]
sig = pd.read_parquet(SP + "my_signals.parquet")
want = set(sig.t0.unique())
f = pq.ParquetFile(f"{R}data/gaps_btc5m_tail_sniper/mw/l2_{day}.parquet")
events = {}   # t0 -> list of tuples
for rg in range(f.metadata.num_row_groups):
    t = f.read_row_group(rg, columns=["market_slug", "timestamp", "event_type", "ask_prices", "ask_sizes", "bid_prices", "bid_sizes",
                                      "best_ask", "best_bid", "pc_price", "pc_size", "pc_side"])
    slug = t["market_slug"].to_pylist()
    t0 = np.array([int(s.rsplit("-", 1)[1]) for s in slug])
    ts = t["timestamp"].cast(pa.timestamp("us")).cast(pa.int64()).to_numpy() / 1e6   # seconds since epoch (UTC)
    rel = ts - t0
    sel = np.where((rel >= 150) & (rel <= 300) & np.isin(t0, list(want)))[0]
    if len(sel) == 0: continue
    et = t["event_type"].to_pylist(); ba = t["best_ask"].to_numpy(zero_copy_only=False); bb = t["best_bid"].to_numpy(zero_copy_only=False)
    pp = t["pc_price"].to_numpy(zero_copy_only=False); ps = t["pc_size"].to_numpy(zero_copy_only=False); sd = t["pc_side"].to_pylist()
    ap, az, bp, bz = (t[c].to_pylist() for c in ("ask_prices", "ask_sizes", "bid_prices", "bid_sizes"))
    for i in sel:
        if et[i] == "book":
            events.setdefault(int(t0[i]), []).append((ts[i], "book", ap[i], az[i], bp[i], bz[i]))
        elif et[i] == "price_change":
            events.setdefault(int(t0[i]), []).append((ts[i], "pc", float(pp[i]), float(ps[i]), sd[i], float(ba[i]), float(bb[i])))
print(day, "markets", len(events), "events", sum(len(v) for v in events.values()))
pickle.dump(events, open(SP + f"ev_{day}.pkl", "wb"))
