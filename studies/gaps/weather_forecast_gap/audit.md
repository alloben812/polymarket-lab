# Audit: weather_forecast_gap (daily-high bucket prices against public MOS/NBM forecasts)

Auditor: independent agent with a fresh context, 2026-11-27. Checklist: `docs/audit-checklist.md`. I did not edit the
author's files. My code is in `audit/` and imports none of the author's code (`common.py`, `s05`, `s09`) and no
`pmlab` analysis functions:

- `audit/a1_rule.py [LAG] [TIE]`: universe parsed from the raw gamma dump `events_raw.json.gz`, local day with
  `zoneinfo`, winners cross-checked against gamma `outcomePrices`, first buyable print read from the raw tapes in
  `data/tape/`, all 24 cells, the selection rule, robustness checks, a blind rule, tape completeness, and a diff
  against the author's `entries.csv`. `LAG` = seconds subtracted from block time (0 = author, 3 = AGENTS.md rule 4);
  `TIE` = which print counts when several buyable prints share one block second (`min` price = author, `max` =
  conservative, `api` = tape order). Output of the conservative run: `audit/a1_out_conservative.txt`.
- `audit/a2_model.py`: my own implementation of protocol B2-B4 (METAR maximum, MOS run selection with public-time
  delays, trailing 45-day errors, BEST and AVG) from the raw Iowa Mesonet files, compared with `obs_max.csv` and
  `model_probs.csv`.
- `audit/a3_scores.py`: F2 log scores (market vs model) from the raw price histories, coverage of tapes, and win rate
  of the buckets the rule bought.

## Verdict: HOLDS (NO EDGE)

The negative result reproduces exactly from the raw data with independent code. My corrections lower only the
tuning-period number. November stays at zero. I found no bug that could be hiding an effect.

**Corrected headline:** NO EDGE. I used the conservative fill rule (match time = block time - 3 s, and the
highest-priced buyable print when several share a block second). Under it the selected cell (AVG, g >= 0.15, 60 h)
made **+0.2% on stake in November, +$1.1 on $540, +0.02 c/share, 54 entries on 53 city-days, t 0.01** (author:
+0.5%, +$2.6, +0.05 c). Its tuning result is **+32.4%, t 0.88, 90 entries on 88 city-days** (author: +42.1%, t 1.15,
93 entries). The selected cell does not change. All six variants pooled over the four decision times returned
-10.6% .. +9.2% in November, |t| <= 0.52, on 106-499 entries and 89-247 city-days. The market beats the AVG model on
November log score at every horizon: t = 2.4 / 7.5 / 8.0 / 23.0 by city-day at 60 / 36 / 18 / 6 h, reproduced to
the third decimal.

## Reproduction (check 6)

| quantity | author | mine, author's fill rule (`a1 0 min`) | mine, conservative (`a1 3 max`) |
|---|---|---|---|
| all-cell entries | 4,857 | 4,857 (0 only-mine, 0 only-author) | 4,807 |
| selected cell, tune: n / city-days / net / return / t | 93 / 91 / +391 / +42.1% / 1.15 | 93 / 91 / +391.4 / +42.1% / 1.15 | 90 / 88 / +292.0 / +32.4% / 0.88 |
| selected cell, Nov: n / city-days / net / return / t | 54 / 53 / +2.6 / +0.5% / 0.01 | 54 / 53 / +2.6 / +0.5% / 0.01 | 54 / 53 / +1.1 / +0.2% / 0.01 |
| selected cell, Nov: c/share, avg price, win rate | +0.05 | +0.05, 0.149, 0.185 | +0.02, 0.149, 0.185 |
| pooled Nov return range (6 variants) | -10.5% .. +8.4% | -10.5% .. +8.4% | -10.6% .. +9.2% |
| pooled Nov t range | -0.51 .. +0.27 | -0.51 .. +0.27 | -0.52 .. +0.24 |
| selection on tune (max city-day t, >= 50 city-days) | AVG 0.15 60 h | same (t 1.153) | same (t 0.879) |
| Nov cells, max abs t | below 2.1 | 2.00 (AVG 0.25 36 h, negative) | 2.00 |

- The whole sample was reproduced, not a quarter: all 737 city-days, 8,107 markets and 24 cells.
- Model (`a2`): 64,856 bucket probabilities (737 city-days x 4 times x 2 versions x 11 buckets) were recomputed from
  the raw MOS and METAR files. 0 differ by more than 1e-4 (largest difference 4.9e-6, from rounding in the file).
  The recomputed METAR maxima match all 1,414 station-days that have at least 20 reports.
