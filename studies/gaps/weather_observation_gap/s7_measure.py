"""Steps 6-7: O1 dead buckets, O2 lock-in, O3 rules (12 variants), O4 risk. See protocol.md.
Usage: s7_measure.py [--slice]   (--slice = NYC 2026-11-10..16 sanity run, prints checks)
Writes data/gaps_weather_obs/out_<tag>.json and prints tables."""
import bisect, collections, datetime as dt, gzip, json, math, os, statistics as st, sys
sys.path.insert(0, "/home/user/polymarket-lab")
sys.path.insert(0, "/home/user/polymarket-lab/studies/gaps/weather_observation_gap")
from pmlab import stats
from common import *

SLICE = "--slice" in sys.argv
TAG = "slice" if SLICE else "full"
M = load_markets()
if SLICE:
    M = [e for e in M if e["city"] == "nyc" and "2026-11-10" <= e["date"] <= "2026-11-16"]
OBS3, OBS4 = {}, {}
for e in M:
    if e["icao"] not in OBS3:
        OBS3[e["icao"]] = load_obs(e["icao"], 3); OBS4[e["icao"]] = load_obs(e["icao"], 4)


def load_px(cond):
    p = f"{DATA}/px/{cond}.json.gz"
    if not os.path.exists(p):
        return None
    d = json.load(gzip.open(p, "rt"))
    return {k: ([x[0] for x in v], [x[1] for x in v]) for k, v in d.items()}


def load_tape(cond):
    p = f"{DATA}/tape/{cond}.jsonl.gz"
    if not os.path.exists(p):
        return None
    return [json.loads(l) for l in gzip.open(p, "rt")]


def px_at(series, T):
    if not series or not series[0]:
        return None
    i = bisect.bisect_right(series[0], T) - 1
    return None if i < 0 else series[1][i]


def yes_buyable(r):  # price at which YES was buyable according to this print, or None
    if r["s"] == "BUY" and r["o"] == "Yes":
        return r["p"]
    if r["s"] == "SELL" and r["o"] == "No":
        return 1.0 - r["p"]
    return None


def no_buyable(r):
    if r["s"] == "BUY" and r["o"] == "No":
        return r["p"]
    if r["s"] == "SELL" and r["o"] == "Yes":
        return 1.0 - r["p"]
    return None


def first_print(tape, T, fn, window=1800):
    """first print with match time in [T, T+window] for which fn(row) is not None -> (match_time, price, size)"""
    for r in tape:
        mt = r["t"] - BLOCK_LAG
        if mt < T:
            continue
        if mt > T + window:
            return None
        p = fn(r)
        if p is not None:
            return mt, p, r["z"]
    return None


def period_of(e):
    return "Oct" if e["date"] < "2026-11-01" else "Nov"


A_DELAYS = [5, 15, 60]
B_HOURS = [19, 21, 23]
B_CAPS = [0.80, 0.90, 0.95]
O2_HOURS = [17, 19, 21, 23]
O1_OFFS = [5, 15, 60]

o1 = []          # one row per (kill report, newly dead bucket)
o2 = []          # one row per (event, hour)
entries = []     # O3 fills
risk_revived, risk_lock = [], []
missing = collections.Counter()
sanity = collections.Counter()
calib = []       # (price, won) of taker BUY-Yes prints at 0.40-0.60
stamp_chk = {"start": [], "end": []}
sum_chk = []
dup_diff = []

