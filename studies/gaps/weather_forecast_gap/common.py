"""Shared definitions for the weather forecast-gap study (see protocol.md)."""
import datetime as dt
import math
import re
from zoneinfo import ZoneInfo

ROOT = "/home/user/polymarket-lab"
DATA = ROOT + "/data/gaps_weather_fc"
UTC = dt.timezone.utc
CITY_TZ = {"nyc": "America/New_York", "atlanta": "America/New_York", "miami": "America/New_York",
           "chicago": "America/Chicago", "dallas": "America/Chicago", "houston": "America/Chicago", "austin": "America/Chicago",
           "denver": "America/Denver", "los-angeles": "America/Los_Angeles", "san-francisco": "America/Los_Angeles",
           "seattle": "America/Los_Angeles"}
STATION_TZ = {"KLGA": "America/New_York", "KATL": "America/New_York", "KMIA": "America/New_York", "KORD": "America/Chicago",
              "KDAL": "America/Chicago", "KHOU": "America/Chicago", "KAUS": "America/Chicago", "KDEN": "America/Denver",
              "KBKF": "America/Denver", "KLAX": "America/Los_Angeles", "KSFO": "America/Los_Angeles", "KSEA": "America/Los_Angeles"}
MONTHS = {m: i + 1 for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                           "september", "october", "november", "december"])}
SLOTS = [60, 36, 18, 6]
UNIVERSE = (dt.date(2026, 9, 20), dt.date(2026, 11, 25))
SPLIT = dt.date(2026, 11, 1)  # D >= SPLIT is the reporting period
DELAY_H = {"NBS": 2.0, "NBE": 2.0, "GFS": 5.0, "MEX": 6.0, "NAM": 4.0}
FAMILY = {"NBS": "NBM", "NBE": "NBM", "GFS": "GFSMOS", "MEX": "GFSMOS", "NAM": "NAMMOS"}
FAMILIES = ["NBM", "GFSMOS", "NAMMOS"]
PREF = {"NBS": 0, "NBE": 1, "GFS": 0, "MEX": 1, "NAM": 0}


def t_end(tz: str, d: dt.date) -> int:
    """UTC epoch of the local midnight that ends local day d."""
    nxt = d + dt.timedelta(days=1)
    return int(dt.datetime(nxt.year, nxt.month, nxt.day, tzinfo=ZoneInfo(tz)).timestamp())


def t_start(tz: str, d: dt.date) -> int:
    return int(dt.datetime(d.year, d.month, d.day, tzinfo=ZoneInfo(tz)).timestamp())


def half_up(x: float) -> int:
    return int(math.floor(x + 0.5 + 1e-9))


def c10_to_f(tenths_c: int) -> int:
    """Tenths of a degree C -> whole F, half-up, in exact integer arithmetic (F*10 = tenths*9/5 + 320)."""
    # F = tenths*0.18 + 32 ; work in hundredths: tenths*18 + 3200
    h = tenths_c * 18 + 3200
    return (h + 50) // 100  # floor((x + 0.5)) for hundredths; exact for negatives too


def parse_slug(slug: str):
    m = re.match(r"highest-temperature-in-(.+)-on-([a-z]+)-(\d+)-(\d{4})$", slug)
    if not m:
        return None
    return m.group(1), dt.date(int(m.group(4)), MONTHS[m.group(2)], int(m.group(3)))


def parse_bucket(title: str):
    """'61°F or below' -> (-inf, 61); '62-63°F' -> (62, 63); '80°F or higher' -> (80, inf). Whole F, inclusive."""
    t = title.replace("°", "").replace(" ", "")
    m = re.match(r"^(-?\d+)Forbelow$", t)
    if m:
        return (-10**6, int(m.group(1)))
    m = re.match(r"^(-?\d+)Forhigher$", t)
    if m:
        return (int(m.group(1)), 10**6)
    m = re.match(r"^(-?\d+)-(-?\d+)F$", t)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    raise ValueError(title)
