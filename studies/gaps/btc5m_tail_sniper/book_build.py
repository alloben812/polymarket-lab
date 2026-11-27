"""OOS-BOOK build (protocol 3.1): Binance signals + book replay at tau and tau + d. No outcome statistics here.

Output: data/gaps_btc5m_tail_sniper/book_queries.parquet, one row per (market, signal second T, query offset d):
the tail's ask levels <= 0.05 at time tau + d (tau = T + 1) as two lists (prices, sizes).
"""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BOOK_DELAYS, DATA, signals  # noqa: E402
from pmlab.px import Px  # noqa: E402

MW = DATA / "mw"
START, END = 1786665600, 1787356800  # 2026-08-14 00:00 .. 2026-08-22 00:00
DAYS = [f"08{d:02d}" for d in range(14, 22)]
LO_REL, HI_REL = 150.0, 300.0
EXTRA = [0.5]  # protocol 6: clock-offset sensitivity (tau shifted +0.5 s), queried as offsets 0.5 + d for d in {0, 2}


def load_events(day: str, keep_t0: set) -> pd.DataFrame:
    f = pq.ParquetFile(MW / f"l2_{day}.parquet")
    cols = ["market_slug", "timestamp", "event_type", "ask_prices", "ask_sizes", "bid_prices", "bid_sizes", "pc_price", "pc_size", "pc_side"]
    parts = []
    base = 0
    for rg in range(f.metadata.num_row_groups):
        t = f.read_row_group(rg, columns=cols)
        n = t.num_rows
        slug = t["market_slug"].to_numpy(zero_copy_only=False)
        uniq, inv = np.unique(slug, return_inverse=True)
        t0u = np.array([int(s.rsplit("-", 1)[1]) for s in uniq])
        t0 = t0u[inv]
        ts = pc.cast(t["timestamp"], pa.int64()).to_numpy() / 1e6
        rel = ts - t0
        et = t["event_type"].to_numpy(zero_copy_only=False)
        inwin = (rel >= LO_REL) & (rel <= HI_REL) & np.isin(t0, list(keep_t0))
        # price changes in the relevant ranges
        side = t["pc_side"].to_numpy(zero_copy_only=False)
        pp = t["pc_price"].to_numpy(zero_copy_only=False).astype(float)
        ps = t["pc_size"].to_numpy(zero_copy_only=False).astype(float)
        is_pc = et == "price_change"
        selA = inwin & is_pc & (side == "SELL") & (pp <= 0.05 + 1e-9)
        selB = inwin & is_pc & (side == "BUY") & (pp >= 0.95 - 1e-9)
        idx = np.arange(n) + base
        for sel, sd in ((selA, "A"), (selB, "B")):
            if sel.any():
                parts.append(pd.DataFrame({"t0": t0[sel], "ts": ts[sel], "ord": idx[sel], "kind": 1, "side": sd, "p": pp[sel], "z": ps[sel]}))
        # book snapshots: reset + filtered levels
        selbk = inwin & (et == "book")
        if selbk.any():
            ii = np.where(selbk)[0]
            parts.append(pd.DataFrame({"t0": t0[ii], "ts": ts[ii], "ord": idx[ii], "kind": 0, "side": "R", "p": np.nan, "z": np.nan}))
            sub = t.take(pa.array(ii))
            for pcol, zcol, sd, cond in (("ask_prices", "ask_sizes", "A", lambda x: x <= 0.05 + 1e-9), ("bid_prices", "bid_sizes", "B", lambda x: x >= 0.95 - 1e-9)):
                lp = sub[pcol].combine_chunks()
                lz = sub[zcol].combine_chunks()
                par = pc.list_parent_indices(lp).to_numpy()
                fp = pc.list_flatten(lp).to_numpy(zero_copy_only=False).astype(float)
                fz = pc.list_flatten(lz).to_numpy(zero_copy_only=False).astype(float)
                m = cond(fp)
                if m.any():
                    rows = ii[par[m]]
                    parts.append(pd.DataFrame({"t0": t0[rows], "ts": ts[rows], "ord": idx[rows], "kind": 2, "side": sd, "p": fp[m], "z": fz[m]}))
        base += n
    ev = pd.concat(parts, ignore_index=True)
    return ev.sort_values(["t0", "ord", "kind"], kind="stable").reset_index(drop=True)


