# Weather observation gap: dead and locked temperature buckets after the airport's own reports

Protocol written 2026-11-27, BEFORE any outcome, price or tape was looked at. What was looked at before writing:
gamma event metadata (slugs, rule texts, bucket titles), one live aviationweather.gov response, the column layout of
one Iowa Mesonet response, the layout of one prices-history response and of three tape rows (to know the field names).
After this file the rules do not change; anything else goes under "ideas" in results.md.

## Protocol as given by the lab lead (verbatim summary)

Background: daily highest-temperature markets settle on the highest temperature in the hourly T-group remark of the
ROUTINE METAR reports of one named station (specials excluded), tenths of a degree C, converted to F and rounded
half-up for US cities, resolved at the first report of the next day. One event per city-day, one binary market per
bucket. Weather fee rate 0.01.

Question: once a routine report prints a value, every bucket wholly below it is dead, and late in the local day the
bucket holding the day's maximum is nearly locked. How long do prices take to reflect that, and what could a taker
have bought after a realistic delay?

- Universe: US-station daily highest-temperature events resolved 2026-10-01 .. 2026-11-25; cities with >= 30 days.
- Observations: Iowa Mesonet ASOS archive, raw METAR text, routine reports; parse the T-group; market's own rounding.
  Validate first: computed daily maximum must pick the winning bucket on >= 95% of city-days; list and explain misses.
- Prices: `pmlab.dataapi.prices_history`, 300 s, YES and NO token of every bucket. Tapes: `iter_trades(condition=)`.
- Public time of a report = observation time + 5 minutes.
- O1 dead buckets, O2 lock-in, O3 rules A (3 delays) and B (3 hours x 3 caps) = 12 variants, O4 risk cases.
- Tune on October, report November separately. Cluster by city-day. Fee 0.01 * p * (1-p) per share, rebates 0.

## Things found while reading the rule texts (metadata only) that the protocol did not know

1. The rule CHANGED inside the window. For every one of the 11 US cities:
   - observation dates up to 2026-10-22 ("old rule"): "highest reading under the Temp column ... Hourly Data" of
     `https://www.weather.gov/wrh/timeseries?site=<icao>`, whole degrees Fahrenheit, no mention of METAR type or T-group;
   - observation dates from 2026-10-23 ("new rule"): the routine-METAR / T-group / half-up rule of the background
     paragraph, source `aviationweather.gov/api/data/metar?ids=<ICAO>&format=raw&date=...&hours=27|30`. The text of
     Oct 23 differs from Oct 24+ only in the URL window (`hours=27` vs `hours=30`).
   Decision: the SAME reconstruction (routine reports, T-group, half-up) is applied to both regimes; validation is
   reported per regime. All city-days stay in the study whatever the validation says per day (a trader following
   the reports would have traded those days too); a regime whose match rate is under 95% is reported as failing and
   its results are shown separately, not dropped silently.
2. Fee history (NOTES.md): weather takers were actually charged 0.05 until 2026-11-20, zero on 2026-10-20..31, and
   0.01 since. The protocol fee (0.01) is used for all headline numbers because it is the fee a trader would pay
   now. The same fills are also re-priced at 0.05 as a sensitivity line (same entries, not a new variant).
3. Non-US cities use whole-degree-C buckets and are outside this study by protocol.
4. Denver changed station with the rule: Buckley Space Force Base (KBKF) for observation dates up to 2026-10-22,
   Denver International (KDEN) from 2026-10-23 (found while building the market table, before any outcome was
   compared). The station is therefore taken per event from its own rule text; KBKF reports are downloaded the
   same way. All other cities keep one station for the whole window.

## Concrete implementation choices

### Universe
- gamma `iter_events(closed='true', tag_slug='weather', limit=50, end_date_min=2026-09-29, end_date_max=2026-11-28)`,
  slug `highest-temperature-in-<city>-on-<month>-<day>-2026`.
