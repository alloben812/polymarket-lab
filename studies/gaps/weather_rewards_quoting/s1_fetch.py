"""Step 1: pull Houroux/polymarket-l2-history for the study dates, keep temperature markets only, delete raw files.

usage: python3 -I s1_fetch.py markets            (discovery snapshots -> markets_<date>.parquet)
       python3 -I s1_fetch.py events <date>...   (market_ws events + book levels -> events_<date>.parquet, levels_<date>.parquet)
Downloaded files are untrusted data: they are only read with pyarrow, in their own directory, and removed.
Sequential downloads only (one curl at a time).
"""
import json, os, subprocess, sys, time, urllib.parse
import pyarrow as pa, pyarrow.parquet as pq, pyarrow.compute as pc

DS = "Houroux/polymarket-l2-history"
OUT = "/home/user/polymarket-lab/data/datasets/houroux_weather"
TMP = OUT + "/raw_tmp"
DATES = ["2026-10-%02d" % d for d in range(2, 12)]
EV_COLS = ["sequence", "received_at_ns", "record_type", "connection_id", "control_event", "event_type", "exchange_timestamp_ms",
           "market", "asset_id", "change_index", "side", "price", "size", "best_bid", "best_ask", "tick_size",
           "fee_rate_bps", "transaction_hash"]
MK_DROP = ["market_json", "description", "clob_rewards_json", "fee_details_json"]


def curl(url, path, tries=6):
    for a in range(tries):
        r = subprocess.run(["curl", "-s", "-L", "--fail", "--max-time", "600", "-o", path, url])
        if r.returncode == 0 and os.path.exists(path) and os.path.getsize(path) > 0:
            return True
        time.sleep(5 + 10 * a)
    return False


def listing(table, date):
    path = f"{OUT}/ls_{table}_{date}.json"
    if os.path.exists(path):
        return json.load(open(path))
    rows, url = [], f"https://huggingface.co/api/datasets/{DS}/tree/main/analytics/{table}/date={date}?limit=1000"
    while url:
        hdr = TMP + "/_hdr.txt"
        subprocess.run(["curl", "-s", "-L", "--fail", "--max-time", "120", "-D", hdr, "-o", TMP + "/_ls.json", url], check=True)
        rows += json.load(open(TMP + "/_ls.json"))
        url = None
        for line in open(hdr):
            if line.lower().startswith("link:") and 'rel="next"' in line:
                url = line.split("<")[1].split(">")[0]
        time.sleep(0.7)
    json.dump(rows, open(path, "w"))
    return rows


def fetch(path_in_repo):
    dst = TMP + "/f.parquet"
    if os.path.exists(dst):
        os.remove(dst)
    ok = curl(f"https://huggingface.co/datasets/{DS}/resolve/main/{urllib.parse.quote(path_in_repo)}", dst)
    return dst if ok else None


def do_markets():
    for date in DATES:
        out = f"{OUT}/markets_{date}.parquet"
        if os.path.exists(out):
            continue
        files = sorted(x["path"] for x in listing("markets", date) if "__discovery__" in x["path"] and x["size"] > 100_000)
        pick = sorted(set(files[::4] + files[-1:]))
        parts = []
        for p in pick:
            f = fetch(p)
            if not f:
                print("FAILED", p, flush=True); continue
            t = pq.read_table(f, columns=[c for c in pq.ParquetFile(f).schema_arrow.names if c not in MK_DROP])
            t = t.filter(pc.match_substring(t["market_slug"], "temperature"))
            parts.append(t)
            os.remove(f)
        t = pa.concat_tables(parts)
        pq.write_table(t, out, compression="zstd")
        print(date, "discovery files", len(files), "used", len(pick), "rows", t.num_rows, flush=True)


def cond_set():
    s = set()
    for date in DATES:
        t = pq.read_table(f"{OUT}/markets_{date}.parquet", columns=["condition_id"])
        s |= set(t["condition_id"].to_pylist())
    return pa.array(sorted(s))


def do_events(dates):
    conds = cond_set()
    print("temperature conditions", len(conds), flush=True)
    for date in dates:
        out_e, out_l = f"{OUT}/events_{date}.parquet", f"{OUT}/levels_{date}.parquet"
        if os.path.exists(out_e) and os.path.exists(out_l):
            continue
        t0 = time.time()
        log = {"date": date, "files": 0, "failed": [], "raw_bytes": 0, "raw_rows": 0}
        parts = []
        for x in sorted(listing("events", date), key=lambda r: r["path"]):
            if "__market_ws__" not in x["path"]:
                continue
            f = fetch(x["path"])
            if not f:
                log["failed"].append(x["path"]); print("FAILED", x["path"], flush=True); continue
            t = pq.read_table(f, columns=EV_COLS)
            log["files"] += 1; log["raw_bytes"] += x["size"]; log["raw_rows"] += t.num_rows
            keep = pc.or_(pc.is_in(t["market"], value_set=conds), pc.not_equal(t["record_type"], "market_ws"))
            keep = pc.fill_null(keep, False)
            parts.append(t.filter(keep))
            os.remove(f)
        ev = pa.concat_tables(parts)
        pq.write_table(ev, out_e, compression="zstd")
        parts = []
        for x in sorted(listing("book_levels", date), key=lambda r: r["path"]):
            if "__market_ws__" not in x["path"] or x["size"] < 2000:
                continue
            f = fetch(x["path"])
            if not f:
                log["failed"].append(x["path"]); print("FAILED", x["path"], flush=True); continue
            t = pq.read_table(f)
            parts.append(t.filter(pc.fill_null(pc.is_in(t["market"], value_set=conds), False)))
            os.remove(f)
        lv = pa.concat_tables(parts)
        pq.write_table(lv, out_l, compression="zstd")
        log.update(kept_event_rows=ev.num_rows, kept_level_rows=lv.num_rows, seconds=round(time.time() - t0))
        json.dump(log, open(f"{OUT}/fetchlog_{date}.json", "w"))
        print(log, flush=True)


if __name__ == "__main__":
    os.makedirs(TMP, exist_ok=True)
    if sys.argv[1] == "markets":
        do_markets()
    else:
        do_events(sys.argv[2:] or DATES)
