"""Step 2: sample (rule 3), resolutions (rule 7), price histories of both tokens (rules 9-10). Resumable."""
import gzip
import json
import random
import sys
import time

from pmlab import dataapi
from common import DATA, SEED, read_jsonl, ts, write_jsonl

N_SAMPLE = 5000
CHUNK = 14 * 86400


def main():
    uni = read_jsonl(DATA / "universe.jsonl.gz")
    ids = sorted(m["conditionId"] for m in uni)
    print("universe", len(ids), flush=True)
    pick = set(random.Random(SEED).sample(ids, N_SAMPLE)) if len(ids) > N_SAMPLE else set(ids)
    sample = [m for m in uni if m["conditionId"] in pick]
    sample.sort(key=lambda m: m["conditionId"])
    write_jsonl(DATA / "sample.jsonl.gz", sample)
    print("sample", len(sample), flush=True)

    # resolutions
    res_path = DATA / "resolutions.json"
    res = json.loads(res_path.read_text()) if res_path.exists() else {}
    todo = [m["conditionId"] for m in sample if m["conditionId"] not in res]
    for i in range(0, len(todo), 200):
        res.update(dataapi.resolutions(todo[i:i + 200]))
        res_path.write_text(json.dumps(res))
        print("resolutions", len(res), flush=True)

    # price histories
    hist_path = DATA / "hist.jsonl.gz"
    done = set()
    if hist_path.exists():
        with gzip.open(hist_path, "rt") as f:
            for line in f:
                try:
                    done.add(json.loads(line)["cid"])
                except ValueError:
                    pass
    print("hist done", len(done), flush=True)
    t0 = time.time()
    n = 0
    with gzip.open(hist_path, "at") as f:
        for m in sample:
            cid = m["conditionId"]
            if cid in done:
                continue
            end, closed = ts(m["endDate"]), ts(m["closedTime"])
            start = end - 24 * 3600 - 900
            row = {"cid": cid, "skip": None, "h": [[], []], "err": None}
            if closed <= start:
                row["skip"] = "closed_before_window"
            else:
                stop = closed + 300
                try:
                    for k, tok in enumerate(m["clobTokenIds"]):
                        a = start
                        pts = []
                        while a < stop:
                            b = min(a + CHUNK, stop)
                            for r in dataapi.prices_history(tok, int(a), int(b), 300):
                                pts.append([r["timestamp"], r["price"], r.get("resolution_seconds")])
                            a = b
                        seen = set()
                        uniq = []
                        for p in sorted(pts):
                            if (p[0], p[2]) in seen:
                                continue
                            seen.add((p[0], p[2]))
                            uniq.append(p)
                        row["h"][k] = uniq
                except Exception as e:  # noqa: BLE001
                    row["err"] = repr(e)[:300]
            f.write(json.dumps(row) + "\n")
            n += 1
            if n % 100 == 0:
                f.flush()
                print(f"hist {n} new, {time.time()-t0:.0f}s", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
