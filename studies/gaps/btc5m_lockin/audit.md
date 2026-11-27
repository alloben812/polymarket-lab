# Audit of the BTC 5m lock-in study (sceptic's pass, 2026-11-27)

Audited: `protocol.md`, `results.md`, `common.py`, `fetch.py`, `build.py`, `analyze.py`, `diag.py`, `ws_timing.py`, `out/*`.
My code and raw outputs: `audit/a1_extract.py` .. `audit/a6_states.py`, `audit/out_a*.txt`. Nothing of the analyst's was
edited. My scripts do not import `pmlab` or the analyst's code: they read the Binance zips, the cached gamma
metadata and the raw tape files directly and carry their own model and rule engine.

## Verdict: WEAKENED

The study's own verdict (INCONCLUSIVE) stands, and its arithmetic is right: every headline number reproduces to the
last digit from the raw files, with independent code, on all 1,728 markets. I found no look-ahead, no accounting
error and no data hole. What does not survive is the size and the cleanness of the positive (filtered) part:

1. **The dollars assume we take half of everything that every real taker got.** All prints that satisfied the rule,
   with no caps, were worth $152/day (floor 0.99) or $289/day (floor 0.97) to 315-447 wallets together. The rule's
   "$80-139/day" is 48-52% of that pie (59-75% of it in the reporting period). The best real wallet made $25/day
   (one large print in one market); the most frequent one (30 of 62 markets) made $3/day.
2. **Two thirds of the result compares a 2-3 s old model with a current price.** Only 37% (floor 0.99) / 41%
   (floor 0.97) of the shares, and 29% / 33% of the dollars, are prints that are still 2 c under the model on the
   Binance second that closes at the match. For the rest the expected average had moved a median $11-14 against the
   favourite between the model second and the print: the market had marked the favourite down and the model had not
   seen it yet. What remains: 15 / 27 markets in six days, +3.9 / +4.3 c/share, $23 / $45 a day at the cap; in the
   reporting period 3 / 5 markets.
3. **"No traded market lost" is true only for one time alignment.** With the model one second fresher (D = 0), one
   second older (D = 2), or the block lag set to the measured 2 s instead of 3 s, the floor-0.97 variant has one
   net-losing market in 52-62 (t0 = 1795455000, 23 Nov). The floor-0.99 variant stays loss-free from D = -1 to
   D = 2 and loses a market at D = 3 and at lag 2 / D = 2. Match times are only known to about +-1.1 s, so these
   alignments cannot be told apart on the tape.
4. **The general effect behind it is gone in the reporting period.** Every buyable print of the Binance leader in
   the last minute with the distance outside the basis band, no model rule: +1.45 c/share on 21-24 Nov (t 2.9,
   512 markets), -0.47 c/share on 25-26 Nov (t -0.3, 219 markets, 15 of them with a losing print).

### Corrected numbers

| | study (D = 1, filter on) | corrected |
|---|---|---|
| floor 0.99 (judged), six days | 39 markets, 9,586 sh, +5.00 c/sh, $80/day, 0 lost | still cheap at the match: 15 markets, 3,515 sh, +3.94 c/sh, $23/day, 0 lost |
| floor 0.99, tune / report | 34 mkts +5.30 c $105/day / 5 mkts +3.58 c $30/day | 12 mkts +4.04 c $25/day / 3 mkts +3.69 c $18/day |
| floor 0.97 (widest), six days | 59 markets, 15,299 sh, +5.44 c/sh, $139/day, 0 lost | still cheap at the match: 27 markets, 6,283 sh, +4.34 c/sh, $45/day, 0 lost |
| floor 0.97, tune / report | 49 mkts +5.23 c $163/day / 10 mkts +6.43 c $90/day | 22 mkts +4.42 c $51/day / 5 mkts +4.11 c $34/day |
| lost markets, floor 0.97 | 0 of 59 | 0-1 of 52-62 for D = -1..2 and lag 2..3 (1 in five of seven neighbouring alignments), 2 of 65 at D = 3 |
| loss-rate bound | 0 of 59: 95% upper bound 5.0% vs break-even 5.4% | 0 of 27: upper bound 10.5% vs break-even 4.4%; 0 of 15: 18.1% vs 3.9% |
| dollars a newcomer could expect | $30-163/day "at this size" | whole pie $152-289/day for all takers ($51-120 in the reporting period); best real wallet $25/day, most systematic real wallet $3/day; a third of that for the part still cheap at the match |

