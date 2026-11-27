"""For every account: taker purchases of NO (or sales of YES) timed against the routine report that made the bucket impossible
(report time from the merged AWC+IEM series) and against the moment aviationweather.gov says it RECEIVED that report."""
import json, sys, bisect, collections, datetime as dt, math
F = json.load(open("out/fills.json")); MK = json.load(open("out/mk.json")); OBS = json.load(open("out/obs2.json")); REC = json.load(open("out/receipt.json"))
FEE_SWITCH = dt.datetime(2026, 11, 21, tzinfo=dt.timezone.utc).timestamp()
def whole(t, unit):
    v = t / 10.0 if unit == "C" else t / 10.0 * 9 / 5 + 32
    return math.floor(v + 0.5 + 1e-9)
edges = [-1e9, -1800, -300, 0, 60, 180, 600, 1800, 7200, 1e9]
lab = ["<-30m", "-30..-5m", "-5..0m", "0..1m", "1..3m", "3..10m", "10..30m", "30m..2h", ">2h"]
kc = {}
def kill(d):
    k = (d["station"], d["est"], d["unit"], d["hi"])
    if k not in kc:
        kc[k] = next((t for t, v, _ in OBS.get(d["station"], []) if v is not None and d["est"] <= t < d["est"] + 86400 and whole(v, d["unit"]) > d["hi"]), None)
    return kc[k]
for acct, fills in F.items():
    tab = collections.defaultdict(lambda: [0, 0.0, 0.0, set()]); rcv = []; us = collections.Counter(); tot = [0, 0.0, 0.0]
    for r in fills:
        d = MK.get(r["condition_id"])
        if not d or not d["ok"] or d["kind"] != "hi" or d["final"] is None: continue
        longno = (r["side"] == "BUY") == (r["outcome"] == "No")
        if not longno or r["role"] != "T": continue
        k = kill(d); t = r["timestamp"] - 3
        if k is None or not (d["est"] <= t < d["est"] + 86400): continue
        p, sh = float(r["price"]), float(r["size"]); v = float(d["final"][r["outcome"]])
        pnl = (sh * (v - p) if r["side"] == "BUY" else sh * (p - v)) - (0.05 if t < FEE_SWITCH else 0.01) * sh * p * (1 - p)
        b = lab[bisect.bisect_right(edges, t - k) - 1]
        a = tab[b]; a[0] += 1; a[1] += sh * p; a[2] += pnl; a[3].add(r["condition_id"])
        if -300 <= t - k < 600:
            us["US" if d["station"].startswith("K") else "intl"] += 1
            rc = REC.get(d["station"], {}).get(str(k))
            if rc: rcv.append(t - rc)
    print(f"\n{acct}: taker long-NO fills inside the local day on buckets that a routine report eventually exceeded")
    print("  fill minus report time : " + "  ".join(f"{b}: n={tab[b][0]} ${tab[b][1]:.0f} net${tab[b][2]:.0f} mk={len(tab[b][3])}" for b in lab if tab[b][0]))
    rcv.sort()
    if rcv: print(f"  within -5..+10 min of the report: {dict(us)}; fill minus AWC receipt time (n={len(rcv)}): median {rcv[len(rcv)//2]:.0f}s, p10 {rcv[len(rcv)//10]:.0f}s, p90 {rcv[9*len(rcv)//10]:.0f}s; share filled BEFORE AWC had the report: {sum(1 for x in rcv if x < 0)/len(rcv):.0%}")
