# Bookmaker lines as a signal for pre-game soccer on Polymarket — results

Study run 2026-11-27 (about 25 minutes of compute and download). Protocol: `protocol.md` (frozen before any outcome
number). Code: `fetch.py` (sample), `analyze.py` (protocol runs), `diag.py` (post-hoc diagnostics, marked as such).
Raw outputs: `out/report.txt`, `out/variants.csv`, `out/diag.txt`. Data: `data/gaps_cross_venue_signal/` (not in git).

## Verdict: NOTHING TO TEST HERE (clean negative)

- **Polymarket and the Betfair Exchange price soccer matches almost identically.** Over 724 matches (six European
  leagues, 14 Aug - 25 Nov 2026), the median gap between the Polymarket taker price and the de-margined Betfair
  Exchange price is 0.4-0.6 points, and Polymarket is as accurate as the exchange (log-loss 0.9636 vs 0.9630 a day
  before kick-off, 0.9629 vs 0.9623 at 30 minutes before; per-match difference +0.0006 +- 0.0013).
- **A gap of 3 points or more that you could actually buy hardly ever happens.** With the protocol rule (first taker
  buy on the tape within 30 minutes of the signal that is at least X points under the bookmaker value) there were 8
  trades in 724 matches with the tradable Friday/Tuesday signal (S1) and 6 with the near-closing signal (S2) at X = 3
  points, 1 and 0 at X = 5, and 0 and 0 at X = 8. That is about 0.06-0.08 trades a day. No variant reached the 20
  trades the protocol requires to be chosen, so the decision rule fails before any profit question arises.
- **When a big gap does appear, the stale price is usually the bookmaker's, not Polymarket's.** The Friday exchange
  line moved 54% of the way to Polymarket's price by kick-off, Polymarket moved 39% of the way to the Friday line;
  of 81 outcomes with a gap of 2+ points, the bookmaker moved toward Polymarket in 62. Of the 8 S1 trades
  ("buy what is cheap against the Friday line") 5 lost. This repeats the OddsPapi observation in the catalog.
- **A looser post-hoc rule does not rescue it.** Buying the first print that is cheap enough to beat the fee at all
  (expected edge > 0 after fee; a post-hoc variant, counted, cannot change the verdict) gave -33% and +5% per dollar
  on S1 (28 / 36 trades, early / late, CIs about +-40 points) and -12% and -5% on S2 (71 / 90 trades). The signal
  itself promised only +1.2 to +2.0% per dollar, less than the noise of a few dozen soccer bets.
- **For the owner's weekend question:** soccer is mostly a weekend product (353 of 724 matches on Saturday, 195 on
  Sunday, UTC) and liquid (median $20K of taker buys per match in the last 30 minutes), so weekend markets exist.
  But this signal gives nothing on any day: the price is already right to within the 1.25-cent fee.

## Question

Some hours before kick-off, when the Polymarket price of a soccer match outcome differs from the de-margined
bookmaker price by at least X points, does buying the side that is cheap on Polymarket (taker, Polymarket only; the
bookmaker is only a signal) make money after the 0.05 sports taker fee? Tennis was part of the brief but was dropped:
tennis-data.co.uk returns a Cloudflare 403 to this sandbox.

## Data

- **Odds:** football-data.co.uk 2026/27 files E0 (Premier League), E1 (Championship), SP1, D1, I1, F1, downloaded
  2026-11-27 18:33 UTC. The 2026/27 files carry **no Pinnacle columns**; the sharpest price in them is the Betfair
  Exchange (BFEH/D/A pre-closing, BFECH/D/A closing), present on 751 of 752 rows (all three
  pre-closing prices on 719 of the 724 matched, closing on 724) and used for every traded match (the
  `Avg` fallback covered 5 matches for S1, none of them traded). Pre-closing odds are collected "Friday afternoons for weekend games, Tuesday
  afternoons for midweek games" (football-data notes); closing odds are the last before kick-off.
