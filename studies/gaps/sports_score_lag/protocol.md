# Sports in-play score lag — protocol (frozen 2026-11-27 ~18:35 UTC, before any outcome statistic)

Catalog family: `sports-inplay-latency`. Author: Claude (workflow subagent). Budget: about 110 minutes wall-clock.

## Question

After a scoring event in a live game (a soccer goal, an NFL score), how long do pre-event ("stale") prices stay
buyable on Polymarket, how many dollars trade at stale prices, within how many seconds, and how many wallets take
them? Does a follower who acts 3, 10 or 60 seconds after the event, or after the first price move on the
Polymarket tape, make money after the 0.05 sports taker fee? Weekend relevance: soccer leagues and the NFL play on
Saturday and Sunday.

## What was inspected before writing this (no outcome numbers)

- ESPN site API (`site.api.espn.com/apis/site/v2/sports/...`) returns, per game, plays with a second-level
  `wallclock` (NFL `drives.previous[].plays[]`, soccer `keyEvents[]` with `scoringPlay`). Free, public.
- Gamma soccer events have three Yes/No moneyline markets (home win, draw, away win; slug suffixes), NFL events a
  moneyline market whose slug equals the event slug with team-name outcomes. `secondsDelay = 1` and
  `feeSchedule.rate = 0.05` on the markets checked.
- `trades?condition=` returns a complete tape (one EPL market: 909 taker rows, share sum = gamma `volumeNum`).

## Data and sample (fixed in advance)

- Soccer: ESPN leagues `eng.1, esp.1, ger.1, ita.1, fra.1, uefa.champions, uefa.europa`, kickoff
  2026-11-21 00:00 to 2026-11-27 00:00 UTC. A match is kept if a gamma event with the three moneyline markets is
  found (kickoff within 20 minutes, team names match) and all three tapes download.
- NFL: every ESPN game with kickoff 2026-11-20 00:00 to 2026-11-27 06:00 UTC that has a Polymarket moneyline market.
- If downloads do not fit the budget: process matches in kickoff order and stop at a match count, stated under
  Limitations.
- Events: soccer `keyEvents` with `scoringPlay` true (own goals and penalties included, shoot-outs excluded); NFL
  `scoringPlays` joined by play id to the play's `wallclock` (events with no wallclock dropped). An event is dropped
  if another event of the same game has a wallclock less than 180 s before it (contaminated pre-window).
- Event time T_e = ESPN wallclock. Tape times: match time = block time - 3 s (lab rule).
- Favoured token per market: soccer scoring team's win market -> Yes; other team's win market -> No; draw market ->
  Yes if |goal difference| after the goal is smaller than before, else No. NFL moneyline -> the scoring team.
- Tape conversion: a taker BUY of token X at p means X was buyable at p; a taker SELL of the other token at q means X
  was buyable at 1 - q (mirror books). Same for "sellable".
- P_pre = median price of all prints (converted to the favoured token) with match time in [T_e - 120, T_e - 10].
  Events whose market has fewer than 1 print in that window, or P_pre outside [0.05, 0.95], are skipped for that
  market.

## Descriptive measures (no rule, the "stale pool")

For each (event, market) with P_pre defined: P_post = median converted price in [T_e + 120, T_e + 300];
J = P_post - P_pre. Only J >= 0.05 enters the pool tables. "Stale buy" = a buyable print of the favoured token with
match time >= T_e - 30 and price <= P_pre + J/2. Report: dollars, shares, profit locked
(P_post - price - fee) x shares, distribution of (match time - T_e), distinct taker wallets, per sport and period.
Also the time from T_e to the first print at >= P_pre + J/2 (reprice time), which also calibrates the ESPN clock.

## Strategy variants (12 in total, no others)

Trigger x delay, per sport (soccer, NFL):

- Trigger E (event clock): t_trig = T_e. Upper bound for someone with a feed as fast as ESPN's wallclock.
- Trigger T (tape clock): t_trig = first match time in [T_e - 30, T_e + 300] at which a print of the favoured token
  (converted) is at >= P_pre + 0.03. Implementable by watching Polymarket alone plus knowing a score happened.
- Delay d in {3, 10, 60} s. Order reaches matching at t_a = t_trig + d + 1 (the 1 s sports taker delay).

Fill: the first buyable print of the favoured token with match time in [t_a, t_a + 30]; fill price = that print's
price; shares = min(print shares, 20 USD / price). No print -> no trade. One trade per (event, market).

PnL per share, two measures:
1. Hold to resolution (primary, money): final price of the token - price - 0.05 p (1 - p).
2. 5-minute markout (diagnostic): median converted price of all prints in [t_a + 240, t_a + 360] - price - fee.

Unit and errors: the game (match). Edge per share = sum PnL / sum shares with errors clustered by game
(`pmlab.stats.ratio_cluster`); 95% interval = +-1.96 se. Net per trade in USD at the 20 USD cap.

## Time split

Early = kickoff before 2026-11-24 00:00 UTC (weekend of 21-23 Nov); late = kickoff from 2026-11-24 (UCL/UEL
midweek, Thanksgiving NFL). Nothing is tuned; both parts are reported separately.

## Decision rule

A variant deserves a live micro-test only if, in the late part, hold-to-resolution net > 0 with t >= 2 by game AND
markout net > 0 with t >= 2, the early part has the same sign on both, and the late part has >= 30 trades. Among
qualifying variants the live test uses the trigger-T variant with the smallest d (implementable); if only trigger-E
variants qualify, the answer is "needs a faster feed than we have", not a test. Otherwise: nothing to test.

## Attacks planned on any positive result

Look-ahead (P_pre and trigger use only the past; P_post only in descriptive tables), fills (shown size only, first
print after t_a), ESPN clock error (reprice-time distribution), small sample (games, not trades), outcome luck
(markout vs hold).
