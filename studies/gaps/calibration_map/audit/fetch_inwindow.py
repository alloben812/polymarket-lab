"""Exploratory (NOT pre-registered): in-window prices of late updown-15m markets, 300 s buckets. 200 markets, sequential."""
import gzip, json, random, time
from datetime import datetime, timezone
from pmlab import dataapi
D = "/home/user/polymarket-lab/data/gaps_calibration_map/"
SPLIT = datetime(2026, 10, 28, tzinfo=timezone.utc).timestamp()
ms = [json.loads(l) for l in gzip.open(D + "sample.jsonl.gz", "rt")]
ms = [m for m in ms if m["fam"] == "updown-15m" and m["anchor"] >= SPLIT]
random.Random(1).shuffle(ms)
ms = ms[:200]
out = open("inwindow.jsonl", "a")
done = {json.loads(l)["cid"] for l in open("inwindow.jsonl")} if False else set()
t0 = time.time()
for i, m in enumerate(ms):
    a = int(m["anchor"])
    try:
        h = dataapi.prices_history(m["tokens"][0], a - 900 - 600, a, 300)
        pts = [[int(x["timestamp"]), float(x["price"])] for x in h]
    except Exception as e:
        pts = None
    out.write(json.dumps({"cid": m["cid"], "slug": m["slug"], "anchor": a, "rate": m["rate"], "win": m["win"], "pts": pts}) + "\n"); out.flush()
    if i % 40 == 0: print(i, time.time() - t0, flush=True)
