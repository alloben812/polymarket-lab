"""Step 3: classify every temperature fill by the information state of the station at fill time, and attribute PnL.
States (highest-temperature markets resolved from routine METARs; obs counted as public LAG seconds after their time stamp):
  pre>24h / pre<24h : fill before the station's local day starts
  day-open          : in the local day, running max has not yet reached its final value (genuinely uncertain)
  day-peak-in       : in the local day, running max already equals the final max, bucket not yet impossible
  day-dead          : in the local day, running max already ABOVE the bucket's top -> YES is impossible, NO is certain
  after-day         : local day over, everything is known, market not yet resolved
Usage: python3 -I analyse.py [LAG_SECONDS]"""
import json, re, sys, math, collections, datetime as dt, bisect
LAG = int(sys.argv[1]) if len(sys.argv) > 1 else 300
F = json.load(open("out/fills.json")); M = json.load(open("out/markets.json")); OBS = json.load(open("out/obs2.json"))
FEE_SWITCH = int(dt.datetime(2026, 11, 21, tzinfo=dt.timezone.utc).timestamp())
def ep(s):
    return int(dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())
ITEM = re.compile(r"^(-?\d+)(?:-(-?\d+))?°([CF])( or below| or higher)?$")
def whole(tenths, unit):
    v = tenths / 10.0 if unit == "C" else tenths / 10.0 * 9 / 5 + 32
    return math.floor(v + 0.5 + 1e-9)
MK = {}
for c, m in M.items():
    s = m.get("slug") or ""
    st = re.search(r"ids=(\w+)", m.get("src") or "")
    it = ITEM.match((m.get("item") or "").strip())
    if not (s.startswith("highest-temperature") or s.startswith("lowest-temperature")):
        continue
    d = dict(kind="hi" if s.startswith("highest") else "lo", station=st.group(1) if st else None, ok=bool(st and it and m.get("est")), event=m["event"], slug=s, vol=m.get("vol") or 0)
    if d["ok"]:
        a, b, unit, tail = int(it.group(1)), it.group(2), it.group(3), it.group(4)
        lo, hi = (a, int(b)) if b else (a, a)
        if tail == " or below": lo = -999
        if tail == " or higher": hi = 999
        d.update(lo=lo, hi=hi, unit=unit, est=ep(m["est"]))
    r = m.get("res") or {}
    d["final"] = r.get("final") if r.get("resolved") else None
    MK[c] = d
# running extreme per (station, est, unit, kind)
RUN = {}
def run(station, est, unit, kind):
    k = (station, est, unit, kind)
    if k not in RUN:
        ts, vals = [], []
        cur = None
        for t, v, _ in OBS.get(station, []):
            if v is None or not (est <= t < est + 86400): continue
            w = whole(v, unit)
            cur = w if cur is None else (max(cur, w) if kind == "hi" else min(cur, w))
            ts.append(t); vals.append(cur)
        RUN[k] = (ts, vals)
    return RUN[k]
# validation of the reconstruction against official resolutions
agree = tot = 0; bad = collections.Counter(); evdays = set()
for c, d in MK.items():
    if not d["ok"] or d["final"] is None or d["kind"] != "hi": continue
    ts, vals = run(d["station"], d["est"], d["unit"], d["kind"])
    if not vals: continue
    pred = 1.0 if d["lo"] <= vals[-1] <= d["hi"] else 0.0
    tot += 1; evdays.add(d["event"])
    if pred == d["final"].get("Yes"): agree += 1
    else: bad[d["station"]] += 1
print(f"LAG={LAG}s  reconstruction check: {agree}/{tot} markets agree with official resolution over {len(evdays)} event-days; mismatches by station: {dict(bad.most_common(8))}")
def state(d, t):
    if not d["ok"] or d["kind"] != "hi": return "other-weather", None
    ts, vals = run(d["station"], d["est"], d["unit"], d["kind"])
    if not vals: return "no-obs", None
    if t < d["est"]: return ("pre>24h" if d["est"] - t > 86400 else "pre<24h"), None
    if t >= d["est"] + 86400 + LAG: return "after-day", None
    i = bisect.bisect_right(ts, t - LAG) - 1
    if i < 0: return "day-open", None
    rm, fin = vals[i], vals[-1]
    if rm > d["hi"]:
        j = next(k for k, v in enumerate(vals) if v > d["hi"])
        return "day-dead", t - ts[j]
    if rm == fin:
        j = vals.index(fin)
        return "day-peak-in", t - ts[j]
    return "day-open", None