for ei, e in enumerate(M):
    key = e["slug"]
    per = period_of(e)
    bks = e["buckets"]
    rng = [(b["lo"], b["hi"]) for b in bks]
    win = next(i for i, b in enumerate(bks) if b["won"])
    rep = [r for r in OBS3[e["icao"]] if e["day0"] <= r["t"] < e["day1"] and r["f"] is not None]
    for r in rep:
        if r["dup"] and parse_value(r["dup"])[0] != r["c10"]:
            dup_diff.append((key, iso(r["t"]), r["dup"], r["raw"]))
    PX = [load_px(b["cond"]) for b in bks]
    TP = [load_tape(b["cond"]) for b in bks]
    for i, b in enumerate(bks):
        if PX[i] is None:
            missing["px file"] += 1
        if TP[i] is None:
            missing["tape file"] += 1; TP[i] = []
        elif not TP[i]:
            missing["empty tape"] += 1
    yes = [(p["yes"] if p else None) for p in PX]
    # ---- sanity material
    for i, b in enumerate(bks):
        if PX[i] and PX[i]["yes"][0] and PX[i]["no"][0]:
            for T in (e["day0"] + 6 * 3600, e["day0"] + 12 * 3600, e["day0"] + 18 * 3600):
                a, c = px_at(PX[i]["yes"], T), px_at(PX[i]["no"], T)
                if a is not None and c is not None:
                    sum_chk.append(a + c)
        for r in TP[i]:
            if r["s"] == "BUY" and r["o"] == "Yes" and 0.40 <= r["p"] <= 0.60:
                calib.append((key, r["p"], b["won"], r["z"]))
        if SLICE and PX[i] and TP[i]:
            # stamp meaning: compare px(t) with last YES-equivalent trade price at <= t and at <= t+300
            tt = [r["t"] for r in TP[i]]
            yp = [(r["p"] if r["o"] == "Yes" else 1 - r["p"]) for r in TP[i]]
            ts_, ps_ = PX[i]["yes"]
            for t, p in zip(ts_, ps_):
                if t % 300:
                    continue
                j0 = bisect.bisect_right(tt, t) - 1; j1 = bisect.bisect_right(tt, t + 300) - 1
                if j0 >= 0 and j1 > j0:  # a trade happened inside [t, t+300)
                    stamp_chk["start"].append(abs(p - yp[j0])); stamp_chk["end"].append(abs(p - yp[j1]))
    # ---- O1 kills
    runmax = None; dead_at = {}
    for k, r in enumerate(rep):
        if runmax is not None and r["f"] <= runmax:
            continue
        prev = runmax; runmax = r["f"]
        pub = r["t"] + PUBLIC_LAG
        for i, b in enumerate(bks):
            if b["hi"] is None or b["hi"] >= runmax or i in dead_at:
                continue
            dead_at[i] = r
            row = {"key": key, "city": e["city"], "date": e["date"], "per": per, "regime": e["regime"], "bucket": b["title"], "bi": i, "obs_t": r["t"], "pub": pub,
                   "first": k == 0, "f": r["f"], "prev": prev, "won": b["won"], "raw": r["raw"],
                   "pre": px_at(yes[i], r["t"]) if yes[i] else None}
            for off in O1_OFFS:
                row[f"p{off}"] = px_at(yes[i], pub + off * 60) if yes[i] else None
            row["p0"] = px_at(yes[i], pub) if yes[i] else None
            # time until YES price first < 0.02 after obs (minutes relative to public time)
            fix = None
            if yes[i]:
                j = bisect.bisect_right(yes[i][0], r["t"])
                while j < len(yes[i][0]):
                    if yes[i][1][j] < 0.02:
                        fix = (yes[i][0][j] - pub) / 60.0; break
                    j += 1
            row["fix_min"] = fix
            # tape after obs
            dumb_sh = dumb_usd = 0.0
            stale = collections.defaultdict(lambda: [0.0, 0.0, 0])  # bin -> shares, usd profit, prints
            for tr in TP[i]:
                mt = tr["t"] - BLOCK_LAG
                if mt < r["t"]:
                    continue
                yb = yes_buyable(tr)
                if yb is not None:           # a taker paid yb for dead YES (or sold NO at 1-yb)
                    if mt >= pub:
                        dumb_sh += tr["z"]; dumb_usd += tr["z"] * yb
                else:                        # taker sold YES at p / bought NO at 1-p
                    pyes = 1.0 - no_buyable(tr)
                    if pyes >= 0.02:
                        dtm = (mt - pub) / 60.0
                        bn = "pre" if dtm < 0 else "0-5" if dtm < 5 else "5-15" if dtm < 15 else "15-60" if dtm < 60 else "60+"
                        s_ = stale[bn]; s_[0] += tr["z"]; s_[1] += tr["z"] * pyes; s_[2] += 1
            row["dumb_sh"], row["dumb_usd"] = dumb_sh, dumb_usd
            row["stale"] = {k2: v for k2, v in stale.items()}
            o1.append(row)
            if b["won"]:
                risk_revived.append({"key": key, "bucket": b["title"], "killed_by": r["raw"], "obs": iso(r["t"]), "f": r["f"],
                                     "official": bks[win]["title"], "regime": e["regime"]})
            # ---- Rule A
            for d in A_DELAYS:
                T = pub + d * 60
                fp = first_print(TP[i], T, no_buyable)
                sanity[f"A{d} candidates"] += 1
                if fp is None:
                    sanity[f"A{d} no print"] += 1; continue
                mt, p, z = fp
                if p > 0.97 + 1e-9:
                    sanity[f"A{d} first print above 0.97"] += 1; continue
                sh = min(z, 50.0 / p) if p > 0 else z
                pay = 1 - b["won"]
                fee = FEE * p * (1 - p)
                entries.append({"var": f"A d={d}", "key": key, "per": per, "city": e["city"], "date": e["date"], "bucket": b["title"], "T": T, "mt": mt, "p": p, "sh": sh,
                                "pay": pay, "fee": fee, "net": pay - p - fee, "first": k == 0, "day0": e["day0"], "day1": e["day1"], "closed": e["closed_ts"]})
    # ---- O2 lock and Rule B
    date = dt.date.fromisoformat(e["date"])
    for h in O2_HOURS:
        T = local_clock(e["city"], date, h)
        vis = [r for r in rep if r["t"] + PUBLIC_LAG <= T]
        if not vis:
            missing[f"O2 no report by {h}"] += 1; continue
        mx = max(r["f"] for r in vis)
        li = bucket_index(rng, mx)
        up = li + 1 if li + 1 < len(bks) else None
        later = [r for r in rep if r["t"] + PUBLIC_LAG > T]
        row = {"key": key, "city": e["city"], "date": e["date"], "per": per, "regime": e["regime"], "h": h, "T": T, "mx": mx, "lock": bks[li]["title"],
               "lock_won": bks[li]["won"], "up_won": (bks[up]["won"] if up is not None else None), "winner": bks[win]["title"],
               "lock_px": px_at(yes[li], T) if yes[li] else None, "up_px": (px_at(yes[up], T) if (up is not None and yes[up]) else None),
               "win_minus_lock": win - li}
        o2.append(row)
        if not bks[li]["won"]:
            sp = [r for r in OBS4[e["icao"]] if T - PUBLIC_LAG < r["t"] < e["day1"] and r["f"] is not None]
            risk_lock.append({**{k2: row[k2] for k2 in ("key", "h", "mx", "lock", "winner", "lock_px", "regime")},
                              "final_my_max": max(r["f"] for r in rep),
                              "later_routine": [(iso(r["t"]), r["f"], r["raw"]) for r in later],
                              "later_special": [(iso(r["t"]), r["f"], r["raw"]) for r in sp]})
        if h in B_HOURS:
            fp = first_print(TP[li], T, yes_buyable)
            for cap in B_CAPS:
                v = f"B h={h} cap={cap:.2f}"
                sanity[f"{v} candidates"] += 1
                if fp is None:
                    sanity[f"{v} no print"] += 1; continue
                mt, p, z = fp
                if p > cap + 1e-9:
                    sanity[f"{v} first print above cap"] += 1; continue
                sh = min(z, 50.0 / p) if p > 0 else z
                pay = bks[li]["won"]
                fee = FEE * p * (1 - p)
                entries.append({"var": v, "key": key, "per": per, "city": e["city"], "date": e["date"], "bucket": bks[li]["title"], "T": T, "mt": mt, "p": p, "sh": sh,
                                "pay": pay, "fee": fee, "net": pay - p - fee, "first": False, "day0": e["day0"], "day1": e["day1"], "closed": e["closed_ts"]})
    if ei % 50 == 0:
        print("..", ei, len(M), file=sys.stderr, flush=True)

