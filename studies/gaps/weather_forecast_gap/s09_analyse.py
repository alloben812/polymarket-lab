"""Steps 5-7: F1 (forecast skill), F2 (market skill), F3 (rule), F4 (where), capacity. Prints markdown tables.
Usage: python3 -I s09_analyse.py [slice]   ('slice' = nyc + chicago, 2026-11-01..10 only, sanity checks)."""
import bisect, csv, gzip, json, math, os, sys, collections, datetime as dt, statistics
sys.path.insert(0, "/home/user/polymarket-lab")
sys.path.insert(0, "/home/user/polymarket-lab/studies/gaps/weather_forecast_gap")
import common as C
from pmlab.stats import mean_se, ratio_cluster

SLICE = len(sys.argv) > 1 and sys.argv[1] == "slice"
THRESH = [0.08, 0.15, 0.25]
VERSIONS = ["BEST", "AVG"]
BINS = [0.0, 0.05, 0.15, 0.30, 0.50, 0.70, 1.0000001]
FLOOR = 0.01


def per(d):
    return "report" if d >= C.SPLIT.isoformat() else "tune"


# ---------- load
markets = collections.defaultdict(list)
M = {}
for r in csv.DictReader(open(f"{C.DATA}/markets.csv")):
    if SLICE and not (r["city"] in ("nyc", "chicago") and "2026-11-01" <= r["date"] <= "2026-11-10"):
        continue
    r["lo"], r["hi"], r["t_end"] = int(r["lo"]), int(r["hi"]), int(r["t_end"])
    markets[(r["city"], r["date"])].append(r); M[r["condition"]] = r
win = {}
for r in csv.DictReader(open(f"{C.DATA}/winners.csv")):
    if r["condition"] in M and r["yes_final"] != "":
        win[r["condition"]] = float(r["yes_final"])
dropped = []
for k in list(markets):
    ys = [win.get(m["condition"]) for m in markets[k]]
    if any(y is None for y in ys) or sorted(ys) != [0.0] * (len(ys) - 1) + [1.0]:
        dropped.append((k, ys)); del markets[k]
print(f"city-days in scope: {len(markets)}; dropped (not exactly one winner): {len(dropped)} {dropped[:5]}")
obs = {}
for r in csv.DictReader(open(f"{C.DATA}/obs_max.csv")):
    if int(r["n_reports"]) >= 20:
        obs[(r["station"], r["date"])] = int(r["max_f"])
prob = collections.defaultdict(dict)  # (city,date,slot,version) -> {condition: p}
for r in csv.DictReader(open(f"{C.DATA}/model_probs.csv")):
    if (r["city"], r["date"]) in markets:
        prob[(r["city"], r["date"], int(r["slot"]), r["version"])][r["condition"]] = float(r["prob"])
meta = {}
for r in csv.DictReader(open(f"{C.DATA}/model_meta.csv")):
    if (r["city"], r["date"]) in markets:
        meta[(r["city"], r["date"], int(r["slot"]), r["version"])] = r


def table(headers, rows):
    print("| " + " | ".join(headers) + " |"); print("|" + "---|" * len(headers))
    for r in rows:
        print("| " + " | ".join(str(x) for x in r) + " |")
    print()


def f2(x, n=2):
    return "nan" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{n}f}"


# ---------- agreement of the recomputed maximum with the actual winner
print("\n## Truth check: bucket of the recomputed METAR maximum vs the bucket that actually won\n")
agree = collections.Counter()
miss = []
for (city, d), mk in markets.items():
    st, era = mk[0]["station"], mk[0]["era"]
    if (st, d) not in obs:
        agree[(era, "no recomputed max")] += 1; continue
    w = next(m for m in mk if win[m["condition"]] == 1.0)
    ok = w["lo"] <= obs[(st, d)] <= w["hi"]
    agree[(era, "agree" if ok else "differ")] += 1
    if not ok: miss.append((city, d, st, obs[(st, d)], w["bucket"]))
