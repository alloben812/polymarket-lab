# Audit — crypto price-level markets vs option-implied probabilities

Sceptic's pass, 2026-11-27. Audited: `protocol.md`, `results.md`, the code and `data/gaps_levels/`.
My scripts are in `audit/` (run from a scratch directory, in this order: `repro.py`, `compare.py`, `data_checks.py`,
`live1.py`, `live2.py`, `robust.py`, `robust2.py`, `robust3.py`, `ot_check.py`, `final_checks.py`). The analyst's files
were not edited.

## Verdict: WEAKENED

The study's conclusion — no tradable edge shown — stands, and is firmer than the analyst wrote. What does not stand
is the one positive number left in the headline: **+$694 on 43 tape-confirmed entries, t = 2.08, +$63 a day**. Every
number in the study reproduces to the cent, but that residual is produced by four things that are not an edge:
uncapped size, fill evidence that predates the entry price, a tune/report split that leaks, and a benchmark of zero
in a month when any NO buyer made +94% on stake. Corrected, it is between -$22 and +$164 (t between -0.9 and +1.9
against zero) and indistinguishable from zero against blind NO buying. The lab should read this study as
"no edge for the taker rule", not as "inconclusive with +$63 a day to follow up".

## What I reproduced (point 6)

Own code, no shared functions, from the raw inputs (`universe.json` metadata, `ph/*.json`, Binance and DVOL arrays,
`tape/*.json.gz`). Coverage is 100% of the sample, not a quarter.

| item | analyst | mine |
|---|---|---|
| European universe re-derived from the raw gamma dump | 560 (550 daily + 10 hourly) | 560, same condition ids |
| official outcome from the Binance candle opening 11:59 ET / 12:00 ET | 550 / 549 of 550 | 550 / 549 |
| rule entries, 9 variants | 3,352 (2,078 distinct, 514 markets) | 3,352 matched one to one; entry price, gap, model identical; PnL differs by at most 1e-14 |
| tape-confirmed distinct entries | 473 | 473, same entries; full-size flag identical |
| 18 confirmed cells (period x g x band) | table in results.md | every cell identical |
| tuned variant, confirmed, report | 43 entries, 34 markets, 15 clusters, +$694.5, t 2.08 | same |
| 150-entry protocol sample (same seed) | 46 confirmed, 30 with size | 46, 30 |
| L1 active market-hours / mean / sd / mean abs / share >= 0.05 | 40,866 / +0.005 / 0.039 / 0.024 / 8.6% | 40,866 / +0.0047 / 0.0385 / 0.0239 / 8.6% |
| L2 autocorrelation 1 / 4 / 12 h; decay slopes | 0.65 / 0.58 / 0.47; 0.41 / 0.32 / 0.24 | 0.652 / 0.577 / 0.469; 0.407 / 0.322 / 0.242 |
| one-touch entries | 2,717 | 2,717 matched, PnL identical |

Raw data against the live APIs: 12,000 freshly downloaded Binance 1-minute candles (12 random blocks) — 0 differ
from the cache, no missing minutes, no duplicates. DVOL hourly row stamped X carries the value at X + 3600 (checked
against 1-minute DVOL), so "close of the last finished hour" in the code is right. 81 markets re-downloaded (all 61
with a confirmed tuned entry and 20 random): 0 tapes differ, 2 price histories differ by one point. Tape shares equal
gamma `volumeNum` in 532 of 532 cached tapes, so no tape is truncated.

## Audit by item

**1. Look-ahead.** None in the model inputs: spot is the close of the candle that ended at or before t, DVOL is the
last finished hour, realised vol ends at t, the outcome enters only at settlement. The `prices-history` point labelled
t equals the 1-minute point labelled t; its changes line up with the Binance minute ending at t (correlation 0.89
on the near-the-money market checked) and slightly with the next minute (0.18), so the snapshot is taken a few
seconds after t. That does not touch PnL because the entry is priced at t + 300. Two look-ahead-type defects do
matter and are listed as problems 2 and 3 (fill evidence dated before the entry price; variant selected on outcomes
that were not yet known when 18 of the 43 report entries were made).

**2. Fills.** This is where the headline fails; problems 1 and 2. Within the tuned variant no print is used twice
(entries of one market are 12 h apart). In the pooled "all distinct confirmed" figures (+$1,249 / +$967) 9 entries
share their 10-minute window with another entry of the same market and side, and 145 sit within 12 h of one; those
pooled figures are descriptive only, as the analyst says.

