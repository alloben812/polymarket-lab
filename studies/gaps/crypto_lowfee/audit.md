# Audit: thin, low-fee crypto up/down series against exchange prices

Auditor's pass, 2026-11-27. Study files: `protocol.md`, `results.md`, `analyze.py`, `build.py`, `extra.py`.
My scripts: `audit/a1..a8_*.py`, their output: `audit/logs/`. Nothing of the analyst's was edited; `pmlab/` and
`NOTES.md` were not edited.

## Verdict: HOLDS

The headline is a negative one and it survives. Every number I checked reproduces from the raw files with code
that shares nothing with the analyst's (own tape reader, own Binance reader, own fair-value formula, own cap and
clustering code): all 4,330 markets, all 1,512,241 tape rows, all 180 rule rows (90 variants x 2 periods). I found
no look-ahead, no fee or settlement error, no reused liquidity, no missing or truncated data. The one real defect,
a change of the on-chain timestamp delay inside the sample, does not move the verdict: with the timing re-aligned
there is still no variant that is positive with t above 2 in the reporting period. Three extra tests that go at
the lag question more directly than the protocol did agree with the analyst.

What the study does not show, and should not be read as showing: (a) anything about quotes that nobody hit (the
analyst says so); (b) that an edge of 1-2 cents a share in sol/xrp is absent (two reporting days cannot tell);
(c) that the lock-in idea fails (M5 tests a model with a known 4-5 s misalignment, on 1-20 markets).

## What was reproduced (100% of the sample, independent code)

| item | analyst | audit |
|---|---|---|
| universe | 4,330 markets, 1,512,241 rows, none missing | same; every market closed, slug and end time consistent, 4,330 distinct conditions |
| fair value grid | - | max abs difference to the analyst's grid 2e-16 over all 2.7M market-seconds |
| M1 | $/day, median $/market, wallets, top-5 share, seconds with a fill | identical in all six series |
| M2 by series and period (18 rows) | e.g. eth-5m -0.551 c/sh, t -3.82 | identical to the third decimal |
| M2 by time, price, side (84 cells) | none positive with t > 2 | identical; largest t is +1.45 (eth-5m pre-window) |
| M3 peak lag all / tune / report and by day | 2/2/1 ... | identical lags and correlations in all six series |
| proxy check | sd 0.99-1.27 bp, wrong 0.9-1.9% | identical (15m series on 575 of 576 windows: I did not load the 27 Nov seconds) |
| M4 + M5, 180 rows | - | trades equal in 180 of 180 rows; max difference 0.005 c/sh, 0.005 in t, $0.05/day (rounding) |
| selection | 10 selected variants | same variants follow from the tuning-period t |
| variants positive in reporting, t > 2, >= 100 markets | 0 of 90 | 0 of 90 |

## The audit, in the order asked

### 1. Look-ahead: none found

- `Px.price(s)` is the close of the 1 s kline opening at s (time s + 1). The analyst handled this: the fair value
  for "data up to x" is `G(x - 1)`. Checked in `build.py` (`look(mt - d - 1)`) and by a hand computation of one
  trade from the raw zip (`logs/a6_quiet.txt`): same f, same edge, same PnL.
- Strike = Binance mean of the 60 klines ending with the one that opens at t0; the earliest fair value used is
  G(t0), information time t0 + 1. Volatility is trailing 900 s. The settlement branch of `fair_up` (t >= t1, which
  returns the outcome) is never reached: G is computed for s <= t1 - 1 and M4/M5 stop at t1 - 5 / t1 - 2.
- The official outcome, `final_price` and `price_to_beat` enter only the PnL and the proxy table.
- Match time = block time - 3. Against the lab's millisecond measurement (block lag 1.06-3.33 s, median 2.09 s,
  21-22 Nov) the D=0 variants see Binance data later than the match only for fills whose block lag exceeded 3 s
  (a few percent, by at most 0.3 s). Immaterial.
- How much look-ahead would be worth, as a calibration: moving the assumed match to block time - 1 in the tuning
  period (about 1.4 s after the moment the tape price was set) turns D0_thr0.02 into +2.37 c/sh (t 4.0) in eth 5m
  and +3.05 (t 3.5) in btc 15m. In sol and xrp the same foresight gives -1.14 (t -0.9) and +0.61 (t 0.4). Two
  readings: the analyst's alignment is not leaking (their D=0 numbers are nowhere near these), and in the thin
  series even a second and a half of foresight does not help, which is itself evidence against a multi-second lag.

### 2. Fills

- One print is used at most once per variant; the cap is applied in tape order per (market, side): my own
  implementation gives the same trade counts in all 180 rows.
