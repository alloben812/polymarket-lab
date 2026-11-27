# BTC 5-minute markets: does buying the abandoned side for about one cent pay? — results

Study run 2026-11-27 (second researcher; the first one wrote `protocol.md` and the scripts and was stopped after
about a quarter of the download). Protocol: `protocol.md`, executed as written. Code: `fetch.py` (+ `fetch_par.py`,
a parallel driver of the same download), `fetch_px.py`, `fetch_v7.py` (+ `fetch_v7_par.py`, a parallel cache warmer),
`build.py`, `sanity.py`, `t1_t4.py`, `t2.py`, `t3.py` (protocol runs), `capacity.py`, `t3_extra.py` (post-hoc,
descriptive, marked as such below). Raw outputs: `out/full/` (`t1_t4.md`, `t2.md`, `t3.md`, `capacity.md`,
`t3_extra.md`, `sanity.txt`, CSVs). Large tables (prints, tickets, units) are in `data/gaps_btc5m_tails/`.

## Question

An account named Vega7 (0x6ba25c9f…) is advertised as making 10-14K dollars a month by buying the abandoned side of
Bitcoin 5-minute up/down markets at about one cent, 10-25 dollars a ticket, mostly 15-75 seconds before the window
ends. Is that side really underpriced in some part of the window, so that a small trader could buy it by rule, or is
Vega7 one lucky or selective wallet among the many that lose on the same tickets?

## Verdict: NO EDGE for the published rule; Vega7 is selective, not lucky

- **The published rule loses.** Buying every buyable print at <= 0.02 (variant A, primary) or <= 0.05 (variant B)
  in seconds 225-285, up to $25 of stake per market, after the taker fee:
  - reporting month (November 1-26): A **-46.4% of stake** (95% CI -82% to -11%, t -2.57, 1,808 markets traded,
    17 of them won), net -$13,325 on $28,734 (bootstrap 95% of net -$22,800 to -$2,377); B -40.1% (CI -66% to -14%,
    t -3.00, 1,838 markets, 37 won), net -$12,822;
  - earlier months (September-October pooled): A -31.9% (CI -61% to -3%, t -2.17, 4,210 markets), B -22.0%
    (CI -43% to -2%, t -2.10, 4,288 markets);
  - whole period: A -36.4% (CI -59% to -14%, t -3.13, 6,018 markets, 61 won), B -27.3% (CI -44% to -11%, t -3.25,
    6,126 markets, 150 won). Every month is negative for both variants.
  - Protocol rule 2.4: November return on stake <= 0 for both variants (and pooled <= 0 for both) -> **NO EDGE**.
- **The one-cent side is overpriced, not underpriced.** In all six seconds-left bands, tails priced at or under
  1.5 c won less often than their break-even price: in seconds 225-285 (75-45 and 45-15 s left) 15 of 4,372 and 17
  of 5,673 markets won against 0.92% and 0.86% needed (exact binomial p < 0.001 in both); in the last 15 s 2 of
  4,930. The favourite side priced >= 0.985 in the same cells is roughly fair (-0.14 to +0.52 c a share). No tail
  cell is positive after the correction for 42 cells.
- **Vega7 is real but selective.** In the same period, after fees at our rates, Vega7 kept **+$34,047 on $31,139 of
  stake** (+1.72 c a share, t 4.4 by market, 3,636 markets; Sep +$13,279, Oct +$10,536, Nov +$10,232), which matches
  the advertised figure. Its tickets do not win because tails are cheap; they win because it picks different
  markets: in the cell "price <= 0.05, seconds 225-285" its markets won 3.74% (61 of 1,630) against 2.45% (153 of
  6,233) for all markets with a print there (z +2.8); in the cell "<= 1.5 c, 75-45 s left" 3.80% (20 of 526)
  against 0.34% (15 of 4,372) (z +8.9). Against its own break-even the pooled cell has exact p 2.6e-7, so luck
  is very unlikely even after allowing for a promoter picking it out of thousands of wallets.
