"""Release calendar fixed BEFORE any tape was read (see protocol.md).

Each row: release id, type, group, scheduled time UTC, tier, source of the time, slug regex of the Polymarket events it decides,
judgement flag for the family ('' = the headline number maps mechanically to a bucket).
Tier A = US official calendar fetched in this session (bls.gov 2026 schedule page via WebFetch, bea.gov/news/schedule/full
and apps.bea.gov release_dates.json, federalreserve.gov fomccalendars.htm). FOMC statements are issued at 14:00 ET.
Tier B = date taken from the market's own rules text (which cites the publisher's calendar), clock time = the publisher's
standing publication time (analyst's knowledge, NOT fetched from the publisher in this session) -> usable only if the tape
confirms it (protocol section 4).
US daylight time ends 2026-11-01; EU/UK summer time ends 2026-10-25; Sydney DST starts 2026-10-04; NZ DST starts 2026-09-27.
"""
import calendar, re, time


def utc(s):
    return calendar.timegm(time.strptime(s, "%Y-%m-%d %H:%M"))


R = []


def add(rid, typ, group, when, tier, src, pattern, flag=""):
    R.append({"id": rid, "type": typ, "group": group, "T": utc(when), "when": when, "tier": tier, "src": src,
              "pattern": re.compile(pattern), "flag": flag})


BLS = "bls.gov/schedule/2026 (8:30 ET)"
BEA = "bea.gov/news/schedule/full + release_dates.json"
FED = "federalreserve.gov fomccalendars (statement 14:00 ET)"
# ---- Tier A: US official calendars
for mon, when in (("august", "2026-09-04 12:30"), ("september", "2026-10-02 12:30"), ("october", "2026-11-06 13:30")):
    add(f"US-EMP-{mon}", "Employment", "US", when, "A", BLS, rf"^({mon}-unemployment-rate|how-many-jobs-added-in-{mon})")
for mon, when in (("august", "2026-09-11 12:30"), ("september", "2026-10-14 12:30"), ("october", "2026-11-10 13:30")):
    add(f"US-CPI-{mon}", "CPI", "US", when, "A", BLS, rf"^({mon}-inflation-us-(annual|monthly)|core-cpi-(mom|yoy)-{mon})")
    add(f"US-CPI-{mon}", "CPI", "US", when, "A", BLS, rf"^price-of-dozen-eggs-in-{mon}", "eggs: resolves on the FRED chart update, number is in BLS average-price tables, not the news release")
for mon, when in (("august", "2026-09-10 12:30"), ("september", "2026-10-15 12:30"), ("october", "2026-11-13 13:30")):
    add(f"US-PPI-{mon}", "PPI", "US", when, "A", BLS, rf"^ppi-yoy-{mon}")
for mon, when in (("august", "2026-09-30 12:30"), ("september", "2026-10-29 12:30"), ("october", "2026-11-25 13:30")):
    add(f"US-PCE-{mon}", "PCE", "US", when, "A", BEA, rf"^core-pce-(mom|yoy)-{mon}")
add("US-GDP-q3adv", "GDP", "US", "2026-10-29 12:30", "A", BEA, r"^us-gdp-growth-in-q3-2026")
for mon, when in (("september", "2026-09-16 18:00"), ("october", "2026-10-28 18:00")):
    add(f"US-FOMC-{mon}", "FOMC", "US", when, "A", FED, rf"^fed-decision-in-{mon}")
    add(f"US-FOMC-{mon}", "FOMC", "US", when, "A", FED, rf"^how-many-dissent-at-the-{mon}-fed-meeting", "dissent count: needs reading the vote paragraph of the statement")
add("US-FOMC-september", "FOMC", "US", "2026-09-16 18:00", "A", FED, r"^fed-decisions-(jun-sep|juloct)", "combination over three meetings: needs the path logic; only buckets still open at this meeting")
for mon, when in (("july", "2026-09-01 14:00"), ("august", "2026-09-29 14:00"), ("september", "2026-11-03 15:00")):
    add(f"US-JOLTS-{mon}", "JOLTS", "US", when, "A", "bls.gov/schedule/2026 (10:00 ET)", rf"^jolts-job-openings-{mon}")
# ---- Tier B: US private publishers, time printed in the market rules (10:00 ET)
for mon, when in (("august", "2026-09-01 14:00"), ("september", "2026-10-01 14:00"), ("october", "2026-11-02 15:00")):
    add(f"US-ISMM-{mon}", "ISM", "US", when, "B", "market rules: 10:00 AM ET", rf"^ism-manufacturing-pmi-{mon}")