# ================= output =================
def pct(a, b):
    return "  n/a" if not b else f"{100*a/b:5.1f}%"


def med(xs):
    xs = [x for x in xs if x is not None]
    return float("nan") if not xs else st.median(xs)


def mean(xs):
    xs = [x for x in xs if x is not None]
    return float("nan") if not xs else sum(xs) / len(xs)


print(f"\n===== {TAG}: {len(M)} city-days, {sum(len(e['buckets']) for e in M)} markets; missing: {dict(missing)}")
print("duplicate-time reports with different values:", len(dup_diff))
for d in dup_diff[:20]:
    print("   ", d)

# ---- sanity
print("\n--- sanity")
if sum_chk:
    print(f"YES+NO price sum: n={len(sum_chk)} mean={mean(sum_chk):.4f} min={min(sum_chk):.3f} max={max(sum_chk):.3f} share within 0.01 of 1: {pct(sum(abs(x-1)<=0.01 for x in sum_chk), len(sum_chk))}")
if calib:
    byk = collections.defaultdict(lambda: [0.0, 0.0])
    for k_, p, w, z in calib:
        byk[k_][0] += z * (w - p); byk[k_][1] += z
    r_, se_, t_ = stats.ratio_cluster([v[0] for v in byk.values()], [v[1] for v in byk.values()])
    print(f"taker BUY-Yes prints at 0.40-0.60: n={len(calib)} mean price={mean([c[1] for c in calib]):.3f} win rate={mean([c[2] for c in calib]):.3f} "
          f"(share-weighted edge {100*r_:.2f}c, se {100*se_:.2f}, {len(byk)} city-days)")
