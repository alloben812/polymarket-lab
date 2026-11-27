"""Independent recompute (audit). Does not import the study's code. Reads raw caches only:
iem/*.csv (METAR text), awc/*.json (receiptTime), tape/*.jsonl.gz, markets.json (bucket titles + resolution).
Key number: stale profit taken by takers on newly dead buckets AFTER the official aviationweather.gov receipt
(12-24 Nov), plus the same split at obs+300 s, plus sensitivity to the 3 s block lag, plus an unrun variant:
buying the locked bucket at high prices (no cap)."""
import csv, datetime as dt, gzip, json, re, sys, os, collections, bisect, statistics as st
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo
D = "/home/user/polymarket-lab/data/gaps_weather_obs"
TZ = {"KLGA": "America/New_York", "KATL": "America/New_York", "KMIA": "America/New_York", "KORD": "America/Chicago",
      "KDAL": "America/Chicago", "KAUS": "America/Chicago", "KHOU": "America/Chicago", "KDEN": "America/Denver",
      "KBKF": "America/Denver", "KLAX": "America/Los_Angeles", "KSFO": "America/Los_Angeles", "KSEA": "America/Los_Angeles"}
M = json.load(open(D + "/markets.json"))
tg = re.compile(r"\sT([01])(\d{3})([01])(\d{3})\b")
def load(icao):
    out = {}
    for row in csv.DictReader(open(f"{D}/iem/{icao[1:]}_3.csv")):
        raw = row["metar"]; t = int(dt.datetime.strptime(row["valid"], "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc).timestamp())
        m = tg.search(" " + raw)
        if m:
            c = Decimal(int(m.group(2))) / 10 * (-1 if m.group(1) == "1" else 1)
        else:
            b = re.search(r"\s(M?\d\d)/", " " + raw.split(" RMK")[0])
            if not b: continue
            c = Decimal(int(b.group(1).replace("M", "-")))
        f = int((c * 9 / 5 + 32).quantize(Decimal(1), rounding=ROUND_HALF_UP))   # half-up (toward +inf for .5)
        out[t] = f
    return out
OBS = {}
REC = {}
for fn in os.listdir(D + "/awc"):
    for r in json.load(open(D + "/awc/" + fn)):
        if r.get("metarType") == "SPECI": continue
        REC[(r["icaoId"], r["obsTime"])] = dt.datetime.fromisoformat(r["receiptTime"].replace("Z", "+00:00")).timestamp()
def tape(cond):
    p = f"{D}/tape/{cond}.jsonl.gz"
    return [json.loads(l) for l in gzip.open(p, "rt")] if os.path.exists(p) else []
def lday(e):
    tz = ZoneInfo(TZ[e["icao"]]); y, m, d = map(int, e["date"].split("-"))
    a = dt.datetime(y, m, d, tzinfo=tz); b = a + dt.timedelta(days=1)  # aware add: wall-clock next midnight
    b = dt.datetime(*(a.date() + dt.timedelta(days=1)).timetuple()[:3], tzinfo=tz)
    return int(a.timestamp()), int(b.timestamp())

LAG = int(sys.argv[1]) if len(sys.argv) > 1 else 3
match = tot = 0
kills = []   # (event, bucket idx, obs t, report f)
for e in M:
    if e["icao"] not in OBS: OBS[e["icao"]] = load(e["icao"])
    a, b = lday(e)
    rep = sorted((t, f) for t, f in OBS[e["icao"]].items() if a <= t < b)
    bk = e["buckets"]
    # validation
    mx = max(f for _, f in rep)
    pred = [i for i, x in enumerate(bk) if (x["lo"] is None or mx >= x["lo"]) and (x["hi"] is None or mx <= x["hi"])]
    won = [i for i, x in enumerate(bk) if x["won"]]
    tot += 1; match += (pred == won)
    run = None; dead = set()
    for t, f in rep:
        if run is not None and f <= run: continue
        run = f
        for i, x in enumerate(bk):
            if x["hi"] is not None and x["hi"] < run and i not in dead:
                dead.add(i); kills.append((e, i, t, f))
print(f"validation (own parser/tz): {match}/{tot}; kill events (newly dead buckets): {len(kills)}")

def stale_rows(e, i, t0):
    for tr in tape(e["buckets"][i]["cond"]):
        mt = tr["t"] - LAG
        if mt < t0: continue
        if tr["s"] == "SELL" and tr["o"] == "Yes": py = tr["p"]
        elif tr["s"] == "BUY" and tr["o"] == "No": py = 1 - tr["p"]
        else: continue
        yield mt, py, tr["z"], tr
for lo_name, lo_thr in (("pyes>=0.02", 0.02), ("pyes>=0.005", 0.005)):
    agg = collections.defaultdict(float); n_rec = 0; days = set(); cnt = collections.Counter()
    for e, i, t, f in kills:
        rc = REC.get((e["icao"], t))
        if rc is None: continue
        n_rec += 1; days.add(e["date"])
        for mt, py, z, tr in stale_rows(e, i, t):
            if py < lo_thr: continue
            d = mt - rc
            k = "before receipt" if d < 0 else "0-10s" if d < 10 else "10-30s" if d < 30 else "30-120s" if d < 120 else "120s+"
            agg[k] += z * py; cnt[k] += 1
    print(f"[LAG={LAG}s, {lo_name}] kills with receipt: {n_rec}, dates {len(days)} ({min(days)}..{max(days)})")
    for k in ("before receipt", "0-10s", "10-30s", "30-120s", "120s+"):
        print(f"    {k:15s} ${agg[k]:9.1f}  prints {cnt[k]}")
    print(f"    after receipt total ${sum(v for k,v in agg.items() if k!='before receipt'):.1f}")
# same on obs+300
agg = collections.defaultdict(float)
for e, i, t, f in kills:
    for mt, py, z, tr in stale_rows(e, i, t):
        if py < 0.02: continue
        agg["Oct" if e["date"] < "2026-11-01" else "Nov", "pre" if mt < t + 300 else "post"] += z * py
print("obs+300 split, all 3,335:", {f"{a}-{b}": round(v) for (a, b), v in sorted(agg.items())})
# weekend/weekday after obs+300 under new rule only