for mon, when in (("august", "2026-09-03 14:00"), ("september", "2026-10-05 14:00"), ("october", "2026-11-04 15:00")):
    add(f"US-ISMS-{mon}", "ISM", "US", when, "B", "market rules: 10:00 AM ET", rf"^ism-services-pmi-{mon}")
for mon, when in (("september", "2026-09-25 14:00"), ("october", "2026-10-23 14:00"), ("november", "2026-11-20 15:00")):
    add(f"US-UMICH-{mon}", "UMich", "US", when, "B", "market rules: 10:00 AM ET (final reading)", rf"^university-of-michigan-consumer-sentiment-{mon}")
# ---- Tier B: other central banks (date from rules; standing announcement time)
CB = "Central bank (non-US)"
add("BOC-sep", CB, "non-US", "2026-09-02 13:45", "B", "BoC 09:45 ET", r"^bank-of-canada-decision-in-september")
add("BOC-oct", CB, "non-US", "2026-10-28 13:45", "B", "BoC 09:45 ET", r"^bank-of-canada-decision-in-october")
add("RBNZ-sep", CB, "non-US", "2026-09-02 02:00", "B", "RBNZ 14:00 NZST", r"^reserve-bank-of-new-zealand-decision-in-september")
add("RBNZ-oct", CB, "non-US", "2026-10-28 01:00", "B", "RBNZ 14:00 NZDT", r"^reserve-bank-of-new-zealand-decision-in-october")
add("BOI-sep", CB, "non-US", "2026-09-01 13:00", "B", "BoI 16:00 Israel time", r"^bank-of-israel-decision-in-september")
add("BOI-oct", CB, "non-US", "2026-10-21 13:00", "B", "BoI 16:00 Israel time", r"^bank-of-israel-decision-in-october")
add("BOI-nov", CB, "non-US", "2026-11-23 14:00", "B", "BoI 16:00 Israel time", r"^bank-of-israel-decision-in-november")
add("ECB-sep", CB, "non-US", "2026-09-10 12:15", "B", "ECB 14:15 CEST", r"^ecb-interest-rates-september")
add("ECB-oct", CB, "non-US", "2026-10-29 13:15", "B", "ECB 14:15 CET", r"^ecb-interest-rates-october")
add("CBR-sep", CB, "non-US", "2026-09-11 10:30", "B", "Bank of Russia 13:30 Moscow", r"^bank-of-russia-decision-in-september")
add("CBR-oct", CB, "non-US", "2026-10-23 10:30", "B", "Bank of Russia 13:30 Moscow", r"^bank-of-russia-decision-in-october")
add("BOE-sep", CB, "non-US", "2026-09-17 11:00", "B", "BoE 12:00 London (BST)", r"^bank-of-england-decision-in-september")
add("BOE-nov", CB, "non-US", "2026-11-05 12:00", "B", "BoE 12:00 London (GMT)", r"^bank-of-england-decision-in-november")
add("SNB-sep", CB, "non-US", "2026-09-24 07:30", "B", "SNB 09:30 CEST", r"^swiss-national-bank-decision-in-september")
add("BANXICO-sep", CB, "non-US", "2026-09-24 19:00", "B", "Banxico 13:00 Mexico City", r"^bank-of-mexico-decision-in-september")
add("BANXICO-nov", CB, "non-US", "2026-11-05 19:00", "B", "Banxico 13:00 Mexico City", r"^bank-of-mexico-decision-in-november")
add("RBA-sep", CB, "non-US", "2026-09-29 04:30", "B", "RBA 14:30 AEST", r"^reserve-bank-of-australia-decision-in-september")
add("RBA-nov", CB, "non-US", "2026-11-03 03:30", "B", "RBA 14:30 AEDT", r"^reserve-bank-of-australia-decision-in-november")
add("BCCH-oct", CB, "non-US", "2026-10-27 21:00", "B", "Banco Central de Chile 18:00 Santiago", r"^central-bank-of-chile-decision-in-october")
# ---- Tier B: non-US data
FX = "Inflation (non-US)"
add("AR-CPI-aug", FX, "non-US", "2026-09-10 19:00", "B", "INDEC 16:00 Buenos Aires", r"^argentina-monthly-inflation-august")
add("AR-CPI-sep", FX, "non-US", "2026-10-13 19:00", "B", "INDEC 16:00 Buenos Aires", r"^argentina-monthly-inflation-september")
add("AR-CPI-oct", FX, "non-US", "2026-11-12 19:00", "B", "INDEC 16:00 Buenos Aires", r"^argentina-monthly-inflation-october")
add("UK-CPI-sep", FX, "non-US", "2026-10-21 06:00", "B", "ONS 07:00 London (BST)", r"^inflation-uk-annual-20260916")
add("UK-CPI-oct", FX, "non-US", "2026-11-18 07:00", "B", "ONS 07:00 London (GMT)", r"^october-inflation-uk-annual")
GX = "GDP (non-US)"
add("BR-GDP-q2", GX, "non-US", "2026-09-01 12:00", "B", "IBGE 09:00 Brasilia", r"^brazil-gdp-growth-in-q2")
add("CA-GDP-jul", GX, "non-US", "2026-09-29 12:30", "B", "StatCan 08:30 ET", r"^canada-gdp-july")
add("CA-GDP-aug", GX, "non-US", "2026-10-30 12:30", "B", "StatCan 08:30 ET", r"^canada-gdp-august")
add("CN-GDP-q3", GX, "non-US", "2026-10-20 02:00", "B", "NBS 10:00 Beijing, date from rules", r"^china-gdp-growth-yy-in-q3")
add("KR-GDP-q3", GX, "non-US", "2026-10-26 23:00", "B", "Bank of Korea 08:00 KST Oct 27", r"^south-korea-gdp-growth-yoy-in-q3")
add("DE-GDP-q3", GX, "non-US", "2026-10-30 09:00", "B", "Destatis 10:00 CET", r"^germany-gdp-growth-in-q3")
add("EZ-GDP-q3", GX, "non-US", "2026-10-30 10:00", "B", "Eurostat 11:00 CET", r"^eurozone-gdp-growth-in-q3")
add("MX-GDP-q3", GX, "non-US", "2026-10-30 12:00", "B", "INEGI 06:00 Mexico City", r"^mexico-gdp-growth-in-q3")
add("UK-GDP-q3", GX, "non-US", "2026-11-12 07:00", "B", "ONS 07:00 London (GMT)", r"^uk-gdp-growth-in-q3")
add("JP-GDP-q3", GX, "non-US", "2026-11-15 23:50", "B", "Cabinet Office 08:50 JST Nov 16", r"^japan-gdp-growth-in-q3")