ORDER = ["pre>24h", "pre<24h", "day-open", "day-peak-in", "day-dead", "after-day", "other-weather", "no-obs", "unresolved"]
rows_out = {}
for acct, fills in F.items():
    agg = collections.defaultdict(lambda: dict(n=0, usd=0.0, net=0.0, fee=0.0, mk=set(), ev=collections.Counter(), px=0.0, sh=0.0, lags=[]))
    rows = []
    for r in fills:
        d = MK.get(r["condition_id"])
        if d is None: continue
        p, sh, t = float(r["price"]), float(r["size"]), int(r["timestamp"]) - 3
        fee = (0.05 if t < FEE_SWITCH else 0.01) * sh * p * (1 - p) if r["role"] == "T" else 0.0
        st, lag = state(d, t)
        fin = d["final"]
        if fin is None or fin.get(r["outcome"]) is None:
            st, pnl = "unresolved", 0.0
        else:
            v = float(fin[r["outcome"]])
            pnl = sh * (v - p) if r["side"] == "BUY" else sh * (p - v)
        longyes = (r["side"] == "BUY") == (r["outcome"] == "Yes")
        rows.append(dict(c=r["condition_id"], t=t, st=st, lag=lag, role=r["role"], side=r["side"], out=r["outcome"], p=p, sh=sh, pnl=pnl - fee, fee=fee, ly=longyes, tx=r["transaction_hash"]))
        for key in ((st, "all"), (st, r["role"]), (st, "LY" if longyes else "LN")):
            a = agg[key]; a["n"] += 1; a["usd"] += sh * p; a["net"] += pnl - fee; a["fee"] += fee; a["mk"].add(r["condition_id"]); a["ev"][d["event"]] += pnl - fee
            a["px"] += p * sh; a["sh"] += sh
            if lag is not None: a["lags"].append(lag)
    rows_out[acct] = rows
    tot_net = sum(a["net"] for (s, k), a in agg.items() if k == "all"); tot_usd = sum(a["usd"] for (s, k), a in agg.items() if k == "all")
    print(f"\n=== {acct}: weather fills {len(rows)}, turnover ${tot_usd:,.0f}, net after calibrated fees ${tot_net:,.0f} ({100*tot_net/max(tot_usd,1):.1f}% of turnover)")
    print(f"{'state':14s}{'sub':4s}{'fills':>6s}{'usd':>9s}{'avg_px':>7s}{'net$':>9s}{'net%':>7s}{'fee$':>7s}{'mkts':>6s}{'evdays':>7s}{'t(evday)':>9s}{'med_lag_h':>10s}")
    for s in ORDER:
        for k in ("all", "T", "M", "LY", "LN"):
            a = agg.get((s, k))
            if not a or (k != "all" and a["n"] < 15): continue
            ev = list(a["ev"].values()); n = len(ev); mu = sum(ev) / n
            se = (sum((x - mu) ** 2 for x in ev) / (n - 1) / n) ** 0.5 if n > 2 else 0
            lagm = sorted(a["lags"])[len(a["lags"]) // 2] / 3600 if a["lags"] else float("nan")
            print(f"{s if k=='all' else '':14s}{k:4s}{a['n']:6d}{a['usd']:9.0f}{a['px']/max(a['sh'],1e-9):7.3f}{a['net']:9.0f}{100*a['net']/max(a['usd'],1e-9):7.1f}{a['fee']:7.0f}{len(a['mk']):6d}{n:7d}{(mu/se if se else float('nan')):9.2f}{lagm:10.2f}")
json.dump(rows_out, open(f"out/rows_lag{LAG}.json", "w"))
json.dump({c: {k: v for k, v in d.items()} for c, d in MK.items()}, open("out/mk.json", "w"))