- F2 (`a3`): November log score, model AVG / market: 60 h 1.762 / 1.638, 36 h 1.582 / 1.213, 18 h 1.471 / 1.065,
  6 h 1.485 / 0.063. These are the author's numbers. The mean price sum at 60 h is 1.39.

## Checklist

### 1. Look-ahead: clean
- **Model.** The training days for target D at decision t are D-45..D-1, and only those whose local day ended at
  least 2 h before t (`tend(q) + 7200 <= t` in `a2`). A run is used only if run time + assumed delay <= t. The
  delays (NBS/NBE 2 h, GFS 5 h, MEX 6 h, NAM 4 h) are on the slow side. The author's one live poll put GFS 12Z at
  +4 h 11 to +4 h 19. No market data enters the model, and my rebuild needs only the IEM files and `markets.csv`
  bucket bounds. Remaining risk: the IEM archive stores run time, not receipt time. Any error there would only flatter
  the model, which loses anyway.
- **Entry.** The entry print must have block time >= t (author). Under AGENTS.md rule 4 (match = block - 3 s) a
  print matched up to 3 s before t could slip in. Running `a1` with `LAG = 3` and the author's tie rule changes
  nothing in the selected cell (93 / +$391.4 tune, 54 / +$2.6 Nov). The protocol's "block time as is" is a small
  departure from rule 4 with no effect.
- **F2 prices.** `prices-history` points are taken at or before t. If a point stood for the close of its bucket,
  this could leak up to 5 or 30 min. Shifting every lookup back 30 min changes the November log-score differences by
  at most 0.025 (t 2.3 / 7.2 / 7.9 / 21.7). F2 is not used for trading.
- **Outcomes.** The outcome enters only through P&L. Winners from data-api agree with gamma `outcomePrices` on
  8,107 of 8,107 markets.

### 2. Execution: one optimistic detail, which only affects tuning
- **Tie-break inside a block second (new finding).** `s09.entry_print` sorts buyable prints as `(t, price, size)`
  tuples. When several buyable prints share a block timestamp, it therefore takes the **cheapest** one as "the first
  print". The protocol does not specify this, and the true order inside a block is unknown. It happens on 336 of the
  4,857 entries, with a mean spread of 1.93 c between the cheapest and dearest print in that second.
  - Taking the dearest print instead (`a1 0 max`) gives the tuning selected cell 90 entries, +$292, +32.4%, t 0.88
    (instead of +42.1%, t 1.15).
  - November changes from +0.5% to +0.2%. Pooled tuning rows drop by 1-5 points (AVG 0.15: +7.0% -> +2.1%).
  - Severity: low for the verdict. It inflated the in-sample number that made the selected cell look promising and
    left the out-of-sample number at zero.
- **Size.** The protocol buys $10 at the first print whatever the print's size. The author already reports that only
  10.6% of entry prints covered $10 (median $1.84). Capping the size to the print, my numbers for the selected cell
  are: tune +13.0% on $259 staked (t 0.45), November -0.9% on $184 (t -0.03).
- **Liquidity used twice.** A bucket bought at two decision times or under two variants counts in each, as
  pre-registered. Pooled rows add the same cells together, and clustering by city-day absorbs the duplication.
  Each print is used once per cell.
- **Buyability.** Prints come from taker BUY Yes, or taker SELL No at 1 - p (the market is negRisk, outcomes
  `["Yes","No"]`). This is the right reading of the tape: one row per fill on the taker side (NOTES.md).

### 3. Fees and accounting: clean
- Net per entry = shares x (y - p) - 0.01 x p x (1 - p) x shares, with y = 1 if the bucket won. The fee is counted
  once and the sign is right: buying YES pays out 1 when the bucket wins.
- My zero-fee run of the selected cell gives November +1.1% and tuning +31.8% (conservative fill). The fee is not
  what kills the result.
- Fee actually charged at the time (0.05 until 2026-11-20 23:59 UTC, 0 on 10-20..31, 0.01 after; NOTES.md): selected
  cell November -2.2%, tuning +28.7%.
- Rebates are 0 (`pmlab.fees` rate table: weather 0.01).
- Bucket bounds and "or below / or higher" edges: the winning bucket contains the recomputed METAR maximum on 374/374
  METAR-rule city-days and on 360/363 weather.gov-rule city-days. This also validates the bucket parse, the
  condition join and the time zone.

### 4. Statistics: clean, and the in-sample number was fragile
- Standard errors are clustered by city-day and by calendar date. Both give the same t (0.01 / 0.01 November; 0.88 /
  0.89 tune, conservative).
- The periods do not overlap: tuning D <= 10-31, report D = 11-01..11-25, keyed by observation day. The last tuning
  markets close on the morning of 11-01, and the first reporting markets are created about 70 h before the end of
  11-01. Prices overlap in calendar time, but no reporting outcome is known during tuning.
