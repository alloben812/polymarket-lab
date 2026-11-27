# Audit: resolution bonds (buying the 0.95-0.98 favourite shortly before resolution)

Auditor: independent agent, fresh context, 2026-11-27. Sources read: `docs/audit-checklist.md`, AGENTS.md
"Правила исследования", NOTES.md (fees, data-api, up/down mechanics), `protocol.md`, `results.md`, scripts s1-s10,
`out/*`. Raw data: `data/gaps_resolution_bonds/` (universe, sample, resolutions, 5-min price histories, tapes; file
times 2026-11-27 16:33-18:46 UTC). New data fetched by the audit: `data/gaps_resolution_bonds/audit_1h/` (430 hourly
BTC/ETH Up/Down markets of 18-26 Nov with their tapes, plus tapes of 32 crypto markets that had no entry). Audit code:
`audit/a1`-`a9` (own parsing, trigger, payoff mapping and clustered t; no study function is imported).

## Verdict: WEAKENED

- **The pre-registered result holds** and reproduces to the last digit: the claim as registered loses after fees.
- **The post-hoc crypto result, the basis for the proposed live test, does not hold for the markets the test
  would trade.** Two-thirds of its 429 trades are hourly Bitcoin Up/Down markets, and that series is tested only up
  to 17 Nov. From 18 Nov the hourly markets are named `btc-updown-1h-<epoch>`, and the study's own `-updown-`
  filter dropped them (one hourly market from 18 Nov in the whole universe). On those markets (18-26 Nov, 430
  BTC+ETH markets) the same rule gives **150 trades, 6 lost (4.0%, Wilson 1.8-8.5%), break-even 3.4%, -0.06 USD
  per 10 USD (t -0.4)**. A rule closer to a live program, which triggers on the tape instead of 5-minute snapshots,
  gives **327 trades, 12 lost (3.7%), +0.03 USD per 10 USD (t +0.3)**: zero. In the study period the 5-minute
  trigger also misses losers: in 13 hourly markets takers bought the eventual loser at 0.95-0.98 in the last hour,
  but no 5-minute snapshot showed it in range.
- What remains is a weak post-hoc hypothesis on the daily crypto strike markets ("above X", "between X and Y",
  "dip to / reach X", daily Up/Down): 149 trades, 1 lost, +0.27 USD per 10 USD. These markets fall into only 66
  asset-day clusters, and the result loses about 40% with one tick of slippage.

## Corrected headline

Buying the 0.95-0.98 favourite in the last hour loses after fees in the pre-registered test. Late period -2.30 c per
share at the mid (577 markets, 450 events, t -2.3), C-cons -2.08 (t -2.1). Early period -1.48 c (1,321). Sports
-2.35 c late (523), weather -19 c (13). Reproduced exactly.

The post-hoc crypto result (+0.23 USD per 10 USD, 429 markets, 5 lost) reproduces on its own data, but it fails out
of sample on the hourly Up/Down markets that replaced the tested series on 18 Nov: 150 trades, 6 lost, -0.06 per
10 USD (t -0.4). A tape-triggered version gives 327 trades, 12 lost, +0.03 (t +0.3). One candidate is left, and it
is post hoc: the daily crypto strike markets, 149 trades, 1 lost, +0.27 per 10 USD before slippage, 66 independent
asset-days, about 4 trades a day.

## Independent reproduction (checklist item 6)

`python3 -I audit/a1_recompute.py` (all 4,424 analysed sample markets and all 3,796 extension markets; that is the
full sample, not a quarter):

| row | markets | events | lost | net c/share | t (event) | author |
|---|---|---|---|---|---|---|
| ALL late C-mid | 577 | 450 | 34 | -2.30 | -2.3 | -2.30, t -2.3 |
| ALL late C-cons | 577 | 450 | 34 | -2.08 | -2.1 | -2.08 |
| ALL early C-mid | 1,321 | 987 | 68 | -1.48 | -2.3 | -1.48 |
| sports late | 523 | 400 | 31 | -2.35 | -2.2 | -2.35 |
| weather late / early | 13 / 45 | | 3 / 7 | -19.00 / -11.85 | -1.6 / -2.2 | same |
| crypto late / politics late | 15 / 21 | | 0 / 0 | +3.30 / +4.01 | | same |
| ext crypto early / late | 376 / 138 | | 4 / 1 | +2.50 / +2.79 | +4.7 / +3.8 | same |
| ext politics late | 132 | 80 | 5 | +0.05 | +0.0 | same |

