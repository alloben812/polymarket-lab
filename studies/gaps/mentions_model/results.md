# Mentions markets ("will X say Y during Z"): does a base-rate rule before the event beat the price? — results

Study run 2026-11-27. Protocol: `protocol.md` (saved before any outcome number, not edited after). Code:
`universe.py` (metadata), `fetch.py` (tapes), `analyze.py` (the protocol runs), `attack.py` (post-hoc diagnostics,
marked as such). Outputs: `out/results.txt`, `out/attack.txt`, `out/trades.json` (every simulated entry).
Raw data: `data/gaps_mentions_model/` (gamma events, universe), tapes in `data/mentions_tapes/`.

## Verdict: NOTHING TO TEST LIVE (both rules inconclusive under the frozen decision rule)

- **V1, "buy No on single-word markets priced 0.05-0.50 Yes, in the 24 h before the start"** (the lead of the earlier
  wallet study) is positive on the fresh early data and negative on the later data: +8.2% of stake
  [95% +3.1, +13.3] on Aug 1 - Sep 28 (665 trades, 144 events), **-2.4% [-10.2, +5.4] on Sep 29 - Nov 23**
  (508 trades, 99 events), pooled +3.6% [-1.0, +8.1] (1,173 trades, 243 events). It fails rule 1 (positive in both
  parts), rule 4 (without the 3 best events +2.3% [-2.2, +6.7]; at price +1 cent +2.1% [-2.4, +6.6]). By month:
  Aug +3.7%, Sep +11.7%, Oct -4.4%, Nov +1.5%. Not stable.
- **V2, "transcript frequency" (the same speaker's earlier resolutions of the same word, >= 3 priors, buy when the
  price is 15 points or more below that base rate)**: +9.2% [-20.3, +38.6] early (265 trades, 68 events), +16.4%
  [-13.7, +46.5] late (209 trades, 48 events), pooled +12.6% [-8.4, +33.6] (474 trades, 116 events). Positive in
  both parts but the interval is wide and it halves without the 3 best events (+4.4%) and at +1 cent (+8.1%). Its
  Yes leg loses (-4.0%, 220 trades); all of the result is the No leg (+26.5% [-1.0, +54.1], 254 trades) and in the
  early part one show (Big Brother, 18 events) is +$246 of the +$174 total. Fails rule 2.