- A taker SELL of X at p is used as "the other side was buyable at 1 - p". Correct for a mirrored book; fee
  p(1-p) is the same in both forms.
- Tape rows are per taker order at the VWAP, so "min(print, 50) shares at the print price" is not better than
  what the first shares of that order got.
- Exact duplicate rows are 1.4-5.2% of the tapes. They are in gamma's volume as well (tape shares / gamma volume:
  median 1.0000, no market below 0.98, 2 eth-5m markets above 1.02), so they are real fills, not paging repeats.
- Optimism that remains (admitted by the analyst): the fill is liquidity a real taker took, so we would have had
  to be ahead of that taker; 9-17% of the trades of the selected M4 variants come from prints below the 5-share
  minimum order (the hand-checked trade is a 0.43-share print). For a negative result this cuts the safe way.
- The sizing shapes the numbers: at full print size instead of 50/300 the reporting-period result of the selected
  variants is eth-5m -1.99 c/sh (t -2.0), eth-15m +2.02 (t 0.9), sol-15m +5.06 (t 1.6), xrp-15m -7.54 (t -3.7),
  btc-15m +3.52 (t 0.9). Nothing significant on the plus side either way.

### 3. Fees and accounting

- 18 fills recomputed by hand (three per series, `logs/a2_checks.txt`) and one M4 trade end to end: correct.
- Settlement: `up_won` equals `final_price >= price_to_beat` in 4,330 of 4,330 markets; there is no tie in the
  sample, so the >= rule was never exercised.
- Fee rate against real charges (activity `usdc_size` minus size x price, 40 fills drawn at random over the six
  days, `a7_fee_check.py`): sol 10 of 10, eth-15m 6 of 6, eth-5m 6 of 6 at 0.0100; btc-15m 4 of 4 at 0.0500; xrp
  13 of 14 at 0.0100 and one at 0.0192. A second xrp fill seen in a trial call was charged 0.0180. I cannot explain
  the two xrp outliers (both are multi-level orders, but so are others that were charged 0.0100). Effect if it were
  general: under 0.2 c/sh; it is not general.
- Rows before the fee change of 20 Nov 23:59 UTC (pre-window trades of the first markets): 38 rows in total,
  0.00% of dollars.

### 4. Statistics

- Clustering by market is adequate here: lag-1 autocorrelation of per-market PnL of the selected M4 variants is
  -0.05..+0.03, and t by 1-hour or 3-hour blocks is the same as by market (xrp-15m -2.9 / -3.6 against -3.1).
- Series are not independent tests: per-window PnL of the selected M4 variants correlates 0.03-0.33 across the
  four 15m series. The analyst does not add series up, so nothing depends on it.
- Reporting period untouched by tuning: the protocol file predates the first download (15:44:43 against 15:45:10);
  the slice seen before the full run is 21 Nov only; selection is mechanical. (The btc 5m tapes and the BTC Binance
  files were already on disk from earlier studies; they feed the reference series only.) `analyze.py` carries a modification
  time five minutes after its outputs (16:25 against 16:20) and there is no earlier version in git, so I cannot see
  what changed; since an independent rebuild from the protocol text reproduces every output, it did not change a
  number.
- Variants: 90, all reported. Correct.
- Does a day or a handful of markets carry the result? For the two selected variants that are positive in
  reporting, yes, and they vanish:

| selected M4, reporting | as reported | without the 10 best markets | without the 10 worst | by day |
|---|---|---|---|---|
| eth-15m D0_thr0.01 | +0.59 c/sh (t 0.6), +$266/day | -0.76 (t -0.8), -$323/day | +1.86 (t 2.2) | 25 Nov +$1,327, 26 Nov -$795 |
| sol-15m D0_thr0.02 | +2.29 (t 1.3), +$666/day | -1.30 (t -0.9), -$349/day | +3.84 (t 2.3) | 25 Nov +$1,306, 26 Nov +$26 |
| eth-5m D0_thr0.02 | -0.82 (t -1.3) | -1.56 (t -2.5) | -0.26 (t -0.4) | -$1,077, -$897 |
| xrp-15m D2_thr0.01 | -5.47 (t -3.1) | -9.37 (t -6.4) | -2.54 (t -1.6) | -$775, -$1,184 |
| btc-15m D0_thr0.04 | -2.31 (t -1.6) | -4.78 (t -3.5) | -0.37 (t -0.3) | -$54, -$1,571 |

  Ten markets out of 190 move each 15m result by 1.3-3.9 c/sh. That is the size of the noise, in both directions.

### 5. Data