def replay(ev: pd.DataFrame, queries: np.ndarray):
    """ev: events of one market sorted by (ord). queries: sorted times. Yields (q, asks{p:z}, bids{p:z}) states."""
    ts = ev.ts.to_numpy(); kind = ev.kind.to_numpy(); side = ev.side.to_numpy(); p = ev.p.to_numpy(); z = ev.z.to_numpy()
    A, B = {}, {}
    seen_book = False
    j, n = 0, len(ts)
    out = []
    for q in queries:
        while j < n and ts[j] <= q:
            k = kind[j]
            if k == 0:
                A, B = {}, {}
                seen_book = True
            else:
                d = A if side[j] == "A" else B
                pr = round(float(p[j]), 4)
                if z[j] > 0:
                    d[pr] = float(z[j])
                else:
                    d.pop(pr, None)
            j += 1
        out.append((q, dict(A), dict(B), seen_book))
    return out


def main() -> None:
    t_start = time.time()
    mk = pd.read_parquet(MW / "markets.parquet")
    mk["t0"] = mk.market_slug.str.rsplit("-", n=1).str[1].astype(int)
    mk = mk[(mk.t0 >= START) & (mk.t0 < END)].copy()
    print("markets in period", len(mk), flush=True)
    P = Px.load("BTCUSDT", [f"2026-08-{d}" for d in range(13, 23)])
    sig_rows = []
    for t0 in mk.t0:
        for T, tail, dist, mv, s in signals(P, int(t0), 300):
            if s:
                sig_rows.append((int(t0), T, tail, dist, mv))
    sig = pd.DataFrame(sig_rows, columns=["t0", "T", "tail", "dist", "mv30"])
    print("signal seconds", len(sig), "markets with a signal", sig.t0.nunique(), f"{time.time() - t_start:.0f}s", flush=True)
    sig.to_parquet(DATA / "book_signals.parquet")
    offs = sorted(set(BOOK_DELAYS) | {e + d for e in EXTRA for d in (0.0, 2.0)})
    recs = []
    for day in DAYS:
        ev = load_events(day, set(sig.t0.unique()))
        print(day, "events", len(ev), f"{time.time() - t_start:.0f}s", flush=True)
        for t0, g in ev.groupby("t0", sort=False):
            s = sig[sig.t0 == t0]
            if s.empty:
                continue
            qs = sorted({float(T + 1 + o) for T in s["T"] for o in offs})
            st = {q: (a, b, sb) for q, a, b, sb in replay(g, np.array(qs))}
            for T, tail in zip(s["T"], s["tail"]):
                for o in offs:
                    a, b, sb = st[float(T + 1 + o)]
                    if tail == "Up":
                        lv = sorted(a.items())
                    else:
                        lv = sorted(((round(1.0 - pb, 4), zb) for pb, zb in b.items()))
                    recs.append((int(t0), int(T), tail, o, [x[0] for x in lv], [x[1] for x in lv], sb))
        del ev
    q = pd.DataFrame(recs, columns=["t0", "T", "tail", "off", "ask_p", "ask_z", "seen_book"])
    # a market can appear in two day files (window around midnight); keep the record built from the file with a book
    q = q.sort_values(["t0", "T", "off", "seen_book"]).drop_duplicates(["t0", "T", "off"], keep="last")
    q.to_parquet(DATA / "book_queries.parquet")
    print("queries", len(q), "markets", q.t0.nunique(), f"{time.time() - t_start:.0f}s", flush=True)


if __name__ == "__main__":
    main()
