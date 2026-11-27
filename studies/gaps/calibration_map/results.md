# Calibration map: does buying an outcome at the shown price pay after the taker fee? — results

Study run 2026-11-27 (18:09-18:45 UTC). Protocol: `protocol.md` (written and saved before any outcome number). Code:
`common.py`, `s1_list.py` (gamma listing), `s2_sample.py` (universe and sample), `s3_fetch.py` (prices-history),
`s4_cells.py` (observations, cell table, decision rule), `s5_tape.py` (tape stage; not triggered), `s6_report.py`,
`s7_family.py` (descriptive tables). Outputs: `out/cells.csv` (all 828 cells), `out/decision.json`, `out/pooled.md`
(family x horizon), `out/family.md`, `out/shape.md` (bucket x horizon), `out/weekend.md`, `out/headline.txt`,
`out/universe.json`, `out/obs_counts.json`. Raw data: `data/gaps_calibration_map/` (listing, sample, ph.jsonl, obs.pkl).

## Verdict: NO EDGE (clean negative). Nothing here deserves a live micro-test.

- **0 of 828 cells passed the pre-registered rule** (candidate in the early part, confirmed in the late part with
  >= 200 events, t >= 3 by event and t >= 2 by day). Two cells were candidates in the early part and both failed:
  crypto up/down 15m, leader at 0.50-0.60 five minutes into the window: +5.1 c/share net early (409 markets, t 2.1),
  +1.9 c late (423 markets, t 0.8, t by day 0.7); daily temperature, favourite at 0.98-0.995 six hours before the end
  of the local day: +0.49 c early (114 markets, all won), +0.25 c late on only 18 markets. No tape stage was run,
  because the rule sends only confirmed cells to it.
- **All families together, one market per horizon:** buying the favourite at the shown price + slippage loses
  1.08 c/share after fee in the early part (95% CI -2.05..-0.11, 16,706 observations, 5,087 events) and 1.17 c in the
  late part (-2.52..+0.17, 9,426 observations, 2,677 events). Buying the long shot loses 1.65 c (-2.62..-0.68) and
  1.62 c (-2.96..-0.28). Before slippage and fee the favourite's edge is +0.28 c (-0.69..+1.25) and +0.22 c
  (-1.12..+1.56): on average the shown prices are calibrated, and the cost of crossing (slippage 0.5-1 c plus a fee
  of up to 1.25 c) is what you lose.
- **The bias map, read honestly:** there is a weak favourite-underpriced / long-shot-overpriced tilt in the
  non-sports families (culture/tech "other", politics late, crypto one-touch, weather, esports: long shots lose 3-8
  c/share), and the reverse in sports moneylines in the early part (favourites lost 6.0 c/share net, t -3.7, 753
  events; late -2.8 c, t -1.3). None of these is stable across the two halves at cell level, and buying the cheap side
  of the reverse bias (sports underdogs) made +2.1 c early (t 1.3) and -1.0 c late. Only 22 of 828 cells had >= 100
  events in both halves and only 10 had >= 200 late events; the largest late t among those 10 is 0.8.
- **For the owner's weekend question:** Polymarket is not mostly stock quotes. Stock/commodity markets ("finance")
  are 7% weekend; crypto up/down, crypto ladders and weather are 27-29% weekend; sports are 44-55% weekend (Saturday
  and Sunday are their busiest days). So there is plenty to trade on weekends, but on this map nothing pays on
  weekends either (`out/weekend.md`: the only weekend rows with a positive net and t >= 2 are culture/tech "other",
  +5.0 c on 147 observations, t 2.1, and finance, 10 observations; sports moneyline favourites lost 6.1 c on
  weekends, t -2.4, 1,118 observations). The "time gap" (an event already happened elsewhere) is a different game from this map: the lab's
  earlier studies found those gaps in weather, mentions, economic releases and BTC 5m closed within 2-25 seconds by
  faster bots (NOTES.md: weather METAR 25 s median, 53 of 53 before the official source; releases > 90 c at 9 s;
  mentions first print >= 0.90 in 57% of jumps). A Mac in Serbia polling every few seconds arrives after that.