table(["rule period", "agree", "differ", "no recomputed max"], [[era, agree[(era, "agree")], agree[(era, "differ")], agree[(era, "no recomputed max")]] for era in ("wxgov", "metar")])
print("differences (city, date, station, recomputed max F, winning bucket):", miss[:40], "\n")

# ---------- F1
print("\n## F1. Forecast skill\n")
rows = []; cal = collections.defaultdict(lambda: [0, 0.0, 0.0])
f1 = collections.defaultdict(list)
for (city, d, slot, v), pr in prob.items():
    mk = markets[(city, d)]; mt = meta[(city, d, slot, v)]
    w = next(m for m in mk if win[m["condition"]] == 1.0)
    pw = pr[w["condition"]]
    ae = abs(int(mt["obs_max"]) - float(mt["f"])) if mt["obs_max"] != "" else None
    bias = (int(mt["obs_max"]) - float(mt["f"])) if mt["obs_max"] != "" else None
    for key in ((v, slot, "ALL", per(d)), (v, slot, city, "all"), (v, slot, "ALL", "all")):
        f1[key].append((ae, bias, pw, -math.log(max(pw, FLOOR)), float(mt["run_lead_h"]), int(mt["n_train"]), mt["family"]))
    for m in mk:
        p = pr[m["condition"]]; b = bisect.bisect_right(BINS, p) - 1
        a = cal[(v, slot, b)]; a[0] += 1; a[1] += p; a[2] += win[m["condition"]]
hdr = ["version", "decision", "scope", "period", "city-days", "MAE F", "bias F (obs-fc)", "mean P(winner)", "log score", "run lead h (mean)", "train n (mean)", "families used"]
for v in VERSIONS:
    for slot in C.SLOTS:
        for scope, pd_ in (("ALL", "all"), ("ALL", "tune"), ("ALL", "report")):
            L = f1.get((v, slot, scope, pd_))
            if not L: continue
            aes = [x[0] for x in L if x[0] is not None]; bs = [x[1] for x in L if x[1] is not None]
            fam = collections.Counter(x[6] for x in L)
            rows.append([v, f"{slot}h", scope, pd_, len(L), f2(statistics.mean(aes)), f2(statistics.mean(bs)), f2(statistics.mean(x[2] for x in L), 3),
                         f2(statistics.mean(x[3] for x in L), 3), f2(statistics.mean(x[4] for x in L), 1), f2(statistics.mean(x[5] for x in L), 1),
                         " ".join(f"{k}:{n}" for k, n in fam.most_common())])
table(hdr, rows)
print("Per city (both periods), MAE F / mean P(winner):\n")
cities = sorted({k[0] for k in markets})
for v in VERSIONS:
    rows = []
    for city in cities:
        row = [v, city]
        for slot in C.SLOTS:
            L = f1.get((v, slot, city, "all")) or []
            aes = [x[0] for x in L if x[0] is not None]
            row.append(f"{f2(statistics.mean(aes)) if aes else 'nan'} / {f2(statistics.mean(x[2] for x in L), 3) if L else 'nan'} (n={len(L)})")
        rows.append(row)
    table(["version", "city"] + [f"{s}h" for s in C.SLOTS], rows)
print("Calibration of model bucket probabilities (all buckets, both periods): mean probability -> share that won (n)\n")
rows = []
for v in VERSIONS:
    for slot in C.SLOTS:
        row = [v, f"{slot}h"]
        for b in range(len(BINS) - 1):
            a = cal.get((v, slot, b))
            row.append("-" if not a or not a[0] else f"{a[1]/a[0]:.3f} -> {a[2]/a[0]:.3f} ({a[0]})")
        rows.append(row)
table(["version", "decision"] + [f"[{BINS[i]:.2f},{min(BINS[i+1],1):.2f})" for i in range(len(BINS) - 1)], rows)

