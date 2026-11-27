"""Step 4: forecast table, trailing errors, model bucket probabilities (no market data used).
Writes data/gaps_weather_fc/forecasts.csv (station,date,slot,family forecasts, run used, lead)
       data/gaps_weather_fc/model_probs.csv (city,date,slot,version,condition,bucket,prob,f,n_train,mae_train,family)
       data/gaps_weather_fc/model_meta.csv  (city,date,slot,version -> f, family, n_train, obs max)
Run with python3 -I."""
import csv, datetime as dt, glob, os, sys, collections, statistics
sys.path.insert(0, "/home/user/polymarket-lab/studies/gaps/weather_forecast_gap")
import common as C

D0, D1 = dt.date(2026, 8, 1), dt.date(2026, 11, 26)


def ts(s):
    return int(dt.datetime.strptime(s[:16], "%Y-%m-%d %H:%M").replace(tzinfo=C.UTC).timestamp())


# ---- load MOS: runs[station][model] = {run_ts: {ftime_ts: max_value}}
runs = collections.defaultdict(lambda: collections.defaultdict(dict))
nrows = collections.Counter()
for path in sorted(glob.glob(f"{C.DATA}/iem/mos_*.csv")):
    _, st, model, _ = os.path.basename(path)[:-4].split("_")
    with open(path, newline="") as f:
        rd = csv.DictReader(f)
        if not rd.fieldnames or "runtime" not in rd.fieldnames:
            continue
        fld = "txn" if model in ("NBS", "NBE") else "n_x"
        for r in rd:
            v = r.get(fld)
            if v in (None, "", "None"):
                continue
            if r["ftime"][11:16] != "00:00":
                continue  # 00Z slot = daytime maximum
            try:
                val = float(v)
            except ValueError:
                continue
            runs[st][model].setdefault(ts(r["runtime"]), {})[ts(r["ftime"])] = val
            nrows[(st, model)] += 1
for st in sorted(runs):
    print(st, {m: (len(runs[st][m]), dt.datetime.fromtimestamp(min(runs[st][m]), C.UTC).strftime("%m-%d %HZ"),
                    dt.datetime.fromtimestamp(max(runs[st][m]), C.UTC).strftime("%m-%d %HZ")) for m in runs[st]})

# ---- observations
obs = {}
with open(f"{C.DATA}/obs_max.csv") as f:
    for r in csv.DictReader(f):
        if int(r["n_reports"]) >= 20:
            obs[(r["station"], dt.date.fromisoformat(r["date"]))] = int(r["max_f"])


def slot_ftime(d):
    n = d + dt.timedelta(days=1)
    return int(dt.datetime(n.year, n.month, n.day, tzinfo=C.UTC).timestamp())


def family_forecast(st, d, t, shift_days=0):
    """{family: (value, model, run_ts, public_ts)} of the usable runs at decision moment t for local day d."""
    ft = slot_ftime(d + dt.timedelta(days=shift_days))
    best = {}
    for model, rr in runs[st].items():
        delay = int(C.DELAY_H[model] * 3600)
        fam = C.FAMILY[model]
        # candidate run times: public <= t and >= t - 24h
        lo, hi = t - 24 * 3600 - delay, t - delay
        for rt, slots in rr.items():
            if lo <= rt <= hi and ft in slots:
                key = (rt + delay, -C.PREF[model])
                if fam not in best or key > best[fam][0]:
                    best[fam] = (key, slots[ft], model, rt, rt + delay)
    return {fam: v[1:] for fam, v in best.items()}


# ---- forecast table for every station / day / slot
FC = {}  # (st, d, slot) -> {family: (value, model, run_ts, public_ts)}
days = [D0 + dt.timedelta(days=i) for i in range((D1 - D0).days + 1)]
for st, tz in C.STATION_TZ.items():
    for d in days:
        te = C.t_end(tz, d)
        for slot in C.SLOTS:
            FC[(st, d, slot)] = family_forecast(st, d, te - slot * 3600)