if stamp_chk["start"]:
    print(f"prices-history stamp vs tape (buckets with a trade inside): |px(t) - last trade <= t| mean={mean(stamp_chk['start']):.4f}; "
          f"|px(t) - last trade <= t+300| mean={mean(stamp_chk['end']):.4f}; n={len(stamp_chk['start'])}")
bad_fee = sum(1 for x in entries if abs(x["fee"] - 0.01 * x["p"] * (1 - x["p"])) > 1e-12)
bad_win = sum(1 for x in entries if not (x["T"] <= x["mt"] <= x["T"] + 1800))
bad_usd = sum(1 for x in entries if x["sh"] * x["p"] > 50.0001)
bad_day = sum(1 for x in entries if x["var"].startswith("B") and not (x["day0"] <= x["T"] < x["day1"]))
after_close = sum(1 for x in entries if x["mt"] > x["closed"])
print(f"entries={len(entries)} fee formula violations={bad_fee} prints outside [T,T+1800]={bad_win} entries above $50={bad_usd} "
      f"rule-B decision outside local day={bad_day} entries after closedTime={after_close}")
print("candidate funnel:", {k: v for k, v in sorted(sanity.items())})

# ---- O1
print("\n--- O1 dead buckets (one row per newly dead bucket)")
def o1_table(rows, label):
    n = len(rows)
    if not n:
        print(f"{label}: n=0"); return
    line = f"{label:44s} n={n:5d}"
    for nm in ("pre", "p0", "p5", "p15", "p60"):
        v = [r[nm] for r in rows if r[nm] is not None]
        line += f" | {nm}: med {med(v):.3f} >=.02 {pct(sum(x>=0.02 for x in v), len(v))} >=.05 {pct(sum(x>=0.05 for x in v), len(v))}"
    print(line)
