"""Data checks: outcome vs final/beat price, outcome vs last prints, tape duplicates, tape vs gamma volume."""
import gzip, json, os
from collections import Counter
ROOT = "/home/user/polymarket-lab/data"
T0 = 1795219200; T1 = T0 + 6 * 86400
SER = [("btc","5m",1),("eth","5m",1),("sol","5m",1200),("xrp","5m",1200),("btc","15m",1),("eth","15m",1),
       ("sol","15m",1),("xrp","15m",1),("btc","1h",1),("eth","1h",1),("sol","1h",1),("xrp","1h",1)]
DUR = {"5m": 300, "15m": 900, "1h": 3600}
c = Counter(); upn = Counter(); dup = 0; lowvol = Counter(); lastbad = Counter(); fees = Counter(); ticks = Counter()
for a, d, g in SER:
    for t0 in range(T0, T1, DUR[d]):
        if t0 % g: continue
        m = json.load(open(f"{ROOT}/updown_meta/{a}/{d}/{t0}.json"))
        k = f"{a}-{d}"
        upn[k, m["up_won"]] += 1
        fp, pb = m.get("final_price"), m.get("price_to_beat")
        if fp is not None and pb is not None:
            c[k, "consistent" if (fp >= pb) == m["up_won"] else ("tie" if fp == pb else "MISMATCH")] += 1
        else: c[k, "no_price"] += 1
        fees[m.get("fee_rate"), m.get("fee_type")] += 1; ticks[m.get("tick")] += 1
        rows = [json.loads(x) for x in gzip.open(f"{ROOT}/tape/{m['condition']}.jsonl.gz", "rt")]
        keys = Counter((r["t"], r["s"], r["o"], r["z"], r["p"], r["w"]) for r in rows)
        dup += sum(v - 1 for v in keys.values())
        sh = sum(r["z"] for r in rows)
        if m["volume"] and abs(sh / m["volume"] - 1) > 0.02: lowvol[k] += 1
        # last in-tape print before/after t1 implies winner
        post = [r for r in rows if r["t"] > t0 + DUR[d] + 10]
        late = [r for r in rows if t0 + DUR[d] - 60 <= r["t"] <= t0 + DUR[d] + 3]
        if late:
            r = late[-1]; pu = r["p"] if r["o"] == "Up" else 1 - r["p"]
            if (pu > 0.5) != m["up_won"] and abs(pu - 0.5) > 0.3: lastbad[k] += 1
for k in sorted(c): print(k, c[k])
print("up wins", {k: v for k, v in sorted(upn.items())})
print("dup rows", dup, "| markets with |tape/volume-1|>2%:", dict(lowvol), "| late-print contradicts outcome:", dict(lastbad))
print("fees", dict(fees), "ticks", dict(ticks))