# ---------- prices
PX = {}
pres = collections.Counter()
if os.path.exists(f"{C.DATA}/prices.jsonl.gz"):
    with gzip.open(f"{C.DATA}/prices.jsonl.gz", "rt") as f:
        for line in f:
            try: o = json.loads(line)
            except ValueError: continue
            if o["c"] in M:
                PX[o["c"]] = ([p[0] for p in o["pts"]], [p[1] for p in o["pts"]]); pres[o["res"] if o["pts"] else "empty"] += 1
print(f"\n## F2. Market skill at the same moments\n\nprice histories loaded: {len(PX)} of {len(M)} markets; resolution used: {dict(pres)}\n")


def px_at(c, t):
    if c not in PX: return None
    ts, ps = PX[c]; i = bisect.bisect_right(ts, t) - 1
    return ps[i] if i >= 0 and t - ts[i] <= 6 * 3600 else None


mkt = {}  # (city,date,slot) -> {condition: raw price}
for (city, d), mk in markets.items():
    for slot in C.SLOTS:
        t = mk[0]["t_end"] - slot * 3600
        pp = {m["condition"]: px_at(m["condition"], t) for m in mk}
        if all(p is not None for p in pp.values()) and sum(pp.values()) > 0:
            mkt[(city, d, slot)] = pp
rows = []; calm = collections.defaultdict(lambda: [0, 0.0, 0.0])
for slot in C.SLOTS:
    for pd_ in ("all", "tune", "report"):
        L = [(k, pp) for k, pp in mkt.items() if k[2] == slot and (pd_ == "all" or per(k[1]) == pd_)]
        if not L: continue
        sums = [sum(pp.values()) for _, pp in L]; pw = []; ls = []; br = []
        for (city, d, _), pp in L:
            s = sum(pp.values()); w = next(m for m in markets[(city, d)] if win[m["condition"]] == 1.0)
            q = pp[w["condition"]] / s; pw.append(pp[w["condition"]]); ls.append(-math.log(max(q, FLOOR)))
            br.append(sum((pp[m["condition"]] / s - win[m["condition"]]) ** 2 for m in markets[(city, d)]))
            if pd_ == "all":
                for m in markets[(city, d)]:
                    p = pp[m["condition"]]; b = bisect.bisect_right(BINS, min(p, 1.0)) - 1
                    a = calm[(slot, b)]; a[0] += 1; a[1] += p; a[2] += win[m["condition"]]
        rows.append([f"{slot}h", pd_, len(L), f2(statistics.mean(sums), 3), f2(statistics.mean(pw), 3), f2(statistics.mean(ls), 3), f2(statistics.mean(br), 3)])
table(["decision", "period", "city-days with all 11 prices", "mean sum of prices", "mean raw price of winner", "log score (normalised)", "Brier (normalised)"], rows)
print("Calibration of raw bucket prices (history price at the decision moment): mean price -> share that won (n)\n")
rows = []
for slot in C.SLOTS:
    row = [f"{slot}h"]
    for b in range(len(BINS) - 1):
        a = calm.get((slot, b)); row.append("-" if not a or not a[0] else f"{a[1]/a[0]:.3f} -> {a[2]/a[0]:.3f} ({a[0]})")
    rows.append(row)
table(["decision"] + [f"[{BINS[i]:.2f},{min(BINS[i+1],1):.2f})" for i in range(len(BINS) - 1)], rows)