for per in ("Oct", "Nov", None):
    rr = [r for r in o1 if per is None or r["per"] == per]
    tag = per or "all"
    o1_table(rr, f"{tag} all dead buckets")
    o1_table([r for r in rr if r["first"]], f"{tag} killed by first report of day")
    o1_table([r for r in rr if not r["first"]], f"{tag} killed by a later report")
    o1_table([r for r in rr if r["pre"] is not None and r["pre"] >= 0.05], f"{tag} live before kill (pre >= 0.05)")
    o1_table([r for r in rr if r["pre"] is not None and r["pre"] >= 0.05 and not r["first"]], f"{tag} live before kill, later report")
live = [r for r in o1 if r["pre"] is not None and r["pre"] >= 0.05]
fx = [r["fix_min"] for r in live if r["fix_min"] is not None]
if fx:
    q = sorted(fx)
    print(f"live-before-kill buckets: minutes from public time until YES history first < 0.02: n={len(fx)} of {len(live)} "
          f"p10={q[int(.1*len(q))]:.0f} median={med(q):.0f} p75={q[int(.75*len(q))]:.0f} p90={q[int(.9*len(q))]:.0f} max={q[-1]:.0f}; share fixed by public time: {pct(sum(x<=0 for x in fx), len(live))}")
for per in ("Oct", "Nov"):
    rr = [r for r in o1 if r["per"] == per]
    nd = len({r["date"] for r in rr}) or 1
    print(f"{per}: (a) takers paying for dead YES after public time: {sum(r['dumb_sh'] for r in rr):,.0f} shares, ${sum(r['dumb_usd'] for r in rr):,.0f} "
          f"(${sum(r['dumb_usd'] for r in rr)/nd:,.1f}/day over {nd} days); buckets with any: {sum(1 for r in rr if r['dumb_usd']>0)}/{len(rr)}")
    line = f"{per}: (b) stale dead-bucket liquidity taken (YES sold at >= 0.02 / NO bought <= 0.98), profit locked before fee:"
    for bn in ("pre", "0-5", "5-15", "15-60", "60+"):
        sh = sum(r["stale"].get(bn, [0, 0, 0])[0] for r in rr); usd = sum(r["stale"].get(bn, [0, 0, 0])[1] for r in rr); npr = sum(r["stale"].get(bn, [0, 0, 0])[2] for r in rr)
        line += f" [{bn} min: ${usd:,.0f}, {sh:,.0f} sh, {npr} prints]"
    print(line)

# ---- O2
print("\n--- O2 lock-in: bucket holding the running maximum at local hour")
print("hour per  city             n  lock wins  next-up wins   lock px mean/med   up px mean/med   lock px when it wins / loses (mean)")
for h in O2_HOURS:
    for per in ("Oct", "Nov"):
        for city in [None] + sorted(CITY):
            rr = [r for r in o2 if r["h"] == h and r["per"] == per and (city is None or r["city"] == city)]
            if not rr:
                continue
            n = len(rr); lw = sum(r["lock_won"] for r in rr); uw = sum(1 for r in rr if r["up_won"])
            lo, hi = stats.wilson(lw, n)
            print(f"{h:02d}   {per}  {city or 'ALL':14s} {n:4d}  {pct(lw,n)} [{100*lo:.0f}-{100*hi:.0f}]  {pct(uw,n)}   "
                  f"{mean([r['lock_px'] for r in rr]):.3f}/{med([r['lock_px'] for r in rr]):.3f}   {mean([r['up_px'] for r in rr]):.3f}/{med([r['up_px'] for r in rr]):.3f}   "
                  f"{mean([r['lock_px'] for r in rr if r['lock_won']]):.3f} / {mean([r['lock_px'] for r in rr if not r['lock_won']]):.3f}")

