# BTC 5-minute tails: independent audit

Auditor: fresh-context agent, 2026-11-27. Checked against `docs/audit-checklist.md`, AGENTS.md "Правила исследования",
`protocol.md` (mtime 2026-11-27 16:41) and `results.md` (mtime 18:03). The repository is not under git here, so the order
of files is known from file mtimes only. Nothing in `results.md` or `protocol.md` was edited. No orders, wallets or keys
were used.

## Verdict: HOLDS

The negative headline reproduces to the dollar from the raw cache with independent code, and no bug that could hide a
positive effect was found. Eleven audit sensitivity variants were run for each price cap (22 in total, listed under 4).
All of them are negative in November and over the whole period. The Vega7 numbers also reproduce exactly. The audit
narrows one claim: Vega7's edge is real only inside the promoter's 90-day window. The lab's own wallet check found it
roughly flat in April-June and negative in August (`catalog/raw/x1_bot_posts.md`, line 341). The T3 "what it selects"
reading reproduces in direction but not in size (see 6).

**Corrected headline (unchanged in substance).** Buying every buyable print at or under 2c (A) or 5c (B) in seconds
225-285, up to $25 of stake per market, after the taker fee, loses in every month.

- November 1-26: A -46.4% of stake (95% CI -82% to -11%, t -2.57, 1,808 markets traded, 17 won); B -40.1% (CI -66% to
  -14%, t -3.00, 1,838 markets, 37 won).
- Sep-Oct: A -31.9% (t -2.17, 4,210 markets); B -22.0% (t -2.10, 4,288 markets).
- Pooled over 6,244 used markets: A -36.4% (t -3.13, 6,018 traded); B -27.3% (t -3.25, 6,126 traded).
- Tails at or under 1.5c win less often than their break-even. With 75-45 s left 15 of 4,372 (market, outcome) units
  won against 0.92% needed (exact P = 4.5e-6). With 45-15 s left 17 of 5,673 won against 0.86% (P = 1.4e-7).
- Vega7 kept +$34,047 on $31,139 of stake in the same 87 days (+1.72c a share, t 4.41 by market, 3,636 markets). In the
  "1.5c or less, 75-45 s left" cell it hit 3.80% (20 of 526) against 0.34% (15 of 4,372) for all grid markets (z +8.9).
  This is in-sample for the promoter's selection of the wallet, and its persistence outside Sep-Nov is not shown.
- For a 200 EUR account the result is **$0 a day**. Nothing here is tradeable.

## Independent reproduction (checklist item 6)

All code is in `studies/gaps/btc5m_tails/audit/`. It reads the raw cache directly: `data/updown_meta/btc/5m/<t0>.json`
and `data/tape/<condition>.jsonl.gz`, plus `data/binance_1s/*.zip` and `data/gaps_btc5m_tails/vega7_fills.json`. It
imports nothing from the study's `common.py`, `build.py` or `t*.py`, and does not use `pmlab.updown.buyable`. The audit
reimplements the BUY -> (o, p), SELL -> (other, 1-p) mapping, the block lag, the per-market budget walk, the fee, and
the clustered ratio and its t.

- `extract.py OUT.parquet LAG`: 6,264 grid windows -> 6,244 ok, 13 empty tapes, 7 without a market. It finds 693,070
  tail prints (p <= 0.10) and runs in 9 s.
- `t2_recompute.py`: matches `results.md` exactly. The full output:

