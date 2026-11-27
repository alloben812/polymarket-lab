# Resolution bonds: buying the almost-decided side (0.95-0.98) shortly before resolution — results

Study finished 2026-11-27 (started by another agent, who wrote `protocol.md` and `s1`-`s6`; this run executed them
unchanged except a crash fix in `s6` (`P = L.append` could not be called without an argument), and added post-hoc
checks `s7`-`s10`, all marked as such). Raw outputs: `out/tables.md` (B-a, B-b, claim, B-d), `out/tape_tables.md`
(B-c, C-tape), `out/attack_tables.md` (s7), `out/extension_tables.md` (s8), `out/losers_rate.md` (s9),
`out/crypto_first_print.md` (s10), `out/losers.csv` (all 142 losers). Large data in `data/gaps_resolution_bonds/`.

## Verdict: NO EDGE for the claim as registered (all categories, sports, weather: negative); crypto and politics INCONCLUSIVE by the rule. A post-hoc out-of-sample check makes crypto price markets the one candidate worth a live micro-test.

- **The pre-registered claim fails as stated.** Buying the favourite the first time its mid is in [0.95, 0.98)
  between endDate - 1 h and settlement, all categories: late period (13-24 Nov) **-2.30 c/share** at the mid
  (577 markets, 450 events, t -2.3 clustered by event), -2.08 c/share with the 5-minute-later fill (C-cons, t -2.1).
  Early period (20 Oct - 12 Nov) -1.48 c (1,321 markets, t -2.3). The "sure thing" lost in 5.9% of the late
  entries (34 of 577) and 5.2% of the early ones (68 of 1,321); break-even at these prices is about 3.6%.
- **Sports carries the loss** (87% of the entries): late -2.35 c/share (523 markets, t -2.2), early -1.55 c (1,125,
  t -2.2). Most sports entries are in-play (endDate is the scheduled start), and in-play 0.95 favourites lose about
  6% of the time. **Weather** is the worst family: -19.0 c late (13 markets), -11.9 c early (45, t -2.2); 10 of 58
  favourites at 0.95-0.98 lost.
- **Crypto price markets and politics are positive but not proven.** Crypto: +3.30 c late (15 markets, 0 lost),
  +1.52 c early (47, 1 lost). Politics: +4.01 c late (21, 0 lost), +2.35 c early (88, 1 lost). The tape version
  (only prices someone actually paid, rule 18) agrees: +3.07 c/share (crypto+politics, 118 markets, 2 lost). But the
  reporting period has 36 such markets against the 100 the verdict rule needs, and with zero losses the t values
  (10-20) mean nothing: the whole question is the rare loss. Over both periods the non-sports, non-weather
  families together won 190 of 192 entries (98.96%, Wilson 96.3-99.7%) against a break-even of 96.5%: the lower
  confidence bound sits right on break-even.
- **Post-hoc extension (not part of the verdict, chosen after seeing the sample).** The unchanged claim on every
  crypto and politics market of the universe outside the sample (3,796 markets, 1,234 entries). **Crypto holds up:**
  514 entries, 5 lost (0.97%, Wilson 0.4-2.3%), +2.58 c/share at the mid (t 5.9), late period 138 entries, 1 lost,
  +2.79 c (t 3.8), 5-minute-later fill +2.38 c (t 5.3). On the tape, one trade per market at the first real taker
  buy at 0.95-0.98 at least 10 s after the trigger (sample + extension, 429 markets): **5 lost (1.2%, Wilson
  0.5-2.7%) against a break-even of 3.4%, +0.23 USD per 10 USD (t 4.2 by event, 4.4 by day)**; late period 109
  markets, +0.24 USD per 10 USD (t 2.5). With 60 s delay the same (+0.24, 387 markets), with 300 s +0.21 (247).
  All five losses are Bitcoin up/down markets that reversed in the last 10-70 minutes. **Politics does not hold
  up:** POLITICS_EXT
