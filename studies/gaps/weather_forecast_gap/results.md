# Weather: do daily highest-temperature bucket prices lag public station forecasts? — results

Study finished 2026-11-27 (resumed after an interruption; the pipeline, the model file and most downloads were
already there). Protocol: `protocol.md` (written before any price, tape or outcome was looked at; not changed).
Code: `s01_events.py` .. `s09_analyse.py` (protocol steps), `s07b_prices_parallel.py` (same price request as
`s07_prices.py`, threaded, used to finish the download), `s10_diag.py` and `s11_summary.py` (post-hoc, descriptive,
marked as such below). Raw outputs: `out/report.md` (everything `s09` prints), `out/summary.md` (`s11`),
`out/diag.md` (`s10`). Large intermediate files are in `data/gaps_weather_fc/` (not in git).

## Verdict: NO EDGE

- **The question.** Polymarket lists, for 11 US cities, one event per day with 11 temperature buckets ("62-63°F",
  ...). The account WrongBy1Degree suggested that bucket prices one to three days ahead are set by casual money and
  trail the free numerical forecasts (NWS MOS and NBM station guidance). If so, buying buckets that the public
  forecast rates well above the market price should pay after the taker fee. We tested that on 737 city-days.
- **The market is much better than the public station forecast at every horizon.** Log score (lower is better),
  November, 275 city-days: model AVG 1.76 / 1.58 / 1.47 / 1.49 against market 1.64 / 1.21 / 1.07 / 0.06 at 60 / 36 /
  18 / 6 hours before the end of the local day; the difference favours the market with t = 2.4 .. 23 (clustered by
  city-day). Same picture in the tuning months. The market's implied expected maximum misses by 1.05-1.80 °F, the
  bias-corrected forecast by 1.5-2.1 °F (60-18 h; at 6 h 0.5 against 1.5).
- **The trading rule finds nothing.** The cell picked on September-October (AVG model, gap >= 0.15, 60 h before the
  end of the day; tuning +42% on stake, t 1.15, 93 entries) made **+0.5% on stake in November (95% interval -63% ..
  +64%), +0.05 c/share, +$2.6 on $540 staked, 54 entries on 53 city-days, t 0.01**. All six variants pooled over the
  four decision times: November return -10.5% .. +8.4%, t -0.51 .. +0.27 (107-503 entries, 89-247 city-days); tuning
  -9.1% .. +7.0%, t -0.70 .. +0.46. Not one of the 24 cells has |t| above 2.1 in either period, and the only ones near
  2 are negative.
- **Why.** When the forecast and the market disagree, the market is right. Bucket prices bought by the rule averaged
  0.09-0.27 and won at 0.08-0.28, while the model said 0.25-0.56 (table S4: e.g. model 0.44 -> price 0.19 -> won
  0.192, n = 1,325). The model's probabilities are honest on all buckets taken together (calibration in
  `out/report.md`) but the buckets where it disagrees with the market are exactly where it is wrong.
- **Even a real edge would be tiny in dollars.** Only 11% of the entry prints (514 of 4,857) were big enough for the
  $10 the protocol buys; the median entry print was $1.84. Capacity for an account of about 200 EUR: **$0 a day of
  expected profit**; the money that could actually have been filled on the first print was about $12-62 a day.
- **For tomorrow's paper trading:** nothing from this study qualifies. Do not trade "public forecast vs bucket
  price" on these markets.

Verdict rule (B9): OPPORTUNITY only if November is positive after fees with t > 2 across >= 100 markets. November
is zero (t 0.01 on the selected cell, |t| <= 0.51 on every pooled variant), so NO EDGE.

## Data

- **Universe:** every closed gamma `weather` event with slug `highest-temperature-in-<city>-on-<date>-2026` for the 11
  US cities (atlanta, austin, chicago, dallas, denver, houston, los-angeles, miami, nyc, san-francisco, seattle),
  target dates D = 2026-09-20 .. 2026-11-25: **737 city-days (11 cities x 67 dates), 8,107 bucket markets**, 11
  contiguous buckets each, none dropped (every event had exactly one winner). Tuning: D <= 2026-10-31, 462 city-days
  (42 dates). Reporting: D = 2026-11-01 .. 11-25, 275 city-days (25 dates). Markets were created 67-71 h before the
  end of the local day, so all four decision times exist for every event.
