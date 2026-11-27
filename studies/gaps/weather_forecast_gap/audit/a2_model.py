"""Audit: independent re-implementation of protocol B2-B4 (METAR maximum, MOS forecast, trailing-error model) from the
raw Iowa Mesonet files, compared with the author's obs_max.csv and model_probs.csv. Run: python3 -I a2_model.py"""
import csv, glob, os, re, json, gzip, collections, datetime as dt, statistics
from zoneinfo import ZoneInfo
D = "/home/user/polymarket-lab/data/gaps_weather_fc"
STZ = {"KLGA": "America/New_York", "KATL": "America/New_York", "KMIA": "America/New_York", "KORD": "America/Chicago",
       "KDAL": "America/Chicago", "KHOU": "America/Chicago", "KAUS": "America/Chicago", "KDEN": "America/Denver",
       "KBKF": "America/Denver", "KLAX": "America/Los_Angeles", "KSFO": "America/Los_Angeles", "KSEA": "America/Los_Angeles"}
UTC = dt.timezone.utc
def ep(y, m, d, h=0, tz=UTC): return int(dt.datetime(y, m, d, h, tzinfo=tz).timestamp())
def tend(st, d):
    n = d + dt.timedelta(days=1); return ep(n.year, n.month, n.day, 0, ZoneInfo(STZ[st]))

# ---- observed maximum (whole F) per station-day
OBS = {}; NREP = {}
for st, tz in STZ.items():
    z = ZoneInfo(tz); acc = collections.defaultdict(list)
    for r in csv.DictReader(open(f"{D}/iem/obs_{st}.csv", encoding="utf-8", errors="replace")):
        met = (r.get("metar") or "").strip()
        if not met or met.startswith("SPECI"): continue
        try: t = dt.datetime.strptime(r["valid"], "%Y-%m-%d %H:%M").replace(tzinfo=UTC)
        except Exception: continue
        m = re.search(r"\bT([01])(\d{3})[01]\d{3}\b", met)
        if m: c10 = int(m.group(2)) * (-1 if m.group(1) == "1" else 1)
        else:
            body = met.split(" RMK")[0]
            m = re.search(r"\s(M?\d\d)/(M?\d\d)?(\s|$)", body)
            if not m: continue
            c10 = 10 * int(m.group(1).replace("M", "-"))
        acc[t.astimezone(z).date()].append(c10)
    for d, L in acc.items():
        NREP[(st, d)] = len(L)
        if len(L) >= 20:
            x = max(L) * 18 + 3200   # F in hundredths
            OBS[(st, d)] = (x + 50) // 100
A = {(r["station"], dt.date.fromisoformat(r["date"])): (int(r["n_reports"]), int(r["max_f"])) for r in csv.DictReader(open(D + "/obs_max.csv"))}
dif = [(k, OBS[k], A[k]) for k in OBS if k in A and A[k][1] != OBS[k]]
print("obs max: mine", len(OBS), "author rows", len(A), "differing", len(dif), dif[:5])

# ---- MOS runs: (st, model) -> {run_ts: {ftime_ts: value}} at 00Z ftimes only
DELAY = {"NBS": 7200, "NBE": 7200, "GFS": 18000, "MEX": 21600, "NAM": 14400}
FAM = {"NBS": "NBM", "NBE": "NBM", "GFS": "GFSMOS", "MEX": "GFSMOS", "NAM": "NAMMOS"}
RUN = collections.defaultdict(lambda: collections.defaultdict(dict))
for p in glob.glob(f"{D}/iem/mos_*.csv"):
    _, st, mdl, _ = os.path.basename(p)[:-4].split("_")
    fld = "txn" if mdl in ("NBS", "NBE") else "n_x"
    try: rd = list(csv.DictReader(open(p)))
    except Exception: continue
    for r in rd:
        if fld not in r or r[fld] in ("", None, "None") or not r["ftime"].endswith("00:00:00") or r["ftime"][11:13] != "00": continue
        try: v = float(r[fld])
        except ValueError: continue
        rt = int(dt.datetime.strptime(r["runtime"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC).timestamp())
        ft = int(dt.datetime.strptime(r["ftime"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC).timestamp())
        RUN[(st, mdl)][rt][ft] = v

def fams(st, d, t):
    n = d + dt.timedelta(days=1); ft = ep(n.year, n.month, n.day)
    best = {}
    for mdl in ("NBS", "NBE", "GFS", "MEX", "NAM"):   # preference order inside a family on equal public time
        for rt, sl in RUN.get((st, mdl), {}).items():
            pub = rt + DELAY[mdl]
            if t - 86400 <= pub <= t and ft in sl:
                f = FAM[mdl]
                if f not in best or pub > best[f][0]: best[f] = (pub, sl[ft])
    return {f: v[1] for f, v in best.items()}

def fc(st, d, slot, ver):
    F = fams(st, d, tend(st, d) - slot * 3600)
    if not F: return None
    return sum(F.values()) / len(F) if ver == "AVG" else F.get(ver)

def errs(st, d, slot, ver):
    t = tend(st, d) - slot * 3600; out = []
    for k in range(1, 46):
        q = d - dt.timedelta(days=k)
        if tend(st, q) + 7200 > t or (st, q) not in OBS: continue
        f = fc(st, q, slot, ver)
        if f is not None: out.append(OBS[(st, q)] - f)
    return out

def hu(x):
    import math; return int(math.floor(x + 0.5 + 1e-9))

# ---- markets
MK = collections.defaultdict(list)
for r in csv.DictReader(open(D + "/markets.csv")):
    MK[(r["city"], r["date"], r["station"])].append((r["condition"], int(r["lo"]), int(r["hi"])))
AP = {(r["condition"], int(r["slot"]), r["version"]): float(r["prob"]) for r in csv.DictReader(open(D + "/model_probs.csv"))}
n = bad = miss = 0; maxd = 0.0; cnt = collections.Counter()
for (city, ds, st), L in MK.items():
    d = dt.date.fromisoformat(ds)
    for slot in (60, 36, 18, 6):
        for ver in ("AVG", "BEST"):
            if ver == "AVG":
                f = fc(st, d, slot, "AVG"); e = errs(st, d, slot, "AVG") if f is not None else []
                if f is None or len(e) < 20: miss += 1; continue
            else:
                c = []
                for i, fam in enumerate(("NBM", "GFSMOS", "NAMMOS")):
                    ff = fc(st, d, slot, fam)
                    if ff is None: continue
                    ee = errs(st, d, slot, fam)
                    if len(ee) >= 20: c.append((statistics.mean(abs(x) for x in ee), i, ff, ee))
                if not c: miss += 1; continue
                _, _, f, e = min(c, key=lambda x: (x[0], x[1]))
            vals = [hu(f + x) for x in e]
            for cond, lo, hi in L:
                p = sum(lo <= v <= hi for v in vals) / len(vals)
                q = AP.get((cond, slot, ver))
                n += 1
                if q is None or abs(p - q) > 1e-4: bad += 1; cnt[(ver, slot)] += 1
                elif abs(p - q) > maxd: maxd = abs(p - q)
print(f"bucket probabilities compared: {n}; differing by > 1e-4: {bad} {dict(cnt)}; city-day/slot/version without model: {miss}; max |diff| on agreeing rows {maxd:.2e}")
