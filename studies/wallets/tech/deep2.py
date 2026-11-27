"""(A) per-event PnL concentration, (B) entry timing vs market creation, (C) drift after pre-appearance buys (copyability),
(D) what 0xAee8611B's merges are."""
import sys, bisect, collections, statistics as st, pickle, os
from common import *
from race import INFO, JUMP, appearance, pw_rows, check_time
def wq(xs, q):
    xs = sorted(xs); tot = sum(w for _, w in xs); c = 0
    for v, w in xs:
        c += w
        if c >= q * tot: return v
    return float("nan")
def bought_px_at(c, outcome, t):
    rows = pw_rows(c); i = bisect.bisect_right([r[0] for r in rows], t) - 1
    if i < 0: return None
    return rows[i][1] if outcome == INFO[c]["winner"] else 1 - rows[i][1]
for name in ["iutwpfal", "NoTeacher", "lamyk", "KimchiCapital", "fountaim", "0xAee8611B"]:
    d = load(name); ms = d["_markets"]; bym = {m["condition"]: m for m in ms}
    print(f"\n===== {name}")
    # (A) per event, tech arena/hle resolved markets (net after estimated fee; incomplete markets flagged)
    ev = collections.defaultdict(lambda: [0.0, 0, 0, 0.0])
    for m in ms:
        if m["sub"] in ("arena", "hle") and m["resolved"]:
            e = ev[m["event"]]; e[0] += m["net"]; e[1] += 1; e[2] += m["incomplete"]; e[3] += m["turnover"]
    rows = sorted(ev.items(), key=lambda x: -x[1][0]); tot = sum(v[0] for _, v in rows); pos = sum(1 for _, v in rows if v[0] > 0)
    print(f"(A) resolved arena+hle events {len(rows)}: net {tot:.0f}; positive {pos}; top3 {sum(v[0] for _, v in rows[:3]):.0f}; bottom3 {sum(v[0] for _, v in rows[-3:]):.0f}; median event {st.median(v[0] for _, v in rows):.0f}")
    for e, v in rows[:6] + rows[-3:]:
        print(f"      {v[0]:8.0f}  mk {v[1]:3d} inc {v[2]:2d} turnover {v[3]:7.0f}  {e[:75]}")
    wk = collections.defaultdict(float)
    for m in ms:
        if m["sub"] in ("arena", "hle") and m["resolved"] and m.get("closed_at"): wk[dt.datetime.fromtimestamp(m["closed_at"], dt.timezone.utc).strftime("%m")] += m["net"]
    print("    arena+hle net by month of close: " + " ".join(f"{k}:{v:.0f}" for k, v in sorted(wk.items())))
    # (B) + (C)
    age = []; drift = collections.defaultdict(list); lead = []
    for r in d["_fills"]:
        c = r["condition_id"]; m = bym[c]
        if m["sub"] not in ("arena", "hle") or r["side"] != "BUY" or r["role"] != "T": continue
        u = float(r["size"]) * float(r["price"])
        if m.get("created"): age.append(((r["timestamp"] - m["created"]) / 86400, u))
        if c in JUMP and "debut" in (m["event"] or "") and appearance(c) and r["timestamp"] < appearance(c) - 3600:
            lead.append(((appearance(c) - r["timestamp"]) / 86400, u))
            for lab, dtm in (("+10m", 600), ("+1h", 3600), ("+24h", 86400)):
                if r["timestamp"] + dtm < appearance(c):
                    p = bought_px_at(c, r["outcome"], r["timestamp"] + dtm)
                    if p is not None: drift[lab].append((p - float(r["price"]), u, c))
            val = 1.0 if r["outcome"] == INFO[c]["winner"] else 0.0
            drift["settle"].append((val - float(r["price"]), u, c))
    if age: print(f"(B) taker buys, days after market creation ($-weighted q10/q50/q90): {wq(age,.1):.1f}/{wq(age,.5):.1f}/{wq(age,.9):.1f}; pre-appearance buys, days before appearance q10/q50/q90: " + (f"{wq(lead,.1):.1f}/{wq(lead,.5):.1f}/{wq(lead,.9):.1f} (n={len(lead)})" if lead else "none"))
    for lab in ("+10m", "+1h", "+24h", "settle"):
        x = drift.get(lab)
        if x:
            tu = sum(u for _, u, _ in x); mk = len({c for _, _, c in x})
            print(f"(C) pre-appearance taker buys: tape price of the bought side {lab} minus fill price, $-weighted mean {100*sum(dp*u for dp, u, _ in x)/tu:+.1f}c (fills {len(x)}, markets {mk}, ${tu:.0f})")