- **What separates its picks (hypothesis only, nothing fitted).** Vega7 buys a tail when Bitcoin on Binance has
  just moved toward that tail (last 30 s: +0.55 bp vs -0.85 bp for all prints; standardised difference +0.46,
  rank-sum z +17.5) and when the tail is closer to winning in model terms (2.96 vs 3.81 model standard deviations,
  -0.41, z -16.3), with lower recent volatility (-0.25). Hour of day does not separate. This looks like a speed and
  model trade on stale tail offers right after a Binance move, not a structural mispricing of the tail.
- **For a 200 EUR account: $0 a day.** The rule as published would have lost about $1,570 a day at $25 a market
  across all windows (Nov: about $2,050 a day): it is not something to paper-trade. Copying Vega7 is not possible
  from public data (its fills are visible only after the block, when the price is gone).

## Data

- Windows: every 4th BTC 5m window (`t0 % 1200 == 0`) from 2026-09-01 00:00 to 2026-11-26 23:40 UTC: 6,264
  windows, **all downloaded** (the protocol's fallback to a sub-grid was not needed). 7 had no market, 13 an empty
  tape; **6,244 used** (Sep 2,147, Oct 2,231, Nov 1,866).
- Sources: official outcome, price to beat and gamma volume from `pmlab.updown.load_market` (gamma events, read
  2026-11-27); whole-market tapes from the Data API v2 (`trades?condition=`, read 2026-11-27): 9,569,388 buyable
  prints, of which 539,413 before the window opens (excluded, counted). Binance BTCUSDT 1-second closes,
  `data.binance.vision` daily dumps 2026-08-31..11-26, no gaps. Vega7's fills from `pmlab.wallet.fetch_fills`
  (3,693 BTC 5m BUY fills, all taker, in 3,636 windows, 901 of them on the grid) and official metadata for all of its
  windows (0 missing).
- Completeness: tape shares / gamma volume median 1.0000, p1 1.0000, p99 1.0011 over 5,806 markets (gamma volume
  missing on 451), so the 90% filter was applied as the protocol says; it excluded 0 markets. All 907 of Vega7's fills
  in used grid markets are in the tapes (same block time, outcome, price, size).
- Sanity (`out/full/sanity.txt`, prices 0.10-0.90 only): prints at 0.45-0.55 won 50.6% share-weighted (964,688 prints,
  5,366 markets); fee 0.0693 c at 0.01, 1.75 c at 0.50 (rate 0.07); 94.1% of prints inside the window; Binance 60 s
  average agrees with the official outcome in 6,128 of 6,257 markets (97.9%).
- Fees: `rate * p * (1 - p)` per share, rate by block time (0.07 before 2026-11-20 23:59 UTC, 0.05 after), rebates 0.

## What was run (all of it is counted)

- **Trading rules: 2** (T2 variants A and B), each in 4 periods (Sep, Oct, Nov, pooled) = 8 variant-periods. Nothing
  was tuned; November is the reporting month.
- **Descriptive cells:** T1 24 tail cells (4 price bands x 6 seconds-left bands) pooled, 72 cell-months, 24 cells for
  source B only; T4 18 favourite cells pooled and 54 cell-months; T3 7 comparison cells and 7 features each. In total
  120 T1 + 72 T4 + 7 T3 cell tables.
- **Post-hoc, descriptive, not rules:** `capacity.py` (size of the whole pie in the T2 cell, concentration of the T2
  result), `t3_extra.py` (exact binomial of Vega7 against its own break-even, by month; result without its best 3
  markets).

## T2. The published rule (protocol 2.4), after fees

| variant | period | markets traded | tickets | stake $ | avg price | markets won | return on stake (95% CI) | t | net $ (bootstrap 95%) | $/day, all windows |
|---|---|---|---|---|---|---|---|---|---|---|
| A <= 0.02 | Sep | 2,054 | 41,067 | 32,261 | 0.0093 | 24 | -29.8% (-74, +14) | -1.33 | -9,615 (-22,180, +5,504) | -1,282 |
| A <= 0.02 | Oct | 2,156 | 37,470 | 32,783 | 0.0082 | 20 | -34.0% (-71, +3) | -1.78 | -11,151 (-22,085, +1,736) | -1,439 |
| A <= 0.02 | **Nov** | 1,808 | 30,183 | 28,734 | 0.0076 | 17 | **-46.4% (-82, -11)** | -2.57 | -13,325 (-22,800, -2,377) | -2,050 |
| A <= 0.02 | All | 6,018 | 108,720 | 93,778 | 0.0083 | 61 | -36.4% (-59, -14) | -3.13 | -34,091 (-53,620, -11,739) | -1,567 |
| B <= 0.05 | Sep | 2,097 | 35,811 | 39,932 | 0.0146 | 59 | -13.2% (-46, +20) | -0.79 | -5,258 (-17,042, +8,885) | -701 |
| B <= 0.05 | Oct | 2,191 | 35,096 | 38,457 | 0.0116 | 54 | -31.2% (-56, -7) | -2.52 | -12,005 (-20,644, -2,559) | -1,549 |
| B <= 0.05 | **Nov** | 1,838 | 28,486 | 31,974 | 0.0102 | 37 | **-40.1% (-66, -14)** | -3.00 | -12,822 (-20,539, -3,922) | -1,973 |
| B <= 0.05 | All | 6,126 | 99,393 | 110,362 | 0.0120 | 150 | -27.3% (-44, -11) | -3.25 | -30,084 (-46,775, -11,626) | -1,383 |

How to read: "markets won" = markets where at least one ticket was on the winning side; CIs are +-1.96 clustered
standard errors (markets are the clusters). Share-weighted, variant A paid a break-even of 0.89% and its shares won
0.59% (11.3M shares); variant B 1.28% vs 0.95%. A typical losing market costs $16.60 (A) and a winning one pays
$1,062, so the result hangs on about 60 wins: removing the best 3 markets makes it worse (A -$42,724, B -$38,406).
Raw: `out/full/t2.md`, `out/full/capacity.md`.

## T1. All buyable tail prints (pooled, all sources)

Selected cells (full table with Wilson intervals, by month and for source B: `out/full/t1_t4.md`).

| price | s left | markets | hit markets (rate) | break-even | exact p | net c/share (t) | Sep / Oct / Nov net c/share |
|---|---|---|---|---|---|---|---|
| <= 0.015 | 180-75 | 2,433 | 12 (0.49%) | 0.99% | 0.005 | -0.11 (-0.3) | -0.30 / +0.82 / -0.91 |
| <= 0.015 | 75-45 | 4,372 | 15 (0.34%) | 0.92% | <0.001 | -0.16 (-0.7) | -0.13 / -0.19 / -0.16 |
| <= 0.015 | 45-15 | 5,669 | 17 (0.30%) | 0.86% | <0.001 | -0.38 (-2.9) | -0.16 / -0.30 / -0.68 |
| <= 0.015 | 15-0 | 4,929 | 2 (0.04%) | 0.81% | <0.001 | -0.62 (-8.6) | -0.58 / -0.71 / -0.56 |
| 0.015-0.03 | 75-45 | 2,855 | 65 (2.27%) | 2.58% | 0.17 | +0.12 (+0.2) | -0.51 / +1.48 / -0.74 |
| 0.015-0.03 | 45-15 | 1,754 | 46 (2.60%) | 2.53% | 0.45 | -0.01 (-0.0) | +0.36 / +0.39 / -1.01 |
| 0.03-0.05 | 75-45 | 2,501 | 113 (4.49%) | 4.57% | 0.45 | +0.11 (+0.2) | -0.61 / +0.60 / +0.50 |
| 0.03-0.05 | 45-15 | 1,345 | 66 (4.81%) | 4.52% | 0.32 | -0.56 (-0.9) | +0.49 / +0.20 / -2.44 |
| 0.05-0.10 | 75-45 | 2,577 | 226 (8.55%) | 8.15% | 0.24 | +0.01 (+0.0) | -0.04 / +1.69 / -2.10 |
| 0.05-0.10 | 45-15 | 1,249 | 120 (9.06%) | 7.96% | 0.08 | -1.40 (-1.6) | -0.65 / -1.26 / -2.39 |

How to read: "hit markets" counts (market, outcome) pairs with a print in the cell whose outcome won; break-even is
the average price + fee of those pairs; "exact p" is the one-sided binomial probability of a deviation this large
if the break-even were the true win rate. All tail prints inside the window together: 666,973 prints, $1.48M of
stake, -0.41 c a share (t -2.5), -14.6% of stake; prints where a taker really bought the tail (source B) -0.33 c
(t -1.9); prints where a taker sold the favourite into a bid (source S) -0.78 c (t -4.4). November is the worst of the three
months in 14 of the 21 tail cells that have prints in every month.

Correction for many cells (protocol 2.7, |t| >= 3.1 for 24 cells, 3.25 for 42, same sign in all three months):
three tail cells pass, all negative: <= 1.5 c with 15-0 s left (-0.62 c, t -8.6, binomial z -6.0), <= 1.5 c after
the end (-0.30 c, t -15.7, z -5.4) and <= 1.5 c with 300-180 s left (-1.09 c, 0 of 64 won: the t there is
meaningless, binomial p 0.50). **No positive tail cell survives; no positive tail cell reaches |t| 2.**

## T4. The mirror: favourite prints at 0.95 or more

The favourite side is roughly fair inside the window (pooled -2.0 to +0.5 c a share in 14 of the 15 cells inside
the window; the exception is below). Mirror check, <= 1.5 c tail vs >= 98.5 c favourite: "tail dear, favourite
cheap or fair" in 5 of 6 seconds bands; in 45-15 s left both lose (-0.38 c and -0.14 c: the spread). The signs agree
with T1: the cheap side is the overpriced side.

Cells that pass the correction (all positive, all favourites, all thin): >= 0.985 after the end (+0.95 c, 24 of 24
markets won), 0.97-0.985 after the end (+1.75 c, 10 of 11), and **0.95-0.97 with 15-0 s left (+3.10 c a share,
t +7.3, 225 of 232 markets won, positive in each month: +2.36 / +3.13 / +4.03 c)**. Their t rests on few or no
losing markets; at the market level none beats its break-even significantly (binomial z -1.7 to +0.7). The last
cell is about 10 markets a day across all windows. It is outside this study's question: see "Ideas".

## T3. Vega7 against all tail prints

| | units (market, outcome) | won | rate [Wilson 95%] |
|---|---|---|---|
| Vega7, cell "<= 0.05, seconds 225-285", all its markets | 1,630 | 61 | 3.74% [2.92, 4.78] |
| Vega7, same cell, grid markets only | 389 | 16 | 4.11% [2.55, 6.58] |
| all grid markets with a print in that cell (baseline) | 6,233 | 153 | 2.45% [2.10, 2.87] |
| Vega7, "<= 1.5 c, 75-45 s left" | 526 | 20 | 3.80% [2.47, 5.80] |
| baseline, same cell | 4,372 | 15 | 0.34% [0.21, 0.57] |
| Vega7, "<= 1.5 c, 45-15 s left" | 613 | 15 | 2.45% [1.49, 4.00] |
| baseline, same cell | 5,673 | 17 | 0.30% [0.19, 0.48] |

Vega7 pays about the same price as the baseline (0.0091 vs 0.0080 in the 75-45 cell), so the difference is in the
markets, not the price. In the four 1.5-3 c and 3-5 c cells (88-198 Vega7 units) the difference is small and not
significant (z +0.5 to +1.3). By month in the pooled cell: Sep 31 of 1,036 won (+$12,798), Oct 15 of 438 (+$8,309),
Nov 15 of 156 (+$7,592); exact p against its own break-even 0.006, 0.010, 1.3e-6. Without its best 3 markets the
pooled cell is still +$23,539. But Vega7 is fading: 91 fills a day in September, 20 in October, 13 in November, and in
the two <= 1.5 c cells its October and November results turn negative without the best 3 markets (-$128 to -$784).

Separation (pooled cell, Vega7 1,630 units vs baseline 6,233; tercile hit rates are the baseline's):

| variable | Vega7 mean | baseline mean | std. mean diff | rank-sum z | baseline hit rate by tercile low / mid / high |
|---|---|---|---|---|---|
| distance from winning, model sd | 2.96 | 3.81 | -0.41 | -16.3 | 6.7% / 0.5% / 0.1% |
| same, window shifted 5 s | 3.62 | 4.23 | -0.30 | -12.6 | 6.9% / 0.4% / 0.1% |
| Binance move toward the tail, last 30 s (bp) | +0.55 | -0.85 | +0.46 | +17.5 | 1.8% / 1.3% / 4.2% |
| realised volatility, last 5 min (bp) | 6.46 | 8.18 | -0.25 | -6.9 | 2.5% / 2.9% / 2.0% |
| absolute 30 s move (bp) | 2.26 | 2.45 | -0.07 | -2.8 | 3.1% / 2.1% / 2.2% |
| hour of day (four 6-hour blocks) | 25 / 29 / 25 / 21% | 25% each | | | no difference |

Inside the top tercile of "move toward the tail" Vega7 still wins 5.7% (52 of 915) against 4.2% for the baseline,
so no single variable explains it. In the <= 1.5 c, 45-15 cell the distance difference is larger (3.73 vs 5.63 sd,
-0.84). **Hypothesis for a later out-of-sample test (not a rule):** tails priced <= 1.5 c in seconds 225-285 are
underpriced when the Binance-based expected settlement average is within about 2.6 model standard deviations of the
strike AND Bitcoin has moved toward the tail in the last 30 s; everywhere else they are overpriced. This is a race
for stale offers after a Binance move. Raw: `out/full/t3.md`, `out/full/t3_extra.md`.

## Capacity, for an account of about 200 EUR

- **Published rule: $0 a day.** At the stated $25 a market it would have lost about $1,570 a day over all windows
  (A, pooled; Nov $2,050). Capital is not the limit (a ticket ties $25 for about a minute), the sign is.
- **Size of the whole pie** (every print in the T2 cell taken by somebody, scaled to all windows, `capacity.md`):
  about $7,900 a day of stake at <= 0.02 and $13,800 at <= 0.05, and all of it together lost $2,300-2,400 a day.
  Median print: 17-20 shares, $0.18-0.36.
- **Vega7-style selection (if the hypothesis holds out of sample):** Vega7 itself made about $390 a day on about $360
  a day of stake with $10 median tickets. A 200 EUR account cannot carry $10-25 tickets at a 3-4% hit rate (20 tickets
  without a win happen about half the time), but the minimum order is 5 shares, i.e. $0.05 at 1 c, so $1-2 tickets
  are possible; at that size the honest ceiling is tens of dollars a day before competition, and zero until the
  hypothesis is tested.

## What a trader would need to run it live

For the published rule: nothing; do not run it. For the Vega7-style hypothesis, after it passes an out-of-sample
test: a real-time Binance BTCUSDT trade feed (WebSocket, millisecond timestamps) and the Polymarket CLOB market
WebSocket for both outcomes; a model of the expected 60-second settlement average (the official average runs about
5 s behind Binance, see the lock-in study); reaction within about a second of a Binance move, with the 150 ms crypto
taker delay on top (the offers it buys are stale quotes that get pulled); a server near London (the matching engine
is in AWS eu-west-2) in a country that is not geoblocked; capital of a few hundred dollars for $1-10 tickets and long
losing streaks. None of this can be built or recorded in this sandbox (no WebSockets).

## Attacks on the results

- **Negative T2 result:** not a fill artefact (the rule takes prints that really traded, at their own price and
  size, which flatters it if anything); not one bad month (all three months negative for both variants); not a fee
  artefact (fees are 6-7% of stake; the result is -27 to -36%). Concentration makes it worse, not better.
- **Vega7 result:** (1) survivorship: the wallet was picked by a promoter for its 90-day result, and our period is
  the same 90 days, so this is in-sample for that selection; the exact p 2.6e-7 survives even a selection out of
  10,000 wallets, but persistence after the selection window is untested. (2) Look-ahead: features use the Binance
  second at block time minus 3 s, about 0.9 s before the real match; no future data. (3) Completeness: all 907 of
  its grid fills are in the tapes. (4) Small sample: 61 winning markets in the pooled cell, 20 and 15 in the two
  1.5 c cells; November rests on 15 wins; the clustered t is shown with exact binomials next to it.
- **The tail cells' t values** with 0-10 winning markets are unreliable (marked in `t1_t4.md`); conclusions above
  use the exact binomial where that matters.

## Limitations

- One window in four (6,264 of about 25,000); dollar-per-day figures are scaled x4.
- Fills are taken from the tape: the hypothetical trader replaces the taker who really got that liquidity, at the
  print's price and size and match time. No extra reaction delay or queue can be simulated on the tape; for source-S
  prints the resting bid may already have been taken by the real seller.
- Gamma volume is missing on 451 used markets, so their tape completeness could not be checked (5,806 checked
  markets all pass).
- The T3 baseline is grid markets only; Vega7's own numbers use all its markets (the grid-only subset is shown).
  Its separation analysis is descriptive; the tercile cuts were not chosen to optimise anything, but the hypothesis
  above has been written after seeing them and must be tested on other data.
- The fee changed on 2026-11-20 (0.07 -> 0.05); only 6 days of the period are at today's rate.
- Deviations from the protocol: (1) the first researcher ran `t1_t4.py`, `t2.py`, `t3.py` on a 222-market September
  slice (`out/slice/`) before the full run, i.e. outcome statistics on tail prices were seen on 3.5% of the sample;
  `protocol.md` predates those files and was not changed. (2) The download was run with 8 parallel processes
  (`fetch_par.py`) and Vega7's metadata with 3 (`fetch_v7_par.py`) instead of sequentially; same grid, same records,
  plumbing only. (3) `t3.py` prints separation tables only for cells with at least 30 Vega7 units (the hit-rate table
  covers all 7 cells). (4) `audit.md` (independent check) does not exist yet: per AGENTS.md this result is not
  accepted until it does.

## Ideas, not tested

1. Pre-registered out-of-sample test of the T3 hypothesis (tail <= 1.5 c, seconds 225-285, distance < about 2.6
   model sd, Binance moving toward the tail) on December 2026 tapes, or on June-August 2026, with the thresholds fixed
   before looking.
2. Vega7 before September (June-August fills): does the selection edge exist outside the promoter's window?
3. Replay against recorded L2 books (HF `Fahri-5/updown-5m-polymarket-raw` 17 Oct - 8 Nov, `ithiria894` 16-22 Nov)
   to see whether a taker reacting 0.15-1 s after the Binance move still finds the 1 c offer.
4. Favourite at 0.95-0.97 in the last 15 s (+3.1 c a share, 232 markets, 7 lost): a separate pre-registered study
   with a book replay; it overlaps the lock-in study's "last-minute favourite" finding.
5. Equal small size per market instead of "take the print": in the pooled cell the equal-weight hit rate of (market, outcome)
   units (2.45%) is far above the share-weighted hit rate of all prints there (1.16%, against an average price of
   1.30%), i.e. the big tail prints are the losing ones.
