# Audit: pair_accumulation (independent, fresh context, 2026-11-27)

## Verdict: HOLDS

The negative result stands. I found no wrong sign, join, time zone or double-counted fee, and no fill rule so strict
that it hides a positive result. I reproduced the headline numbers to the cent with new code. Nothing to re-run for
the stated question. The caveats below are limits of scope, not errors.

## What I recomputed (own code, `audit/recompute.py`, no pmlab imports, raw tapes and gamma JSON only)

Headline: pooled net per window at $10 per leg, conservative fills (first print strictly through L inside
[t0, t1), match time = block time - 3 s, placement skip if the ask was at or below L in the 30 s before t0), all 7,200
markets of the 12 series, standard errors clustered by UTC hour.

| L | mine: net per window (t) | author: net per window (t) | mine: early / late | author: early / late |
|---|---|---|---|---|
| 0.45 | -1.306 (-12.3) | -1.31 (-12.3) | -1.460 / -0.996 | -1.46 / -1.00 |
| 0.40 | -1.328 (-10.6) | -1.33 (-10.6) | -1.395 / -1.194 | -1.40 / -1.19 |
| 0.30 | -1.456 (-8.2) | -1.46 (-8.2) | -1.585 / -1.199 | -1.59 / -1.20 |
| 0.05 | -3.739 (-8.1) | -3.74 (-8.1) | -3.477 / -4.263 | -3.48 / -4.26 |

The touch (optimistic) scenario also matches: -1.141 / -1.105 / -1.057 / -2.401 against the author's -1.14 / -1.11 /
-1.06 / -2.40. Filled legs at 0.45: 8,660, and they won 40.1% against 45% paid (-4.9 c a share). The mechanism is
adverse selection on the fill, as claimed.

## Stress variants I ran (`audit/recompute_out.txt`; pooled net per window at 0.45 / 0.40 / 0.30 / 0.05, all negative)

- Block lag 0 s: -1.32 / -1.33 / -1.47 / -3.76. Block lag 6 s: -1.32 / -1.32 / -1.41 / -3.74. The sign does not depend
  on the 3 s clock assumption.
- No placement skip: -1.97 / -1.67 / -1.52 / -3.74. The skip does not hide a positive result. It removes the worst
  legs. Note that without it the 0.45 loss is larger.
- Touch fills with no skip and lag 0 (most generous combination): -1.72 / -1.36 / -1.10 / -2.42 (t -17 to -4.7).
- Early and late halves are negative in every variant (late t between -2.6 and -9.5).
- By UTC day (`audit/byday_out.txt`), all six days negative at all four levels. Sat 21 Nov: -2.14 at 0.45. Sun 22 Nov:
  -1.41. Mon to Thu: -0.95 to -1.15.

## Variants the protocol did not run (post-hoc and exploratory, `audit/extend.py`, `audit/extend_out.txt`)

The claim C2 quotes pair costs of 0.946-0.98, i.e. 0.47-0.49 per leg, which is nearer the mid than the four study
levels. I ran 0.49, 0.48, 0.47, 0.46, 0.35, 0.20 and 0.10 with the same rules (7 extra levels, counted). All are
negative in the conservative and the touch scenario, in 5m, 15m and 1h separately:
- Conservative, pooled: -1.17 (0.49), -1.20 (0.48), -1.23 (0.47), -1.26 (0.46), -1.37 (0.35), -2.09 (0.20),
  -3.40 (0.10); t between -8.4 and -12.0.
- Touch fills, pooled: -1.09 (0.49) to -2.21 (0.10).
- The loss per filled share is -5.9 c at 0.49 and falls to -3.5 c at 0.35. There is no level where it turns positive.
  Win rate of a filled leg stays 1 to 5 points below the price paid at every level.

## What I checked and found clean

- Time zone: T_START 1795219200 is 2026-11-21 00:00 UTC. The early/late split at 11-25 00:00 UTC is correct.
- Outcome sign: `up_won` is consistent with `final_price >= price_to_beat` in all 7,198 markets that carry both
  prices (the other 2 have no price fields). Up wins 49-51% in every series, with SOL and XRP 5m somewhat lower.
  Late prints near the window end agree with the outcome in all but one XRP 5m market.
- Fill-side mapping (`updown.sellable`): a taker SELL of X at p, or a taker BUY of the other outcome at 1-p, counts as
  a hit on X bids. I checked that this is what the unified Polymarket book does (a Down ask at q equals an Up bid at
  1-q). The strict "through" rule keeps it conservative even where a BUY of the complement was matched against a real
  ask.
- Fees: makers pay nothing, so the P&L is S x (won - L) and no taker fee enters. Gamma fee fields are 0.05 for
  BTC 5m/15m (2,304 markets) and 0.01 for the rest (4,896), as the study states. There is no double count.
- Data: all 7,200 markets are present and resolved, and every one has a tape. Only 5 markets (3 BTC 5m, 2 ETH 5m)
  have tape shares differing from gamma volume by more than 2%. There are 147,663 exact duplicate tape rows (same
  second, side, size, price and wallet). They look like multi-fill sweeps, and they cannot change a "first print
  through L" fill time. The tick is 0.01 in 139 1h markets and 0.001 elsewhere; this does not affect the fills.
- Look-ahead: the decision uses only t0, t1 and prints after placement. The placement check uses prints before t0
  only. There is no future information.
- Clustering by UTC hour and the pooled-by-hour treatment are reasonable. My clustered SEs agree with the author's.

## Caveats (scope limits, not errors; none changes the conclusion)

1. Six days, one weekend. The weekend question from the owner is answered only for Sat 21 and Sun 22 Nov (the two
   worst days). Only BTC 5m has a long history (the author's Sep-Nov grid, which I did not recompute).
2. Fixed-level resting orders only. Not tested: cancel-on-move, cancel after the first fill, re-quoting at the best
   bid, or resting before t0 (markets begin trading hours before t0, with prints near 0.50). The author lists the first
   three as ideas. They would need a new protocol and likely L2 data. Resting before t0 is one more variant that
   no study has run. With a stale-bid adverse-selection mechanism there is no reason to expect a sign change.
3. Tape fills cannot show queue position. Both scenarios bracket it, and both are negative.
4. The 1h cells have 144 markets and are noisy, but they are not close to the pass line.

## Live micro-test

Nothing to test here. A live test would only confirm a loss of about 10% of each filled leg (about -$1.1 per
window at $10 a leg). The level to avoid is anywhere from 0.05 to 0.49.

## Files

`audit/recompute.py` (main recomputation, output `recompute_out.txt`), `audit/extend.py` (`extend_out.txt`),
`audit/byday.py` (`byday_out.txt`), `audit/datachecks.py`. No background processes of mine remain.
