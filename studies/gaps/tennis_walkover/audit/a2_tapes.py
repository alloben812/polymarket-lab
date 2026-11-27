"""Audit step 2: tape completeness (dollars on tape vs gamma volumeNum), duplicates, row-count caps, time range."""
import gzip, json, os, collections, statistics
SC = "/tmp/claude-0/-home-user/05556429-066d-541b-b886-b8da26bcc648/scratchpad/"
TD = "/home/user/polymarket-lab/data/tape/"
U = json.load(open(SC + "aud_universe.json"))
def load(cid):
    p = TD + cid + ".jsonl.gz"
    if not os.path.exists(p): return None
    return [json.loads(l) for l in gzip.open(p, "rt")]
res = collections.Counter(); ratios = []; nrows = collections.Counter(); dups = 0; tot = 0; after_close = 0; bad = []
for grp in ("A", "S"):
    for r in U[grp]:
        tp = load(r["cid"])
        if tp is None:
            res[grp + "_missing_tape" + ("_volpos" if r["vol"] else "_vol0")] += 1; continue
        res[grp + "_tape"] += 1
        n = len(tp); tot += n
        if n and n % 1000 == 0: nrows[n] += 1
        key = collections.Counter((x["t"], x["s"], x["o"], x["z"], x["p"], x["w"]) for x in tp)
        dups += sum(v - 1 for v in key.values() if v > 1)
        usd = sum(x["z"] * x["p"] for x in tp)
        if r["vol"]:
            ratios.append((usd / r["vol"], r["slug"], n))
        after_close += sum(1 for x in tp if x["t"] > r["closed"] + 60)
print(dict(res)); print("rows", tot, "exact-1000 counts", dict(nrows), "identical-row dups", dups, "rows > closedTime+60s", after_close)
rs = sorted(x[0] for x in ratios)
print("tape$ / volumeNum: n", len(rs), "p1 %.3f p5 %.3f p50 %.3f p95 %.3f p99 %.3f" % tuple(rs[int(q * (len(rs) - 1))] for q in (0.01, .05, .5, .95, .99)))
low = sorted(ratios)[:8]; print("lowest", [(round(a, 3), s, n) for a, s, n in low])
big = sorted(ratios, key=lambda x: -x[2])[:5]; print("largest tapes", [(round(a, 3), s, n) for a, s, n in big])
