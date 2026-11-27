# Predicting tennis walkovers hours ahead — results

**Verdict: NO EDGE, nothing to test live.** Hours before the start, only 2.0% of the matches you can actually buy
end in a walkover (153 of 7,641 weighted matches, 1,089 trades), so the extra value of the underdog is
0.42 cents a share, while the 0.05 taker fee at the same prices costs 0.99 cents. To break even the walkover rate
has to be about 5% (2.5 times the base rate). None of the seven public-fact flags gets there. The best flags reach
3.2-3.7% (double duty, doubles, recent retirement) on 17-107 early trades. Measured with real outcomes, the blind
underdog lost -1.71 c/share [-4.47, +1.04] (n = 1,089). The two pre-registered rules on the late period were
-2.39 c [-20.4, +15.6] (n = 30) and +10.1 c [-5.3, +25.5] (n = 46). Both are noise around a structural loss of
about 0.4-0.6 c a share. Resting bids (no fee) fill mostly in matches where no walkover happens: among filled bids
the walkover rate halves, to about 1.0%.

Protocol: `protocol.md` (saved before any outcome statistic; not changed). Code: `s1_build.py` (trades and features),
`s2_analyse.py` (all variants, output `out/s2_tables.txt`), `s3_diag.py` (where the walkovers went, outcome-free
bound, `out/s3_diag.txt`), `out/selection.json` (S1/S2 chosen on the early part). Per-match rows:
`data/gaps_tennis_wo_pred/trades.json` (not in git).

## Question

A Polymarket tennis match market settles 50/50 when a player withdraws before the start. Buying the underdog at
price p therefore earns an extra P(walkover) x (0.5 - p). The questions were: (a) do underdog prices a few hours
ahead already include this premium? (b) Can facts that are public at the moment of the trade flag matches with a
higher walkover rate, so that buying the underdog in flagged matches 1-6 hours ahead pays after the 0.05 sports
taker fee? The flags were tour level, doubles, short rest, a long previous match, a recent retirement, a second
event scheduled at the same time, and the player's walkover history.

## Data

- Period: moneylines with `closedTime` 2026-09-01 .. 2026-11-25 (86 days), from the cached universe of
  `studies/gaps/tennis_walkover` (`data/gaps_tennis_wo/universe.json`). All 830 walkover moneylines (weight 1), plus
  the deterministic 1-in-8 sample of the 21,849 moneylines that resolved 1/0 with volume: 2,734 (weight 8). Final
  prices are confirmed through the Data API. No new downloads.
- Tapes: `data/tape/` (whole-market fills; match time = block time - 3 s).
- Public facts: the 32,604 tennis match events in `data/gaps_tennis_wo/events.jsonl.gz`. These give the schedule,
  previous matches and their closing times, retirements (moneyline 1/0 with the "completed match" market = No), the
  walkover history and creation times. External match-result files were not reachable: JeffSackmann
  `atp_matches_2025/2026.csv` returned 404 and tennis-data.co.uk returned 403. Round and medical timeouts are not
  available.
- Where the 830 walkovers went: 267 were never traded and 62 had no print before the scheduled start. In 348 the
  underdog never printed at 0.05-0.45 in the window: the news was usually already priced, or the market was not
  trading. 153 were tradable by the rule. Of the 2,734 controls, 936 were tradable. Hours ahead, the tradable
  walkover rate is therefore about 2.0%, not the 3.7% of all moneylines.

## What was run (10 taker variants plus 6 maker scenarios)

- The trade (protocol 3): T = scheduled start. Take the first fill print in [T - 6 h, T - 1 h] at which the underdog
  could be bought at 0.05-0.45. Fill at that price for at most the shown size, with targets of $5, $10 and $20.
  Fee 0.05 x p x (1 - p), no rebate, hold to settlement. One trade per match.
- V0: blind underdog. Screening F1-F7 on the early part (7 variants). S1 = the best early edge among flags with 100
  or more early trades, which selected `recent_ret`. S2 = the OR of the flags with an early walkover lift of 1.5 or
  more and 50 or more trades, which selected `double_duty` only. S1 and S2 were run once on the late part.
- Maker scenarios for V0, S1 and S2, fee 0. A bid at p - 0.01 counts as filled only by a later print strictly
  through it, or, in the optimistic version, by a print at the bid.
