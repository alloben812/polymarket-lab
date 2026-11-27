# Maker edge map: what a passive fill earns, by market family — results

Study run 2026-11-27. Protocol: `protocol.md` (frozen before any outcome number; the only later edit is the tick-rounding
line, added before the first run). Code: `universe.py` (gamma listing), `sample.py` (families and the fixed sample),
`fetch.py` (tapes), `analyze.py` (V1/V2/V2o fills and markouts), `report.py` (protocol tables and decision rule),
`survivor.py` and `attack.py` (post-hoc attacks, labelled as such). Outputs: `out/report.md` (all protocol tables),
`out/attack.md` (attacks and the 100-market extension), CSVs in `out/`. Large files: `data/gaps_maker_edge/`.
Audit (`audit.md`) is still to be done by an independent agent.

## Verdict: NO FAMILY PAYS A SLOW SMALL MAKER; ONE WEAK CELL (post-count markets, bids at 0.95+ held to resolution)

- **Crypto up/down (BTC 5m, BTC 15m, other coins 5m/15m, hourly/4h/daily): the small maker is picked off.** A maker
  who rests at the last traded bid and ask and is filled only when a trade prints through his price (V2) is down
  1-4 c/share 30 s after the fill in every crypto up/down family and both halves (100-market extension: BTC 5m
  -1.13 / -2.30, BTC 15m -2.02 / -2.11, other coins -2.67 / -3.83, hourly+ -0.94 / -1.20 c/share early / late, all
  CIs below zero). Held to settlement he loses 3-12% of the dollars he puts in. The book as a whole (V1, every real
  maker fill at the print price) is roughly flat there (BTC 5m +0.02 / +0.46 c/share, 100 + 100 markets, CIs
  include zero; consistent with the +0.66 c of tape_A.py): the money that the resting book makes goes to the fast
  makers who requote first; the slow one gets the fills the fast ones cancel out of.
- **Everything else: no family pays him.** In sports, weather, post-counts, culture, politics, finance, tech,
  economics, mentions and crypto price ladders the 30 s markout of V2 is about zero or slightly positive (weather
  +0.72 / +0.69, culture +0.39 / +1.23 c/share: some half-spread survives 30 s), the 5-minute markout is about zero
  or slightly negative, and the markout to the final outcome is negative or not distinguishable from zero in every
  family and half except one cell below. No family met the protocol's "paid" label (final AND 5-min CI above zero)
  except mentions in the early half, which rests on 3 markets and 13 fills (late: 9 markets, final -0.95 c/share).
- **The one cell that passed the frozen rule does not survive as an edge.** Three cells were selected on the early
  half and passed on the late half: buys at 0.95+ in crypto price ladders, culture and post-count markets
  (+1.7 / +2.9 / +2.5 c/share, t 8-20, but on 8-10 markets each and with zero losses). On markets the protocol never
  saw (next 75 per half in the same fixed order): crypto ladders -0.87 +- 4.48 c/share (4 of 66 markets had a
  losing fill), culture -1.31 +- 5.80 (2 of 39): both fail. Post-counts held: +2.67 +- 0.24 c/share on 42 new
  markets, zero losers. But the whole post-count cell is 10 events (800 of 847 fills are Elon Musk tweet-count
  buckets), and "zero losses in 10 events" only bounds the event loss rate below 28% (Wilson 95%), while break-even
  at an average price of 0.974 is about 2.6%. The 0.95+ result in every family is the resolution-bond trade (buy the
  near-certain side, hold): its profit is exactly 1 minus the price until the rare loss arrives, and the lab's own
  resolution-bond study found 3.2% of outcomes seen at 0.95+ fail to pay (4,407 markets, `studies/gaps/resolution_bonds/out/losers_rate.md`, 2026-11-27). **Status: not established;
  possible but unproven.**

## Question