The corrected rows still use tape fills (somebody else's print, taken ahead of them), so they are ceilings.

## 1. Look-ahead

Nothing found.

- Binance dumps: column 0 is the open time on whole seconds, close time minus open time is 0.999999 s in every row,
  604,800 rows for 20-26 Nov, no gap, no duplicate. `px.price(t)` is the close of the second that opens at t, known
  at t + 1. The rule calls the model at t = m - D - 1, so its last input closes at m - D. My own model is built only
  from closes with open time <= t (K, the 900 s volatility, the running average) and gives the identical trade list
  (449 and 744 rows, same tape rows, sizes equal, net difference $0.0000). So f, K, sigma and the expected average
  contain no later price.
- Volatility: `px.sigma(t)` sums the 900 squared returns that end at the close of second t. No future data.
- Match time: m = block time - 3. The analyst's WebSocket check (I read `ws_timing.py`: one-to-one matching on
  token, side, size and price; I did not re-measure it) gives a lag of 1.06-3.33 s, so the real match is between
  m - 0.3 and m + 1.9. At D = 1 the model's last input is 0.7-2.9 s older than the match.
- The official outcome and final price enter only the payoff and E99. E99 is the all-window value, as the protocol
  says; it is in-sample. Sensitivity (floor 0.97, D = 1, six days): threshold 20.46 (tuning only) 55 markets
  +5.54 c, 25: 43 markets +5.12 c, 30: 33 markets +5.00 c, all without a loss; 15: 72 markets, 1 lost, +4.21 c
  (t 2.5); 10: 86 markets, 2 lost, +3.02 c (t 1.3). The four unfiltered losers sit at $5.7, $8.8, $11.8 and $15.0
  from the strike. E99 = 18.63 was not tuned, but it is just above the largest of them, and three of the four are
  basis misses, which a band made from the same windows removes by construction.
- The problem is the opposite of look-ahead: the model is older than the print. See 2.

Delay scan (six days, filter on, model uses Binance closed by m - D; negative D is deliberate look-ahead):

| D | floor 0.99: markets, c/sh, markets with a losing fill | floor 0.97: markets, c/sh, markets with a losing fill |
|---|---|---|
| -3 (look-ahead) | 58, +6.03, 0 | 105, +6.79, 0 |
| -2 (look-ahead) | 41, +4.66, 0 | 69, +6.20, 0 |
| -1 (about the match) | 30, +5.05, 0 | 52, +5.61, 1 |
| 0 | 26, +5.12, 0 | 54, +5.29, 1 |
| 1 (study) | 39, +5.00, 0 | 59, +5.44, 0 |
| 2 | 34, +4.78, 0 | 58, +4.71, 1 |
| 3 | 37, +4.94, 1 | 65, +3.79, 2 |
| 5 | 34, +2.10, 2 | 63, +4.05, 4 |
| 8 | 30, -0.20, 3 | 64, +1.54, 6 |
| 12 | 27, -1.50, 4 | 55, +1.13, 6 |

Two readings. First, real look-ahead of 2-3 s would have doubled the number of markets, and the study's count is
not inflated that way. Second, the count of "cheap" prints barely changes from D = 0 to D = 8: the prints are not
tied to the second in which the model crosses its floor, which is not what a stale-quote race looks like.

## 2. Fills

- Caps and single use hold. In the analyst's trade file the largest total per (variant, market) is 500.000 shares,
  the largest fill 100, no fill exceeds its print, no tape row is used twice inside a variant, smallest print 5.
- Exact duplicate tape rows (93,551 of 2,653,763; 30 of the 449 and 49 of the 744 traded rows) are real repeated
  fills: tape share totals equal gamma `volumeNum` in 1,572 of 1,575 markets with the duplicates kept.
- 97% / 94% of the traded shares come from taker BUY rows, 3% / 6% from taker SELL rows of the other side. 3 of 19
  and 7 of 49 of those SELL-derived prints have a BUY row with the same block, size and price next to them, which
  may be one match seen twice. Under 1% of the shares.