- Diagnostic cuts that are not variants: price band, series, month, and the outcome-free bound in `s3_diag.py`.
- Split: early = moneyline closed before 2026-10-26 13:35 UTC (55.6 days); late = after that (30.4 days). The unit is
  the match, with weighted standard errors. Clustering by start day changes the t-statistics by at most 0.6 (itf early: -2.48 by match, -3.05 by day).

## Headline numbers (edge per share after fee, 95% CI, clustered by match)

| rule | part | trades (weighted) | walkovers | walkover rate | avg p | edge c/share | t |
|---|---|---|---|---|---|---|---|
| V0 blind | early | 697 (4,911) | 95 | 1.9% | 0.298 | -2.90 [-6.28, +0.48] | -1.68 |
| V0 blind | late | 392 (2,730) | 58 | 2.1% | 0.304 | +0.42 [-4.32, +5.16] | +0.17 |
| S1 recent_ret | early (selection) | 107 (744) | 16 | 2.2% | 0.302 | +6.49 [-2.83, +15.80] | +1.36 |
| **S1 recent_ret** | **late (test)** | 30 (191) | 7 | 3.7% | 0.325 | **-2.39 [-20.39, +15.62]** | -0.26 |
| S2 double_duty | early (selection) | 92 (603) | 19 | 3.2% | 0.303 | +0.75 [-9.26, +10.76] | +0.15 |
| **S2 double_duty** | **late (test)** | 46 (298) | 10 | 3.4% | 0.308 | **+10.10 [-5.27, +25.46]** | +1.29 |

Early screening of the walkover rate (base rate 1.93%, lift in brackets):

| flag | trades | walkovers | rate | edge c/share |
|---|---|---|---|---|
| itf | 270 | 29 | 1.5% (0.77) | -6.36 |
| doubles | 17 | 4 | 3.7% (1.91) | -15.69 |
| short_rest | 54 | 7 | 1.8% (0.94) | -5.92 |
| long_prev | 375 | 44 | 1.6% (0.84) | -2.47 |
| recent_ret | 107 | 16 | 2.2% (1.11) | +6.49 |
| double_duty | 92 | 19 | 3.2% (1.63) | +0.75 |
| wo_history | 180 | 30 | 2.4% (1.26) | +3.11 |

**(a) Is the premium priced in? This cannot be decided from the outcomes, and it does not matter.** Over all 1,089
trades, the gross payoff minus the price was -0.72 c [-3.48, +2.04]. The walkover share of that is +0.42 c. Played
matches alone gave -1.16 c [-3.97, +1.65]. The premium is ten times smaller than the outcome noise: telling 0.4 c
from 0 would take on the order of 100,000 matches. What can be measured without outcomes is decisive anyway. Even if
underdogs were otherwise priced fairly, the premium (+0.42 c) is below the fee (0.99 c) in both parts (early -0.56 c,
late -0.59 c), and below it for every flag in both parts (premium minus fee from -0.09 to -0.76 c). The required
walkover rate is about 5% overall and 9.8% for underdogs at 0.30-0.45.

Why the measured edges swing between -6 and +10 c: whether the underdog wins a played match moves every number by
plus or minus 0.45 per share. With 30-100 trades that swamps a 0.5-cent effect. The S2 late +10 c corresponds to a
walkover rate of 3.4% and a premium of 0.63 c. The rest is ordinary underdog wins.

## Opportunities, size, net per trade, capacity

- Trades available: about 620 a week for blind underdog buys (weighted). The flags give 44-94 a week (recent_ret
  94 early and 44 late; double_duty 76 and 69).
- Size: the median first print shows $4.76 (p25 $1.85, p75 $13.34). Only 48% of $5 trades, 32% of $10 trades and
  20% of $20 trades fill in full from that print. The median dollar volume of underdog fills at <= 0.45 in the
  whole 5-hour window is $23 (p75 $214). The median trade is 4.4 h before the start.
- Net per trade, V0, all 86 days: -$0.15 at $5, -$0.12 at $10, -$0.17 at $20 (filled $3.51 / $5.28 / $7.57 on
  average).
- Capacity for an account of about 200 EUR: **$0 a day.** No rule has an expected value above zero once the fee is
  paid. Capital is not the limit: each trade is $5-20 and settles within hours.
