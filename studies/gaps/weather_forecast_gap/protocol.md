# Weather: do daily highest-temperature bucket prices lag public station forecasts? (protocol)

Written 2026-11-27 BEFORE any market price, tape or resolution was analysed. What had been looked at when this was
written: NOTES.md, the toolkit, the gamma event list (slugs, rule texts, stations, bucket labels, creation times), the
shape of one `prices-history` and one tape response (format check on two NYC markets, no outcome used), and the Iowa
Mesonet MOS archive (which models and fields exist). After this file the rules do not change; anything that turns out
to be ambiguous later is resolved in the conservative direction and listed under "Deviations" in results.md.

## Part A. Protocol as fixed by the lab lead (verbatim in substance)

Background. A first look at one profitable account showed its profit came from buys made one to seven days before
the market's end, not from the last day. Hypothesis: bracket prices are set by casual money and lag the public
numerical forecasts. Settlement rule: the highest temperature in the hourly T-group of the routine METAR reports of
one named station, tenths of a degree Celsius converted to Fahrenheit and rounded half-up for US cities; each
city-day is an event with one binary market per bucket; fee rate 0.01.

Universe. Daily highest-temperature events for US stations resolved between 2026-09-20 and 2026-11-25
(`pmlab.gamma.iter_events(closed='true', tag_slug='weather', ...)`); each city's rules read once for the station and
the local-day boundary. Truth: the bucket that actually won (`pmlab.dataapi.resolutions`) and the settlement maximum
recomputed from Iowa Mesonet routine METARs (`asos.py`, `data=metar`, `report_type=3`).

Forecasts. Historical station guidance with its issue time from the Iowa Mesonet MOS archive (NBE, NBS, GFS, MEX,
LAV, MET). Find which models/fields are served for 2026, which field is the daily maximum, when each run becomes
public (run time plus the documented dissemination delay; say what was assumed), how the forecast day maps to the
market's local day. If the archive does not serve what is needed, look for another public historical source; never
use a source that only has today's forecast.

Model (fixed before looking at market prices). For station s, lead L (hours from the public time of the run to the
end of the local day) and model m: forecast error e = settled maximum minus forecast maximum. Empirical distribution
of e by station and lead bucket on a trailing window of the previous 45 days only; probability of a bucket = share of
that error distribution that places the settled maximum inside it. Two versions: the single best model by trailing
mean absolute error, and a simple average of the available models.

Decision times. Each city-day at 60 h, 36 h, 18 h and 6 h before the end of the local day, using the latest run
that was public at that moment.

Prices and fills. `prices_history` (300-second buckets) for a first comparison; for the trading rule the entry price
is the first tape print at or after the decision time that shows the bucket's YES was buyable (taker BUY of YES, or
taker SELL of NO at one minus that price) within 3 hours; no print means no fill.

Measurements.
- F1 forecast skill: MAE and probability assigned to the winning bucket by lead, per city; calibration of the model's
  bucket probabilities.
- F2 market skill at the same moments: price of the winning bucket, calibration of bucket prices; model vs market by
  lead (log score and Brier score per city-day).
- F3 rule (3 thresholds x 2 model versions = 6 variants, each evaluated at the 4 decision times): buy YES of a bucket
  when model probability minus entry price >= g, g in {0.08, 0.15, 0.25}, and 0.03 <= entry price <= 0.85; $10 per
  entry; at most 3 buckets per city-day per decision time (largest gaps first); fee 0.01 * p * (1 - p) per share;
  hold to settlement. Tune on events resolved before 2026-11-01, report 1-25 November separately. Cluster by city-day
  and also by calendar day. Report entries, city-days, average price, win rate, net cents per share, net dollars,
  return on dollars staked, t.
- F4 where the edge sits: by lead, by price of the bucket bought, by city; share of entries with a confirming print.

State the number of variants run; say plainly if the forecast source is not a true archive.

## Part B. Concrete choices (mine, fixed now)

### B1. Universe
- Source: `gamma.iter_events(closed="true", tag_slug="weather", limit=50, end_date_min=2026-09-18, end_date_max=2026-11-27)`,
  slug `highest-temperature-in-<city>-on-<month>-<day>-2026`.
- US cities (all there are in the tag): atlanta, austin, chicago, dallas, denver, houston, los-angeles, miami, nyc,
  san-francisco, seattle. 11 buckets per event (lowest "X°F or below", nine 2 °F ranges, highest "Y°F or higher"),
  parsed from `groupItemTitle`.
- A city-day is keyed by its TARGET (observation) date D from the slug. Universe: D from 2026-09-20 to 2026-11-25.
  "Resolved before 2026-11-01" is read as D <= 2026-10-31 (tuning, 42 dates); reporting period D = 2026-11-01 ..
  2026-11-25 (25 dates). (The market for D resolves on the morning of D+1; keying by D keeps whole local days
  together.)