- **Polymarket:** gamma match events (tags `premier-league`, `efl-championship`, `la-liga`, `bundesliga`, `sea`,
  `ligue-1`), three moneyline markets per match; whole tapes from the Data API (2,172 markets, 0 errors; 243 tapes
  reused from `data/gaps_sports_lag/`).
- **Sample:** 752 football-data matches; 724 matched (start times agree to the minute in all 724; 28 not matched
  because the name similarity stayed under the fixed 1.2 threshold: QPR, Racing Santander and similar). All 724
  had three markets resolved 1/0 that agree with football-data's result. By league: E0 110, E1 192, SP1 114, D1 90,
  I1 120, F1 98. Early part 360 matches (14 Aug - 10 Oct), late part 364 (10 Oct - 25 Nov).

## What was run

Fair value: proportional de-margining of the Betfair Exchange three-way odds. Fill: the first taker BUY print (block
time) of any of the six tokens (Yes and No of home, draw, away) within 30 minutes after the decision time whose price
is at least X under fair; price = print price, size capped by the print; fee 0.05 * p * (1 - p); 10 USD per trade.

| # | variant | decision time | status |
|---|---|---|---|
| 1-3 | S1: pre-closing Betfair line, X = 3 / 5 / 8 points | latest Tue/Fri 18:00 UTC at least 30 min before kick-off (median 22.5 h before) | protocol |
| 4-6 | S2: closing Betfair line, X = 3 / 5 / 8 points | kick-off - 30 min (mild look-ahead: the close includes the last 30 min) | protocol |
| 7-8 | first print with fair - price - fee > 0, S1 and S2 | as above | post-hoc, counted |
| - | fee = 0 re-run of 1-6; log-loss / Brier of PM vs S1 vs S2; who-leads regression; gap distribution | - | diagnostics |

Eight trading variants in total.

## Headline numbers (return per dollar staked, after the 0.05 fee; one trade per match; 95% bootstrap CI)

| variant | early n | early ret/$ [CI] | late n | late ret/$ [CI] |
|---|---|---|---|---|
| S1 X=3 | 5 | -38% [-103, +34] | 3 | -35% [-103, +102] |
| S1 X=5 | 1 | -103% | 0 | - |
| S1 X=8 | 0 | - | 0 | - |
| S2 X=3 | 2 | -17% [-102, +67] | 4 | +79% [+56, +112] |
| S2 X=5 | 0 | - | 0 | - |
| S2 X=8 | 0 | - | 0 | - |
| post-hoc S1, edge > fee | 28 | -33% [-67, +5] | 36 | +5% [-34, +44] |
| post-hoc S2, edge > fee | 71 | -12% [-36, +14] | 90 | -5% [-33, +30] |

The S2 X=3 late line (+79%, 4 wins out of 4) is four bets with a stated edge of 3 points each; it means nothing.
Without the fee every protocol variant has the same sign (fee is 1.1-1.25 c/share at these prices).

How tradable gaps are, all taker BUY prints in the windows (`out/diag.txt`):

| window | matches with any print | prints | median fair - price | p90 | p99 | prints with gap >= 3 pts |
|---|---|---|---|---|---|---|
| S1, 22 h before (median) | 372 of 724 | 6,401 | -0.42 pts | +1.47 | +6.79 | 169 (2.6%), 115 of them in one match |
| S2, last 30 min | 717 of 724 | 99,242 | -0.41 pts | +0.54 | +1.60 | 138 (0.14%) |

A day before kick-off half the matches have no taker buy at all in 30 minutes; most of the S1 large gaps sit in one
match (Sevilla - Valencia, 11 Sep: Friday line 0.48, Polymarket 0.50, close 0.53, Polymarket was right).

## Opportunities, size, capacity, reaction time

- **Opportunities per day:** 8 S1 trades in 103 days at X = 3 (0.08/day), 6 S2 trades (0.06/day); 0 at X >= 5 in the
  late part.