- **Live micro-test: one, on crypto price markets only** (hourly and daily up/down, "above X", ranges,
  "dip to / reach"; fee 0.01): 10 USD taker buys at 0.95-0.98 in the last hour, 300 repetitions, stop at the 4th
  loss in the first 100. Details in "Live micro-test". If the edge is what the data say, it is worth about 2-5 USD a
  day to a 200 EUR account: a test of a mechanism, not an income. Nothing in sports, weather or politics deserves one.

## Question

When an outcome looks almost decided (favourite priced 0.95-0.99) shortly before a market resolves, is buying it
profitable after the taker fee? How often does the near-certain side lose, in which market families, how long is the
money locked, and what could a ~200 EUR account earn by repeating it many times a day at 5-20 USD a trade?

## Data

- Universe (rule 1-2): gamma closed markets with endDate 2026-09-29 .. 2026-12-09, volumeNum >= 10,000, two outcomes,
  slug without `-updown-`, closedTime in [2026-10-20, 2026-11-25): 81,812 listed, 22,363 up/down removed, 22,845
  closed outside the window -> **36,604 markets**. Random sample (seed 20261127) of **5,000**; 576 closed more than
  24 h before endDate (no observation possible) -> **4,424 analysed markets in 3,083 events**: sports 3,550
  (sports/start 3,032, sports/other 518), politics 326, crypto 322, weather 141, finance 26, culture 22, tech 22,
  economics 15. Early part (closedTime before 13 Nov) 3,153 markets, late part 1,271. All 5,000 resolved.
- Prices: data-api `prices-history`, 300-s buckets, both tokens, endDate - 24 h 15 min .. closedTime + 5 min
  (no download errors). Outcome: data-api `tokens` final prices matched to gamma outcomes by name.
- Tapes (rule 19-20): the whole-market tape of all 171 claim-entry markets in the two "best-looking" families (crypto
  62, politics 109; fewer than 300 exist, so all). No tape hit the 60,000-row cap.
- Fees: `feeSchedule.rate` (sports 0.05 / 0.03, crypto, politics, weather, culture, economics 0.01, finance and tech
  0.05; 0 where fees are disabled: 34 markets), applied to all dates. Rebates 0.

### Sanity checks (rule order of operations)

- Payoff mapping by name agrees with gamma `outcomePrices` in 5,000 of 5,000 markets; the last point of token 0's
  price series equals its payoff in 4,424 of 4,424 (token order is right). The two tokens' mids sum to exactly 1 on
  111,625 paired buckets (1st-99th percentile 0.0000 off). Data-api token ids are float-rounded: matching by name
  is required, as the protocol says.
- Fee per share = rate x p x (1-p): 0.146 c at p = 0.97 and rate 0.05, as NOTES.md.
- **Calibration below 0.80 is poor in sports** (sanity table in `out/tables.md`): favourites at 0.60-0.80 one hour
  before the scheduled start won about 59% against a mid of 0.69 (sports/start, 1,106 markets), while politics
  (24-44) and the other families are closer. It is not a volume-filter effect (similar in every volume tier). Most of
  these are thin alternate spread and total lines (NBA spreads 127 markets won 53.5%, NBA totals 67 won 46%), where a
  5-minute mid is not a price anyone could trade at. Consequence: every number below that is bought "at the mid"
  is a weak measure in sports; the tape variant (C-tape) is the one that decides.

## What was run (every variant)

Pre-registered (protocol): B-a calibration table (5 observation times x 11 category rows x 5 price buckets = 275
cells), B-b (33 share cells, 165 outcome cells), the claim in 3 fill variants (C-mid and C-cons: 11 category rows x 2
periods = 22 cells each; C-tape: 3 rows x 3 periods), B-c capacity (3 x 3), B-d losers list, plus the sanity
calibration table (15 cells). **532 table cells, 3 claim variants.**

Added after the results were seen, none of them used for the verdict (8 more): A1 C-tape with only prints at or
after the entry time, A2 the same 5 minutes later, A3 print-timing profile, A4 size check, D1 weekday/weekend split,
D2 crypto sub-types, D3 pooled "all families except sports and weather" (C-mid and C-cons), the B-d denominator (s9),
and the extension of the unchanged claim to all out-of-sample crypto and politics markets (s8, 3 fill variants).
Two diagnostics of the sanity table (calibration by volume tier and by family). **Total: 3 pre-registered + 11
post-hoc variants/splits + 2 diagnostics.**