**3. Fees and accounting.** Three entries recomputed by hand match (for example NO at 0.114: 175.439 shares, fee
$0.1772, win, +$155.261). Settlement direction is right: rule text says "higher than", outcomes are the official
ones, and the one market that separates the two candle readings resolved with the 11:59 candle. The tape has no fee
field, so the rate before 20 Nov stays unverified; at 0.07 instead of 0.01 the report figure would be +$676.6
instead of +$694.5. Not material.

**4. Statistics.** Problems 3, 4 and 5.

**5. Data.** Clean apart from the volume unit (problem 8). No duplicated markets or tokens; price histories cover
99.9% or more of the expected 5-minute buckets in every daily market (6 markets have a hole of up to 15 minutes);
28 European markets have no cached tape, and none of them has an entry in the primary run.

## Problems

| # | severity | problem | effect on the numbers |
|---|---|---|---|
| 1 | high | Size is not capped at what the tape shows. The simulation books $20 at the entry price whenever any print at that price exists. Median tape size at or below the entry price is 16 shares against 26.8 assumed; 16 of 43 entries had under a quarter of the size, 9 had exactly the 5-share minimum. The three largest wins buy 160-178 NO shares at 11-12 cents where the tape shows 10, 18 and 31 shares. | Report, tuned, confirmed: +$694.5 -> **+$164.4** on $480 of stake actually on the tape (t 1.88). The top three entries: $453.5 -> $52.3. Tune: +$471.9 -> +$48.9 (t 0.43). |
| 2 | high | Fill evidence predates the entry price. The entry price is the mid of bucket t + 300 plus 1 cent, but a print anywhere in (t, t + 600] counts. In 30 of the 43 entries the only qualifying print came before t + 300, before the price the order is supposed to pay was observable. Those 30 carry $651. (The window is the lab lead's wording; the defect is inherited from the protocol.) | Prints in (t+300, t+600] only: 13 entries, **+$43.9** (t 0.41); size-capped -$21.5. Prints in (t+300, t+900]: 28 entries, +$153.4 (t 1.08); size-capped +$4.9. Tune period under the same two windows: -$57 and -$55. Across the 48 h-7 d band the confirmed share falls from 7.0% to 2.8-4.5%. |
| 3 | high | The split leaks. Markets are assigned by resolution date, but a ladder trades for 7 days before it resolves, so "report" entries run from 9 Nov while "tune" outcomes run to 15 Nov. 18 of the 43 report entries were signalled before the last tune market resolved; the variant was chosen on outcomes produced by the same BTC path (75.1K on 9 Nov to 64.7K on 15 Nov) and not yet known at those entries. | Those 18 entries: +$647.4. The 25 entries made after the tune period ended: **+$47.2** (t 0.43); size-capped -$19.5. |
| 4 | high | The t-value is against zero, which is the wrong benchmark in a month with BTC -27%. Placebo with the same band, same entry price, same tape rule and no gap condition: blind NO earned +94% on stake in the report period (980 entries, 185 markets; +92% for entry prices 0.10-0.90) and +102% in the tune period; blind YES lost 59% and 50%. The signal: +81% overall, +114% on its NO side, 72% of its entries are NO. | Excess of the 43 entries over blind buying of the same side: same resolution ladder **-$322** (t -1.06), same market at a random confirmable time -$1,470 (t -1.69), same period +$250 (t 0.75). Tune period: +$85 to +$183, t 0.4-0.6. If the model were exactly right the 43 entries would be worth +$40; they made +$694. At least nine tenths of the figure is the price path. |
| 5 | medium | Concentration. Ten markets make $737 of the $694.5; three entries make $453.5. | Without the best ten markets: 29 entries, -$42.1 (t -0.52). Without the best resolution date: +$379.5 (t 1.81). Clustered by resolution date with BTC and ETH together: t 1.90; by entry day: t 1.76. |
| 6 | medium | The rule does not check that the gap still exists at the entry bucket. Only 14 of the 43 report entries still had a gap of 0.05 at t + 300; the 29 others carry $416. One entry buys YES at 0.774 with the model at 0.571. Mean model edge at the entry price (model value at the signal bucket) is 2.3 cents a share, less than half the threshold. | Most confirmed entries are not trades on a 5-point gap. Among paper entries 44-48% of gaps are gone one bucket later. |
| 7 | medium | Deribit check (c) does not carry the weight put on it. The model there uses Binance BTCUSDT as the forward for options that settle on the USD index; NOTES.md warns about this basis (live today: Binance $51 above the Deribit index). The signature is in the analyst's own data: near-the-money implied vol / DVOL is 1.00 from calls and 1.20 from puts. The agreement in the outer buckets (option digital above the model at 0-0.1, below at 0.9-1) is what clipping a noisy spread estimate to [0, 1] produces. | With the forward lowered by $51-73 the option digital sits 4.2-5.0 points above the lognormal model in the 0.3-0.7 bucket (analyst: 2.6; all 10 expiries have the same sign), while Polymarket is 1.4 points above it. So at one-day horizons Polymarket is about 3 points below the option digital near the money. "The systematic gap is model error" is not established, and "2-3 points, not 5-6" is a distance to a flat-vol model, not to option prices. The pooled vol ratio of 1.10 survives the correction. No effect on any PnL figure. |
| 8 | low | `volumeNum` is shares, not dollars (tape shares equal it in every market). The "volume >= $5K" universe contains 104 markets of 532 with under $5,000 of turnover, 50 under $2,000. The filter also uses final volume, unknown at entry time; 132 of 682 daily markets were dropped by it (105 of them ETH). | Headline: 1 of the 34 confirmed markets is under $5,000; without it 42 entries, +$675.8. The universe description in results.md is wrong by a factor of about 2.4 in dollars. |
| 9 | low | Fee rate before 20 Nov is assumed. | At most -$18 on the report figure. |
| 10 | low | One-touch: 5 signals are dropped because the entry bucket fell after the barrier was hit. | -$58 on the tune period had they been entered. The one-touch conclusion is unchanged. |

## Corrected numbers

Tuned variant (g 0.05, 48 h-7 d), reporting period, DVOL model:

| version | entries | PnL | t | per day |
|---|---|---|---|---|
| analyst, tape-confirmed | 43 | +$694.5 | 2.08 | +$63 |
| size capped at the tape | 43 ($480 staked) | +$164.4 | 1.88 | +$15 |
| print after the entry-price bucket, 5 min | 13 | +$43.9 | 0.41 | +$4 |
| print after the entry-price bucket, 10 min | 28 | +$153.4 | 1.08 | +$14 |
| same, size capped | 28 ($283 staked) | +$4.9 | 0.17 | $0 |
| entries after the tune period ended | 25 | +$47.2 | 0.43 | +$4 |
| same, size capped | 25 ($256 staked) | -$19.5 | -0.44 | -$2 |
| excess over blind NO/YES of the same ladder | 43 | -$322 | -1.06 | - |
| without the best ten markets | 29 | -$42.1 | -0.52 | - |

Under the stricter fill evidence (prints after the entry-price bucket, 10 min) no variant of the nine has t above
1.7 in the reporting period, and the only significant cells are negative ones at 2-12 h (g 0.05 tune -$234, t -3.2;
g 0.08 report -$133, t -2.7).

## What stands

- The descriptive results: gap to the DVOL model of 2-3 points on active strikes, autocorrelation and decay, the
  market closing the gap rather than spot, 77% of entries without a print at the assumed price in 10 minutes (93% at
  48 h-7 d).
- The analyst's own caveats were right and are understated. The paper result is not real; the confirmed result is
  a short position in a falling month.
- One thing in the other direction, measured by me and not pre-registered: over all 473 confirmed entries the mid
  moved toward the model, net of the model's own move, by 1.7 cents a share after 12 h (308 entries still open,
  t 3.4) and 2.5 cents after 24 h (207 entries, t 3.8). For the 43 tuned entries it is -0.7 cents after 1 h and +0.6 after 24 h. It is an exit at the mid,
  which is not executable, and it is smaller than the 1-cent entry concession plus an exit spread. It supports the
  analyst's maker idea more than any taker rule.

## Not checked

- Books. Like the analyst, I only have prints; a print proves someone else took that liquidity.
- ETH options, and any option data other than the analyst's cached trade candles.
- The realised-vol secondary run beyond the shared entry and confirmation code path, which I rebuilt for the
  primary and one-touch runs only.
- Fee charges before 20 Nov from a real wallet.