- Station: taken from every event's own rule text (`resolutionSource`), not assumed constant. Observed when reading
  the rules: for D <= 2026-10-22 the rule is "highest reading in the Temp column of the NOAA hourly data,
  weather.gov/wrh/timeseries?site=<id>, whole degrees F" and Denver is Buckley (KBKF); for D >= 2026-10-23 the rule
  is the METAR T-group rule on aviationweather.gov and Denver is KDEN. Other cities: KATL, KAUS, KORD, KDAL, KHOU,
  KLAX, KMIA, KLGA, KSFO, KSEA in both periods.
- Local day: the station's civil day with daylight saving (America/New_York: nyc, atlanta, miami; America/Chicago:
  chicago, dallas, houston, austin; America/Denver: denver; America/Los_Angeles: los-angeles, san-francisco,
  seattle). T_end(D) = local midnight that ends D, in UTC. Checked against gamma `eventStartTime` (+ one local day)
  where that field is present.
- An event is dropped (and counted) if it does not have exactly one bucket with final YES price 1.

### B2. Truth
- Winner: `dataapi.resolutions` (final price of the Yes token). All profit and loss uses the actual winner.
- Recomputed maximum (the number the error statistics are built on, both rule periods): Iowa Mesonet `asos.py`,
  `report_type=3` (routine), `data=metar`, 2026-08-01 .. 2026-11-27 UTC, all reports whose valid time falls in the
  local day; temperature = T-group tenths of a degree C if present, else whole degrees from the body; F = C*9/5+32
  rounded half-up; the maximum over the day. A station-day with fewer than 20 routine reports has no recomputed
  maximum (excluded from error statistics and from F1; still traded and settled on the actual winner).
- The agreement between the recomputed maximum's bucket and the actual winner is reported separately for the
  weather.gov period and the METAR period. No rule changes depending on it.

### B3. Forecast source and mapping
- Archive: `https://mesonet.agron.iastate.edu/cgi-bin/request/mos.py` (station, model, sts, ets, csv), 2026-08-01 ..
  2026-11-27, one request per station/model/month, >= 6 s between requests, cached on disk.
- Served for 2026 (probed on KLGA, 1-3 Nov): NBS runs 00/06/12/18Z, field `txn` (with `xnd`, its spread);
  NBE runs 00/12Z, `txn`; GFS (the short-range GFS MOS, "MAV") runs 00/06/12/18Z, field `n_x`; MEX runs 00/12Z,
  `n_x`; NAM (= MET, the service calls it NAM; "MET" is rejected) runs 00/12Z, `n_x`, the archive page says it ends
  with the 2026-11-03 12Z run (NAM retired); LAV runs 00/06/12/18Z only, hourly `tmp`, NO maximum field.
- Daily maximum field: `txn` (NBS/NBE) and `n_x` (GFS/MEX/NAM) are the 12-hourly max/min; the value stored at
  forecast time 00:00Z is the daytime maximum of the local day that is ending (MOS convention: daytime max 7am-7pm
  local standard time), the value at 12:00Z is the night minimum. Mapping: forecast maximum for local day D =
  value at ftime 00:00Z of D+1 (UTC date). This is the same slot for all four US time zones. Sanity check on the
  mapping (weather data only): the MAE against the recomputed maximum must be smallest for this slot compared with
  the 00:00Z slots one day earlier and later; reported.
- Known mismatch that the error distribution has to absorb (not corrected otherwise): the guidance is a 7am-7pm
  continuous maximum in whole F, the settlement is the maximum of the hourly reports of the whole civil day.
- Model families (to avoid counting one model twice):
  NBM = NBS, or NBE when no usable NBS run contains the slot; GFSMOS = GFS (MAV), or MEX when no usable GFS run
  contains the slot; NAMMOS = NAM while it is served. LAV is not used (no maximum field, 38 h range).
- Public time of a run = run time + assumed delay: NBS and NBE 2 h 00; GFS (MAV) 5 h 00; MEX 6 h 00; NAM 4 h 00.
  These are assumptions on the slow side of what I know of the NWS schedule (NBM text about +1.1 h, MAV about
  +4.2 h, MEX about +5 h, MET about +3 h); the IEM archive stores the run time only, not the receipt time. A
  background poll of the IEM "latest run" service on 2026-11-27 measures when the 12Z/18Z runs appear; that
  measurement is reported, and it does not change the delays.
- A run is "usable" at decision moment t if public time <= t, public time >= t - 24 h, and it has a non-missing
  value in the slot. Per family the usable run with the latest public time is used (within a family, on equal
  public time NBS before NBE and GFS before MEX).

### B4. Model
- Decision moments: t(D, d) = T_end(D) - d hours, d in {60, 36, 18, 6}. The "lead bucket" is d (the lead of the run
  actually used is recorded and reported).
- For a station s, slot d and family m, the forecast f_m(s, D, d) is the usable run's value. Version AVG:
  f_avg = arithmetic mean of the families usable at t (at least one). Version BEST: the family with the lowest
  trailing MAE (below); ties in the order NBM, GFSMOS, NAMMOS.