| variant | period | markets | stake $ | markets won | fees $ | net $ | return on stake [95% CI] | t |
|---|---|---|---|---|---|---|---|---|
| A <=0.02 | Sep | 2,054 | 32,261 | 24 | 2,230 | -9,615 | -29.8% [-74, +14] | -1.33 |
| A | Oct | 2,156 | 32,783 | 20 | 2,267 | -11,151 | -34.0% [-71, +3] | -1.78 |
| A | **Nov** | 1,808 | 28,734 | 17 | 1,857 | -13,325 | **-46.4% [-82, -11]** | -2.57 |
| A | Sep+Oct | 4,210 | 65,044 | 44 | 4,497 | -20,766 | -31.9% [-61, -3] | -2.17 |
| A | All | 6,018 | 93,778 | 61 | 6,354 | -34,091 | -36.4% [-59, -14] | -3.13 |
| B <=0.05 | Sep | 2,097 | 39,932 | 59 | 2,719 | -5,258 | -13.2% [-46, +20] | -0.79 |
| B | Oct | 2,191 | 38,457 | 54 | 2,624 | -12,005 | -31.2% [-56, -7] | -2.52 |
| B | **Nov** | 1,838 | 31,974 | 37 | 2,040 | -12,822 | **-40.1% [-66, -14]** | -3.00 |
| B | Sep+Oct | 4,288 | 78,389 | 113 | 5,343 | -17,262 | -22.0% [-43, -2] | -2.10 |
| B | All | 6,126 | 110,362 | 150 | 7,383 | -30,084 | -27.3% [-44, -11] | -3.25 |

- `vega7_recompute.py`: reproduces 3,693 BUY fills in 3,636 windows, with outcomes taken from the raw meta cache rather
  than the study's `vega7_meta.json`. Net is +$34,047 on $31,139, +1.72c a share, t +4.41. By month: Sep +13,279, Oct
  +10,536, Nov +10,232. The cell results match: 20/526 vs 15/4,372 (z +8.9), 15/613 vs 17/5,673 (z +7.1), and the
  pooled <=5c cell 61/1,630 vs 153/6,233 (z +2.8). On the grid alone Vega7 hits 5 of 124 and 3 of 151.
- `cells_and_handcheck.py`: exact binomials of the <=1.5c cells (above; the 15-0 s cell is 2 of 4,930 against 0.81%,
  P = 3e-15). It also has a hand check of tickets.

## Checklist

### 1. Look-ahead: clean

- T2 decides from the print alone: match time (block time - 3 s), price and the budget used so far. Neither the outcome
  nor any later print enters the decision. The budget walk uses a cumulative sum over earlier prints only.
- Block-delay sensitivity (`extract.py` with lag 0, 2 and 5, then `t2_recompute.py`):
  - A, November: -44.1%, -45.9% and -45.5%.
  - A, pooled: -37.3%, -35.8% and -35.5%.
  - B, November: -42.6%, -42.7% and -39.4%.
  - B, pooled: -26.1%, -27.3% and -26.3%.
  - The result does not depend on the 3 s assumption.
- Tie order inside one block: the cache is stable-sorted from a newest-first API, so ties may sit in reverse order.
  Reversing them gives A Nov -46.3% / All -35.8% and B Nov -39.3% / All -25.6%.
- Vega7 is measured from its own real fills. T3 features use Binance at match time, which is before the fill.

### 2. Execution: optimistic, which cannot rescue a negative sign

- The rule takes each printed fill at its own price and size and at its match time. It replaces the real taker, with no
  queue, no reaction delay and no 150 ms taker delay. For source-S prints the resting favourite bid was consumed by the
  real seller, so a second taker would not have got it.
- Every one of these assumptions flatters the rule, and it still loses. Taker rows are VWAPs of whole taker orders (NOTES,
  data API section), so a print price may never have stood as a single level. Sweeping the same levels gives the same
  VWAP, so this does not bias the result.
- The $25 cap holds: the stake per market is at most 25.00 by construction (`np.minimum(budget - used, full)`).
- Liquidity is not used twice: each print is taken once, and each market's budget is shared by both outcomes.
- Source split, first print, 5 shares (`sensitivity.py`):
  - At <=2c: real tail buys (BUY) -31.0% pooled (t -3.15); favourite sold into a bid (SELL) -51.9% (t -5.94).
  - At <=5c: BUY -12.0% (t -1.57); SELL -24.4% (t -3.10).

### 3. Fees and accounting: correct, counted once

- Rate by block time: 0.07 before 1795219140 (2026-11-20 23:59 UTC), 0.05 after. The meta cache agrees: fee type
  `crypto_btc_5m_15m_fees` at 0.05 on 432 grid markets after the change. The 0.01 `crypto_fees_v2` value on older
  markets is the unreliable field that NOTES warns about.