## Headline numbers (after fees)

### The claim: first favourite mid in [0.95, 0.98) from endDate - 1 h to settlement, one share per market

| row | period | markets | events | lost | win % (Wilson 95%) | mean price | C-mid net c/share (SE, t) | C-cons net c/share (t) | mean lock-up h |
|---|---|---|---|---|---|---|---|---|---|
| ALL | early | 1,321 | 987 | 68 | 94.85 (93.5-95.9) | 0.962 | -1.48 (0.63, -2.3) | -1.70 (-2.7) | 6.7 |
| ALL | late | 577 | 450 | 34 | 94.11 (91.9-95.8) | 0.962 | **-2.30 (1.01, -2.3)** | **-2.08 (-2.1)** | 16.4 |
| sports | early | 1,125 | 802 | 59 | 94.76 (93.3-95.9) | 0.962 | -1.55 (0.69, -2.2) | -1.70 (-2.5) | 2.0 |
| sports | late | 523 | 400 | 31 | 94.07 (91.7-95.8) | 0.963 | -2.35 (1.07, -2.2) | -2.25 (-2.2) | 2.4 |
| weather | early | 45 | 43 | 7 | 84.4 (71.2-92.3) | 0.963 | -11.85 (5.49, -2.2) | -12.04 (-2.3) | 20.7 |
| weather | late | 13 | 13 | 3 | 76.9 (49.7-91.8) | 0.959 | -19.00 (12.13, -1.6) | -18.71 (-1.6) | 22.0 |
| crypto | early | 47 | 43 | 1 | 97.87 (88.9-99.6) | 0.963 | +1.52 (2.12, +0.7) | +0.23 (+0.1) | 0.8 |
| crypto | late | 15 | 14 | 0 | 100 (79.6-100) | 0.967 | +3.30 (0.23, +14.3) | +8.81 (+1.9) | 0.7 |
| politics | early | 88 | 84 | 1 | 98.86 (93.8-99.8) | 0.965 | +2.35 (1.14, +2.1) | +1.83 (+1.6) | 62.4 |
| politics | late | 21 | 18 | 0 | 100 (84.5-100) | 0.959 | +4.01 (0.21, +18.7) | +3.64 (+8.9) | 374.0 |

Culture (3 + 3 markets), finance (9 + 1), tech (4 + 1), sports/other (5 + 4): all won, too few to say anything.
Entries before endDate 302, at or after 1,596. In crypto late C-cons the 5-minute-later mid was lower than the entry
mid on average (0.911), which is why C-cons looks better there; it is noise on 15 markets.

### C-tape: real taker buys of the entry-time favourite at 0.95-0.98 in [endDate - 1 h, settlement]

| row | period | markets | lost | $ bought | net c/share | t (event) | A1: only prints >= entry time, markets / net c (t) | A2: >= entry + 5 min |
|---|---|---|---|---|---|---|---|---|
| crypto | early | 43 | 1 | 46,379 | +2.00 | +1.3 | 39 / +0.25 (+0.1) | 24 / -0.30 (-0.1) |
| crypto | late | 13 | 0 | 8,342 | +3.07 | +15.1 | 10 / +2.91 (+10.3) | 4 / +2.36 |
| politics | early | 49 | 1 | 134,295 | +3.41 | +15.7 | 39 / +3.07 (+18.7) | 38 / +3.09 |
| politics | late | 13 | 0 | 6,644 | +3.57 | +18.5 | 11 / +3.33 (+12.6) | 11 / +3.33 |
| both | both | 118 | 2 | 195,659 | +3.07 | +7.3 | 99 / +2.57 (+4.4) | 77 / +2.78 (+7.6) |