For every market family: what does a passive (maker) fill earn, marked to the final outcome and to the mid price
30 s and 5 min later, per share and per dollar, by price bucket and time to resolution; where a small maker with a
reaction time of seconds is paid and where he is picked off; and what a ~200 EUR account quoting 5-20 USD clips
could expect. (Owner's side question: is anything workable at the weekend?)

## Data

- Universe: every gamma market closed with `endDate` in 20-26 Nov 2026 and `volumeNum` >= 1,000: 29,060 markets,
  all resolved (0 with an undecided `outcomePrices`; none resolved 50/50 in the protocol sample). 74 markets with an
  endDate in the window are still open (62 sports, 8 politics incl. one disputed mention-style market, 2 weather,
  1 culture, 1 finance): survivorship is small.
- Families by a fixed slug/tag rule (15 families; "other" was empty). Protocol sample: up to 25 markets per family
  per half in a fixed pseudo-random order (sha1 of the condition id): 667 markets (mentions has only 19, economics
  48). Early half = endDate 20-23 Nov (tuning), late half = 24-26 Nov (reporting).
- Extension (post-hoc attack): up to 100 markets per family per half in the same order, 2,261 markets.
- Tapes: data API `trades?condition=`, whole-market, taker side; 124 reused from `data/tape`, the rest downloaded;
  none hit the 20,000-row cap, 0 failed. Tape dollars are 0.49-0.69 of gamma `volumeNum` in every family (gamma
  volume counts both sides), so tapes are complete to the same degree everywhere. Match time = block time - 3 s.
- Fills: protocol sample 218,794 V1 maker fills, 10,990 V2, 18,229 V2o; extension 826,279 / 44,264 / 70,699.

## What was run (all variants)

Three fill variants, each marked three ways (final outcome, mid +30 s, mid +300 s), protocol sample, both halves:

- **V1 aggregate makers**: every print, maker side = opposite of the taker at the print price (what the resting book
  earned; optimistic for a newcomer).
- **V2 touch-maker, conservative**: every 10 s the maker rests a bid at the last bid-side print and an offer at the
  last ask-side print (each <= 900 s old, rounded to tick, a > b), live 2-10 s after the decision; filled only if a
  print goes strictly through his price; fill at his limit; <= 1 fill per side per window. No fee (maker), no
  rewards, no rebates.
- **V2o**: as V2, a print at his price also fills him (queue share optimistic).

Mid = average of the last bid-side and last ask-side print (each <= 1 h old), or the payout once the market is
closed. Selection: 98 cells (14 families x 7 price buckets) screened on the early half; 6 selected; 3 passed on the
late half. Post-hoc attacks: out-of-sample extension (same frozen rules), clustering by event, loss rate vs
break-even, concentration, survivorship, weekend split. Nothing else was run.

## Headline numbers (protocol sample, c/share, 95% CI clustered by market; fin %$ = % of dollars paid)

V2 (the small maker), early / late, 25 markets per half unless noted:

| family | fin c/sh early | fin c/sh late | fin % of $ (e / l) | m30 early | m30 late | m300 early | m300 late | label |
|---|---|---|---|---|---|---|---|---|
| btc-5m | -2.50 (-5.53..+0.53) | -2.96 (-6.48..+0.55) | -7.8 / -8.5 | -2.16 (-3.30..-1.02) | -2.57 (-3.45..-1.69) | -2.72 | -2.50 | picked off |
| btc-15m | -2.97 (-5.41..-0.52) | -1.08 (-4.32..+2.16) | -11.7 / -3.6 | -2.44 (-3.20..-1.69) | -2.15 (-3.03..-1.27) | -3.16 | -0.32 | picked off |
| alt-updown-5m15m | -5.42 (-9.74..-1.09) | -2.34 (-6.43..+1.75) | -15.8 / -6.4 | -3.26 (-4.45..-2.07) | -4.59 (-5.99..-3.19) | -3.80 | -0.98 | picked off |
| crypto-updown-long | -3.22 (-5.52..-0.91) | -3.00 (-4.22..-1.79) | -14.6 / -12.9 | -1.15 (-1.81..-0.50) | -0.94 (-1.43..-0.44) | -1.68 | -1.68 | picked off |
| crypto-other (15 / 20 mkts) | -2.23 (-2.73..-1.72) | -1.79 (-2.86..-0.73) | -18.2 / -17.5 | +0.06 | -0.06 | -0.05 | -0.24 | unclear |
| post-counts (12 / 12) | -2.19 (-2.94..-1.43) | -1.75 (-2.15..-1.35) | -23.5 / -18.3 | +0.07 | +0.06 | -0.05 | -0.06 | unclear |
| sports (13 / 16) | -10.33 (-19.0..-1.6) | -0.44 (-11.1..+10.2) | -53.4 / -1.8 | +0.03 | -0.81 (-1.59..-0.02) | -3.24 (-6.09..-0.39) | -0.11 | picked off |
| weather (21 / 22) | +0.63 (-6.09..+7.34) | -2.43 (-4.91..+0.05) | +2.4 / -9.0 | +1.07 (+0.09..+2.05) | +0.84 (+0.10..+1.58) | -0.23 | -0.35 | unclear |
| culture (23 / 17) | -0.21 (-7.49..+7.07) | -5.34 (-8.24..-2.44) | -0.9 / -31.3 | +0.86 (+0.44..+1.28) | +1.70 (+0.73..+2.67) | +0.28 | -0.37 | unclear |
| politics (12 / 4) | -3.45 (-4.08..-2.83) | +10.52 (-2.6..+23.6) | -33.3 / +23.3 | +0.18 | +4.99 | -0.03 | +6.19 | unclear |
| finance (8 / 16) | -1.33 (-6.03..+3.37) | -5.02 (-7.96..-2.09) | -9.9 / -20.0 | +0.08 | +0.32 | +0.09 | -0.22 | unclear |
| tech (11 / 8) | -2.81 | -2.89 | -17.6 / -27.4 | +0.09 | +1.40 (+0.23..+2.56) | -0.30 | +1.10 | unclear |
| economics (10 / 15) | +6.05 (-7.96..+20.06) | +0.18 (-16.1..+16.4) | +25.5 / +0.5 | +0.43 | +0.77 | +0.39 | -1.03 | unclear |
| mentions (3 / 9) | +38.29 (13 fills) | -0.95 (38 fills) | +98.0 / -8.0 | +19.10 | +16.78 | +18.71 | +3.31 | paid / unclear (3 markets) |

V1 (the book as a whole), 25 + 25 markets: BTC 5m +0.46 / +0.21 c/share to final (CIs about +-1.5), weather
+1.93 / +1.20 (m30 +1.48 / +1.32, CI above zero), post-counts -0.08 / -0.19 (m30 +0.22 / +0.37), culture
-1.95 / -1.26, economics -4.06 / -1.70 (m300 late -1.72, CI below zero). Full tables: `out/report.md`.

How to read: the "fin" column of a small sample is dominated by which few markets went the wrong way (CIs are
wide, and where one market holds most of the shares, a tight CI is an artefact of the linearised SE: in sports early
one market holds 94% of V1 shares, in politics early 90%). The 30 s and 5 min markouts are the informative columns
for "paid or picked off".

By time to resolution (extension, all families pooled): V2's 30 s markout is -1.65 +- 0.47 c/share with < 5 min
left and -1.60 +- 0.20 with 5-60 min left (these buckets are mostly crypto up/down), and +0.17..+0.54 with more than
an hour left; its 5 min markout is negative in every bucket up to 3 days (-0.17..-2.37). V1's 30 s markout is
positive in every bucket (+0.13..+0.58).

By price: the low buckets (< 0.20) lose about their whole price at settlement in ladders (post-counts, politics,
crypto ladders, finance, culture: -98% to -100% of dollars in V2), the 0.80-0.95 and 0.95+ buckets win: this is the
favourite/longshot shape of multi-outcome ladders, but each cell rests on 2-12 markets and 1-6 events.

## Candidate cells and the late check (protocol rule)

| cell (selected on early) | early | late | late $/day at $10 clips (protocol scaling) | protocol |
|---|---|---|---|---|
| btc-15m 0.95+ | +3.04 c, 9 mkts | -4.82 (t -0.8), 13 mkts | -61 | FAIL |
| btc-5m 0.95+ | +2.86 c, 14 mkts | -7.53 (t -0.7), 8 mkts | -185 | FAIL |
| crypto-other 0.95+ | +2.16 c, 10 mkts | +1.69 (t 19.8), 10 mkts, 0 losers | +51 | PASS |
| culture 0.80-0.95 | +13.3 c, 9 mkts | +3.24 (t 0.4), 8 mkts | +30 | FAIL |
| culture 0.95+ | +2.16 c, 10 mkts | +2.87 (t 14.6), 9 mkts, 0 losers | +6 | PASS |
| post-counts 0.95+ | +2.57 c, 10 mkts | +2.47 (t 8.5), 8 mkts, 0 losers | +14 | PASS |

## Attacks on the three passing cells (post-hoc; `attack.py`, `out/attack.md`)

1. **Out of sample (markets 26-100 of the fixed order, never used by the protocol run), V2 frozen:**
   crypto-other 0.95+ -0.87 +- 4.48 c/share, 66 markets, 4 with a losing fill -> **fails**;
   culture 0.95+ -1.31 +- 5.80, 39 markets, 2 losers -> **fails**;
   post-counts 0.95+ +2.67 +- 0.24, 42 markets, 0 losers (early +2.68, late +2.65) -> holds in the mean.
   V2o (optimistic) says the same (+2.51 +- 0.26, 45 markets). All families pooled, 0.95+, V2: +0.20 +- 1.60 c/share
   on 494 markets with 22 losing markets (4.5%, Wilson 3.0-6.7%) against a break-even of 2.7%.
2. **Unit = event, not market.** Post-count buckets of one event share one counter, so a surge kills several
   positions at once. Post-counts 0.95+ V2 (extension, all 60 markets): 10 events, 0 losing; Wilson 95% upper bound
   on the event loss rate 27.8%. V1 at 0.95+ in post-counts: 19 events, 2 losing (Truth Social 100-119 bought at
   0.962; Truth Social 60-79 at 0.950). Break-even loss rate per fill ~ 1 - price = 2.6%.
3. **Concentration.** 800 of the 847 post-count 0.95+ fills are Elon Musk tweet-count buckets; result without the best
   market +2.63 c/share (no single market drives it, but a single event family does).
4. **Look-ahead.** Quotes use only prints with match time <= the decision time; fills are later prints. None found.
5. **Survivorship.** 74 of ~29,100 markets with an endDate in the window are still open; none are post-count
   markets, none are crypto ladders, one is culture (a MrBeast views bucket).
6. **Impossible fills.** V2 counts only prints strictly through the limit; V2o barely differs at 0.95+ (above).

Conclusion of the attacks: the post-count 0.95+ cell is "all fills won in 10 events". That is what a fairly priced
tail risk looks like too. It is not an edge until the loss rate is pinned down.

## Opportunities per day, net per trade, capacity for a ~200 EUR account

- V2 fills per day if the bot quoted every market of the family (late half, scaled to all resolved markets with
  volume >= $1K): BTC 5m ~7,000, other coins up/down ~7,700, BTC 15m ~4,000, crypto hourly+ ~2,200, crypto ladders
  ~2,200, weather ~3,300-4,700, sports ~19,000-25,000, post-counts ~1,000-1,100, culture ~200-400, finance ~200,
  politics ~140-180, tech/economics/mentions under 100 (`out/extension_map.csv`).
- Net per trade at a $10 clip = clip x "fin % of $" (extension, early / late): crypto up/down -$0.31 to -$1.18 per
  fill in every family and half; crypto ladders +$1.55 / -$1.75, culture +$0.77 / -$1.21, weather +$0.77 / -$0.81,
  sports +$2.90 / -$1.54, finance +$1.03 / -$2.27, politics -$3.33 / +$0.19, tech -$2.21 / -$1.63, post-counts
  -$1.43 / +$0.17; no family has a final-markout CI above zero in both halves. At $5 halve these, at $20 double them.
- Post-count 0.95+ cell: 847 V2 fills on the 200 of 213 post-count markets that ended in the 7 days, i.e. about
  120 fills a day across all post-count markets; each $10 fill earns +$0.26 if it wins and loses about -$9.70 if it
  loses. Capital is tied up a median 11-15 h, so taking every fill needs about $600 at any time; a 200 EUR (~$215)
  account can carry about a third of them (~40 a day). Best case (no loss): ~$10/day; one lost event with 3 open
  clips costs ~$29, i.e. about three days of best-case profit, and the observed V1 loss rate at 0.95+ in this family
  (2 of 19 events) would make it negative.
- **Capacity: $0/day of demonstrated edge.** Upper bound if the post-count cell were real: ~$10/day on this account.

## Reaction time

A maker who can only react in seconds is stale exactly when it matters: in crypto up/down the fills that go through
his price come right after a Binance move, and he is down 1-4 c/share within 30 s. To be paid there one has to
requote in well under a second (the fast makers who keep V1 about flat). In the slower families reaction time is not
the problem: the 30 s markout is ~0 even for a 10-second-stale quote; the problem is that nothing is left after the
spread (5 min ~0, settlement negative or noise). The post-count 0.95+ cell needs no speed (hours to resolution).

## Weekend (owner's question)

Families that run at the weekend just as on weekdays (markets ending per day, Sat-Sun 21-22 Nov vs Mon-Fri): BTC 5m
262 vs 262, BTC 15m 97 vs 97, other coins 536 vs 517, weather 318 vs 309, crypto ladders 86 vs 99; sports has more
(4,108 vs 2,274 a day). Stock/finance (2 vs 41), economics (1 vs 15), mentions (0 vs 4) and post-count endings
(5 vs 41) are weekday families. So the market is there at the weekend, but the families that are open at the weekend
are exactly the ones where a slow maker is picked off (crypto) or not paid (sports, weather). Weekend split of V2
(protocol sample, `out/wkend.csv`): crypto up/down 30 s markout at the weekend -0.49 (hourly+) to -3.69 (other
coins) c/share against -1.20 to -4.05 on weekdays; sports +0.11 vs -0.60, weather +0.40 vs +1.12; settlement
markout negative or noise on both (6-15 weekend markets per family).
On the time-gap idea: the earlier lab studies found the seconds-long gaps (weather reports, data releases, mention
words, crypto closes) already taken by bots in 2-25 s; this study adds that resting quotes do not earn the gap
either: they are the side that gets hit.

## Live micro-test

Nothing here deserves a live test as an edge test. If the owner wants to spend a part of the 50-100 USD test account
on checking the mechanics of resting orders (fill rate against this tape model) on the one weak cell, the exact rule is:

- **Rule (as tested, V2):** Elon Musk / Truth Social post-count markets (xtracker). Every 10 s, for each bucket where
  one side's best bid is 0.95-0.99, rest a **post-only limit BUY** of that side at the current best bid (join, do
  not improve). Hold to resolution; never sell. One open clip per market, at most 3 open clips per event.