`audit/a2_crypto_tape.py` (own tape reading): 10 s variant **429 markets, 5 lost (1.17%, Wilson 0.5-2.7%),
break-even 3.36%, +0.227 USD per 10 USD, t 4.2 by event, 4.4 by day**. The 60 s variant (387, +0.244) and the 300 s
variant (247, +0.211) also match. The payoffs agree with gamma `outcomePrices` in every market. They also agree
with Binance 1-hour candles (open against close) in **659 of 659** hourly Up/Down markets before 18 Nov
(`audit/a5_binance_check.py`).

## Checklist

**1. Look-ahead.** Clean for the trigger. The 5-minute bucket at t is a snapshot at t: the median absolute gap
between the bucket and the tape's implied price is 0.005 in [t-60, t), 0.005 in [t, t+60), 0.015 in [t+60, t+180)
and 0.021 in [t+240, t+300), over 337 crypto markets (`a6`). The buy is a print at least 10 s after t. Using
`match = block - 3 s` (require block >= t+13) gives 421 markets, +0.226: no change. The leak in s6 (C-tape used
prints from before the entry, with the later choice of favourite) is real and was found by the author: the
early in-sample crypto tape figure drops from +2.17 to +0.66 c with it removed. The verdict does not use s6.
The universe selection on final volume >= 10,000 USD is look-ahead (see 5).

**2. Execution.** The fills are optimistic, and the margin is exactly the size of the slippage.
- The buy price is the price another taker paid. In 66% of the first prints, no other wallet bought at that price
  or lower in the next 30 s (`a6`). Whether a second 10 USD order would have filled there is unknown.
- **+1 tick (0.01) on the print price: +0.124 USD per 10 USD (t 2.3). +2 ticks: +0.022 (t 0.4)** (`a2`). The
  whole edge is 1-2 ticks.
- The trigger runs on 5-minute snapshots, but the live rule watches the book every 5-10 s, and the two do not take
  the same markets. In 13 hourly markets of the study period, the eventual loser was bought by takers at 0.95-0.98
  in the last hour (3-760 USD each), yet no snapshot showed it in range, so the backtest never entered (`a8`). A
  live poller would likely have entered several of them. Each such loss costs about 10 USD, against +0.35 per
  winning trade. The extra winners a poller would also catch were not measured for the study period. Measured
  out of sample instead (`a9`): the tape-triggered rule gives +0.03 per 10 USD on 327 trades.
- Size: one 10 USD trade per market, so capacity is not the problem. 391 of 429 first prints were at least
  10 USD themselves (that subset gives +0.264).
- The median delay from trigger to first qualifying print is 40 s (p90 445 s). The live rule says "give up if the
  ask leaves the range". With the print required within 60 s: 255 trades, +0.228. Within 300 s: 369, +0.209.
  Neither changes the result.

**3. Fees and accounting.** The crypto rate is 0.01 for all 576 entries. It is unchanged across the 20 Nov fee
change per NOTES.md, and the gamma `feeSchedule` of the out-of-sample hourly markets is 0.01 in all 430. Checked by
hand: at p = 0.966 the fee is 0.01 x 0.966 x 0.034 = 0.033 c, and net per 10 USD on a win is 10 x (1 - 0.96633) /
0.96633 = +0.348. That matches a2's mean win of +0.348 and mean loss of -10.00. The payoff direction was checked
against Binance (above). No 50-50 resolutions occur among crypto entries. Fees before 21 Nov in weather, economics
and mentions were higher than the rate applied, as the author flags, which makes the weather loss slightly
understated. The headline is not affected.

**4. Statistics.**
- Clustering: by event and by day (36 clusters), t 4.2 and 4.4. Reproduced.
- Time split: the crypto result was chosen after looking at the sample (post hoc, as stated). The "late period"
  test (109 trades) shares the 13-17 Nov hourly series with nothing out of sample. Only 38 of the 109 late trades
  are after 18 Nov, and 1 of those is hourly.
- Composition: the 5 losses are all hourly or daily Bitcoin Up/Down. Hourly Up/Down: 280 trades, 4 lost (1.43%,
  Wilson 0.6-3.6%, upper bound above the 3.38% break-even), +0.20 (t 2.7). Non-hourly: 149 trades, 1 lost, +0.27
  (t 3.9), but these fall into only **66 asset-day clusters**, because strikes of one asset on one day share a
  price path. The t values of 26-28 in the zero-loss sub-types are not evidence.
- Robustness: without the best day, +0.221 on 411 trades. Without the 10 best markets, +0.220. The worst day is
  -7.9 USD. The figure does not depend on a few winners. It depends on the loss rate (one loss = 29 wins).
