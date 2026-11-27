"""Step 1b: books and prints of the rewarded highest-temperature markets from the PendulumFlow V3.1 mirror
(HF chitoyuuri/polymarket-l2-v3-1-archive), hourly weather files 2026-10-02T00 .. 2026-10-12T02.

usage: python3 -I s1b_fetch_pflow.py            (all hours, resumable)
Keeps rows with sub_tag == highest-temperature whose market is in the Houroux reward universe; deletes the raw file.
Sequential downloads only.
"""
import datetime as dt, glob, json, os, subprocess, sys, time
import pyarrow as pa, pyarrow.parquet as pq, pyarrow.compute as pc

DS = "chitoyuuri/polymarket-l2-v3-1-archive"
HX = "/home/user/polymarket-lab/data/datasets/houroux_weather"
OUT = "/home/user/polymarket-lab/data/datasets/pflow_weather"
TMP = OUT + "/raw_tmp"
H0, H1 = dt.datetime(2026, 10, 2, 0), dt.datetime(2026, 10, 12, 2)
FLAT = ["event_type", "timestamp", "market", "asset_id", "best_bid", "best_ask", "price", "size", "side",
        "new_tick_size", "row_ordinal", "recv_lag_ms"]


def universe():
    conds = set()
    for f in sorted(glob.glob(HX + "/marketsfull_*.parquet")):
        t = pq.read_table(f, columns=["condition_id", "market_slug"]).to_pandas()
        conds |= set(t[t.market_slug.str.startswith("highest-temperature-in-")].condition_id)
    return sorted(conds)


def curl(url, path, tries=6):
    for a in range(tries):
        r = subprocess.run(["curl", "-s", "-L", "--fail", "--max-time", "900", "-o", path, url])
        if r.returncode == 0 and os.path.exists(path) and os.path.getsize(path) > 0:
            return True
        time.sleep(5 + 10 * a)
    return False


def main():
    os.makedirs(TMP, exist_ok=True)
    conds = universe()
    vs = pa.array([bytes.fromhex(c[2:]) for c in conds], type=pa.binary())
    print("universe conditions", len(conds), flush=True)
    h = H0
    while h <= H1:
        tag = h.strftime("%Y-%m-%dT%H")
        out_f, out_b = f"{OUT}/flat_{tag}.parquet", f"{OUT}/book_{tag}.parquet"
        if not (os.path.exists(out_f) and os.path.exists(out_b)):
            raw = TMP + "/w.parquet"
            if os.path.exists(raw):
                os.remove(raw)
            url = f"https://huggingface.co/datasets/{DS}/resolve/main/v3.1/{h:%Y-%m-%d}/{h:%H}/{tag}.weather.parquet"
            if not curl(url, raw):
                print("FAILED", tag, flush=True); h += dt.timedelta(hours=1); continue
            t = pq.read_table(raw, columns=FLAT + ["bids", "asks", "sub_tag"])
            n_raw = t.num_rows
            t = t.filter(pc.equal(t["sub_tag"], "highest-temperature"))
            n_ht = t.num_rows
            mk = t["market"].cast(pa.binary())
            t = t.filter(pc.is_in(mk, value_set=vs))
            df = t.select(FLAT).to_pandas()
            df["market"] = df["market"].map(lambda b: "0x" + b.hex()).astype("category")
            df["asset_id"] = df["asset_id"].map(lambda b: str(int.from_bytes(b, "big")) if isinstance(b, (bytes, bytearray)) else None).astype("category")
            df["ts"] = df["timestamp"].astype("int64") // (1 if str(df["timestamp"].dtype).startswith("datetime64[ms") else 1_000_000)
            for c in ["best_bid", "best_ask", "price", "size", "new_tick_size"]:
                df[c] = df[c].astype("float64")
            df = df.drop(columns=["timestamp"])
            isb = df.event_type == "book"
            df[~isb].to_parquet(out_f, compression="zstd", index=False)
            tb = t.filter(pa.array(isb.values))
            bk = pa.table({
                "ts": pa.array(df.ts[isb].values), "market": pa.array(df.market[isb].astype(str).values),
                "asset_id": pa.array(df.asset_id[isb].astype(str).values), "row_ordinal": tb["row_ordinal"],
                "bid_px": pa.array([[float(x["price"]) for x in (r or [])] for r in tb["bids"].to_pylist()], type=pa.list_(pa.float64())),
                "bid_sz": pa.array([[float(x["size"]) for x in (r or [])] for r in tb["bids"].to_pylist()], type=pa.list_(pa.float64())),
                "ask_px": pa.array([[float(x["price"]) for x in (r or [])] for r in tb["asks"].to_pylist()], type=pa.list_(pa.float64())),
                "ask_sz": pa.array([[float(x["size"]) for x in (r or [])] for r in tb["asks"].to_pylist()], type=pa.list_(pa.float64())),
            })
            pq.write_table(bk, out_b, compression="zstd")
            os.remove(raw)
            print(tag, "raw rows", n_raw, "highest-temp", n_ht, "kept", len(df), "books", int(isb.sum()), flush=True)
        h += dt.timedelta(hours=1)


if __name__ == "__main__":
    main()
