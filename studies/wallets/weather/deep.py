"""Deeper cuts.  (1) in-day fills by local hour x direction x position of the bucket relative to the running max at fill time.
(2) pair/merge decomposition for accounts that buy both outcomes.  (3) who is on the other side: shared transaction hashes.
(4) sizing, concurrency, exits.   python3 -I deep.py"""
import json, bisect, collections, datetime as dt, math, statistics as S
F = json.load(open("out/fills.json")); MK = json.load(open("out/mk.json")); OBS = json.load(open("out/obs2.json"))
FEE_SWITCH = dt.datetime(2026, 11, 21, tzinfo=dt.timezone.utc).timestamp()
def whole(t, unit):
    v = t / 10.0 if unit == "C" else t / 10.0 * 9 / 5 + 32
    return math.floor(v + 0.5 + 1e-9)
RUN = {}
def run(d):
    k = (d["station"], d["est"], d["unit"])
    if k not in RUN:
        ts, vals, cur = [], [], None
        for t, v, _ in OBS.get(d["station"], []):
            if v is None or not (d["est"] <= t < d["est"] + 86400): continue
            w = whole(v, d["unit"]); cur = w if cur is None else max(cur, w); ts.append(t); vals.append(cur)
        RUN[k] = (ts, vals)
    return RUN[k]
def pnl_of(r, d):
    p, sh = float(r["price"]), float(r["size"]); v = float(d["final"][r["outcome"]])
    fee = (0.05 if r["timestamp"] < FEE_SWITCH else 0.01) * sh * p * (1 - p) if r["role"] == "T" else 0
    return (sh * (v - p) if r["side"] == "BUY" else sh * (p - v)) - fee
print("##### (1) in-day fills: local hour x direction x bucket position vs running max (step = 1 bucket width; 'dead' = already exceeded)")
for acct in ["241532532432", "haiwenxiang", "Lex-tang", "edgewarehouse", "HighTempTation"]:
    tab = collections.defaultdict(lambda: [0, 0.0, 0.0, set()])
    for r in F[acct]:
        d = MK.get(r["condition_id"])
        if not d or not d["ok"] or d["kind"] != "hi" or d["final"] is None: continue
        t = r["timestamp"] - 3
        if not (d["est"] <= t < d["est"] + 86400): continue
        ts, vals = run(d)
        i = bisect.bisect_right(ts, t) - 1
        if i < 0: continue
        rm = vals[i]; width = (d["hi"] - d["lo"] + 1) if -900 < d["lo"] and d["hi"] < 900 else 1
        pos = "dead" if rm > d["hi"] else ("holds-max" if rm >= d["lo"] else ("next-up" if d["lo"] - rm <= width else "2+up"))
        lh = (t - d["est"]) / 3600; hb = "00-09" if lh < 9 else "09-12" if lh < 12 else "12-15" if lh < 15 else "15-18" if lh < 18 else "18-24"
        ly = (r["side"] == "BUY") == (r["outcome"] == "Yes")
        for key in ((hb, "LY" if ly else "LN", pos), ("all", "LY" if ly else "LN", pos)):
            a = tab[key]; a[0] += 1; a[1] += float(r["size"]) * float(r["price"]); a[2] += pnl_of(r, d); a[3].add(r["condition_id"])
    print(f"\n{acct}")
    for hb in ["00-09", "09-12", "12-15", "15-18", "18-24", "all"]:
        cells = []
        for dirn in ("LY", "LN"):
            for pos in ("dead", "holds-max", "next-up", "2+up"):
                a = tab.get((hb, dirn, pos))
                if a and a[0] >= 10: cells.append(f"{dirn}/{pos}: n={a[0]} ${a[1]:.0f} net${a[2]:.0f} mk={len(a[3])}")
        print(f"  local {hb}h | " + " | ".join(cells))