- Rebates are 0.
- Before fees: A -29.6% (t -2.55), B -20.6% (t -2.45). After fees: -36.4% and -27.3%. The difference equals fees divided
  by stake (6,354 / 93,778 = 6.8%), so the fee is counted exactly once.
- Hand check, market t0 1788730800, Down won, three tickets at p 0.001 with e = 225-226:
  - 125.18 shares cost $0.1252 plus a fee of 0.07 x 0.001 x 0.999 x 125.18 = $0.0088, for a net of +$125.046. The code
    gives the same.
  - The 5.07-share and 5.00-share tickets give +$5.065 and +$4.995, equal to the code.
- Mean net per losing market is -$16.60, per winning market +$1,062.16, as stated in the results.
- Outcome direction: `up_won` equals (final_price >= price_to_beat) in all 6,242 markets that carry both fields (3,039
  Up, 3,203 Down, 0 disagreements). The "greater or equal" rule is respected.
- The sign of `won` is right. The tail cells at 0.05-0.10 are calibrated (8.55% hit against 8.15% break-even), while a
  flipped sign would show tails winning about 92%.

### 4. Statistics: clean

- Clusters are markets. Clustering by UTC day instead (87 clusters) gives A -36.4% (t -3.14) and B -27.3% (t -3.09).
- Without the best day: A -$37,784, B -$34,108. Without the best 3 / 10 markets: A -$42,724 / -$58,160, B -$38,406 /
  -$48,354. Concentration only makes the result worse.
- Reporting month: November is a later period and nothing was tuned. There are 2 rules x 4 periods. The rule has no
  signal, so it is its own "blind" version.
- Could a different, equally simple sizing hide an edge? `results.md` "Ideas" 5 suggests that equal-weight units hit
  more often than share-weighted prints. Audit variants, pooled:
  - V1, first qualifying print, 5 shares: <=2c -37.2% (t -3.92); <=5c -14.8% (t -1.92).
  - V2, first print, $1: <=2c -43.4% (t -3.81); <=5c -27.8% (t -3.25).
  - V3, every print, 5 shares, no budget: <=2c -36.1% (t -2.98); <=5c -10.6% (t -1.04).
  - Every month of every variant is negative. The equal-weight hit rate (1.01% at <=2c, 2.40% at <=5c) stays below the
    equal-weight average price (1.42c, 2.65c).
- Audit variants counted: lag 0/2/5 (3), tie reversal (1), de-duplication (1), excluding over-counted tapes (1), and V1,
  V2, V3, V1-BUY, V1-SELL (5). That is 11 per cap, 22 in total, and none is positive in any period.
- Multiple cells: the study counts 120 T1 + 72 T4 + 7 T3 cell tables and applies Bonferroni at |t| >= 3.1 / 3.25. The
  three <=1.5c cells re-checked here pass on exact binomials, all negative.

### 5. Data: minor findings, no effect on the numbers

- Coverage: 6,264 grid windows, 6,244 used, with 7 missing markets and 13 empty tapes. This matches `results.md`.
  Binance 1 s: 0 missing seconds from Sep 1 to Nov 26.
- Exact duplicate tape rows: 434,758 of 9,569,388 (4.5%). There is no trade id, so identical (block, side, outcome,
  size, price, wallet) rows can be genuine. The tape-to-volume ratio is 1.0000 at the median and 1.0011 at p99, which
  says they are real fills. De-duplicating anyway: A Nov -45.9% / All -35.4% (t -3.00); B Nov -40.7% / All -27.2%.
  Minor.
- Tape vs gamma volume: 31 markets have tape shares more than 1.02x the gamma volume. In 21 of them the gamma volume is
  absurdly small (2-2,700 against 20K-190K tape shares), so the gamma field looks wrong there, not the tape. The protocol
  filter only removes tapes under 90%, so these markets stay in the sample. Together they contribute +$2,743 (A) and
  +$2,561 (B) to the T2 net (2 wins). Excluding them makes the result more negative: A All -39.5% (t -3.47), B All
  -29.7% (t -3.64). Minor.