# Families looked at and excluded before any tape was read (no scheduled second, or not decided by one release)
EXCLUDED = [
    (r"^bank-of-japan-decision", "BoJ announces at no fixed time"),
    (r"^bank-of-brazil-decision", "Copom announces 'after 18:30' Brasilia, no fixed second"),
    (r"^central-bank-of-colombia-decision", "no fixed announcement time"),
    (r"^(south-african-reserve-bank|reserve-bank-of-india|bank-of-korea)-decision", "announced during a speech / no fixed second"),
    (r"^peoples-bank-of-china-rate-change", "deadline market, not one scheduled release"),
    (r"inflation-china-annual", "rules give only the month, no official calendar obtained in this sandbox"),
    (r"^bank-of-israel-decision-in-august", "rules date 2026-08-31 is before the study period"),
    (r"^(university-of-michigan-consumer-sentiment-august|canada-gdp-june)", "release before 2026-09-01"),
    (r"^fed-decision-in-september-568", "duplicate event closed in May 2026"),
    (r"^(fed-rate-hike-by|no-change-|hike-25-bps-flips|what-will-kevin-warsh-say|who-will-be-confirmed|what-will-happen-before|trump-drops)", "not decided by a number published at a scheduled second"),
    (r"^(will-us-crude-oil-reserves|us-gas-price|will-gas-|how-(high|low)-will-\d+-year-treasury|what-will-the-median-home-value|how-many-ships|avgpt|will-ships|0-ships|ship-traffic|peak-daily|strait-of-hormuz|usd-x-iranian|will-usd-hit|elon-musk-net-worth|gpu-rental|.*largest-company|.*ipo|another-critical|.*comparable|meta-headcount|spotify|2k-container|trump-issues|us-imposes|who-will-buy|what-will-be-in-the-uk-budget|cxmt)", "price/level/ladder markets without a single scheduled release second"),
]


def match(slug):
    for r in R:
        if r["pattern"].search(slug):
            return r
    return None


def excluded_reason(slug):
    for pat, why in EXCLUDED:
        if re.search(pat, slug):
            return why
    return None