- Nothing missing: 6 x the grid, all found, all closed, all resolved, tapes sorted, no price outside (0, 1), no
  zero size, no tape truncated at a page size (four files have a row count divisible by 500 and their share
  totals match gamma). Binance: 604,800 of 604,800 seconds present for each symbol, every kline exactly one second,
  timestamps in microseconds read correctly, no duplicates.
- Symbols and windows: slug `<asset>-updown-<dur>-<t0>` and `t1 = t0 + dur` hold for every market; median Binance
  premium over the official price is 13.5-13.7 bp in all four assets (wrong symbol or wrong hour would show here).
- Timestamps, the one real finding. The delay between Binance and the tape is not constant inside the sample.
  Centre of mass of the M3 correlation over lags 0-4 s, four liquid series, 4-hour blocks (`logs/a8_lag_when.txt`):
  2.1-2.6 s in every block up to 24 Nov 20:00 UTC, 1.1-1.7 s in every block after. It is a step, not a drift, and
  it is on Polymarket's side: the shift of the Binance 60 s average that best matches the official Chainlink
  values is 3.3-5.5 s on every day and asset with no step on the 24th/25th (eth 4.6 -> 4.0 s, sol 5.0 -> 5.1,
  xrp 4.3 -> 3.7, btc 4.5 -> 4.3), so the Binance files did not move. The analyst noticed the change (their
  caveat 3) and guessed the cause correctly; they did not re-run anything with it.

### 6. Independent reproduction

See the table at the top: the whole sample, not a quarter.

## Problems