- **Truth:** winners from `dataapi.resolutions`. Settlement maximum recomputed from Iowa Mesonet routine METARs
  (`asos.py`, report_type 3, T-group tenths of °C, half-up): its bucket equals the winner on **734 of 737 city-days
  (99.6%)**; 360/363 in the weather.gov-rule period (D <= 10-22; the three misses are 1 °F under a bucket edge, KORD
  09-20 and 10-15, KLGA 09-20), 374/374 in the METAR-rule period. Above the 95% the task required.
- **Forecasts:** Iowa Mesonet MOS archive (`mos.py`), runs 2026-08-01 .. 11-27 for 12 stations (KBKF added for Denver
  before 10-23), models NBS, NBE, GFS (MAV), MEX, NAM (NAM ends with the 11-03 00Z run); 252 cached files. This is a
  true archive of the issued bulletins, but it stores the run time, not the time the bulletin became public: the
  public time is assumed (run + 2 h NBS/NBE, + 5 h GFS, + 6 h MEX, + 4 h NAM, protocol B3). Live poll on
  2026-11-27: the GFS 12Z run became visible on the IEM service between 16:10:44 and 16:18:45 UTC (4 h 11 - 4 h 19
  after run time, inside the assumed 5 h); NBS and NBE 12Z were already visible at the first poll (16:10 UTC), which
  only says "<= 4 h 10 min". Daily-maximum slot check (36 h decision, MAE °F): D+1 00Z slot NBM 1.91 / GFSMOS 2.20 /
  NAMMOS 2.38 against 3.41-3.89 for the slots one day off, so the mapping is right.
- **Prices:** `prices-history` for all 8,107 YES tokens, T_end - 72 h .. T_end + 2 h: 7,381 at 300 s, 726 at the
  1800 s fallback (the oldest dates, older than the 60-day 5-minute retention).
- **Tapes:** whole-market tapes for the 3,826 markets that could ever be traded by the rule (model probability >= 0.11
  at some decision time; a lower one can never give gap >= 0.08 at a price >= 0.03) plus the sanity slice. Complete:
  tape shares / gamma `volumeNum` has median 1.000 and 5-95% range 1.000-1.000 (3,820 markets with volume >= 50).

## What was run

- **Model** (fixed before prices were fetched; `model_probs.csv` written 16:41, before the first price request): per station, decision
  time and family, the empirical distribution of (settled maximum - forecast) over the previous 45 days (>= 20
  errors), probability of a bucket = share of errors that put the maximum inside it. BEST = family with the lowest
  trailing MAE; AVG = mean of the usable families. 5,896 of 5,896 city-day x decision x version rows have a model.
  Re-running `s05_model.py` reproduces the three model files byte for byte.
- **Decision times:** 60, 36, 18, 6 h before local midnight that ends the target day.
- **Rule (F3):** buy YES of a bucket when model probability - entry price >= g, g in {0.08, 0.15, 0.25}, entry price
  0.03-0.85, at most 3 buckets per city-day and decision time, $10 per entry, hold to settlement, fee 0.01 x p x (1-p)
  per share. Entry price = first tape print in [t, t + 3 h] where YES was buyable (taker BUY Yes, or taker SELL No at
  1 - price); no print, no trade.
- **Variants:** 6 (2 model versions x 3 thresholds), each at 4 decision times = **24 cells**, plus each variant pooled
  over the 4 times (6 sums of the same cells). Selection on tuning: highest city-day t of return on stake among cells
  with >= 50 city-days. Protocol sensitivity on the same trades: the fee really charged then (0.05 until 11-20, zero
  10-20..31, 0.01 after). Post-hoc, not variants: size-capped fills (S2), confidence intervals (S1), the 6 h entries one
  by one (S3), model-vs-win-rate (S4), and the previous researcher's diagnostics D1-D3 (`s10_diag.py`).
- **Sanity checks** (slice nyc + chicago, 1-10 Nov, before the full run; and the full run): fee formula mismatches 0
  of 4,857 entries; every entry print inside [t, t + 3 h]; all first buyable prints at 0.4-0.5 (mean price 0.44) won 41-44% (n = 215-304
  per decision time, 60/36/18 h) and at 0.5-0.6 (mean 0.54-0.55) won 55-60%, i.e. prices on the tape are about fair.