- Variants: 6 rules x 4 times = 24 cells + 6 pooled rows. The fee sensitivity uses the same trades. The post-hoc
  S1-S4 and D1-D3 choose nothing. This matches the protocol. Under 24 cells, a best tuning t of 1.15 is what chance
  alone produces.
- Without the best day, the selected cell's tuning return falls to +19.7% (author's fill) or +9.1% (conservative).
  Without its 10 best markets it is -48% to -57% (t about -3.4 to -4.3). In November, without the best day (11-15)
  it is -23.8%. The +42% was a handful of cheap winners.
- **Blind comparison** (`a1`, 200 draws): same 60 h decision, same first-print rule, 0.03-0.85 band, up to 3 random
  buckets per city-day, no model signal. Median return: tune -0.4% [5-95%: -4.6, +2.7], November +1.9% [-4.0, +5.8].
  The selected cell's November +0.2% is no better than blind. Caveat: tapes exist only for buckets the model gave
  >= 0.11, so the "blind" pool is restricted to those buckets.
- The buckets the rule bought (unique bucket x decision time) had a mean model probability of 0.342 and a mean
  price of 0.157, and won 13.9% in November (tune: 0.356 / 0.181 / 17.5%). They won at or below the market price,
  as the author says.

### 5. Data: clean
- Universe: 737 city-days = 11 cities x 67 dates, 8,107 markets, every event with exactly one winner. Gamma
  `eventStartTime` equals my zoneinfo local midnight on all 8,107 markets, including the 25-hour local day of
  2026-11-01 (DST end).
- Tapes: every bucket the rule could ever reach (model probability >= 0.11 at some slot and version, 3,712 buckets)
  has a tape file. On the 1,383 traded markets with volume >= 50, tape shares / gamma `volumeNum` is 1.000 (p1) /
  1.000 (median) / 1.002 (p99), so no tape is truncated.
- Price histories: 8,107 of 8,107 present (7,381 at 300 s, 726 at 1,800 s); no corrupt lines.
- Survivorship: the study uses `closed=true` events only, but every one of the 11 x 67 city-days is present, so
  nothing went missing.

### 6. Protocol deviations
- The ones the author declares (the parallel price download, the post-hoc S/D tables, the CI method) are harmless.
- Not declared: (a) the cheapest-print tie-break inside a block second (above); (b) block time used without the 3 s
  of AGENTS.md rule 4. The protocol says "as is", so this is stated in the protocol but contradicts the lab rule.
  Neither changes the verdict.
- Timing: `protocol.md` (16:12) predates `entries_slice.csv` (16:53) and the price downloads (log 17:17). The study
  folder is not a git repository, so the order of work rests on file mtimes and could not be verified from history.

## Could a bug be hiding a real effect?

I checked the sign of the payoff, the condition-to-bucket join (independent bucket parse, 734/737 agreement with the
METAR maximum), the time zone and DST, the mapping of the forecast slot (an independent rebuild reproduces every
probability), whether the fee is counted twice (no; the zero-fee run is also about zero), tape truncation (none),
and the direction of the gap (model minus entry price, buy YES). None of these hides anything. The only hint of
information beyond the market is the author's post-hoc 60 h encompassing regression (D3, t 3.0-3.4). I did not
reproduce it. The pre-registered 60 h cells and the blind comparison show it does not turn into money at first-print
prices.

## What an account of about 200 EUR could earn, and what live trading would need

Nothing positive remains after corrections: expected profit is **$0 a day**. The selected cell's November result is
+$1.1 over 25 days on $540 staked, and capping size to the print gives -$1.6 on $184. To trade this live you would
need, at minimum:

- a forecast that is better than the free MOS/NBM station guidance, since the market already prices that guidance
  and beats it at every horizon;
- a new pre-registered period, because nothing in this study qualifies;
- the CLOB order book (best ask and depth) at the moment of decision instead of tape prints;
- resting limit orders, because the median buyable print is $1.84 and only about 11% of prints cover $10;
- capital of about $100-450 tied up for one to three days.

Speed is not the constraint here: prints arrive 20-60 min apart.

## What was checked and is clean
Universe and winners (two sources); time zone and DST; METAR maximum; MOS run selection and public-time rule;
trailing-error model (all 64,856 probabilities); the 24 cells and the selection rule; fee formula and sign; tape
completeness; F2 log scores; robustness to block lag; clustering by city-day and by date. Issues found: the
optimistic tie-break inside a block second (tuning +42% -> +32%, November unchanged), and the in-sample result
resting on a few markets. Neither changes NO EDGE.
