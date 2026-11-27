"""Falsification test: when do the accounts trade relative to scheduled releases?
(1) fills in release-event markets vs that event's own release time T; (2) fills in all other economics markets (Fed
decision etc.) vs the nearest preceding major US release."""
import json, sys, pickle, os, collections, calendar, time, re, bisect
sys.path.insert(0, "/home/user/polymarket-lab")
from pmlab import wallet as W
src = open("release_analysis_v2.py").read()
ns = {}
exec("import calendar, time\ndef ts(s): return calendar.timegm(time.strptime(s, '%Y-%m-%d %H:%M'))\n" + src[src.index("SCHED = ["):src.index("OVERRIDE = {")], ns)
sched_T = ns["sched_T"]
ev = json.load(open("release_events.json"))
condT = {}; win = {}
for e in ev:
    T = sched_T(e["slug"])
    for m in e["markets"]:
        if T: condT[m["cond"]] = (T, e["slug"])
        if m.get("prices"):
            pr = [float(x) for x in json.loads(m["prices"])]
            if max(pr) >= 0.99: win[m["cond"]] = ["Yes", "No"][pr.index(max(pr))]
US = sorted({sched_T(p.replace("^", "").split("|")[0].replace("(", "")) or 0 for p in []} | {ns["ts"](t) for pat, t in ns["SCHED"] if re.search(r"unemployment|inflation-us|ppi|pce|ism|fed-decision", pat)})
END = 1795793940; START = END - 88 * 86400
ACC = [("perfectnosta", "0x0ffcad4963e25dc150774363f4061ebe840c8236"), ("GoldmanSachs", "0x71dd2d539a793687451d4af8c43169369b47d61c"), ("ATCapital", "0x7ad3d7e5cda50dbe1fc5c29a1ffc2f61a9232e30"),
       ("Ahpo", "0xcdb1f1ef8213c06911e4ba6a884176c5571e276c"), ("0x831449c4b9", "0x831449c4b94607dd3367023c61525aea99a90b88"), ("Stonktrader", "0x73e35ce0b7e36ef3ce29ebd12b30b28007383239"),
       ("jozeslemsek", "0xd0bf186c69a936395c84d6b45bbd39eadfcf9f9f"), ("TheElement115", "0x8cb3ed8b82e59276ceaef9799287f51dbb450114"), ("road2million", "0x0594680ecb55045909f3f71d93b87d5e836190a5"), ("makeit99", "0x2f633efb75256a2f2445110c8978684ab8936643")]
ECON = re.compile(r"(fed|fomc|interest-rate|rate-cut|rate-hike|bps|cpi|inflation|jobs|payroll|unemployment|gdp|recession|ecb|bank-of-|pce|ppi|treasury|overheating|ism-)", re.I)
B1 = [(-1e12, -86400, "before >1d"), (-86400, -3600, "before 1h-1d"), (-3600, 0, "before <1h"), (0, 60, "after 0-60s"), (60, 1800, "after 1-30min"), (1800, 21600, "after 30min-6h"), (21600, 1e12, "after >6h")]
B2 = [(0, 60, "0-60s"), (60, 1800, "1-30min"), (1800, 21600, "30min-6h")]
res = {}
for label, addr in ACC:
    fp = f"/home/user/polymarket-lab/data/econ_tapes/fills_{label}.pkl"
    if os.path.exists(fp): fills = pickle.load(open(fp, "rb"))
    else:
        fills, _ = W.fetch_fills(addr, START, END, 60000); pickle.dump(fills, open(fp, "wb"))
    a = collections.defaultdict(lambda: [0, 0.0, 0.0]); nm = set(); b = collections.defaultdict(lambda: [0, 0.0]); other_usd = 0.0; all_usd = 0.0
    for r in fills:
        usd = r["size"] * r["price"]; all_usd += usd
        c = r["condition_id"]
        if c in condT:
            T, slug = condT[c]; lag = r["timestamp"] - T
            k = next(n for lo, hi, n in B1 if lo <= lag < hi)
            edge = None
            if c in win:
                fin = 1.0 if r["outcome"] == win[c] else 0.0
                edge = (fin - r["price"]) * r["size"] * (1 if r["side"] == "BUY" else -1)
            x = a[(k, r["role"])]; x[0] += 1; x[1] += usd; x[2] += edge or 0.0; nm.add(c)
        elif ECON.search((r.get("event_slug") or "") + " " + (r.get("slug") or "")):
            other_usd += usd
            i = bisect.bisect_right(US, r["timestamp"]) - 1
            if i >= 0:
                lag = r["timestamp"] - US[i]
                for lo, hi, n in B2:
                    if lo <= lag < hi:
                        y = b[(n, r["role"])]; y[0] += 1; y[1] += usd
    print(f"\n== {label}: all fills {len(fills)}, turnover {all_usd:.0f}; release-event markets touched {len(nm)}")
    for _, _, k in B1:
        for role in "TM":
            if (k, role) in a:
                x = a[(k, role)]; print(f"   own-release {k:15} {role} fills={x[0]:5d} usd={x[1]:9.0f} edge_to_final={x[2]:8.0f}")
    win_frac = len(US) * 21600 / (88 * 86400)
    tot_b = sum(v[1] for v in b.values())
    print(f"   other econ markets (Fed decisions etc.): usd {other_usd:.0f}; within 6h after any of {len(US)} US releases: {tot_b:.0f} = {100*tot_b/other_usd if other_usd else 0:.1f}% (uniform-time baseline {100*win_frac:.1f}%)")
    for _, _, k in B2:
        for role in "TM":
            if (k, role) in b: print(f"      {k:9} {role} fills={b[(k, role)][0]:5d} usd={b[(k, role)][1]:9.0f}")
    res[label] = {"own": {f"{k}|{r}": v for (k, r), v in a.items()}, "other_usd": other_usd, "other_after": {f"{k}|{r}": v for (k, r), v in b.items()}}
json.dump(res, open("timing.json", "w"))