## Headline numbers (fee 0.01, $10 per entry; clustered by city-day; from `out/summary.md` S1)

| rule | period | entries | city-days | staked $ | net $ [95% bootstrap] | return on stake [95%] | net c/share | t (city-day) | t (date) |
|---|---|---|---|---|---|---|---|---|---|
| selected: AVG, g 0.15, 60 h | tune | 93 | 91 | 930 | +391 [-202, +1,099] | +42.1% [-29.5, +113.6] | +5.71 | 1.15 | 1.15 |
| selected: AVG, g 0.15, 60 h | **November** | **54** | **53** | **540** | **+3 [-300, +371]** | **+0.5% [-62.8, +63.8]** | **+0.05** | **0.01** | **0.01** |
| BEST g 0.08 pooled | tune | 875 | 416 | 8,750 | -709 [-2,579, +1,382] | -8.1% [-30.8, +14.6] | -0.80 | -0.70 | -0.63 |
| BEST g 0.08 pooled | November | 503 | 240 | 5,030 | -271 [-1,773, +1,368] | -5.4% [-36.7, +26.0] | -0.50 | -0.34 | -0.36 |
| BEST g 0.15 pooled | tune | 489 | 302 | 4,890 | -445 [-1,895, +1,358] | -9.1% [-41.8, +23.6] | -0.85 | -0.55 | -0.56 |
| BEST g 0.15 pooled | November | 312 | 192 | 3,120 | +180 [-1,073, +1,607] | +5.8% [-36.7, +48.3] | +0.52 | 0.27 | 0.26 |
| BEST g 0.25 pooled | tune | 189 | 156 | 1,890 | +109 [-792, +1,190] | +5.8% [-47.4, +59.0] | +0.48 | 0.21 | 0.21 |
| BEST g 0.25 pooled | November | 107 | 89 | 1,070 | +90 [-627, +962] | +8.4% [-66.9, +83.6] | +0.62 | 0.22 | 0.23 |
| AVG g 0.08 pooled | tune | 856 | 400 | 8,560 | +256 [-1,566, +2,252] | +3.0% [-18.7, +24.7] | +0.32 | 0.27 | 0.29 |
| AVG g 0.08 pooled | November | 503 | 247 | 5,030 | -277 [-1,838, +1,487] | -5.5% [-38.7, +27.6] | -0.55 | -0.33 | -0.34 |
| AVG g 0.15 pooled | tune | 453 | 286 | 4,530 | +318 [-923, +1,718] | +7.0% [-22.9, +36.9] | +0.74 | 0.46 | 0.46 |
| AVG g 0.15 pooled | November | 281 | 175 | 2,810 | -294 [-1,284, +899] | -10.5% [-50.4, +29.4] | -0.95 | -0.51 | -0.42 |
| AVG g 0.25 pooled | tune | 153 | 125 | 1,530 | +40 [-714, +1,031] | +2.6% [-56.1, +61.3] | +0.24 | 0.09 | 0.09 |
| AVG g 0.25 pooled | November | 136 | 106 | 1,360 | +15 [-706, +956] | +1.1% [-60.1, +62.4] | +0.10 | 0.04 | 0.03 |

How to read: "return on stake" is net profit after the fee divided by dollars spent on shares. The intervals all
straddle zero widely; the sign flips between tuning and November for 3 of 6 variants.

All 24 cells, both periods (from `out/report.md`; November): 60 h cells -30.8% .. +20.2% (t -1.35 .. +0.37), 36 h
-60.7% .. +11.6% (t -2.00 .. +0.19), 18 h -7.7% .. +25.5% (t -0.31 .. +0.80), 6 h 1-5 entries per cell (see below).
Tuning: 18 h cells were the worst (-24.8% .. -29.8% for g 0.08/0.15, t -1.3 .. -2.1).

**Fee really charged at the time** (protocol sensitivity, pooled): tuning -11.5% .. +4.6%, November -13.1% ..
+5.8%; selected cell November -1.9% (t -0.06). Weather paid 0.05 until 2026-11-20, so the old fee would have made it
slightly worse; today's 0.01 changes nothing.

