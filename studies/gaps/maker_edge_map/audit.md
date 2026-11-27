# Audit: maker_edge_map (independent, fresh context, 2026-11-27)

## Verdict: HOLDS for the crypto up/down result; WEAKENED for the wording of the headline and for "no other family pays"

The sign and size of the main negative result reproduce from the raw tapes with independent code and survive every
quote-policy variant I tried. I found no wrong sign, wrong join, time-zone error or double-counted fee. Two things are
overstated and one thing is under-powered (below). None of them turns the verdict into "there is a maker edge".

## What I recomputed (my own code: `audit/recompute.py`, stdlib only, written from protocol.md, not from analyze.py)

V2 touch-maker, conservative (strict-through), c/share, 95% CI clustered by market. Mine vs the author's `out/V2_family.csv`
and `out/attack.md` table E:

| family, sample | metric | mine | author |
|---|---|---|---|
| btc-5m early, 25 mkts, 674 fills | final / m30 / m300 | -2.50 / -2.16 / -2.72 | -2.50 / -2.16 / -2.72 |
| btc-5m late, 25 mkts, 702 fills | final / m30 / m300 | -2.96 / -2.57 / -2.50 | -2.96 / -2.57 / -2.50 |
| btc-5m late, 100 mkts, 2,683 fills | final / m30 / m300 | -3.83 / -2.30 / -3.75 | -3.83 / -2.30 / -3.75 |
| btc-5m early, 100 mkts, 2,712 fills | final / m30 | -1.14 / -1.13 | -1.14 / -1.13 |
| btc-15m, alt-updown, crypto-updown-long, both halves, 100 mkts | final / m30 / m300 | identical to 2 decimals in all 12 cells | |

CIs match too (btc-5m late m30 -2.57 +- 0.88). Fill counts match exactly for V2. Direction, payout order
(`outcomePrices[0]` = `outcomes[0]`), token mapping of a maker sale of token0 as a purchase of token1 at 1-x, closedTime
parsing (UTC), the 3 s block lag, the 2-10 s window and the strict inequality are all correct as implemented.
Fees: every sampled market has `feeSchedule.takerOnly = true`, so no maker fee exists to count twice or to omit.

## Robustness runs the author did not do (variants of the fill/quote rule, on the 100+100 extension, `audit/variants_*.txt`)

All reported on crypto up/down, 4 families x both halves. 64 + 24 runs, all listed in the files.

- Quote 1, 2, 4 ticks further from the last print (so only bigger moves fill): m30 stays between -0.9 and -3.7 c/share in
  every cell; final -1.0 to -4.0. No cell turns positive.
- "At price" fills allowed (my version of V2o): btc-5m m30 -0.67 (early, CI -1.6..+0.3) and -1.44 (late); btc-15m -1.12 /
  -1.40; alt coins -2.17 / -2.99; hourly+ -0.45 / -0.76. Final markout btc-5m early -0.70 +- 1.85, alt early +0.35 +- 4.43
  (CIs include zero in these two cells, never above it).
- Quiet-market filter (skip the quote if the mid moved more than 1 or 3 cents in the previous 30 s, past data only):
  best case btc-5m, at-price, 1 c: m30 -0.16 +- 0.55 early, -0.56 +- 0.60 late. About zero at best, not positive.
- Price-bucket screen of V2 on the 75 markets per half that the protocol never saw (`audit/pbscan.py`): the only
  both-halves-positive bucket in the protocol sample (btc-5m 0.60-0.80, final +1.9 / +3.9) does not replicate on new
  markets (-4.2 +- 7.3). m30 of V2 is negative (point estimate) in 40 of 40 up/down family x bucket x sample cells (many CIs include zero).

Conclusion: a seconds-reaction maker that quotes every window blindly is not paid in crypto up/down. The 5-minute BTC
book as a whole (V1) is flat (+0.02 / +0.46), so there is nothing to copy either.

## Findings

1. **Headline overstates "CIs below zero for both halves" (low).** BTC 5m early V2 m30 is -1.13 +- 1.26 c/share (CI
   -2.39..+0.13), and final -1.14 +- 2.20; alt-coin early final -1.08 +- 4.17. Pooled over both halves BTC 5m m30 is about
   -1.7 +- 0.75, so the sign claim stands; the "both halves" wording should say "all but BTC 5m early at 30 s". Under the
   optimistic V2o the BTC 5m early cell is -0.57 +- 0.84 (includes zero). Correct headline: BTC 5m maker is "not paid and
   probably picked off" (-1.1 to -3.8 c), the other crypto up/down families are clearly picked off (-0.9 to -3.8).