The two losses: `bitcoin-up-or-down-on-november-8-2026` (a daily up/down, Sunday, favourite Up at 0.99 an hour
before the end, $723 bought at 0.95-0.98) and `will-the-democratic-party-win-the-az-02-house-seat` ($137). In
crypto, one loss decides the sign: with the favourite known (A1) crypto over both periods is +0.66 c/share (49
markets, t 0.3). Politics' share-weighted figure is dominated by a few large markets (139K of 146K shares early);
the equal-size version ($100 per market, rule 21) gives +0.93 $/market early (t 0.4) and +2.91 late (t 7.9).

### How often does the sure thing lose (B-d, s9)

Markets in which an outcome had a mid >= 0.95 at some point in [endDate - 24 h, settlement) and then did not pay 1:
**142 of 4,407 (3.2%, Wilson 2.7-3.8%)**; early 2.8%, late 4.3%. By family: weather 19 of 141 (13.5%), sports 108 of
3,533 (3.1%; when the first >= 0.95 was BEFORE the scheduled start 30 of 272 = 11.0%, in play 68 of 2,757 = 2.5%),
crypto 11 of 322 (3.4%; late 6 of 91), finance 1 of 26, politics 3 of 326 (0.9%), culture/tech/economics 0 of 59.
What happened (the 60 highest-priced losers read; all 142 in `out/losers.csv`):
- Sports (108): real results. Pregame "Under 6.5/7.5 goals" and exact-score "No" at 0.98-0.99 that lost to very
  rare scores (ESPN confirms Lens 9 - 1 Como on 4 Nov for the Under 7.5 at 0.993); alternate spreads at 0.98-0.996;
  in-play favourites that were overturned late (NBA spreads and totals, NHL, CFB, CS2 maps).
- Weather (19): the forecast was wrong (No on a bucket at 0.993-0.998 a day ahead, then the station reached it) or a
  later reading moved the day's maximum (San Francisco 72-73 F Yes at 0.98 eleven hours after endDate); one Cape Town
  "19 C or higher" Yes at 0.9995 resolved No a week later.
- Crypto (11): "dip to / reach X" No at 0.98-0.9985 until a late wick touched the level; one daily up/down reversed in
  its last hour; ranges and "above X" reversed before noon ET.
- Politics (3): an Elon post-count bucket at 0.978, a Brazil city-vote market at 0.97, AZ-02.

### B-a: calibration at fixed times (mid, fee in), all categories

| obs | bucket | markets | lost | net c/share (t) | bucket 0.98-0.995: markets / lost / net (t) | >= 0.995: markets / lost / net (t) |
|---|---|---|---|---|---|---|
| T-24h | 0.95-0.98 | 216 | 17 | -4.51 (-2.4) | 215 / 8 / -2.47 (-1.9) | 128 / 1 / -0.61 (-0.8) |
| T-1h | 0.95-0.98 | 192 | 18 | -6.00 (-2.9) | 170 / 3 / -0.63 (-0.6) | 497 / 0 / +0.13 |
| T-10m | 0.95-0.98 | 184 | 14 | -4.19 (-2.1) | 175 / 5 / -1.76 (-1.4) | 500 / 0 / +0.11 |
| T (endDate) | 0.95-0.98 | 140 | 14 | -6.50 (-2.6) | 142 / 3 / -0.99 (-0.8) | 597 / 0 / +0.11 |

Politics at 0.98-0.995: 54-97 markets per observation time, none lost, +1.1..+1.3 c/share, but mean lock-up 17-33 h
(median 4-25 h). At >= 0.995 everything earns +0.05..+0.2 c/share: a money-market rate, and one loss in 500 erases it.

### B-b: how long prices stay below 1 after endDate (markets settling >= 30 min after endDate)

Share of favourites still under 0.99 / 0.95 at endDate: politics 38% / 20% (258 markets), weather 45% / 40% (138),
crypto 9% / 9% (11), sports/start 99% / 94% (3,022: the game has only started). One hour after endDate: politics 35%
/ 20%, weather 40% / 34%. Politics favourites bought at the mid in that window: 0.95-0.98 +3.2 c (17 markets, 0
lost, mean lock-up 66 h); 0.80-0.95 +11 c (28, 0 lost, 134 h). Gap from endDate to settlement (median): sports/start
3.2 h, politics 2.0 h, weather 11.7 h, crypto 0.2 h, finance 0.3 h.