- US city = bucket titles in degrees F and a K-prefixed ICAO station in the rule text: atlanta KATL, austin KAUS,
  chicago KORD, dallas KDAL, denver KDEN, houston KHOU, los-angeles KLAX, miami KMIA, nyc KLGA, san-francisco KSFO,
  seattle KSEA (station read from each city's rule text; any other station found is recorded).
- Kept: events whose `closedTime` (UTC) is in [2026-10-01 00:00, 2026-11-26 00:00). Observation date = the date in the
  slug. Period "October" (tuning) = observation dates up to 2026-10-31 (this includes Sep 30, resolved on Oct 1);
  "November" (reporting) = observation dates from 2026-11-01.
- An event is dropped (and counted) if its 11 bucket markets are not all resolved with exactly one YES winner in
  `pmlab.dataapi.resolutions`.
- Cities with fewer than 30 kept city-days are dropped (and named).

### Buckets
- Parsed from `groupItemTitle`: "X°F or below" = (-inf, X], "A-B°F" = [A, B], "X°F or higher" = [X, +inf). Whole degrees F.

### Observations
- `https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=<ID without K>&data=metar&...&tz=Etc/UTC&format=onlycomma`
  fetched twice per station: `report_type=3` (routine) and `report_type=4` (specials), 2026-09-29 .. 2026-11-27, one
  request at a time with pauses. Cached raw.
- Routine report = a row of the `report_type=3` download. The `report_type=4` rows are used only to explain misses
  and for O4 texts. (The archive text carries no METAR/SPECI label, so the archive's own classification is used.)
- Value of a report: T-group `T[01]ddd[01]ddd` -> tenths of a degree C (sign digit 1 = negative); if a routine report
  has no T-group, the whole-degree body temperature `TT/DD` (M = negative) is used (as in the new rule text); a
  report with neither is ignored. F = C*9/5+32, rounded half-up, in integer arithmetic: floor((18*t + 3250)/100)
  with t in tenths C.
- Local day: the observation time converted with zoneinfo (America/New_York: KLGA KATL KMIA; America/Chicago: KORD
  KDAL KAUS KHOU; America/Denver: KDEN; America/Los_Angeles: KLAX KSFO KSEA) falls on the observation date. DST
  ends Nov 1 (that day has 25 hours).
- Duplicate rows with the same observation time: the last one in the file is used (corrections); noted in O4 if the
  values differ.
- Public time = observation time + 300 s. Check against live data: aviationweather.gov `format=json` gives
  `receiptTime`; on 2026-11-27 28 reports of KLGA/KORD/KLAX/KDEN had receipt lags of 186-247 s for routine reports
  (one off-hour KORD report 1,387 s, one SPECI 312 s), and the raw listing `ids=KLGA&format=raw&hours=3` at 16:07 UTC
  showed the 15:51Z report. So +300 s is at or slightly after the official appearance of a routine US report.

### Validation (before any price work)
- Daily maximum = max rounded-F value over routine reports of the local day. Predicted winner = the bucket containing
  it. Match = predicted winner is the bucket whose YES resolved 1. Reported: all, per regime (old/new rule), per city.
  Every miss is listed with the computed value, the official winner and the explanation attempted (missing report in
  the archive, special report holding a higher value, 5-minute value, rounding, correction).
- The study goes on whatever the rate, but a rate under 95% (overall or in a regime) is stated at the top of
  results.md and the affected regime is shown separately.

### Prices
- `prices_history(token, local_midnight_utc - 6 h, closedTime + 600 s, 300)` for the YES and the NO token of each
  bucket, cached. "Price at time T" = the last point with timestamp <= T. What the stamp means (start or end of the
  5-minute bucket, mid or last trade) is checked against the tape on the test slice and stated. No point at or
  before T = missing (counted, excluded from shares).
- The NO series is used as a consistency check (YES + NO near 1); O1/O2 quote the YES series.

### Tapes
- `iter_trades(condition=...)`, whole market, cached under `data/gaps_weather_obs/tape/`. Row = one taker order
  (side, outcome Yes/No, size in shares, VWAP price, block timestamp). Match time = block time - 3 s (lab convention).
- "YES buyable at p for s shares at time t": a taker BUY of Yes at p (size s), or a taker SELL of No at q (then
  p = 1 - q). "NO buyable": the mirror image.

### O1 dead buckets
- Walk the routine reports of the local day in time order. Running maximum in rounded F. A "kill report" is a report
  whose value exceeds the running maximum (the first valued report of the day counts, previous maximum = -inf).
  Newly dead buckets of that report = buckets with upper bound < new maximum that were not dead before.
- For each (kill report, newly dead bucket): YES price at the observation time (pre-kill reference: last point
  <= observation time), and at public time +5, +15, +60 minutes. Shares of buckets with YES >= 0.02 and >= 0.05 at
  each offset. Shown for all dead buckets and for the subset "live before the kill" (pre-kill YES >= 0.05), and
  split first-report-of-day vs later reports.
- Tape after the public time (to the end of the tape) for dead buckets:
  (a) protocol measure: taker BUY Yes (dollars = size * p) and taker SELL No at q (dollars = size * (1 - q)):
      money paid by takers for a dead outcome;
  (b) stale liquidity taken by takers: taker SELL Yes at p >= 0.02 and taker BUY No at q <= 0.98: shares, and
      dollars of profit locked (size * YES-price, before fee), by time after the public time (<0 i.e. between
      observation and public time, 0-5, 5-15, 15-60, > 60 minutes).

### O2 lock-in
- Decision times: 17:00, 19:00, 21:00, 23:00 local on the observation date. Running maximum over routine reports with
  public time <= decision time; bucket holding it ("lock bucket"); next bucket up (none if the lock bucket is the top
  one). Reported by city and by month: share of city-days where the lock bucket is the final winner, share where the
  next bucket up wins, YES price (mean, median) of both at the decision time.

### O3 rules (12 variants, fixed)
- Rule A, d in {5, 15, 60} min: for each newly dead bucket (O1), decision time T = public time + d. Take the FIRST
  print with match time in [T, T + 1800 s] that shows NO was buyable (any price). Enter if and only if that print's
  NO price is <= 0.97. If the first print shows NO only above 0.97, or there is no print: no entry. (Conservative
  reading of "first tape print ... that shows the side was buyable": I do not search the window for a later, better
  print.)
- Rule B, h in {19, 21, 23} x cap in {0.80, 0.90, 0.95}: T = h:00 local. Lock bucket as in O2. FIRST print with
  match time in [T, T + 1800 s] that shows YES of the lock bucket was buyable; enter iff its price <= cap.
- Shares = min(printed size, 50 / price) (so at most 50 dollars); no minimum size. One entry per bucket per variant.
- Fee per share 0.01 * p * (1 - p); payoff 1 if the token bought wins, else 0; held to settlement
  (`pmlab.dataapi.resolutions`). Net per share = payoff - p - fee.
- All city-days are traded, including those where my reconstruction of the maximum disagrees with the official
  result (their losses count).
- Per variant and per period (October tuning, November reporting): entries, city-days with an entry, average
  entry price (share-weighted), win rate with a Wilson 95% interval, net cents per share with a city-day-clustered
  standard error and t (`pmlab.stats.ratio_cluster`), net dollars, dollars per calendar day of the period, and the t
  of per-city-day dollars (`mean_se` over city-days with an entry). "Tuning" = naming, from October only, the
  variant with the highest October net dollars; its November line is the headline. All 12 are reported for both
  periods. Sensitivity (same fills): fee 0.05.
- Verdict rule (given): OPPORTUNITY only if November is positive after fees with t > 2 across >= 100 markets.

### O4 risk
- Dead bucket revived: any bucket declared dead by my reconstruction that resolved YES. Locked bucket lost: lock
  bucket at 21:00 or 23:00 that did not win (listed one by one with the texts of the reports after the decision time
  and any special/corrected report); for 17:00 and 19:00 the cases are counted and the largest late rises listed.
  Each case is classified: later routine report higher (late warming), archive/official disagreement (correction or
  missing report), other.

### Sanity slice (before the full run)
NYC, observation dates 2026-11-10 .. 2026-11-16: (1) daily maxima vs winners; (2) YES + NO price sums; (3) fee per
share equals 0.01*p*(1-p) on the simulated fills; (4) all entry prints lie in [T, T+1800 s] and T lies in the local
day; (5) calibration: taker BUY-Yes prints at 0.40-0.60 in the slice should win about half the time; (6) meaning of
the prices-history stamp vs the tape.

### Missing data
- Report missing from the archive: nothing is imputed. City-days with fewer than 20 routine reports are flagged.
- Market without tape rows: no fills. Token without price history: missing in O1/O2 shares.
- API failures are retried by the toolkit; a market that still fails is listed and excluded.

### Order of operations
1 events and market table -> 2 observations -> 3 resolutions and validation -> 4 price histories -> 5 tapes ->
6 sanity slice -> 7 full O1-O4 run -> results.md. Variants run: 12 (plus the fee sensitivity re-pricing).