# (D)
name = "0xAee8611B"; d = load(name); bym = {m["condition"]: m for m in d["_markets"]}
fp = f"{DATA}/inv_{name}.pkl"
if os.path.exists(fp): inv = pickle.load(open(fp, "rb"))
else:
    inv = W.fetch_inventory_events(ACC[name], START, END); pickle.dump(inv, open(fp, "wb"))
print(f"\n===== (D) {name}: inventory events {collections.Counter(r.get('type') for r in inv)}; merged shares {sum(float(r.get('size') or 0) for r in inv if r.get('type')=='MERGE'):.0f}, split {sum(float(r.get('size') or 0) for r in inv if r.get('type')=='SPLIT'):.0f}, redeemed usd {sum(float(r.get('usdc_size') or 0) for r in inv if r.get('type')=='REDEEM'):.0f}")
by = collections.defaultdict(list)
for r in d["_fills"]: by[r["condition_id"]].append(r)
pair = []; gaps = []; tot_m = 0
for c, fs_ in by.items():
    y = [(float(r["price"]), float(r["size"]), r["timestamp"], r["role"]) for r in fs_ if r["side"] == "BUY" and r["outcome"] == "Yes"]
    n = [(float(r["price"]), float(r["size"]), r["timestamp"], r["role"]) for r in fs_ if r["side"] == "BUY" and r["outcome"] == "No"]
    if y and n:
        sy, sn = sum(s for _, s, _, _ in y), sum(s for _, s, _, _ in n); k = min(sy, sn)
        py, pn = sum(p * s for p, s, _, _ in y) / sy, sum(p * s for p, s, _, _ in n) / sn
        pair.append((py + pn, k, c)); tot_m += k
        gaps.append((abs(st.median(t for _, _, t, _ in y) - st.median(t for _, _, t, _ in n)) / 3600, k))
print(f"markets where it bought both Yes and No: {len(pair)} of {len(by)}; matched shares {tot_m:.0f}; avg cost of a Yes+No pair, share-weighted: {sum(p*k for p,k,_ in pair)/tot_m:.4f}; q10/q50/q90 {wq([(p,k) for p,k,_ in pair],.1):.3f}/{wq([(p,k) for p,k,_ in pair],.5):.3f}/{wq([(p,k) for p,k,_ in pair],.9):.3f}; share of pairs under 1.00: {sum(k for p,k,_ in pair if p<1)/tot_m:.2f}")
print(f"hours between median Yes buy and median No buy, share-weighted q25/q50/q75: {wq(gaps,.25):.1f}/{wq(gaps,.5):.1f}/{wq(gaps,.75):.1f}")
# bursts: fills per second and markets per burst
sec = collections.defaultdict(set); 
for r in d["_fills"]: sec[r["timestamp"] // 10].add(r["condition_id"])
sizes = sorted(len(v) for v in sec.values())
print(f"10-second buckets with fills: {len(sizes)}; markets per bucket q50/q90/max: {sizes[len(sizes)//2]}/{sizes[int(len(sizes)*.9)]}/{sizes[-1]}; fills in buckets touching >=3 markets: {sum(1 for r in d['_fills'] if len(sec[r['timestamp']//10])>=3)} of {len(d['_fills'])}")
hours = collections.Counter(dt.datetime.fromtimestamp(r["timestamp"], dt.timezone.utc).hour for r in d["_fills"])
print("fills by UTC hour: " + " ".join(f"{h}:{hours[h]}" for h in range(24)))
days = collections.Counter(dt.datetime.fromtimestamp(r["timestamp"], dt.timezone.utc).strftime("%m-%d") for r in d["_fills"])
print(f"active days {len(days)} of 88; fills/day median {st.median(days.values())}; turnover by sub and role:")
ev = collections.defaultdict(lambda: collections.defaultdict(float))
for r in d["_fills"]:
    e = re.sub(r"-(september|october|november|december|january|february|march).*$|-20\d{6,}.*$", "", bym[r["condition_id"]]["event"] or ""); u = float(r["size"]) * float(r["price"])
    ev[e]["usd"] += u; ev[e][r["side"] + r["role"]] += u; ev[e]["n"] += 1
for e, v in sorted(ev.items(), key=lambda x: -x[1]["usd"])[:14]:
    print(f"   {v['usd']:8.0f} fills {int(v['n']):5d} buyT {v['BUYT']:7.0f} buyM {v['BUYM']:7.0f} sellT {v['SELLT']:7.0f} sellM {v['SELLM']:6.0f}  {e[:70]}")
