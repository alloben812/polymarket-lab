# Audit: predicting tennis walkovers hours ahead (studies/gaps/tennis_walkover_prediction)

Auditor: independent agent, fresh context, 2026-11-27. Read: AGENTS.md "Правила исследования", NOTES.md,
`docs/audit-checklist.md`, `protocol.md`, `results.md`, `s1_build.py`, `s2_analyse.py`, `s3_diag.py`, `out/s3_diag.txt`.
Did not edit results.md or protocol.md. Own code in `audit/` (a1..a5): it reads only `data/gaps_tennis_wo/universe.json`
and the raw tapes `data/tape/*.jsonl.gz`; it does not import the author's scripts. Run with `python3 -I audit/aN_*.py`
(a few seconds each, no network).

## Verdict: HOLDS (negative result stands)

I found no wrong sign, join, time zone, double-counted fee or impossible fill rule. The key number reproduces from raw
data. The structural argument (extra value q x (0.5 - p) against fee 0.05 x p x (1 - p) at the same prices) holds in
every entry window I tried; the one window where it comes out level is not profitable and cannot be tested with
50-100 USD. Caveats below are things the study did not run, none of them changes "nothing to test here".

## Recomputed key number (a1)

Underdog buyable at 0.05-0.45 by the first print in [T-6h, T-1h], match time = block time - 3 s, BUY of X at p or SELL
of the other outcome at 1 - p, class A weight 1, control weight 8, fee 0.05 x p x (1 - p):

| quantity | author | audit |
|---|---|---|
| trades / walkovers / weighted matches | 1,089 / 153 / 7,641 | 1,089 / 153 / 7,641 |
| walkover rate | 2.0% | 2.00% |
| premium q x (0.5 - p) | +0.42 c/share | +0.424 c |
| taker fee | 0.99 c | 0.992 c |
| premium minus fee | -0.57 c | -0.567 c |
| blind net edge | -1.71 c | -1.69 c (the 0.02 c is tie-breaking of equal-second prints) |

Same for the cheap band and per-flag bound printed in `out/s3_diag.txt`: band 0.05-0.15 reproduces as q 2.0%,
premium +0.82 c vs fee 0.46 c.

## What I checked

- **Sign and join.** Payoff is the final price of the bought outcome, joined by outcome name; underdogs lose slightly
  more than their price in played matches (controls only: -1.15 c [-3.96, +1.66]), so no sign inversion. A walkover
  pays 0.5, premium (0.5 - p) is positive for p < 0.5. Correct.
- **Time zone.** `gameStartTime` equals the event `startTime` for 830 of 830 walkovers and 2,734 of 2,734 controls
  (a4), all parsed as UTC. No offset asymmetry between classes. Closed-minus-start differs a lot (walkovers resolve
  late) but only start and print times enter the trade.
- **Fee.** Counted once, rate 0.05 as in gamma `feeSchedule` on all 33,300 moneylines and as implied from real
  charges in the earlier tennis study. Even at 0.03 the bound stays negative (premium - fee -0.17 c, net -1.30 c).
- **Fill rule.** Not too strict: widening the price band to 0.02-0.499 changes q to 2.0% and the bound to -0.61 c;
  shifting the window to T-12h..T-1h, T-3h..T-0.5h, T-1h..T gives q 1.6-2.1% and premium - fee -0.54 to -0.63 c.
  Walkovers are not hidden by the 1-6 h window: the rate does not rise towards the start.
- **Selection of the sample.** 82% of the walkovers (677 of 830) have no tradable underdog print in the window
  (267 no tape, 62 no print before the start, 348 no print at 0.05-0.45). The control side is filtered by the same
  rule, so the 2.0% is like against like. Class A has tapes for 563 of 830, controls for 2,734 of 2,734 (controls
  were chosen with volume); an untraded market cannot be bought, so this is not a bias.
- **Variants the protocol promised.** V0, 7 screens, S1, S2, maker scenarios were all run and reported; the decision
  rule was applied as written (fails: late CI contains 0, S1 late n=30, walkovers 7).

## Things not run (do not change the verdict)

1. **Earlier entry (T-24h and before) was never measured.** Post-hoc, exploratory, one of 7 windows I looked at (a3):
   first print in [T-48h, T-24h]: 259 trades, 91 walkovers, q 6.3%, premium - fee +0.06 c per share (level, not
   positive), net edge +3.83 c [-2.42, +10.08], t +1.2 (early part +3.1 c, late +5.1 c, both CIs contain 0). Windows
   T-24h..T-6h: q 2.2%, premium - fee -0.62 c. The +3.8 c is played-match noise (underdog win - p in that window is
   +4.0 c [-2.7, +10.7], n=168); a fairly priced underdog earns about nothing. About 117 weighted matches a week, median
   first print 10 shares, average p 0.32. A 50-100 USD test would give 10-20 trades and cannot tell +0.06 c from -3 c.
2. **Cheap underdogs 0.05-0.15** (author's own "idea, not tested"): outcome-free bound is +0.36 c per share
   (140 trades, 20 walkovers), i.e. cents per trade at 5 USD, about 80 weighted trades a week in the whole market;
   measured net -0.93 c with a CI of several cents. Not a test candidate; it would need thousands of trades.
3. **Maker side in earlier windows**, and **`tennis_completed_match` "No"** (pays on a walkover and a retirement): not
   priced from tapes. Neither is tested here. The maker line shows adverse selection already in the 1-6 h window
   (walkover rate among filled bids about 1%).
4. External match data are still unreachable: raw.githubusercontent Sackmann `atp/wta_matches_2025.csv` 404 and
   tennis-data.co.uk 403 (rechecked today, one request each). Round, ranking, medical timeouts stay missing; the flags
   cannot reach the 2.5x lift (needed 5.0% vs best 3.2-3.7% early). One small inaccuracy in the headline: doubles in
   the late part shows 4.9% (7 of 24), but it needs 7.6% there and has n=24.

## Corrected headline

Same as the author's: among underdogs buyable 1-6 h before the start, 153 of 7,641 weighted matches (2.0%) end as a
walkover, the extra value is +0.42 c/share against a 0.99 c fee, so a blind or flagged buy loses about 0.57 c/share
before noise; break-even needs about 5%. Not examined: entries more than 24 h before the start (q 6.3% but only level
with the fee, 259 trades) and external match data. Nothing to test live.