| # | problem | severity | effect on the numbers |
|---|---|---|---|
| 1 | The on-chain timestamp delay fell by about 1 s at 24 Nov ~20:00 UTC, four hours before the tune/report boundary. With match = block - 3 the rules saw Binance data about 0.5 s older than the tape price in tuning and about 1.5 s older in reporting. Tuning and reporting are therefore not like-for-like for anything timing-sensitive (D, the M5 window, the M2 time buckets). | medium | Verdict unchanged. Reporting period re-run at block - 2 (like-for-like with tuning) and block - 1 (no margin): 0 of 90 variants positive with t > 2 on >= 100 markets in both. Selected M4, block - 3 / - 2 / - 1: eth-5m -0.82 / -0.99 / -0.09 c/sh; eth-15m +0.59 / +0.59 / +0.82; sol-15m +2.29 / +2.26 / +3.02 (t 1.8); xrp-15m -5.47 / -4.38 / -4.11; btc-15m -2.31 / -2.05 / -1.05. M5 eth-5m mrg0.08: -24.4 (t -2.0, 10 markets) / -15.0 (t -1.3, 12) / -4.1 (t -0.4, 13). |
| 2 | "M5 loses out of sample, the tape is right and the model is wrong" is overstated. Part of the reporting-period loss is problem 1 (the model was a second staler than in tuning), and the model's last-minute branch averages the wrong 60 seconds: the official average trails Binance by 4-5 s in all four assets (proxy drift sd falls from 0.7-1.7 bp to 0.3-1.1 bp at the best shift; known in NOTES from the BTC lock-in study, not applied here). | medium for the M5 reading, none for the headline | M5 eth-5m reporting is -4 to -15 c/sh on 12-13 markets with aligned timing, not -20 to -38; not distinguishable from zero. M5 as run says nothing about a correctly specified lock-in rule. Still not positive anywhere with more than 20 markets. |
| 3 | "NO EDGE" is stronger than the data for sol-15m and xrp-15m, and by the protocol's own wording (B9: no edge "if clearly negative or zero", otherwise inconclusive) sol-15m and eth-15m M4 are "inconclusive": all 24 of their variants are positive in reporting at 0.4-1.8 standard errors. | medium (label, not numbers) | 95% interval of the selected variant: sol-15m reporting +2.3 +/- 3.3 c/sh, pooled -0.1 +/- 2.0; xrp-15m pooled -0.9 +/- 2.0; eth-15m pooled 0.0 +/- 1.3. The plus in sol and eth 15m is one day and ten markets (table in section 4). Read the verdict as "no edge shown; an edge under about 2 c/sh in sol/xrp is not excluded". The analyst's caveat 4 says the same. |
| 4 | M4 is a weak instrument for the question. 71-95% of the shares it buys are underdogs (average price 0.25-0.41) because the model is under-confident, so its PnL is "did underdogs come in on those days" (sol yes, xrp no on 25-26 Nov; xrp's t of -3.1 to -3.8 is as "significant" as anything in the study and means nothing). Only the dependence on D speaks to lag. | low-medium | The second clause of the headline ("none of 90 positive") is true but carries little information about lag. The first clause had to be supported separately; see the extra tests below, which do support it. |
| 5 | Peak lag is the least sensitive statistic the M3 curve offers: sol and xrp have the same peak but a mean lag of 6-7 s against 2-2.6 s. The analyst's explanation (sparse trading) was asserted; M3b, offered as the test, barely discriminates (RMS 0.087 at the best lag, 0.088 at lag 0, 0.091 at lag 3). | low after my tests | Three direct tests back the analyst's reading (next section). |
| 6 | Headline wording: without the ">= 100 markets" qualifier two M5 variants are positive with t > 2 in reporting, on two markets each (eth-15m mrg0.03: t 24.7, 7 trades, $2/day; btc-15m mrg0.03_2bp: t 36.8, 24 trades, $11/day). | low | None; keep the qualifier in the one-line summary. |
| 7 | Two of 15 sampled xrp fills were charged 1.8-1.9 times the 0.01 formula; unexplained. | low | Under 0.2 c/sh on such fills; 39 of 40 fills in the scripted sample are exact. |
| 8 | `analyze.py` was modified after its outputs were written; no history. | low | None: outputs reproduce from the protocol text with independent code. |

## Extra tests of the lag claim (mine, exploratory, not in the protocol)

Run because problems 4 and 5 leave the first clause of the headline resting on one insensitive statistic.

1. Staleness regression at trade seconds (`a3_lag.py`): trade price minus the fair value 3 s before the block,
   regressed on the change of the fair value over the 10 s before that. Stale trade prices give a negative slope.
   Slopes (tune / report): eth-5m +0.06 / +0.05, eth-15m +0.03 / +0.05, sol-15m +0.09 / +0.13, xrp-15m +0.08 / +0.11,
   btc-15m +0.04 / +0.04, btc-5m +0.06 / +0.04, standard errors 0.01-0.04. Prices at which sol and xrp trade are not
   behind the last ten seconds of Binance; if anything they have moved further than the model.
2. Takers who arrive after silence (`a6_quiet.py`): real fills that come at least 15 s after the previous print in
   that market and buy the side whose fair value rose 3 cents or more in the last 10 s. If quotes sat stale while
   nobody traded, these are the people who picked them off. They lose: sol-15m -2.12 c/sh after fees (t -1.7,
   2,450 fills in 559 markets), xrp-15m -3.14 (t -1.8, 2,372 fills in 541 markets), eth-15m -1.55 (t -0.7). This is
   the nearest the tape gets to the quotes nobody hit, and it shows nothing to take.
3. A rule that buys in the direction of a Binance-driven jump (fair value of the bought side up 0.03 or 0.06 over
   3 or 10 s; 50/300 sizing; `a4_rules.py`): in sol and xrp all 16 tuning cells are negative (-0.1 to -2.2 c/sh)
   and the reporting cells run from -3.8 to +2.9 with no t above 1.4. With half a second of foresight (block - 2
   in tuning) the liquid series do respond (eth-5m +1.32, t 2.7; btc-15m +1.75, t 2.4; btc-5m +1.82, t 2.4): the
   sub-second race the analyst describes. Sol and xrp do not respond even then.

Count of what I ran: the protocol's 90 variants re-evaluated at two other timestamp alignments (180 evaluations),
the jump rule in 4 variants x 6 series x 2 alignments (48), and the descriptive tables above. None is positive with
t above 2 in the reporting period; none is proposed as a strategy.

## What remains open

- Quotes between trades in sol/xrp (94-96% of seconds). Test 2 above narrows it but is still the tape. The L2
  archive is the only way to close it.
- An edge below about 2 c/sh in sol/xrp: needs more days, not more variants.
- The lock-in idea with the official average shifted 4-5 s and the official strike: not tested here.

## Facts for NOTES.md (not added by me)

- Up/down tapes: the gap between a Binance move and the on-chain timestamp of the trades that reflect it was
  2.1-2.6 s until 24 Nov ~20:00 UTC and 1.1-1.7 s after (six series, 4-hour blocks). Binance files are not the
  cause (the Chainlink-matching shift is stable). `updown.BLOCK_LAG = 3` is about 0.9 s early before the step and
  about 2 s early after it; block - 1 on data from before the step is look-ahead worth +1 to +3 c/sh in M4-type
  rules on eth 5m and btc 15m.
- The official 60 s average trails Binance by 4-5 s in ETH, SOL and XRP as well as BTC.
- Real charges confirm 0.0100 on eth/sol/xrp up/down and 0.0500 on btc 15m (activity `usdc_size`), with two
  unexplained xrp fills at about 0.018-0.019.
- In sol/xrp 15m, takers who trade with a Binance move after 15 s of silence lose 2-3 c/sh: no stale-quote
  pick-off is visible on the tape.