- Trailing errors: for target day D and slot d, the training days are D' in [D-45, D-1] whose local day ended at
  least 2 hours before t(D, d) (their maximum was fully observable) and which have a recomputed maximum and a
  forecast built the same way at t(D', d) (same station, same slot, the families usable on that day).
  e(D') = recomputed maximum(D') - f(D', d). At least 20 training errors are required, otherwise there is no model
  probability for that city-day/slot/version (counted, not traded).
- Bucket probability: share of training errors e_i for which roundhalfup(f + e_i) lies in the bucket (lowest and
  highest buckets are open-ended). No smoothing, no use of `xnd`, no market information.
- Denver: errors are per station; for D >= 10-23 the KDEN history is used (it exists for all dates), before that
  KBKF. If KBKF has no guidance in the archive, Denver before 10-23 has no model and is counted as such.
- Everything in B3-B4 is computed and written to disk (`model_probs.csv`) before prices or tapes are downloaded.

### B5. Market prices (F2)
- `dataapi.prices_history(yes_token, t_first, t_last, 300)`; where 300-second history is no longer kept (older than
  about 60 days) the 1800-second history is used and flagged.
- Price at decision moment t: the last point with timestamp <= t and >= t - 6 h; else missing.
- A city-day/slot enters F2 only if all 11 buckets have a price and a model probability exists (both versions
  reported on their own sets). Market probability = price / sum of the 11 prices; the raw sum is reported.
- Scores per city-day: log score = -ln(max(p_winner, 0.01)); Brier = sum over buckets of (p_b - y_b)^2.
  Model minus market difference per city-day, mean with standard error clustered by city-day (`stats.mean_se`) and by
  calendar date D (mean of the date's city-days first).
- Calibration bins for bucket probabilities/prices: [0, .05), [.05, .15), [.15, .30), [.30, .50), [.50, .70), [.70, 1].

### B6. Trading rule (F3) and fills
- Tape: `updown.tape(condition)` logic (whole-market tape, cached) for every bucket market of the universe.
- Entry print of a bucket at decision moment t: the first tape row with block timestamp in [t, t + 3 h] that is a
  taker BUY of Yes (entry price = its price) or a taker SELL of No (entry price = 1 - its price). Block time is used
  as is (it is 2-3 s after the match, so the print is certainly not before the decision). No such row = no fill.
  The first such row is THE entry price even if a later row would be better.
- Signal: model probability (as of t; not refreshed during the 3 hours) minus entry price >= g and
  0.03 <= entry price <= 0.85. Per city-day and decision time at most 3 buckets, largest gap first.
- Size: $10 per entry, shares = 10 / price. Fee per share = 0.01 * p * (1 - p) (today's weather rate, as the lab
  lead fixed it). Net per share = y - p - fee, y = 1 if the bucket won. Stake = $10 (fee on top).
- 6 variants (g in {0.08, 0.15, 0.25} x {BEST, AVG}), each at 4 decision times = 24 cells, plus each variant pooled
  over the 4 decision times (the same 24 cells added up; a bucket bought at two decision times counts twice).
- Statistics per cell and period: entries, city-days, average price (share-weighted cost / shares and simple mean),
  win rate, net cents per share (`stats.ratio_cluster`, clusters = city-days), net dollars, return on dollars staked
  (`ratio_cluster`), t clustered by city-day and t clustered by calendar date D.
- Tuning: on D <= 10-31 the cell with the highest city-day-clustered t of return on stake among cells with >= 50
  city-days is "the selected cell"; its November result is the headline. All 24 cells and 6 pooled rows are reported
  for both periods regardless.
- Reported once as a sensitivity on the same trades (not a variant): the fee that was really charged at the time
  (0.05 until 2026-11-20, zero 2026-10-20..31, 0.01 from 2026-11-21, per NOTES.md).

### B7. F4 and capacity
- Results of the 6 variants (pooled over decision times and both periods shown separately) by decision time, by
  entry price band (0.03-0.10, 0.10-0.25, 0.25-0.50, 0.50-0.85) and by city.
- Capacity: (a) share of history-price signals (model minus `prices_history` price at t >= g, price in 0.03-0.85)
  that had any buyable print within 3 h, and the share whose print still met the rule; (b) share of entries whose
  entry print was at least as large as the shares needed for $10; median print size in dollars.

### B8. Order of operations
1. Events (done, metadata only). 2. METAR reports and recomputed maxima. 3. MOS archive. 4. Forecast table, trailing
errors, model probabilities for every city-day/slot/version -> disk. 5. Resolutions; agreement check; F1.
6. `prices_history`; F2. 7. Tapes; F3; F4. A small slice (nyc + chicago, 10 dates) is run through steps 5-7 first
for sanity checks only (win rate of all first prints priced 0.40-0.60 near 50%, fee equals the formula, print
timestamps inside the window), then the full period with the same code.

### B9. Verdict rule (lab lead)
OPPORTUNITY only if the reporting period is positive after fees with t above 2 across at least 100 markets; NO EDGE
if clearly negative or zero; otherwise INCONCLUSIVE.

Variants planned: 6 rule variants x 4 decision times = 24 cells. Nothing else will be tried; follow-ups go under ideas.