- Count typo: `results.md` says gamma volume is missing on 451 markets. Among the 6,244 used markets it is 438
  (5,806 + 438 = 6,244). 451 probably counted all 6,257 markets with metadata. Cosmetic.
- T1 table: 5,669 "markets" against 5,673 "units" in the 45-15 cell. This is not an error: one counts markets, the other
  (market, outcome) units.
- Time zone: months are UTC months of t0, and the fee switch time was checked (Nov 27 00:00 UTC - 1795219140 s = 6.0
  days, i.e. Nov 20 23:59 UTC).

### 6. Deviations from the protocol and other open points

- Disclosed in the results: the first researcher ran T1/T2/T3 on a 222-market September slice (`out/slice/`, mtimes
  16:44-16:47) after `protocol.md` was written (16:41). That is 3.5% of the sample, the protocol was not changed, and
  nothing was tuned. The download was parallelised. Neither point affects the result.
- Vega7 selection (moderate, about the T3 claim, not about the headline):
  - The 87-day window is the promoter's selection window.
  - The lab's earlier wallet decomposition (`catalog/raw/x1_bot_posts.md`, line 341) shows Apr-Jun +$1.0K on $47K
    staked and Aug -$0.6K.
  - The study's own data show fills fading: 91 a day in September, 20 in October, 13 in November.
  - "Real but selective" therefore holds for Sep-Nov only. Out-of-sample persistence is unknown, and the exact p of
    2.6e-7 does not cover a selection over wallets x months.
- T3 separation reproduced in direction only (`t3_direction.py`). With simpler definitions than the study's (a raw
  Binance 30 s move, and Binance minus the official price_to_beat in bp instead of model sd), Vega7's units sit closer
  to the strike (mean gap 3.81 bp vs 7.93 bp; standardised difference -0.37, study -0.41). Binance had also moved
  toward the tail (-0.09 bp vs -0.91 bp; +0.27, study +0.46). The baseline hit rate falls by tercile of the gap (3.5% /
  2.6% / 1.3%) and rises in the top tercile of the move (1.9 / 1.9 / 3.6%). The study's own numbers (+0.55 vs -0.85
  bp, terciles 6.7 / 0.5 / 0.1%) use `gap_in_sigmas` and its own alignment and were not reproduced exactly. They remain
  a hypothesis, as the results say.

## What was checked and is clean

- The T2 headline in all 10 variant-periods, to the dollar.
- The <=1.5c tail cells and their exact binomials.
- The Vega7 totals, monthly split and cell hit rates.
- The fee formula, rate dates and single counting.
- The outcome direction and the >= rule.
- Block-lag and tie-order sensitivity.
- Clustering by market and by day, best day and best markets removed.
- Equal-weight sizing alternatives and the source split.
- Duplicates and the completeness filters.
- Coverage of tapes and Binance data.

## To trade this live you would need

There is nothing to trade. The published rule loses at every lag, sizing and month tested, so a test with real money,
even a small amount, would only measure the connection, not an edge.

The only thing left is the Vega7-style hypothesis: a 1c tail is cheap when Binance has just moved toward it and the
average is close to the strike. That needs, in order:

1. A pre-registered out-of-sample test on other months (June-August or December 2026), with thresholds fixed before
   looking.
2. A replay against recorded L2 books (HF `Fahri-5`, 17 Oct - 8 Nov) to see whether a taker reacting 0.15-1 s after the
   Binance move still finds the 1c offer.
3. Only then, a live set-up: a real-time Binance trade feed and the Polymarket CLOB market WebSocket; a model of the
   60 s settlement average (about 5 s behind Binance); sub-second reaction on a host near AWS eu-west-2 in a country
   that is not geoblocked; and $1-5 tickets (5-share minimum) to survive losing streaks at a 3-4% hit rate.

None of this can be built or recorded in this sandbox (no WebSockets). Until step 1 passes, the realistic expectation for
a 200 EUR account is $0 a day.