**Size-capped fills** (post-hoc, S2; shares = min($10 / price, size of the entry print), as AGENTS.md rule 4 asks):
the stake falls to 27-36% of the protocol's; November pooled returns -0.1% .. +52.8%, t -0.01 .. +1.03; tuning
-22.4% .. +16.3%, t -1.74 .. +0.94; selected cell November +9.2% [-59.5, +77.9] on $196 staked, t 0.26. Nothing
reaches t 2 and the best variant makes about $7 a day.

**Where the result sits (F4).** By entry price band, by city and by settlement-rule period nothing holds in both
periods. Examples (November, pooled): the 0.10-0.25 band loses in every variant (-6% .. -33%, t down to -2.0); the
0.03-0.10 band is positive in every variant (+8% .. +38%, t 0.18 .. 0.76) but was negative in tuning in all 6
(-1% .. -16%). Dallas and Seattle are positive in both periods in the four variants shown (t <= 1.97), San Francisco, Los
Angeles and Atlanta negative (some of their cells lost every entry); 11 cities x 6 variants, so a couple of such "stable" cities are expected by
chance. The weather.gov-rule period (D <= 10-22) is slightly positive (-0.3% .. +21%, t <= 0.72), the METAR-rule
period slightly negative (-7% .. -15%, t >= -1.15).

**The 6 h cells** look spectacular on paper (+134% .. +825% in 11 of 12 cells, -101% in one, on 1-11 entries each) and are noise: 17 distinct buys in
total over both periods (S3), 4 of them won, prints of $0.10-$30 (median $0.82) in buckets the market had at
3-21 c six hours before midnight, when 98% of the money is already on the observed bucket. At 6 h the model has no
information about the day's observations at all.

## Market vs model (F1, F2, D1-D3)

| November, 275 city-days | 60 h | 36 h | 18 h | 6 h |
|---|---|---|---|---|
| log score, model BEST / AVG | 1.79 / 1.76 | 1.68 / 1.58 | 1.63 / 1.47 | 1.62 / 1.49 |
| log score, market (prices normalised to sum 1) | 1.64 | 1.21 | 1.07 | 0.06 |
| t of the difference (by city-day / by date), AVG | 2.4 / 3.4 | 7.5 / 8.6 | 8.0 / 7.8 | 23.0 / 21.2 |
| mean raw price of the winner | 0.309 | 0.370 | 0.444 | 0.979 |
| model AVG mean probability of the winner | 0.236 | 0.269 | 0.298 | 0.298 |
| market favourite wins / model AVG top bucket wins (D2) | 39% / 33% | 51% / 39% | 59% / 39% | 99% / 40% |
| MAE °F market-implied mean / forecast AVG bias-corrected (D1) | 1.80 / 1.96 | 1.23 / 1.69 | 1.05 / 1.52 | 0.52 / 1.53 |

- Forecast MAE against the settled maximum, both periods: AVG 1.58-1.96 °F, BEST 1.80-2.15 °F, best at 18 h; mean
  forecast is 0.3-1.0 °F too warm (the guidance is a continuous 7am-7pm maximum, settlement the hourly reports).
  Hardest city San Francisco (MAE 2.2-2.5), easiest Miami (1.3-1.6).
- Market bucket prices are well calibrated from 36 h on (e.g. 18 h: price 0.39 -> won 0.38, n = 672; 0.58 ->
  0.61, n = 364). At 60 h the raw prices add up to 1.24-1.39 (thin, fresh books) and cheap buckets are overpriced
  (0.087 -> 0.047, n = 1,990).
- D3 (post-hoc encompassing regression, won ~ market probability + model probability, clustered by city-day): at 36,
  18 and 6 h the model adds nothing beyond the market (t -1.5 .. +1.6). At 60 h it does add something in both periods
  (coefficient +0.18-0.25, t 3.0-3.4; market coefficient 0.99-1.07). That is the only hint of a gap, it sits where the
  market's prices still sum to 1.3-1.4, and the pre-registered 60 h trading cells did not turn it into money in
  November (-30.8% .. +20.2%, t <= 0.37). Listed under ideas.

## Capacity (for an account of about 200 EUR)

- Signals: at $10 per entry the rule would stake $43-201 a day across the 11 cities (about 4-20 entries a day,
  positions held one to three days, so about $100-450 of capital tied up). That fits a 200 EUR account.