print("\n##### (2) both-outcome pairs (merge decomposition), resolved hi/lo temperature markets")
for acct in ["241532532432", "OnlyLuckNoBrain", "edgewarehouse", "Lex-tang", "haiwenxiang"]:
    bym = collections.defaultdict(lambda: {"Yes": [0.0, 0.0], "No": [0.0, 0.0], "sell": 0.0, "roles": collections.Counter(), "ts": {"Yes": [], "No": []}})
    for r in F[acct]:
        if r["condition_id"] not in MK: continue
        b = bym[r["condition_id"]]
        if r["side"] == "BUY":
            b[r["outcome"]][0] += float(r["size"]); b[r["outcome"]][1] += float(r["size"]) * float(r["price"]); b["ts"][r["outcome"]].append(r["timestamp"]); b["roles"][r["role"] + r["outcome"]] += float(r["size"])
        else: b["sell"] += float(r["size"]) * float(r["price"])
    n = pairs = 0; locked = cost_sum = sh_sum = 0.0; gaps = []; buyusd = 0.0
    for c, b in bym.items():
        y, no = b["Yes"], b["No"]; buyusd += y[1] + no[1]
        m = min(y[0], no[0])
        if m < 1: continue
        pc = y[1] / y[0] + no[1] / no[0]; pairs += 1; locked += m * (1 - pc); cost_sum += pc * m; sh_sum += m
        gaps.append(abs(S.median(b["ts"]["Yes"]) - S.median(b["ts"]["No"])) / 3600)
    if pairs:
        print(f"{acct}: markets with >=1 matched pair {pairs}/{len(bym)}; matched shares {sh_sum:.0f}; avg pair cost {cost_sum/sh_sum:.4f}; locked before fees ${locked:.0f}; median hours between the YES leg and the NO leg {S.median(gaps):.1f}; buys total ${buyusd:.0f}")
print("\n##### (3) counterparties inside this set: taker account x maker account sharing a transaction hash (weather only)")
idx = collections.defaultdict(list)
for acct, fills in F.items():
    for r in fills:
        if r["condition_id"] in MK: idx[(r["transaction_hash"], r["condition_id"])].append((acct, r["role"], float(r["size"]) * float(r["price"])))
pair = collections.Counter(); pairusd = collections.Counter()
for k, v in idx.items():
    tk = [x for x in v if x[1] == "T"]; mk = [x for x in v if x[1] == "M"]
    for a in tk:
        for b in mk:
            if a[0] != b[0]: pair[(a[0], b[0])] += 1; pairusd[(a[0], b[0])] += b[2]
for k, n in pair.most_common(15): print(f"  taker {k[0]:16s} <- maker {k[1]:16s}: {n} tx, maker-side ${pairusd[k]:.0f}")
print("\n##### (4) sizing / concurrency / exits (temperature markets)")
for acct, fills in F.items():
    per_m = collections.Counter(); per_ev = collections.Counter(); evday = collections.defaultdict(set); sells = buys = 0.0; fs = []
    for r in fills:
        d = MK.get(r["condition_id"])
        if not d: continue
        u = float(r["size"]) * float(r["price"]); per_m[r["condition_id"]] += u; per_ev[d["event"]] += u; fs.append(u)
        evday[dt.datetime.fromtimestamp(r["timestamp"], dt.timezone.utc).strftime("%m-%d")].add(d["event"])
        if r["side"] == "SELL": sells += u
        else: buys += u
    q = lambda xs, p: sorted(xs)[int(p * (len(xs) - 1))]
    print(f"{acct:16s} fill$ med {q(fs,.5):.1f} p90 {q(fs,.9):.0f} max {max(fs):.0f} | per market$ med {q(list(per_m.values()),.5):.0f} p90 {q(list(per_m.values()),.9):.0f} | per event$ med {q(list(per_ev.values()),.5):.0f} p90 {q(list(per_ev.values()),.9):.0f} | events touched per UTC day med {S.median(len(v) for v in evday.values()):.0f} | sells/buys {sells/max(buys,1):.2f} | markets {len(per_m)} events {len(per_ev)}")
