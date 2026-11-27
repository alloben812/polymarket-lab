"""Step 2: per sample hour, download the archive files that hold universe markets, keep only their rows.
usage: python3 -I u2_extract.py 2026-11-21T02 [more hours...]
Writes data/gaps_negrisk/hours/<tag>.ev.parquet and <tag>.open.parquet; raw files are deleted.
"""
import json, os, subprocess, sys, time
import pyarrow as pa, pyarrow.parquet as pq, pyarrow.compute as pc
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import D, families

DS = "https://huggingface.co/datasets/chitoyuuri/polymarket-l2-v3-1-archive"
API = "https://huggingface.co/api/datasets/chitoyuuri/polymarket-l2-v3-1-archive/tree/main/v3.1"
COLS = ["event_type", "timestamp", "market", "asset_id", "best_bid", "best_ask", "bids", "asks", "price", "size",
        "side", "recv_lag_ms", "row_ordinal", "mirror_dropped"]


def curl(url, path, tries=5):
    for a in range(tries):
        r = subprocess.run(["curl", "-s", "-L", "--fail", "--max-time", "900", "-o", path, url])
        if r.returncode == 0 and os.path.exists(path) and os.path.getsize(path) > 0:
            return True
        time.sleep(5 + 10 * a)
    return False


def universe_bytes():
    f = families()
    conds = {m["conditionId"] for k in f for e in f[k] for m in e["markets"]}
    return pa.array([bytes.fromhex(c[2:]) for c in sorted(conds)], type=pa.binary())


def do_hour(tag, vs):
    day, hh = tag[:10], tag[11:13]
    out_e, out_o = f"{D}/hours/{tag}.ev.parquet", f"{D}/hours/{tag}.open.parquet"
    if os.path.exists(out_e) and os.path.exists(out_o):
        return
    tmp = f"{D}/raw/{tag}"; os.makedirs(tmp, exist_ok=True); os.makedirs(f"{D}/hours", exist_ok=True)
    lst = f"{tmp}/tree.json"
    if not curl(f"{API}/{day}/{hh}", lst):
        print("tree FAILED", tag, flush=True); return
    names = [x["path"].split("/")[-1] for x in json.load(open(lst))]
    idx = [n for n in names if ".x_market_index." in n][0]
    curl(f"{DS}/resolve/main/v3.1/{day}/{hh}/{idx}", f"{tmp}/idx.parquet")
    it = pq.read_table(f"{tmp}/idx.parquet", columns=["market", "files"])
    it = it.filter(pc.is_in(it["market"].cast(pa.binary()), value_set=vs))
    files = sorted({f for fl in it["files"].to_pylist() for f in fl})
    print(tag, "universe markets in hour", it.num_rows, "files", files, flush=True)
    # opening state
    op = f"{tmp}/open.parquet"
    curl(f"{DS}/resolve/main/v3.1/{day}/{hh}/{tag}.opening_state.parquet", op)
    ot = pq.read_table(op, columns=["market", "asset_id", "bids", "asks", "best_bid", "best_ask", "book_as_of", "resolved"])
    ot = ot.filter(pc.is_in(ot["market"].cast(pa.binary()), value_set=vs))
    pq.write_table(ot, out_o + ".tmp", compression="zstd")
    os.remove(op)
    parts = []
    for fn in files:
        raw = f"{tmp}/{fn}"
        if not curl(f"{DS}/resolve/main/v3.1/{day}/{hh}/{fn}", raw):
            print("FAILED", fn, flush=True); continue
        pf = pq.ParquetFile(raw)
        n = 0
        for g in range(pf.num_row_groups):
            t = pf.read_row_group(g, columns=COLS)
            t = t.filter(pc.is_in(t["market"].cast(pa.binary()), value_set=vs))
            t = t.set_column(t.schema.get_field_index("market"), "market", t["market"].cast(pa.binary()))
            t = t.set_column(t.schema.get_field_index("asset_id"), "asset_id", t["asset_id"].cast(pa.binary()))
            t = t.set_column(t.schema.get_field_index("event_type"), "event_type", t["event_type"].cast(pa.string()))
            n += t.num_rows
            parts.append(t)
        os.remove(raw)
        print(tag, fn, "kept", n, flush=True)
    if parts:
        pq.write_table(pa.concat_tables(parts), out_e + ".tmp", compression="zstd")
        os.replace(out_e + ".tmp", out_e)
    os.replace(out_o + ".tmp", out_o)
    for f in os.listdir(tmp):
        os.remove(f"{tmp}/{f}")
    os.rmdir(tmp)


if __name__ == "__main__":
    vs = universe_bytes()
    for tag in sys.argv[1:]:
        t0 = time.time()
        do_hour(tag, vs)
        print("DONE", tag, round(time.time() - t0), "s", flush=True)