- One block: 28 of 39 / 35 of 59 markets have all their fills in a single block, and 75% / 67% of the shares sit
  in the first qualifying block. Using only prints in a later block leaves 11 markets and $31/day (floor 0.99) or
  24 markets and $56/day (floor 0.97); prints 3 s or more after the first block leave 4 markets and $13/day or
  14 markets and $24/day.
- The bursts are dips, not jumps. Size-weighted price of the favoured side, median over markets: 0.976 in the 6 s
  before the first qualifying block, 0.965-0.970 in that block, 0.969-0.973 in the next 1-4 s, 0.982-0.985 after
  5-10 s. Median price paid by the rule 0.951-0.965. In the same block 41-54% of the favoured side's volume printed
  at 0.98 or higher, so the rule keeps the cheap half of a noisy two-second block.
- Two clocks (stale = Binance closed by m - 1, the study's D = 1; fresh = closed by m + 1, about the real match):

  | prints that are 2 c under the model on... | floor 0.99 | floor 0.97 | move of the expected average toward the favourite between the clocks, p10 / p50 / p90 |
  |---|---|---|---|
  | both clocks | 15 mkts, 3,515 sh, +3.94 c, $139 | 27 mkts, 6,283 sh, +4.34 c, $273 | -$3 / $0 / +$1 |
  | the stale clock only (in the study's result) | 26 mkts, 6,070 sh, +5.62 c, $341 | 44 mkts, 9,919 sh, +6.16 c, $611 | -$21..-27 / -$11..-14 / -$5..-6 |
  | the fresh clock only (not in the study's result) | 26 mkts, 6,638 sh, +5.60 c, $372 | 44 mkts, 11,365 sh, +6.18 c, $702, 1 losing market | $0 / +$10..12 / +$32 |

  The stale-only prints were not cheap by the fresh model: probability of the bought side 0.927-0.936 against a
  price of 0.935-0.941, expected value -0.7 to -1.1 c/share after the fee. They all won (44 markets); at a fair
  0.93 that happens 4% of the time, so either luck or the model understates the leader there (NOTES records 2-4 c of
  that bias at 0.65-0.90). A system with a live Binance feed would not have sent those orders: its model would
  already be below the floor. The analyst's WebSocket check on 14-20 markets said the same thing (36% / 46% of
  shares still valid at the match); on the full sample it is 37% / 41% of shares and 29% / 33% of the dollars.
  The fresh-only row is the classic race after a favourable Binance move; it needs a reaction inside a second and
  contains the one losing market.
- The pie. Every print that met the rule, without the 100/500 caps and the 5-share minimum: 20,678 shares and $914
  in six days for floor 0.99 (315 wallets), 35,114 shares and $1,734 for floor 0.97 (447 wallets; $374/day in
  tuning, $120/day in the reporting period). The rule's assumed take is 46% / 44% of the shares and 52% / 48% of
  the dollars. Median print 10 shares; median wallet $0.60-0.71 in six days; richest wallets $152, $124, $123, $65,
  $50; the five most frequent wallets (30, 22, 14, 12, 11 markets) $19, $20, $6, $41, $25. Restricted to prints
  cheap on both clocks the pie is $151/day ($53/day in the reporting period, 260 wallets). Nobody harvests these
  prints systematically; the rule's dollars are what a single trader would get by standing in front of all of them.
- Order inside a block is the API's order, not time order, so in the 8-10 markets that hit the 500-share cap the
  choice of prints is arbitrary. Small.

## 3. Fees and accounting

- `fee_rate` 0.05 and `fee_type` crypto_btc_5m_15m_fees on all 1,728 metadata files; every window starts after the
  2026-11-20 23:59 UTC change. I did not check a wallet's real charges for these days (NOTES has two independent
  0.05 calibrations after the change).
- Hand recomputation of six fills from the raw tape row, for example: t0 1795554000, block t1 - 22, raw
  `BUY Down p=0.9600 z=301.5` -> 100 shares of Down at 0.96, Down won, fee 0.05 x 0.96 x 0.04 = 0.00192, net
  100 x (1 - 0.96 - 0.00192) = $3.808; t0 1795293300, raw `BUY Up p=0.9727 z=205.306` -> 100 shares, Up won, fee
  0.00133, net $2.5934. All six match.
- Settlement direction: `up_won` equals (final >= price_to_beat) in 1,727 of 1,727 markets with both prices; no
  tie (smallest gap $0.013); Up won 49.9%.
- Dollars per day divide by 4 and 2 calendar days. Correct.

## 4. Statistics

- Clustering by market is done as stated; my own ratio estimator returns the same t values. With zero losses those
  t values describe the spread of discounts, not the risk (the analyst says so).
- Reporting period and tuning: the judged variant is ranked on tuning rows only (checked in `analyze.py`). E99 uses
  all windows, as the protocol orders. The headline's "59 markets, +5 c" pools both periods and promotes the widest
  variant, which was not the pre-chosen one. The pre-chosen variant's reporting result is 5 markets and $30/day, of
  which 3 markets and $18/day are still cheap at the match.
- Variants: 42 trading runs by the analyst (35 with trades in the trade file, 7 empty), plus diagnostics. Mine: 62
  diagnostic runs of the rule engine (delay scan, lag 2, E99 scan, two-clock split), none used to pick anything.
- Concentration (D = 1, filter on):

  | | floor 0.99 | floor 0.97 |
  |---|---|---|
  | markets per day, 21..26 Nov | 13, 8, 6, 7, 3, 2 | 19, 13, 6, 11, 6, 4 |
  | without the best day (21 Nov) | 26 mkts, +4.80 c, $67/day | 40 mkts, +5.52 c, $125/day |
  | without the ten best markets | 29 mkts, +3.43 c, $32/day | 49 mkts, +4.48 c, $81/day |
  | share of dollars in the ten best markets | 60% | 42% |
  | one loss at the cap ($474) against six-day net | $480 | $833 |

  No single day or handful of markets carries the per-share number, because nothing lost. The absence of one loss
  carries it: one capped loss is the whole six-day profit of the judged variant.
- Base rate behind the rule (leader side by the D = 1 clock, distance >= E99, every buyable print, no caps):

  | price | six days: markets (with a losing print), win, net c/sh (t) | tune | report |
  |---|---|---|---|
  | 0.50-0.90 | 240 (35), 85.3%, +3.77 (1.0) | +4.79 (1.0) | +1.27 (0.3) |
  | 0.90-0.95 | 330 (16), 96.5%, +3.43 (2.9) | +4.54 (4.5) | +0.79 (0.2) |
  | 0.95-0.97 | 408 (10), 97.9%, +1.73 (2.2) | +1.88 (2.1) | +1.34 (0.9) |
  | 0.97-0.98 | 417 (7), 98.4%, +0.94 (1.1) | +1.66 (2.3) | -0.83 (-0.4) |
  | 0.98-0.99 | 485 (5), 98.7%, +0.27 (0.4) | +1.20 (4.2) | -2.22 (-0.9) |
  | 0.99-1.00 | 623 (4), 99.4%, +0.29 (0.9) | +0.56 (2.0) | -0.60 (-0.6) |
  | all | 731 (36), 97.8%, +0.96 (1.8) | +1.45 (2.9) | -0.47 (-0.3) |

  The basis band alone does not make the favourite safe with 40-60 s left (36 markets with a losing print), and the
  small general underpricing of 21-24 Nov is absent on 25-26 Nov. The rule's zero-loss set is the slice of this
  population where a 1-2 s old model is above its floor.

## 5. Data

- 1,728 of 1,728 metadata files and tapes, 1,728 distinct conditions, slug/asset/duration consistent, all closed and
  resolved, tapes sorted, only BUY/SELL and Up/Down values, 2,653,763 rows.
- Completeness: tape shares equal gamma volume in 1,572 of 1,575 markets that carry one (the other three have a
  gamma volume of 2-46, as reported). 153 markets have no gamma volume and cannot be checked that way; their row
  counts and share totals look like the rest. Of the 59 traded markets 53 can be checked and 52 match. The three
  tapes with exactly 1,000 rows match gamma to the share, so they are not cut pages. 148 tapes stop more than 10 s
  before the end; those are decided markets (median distance $109 against $54) and all 135 of them with a gamma
  volume match it.
- Binance: seven full days, no gaps. `common.DAYS` lists 2026-11-27, for which there is no dump in the store, so
  every `load_px()` fetches that partial day from the mirror. It affects one number (the end average of the last
  window; my basis has n = 1,726 instead of 1,727 with the same sd 5.64, p99 18.63, max 61.37, 33 misses).
- Time zone and split: START = 1795219200 is 2026-11-21 00:00 UTC, SPLIT = START + 4 days. Symbol BTCUSDT.

## 6. Independent reproduction (100% of the sample)

| | study | mine |
|---|---|---|
| descriptive 0.90-1.00, all / tune / report | +0.91 (t 2.6) / +1.35 (6.2) / -0.09 (-0.1) | identical; all five buckets identical |
| basis sd, p50, p95, p99, max, misses | 5.64, 2.92, 10.96, 18.63, 61.4, 33 | 5.64, 2.92, 10.96, 18.63, 61.37, 33 |
| judged, tune | 387 / 34 / 7,922 / 0.944 / +5.30 c / t 7.8 / $105 | identical |
| judged, report | 62 / 5 / 1,664 / 0.962 / +3.58 c / t 8.3 / $30 | identical |
| widest, tune and report | 626 / 49 / +5.23 c / $163 and 118 / 10 / +6.43 c / $90 | identical |
| widest, filter off | +3.05 c (t 1.1) $177 and -4.19 c (t -0.5) -$155 | identical |
| three D = 2 runs, L = 30 and L = 15 runs | as in T3 / T4 | identical |

## Problems

| # | problem | severity | effect on the numbers |
|---|---|---|---|
| 1 | Fill assumption takes 44-52% of all volume that printed at rule prices (59-75% of the dollars in the reporting period) | high | $80-139/day pooled is half of a $152-289/day pie shared by 315-447 wallets; best real wallet $25/day, most systematic $3/day |
| 2 | 59-63% of the traded shares (67-71% of the dollars) are prints where the Binance signal had already reversed by the match: stale model against a current price | high | +5.00 / +5.44 c on 39 / 59 markets becomes +3.94 / +4.34 c on 15 / 27 markets; $80 / $139 a day becomes $23 / $45; reporting period 3 / 5 markets |
| 3 | Zero losses depend on the exact alignment (block - 3 s, D = 1) | medium | floor 0.97: 1 net-losing market of 52-62 at D = -1, 0, 2 and at lag 2; 2 of 65 at D = 3. Per-share net stays +4.7..+5.6 c only because the losing prints were 42-150 shares |
| 4 | Sample: 0 losses in 15-27 robust markets, 3-5 in the reporting period | medium | 95% upper bound on the loss rate 10.5-18.1% against a break-even of 3.9-4.4%; the t values of 3.6-13 carry no information about that |
| 5 | The general leader underpricing outside the basis band is absent on 25-26 Nov | medium | +1.45 c (t 2.9) in tuning, -0.47 c (t -0.3) in reporting; the filtered rule is a small slice of a population with no stable sign |
| 6 | E99 comes from the same windows and three of four unfiltered losers are basis misses | low | none in-sample (thresholds 20.46-30 give the same picture); the filter's protection is partly by construction and one window had a $61 error |
| 7 | Headline pools both periods and features the post-hoc widest variant | low | pre-chosen variant, reporting period: 5 markets, $30/day (3 markets, $18/day still cheap at the match) |
| 8 | The NOTES.md line and the headline call the fills "bursts after a Binance move" | low | for about two thirds of the volume the move was against the favourite; wording, no number |
| 9 | `load_px()` depends on a live mirror call for 27 Nov; tape order inside a block is not chronological; results.md quotes a 50 ms taker delay (NOTES: 150 ms since 4 Sep) | low | one basis observation; arbitrary print choice in the 8-10 capped markets; none |

## Not checked

- Whether the asks existed before the prints and for how long (needs the L2 book of 21-22 Nov; not downloaded).
- The WebSocket lag measurement itself (read the script, did not re-run it).
- Real fee charges of a wallet in these markets on these days.
- Anything beyond these six days.