- **Size:** $10 per clip (10.1-10.5 shares at 0.95-0.99; check `min_order_size` in the book); at most $80 open in
  total.
- **Repetitions:** with a 2.6% break-even loss rate, telling an edge from a fair price needs about 115 independent
  events with no loss (or ~180 with one) before the 95% bound on the event loss rate falls below break-even. At
  10-20 post-count events a week that is 1.5-3 months; a 2-4 week run can only test fill mechanics (fills per day
  against the tape model's ~40 a day within $80 of open exposure, and the share of fills that came right before the
  price moved against the bid).
- **Stop rule:** stop at the first losing event, or when cumulative P&L reaches -$15, or after 4 weeks.

## Limitations

- 25 markets per family and half (protocol), 100 in the extension; mentions (19) and economics (71) have fewer.
  The final-outcome markout is dominated by a few markets per cell; the 30 s / 5 min markouts carry the map.
- No order book: the maker's touch is estimated from the last prints on each side (<= 15 min old); in reality he
  would see the book and might quote better or worse. Queue position is not observable (V2 vs V2o brackets it).
- The mid is built from prints (last bid-side and ask-side prints, <= 1 h old), which is stale in thin markets and
  flatters the 30 s / 5 min markout there (half-spread looks earned if nothing trades).
- Clustering is by market (protocol); by event the effective sample is smaller (post-counts: 10 events).
- One week (20-26 Nov), right after the 20 Nov fee change; liquidity rewards (which do pay makers in weather, ladders
  and politics) are not counted, nor are holding rewards. Rebates are 0 for a new account.
- Taker fees do not enter V2 (pure maker, held to resolution); any exit by taker would pay rate x p x (1-p).

## Ideas, not tested

- Post-count buckets already passed by the live xtracker count ("dead" buckets): their No is certain barring a
  counter revision; bid 0.97-0.99 for it and hold. Needs the xtracker posts history (cached under `data/xtracker`)
  joined to the tapes; this would separate the riskless part of the 0.95+ cell from the tail-risk part.
- Liquidity-reward farming as the maker's real income (weather, crypto ladders, H100): markouts here say the fills
  themselves are about zero, so the reward is the whole return; needs reward pool / min size per market.
- Event-level clustering for all ladder families and a longer window (4-8 weeks) for the 0.95+ cells.
- A book-based (L2 archive) version of V2 for weather and sports, where the 30 s markout is mildly positive.