print("Model against market on the same city-days (difference = model minus market; negative = model better). t clustered by city-day / by calendar date\n")
rows = []
for v in VERSIONS:
    for slot in C.SLOTS:
        for pd_ in ("all", "tune", "report"):
            dl = []; db = []; dates = collections.defaultdict(list); datesb = collections.defaultdict(list); ml = []; kl = []; mb = []; kb = []
            for (city, d, s), pp in mkt.items():
                if s != slot or (city, d, slot, v) not in prob or (pd_ != "all" and per(d) != pd_): continue
                pr = prob[(city, d, slot, v)]; mk = markets[(city, d)]; ssum = sum(pp.values())
                w = next(m for m in mk if win[m["condition"]] == 1.0)
                lm = -math.log(max(pr[w["condition"]], FLOOR)); lk = -math.log(max(pp[w["condition"]] / ssum, FLOOR))
                bm = sum((pr[m["condition"]] - win[m["condition"]]) ** 2 for m in mk); bk = sum((pp[m["condition"]] / ssum - win[m["condition"]]) ** 2 for m in mk)
                dl.append(lm - lk); db.append(bm - bk); dates[d].append(lm - lk); datesb[d].append(bm - bk); ml.append(lm); kl.append(lk); mb.append(bm); kb.append(bk)
            if len(dl) < 3: continue
            _, _, tl = mean_se(dl); _, _, tb = mean_se(db)
            _, _, tld = mean_se([statistics.mean(x) for x in dates.values()]); _, _, tbd = mean_se([statistics.mean(x) for x in datesb.values()])
            rows.append([v, f"{slot}h", pd_, len(dl), f2(statistics.mean(ml), 3), f2(statistics.mean(kl), 3), f"{statistics.mean(dl):+.3f}", f"{tl:.1f} / {tld:.1f}",
                         f2(statistics.mean(mb), 3), f2(statistics.mean(kb), 3), f"{statistics.mean(db):+.3f}", f"{tb:.1f} / {tbd:.1f}"])
table(["version", "decision", "period", "city-days", "log model", "log market", "diff", "t", "Brier model", "Brier market", "diff", "t"], rows)

# ---------- tapes and entries
TAPE_DIR = f"{C.ROOT}/data/tape"


def entry_print(c, t):
    """First buyable-YES print with block time in [t, t+3h]: (price, shares, ts) or None; None if no tape file."""
    path = f"{TAPE_DIR}/{c}.jsonl.gz"
    if c not in TP:
        if not os.path.exists(path):
            TP[c] = None
        else:
            with gzip.open(path, "rt") as f:
                rows_ = [json.loads(x) for x in f]
            b = []
            for r in rows_:
                if r["s"] == "BUY" and r["o"] == "Yes": b.append((r["t"], r["p"], r["z"]))
                elif r["s"] == "SELL" and r["o"] == "No": b.append((r["t"], 1.0 - r["p"], r["z"]))
            b.sort(); TP[c] = ([x[0] for x in b], b, len(rows_))
    if TP[c] is None: return None
    ts, b, _ = TP[c]
    i = bisect.bisect_left(ts, t)
    if i < len(b) and b[i][0] <= t + 3 * 3600:
        return b[i][1], b[i][2], b[i][0]
    return False


TP = {}
print("\n## Tape checks\n")
have = sum(1 for c in M if os.path.exists(f"{TAPE_DIR}/{c}.jsonl.gz"))
print(f"tapes on disk for {have} of {len(M)} bucket markets\n")
# sanity: all first prints (every bucket with a tape, every slot), win rate by price band
band = collections.defaultdict(lambda: [0, 0.0, 0.0]); nwin_ts = 0; nprint = 0
FP = {}  # (condition, slot) -> print
for (city, d), mk in markets.items():
    for slot in C.SLOTS:
        t = mk[0]["t_end"] - slot * 3600
        for m in mk:
            e = entry_print(m["condition"], t)
            FP[(m["condition"], slot)] = e
            if e:
                nprint += 1; nwin_ts += (t <= e[2] <= t + 10800)
                b = min(int(e[0] * 10), 9); a = band[(slot, b)]; a[0] += 1; a[1] += e[0]; a[2] += win[m["condition"]]
