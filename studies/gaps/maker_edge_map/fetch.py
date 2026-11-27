"""Download (or reuse) tapes for the sample. Cap 20,000 rows per market (protocol)."""
import gzip, json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
from pmlab import dataapi
D = "/home/user/polymarket-lab/data/gaps_maker_edge"; TAPE = "/home/user/polymarket-lab/data/tape"; CAP = 20000
os.makedirs(f"{D}/tapes", exist_ok=True)
sel = json.load(open(f"{D}/" + (sys.argv[1] if len(sys.argv) > 1 else "sample.json")))
def get(r):
    c = r["conditionId"]; out = f"{D}/tapes/{c}.jsonl.gz"
    if os.path.exists(out): return c, "have"
    p = f"{TAPE}/{c}.jsonl.gz"
    if os.path.exists(p):
        os.symlink(p, out); return c, "cache"
    try:
        rows = []
        for x in dataapi.iter_trades(condition=c, max_rows=CAP + 1):
            rows.append({"t": x["timestamp"], "s": x["side"], "o": x["outcome"], "z": float(x["size"]), "p": float(x["price"]), "w": x.get("proxy_wallet")})
        capped = len(rows) > CAP
        rows = rows[:CAP]; rows.sort(key=lambda q: q["t"])
        tmp = out + ".tmp"
        with gzip.open(tmp, "wt") as f:
            for q in rows: f.write(json.dumps(q) + "\n")
        os.replace(tmp, out)
        if capped: open(f"{D}/tapes/{c}.capped", "w").write("1")
        return c, f"dl{len(rows)}{'C' if capped else ''}"
    except Exception as e:
        return c, f"fail {e!r}"[:200]
t0 = time.time(); st = {}
with ThreadPoolExecutor(3) as ex:
    for i, (c, s) in enumerate(ex.map(get, sel)):
        st[c] = s
        if i % 25 == 0: print(i, round(time.time() - t0), s, flush=True)
json.dump(st, open(f"{D}/fetch_status_" + (sys.argv[1] if len(sys.argv) > 1 else "sample.json"), "w"))
print("done", round(time.time() - t0), sum(1 for s in st.values() if s.startswith("fail")), "failed")