## Opportunities per day, net per trade, capacity

Universe scale factor 36,604 / 5,000 = 7.32. Entries per day (both periods, universe estimate): crypto 12.6, politics
22, sports 335, weather 12. Weekday vs weekend (D1, closedTime UTC; 26 weekdays, 10 weekend days): crypto 13 vs 11
a day (it runs 7 days a week; the one crypto loss was on a Sunday), politics 29 vs 5, sports 251 vs 555 (weekends are
mostly sports, which loses), weather 12 vs 12.

- **Net per trade at 5-20 USD (crypto, the only candidate).** In-sample tape check with the favourite known (A1,
  share-weighted): +0.7% of cost over both periods (49 markets, one loss decides it), +3.0% late (10). Post-hoc,
  one trade per market at the first print >= 10 s after the trigger (s10, 429 markets, sample + extension):
  **+0.23 USD per 10 USD trade (+2.3%), +0.45 per 20 USD**; late period +0.24 per 10 USD (109 markets). One loss
  costs about 9.7 / 19.4 USD, as much as 40 winning trades: the result is the loss rate (1.2% measured, 3.4%
  break-even).
- **Opportunities and size (crypto).** 576 crypto entries in the universe in 36 days = **16 a day** (13 on
  weekdays, 11-12 on weekend days in the sample split; the extension has 391 weekday and 123 weekend entries, both
  positive: weekday +2.58 c, weekend +2.58 c at the mid). 429 (12 a day) had a qualifying print >= 10 s after the
  trigger; 388 (11 a day) had at least 20 USD of such buys, 316 (9 a day) at least 100 USD. Median print 9.8 USD,
  median 5 taker wallets per market. All takers together bought about 6,500 USD a day of these prints.
- **Capacity for ~200 EUR (~215 USD).** Crypto: lock-up 0.5-1 h, so capital is not the limit; about 11 trades a day
  x 20 USD x 2.3% = **about 5 USD a day if the measured edge is real** (2.5 USD at 10 USD a trade), with a loss of
  ~19 USD about once a week; 0 or negative if the loss rate is 3.4% or more. Rule 21 ($100 per entry, sample late
  C-tape): about 22 USD a day, but it needs 100 USD of asks (9 markets a day have them) and rests on 13 late markets
  without a loss. Politics: lock-up 122 h mean in the sample (C-tape sample 170 h), so capital binds: rule 21 for
  $300 gives 3 x 24 / 422 h = 0.17 positions a day, about 0.6 USD/day; at 20 USD slots with 215 USD about 2 trades a
  day, about 1.4 USD/day before the losses the extension shows. Universe-wide, the eventual winner's taker buys at
  0.95-0.98 in the window were about 5,100 USD/day in crypto and 4,100 USD/day in politics in the late period
  (sample scaling, rule 20).

## Reaction time needed

Not a sub-second race. Crypto: the first qualifying print comes a median 5 s after the 5-minute mid bucket shows the
favourite in range, but 67% of the dollars print more than 60 s after the market's first such print and 22% more than
10 minutes after. One trade per market at the first print after 10 s, 60 s or 300 s gives +0.23, +0.24 and +0.21
USD per 10 USD (429, 387, 247 markets): a delay of a few seconds to a minute costs nothing, a longer one costs
opportunities (fewer markets still print in range), not price. Politics: median 64 minutes from entry to the first
print, 79% of dollars more than 10 minutes later. **A program polling the book every 5-10 seconds is enough.**
(In-sample share-weighted A2 for crypto was -0.04 c on 28 markets: one loss among few markets; the per-market
version on 247 markets is the better measure.)

## Live micro-test

Worth one, on crypto only. It tests a post-hoc result, so it is a test, not a deployment: keep the stake small.

- **Markets.** Polymarket crypto price markets with fee 0.01 that resolve on a price at a fixed time: hourly and
  daily "Up or Down" (not the 5- and 15-minute `-updown-` series), "above X on <date>", "between X and Y", "dip to /
  reach X on <date>". BTC, ETH, SOL, XRP. No volume filter at entry (the study's >= 10,000 filter used final volume).
