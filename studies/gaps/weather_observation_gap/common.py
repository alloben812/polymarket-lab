"""Shared helpers for the weather observation gap study (see protocol.md)."""
import csv, datetime as dt, gzip, json, os, re
from zoneinfo import ZoneInfo

ROOT = "/home/user/polymarket-lab"
DATA = ROOT + "/data/gaps_weather_obs"
HERE = ROOT + "/studies/gaps/weather_observation_gap"
UTC = dt.timezone.utc
CITY = {  # city slug -> (ICAO, tz)
    "nyc": ("KLGA", "America/New_York"), "atlanta": ("KATL", "America/New_York"), "miami": ("KMIA", "America/New_York"),
    "chicago": ("KORD", "America/Chicago"), "dallas": ("KDAL", "America/Chicago"), "austin": ("KAUS", "America/Chicago"),
    "houston": ("KHOU", "America/Chicago"), "denver": ("KDEN", "America/Denver"),
    "los-angeles": ("KLAX", "America/Los_Angeles"), "san-francisco": ("KSFO", "America/Los_Angeles"), "seattle": ("KSEA", "America/Los_Angeles"),
}
MONTHS = {m: i + 1 for i, m in enumerate("january february march april may june july august september october november december".split())}
SLUG = re.compile(r"^highest-temperature-in-(.+)-on-([a-z]+)-(\d{1,2})-(\d{4})$")
TG = re.compile(r"\sT([01])(\d{3})([01])(\d{3})(?=\s|$)")
BODY = re.compile(r"\s(M?\d{2})/(M?\d{2})?\s")
PUBLIC_LAG = 300
BLOCK_LAG = 3
FEE = 0.01


def c10_to_f(t10: int) -> int:
    """tenths of a degree C -> whole F, half-up (exact integer arithmetic)."""
    return (18 * t10 + 3250) // 100


def parse_value(raw: str):
    """(tenths C, has_T_group) or (None, False)."""
    s = " " + raw.strip() + " "
    m = TG.search(s)
    if m:
        return (-1 if m.group(1) == "1" else 1) * int(m.group(2)), True
    b = BODY.search(s.split(" RMK")[0] + " ")
    if b:
        return int(b.group(1).replace("M", "-")) * 10, False
    return None, False


def load_obs(icao: str, rtype: int = 3):
    """list of dicts {t (epoch obs time), raw, c10, f, tg} sorted by time; duplicates on time: last kept, dup flagged."""
    path = f"{DATA}/iem/{icao[1:]}_{rtype}.csv"
    rows = {}
    with open(path) as f:
        rd = csv.reader(f)
        next(rd)
        for p in rd:
            if len(p) < 3:
                continue
            try:
                ts = int(dt.datetime.strptime(p[1], "%Y-%m-%d %H:%M").replace(tzinfo=UTC).timestamp())
            except ValueError:
                continue
            raw = ",".join(p[2:])
            c10, tg = parse_value(raw)
            prev = rows.get(ts)
            rows[ts] = {"t": ts, "raw": raw, "c10": c10, "f": None if c10 is None else c10_to_f(c10), "tg": tg,
                        "dup": (prev["raw"] if prev else None)}
    return [rows[k] for k in sorted(rows)]


def local_day_bounds(city: str, date: dt.date):
    tz = ZoneInfo(CITY[city][1])
    a = dt.datetime(date.year, date.month, date.day, tzinfo=tz)
    nd = date + dt.timedelta(days=1)
    b = dt.datetime(nd.year, nd.month, nd.day, tzinfo=tz)
    return int(a.timestamp()), int(b.timestamp())


def local_clock(city: str, date: dt.date, hour: int) -> int:
    tz = ZoneInfo(CITY[city][1])
    return int(dt.datetime(date.year, date.month, date.day, hour, tzinfo=tz).timestamp())


def parse_bucket(title: str):
    """(lo, hi) in whole F; None = unbounded."""
    t = title.replace("°F", "").strip()
    m = re.match(r"^(-?\d+) or below$", t)
    if m:
        return None, int(m.group(1))
    m = re.match(r"^(-?\d+) or higher$", t)
    if m:
        return int(m.group(1)), None
    m = re.match(r"^(-?\d+)-(-?\d+)$", t)
    if m:
        return int(m.group(1)), int(m.group(2))
    raise ValueError(title)


def bucket_index(buckets, f):
    for i, (lo, hi) in enumerate(buckets):
        if (lo is None or f >= lo) and (hi is None or f <= hi):
            return i
    return None


def load_markets():
    return json.load(open(DATA + "/markets.json"))


def iso(ts):
    return dt.datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%d %H:%MZ")