print(f"first buyable prints found: {nprint}; with timestamp inside [t, t+3h]: {nwin_ts}\n")
print("All first buyable prints (not rule-selected), by price decile: mean price -> share that won (n). Biased towards model-likely buckets when only the 'model' tape subset is on disk.\n")
rows = []
for slot in C.SLOTS:
    row = [f"{slot}h"]
    for b in range(10):
        a = band.get((slot, b)); row.append("-" if not a else f"{a[1]/a[0]:.2f} -> {a[2]/a[0]:.2f} ({a[0]})")
    rows.append(row)
table(["decision"] + [f"{b/10:.1f}-{(b+1)/10:.1f}" for b in range(10)], rows)

FEE_CHANGE = 1795219140  # 2026-11-20 23:59 UTC
Z0 = int(dt.datetime(2026, 10, 20, tzinfo=C.UTC).timestamp()); Z1 = int(dt.datetime(2026, 11, 1, tzinfo=C.UTC).timestamp())


def actual_rate(ts):
    if ts >= FEE_CHANGE: return 0.01
    if Z0 <= ts < Z1: return 0.0
    return 0.05


entries = []  # dicts
for (city, d), mk in markets.items():
    for slot in C.SLOTS:
        for v in VERSIONS:
            pr = prob.get((city, d, slot, v))
            if pr is None: continue
            for g in THRESH:
                cands = []
                for m in mk:
                    e = FP.get((m["condition"], slot))
                    if not e: continue
                    p = e[0]; gap = pr[m["condition"]] - p
                    if gap >= g - 1e-12 and 0.03 <= p <= 0.85:
                        cands.append((gap, m, e))
                cands.sort(key=lambda x: -x[0])
                for gap, m, e in cands[:3]:
                    p = e[0]; y = win[m["condition"]]; sh = 10.0 / p
                    fee = 0.01 * p * (1 - p); feea = actual_rate(e[2]) * p * (1 - p)
                    entries.append(dict(city=city, date=d, slot=slot, v=v, g=g, c=m["condition"], bucket=m["bucket"], p=p, y=y, sh=sh, gap=gap, pm=pr[m["condition"]],
                                        net=sh * (y - p - fee), net_actual=sh * (y - p - feea), fee=sh * fee, size=e[1], ts=e[2], lag=e[2] - (m["t_end"] - slot * 3600),
                                        period=per(d)))
# fee check
bad = [e for e in entries if abs(e["fee"] - 0.01 * e["p"] * (1 - e["p"]) * e["sh"]) > 1e-9]
print(f"entries (all cells): {len(entries)}; fee formula mismatches: {len(bad)}; entry timestamps outside [t, t+3h]: {sum(1 for e in entries if not (0 <= e['lag'] <= 10800))}\n")


def stat_row(L, key="net"):
    if not L: return None
    cd = collections.defaultdict(lambda: [0.0, 0.0, 0.0]); dd = collections.defaultdict(lambda: [0.0, 0.0, 0.0])
    for e in L:
        for dct, k in ((cd, (e["city"], e["date"])), (dd, e["date"])):
            a = dct[k]; a[0] += e[key]; a[1] += e["sh"]; a[2] += 10.0
    cps, _, _ = ratio_cluster([a[0] for a in cd.values()], [a[1] for a in cd.values()])
    ret, se, t = ratio_cluster([a[0] for a in cd.values()], [a[2] for a in cd.values()])
    _, _, td = ratio_cluster([a[0] for a in dd.values()], [a[2] for a in dd.values()])
    n = len(L)
    return dict(n=n, cd=len(cd), days=len(dd), avgp=sum(e["p"] for e in L) / n, vwap=10.0 * n / sum(e["sh"] for e in L), win=sum(e["y"] for e in L) / n,
                cps=100 * cps, net=sum(e[key] for e in L), ret=100 * ret, t=t, td=td, pm=sum(e["pm"] for e in L) / n)