- **Rule.** From endDate - 60 min until the market closes, read both books every 5-10 s. The first time the
  favourite (higher mid) has its best ask in [0.95, 0.98), send ONE buy of 10 USD at that ask as a fill-and-kill
  (immediate-or-cancel) limit order; if it does not fill, retry on the next poll while the ask stays in range, then
  give up on that market. One position per market, held to resolution, no stop-loss, no exit. Skip a market whose
  ask is below 0.95 (the price is telling you something) or whose book shows less than 10 USD at the ask.
- **Size.** 10 USD per trade (above the market's minimum order); worst single loss about 9.7 USD. Positions settle
  within about 1 h, so 3-5 open at once is the most the account needs: a 60-100 USD test account is enough.
- **Repetitions.** 300 filled trades (about 3-5 weeks at roughly 10-12 a day). Decision: the edge is real if 5 or fewer
  of the 300 lose (one-sided p < 0.05 against the break-even loss rate of 3.5%); with the measured 1% loss rate this
  passes 92% of the time. Expected result if the data are right: about +70 USD on 3,000 USD of turnover; if the
  market is fair: about 0 (minus the fee already in).
- **Stop rule.** Stop at the 4th loss within the first 100 trades (1.8% chance if the true loss rate is 1%, 47% if
  it is 3.5%), or at a cumulative net of -40 USD, or if fewer than half of the triggers get filled within 60 s (the
  prices would then not be there for a slow program). Log for every trigger: time, both asks and bids, size at the
  ask, fill price and size, time to fill, and the outcome; compare the fill price with the first tape print after the
  trigger to check the study's fill assumption.

## Limitations

- The pre-registered universe conditions on final volume >= 10,000 and on closing inside the window: a look-ahead
  selection (markets with drama attract volume). It did not change calibration much across volume tiers.
- Mid prices (C-mid, B-a, B-b) are 5-minute mid snapshots, not tradable prices; on thin sports lines they are badly
  calibrated. C-tape is the only demonstrably available price, still without queue position, without the 1-3 s
  block lag and without knowing whether a $20 order would have been filled ahead of the printed buyer.
- C-tape rows before the entry time (s6 as written) use the later knowledge of which token becomes the favourite; A1
  removes them (crypto +2.17 -> +0.66 c/share both periods).
- Fees: today's `feeSchedule` applied to all dates. Several categories charged zero on 20-31 Oct and weather /
  economics / mentions charged 0.04-0.05 before 21 Nov, so the early weather figure is optimistic; crypto (0.01) and
  sports were unchanged. Crypto hourly up/down switched from Binance to Chainlink settlement on 18 Nov, inside the
  late period.
- Late period is 12 days. Zero-loss cells: t values there are not evidence. The family label of `pmlab.gamma.family`
  puts mentions into other families and Elon post counts into politics.
- The B-d reading of rules is by slug, rules text and timing, not by replaying each event; one score checked on ESPN.

## Ideas, not tested

- Crypto hourly up/down and range markets in the last hour with a Binance/Chainlink fair-value model (distance to the
  strike, time left, volatility) instead of the bare price: buy only when the model gives >= 0.99 and the ask is
  <= 0.97. Data for it is in `data/binance_1s` and the hourly markets are listable; it would turn a rare-loss bet into
  a measurable one.
- Politics after endDate at 0.80-0.95 (B-b: 28-30 markets, none lost, +11 c, lock-up 5-8 days): a slow "awaiting
  certification" bond; needs a per-event reading of what was still open, and holding-reward eligibility.
- Pregame sports extreme lines (totals, exact score, alternate spreads) look overpriced on the favourite side by mid
  (11% of pregame >= 0.95 favourites lost): selling them (buying the long shot) on the tape, with the book's real ask.
- Weather favourites at 0.95+ before the local afternoon peak lose often (13.5%): buying the cheap side there is the
  mirror of this study's loss; earlier studies found weather well calibrated at local midnight, so it is time-of-day.