## Question

For every resolved binary market of the last ~3 months, take the price shown at fixed horizons (24 h, 6 h, 1 h,
10 min) before the scheduled end, put each market into a family (17 families by slug and tag rules), a horizon and a
favourite price bucket (7 buckets from 0.50 to 0.995), and ask whether buying the favourite (or the long shot) at that
price plus a fixed slippage, held to resolution, returns more than today's taker fee. Emphasis on short-dated
repeating markets that a small program could hit many times a day.

## Data

- Period: anchor (scheduled end) 2026-08-29 .. 2026-11-26 UTC, 90 days. Four months were asked for, but
  `prices-history` returns nothing for markets that ended in early August (checked before the protocol); 30-minute
  points exist back to ~90 days, 5-minute points back to ~60 days.
- Universe: gamma closed markets with endDate 2026-08-25 .. 2026-12-03 and volumeNum >= 500: 481,931 unique listed;
  70,563 BTC/ETH/SOL/XRP 5-minute up/down excluded by rule; 19,676 with the anchor outside the period; 391,692 binary
  resolved markets in the universe (per-family counts and per-day rates in `out/universe.json` and the family table
  below).
- Sample: per family stratified by anchor day, seed 20261127, caps fixed in the protocol: 10,302 markets, all 10,302
  fetched without error (no download shortfall; the 19:35 stop rule was not needed). 407 returned no price points.
  Prices at 1,800 s buckets for anchors before 2026-09-28, at 300 s from then on.
- Observations: 26,132 market x horizon points (drops: 6,504 favourites already above 0.995, 3,271 market not
  trading at that time, 420 stale prices). Split: early = anchor before 2026-10-28 (16,706 obs), late = after
  (9,426 obs). Cluster = gamma event (each up/down market is its own event).
- Fees: today's category rates (BTC 15m 0.05, other crypto 0.01, sports/esports/finance 0.05, weather, mentions,
  counters, economics 0.01, politics 0.01 / elections 0.05 / geopolitics 0, other 0.05, culture 0.01), applied to the
  whole period. Slippage 1 c (shown price 0.10-0.90) or 0.5 c (outside). No rebates.

## What was run (every variant)