2. **The V2 rule is pessimistic by construction (medium, direction known).** A fill needs a print strictly through the
   limit, and the mark is the mid of the last two prints, so the post-fill mid is below the fill price mechanically
   before any information effect (it is real adverse selection, but it excludes the at-touch queue fills that most real
   maker fills are). The author brackets this with V2o; my at-price runs confirm the bracket is still <= 0 in crypto.
   The headline numbers (-0.9 to -3.8) are therefore the low end; the honest range for a newcomer is about -0.2 to -3.8
   c/share at 30 s, none positive. V2o in my reimplementation has 10-13% fewer fills than `analyze.py` (e.g. BTC 5m late
   3,561 vs 4,030; per-market diffs are +-1..2 fills at tolerance edges, see `audit/dbg2.py`); means differ by 0.1 c.
   Not investigated further; V2o cannot promote a cell.
3. **"No family pays" outside crypto is under-powered, not demonstrated (medium).** V2 final markout CIs on 100 markets
   per half are +-2 to +-16 c/share (weather +-5.4 / +-1.8, culture +-4.3 / +-2.6, sports +-15 / +-4.4, finance +-11 / +-2).
   Two things look positive and are filed as "unclear": weather (V1 m30 +1.19 / +1.11 and m300 +0.56 / +0.60 c/share, CIs
   above zero in both halves; V2 m30 +0.72 / +0.69, CI above zero both halves, but V2 m300 -0.60 / -0.16 and final
   +1.76 / -1.84, noisy) and mentions (V2 m30 +19.1 / +16.8 c on 3 and 9 markets, 13 and 38 fills; final late -0.95).
   The study itself says the mid is stale in thin markets and flatters the 30 s mark; no freshness cut was run to separate
   that from earned half-spread. Weather has ~320 markets a day (about 2,200 in the week) and was sampled at 100 per half.
4. **Decision-rule bookkeeping (low).** Under the frozen rule the live test would have gone to the passing cell with the
   most fills/day, i.e. crypto-other 0.95+ (+51 $/day), not post-counts. The author killed it post hoc on 66 new markets
   (-0.87 +- 4.48) and says so; that is a legitimate attack, but the "Live micro-test" section picks a different cell
   (post-counts 0.95+, the smallest of the three by protocol scaling) on a post-hoc basis. It is labelled "mechanics only",
   which is honest. Note the post-count cell is 10 events with zero losses; the 95% bound on event loss rate (28%) against
   a 2.6% break-even means it is untestable in 2-4 weeks, as the author writes.
5. **Not an issue, checked:** look-ahead (decision at tau uses prints with match time <= tau; window starts tau+2),
   survivorship (74 open markets, none crypto up/down), tape completeness (no cap hit, 0 failed), tick 0.001 markets
   handled by the tick rounding line, the V1 maker side/sign, UTC weekend flag, split rule (fixed sha1 order, half by
   endDate). closedTime after endDate by ~23 s for 5m markets: fills in that gap would bias V2 up, not down.

## What should be re-run (to remove the WEAKENED part)

- Weather, culture, sports, mentions, finance: all resolved markets of the week (tapes are cached per market; rerun
  `analyze.py` on a larger sample) with event-level clustering, plus a cut with a fresh mid (last bid-side and ask-side
  print both < 60 s old). Only if V2 m300 and final CIs lie above zero in both halves is there a cell worth a live test.
- Liquidity-reward and maker-rebate income (`rebateRate` 0.20-0.25 of taker fees exists in `feeSchedule`) is outside
  the study; the project rule sets rebates to 0 for a new account, so I did not add it.

## Needed to trade live

Nothing from this study. For a 50-100 USD test the only defensible items are mechanics checks (fill rate of a resting
post-only order against the tape model); no maker rule here has a demonstrated positive expectation.

Files: `audit/recompute.py`, `audit/pbscan.py`, `audit/dbg2.py`, `audit/variants_updown.txt`, `audit/variants_volfilter.txt`.