- **Net per trade at 5-20 USD:** not estimable (n <= 5 per part); the expected edge stated by the signal at X = 3 is
  about 3.5 points minus a 1.2-cent fee, about +4% per dollar, i.e. +0.2 to +0.8 USD per 5-20 USD bet, before the
  evidence that the bookmaker side is the stale one. Realised: -35% to -38% per dollar on S1.
- **Capacity for a ~200 EUR account:** effectively zero (well under 1 USD a day of expected profit). Liquidity is not
  the constraint: the last 30 minutes carry a median $20K of taker buys per match; the constraint is that the
  price is already right.
- **Reaction time:** not the issue. S1 is a minutes-to-hours trade (median about 9 minutes from the signal time to the print used, 8
  trades); S2's prints came a median 15 s after its decision time (6 trades), and S2 would need a live exchange feed checked within a minute or so. Speed does not create a gap that is not there.

## Live micro-test

Nothing here deserves one. The tradable variant had 8 trades in 724 matches and lost on them; even the looser
post-hoc rule shows no positive sign, and the gap that appears is mostly the bookmaker being stale. Spending the
test account on this would measure noise.

## Free sources of live or near-live odds (checked from this sandbox on 2026-11-27)

| source | access | what it gives | note |
|---|---|---|---|
| Smarkets exchange `api.smarkets.com/v3/` (`events`, `markets/<id>/quotes/`, `last_executed_prices/`) | public, no key, REST, works | live back/lay ladder in basis points (6211 = 62.11%) for football and more | the best free live sharp-ish signal found; exchange with ~2% commission |
| ESPN site API scoreboard `competitions[].odds` | public, works | DraftKings moneylines incl. draw | a soft US book; good for "what the US retail price is" |
| football-data.co.uk | free CSV, works | Betfair Exchange, Bet365, Avg/Max pre-closing (Fri/Tue) and closing | twice a week, not live; no Pinnacle in 2026/27 |
| Kalshi public market data | public, works (catalog r4) | soccer/US sports game lines | already identical to Polymarket to the cent (r4 snapshots) |
| The Odds API, OddsPapi | free tier needs a key (401 without) | many books incl. Pinnacle (OddsPapi) | key = account; not tried |
| Betfair Exchange API | 403 without an app key | the deepest exchange | needs an account and app key; eligibility from Serbia not checked |
| oddsportal.com, betexplorer.com | pages load (200) | historical and current odds | scraping; terms of use not checked; JavaScript-rendered |
| tennis-data.co.uk | Cloudflare 403 here | tennis Pinnacle/B365 closing odds | not usable from this sandbox |

## Limitations

- No Pinnacle: the 2026/27 football-data files dropped it; Betfair Exchange is the reference. Betfair's back price
  is close to fair (median overround 0.8% pre-closing, 0.6% closing, 719 / 724 matches), so this is a fair test of "a sharp line", but not of Pinnacle itself.
- The pre-closing collection time is only "Friday / Tuesday afternoon"; the protocol uses 18:00 UTC as the earliest
  time the line surely exists. If the real collection is earlier, S1's line is staler than assumed, which only
  makes S1 worse.
- Fills are taker prints (VWAPs), not the book; a resting order could get better prices, but a maker leg was not in
  the question.
- Tennis is not covered (source blocked). Only six European leagues; other leagues or US sports could differ.
- Fee 0.05 is applied to the whole period; earlier sports rates were lower for some leagues, which does not matter
  here since the verdict holds even gross.

## Ideas, not tested

- Paper-log Smarkets best back/lay against Polymarket books every 30-60 s over two weekends (both are REST, no key):
  counts how often a 2+ point live gap with size exists and how long it lasts. Only worth doing if the owner wants a
  definitive "live" answer; the archive says the level gap is ~0.5 points.
- Lineup news (team sheets about 60 minutes before kick-off) as the event: the catalog's "stale-quote taking on
  team news" candidate. Here S2 at -30 min already includes it and shows no gap at the print level.
- Smaller, less liquid leagues where Polymarket may lag more (Polymarket lists many; football-data covers some).