def fmt(s):
    if s is None: return ["0"] + ["-"] * 10
    return [s["n"], s["cd"], f2(s["avgp"], 3), f2(s["vwap"], 3), f2(s["pm"], 3), f2(s["win"], 3), f"{s['cps']:+.2f}", f"{s['net']:+.1f}", f"{s['ret']:+.1f}%", f2(s["t"], 2), f2(s["td"], 2)]


H = ["entries", "city-days", "avg price", "cost per share", "avg model prob", "win rate", "net c/share", "net $", "return on stake", "t (city-day)", "t (date)"]
print("\n## F3. Rule: 24 cells (6 variants x 4 decision times) and 6 pooled rows, fee 0.01\n")
sel = None
for pd_ in ("tune", "report"):
    print(f"### Period: {pd_} ({'D <= 2026-10-31' if pd_ == 'tune' else 'D = 2026-11-01 .. 11-25'})\n")
    rows = []
    for v in VERSIONS:
        for g in THRESH:
            for slot in C.SLOTS + ["pooled"]:
                L = [e for e in entries if e["v"] == v and e["g"] == g and e["period"] == pd_ and (slot == "pooled" or e["slot"] == slot)]
                s = stat_row(L)
                rows.append([v, g, slot if slot == "pooled" else f"{slot}h"] + fmt(s))
                if pd_ == "tune" and slot != "pooled" and s and s["cd"] >= 50 and not math.isnan(s["t"]):
                    if sel is None or s["t"] > sel[0]: sel = (s["t"], v, g, slot)
    table(["version", "g", "decision"] + H, rows)
if sel:
    _, v, g, slot = sel
    print(f"### Selected cell on the tuning period (highest city-day t with >= 50 city-days): version {v}, g = {g}, decision {slot}h\n")
    rows = []
    for pd_ in ("tune", "report"):
        L = [e for e in entries if e["v"] == v and e["g"] == g and e["slot"] == slot and e["period"] == pd_]
        rows.append([pd_, "0.01"] + fmt(stat_row(L))); rows.append([pd_, "actual at the time"] + fmt(stat_row(L, "net_actual")))
    table(["period", "fee"] + H, rows)
print("### Fee sensitivity on the same trades (pooled rows): fee really charged at the time (0.05 until 11-20, zero 10-20..31, 0.01 after)\n")
rows = []
for pd_ in ("tune", "report"):
    for v in VERSIONS:
        for g in THRESH:
            L = [e for e in entries if e["v"] == v and e["g"] == g and e["period"] == pd_]
            rows.append([pd_, v, g] + fmt(stat_row(L, "net_actual")))
table(["period", "version", "g"] + H, rows)

print("\n## F4. Where the result sits (each variant pooled over the 4 decision times)\n")
PB = [(0.03, 0.10), (0.10, 0.25), (0.25, 0.50), (0.50, 0.8500001)]
for pd_ in ("tune", "report"):
    print(f"### By entry price band, period {pd_}\n")
    rows = []
    for v in VERSIONS:
        for g in THRESH:
            for lo, hi in PB:
                L = [e for e in entries if e["v"] == v and e["g"] == g and e["period"] == pd_ and lo <= e["p"] < hi]
                rows.append([v, g, f"{lo:.2f}-{min(hi, .85):.2f}"] + fmt(stat_row(L)))
    table(["version", "g", "price band"] + H, rows)
print("### By city, both periods together and report period, variant g = 0.08 and g = 0.15\n")
for g in (0.08, 0.15):
    rows = []
    for v in VERSIONS:
        for city in cities:
            La = [e for e in entries if e["v"] == v and e["g"] == g and e["city"] == city]
            Lr = [e for e in La if e["period"] == "report"]
            sa, sr = stat_row(La), stat_row(Lr)
            rows.append([v, g, city, sa["n"] if sa else 0, f"{sa['net']:+.1f}" if sa else "-", f"{sa['ret']:+.1f}%" if sa else "-", f2(sa["t"], 2) if sa else "-",
                         sr["n"] if sr else 0, f"{sr['net']:+.1f}" if sr else "-", f"{sr['ret']:+.1f}%" if sr else "-", f2(sr["t"], 2) if sr else "-"])
    table(["version", "g", "city", "entries all", "net $ all", "return all", "t all", "entries Nov", "net $ Nov", "return Nov", "t Nov"], rows)