# ---- O3
def summarise(rows, fee_rate=0.01, ndays=1):
    if not rows:
        return None
    byk = collections.defaultdict(lambda: [0.0, 0.0])
    for x in rows:
        net = x["pay"] - x["p"] - fee_rate * x["p"] * (1 - x["p"])
        byk[x["key"]][0] += net * x["sh"]; byk[x["key"]][1] += x["sh"]
    num = [v[0] for v in byk.values()]; den = [v[1] for v in byk.values()]
    r_, se_, t_ = stats.ratio_cluster(num, den)
    m_, mse_, mt_ = stats.mean_se(num)
    wins = sum(x["pay"] for x in rows); n = len(rows)
    lo, hi = stats.wilson(wins, n)
    shares = sum(den); usd = sum(x["sh"] * x["p"] for x in rows)
    return {"n": n, "days": len(byk), "avg_p": usd / shares, "win": wins / n, "wlo": lo, "whi": hi, "cps": 100 * r_, "se": 100 * se_ if se_ == se_ else float("nan"), "t": t_,
            "net": sum(num), "per_day": sum(num) / ndays, "t_usd": mt_, "stake": usd, "worst_day": min(num), "wins": wins}

NDAYS = {per: len({e["date"] for e in M if period_of(e) == per}) for per in ("Oct", "Nov")}
print(f"\n--- O3 rules (fee 0.01; calendar days: {NDAYS})")
VARS = [f"A d={d}" for d in A_DELAYS] + [f"B h={h} cap={c:.2f}" for h in B_HOURS for c in B_CAPS]
res = {}
hdr = "variant            per   entries cdays  stake$  avg px  win rate [Wilson 95%]    net c/sh (se)      t    net $   $/day  t($/cday)  worst cday $ | net $ at fee 0.05"
print(hdr)
for v in VARS:
    for per in ("Oct", "Nov"):
        rows = [x for x in entries if x["var"] == v and x["per"] == per]
        s = summarise(rows, 0.01, NDAYS[per] or 1); s5 = summarise(rows, 0.05, NDAYS[per] or 1)
        res[(v, per)] = s
        if not s:
            print(f"{v:18s} {per}   0 entries"); continue
        print(f"{v:18s} {per}  {s['n']:6d} {s['days']:5d} {s['stake']:7.0f}  {s['avg_p']:.3f}  {100*s['win']:5.1f}% [{100*s['wlo']:.1f}-{100*s['whi']:.1f}]  "
              f"{s['cps']:+6.2f} ({s['se']:.2f}) {s['t']:+6.2f} {s['net']:+8.1f} {s['per_day']:+7.2f} {s['t_usd']:+6.2f}  {s['worst_day']:+8.1f} | {s5['net']:+8.1f}")
octs = {v: res[(v, "Oct")]["net"] for v in VARS if res[(v, "Oct")]}
if octs:
    best = max(octs, key=octs.get)
    print(f"October-selected variant (highest October net $): {best}; its November line is the headline:", res.get((best, "Nov")))
# Rule A split by first report vs later (descriptive)
for v in VARS[:3]:
    for per in ("Oct", "Nov"):
        for fl in (True, False):
            rows = [x for x in entries if x["var"] == v and x["per"] == per and x["first"] == fl]
            s = summarise(rows, 0.01, NDAYS[per] or 1)
            if s:
                print(f"   {v} {per} {'first report of day' if fl else 'later report'}: n={s['n']} avg px {s['avg_p']:.3f} win {100*s['win']:.1f}% net c/sh {s['cps']:+.2f} net ${s['net']:+.1f}")

# ---- O4
print("\n--- O4 risk")
print("dead buckets that resolved YES:", len(risk_revived))
for r in risk_revived:
    print("   ", json.dumps(r))
for h in O2_HOURS:
    rr = [r for r in risk_lock if r["h"] == h]
    cls = collections.Counter("later routine report higher" if r["final_my_max"] > r["mx"] else "official result differs from my routine maximum" for r in rr)
    print(f"lock bucket at {h}:00 lost: {len(rr)} city-days; {dict(cls)}")
losses = [x for x in entries if x["net"] < 0 and x["pay"] == 0]
print("losing entries by variant:", dict(collections.Counter((x["var"], x["per"]) for x in losses)))

json.dump({"o1": o1, "o2": o2, "entries": entries, "risk_revived": risk_revived, "risk_lock": risk_lock, "ndays": NDAYS,
           "missing": dict(missing), "sanity": dict(sanity)}, open(f"{DATA}/out_{TAG}.json", "w"))