- Liquidity on the first print: only 10.6% of entry prints covered $10; median entry print $1.84; median wait to the
  first buyable print 20-31 min at 18-36 h and about 1 h at 60 h; at 60 h only 37-54% of the history-price signals
  had any buyable print within 3 h. With the size cap the fillable stake was about $12-62 a day (November).
- Expected profit: **$0 a day** (November, $10 per entry: -$11.8 .. +$7.2 a day, se $16-33, t -0.42 .. +0.26, 7-10
  positive days of 25). A trader resting limit orders instead of taking prints could buy more, but that is a
  different strategy with adverse selection that this study did not measure.

## What a trader would need to run it live

Nothing to run: there is no edge to capture. For the record, the setup would be the IEM or NWS MOS/NBM text
bulletins (free, hourly-to-6-hourly updates), the Polymarket CLOB book for the 11 events of each day, a reaction time
of minutes (the prints arrive 20-60 min apart, speed is not the bottleneck), about $100-450 of capital, and a
better forecast than the public station guidance, because the market already prices that guidance and more.

## Limitations

- The forecast is only the MOS/NBM station guidance from the IEM archive. Public times are assumed, not measured
  (one live poll: GFS 12Z public 4 h 11 - 4 h 19 after run time, within the assumed 5 h). Hourly NBM, HRRR, ECMWF and
  intraday observations, which traders surely use, are not in the model. The study answers "does the market lag
  this public guidance", not "can any forecast beat the market".
- The 12Z and 18Z MOS runs do not carry the current day's maximum, so at 18 h and 6 h the model uses runs 12-24 h old
  (mean lead from public time to the end of the day 18-25 h at the 6 h decision). The 6 h decision is a test against a
  market that already sees the day's observations; it was always going to lose.
- 726 of 8,107 price histories are 30-minute (late September); they enter F2 and the capacity row only, not the trades.
- Tapes were fetched only for buckets that the rule could ever buy (3,826 of 8,107); the "all first prints"
  calibration table is therefore biased toward model-likely buckets, as `s09` notes.
- The $10 entry assumes the first print could fill $10; 89% of the time it showed less. The size-capped
  sensitivity is post-hoc. Neither version changes the verdict.
- The t values printed for cells where every entry lost (for example -14,312 for AVG/0.15 in Los Angeles) are
  artefacts of a zero cluster variance; read them as "all lost", not as precision.
- Periods: 42 tuning dates and 25 reporting dates in autumn; one season, no summer or winter extremes.
- The study needs `audit.md` by an independent agent (AGENTS.md rule 7) before it counts as accepted.

## Deviations from the protocol

- Prices: the sequential download (`s07_prices.py`) had been stopped after 1,547 of 8,107 markets and left a
  truncated gzip; the 1,547 complete lines were kept and the rest fetched with `s07b_prices_parallel.py` (identical
  request, 300 s with 1800 s fallback, 6 threads, most recent dates first). No market was skipped.
- `s10_diag.py` (D1-D3) and `s11_summary.py` (S1-S4) are post-hoc and descriptive; they choose nothing and the verdict
  rests on the pre-registered cells only.
- Confidence intervals were not specified by the protocol: normal-approximation 95% intervals from the city-day
  clustered standard error, and a city-day cluster bootstrap (4,000 draws) for net dollars.

## Ideas, not tested

1. **60 h only, against a fresh and complete book.** The only sign of information beyond the market is at 60 h,
   where prices still sum to 1.3-1.4. A pre-registered test would compare the model with the CLOB best ask (not the
   last trade) right after market creation, buy with resting limit orders, and count the fills honestly. Expect
   small dollars: prints there are $1-3.
2. **Better forecasts.** Hourly NBM (`blend` v4 hourly text), HRRR or ECMWF point forecasts, with archives that
   store the issue time; plus the day's observations for the 18 h / 6 h decisions (the running maximum is public in
   real time). Only worth testing if the archive can prove what was public when.
3. **Overpriced cheap buckets at 60 h** (price 0.05-0.15 won 4.7% at a mean price 8.7 c, n = 1,990 bucket-days):
   selling them (buying NO) right after creation. NOTES.md already shows NO-buying at local midnight loses, so this
   would be a narrow, new pre-registered test of the first hours only.
4. **Station-specific bias.** San Francisco and Los Angeles were where the model lost most; Dallas and Seattle where it
   did best. A city filter chosen after seeing these tables would be data-mined; it needs a fresh period.
