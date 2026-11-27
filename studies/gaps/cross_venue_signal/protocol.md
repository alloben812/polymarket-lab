# Bookmaker lines as a signal for pre-game soccer on Polymarket — protocol

Frozen 2026-11-27 ~18:50 UTC, before any outcome-based statistic was computed. Catalog family `cross-venue-arb`.
Author: Claude (workflow subagent). Budget: about 110 minutes wall-clock in total.

## Question

Some hours before kick-off, when the Polymarket price of a soccer match outcome differs from the de-margined
bookmaker price by at least X points, does buying the side that is cheap on Polymarket (taker, Polymarket only;
the bookmaker is only a signal) make money after the 0.05 sports taker fee? Secondary: list the free sources of
live odds a small trader could use as the signal.

## What was inspected before writing this (formats only, no outcome numbers)

- football-data.co.uk current-season CSVs (`https://football-data.co.uk/mmz4281/2627/<DIV>.csv`, the `www.` host
  redirects there) are reachable. 2026/27 files have NO Pinnacle columns. They have pre-closing and closing 1X2
  odds of Bet365, Betfred, BetVictor, Betway, Paddy Power, Sky Bet, Max, Avg and **Betfair Exchange (BFEH/BFED/BFEA,
  closing BFECH/BFECD/BFECA)**, present on 751 of 752 rows of E0, E1, SP1, D1, I1, F1 (Aug 14 - Nov 25 2026).
  Official notes: "Betting odds for weekend games are collected Friday afternoons, and on Tuesday afternoons for
  midweek games"; closing odds are the last before kick-off. `Time` is UK local time.
- tennis-data.co.uk returns a Cloudflare 403 to this sandbox (all URLs tried): **tennis is dropped** from the study.
- Gamma tags with match events: `premier-league` (epl-), `efl-championship` (elc-), `la-liga` (lal-), `bundesliga`
  (bun-), `sea` (Serie A), `ligue-1` (fl1-). A match event has three Yes/No moneyline markets (home win, draw, away
  win). Data API `trades?condition=` ignores start/end: whole tapes must be paged. Tapes of 243 soccer markets of
  21-26 Nov are already cached in `data/gaps_sports_lag/tapes/` (median 543 rows) and are reused.

## Data and sample (fixed in advance)

- Leagues: E0 (Premier League), E1 (Championship), SP1, D1, I1, F1. Matches in the football-data files whose
  Polymarket event can be matched (gamma event with 3 moneyline markets, start within 3 h of the football-data
  kick-off converted from Europe/London to UTC, team-name similarity score >= 1.2 as in
  `studies/gaps/sports_score_lag/fetch.py`).
- Outcome: football-data `FTR` (H/D/A). Cross-check against gamma `outcomePrices` of closed markets; matches where
  they disagree, or the market is not resolved 1/0, are dropped and counted.
- Download order: newest kick-off first. Tape downloads stop at 19:40 UTC whatever has been fetched; the sample is
  then "the most recent N matches", stated under Limitations. Request rate: at most 3 parallel workers.

## Signals (de-margining: proportional, p_i = (1/o_i) / sum_j (1/o_j) over H, D, A)

- **S1 (tradable): Betfair Exchange pre-closing odds** (BFEH/D/A; if missing, AvgH/D/A, counted). Decision time
  E1 = the latest Tuesday or Friday 18:00 UTC that is at least 30 minutes before kick-off (the collection is "Friday
  / Tuesday afternoon" UK time, so by 18:00 UTC the odds exist). If E1 is more than 96 h before kick-off, the match
  is dropped for S1 (counted). No look-ahead: the signal exists at E1.
- **S2 (near-close, mild look-ahead): Betfair Exchange closing odds** (BFECH/D/A; fallback AvgCH/D/A, counted).
  Decision time E2 = kick-off - 30 min. The closing line includes the last 30 minutes of movement, so S2 is an
  upper bound for a trader who reads a live exchange price at E2; it is not a backtest of an existing feed.

## Fill rule (taker, conservative)

- Six candidate tokens per match: Yes and No of home, draw, away. Fair value of Yes = p_i, of No = 1 - p_i.
- A candidate trade is a taker BUY print of that token on the tape (block time) in [E, E + 30 min]. Its price is the
  print price (a VWAP of that taker order, so the best ask was at or below it); its size is capped by the print size.
- The trade taken for the match is the FIRST print in time (across the six tokens) with fair - price >= X. One trade
  per match per variant. If none, no trade.
- Fee: 0.05 * p * (1 - p) per share (today's sports rate, applied to the whole period whatever was charged then).
  Rebates 0. P&L per share = 1{token wins} - price - fee. Return per dollar = P&L per share / price.
- Stake model: 10 USD per trade (shares = 10 / price, capped by the print size). Headline in return per dollar staked
  and c/share; dollar figures at 10 USD.

## Variants (all reported)

- S1 x X in {0.03, 0.05, 0.08}: 3 variants. S2 x X in {0.03, 0.05, 0.08}: 3 variants. Total 6 trading variants.
- X is chosen per signal on the early part (highest mean return per dollar with at least 20 trades; ties -> larger
  X), then all three X are reported on the late part, the chosen one marked.
- Diagnostic (not a trading rule, counted separately): log-loss and Brier score of the three-way probability from
  (a) the Polymarket last trade price before E1 / E2 normalised over the three Yes tokens, (b) S1, (c) S2, on the
  matches that have all three. Also: share of the gap |PM - S1| at E1 that is closed by kick-off - 30 min.

## Time split and clustering

- Early = first half of the final matched sample by kick-off time, late = second half (split date stated in
  results). Unit = match (one trade per match per variant); errors: t-interval on per-match return per dollar, and
  a bootstrap 95% CI over matches; robustness: clustering by kick-off calendar day.

## Decision rule

- "Worth a live micro-test" only if the chosen variant of S1 (the tradable one) has, on the LATE part, mean return
  per dollar > 0 with the 95% CI lower bound > 0 or at least t >= 1.5 with >= 40 trades, AND the same sign on the
  early part, AND the result survives the attacks below. S2 alone cannot justify a live test of S1; if only S2 is
  positive the verdict is "needs a live feed test, paper only" (no money).
- Otherwise: "nothing to test here".

## Attacks planned on any positive result

Look-ahead (decision time vs odds collection; S2 is flagged by construction), fills (print size, how many dollars
all takers got at the same prices = the pie), concentration (top matches removed), league split, favourite vs
long-shot split, fee sensitivity.