- **Money, even if V1 were real:** about 10 entries a day, average stake about $12 (the tape rarely shows $20 at the
  rule's price), +$0.43 per trade pooled (+$0.14 at a $5 cap): **about $4 a day**. The category also shrank in
  November: about 400 markets a week in Aug-Oct, 96-153 a week in mid-late November (after the US midterms and the
  end of earnings season).
- **Weekends:** mentions markets do run on weekends (47 of 272 events, 723 of 4,215 markets, 17%, start on a UTC
  Saturday or Sunday: Big Brother, NFL broadcasts, MrBeast videos, some Trump events). Neither rule is positive there:
  V1 -3.1% [-12.3, +6.2] (192 trades, 41 events), V2 +1.7% [-48, +52] (104 trades, 29 events).
- **Seconds-scale time gap in this category:** not usable at a reaction time of a few seconds (earlier study, 131
  clean jumps: the first print after the word is already >= 0.90 in 57% of cases; all takers together locked in
  $5,485 below 0.95 in 8 weeks).

## Question

Markets of the kind "will person X say word Y during event Z" (gamma tag `mention-markets`, taker fee 0.01 since
21 Nov 2026, 0.04 before, zero 20-31 Oct). Is there a simple base-rate or transcript-frequency rule, run by a small
program before the event, that beats the price after fees? Who earns in the category and by what rule? How many
such markets run per week and what size is buyable at the rule's prices?

## Data

- Metadata and outcomes: gamma `/events/keyset?tag_slug=mention-markets&closed=true`, 1,392 events and 24,745
  markets, Jun 2024 - Nov 2026 (read 2026-11-27); 24,681 binary markets resolved exactly 0/1. Plus the 10 events
  still open (123 markets, 62 of them open now).
- Test sample (protocol): live and earnings events with a usable start time in 1 Aug - 27 Nov 2026: **4,215 markets
  in 272 events**, whole-market tapes for all 4,215 (2,530 from the cache, 1,685 fetched, 0 errors). Period events
  (weekly/monthly counts) are excluded. 24% of markets in the period had a start time that failed the validity test
  (start within 1 h of creation, or after the first market closed) and are excluded with their events.
- Segments by event start: S1 = 1 Aug - 28 Sep (fresh), S2 = 29 Sep - 23 Nov (the earlier study's window, where V1
  was found), S3 = 24-27 Nov. **S3 is empty**: no event that started on 24-27 Nov was both closed and had a valid start
  time when the data were read (the Thanksgiving pardon event has a start time equal to its creation time).
- Priors for V2: the whole 2024-2026 resolved universe (metadata only), only markets closed before the entry.

## What was run (4 protocol runs, plus post-hoc diagnostics)

1. V1: single-word markets (no "N+ times"), live/earnings; buy No at the first tape row in [start - 24 h,
   start - 5 min] that shows No buyable at 0.50-0.95; size min(row size, $20); fee 0.01; hold to resolution.
2. V2: key = (type, speaker, quoted terms, count N); base rate b = (k+1)/(n+2) over n >= 3 earlier resolved markets
   of the same key in other events; buy Yes at the first Yes-buyable row priced <= b - 0.15, or No at the first
   No-buyable row priced <= (1-b) - 0.15.
3-4. R-sens: V1 and V2 entries at price + 1 cent.

"Buyable" = a taker BUY of that outcome at that price, or a taker SELL of the other outcome at 1 - price (mirror
books); size never above the row's shares; match time = block time - 3 s. Clustering unit: the event.
Post-hoc diagnostics (`attack.py`, no rule or threshold changed): by speaker/show, by month, at the old 0.04 fee, by
entry price bucket. Nothing was re-run with different parameters.

## Headline numbers after fees (return on stake, 95% interval clustered by event)

| run | part | trades | events | won | mean price | stake | pnl | return | 95% | net/trade (<= $20) | net/trade ($5 cap) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| V1 | early S1 | 665 | 144 | 505 | 0.717 | $8,019 | +$656 | +8.18% | +3.11 .. +13.25 | +$0.99 | +$0.28 |
| V1 | late S2+S3 | 508 | 99 | 355 | 0.706 | $6,153 | -$149 | -2.42% | -10.22 .. +5.38 | -$0.29 | -$0.03 |
| V1 | pooled | 1,173 | 243 | 860 | 0.712 | $14,172 | +$507 | +3.58% | -0.97 .. +8.13 | +$0.43 | +$0.14 |
| V1 | pooled, without 3 best events | 1,173 | 240 | | | $13,754 | +$310 | +2.25% | -2.17 .. +6.68 | | |
| V1 | pooled at +1 c | 1,173 | 243 | | | $14,241 | +$297 | +2.08% | -2.38 .. +6.55 | +$0.25 | +$0.08 |
| V2 | early S1 | 265 | 68 | 66 | 0.240 | $1,904 | +$174 | +9.15% | -20.32 .. +38.62 | +$0.66 | +$0.15 |
| V2 | late S2+S3 | 209 | 48 | 71 | 0.288 | $1,713 | +$282 | +16.43% | -13.69 .. +46.54 | +$1.35 | +$1.04 |
| V2 | pooled | 474 | 116 | 137 | 0.261 | $3,617 | +$456 | +12.60% | -8.36 .. +33.55 | +$0.96 | +$0.54 |
| V2 | pooled, without 3 best events | 474 | 113 | | | $3,399 | +$150 | +4.40% | -15.51 .. +24.31 | | |
| V2 | pooled at +1 c | 474 | 116 | | | $3,728 | +$300 | +8.06% | -12.09 .. +28.20 | +$0.63 | +$0.37 |

Bootstrap of the total by event: V1 early +245 .. +1,080; V1 late -641 .. +319; V1 pooled -122 .. +1,146;
V2 pooled -300 .. +1,227.

Decision rule check: V1 fails 1 (late part negative) and 4; V2 passes 1 and 3, fails 2 (pooled lower bound -8.4%)
and is fragile on 4. Neither earns a live test.

Post-hoc (not used for the verdict): V1 by group, early / late: Trump +8.1% (28 events) / +0.5% (35); earnings calls
+7.4% (32) / +5.3% (35); NFL broadcast "game" markets +12.2% (12) / -35.7% (6). Earnings calls are the only group
positive in both parts and both intervals are wide (+-14 points). At the old 0.04 fee V1 early is +7.3%, late -3.3%:
the fee is not what decides it. V2 Yes entries under 0.20 lost heavily (98 trades, -$335; -101% at 0.00-0.10, -58% at 0.10-0.20): the base rate
says "said before", the price says "not this time", and the price was right.

## Opportunities, size and capacity

- Supply: about 300-470 mention markets in 25-38 events a week from August to the end of October, volume $250K-1.1M
  a week; then 185 (week 45), 153 (46), 109 (47), 38 (48, partial). Sample events by UTC weekday of start: Mon 28,
  Tue 48, Wed 66, Thu 47, Fri 36, Sat 21, Sun 26.
- V1 entries: about 10 a day (1,173 in 119 days); V2 about 4 a day.
- Size: the qualifying tape row showed a median of 20 shares (V1) / 27 shares (V2); only 40% (V1) / 14% (V2) of
  entries could take the full $20. All V1-qualifying rows of a market's 24-hour window add up to a median of $62.
  Average stake reached: $12 (V1), $7.6 (V2).
- Capacity for a ~200 EUR account: pooled V1 +$507 in 119 days = **about $4 a day**; V2 about $4 a day; with the
  November supply a quarter of that. Capital is tied for about 17 h to resolution plus the ~2 h resolution delay.
  Even taking every qualifying row (median $62 a market, about 10 markets a day) at the pooled +3.6% would be about
  $20 a day, and that number is not statistically different from zero.

## Reaction time needed

None worth mentioning for these rules: entries are a median 17 h (V1) and 14 h (V2) before the start, and a program
that polls once a minute would see the same prices. The seconds-scale part of the category (buying right after the
word) is a race the earlier study measured as already lost at the first print in most cases.

## Who earns in mentions and by what rule (from `studies/wallets/mentions/README.md` and its sceptic's check)

- oidocrop (0x23c4...9c42): listens to the event and checks the outcome itself, then buys the decided side at
  0.97-0.99 and holds 2-7 h: about +1.2% per turn, 4 wrong of 663 markets (the blind follower is wrong 4.2% of the
  time and loses). Positive in all three 45-day windows checked; verdict there WEAK on the explanation, real on profit.
- Faston (0xa7fe...3e75): many $30 pre-event Yes picks, SUPPORTED: +$1.2-2.0K per 45 days, its Yes picks +6.4% where
  blind Yes on the same events was -17.0%. What produces its picks is unknown.
- jkerkela: scheduled taker buying No a day ahead, +27% on 59 markets against +7.8% for blind No on the same
  events; two months old. Our V1 is the blind version of this account's rule: it shows a few percent at best and
  flips sign between periods, so whatever jkerkela adds is in the selection, not in "always buy No".
- QuantDeLaFugazi, BipBop, fast listeners: speed after the word pays tens to a few hundred dollars per 45 days.

## Live micro-test

Nothing here deserves a live micro-test. The frozen rule was not met by either variant, and even the best reading
(+3.6% pooled, about $0.40 a trade, $4 a day) would need several hundred trades to tell from noise: at a per-trade
standard deviation of $9.3 (1,173 V1 trades), telling +$0.43 from zero at 2 standard errors needs about 1,800
independent trades (more once trades in one event are treated as correlated), i.e. more than half a year at the
current supply, for an expected gain of about $800. V2: per-trade sd $15.9, about 1,100 trades for +$0.96.

## Limitations

- S3 (24-27 Nov, the only days under today's 0.01 fee) has no trades; every simulated price was formed under the
  0.04 fee (or zero on 20-31 Oct), so other traders' behaviour may differ now. Re-pricing at 0.04 does not change the
  sign of any segment.
- Event start comes from the gamma event `startTime`; 24% of markets in the period failed the validity check and
  are out. If the dropped events differ (e.g. ad-hoc remarks scheduled at short notice), the result does not cover them.
- Fills are tape rows: they prove the price was there, but someone else took that liquidity at that moment. Book
  depth is unknown; a real order a few seconds later may have met a worse price (the +1 c run covers part of this).
- "Transcript frequency" is approximated by Polymarket's own earlier resolutions of the same speaker and word, not
  by real transcripts; the speaker key is coarse ("trump" pools rallies, summits and pardons) and NFL broadcast keys
  are game-specific, so most of them have no priors. 1,609 of 4,215 markets had >= 3 priors.
- The universe is the `mention-markets` tag; mention-like markets without the tag (e.g. "will a turkey gobble")
  are not included. Earlier study noted some exist.
- 116-243 events over four months; intervals of +-5 (V1) and +-20 points (V2) per segment.

## Ideas, not tested

- Earnings-call No only (the one group positive in both parts post hoc, +7.4% / +5.3%, 67 events): needs its own
  protocol and fresh data; earnings season resumes in late January.
- V2 restricted to the No side (+26.5% post hoc, 254 trades): same, a new protocol on fresh data, ideally with
  real transcripts (factba.se for Trump, earnings-call transcripts for companies) instead of resolution history.
- A maker version of V1 (rest a No bid 1-2 cents under the ask a day before, count fills only on prints through it)
  could save the spread that the taker entry pays; the tape alone cannot show queue position.
- A forward paper log of V1/V2 signals from now on (no money): free and would give the 0.01-fee sample that S3 lacks.
