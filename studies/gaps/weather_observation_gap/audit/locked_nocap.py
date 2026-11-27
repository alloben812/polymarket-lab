"""Audit: unrun variant. Protocol Rule B capped the price at 0.80/0.90/0.95; the locked bucket trades at ~0.996-1.000.
Run the same Rule B entry (first YES-buyable print in [T, T+1800 s], T = local 19/21/23 h, lock bucket = bucket of the
running max of reports public at T, public = obs+300) with caps 0.97 .. 0.999 and no cap. Fee 0.01*p*(1-p)."""
import csv, datetime as dt, gzip, json, re, os, collections, math
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo
D = "/home/user/polymarket-lab/data/gaps_weather_obs"
TZ = {"KLGA": "America/New_York", "KATL": "America/New_York", "KMIA": "America/New_York", "KORD": "America/Chicago", "KDAL": "America/Chicago",
      "KAUS": "America/Chicago", "KHOU": "America/Chicago", "KDEN": "America/Denver", "KBKF": "America/Denver", "KLAX": "America/Los_Angeles",
      "KSFO": "America/Los_Angeles", "KSEA": "America/Los_Angeles"}
tg = re.compile(r"\sT([01])(\d{3})([01])(\d{3})\b")
def load(icao):
    out = {}
    for row in csv.DictReader(open(f"{D}/iem/{icao[1:]}_3.csv")):
        raw = row["metar"]; t = int(dt.datetime.strptime(row["valid"], "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc).timestamp())
        m = tg.search(" " + raw)
        if m: c = Decimal(int(m.group(2))) / 10 * (-1 if m.group(1) == "1" else 1)
        else:
            b = re.search(r"\s(M?\d\d)/", " " + raw.split(" RMK")[0])
            if not b: continue
            c = Decimal(int(b.group(1).replace("M", "-")))
        out[t] = int((c * 9 / 5 + 32).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return out
M = json.load(open(D + "/markets.json")); OBS = {}
CAPS = [0.95, 0.97, 0.98, 0.99, 0.995, 0.999, 1.0]
rows = collections.defaultdict(list)
for e in M:
    if e["icao"] not in OBS: OBS[e["icao"]] = load(e["icao"])
    tz = ZoneInfo(TZ[e["icao"]]); y, m, d = map(int, e["date"].split("-"))
    day = dt.date(y, m, d)
    a = int(dt.datetime(y, m, d, tzinfo=tz).timestamp())
    rep = sorted((t, f) for t, f in OBS[e["icao"]].items() if a <= t < a + 86400 + 3600 * 2)
    nd = day + dt.timedelta(days=1)
    b = int(dt.datetime(nd.year, nd.month, nd.day, tzinfo=tz).timestamp())
    rep = [(t, f) for t, f in rep if t < b]
    bk = e["buckets"]
    for h in (17, 19, 21, 23):
        T = int(dt.datetime(y, m, d, h, tzinfo=tz).timestamp())
        vis = [f for t, f in rep if t + 300 <= T]
        if not vis: continue
        mx = max(vis)
        li = next(i for i, x in enumerate(bk) if (x["lo"] is None or mx >= x["lo"]) and (x["hi"] is None or mx <= x["hi"]))
        p = f"{D}/tape/{bk[li]['cond']}.jsonl.gz"
        fp = None
        if os.path.exists(p):
            for l in gzip.open(p, "rt"):
                tr = json.loads(l); mt = tr["t"] - 3
                if mt < T: continue
                if mt > T + 1800: break
                if tr["s"] == "BUY" and tr["o"] == "Yes": px = tr["p"]
                elif tr["s"] == "SELL" and tr["o"] == "No": px = 1 - tr["p"]
                else: continue
                fp = (px, tr["z"]); break
        if fp is None:
            rows[(h, "noprint")].append(1); continue
        px, z = fp
        sh = min(z, 50 / px)
        for cap in CAPS:
            if px <= cap + 1e-9:
                rows[(h, cap)].append((e["date"], e["city"], px, sh, bk[li]["won"], (bk[li]["won"] - px - 0.01 * px * (1 - px)) * sh, sh * px))
for h in (17, 19, 21, 23):
    print(f"hour {h}: city-days with no YES-buyable print in 30 min: {len(rows[(h,'noprint')])} of 616")
    for cap in CAPS:
        r = rows[(h, cap)]
        if not r: continue
        n = len(r); net = sum(x[5] for x in r); stake = sum(x[6] for x in r); w = sum(x[4] for x in r)
        nov = [x for x in r if x[0] >= "2026-11-01"]
        print(f"   cap {cap:5.3f}: entries {n:3d} wins {w:3d} avg px {stake/sum(x[3] for x in r):.4f} net ${net:+7.2f} on stake ${stake:7.0f} ({100*net/stake:+.2f}%)  | Nov: n {len(nov)} net ${sum(x[5] for x in nov):+.2f} stake ${sum(x[6] for x in nov):.0f}")