- Variants: 13 trading-rule variants (3 registered, 10 post hoc), 7 splits and 6 diagnostics are reported. That
  count is honest. Crypto was the only positive family out of 8, and the delay variants and the extension were
  chosen after seeing it.
- **Out of sample on the live target (`a7`, `a9`)**: btc/eth-updown-1h, 18-26 Nov, no volume filter, the same rule:
  150 trades, 6 lost, -0.061 per 10 USD (t -0.4). BTC 74 trades, 4 lost, -0.21. ETH 76 trades, 2 lost, +0.09.
  With the study's volume filter (>= 10k): 58 trades, 4 lost, -0.37. With the tape trigger: 327 trades, 12 lost,
  +0.028 (t 0.3). The study's own split: weekend 35 trades, 0 lost (tape trigger: 74 trades, 1 lost, +0.28, t
  2.0), weekday 115 trades, 6 lost. This is one split of many, and it is not evidence of a weekend edge.

**5. Data.** There are no download errors, no capped tapes (0 of 576 crypto), no duplicates, and resolution matches
are complete. Two population problems:
- Hourly Up/Down was renamed on 18 Nov (`bitcoin-up-or-down-...-et` became `btc-updown-1h-<epoch>`, confirmed on
  gamma for 20 Nov). The universe filter (`-updown-` excluded, meant for 5m/15m) therefore removed every hourly
  market after 17 Nov. `a3`: hourly markets in the universe per endDate day run at 15-26 a day until 11-17, and
  there is 1 on 11-18. The results text calls this "a regime change with 38 markets after 18 Nov". In fact,
  almost all of those 38 are daily strike markets.
- The volume filter is binding. BTC hourly is 18-25 of 24 a day. ETH, SOL and XRP hourly are almost all excluded
  (11 ETH hourly in the universe). The live test proposes "BTC, ETH, SOL, XRP, no volume filter", which is a
  population the study never tested.

**Protocol timing and deviations.** `protocol.md` was saved at 16:27:25 UTC. The listing data is from 16:33,
resolutions from 16:37 and price histories from 17:09. There is no git history, so this rests on file times only.
The protocol was followed: the s6 crash fix is cosmetic, and the C-tape leak is a weakness of the protocol's own
rule 18, which the author disclosed. The verdict rule was applied correctly: NO EDGE for all families, and crypto
and politics INCONCLUSIVE. Every positive crypto claim is post hoc and labelled as such.

## What an account of about 200 EUR could earn

- Hourly crypto Up/Down (most of the claimed opportunities): **about 0 USD a day**. Out of sample: -0.06 to +0.03
  per 10 USD trade, about 15-35 trades a day for BTC+ETH, and a loss of about 10 USD every 25-30 trades.
- Daily crypto strike markets (above / between / dip / reach): about 4 trades a day. At 20 USD a trade and +2.7%
  before slippage, that is about 2 USD a day. With one tick of slippage it is about 1 USD a day, and it is 0 or
  negative if the loss rate is 3% or more instead of the 0.7% seen (1 loss in 149). **Realistic: 0 to 2 USD a day.**

## Would the proposed live micro-test measure the claimed effect?

Partly, and on the wrong population. It would trade mostly `btc-updown-1h` markets, where the effect is already
absent out of sample (6 of 150 lost). Its stop rule ("4th loss in the first 100") would probably fire, and that
would be the correct outcome. It would also correctly measure fill price against the tape, which is the open
question for the daily strike markets. If a test is run at all, it should be restricted to the daily strike markets:
the same rule, 10 USD, logging the ask, the size at the ask and the fill. Even then, telling a 1% loss rate from a
3.4% one takes about 300 trades, which is about 10-11 weeks at 4 a day. For the hourly Up/Down markets: nothing to
test here.

## To trade this live you would need

- A real reason that the loss rate is below about 3%, beyond 36 days of history: for example, a fair-value check of
  the spot price's distance to the strike against the time left and volatility, which the author lists as an idea.
- Evidence that a 10 USD taker order sent a few seconds after the trigger fills at the printed price, not one or
  two ticks worse, because those ticks are the whole margin.
- The test restricted to the daily strike markets, about 300 logged trades, and the acceptance that the expected
  result is about 1-2 USD a day even if it works.

## Checked and clean

- Claim numbers, both periods, all families (exact).
- The payoff mapping (gamma and Binance, 659 of 659).
- Fee formula and rate.
- Trigger timing: the bucket is a snapshot at t.
- Block-time offset.
- No capped tapes and no download errors.
- Clustering by event and by day.
- Without the best day and without the top 10 markets.
- The disclosed number of variants.
- Protocol written before the data (by file time).