print("### By rule period of the market (weather.gov rule <= 10-22, METAR rule >= 10-23), pooled over decision times\n")
rows = []
for v in VERSIONS:
    for g in THRESH:
        for era in ("wxgov", "metar"):
            L = [e for e in entries if e["v"] == v and e["g"] == g and M[e["c"]]["era"] == era]
            rows.append([v, g, era] + fmt(stat_row(L)))
table(["version", "g", "rule period"] + H, rows)

print("\n### Capacity\n")
rows = []
for v in VERSIONS:
    for g in THRESH:
        for slot in C.SLOTS:
            nsig = anyp = okp = notape = 0
            for (city, d, s), pp in mkt.items():
                if s != slot or (city, d, slot, v) not in prob: continue
                pr = prob[(city, d, slot, v)]
                for m in markets[(city, d)]:
                    ph = pp[m["condition"]]
                    if pr[m["condition"]] - ph >= g and 0.03 <= ph <= 0.85:
                        nsig += 1; e = FP.get((m["condition"], slot))
                        if e is None: notape += 1
                        elif e:
                            anyp += 1; okp += (pr[m["condition"]] - e[0] >= g and 0.03 <= e[0] <= 0.85)
            L = [e for e in entries if e["v"] == v and e["g"] == g and e["slot"] == slot]
            cov = sum(1 for e in L if e["size"] >= e["sh"] - 1e-9); med = statistics.median([e["size"] * e["p"] for e in L]) if L else float("nan")
            lag = statistics.median([e["lag"] / 60 for e in L]) if L else float("nan")
            rows.append([v, g, f"{slot}h", nsig, notape, f"{anyp} ({100*anyp/max(nsig,1):.0f}%)", f"{okp} ({100*okp/max(nsig,1):.0f}%)", len(L),
                         f"{cov} ({100*cov/max(len(L),1):.0f}%)", f2(med, 1), f2(lag, 0)])
table(["version", "g", "decision", "history-price signals", "of them without tape file", "any buyable print in 3 h", "print still meets the rule", "entries (rule on print)",
       "print size covers $10", "median print $", "median minutes to print"], rows)

with open(f"{C.DATA}/entries{'_slice' if SLICE else ''}.csv", "w", newline="") as f:
    if entries:
        w = csv.DictWriter(f, fieldnames=list(entries[0].keys())); w.writeheader(); w.writerows(entries)
# dollars per day
print("\n### Dollars per calendar day at $10 per entry (report period, pooled over the 4 decision times)\n")
rows = []
for v in VERSIONS:
    for g in THRESH:
        L = [e for e in entries if e["v"] == v and e["g"] == g and e["period"] == "report"]
        if not L: continue
        byd = collections.defaultdict(float); st = collections.defaultdict(float)
        for e in L: byd[e["date"]] += e["net"]; st[e["date"]] += 10
        nd = 25
        vals = [byd.get((C.SPLIT + dt.timedelta(days=i)).isoformat(), 0.0) for i in range(nd)]
        m, se, t = mean_se(vals)
        rows.append([v, g, len(L), f"{sum(st.values())/nd:.0f}", f"{m:+.2f}", f"{se:.2f}", f2(t, 2), f"{min(vals):+.1f}", f"{max(vals):+.1f}", sum(1 for x in vals if x > 0)])
table(["version", "g", "entries", "staked $/day", "net $/day", "se", "t (days)", "worst day $", "best day $", "positive days of 25"], rows)