with open(f"{C.DATA}/forecasts.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["station", "date", "slot", "obs_max", "family", "value", "model", "run_utc", "public_utc", "lead_public_to_end_h"])
    for (st, d, slot), fams in sorted(FC.items(), key=lambda kv: (kv[0][0], kv[0][1], -kv[0][2])):
        te = C.t_end(C.STATION_TZ[st], d)
        for fam, (val, model, rt, pub) in fams.items():
            w.writerow([st, d.isoformat(), slot, obs.get((st, d), ""), fam, val, model,
                        dt.datetime.fromtimestamp(rt, C.UTC).strftime("%Y-%m-%d %H:%M"), dt.datetime.fromtimestamp(pub, C.UTC).strftime("%Y-%m-%d %H:%M"),
                        round((te - pub) / 3600, 2)])

# ---- mapping sanity check: MAE of the slot (D+1 00Z) against neighbours, NBM and GFSMOS, 36 h decision
print("\nMapping check (MAE in F, decision 36 h before local day end, all stations, 08-10..11-25):")
for shift in (-1, 0, 1):
    for fam in C.FAMILIES:
        errs = []
        for st, tz in C.STATION_TZ.items():
            for d in days:
                if (st, d) not in obs or d < dt.date(2026, 8, 10):
                    continue
                ff = family_forecast(st, d, C.t_end(tz, d) - 36 * 3600, shift_days=shift)
                if fam in ff:
                    errs.append(abs(obs[(st, d)] - ff[fam][0]))
        if errs:
            print(f"  slot shift {shift:+d} day  {fam:7s} n={len(errs):5d} MAE={statistics.mean(errs):.2f}")


# ---- trailing errors and versions
def version_forecast(st, d, slot, version, fam=None):
    fams = FC.get((st, d, slot)) or {}
    if not fams:
        return None
    if version == "AVG":
        return sum(v[0] for v in fams.values()) / len(fams)
    return fams[fam][0] if fam in fams else None


def training(st, d, slot, version, fam=None):
    """Errors of the previous 45 days whose local day ended >= 2 h before the decision moment."""
    tz = C.STATION_TZ[st]
    t = C.t_end(tz, d) - slot * 3600
    errs = []
    for k in range(1, 46):
        dp = d - dt.timedelta(days=k)
        if C.t_end(tz, dp) + 2 * 3600 > t or (st, dp) not in obs:
            continue
        f = version_forecast(st, dp, slot, version, fam)
        if f is None:
            continue
        errs.append(obs[(st, dp)] - f)
    return errs


def model_for(st, d, slot, version):
    """-> (f, errors, family label) or None."""
    if version == "AVG":
        f = version_forecast(st, d, slot, "AVG")
        if f is None:
            return None
        e = training(st, d, slot, "AVG")
        return (f, e, "+".join(sorted(FC[(st, d, slot)]))) if len(e) >= 20 else None
    cands = []
    for i, fam in enumerate(C.FAMILIES):
        f = version_forecast(st, d, slot, "BEST", fam)
        if f is None:
            continue
        e = training(st, d, slot, "BEST", fam)
        if len(e) >= 20:
            cands.append((statistics.mean(abs(x) for x in e), i, f, e, fam))
    if not cands:
        return None
    _, _, f, e, fam = min(cands)
    return f, e, fam


markets = collections.defaultdict(list)
with open(f"{C.DATA}/markets.csv") as f:
    for r in csv.DictReader(f):
        markets[(r["city"], r["date"])].append(r)
skipped = collections.Counter()
n = 0
with open(f"{C.DATA}/model_probs.csv", "w", newline="") as fp, open(f"{C.DATA}/model_meta.csv", "w", newline="") as fm:
    wp = csv.writer(fp); wm = csv.writer(fm)
    wp.writerow(["city", "date", "slot", "version", "condition", "lo", "hi", "prob"])
    wm.writerow(["city", "date", "station", "era", "slot", "version", "f", "family", "n_train", "mae_train", "bias_train", "obs_max", "t_decision", "run_lead_h", "runs_used"])
    for (city, ds), mk in sorted(markets.items()):
        d = dt.date.fromisoformat(ds)
        st = mk[0]["station"]
        for slot in C.SLOTS:
            for version in ("BEST", "AVG"):
                res = model_for(st, d, slot, version)
                if res is None:
                    skipped[(version, slot, "no model" if FC.get((st, d, slot)) else "no forecast")] += 1
                    continue
                f, errs, fam = res
                fams = FC[(st, d, slot)]
                used = fams if version == "AVG" else {fam: fams[fam]}
                te = int(mk[0]["t_end"])
                lead = max((te - v[3]) / 3600 for v in used.values())
                wm.writerow([city, ds, st, mk[0]["era"], slot, version, round(f, 3), fam, len(errs), round(statistics.mean(abs(x) for x in errs), 3),
                             round(statistics.mean(errs), 3), obs.get((st, d), ""), te - slot * 3600, round(lead, 2),
                             ";".join(f"{v[1]}@{dt.datetime.fromtimestamp(v[2], C.UTC).strftime('%m-%d %HZ')}" for v in used.values())])
                vals = [C.half_up(f + e) for e in errs]
                tot = 0.0
                for r in mk:
                    lo, hi = int(r["lo"]), int(r["hi"])
                    p = sum(1 for v in vals if lo <= v <= hi) / len(vals)
                    tot += p
                    wp.writerow([city, ds, slot, version, r["condition"], lo, hi, round(p, 5)])
                assert abs(tot - 1) < 1e-6, tot
                n += 1
print("\nmodel rows (city-day x slot x version):", n, "of", len(markets) * 8)
for k, v in sorted(skipped.items()): print("  skipped", k, v)