- One screen: 414 family x horizon x bucket combinations x 2 sides (favourite, long shot) = **828 cell tests**,
  each evaluated early (selection) and late (confirmation). The two sides of a cell are near mirror images
  (gross edge of one is minus the other's), so this is about 414 independent questions.
- Decision rule applied once: 2 candidates, 0 confirmed. Tape stage (buyability check on whole-market tapes): **not
  run** (protocol: only for confirmed cells). Number of variants: 828 cells + 0 tape variants.
- Descriptive tables computed after the rule (not used for any decision): pooled by family x horizon
  (`out/pooled.md`, 134 rows), pooled by family (`out/family.md`), pooled by bucket x horizon (`out/shape.md`), weekend
  vs weekday (`out/weekend.md`). One diagnostic: the weather anchor coverage check (Limitations).

## Headline numbers (after fee and slippage, cents per share, t clustered by event)

| part | observations | events | gross favourite edge, c (95% CI) | net buy favourite, c (95% CI) | net buy long shot, c (95% CI) |
|---|---|---|---|---|---|
| early (Aug 29 - Oct 27) | 16,706 | 5,087 | +0.28 (-0.69..+1.25) | -1.08 (-2.05..-0.11) | -1.65 (-2.62..-0.68) |
| late (Oct 28 - Nov 26) | 9,426 | 2,677 | +0.22 (-1.12..+1.56) | -1.17 (-2.52..+0.17) | -1.62 (-2.96..-0.28) |

The two candidate cells (the only cells that met the early-part bar):

| cell | early markets | early net c (t) | late markets | late net c (t; t by day) | result |
|---|---|---|---|---|---|
| updown-15m, 10 min before end, leader 0.50-0.60, buy leader | 409 | +5.13 (2.1) | 423 | +1.93 (0.8; 0.7) | fails late t |
| weather-temp, 6 h before end of local day, favourite 0.98-0.995, buy favourite | 114 | +0.49 (10.8, all won) | 18 | +0.25 (3.6; 3.1) | fails late size (18 < 200) |

## The map by family (pooled over horizons and buckets; cents per share, t by event)

| family | universe/day | weekend share | obs early / late | events early / late | gross fav early | gross fav late | net fav early | net fav late | net long early | net long late |
|---|---|---|---|---|---|---|---|---|---|---|
| counters | 27.5 | 0.07 | 214 / 96 | 58 / 25 | +1.88 (+0.7) | +0.29 (+0.1) | +1.10 (+0.4) | -0.42 (-0.1) | -2.67 (-1.0) | -1.02 (-0.3) |
| crypto-hit | 39.4 | 0.22 | 247 / 121 | 107 / 52 | +0.48 (+0.4) | +4.17 (+4.5) | -0.12 (-0.1) | +3.56 (+3.9) | -1.07 (-0.9) | -4.78 (-5.1) |
| crypto-level | 140.4 | 0.27 | 1666 / 925 | 531 / 278 | +0.61 (+0.4) | -0.57 (-0.4) | -0.44 (-0.3) | -1.55 (-1.0) | -1.66 (-1.2) | -0.42 (-0.3) |
| economics | 15.9 | 0.24 | 340 / 217 | 67 / 48 | +1.96 (+0.9) | +0.97 (+0.2) | +1.13 (+0.5) | +0.14 (+0.0) | -2.80 (-1.3) | -1.81 (-0.5) |
| esports | 231.6 | 0.31 | 691 / 419 | 239 / 122 | +5.06 (+2.0) | +3.05 (+0.8) | +2.98 (+1.2) | +0.97 (+0.3) | -7.16 (-2.8) | -5.16 (-1.4) |
| finance | 112.0 | 0.07 | 683 / 413 | 212 / 117 | +3.77 (+2.4) | +0.60 (+0.2) | +2.36 (+1.5) | -1.02 (-0.4) | -5.21 (-3.3) | -2.25 (-0.8) |
| mentions | 23.1 | 0.27 | 1008 / 299 | 131 / 39 | +1.19 (+0.6) | +6.17 (+1.8) | +0.13 (+0.1) | +5.11 (+1.5) | -2.25 (-1.2) | -7.24 (-2.1) |
| other (culture, tech) | 65.7 | 0.27 | 280 / 185 | 100 / 67 | +4.60 (+2.6) | +6.21 (+4.2) | +3.77 (+2.1) | +5.40 (+3.7) | -5.46 (-3.0) | -7.03 (-4.6) |
| politics | 109.3 | 0.18 | 682 / 327 | 142 / 76 | +0.60 (+0.3) | +7.42 (+3.7) | -0.24 (-0.1) | +6.49 (+3.3) | -1.45 (-0.8) | -8.37 (-4.1) |
| sports-line (spreads, totals) | 1100.2 | 0.55 | 1751 / 1024 | 492 / 243 | -0.22 (-0.1) | -0.16 (-0.1) | -1.92 (-1.1) | -1.88 (-0.8) | -1.50 (-0.9) | -1.60 (-0.7) |
| sports-ml (moneyline) | 589.8 | 0.44 | 2351 / 1417 | 753 / 387 | -4.08 (-2.5) | -0.89 (-0.4) | -6.03 (-3.7) | -2.79 (-1.3) | +2.10 (+1.3) | -1.04 (-0.5) |
| sports-other | 988.2 | 0.45 | 648 / 379 | 195 / 100 | +4.47 (+1.7) | -2.21 (-0.6) | +2.82 (+1.1) | -3.75 (-1.0) | -6.15 (-2.3) | +0.64 (+0.2) |
| updown-15m (crypto) | 407.4 | 0.29 | 2947 / 1848 | 932 / 465 | -1.10 (-0.8) | -0.30 (-0.2) | -2.60 (-1.9) | -1.82 (-1.0) | -0.41 (-0.3) | -1.23 (-0.7) |
| updown-1h (crypto) | 7.2 | 0.24 | 0 / 351 | 0 / 90 | - | -2.78 (-0.9) | - | -3.93 (-1.3) | - | +1.63 (+0.5) |
| updown-4h (crypto) | 21.4 | 0.29 | 1324 / 777 | 394 / 204 | -0.28 (-0.2) | -3.59 (-1.8) | -1.38 (-0.9) | -4.64 (-2.3) | -0.82 (-0.5) | +2.54 (+1.3) |
| weather-other | 12.3 | 0.19 | 285 / 171 | 68 / 34 | +4.18 (+2.2) | +3.18 (+1.1) | +3.42 (+1.8) | +2.49 (+0.9) | -4.93 (-2.7) | -3.88 (-1.4) |
| weather-temp (daily temperature) | 460.7 | 0.29 | 1589 / 457 | 678 / 335 | +1.87 (+1.6) | +1.99 (+1.2) | +1.03 (+0.9) | +1.16 (+0.7) | -2.72 (-2.4) | -2.83 (-1.7) |

How to read: "universe/day" is resolved binary markets per day with volume >= $500 in that family. One market can
appear at up to four horizons, all inside one event cluster. Rows pooled over buckets are descriptive only; the
decision was taken per cell (`out/cells.csv`). The late-part t values of 3-4 for "other", politics and crypto-hit
come from 52-76 events and follow early parts with t 2.1, -0.1 and -0.1: with 17 families x 3 columns x 2 halves,
a few |t| > 3 are expected by chance, and the favourite/long-shot columns are the same fact counted twice.

The shape by price bucket (all families, gross favourite edge, `out/shape.md`): no bucket is consistently positive
except 0.98-0.995 (+0.46..+1.04 c gross at every horizon in both halves, 196-519 markets per cell). That is the
"near-certain side" premium the lab already knows from resolution bonds; after the 0.5 c slippage assumed here it
is +0..+0.5 c a share on a 99 c outlay, and one loss in about 200 trades erases it.

## Opportunities, net per trade, capacity, reaction time

- Opportunities per day: large in raw count (updown-15m 407, weather-temp 461, sports moneyline 590 markets a day),
  but no cell has a positive, confirmed net, so tradable opportunities with an edge: 0 per day.
- Net per trade at 5-20 USD: the screen says about -1.1 to -1.2 c per share for "buy the favourite at the shown
  price" in general, i.e. roughly -1.5% to -2% of the stake (-0.08 to -0.35 USD on a 5-20 USD ticket), worse in
  sports moneylines (-2.8 to -6.0 c/share at a 0.05 fee).
- Capacity for a ~200 EUR account: 0 USD/day of edge.
- Reaction time: not a speed question on this map; the prices tested are minutes to a day old. Speed does not
  rescue a cell whose average after costs is zero or negative.

## Live micro-test

Nothing in this study deserves a live micro-test. No cell passed the pre-registered rule, so there is no rule to
send real orders on. (For scale: proving a 1 c/share edge at 0.70 with t = 2 needs about (2 x 0.46 / 0.01)^2 = 8,500
independent markets; a 50-100 USD test account cannot distinguish edges of this size from noise in any reasonable
time. A live test only makes sense for an edge of 5 c or more, of which none was found.)

## Attacks on the result (why the negative is believable)

- Look-ahead: the price used is the last point at or before (observation time - bucket length), so whatever the API's
  bucket convention, the price was known at the observation time. Observations need the market to be open
  (startDate <= o < closedTime). Anchors are scheduled times (endDate, game start, end of the local weather day), not
  closedTime, so early-resolving markets are not selected by their future.
- Survivorship: the universe is every closed market in gamma with volume >= 500, listed by end date day; unresolved
  markets (outcomePrices not 0/1/0.5) are excluded, 0 in practice after the binary filter.
- Fills: the screen assumes a buy at shown price + 0.5-1 c. NOTES.md says shown prices are often not tradable at
  mid + 1 c (23% in crypto ladders), so the real net is, if anything, lower than shown. Since the screen is already
  negative, the optimistic fill assumption makes the negative conclusion stronger, not weaker.
- Fees: today's rates were applied to old markets; before 2026-11-20 rates were higher in weather, mentions,
  economics and BTC (NOTES.md), so the actual past traders paid more than modelled.
- Sample size: the honest weakness is power, not bias. At cell level most cells have 20-300 events, so edges of
  1-3 c (the size that would matter after a 1-2 c cost) are below what this sample can detect. What the sample can
  say: no family shows an edge of 5 c or more that holds in both halves, and on average shown prices are calibrated
  to within about +-1 c.

## Limitations

- Period is 90 days, not four months (price history is gone beyond ~90 days); the 10-minute horizon exists only
  from 2026-09-28 (5-minute points), so 10-minute cells have 30 days in each half.
- 5-minute crypto up/down markets are excluded (no usable horizon at 5-minute buckets); the lab's tape studies cover
  them. Old-style hourly crypto up/down slugs (before the `*-updown-1h-*` format) fell into `crypto-level` by the
  frozen rule; `updown-1h` has only 90 markets, all late.
- Weather anchor inconsistency (found after the run): 802 of 934 early weather-temp markets have no
  `eventStartTime`, so their anchor is endDate (12:00 UTC of the target day); all 466 late markets have it, so their
  anchor is the end of the local day. Early and late weather horizons therefore point at different local times, and
  late 6 h / 1 h / 10 min weather cells are thin (25-44 markets) because the favourite is usually above 0.995 by then.
- `prices-history` is a mid-like snapshot; no spread or depth is known at the observation time. The fixed slippage
  stands in for the half-spread.
- Clustering is by gamma event; up/down markets of different assets at the same time are correlated (one crypto
  move). The day-clustered t was computed for the decision rule only.
- Sampling caps (400-1,400 markets per family) keep many cells below 100 events; the study had no budget for the
  ~10x larger sample a 1 c resolution would need.

## Ideas, not tested

- Favourites in culture/tech ("other"), politics and crypto one-touch ("hit") markets looked underpriced in the late
  part (+3.6..+6.5 c/share net pooled over buckets and horizons, t 3.3-3.9, 52-76 events), but not in the early part
  except "other" (t 2.1). A fresh pre-registered test on December data, pooled over buckets as a single rule per
  family, with the tape stage for buyability, would settle it cheaply.
- Sports moneyline favourites were overpriced in Aug-Oct (-6 c net, t -3.7): a maker-side idea (rest a bid on the
  underdog a cent under the shown price) cannot be tested without queue data; as a taker the underdog side was +2.1
  c early and -1.0 c late.
- Near-certain bucket (0.98-0.995) across families: +0.5-1 c gross at every horizon in both halves. As a resting bid
  (no fee, no spread paid) it is the resolution-bond trade; it needs an L2 replay for queue position and a long sample
  for the rare loss.
- The 15-minute crypto leader five minutes into the window (+5.1 c early, +1.9 c late): a tape-based test with the
  exact in-window second and Binance state, like btc5m_lockin, rather than 5-minute snapshots.
- A larger sample (all markets, not capped) of the four families with the most markets per day (sports-line,
  sports-ml, weather-temp, updown-15m) would bring cells to 1,000+ events and a ~1 c resolution.