- Reaction time needed: none. The rule acts hours ahead. Speed is not what fails here; the ratio of fee to premium is.

## Maker scenarios (fee 0, optimistic)

- V0, bid filled only by a print strictly through it: 477 of 1,089 bids fill (47% weighted). The walkover rate among
  filled bids is about 0.95%, half the base rate. A walkover pushes the underdog up towards 0.50, so a resting bid
  under the market rarely fills in exactly the matches it was placed for. Edge -0.04 c [-4.07, +4.00]. Net per
  placed $20 bid is -$0.12 early, -$0.39 late and -$0.22 overall.
- S1 and S2 maker lines are +4.5 to +6.1 c per filled share overall, with CIs from -7.5 to +17.2. They rest on 62-100
  fills and change sign between the parts (S1 at the bid price: +8.59 c early, -1.82 c late). They are noise, not
  evidence.

## Live micro-test

Nothing here deserves one. None of the rules passes the protocol's decision rule (late lower CI bound above 0, at
least 100 late trades, at least 15 walkovers, positive early edge). The outcome-free bound is negative for every
flag in both parts.

## Attacks on the result (a negative result checked too)

- Look-ahead: the features use only events closed (`closedTime`), or created (`createdAt`), before the trade's match
  time. The tradable set uses the price at the trade and no later information. The walkover class is not used to
  choose trades.
- Is the walkover rate too low because of the window? Walkovers announced before T - 6 h are already priced near
  0.50 and cannot be bought cheaply, so excluding them is correct, not a bias. Those announced inside the window but
  after the trade are counted. A shorter lead time would catch more of them, but the earlier study shows that this
  is the 2-second race.
- Sample: 1,089 trades, 153 walkovers. Late-part flags have only 30-46 trades. The structural bound does not depend
  on that small sample: it needs only the walkover rate, about 2-3.7%, against the fee at the same prices.
- Feature noise: surname matching for doubles players can create false double-duty flags, and the previous match's
  length is measured to the market's close (resolution lag included). Better features would need a walkover rate 2.5
  times the base rate. The best flags here reach 1.6-1.9 times.

## Limitations

- No external match data: round, ranking, medical timeouts and entry lists are missing. Tour level, schedule,
  retirements and walkover history come from Polymarket's own event list, and the history starts 2026-08-20.
- Late-season fatigue cannot be tuned on an early part that ends in October. Only the monthly cut is shown
  (Sep -4.34 c, Oct -0.69 c, Nov +0.20 c; n = 389 / 382 / 316).
- Fills use one print at the shown size. The book was not replayed, so a $20 order is often only partly filled.
- Moneylines that resolved anything other than 0.5/0.5 or 1/0 are not in the universe, and controls are a 1-in-8
  sample with weight 8.

## Ideas, not tested

- Cheap underdogs (0.05-0.15): the fee is only 0.45 c, so the premium (0.88 c) exceeds it if these underdogs are
  otherwise priced fairly. Played-match calibration in this band is unknown (-1.53 c [-6.45, +3.39], n = 131), and the
  usual longshot bias would work against it. This band was chosen after seeing the table, so it is not a result.
  Measuring it would take thousands of matches of tape.
- The `tennis_completed_match` market resolves No = 1.0 on a walkover and on a retirement. In a flagged match its
  "No" is a direct bet on both, with a payoff twice that of the 50/50 legs. Check its prices and fee.
- External features (ranking gap, travel between tournaments, entry lists for the next week's events) could raise
  the walkover lift. They would need to reach about 2.5 times the base rate.

## What this means for the owner's question about infrastructure

For this route no server or speed helps: the loss comes from the fee and the premium, not from latency. The money in
tennis walkovers is in the first 2 seconds after the news (`studies/gaps/tennis_walkover`: 75% of the $480K taken
below 0.45 went in the first 2 s, to 229 takers, three of whom took 55%). Competing for it would take three things:

- A withdrawal source faster than the book, such as the WTA live-scoring API polled every second or the ATP, ITF and
  order-of-play feeds.
- The market WebSocket.
- Orders already signed and sent from a server close to the London matching engine, in a country Polymarket allows.

That is a race against more than 100 wallets, not a gap of several seconds.
