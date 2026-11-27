# Sports in-play score lag (soccer goals, NFL scores): can a few-seconds follower buy stale prices? — results

Study run 2026-11-27. Protocol: `protocol.md` (written and frozen before any outcome number). Code: `fetch.py`
(data), `sanity.py` (data checks), `analyze.py` (the protocol: stale pool + 12 variants), `diag.py` and `attack.py`
(post-hoc diagnostics and attacks, marked as such; they do not change the verdict). Outputs: `out/report.txt`,
`out/variants.csv`, `out/event_markets.csv`, `out/diag.txt`, `out/attack.txt`. Raw data: `data/gaps_sports_lag/`.
Catalog family: `sports-inplay-latency`.

## Verdict: NOTHING TO TEST — no variant meets the decision rule; the stale window is about 1 second

- **No variant passes the frozen rule.** It required hold-to-resolution net > 0 with t >= 2 by game in the late part,
  together with a positive 5-minute markout with t >= 2, the same sign in the early part and >= 30 late trades. In
  soccer the hold result is indistinguishable from zero in every variant (late part -0.8..+2.6 c/share, se 2.7-3.6,
  t <= 0.8). NFL is negative or pure noise (5 late games; the one late hold with t 2.7, `nfl-T10`, has a markout of
  +0.3 c and -6.8 c/share with t -6.0 in the early part).
- **Stale prices last about one second after the market starts moving.** Soccer, 211 goal-markets in 68 games:
  $242.9K was bought at "stale" prices (below halfway between the pre-goal level and the level 2-5 minutes later),
  and $190.0K of that (78%) printed in the same 0-1 s as the first move. That means it was matched before or
  together with the first reacting print. 4 s or more after the first move there was $49.2K in 6 days across 170
  wallets (profit locked vs the later level: about $19K, and $11.7K of that more than 60 s later, which is mostly
  noise around the new level). NFL: $516K, 98% of it in the first second (one wallet, about $600K at 0.93 in one game).
- **The free public clock is behind the market.** ESPN's per-play `wallclock` for soccer goals comes a median 5 s
  AFTER the first print at the halfway price (p10 -9 s, p90 +15 s; 331 of 411 goal-markets repriced before ESPN's
  time). A follower who uses ESPN can never be early. For the NFL the ESPN time is earlier than the market (median
  +7 s), which suggests it stamps the start of the play rather than the score.
- **The only positive signal is conditional on information a follower cannot get in time.** If you already know
  that a goal happened (and stood), then buying the moved side 4 s after the first move and selling 5 minutes later
  at the bid earns +3.0 c/share after two fees (t 3.2; early +2.6, t 2.9; late +3.4, t 2.1; 292 trades in 72 games;
  post-hoc). The market keeps drifting after a goal: 59% of the final move at the first print, 78% at +10 s, 93% at
  +60 s. A trader watching only the tape does not know which jump is a goal: with the same +3 c trigger on the tape
  alone, 803 of 1,123 in-play triggers were not goals, and those lost 2.6 c/share on the round trip (t -2.8). All
  triggers together: -1.1 c/share round trip (t -1.3), +0.5 c/share held to resolution (t 0.2). ESPN's list holds
  only goals that stood; at least 6 goals were overturned by VAR in these 81 matches. So the +3 c also contains look-ahead.
- **For the owner (weekend question).** Weekend sports are where the volume is (42 of 81 soccer matches and 10 of 17
  NFL games in this sample were on Saturday or Sunday). But the time gap after a score is a race measured in
  fractions of a second, against wallets that see the event before any free feed. A program on a Mac in Serbia with
  a few seconds of reaction gets only what remains after that race, and what remains is not positive after the 0.05
  fee. Sports in-play latency is not a weekend strategy for this account.

## Question

After a scoring event in a live game, how long do pre-event prices stay buyable on Polymarket? How many dollars
trade at those stale prices, within how many seconds, and by how many wallets? Does a follower who acts 3, 10 or
60 s after the event (by a public clock) or after the first price move on the Polymarket tape make money after the
0.05 sports taker fee and the 1 s sports taker delay?

## Data

- Period: kickoffs 2026-11-20 01:15 to 2026-11-27 01:20 UTC (soccer 21-26 Nov, NFL 20-27 Nov).
- Games: 98 = 81 soccer matches (Premier League 10, Serie A 10, La Liga 9, Bundesliga 8, Ligue 1 8, Champions
  League 18, Europa League 18) + 17 NFL games. That is every finished ESPN game in the protocol window; each was matched to
  a Polymarket moneyline event by kickoff time and team names.
- Markets: 260 (3 per soccer match: home / draw / away Yes-No; 1 moneyline per NFL game). The whole-market tapes
  of all 260 were downloaded complete (data API `trades?condition=`; 100-5,200 taker rows each).
- Scoring events: 398 from ESPN's site API (`keyEvents` with `scoringPlay` for soccer, `scoringPlays` joined to
  play `wallclock` for the NFL); 385 left after the 180 s overlap rule. 837 event-markets, of which 595 had a pre-event
  price in [0.05, 0.95] (171 outside, 71 with no print in the 110 s window before the event).
- Checks (`sanity.py`): the ESPN running score reproduces the Polymarket resolution in 98 of 98 games (own goals
  included). `secondsDelay = 1` on all 260 markets: sports taker orders wait one second before matching. Fee
  rate on gamma: 0.05 on 259 markets and 0.03 on one (Colts-Texans, Nov 20). 0.05 is used throughout.
- Split: early = kickoff before 2026-11-24 00:00 UTC (weekend 21-23 Nov; 45 soccer, 12 NFL); late = 24-27 Nov
  (Champions/Europa League midweek, Thanksgiving NFL; 36 soccer, 5 NFL).

## What was run

Protocol variants: 12 = {soccer, NFL} x trigger {E: ESPN wallclock, T: first print >= 3 c above the pre-event
median} x delay {3, 10, 60 s}, each order arriving at trigger + d + 1 s, filled at the first buyable print within
30 s, capped at the print's size and 20 USD, scored as hold-to-resolution (primary) and 5-minute markout. Plus the
descriptive stale pool.

Post-hoc, not part of the verdict (counted here): (d) round trip with a sell at the bid 5 minutes later for the 6
trigger-T variants; (e) markout against sell-side prints only for the same 6; (f) one tape-only trigger
(`attack.py`, soccer, d = 3). The total is 12 protocol variants and 13 post-hoc runs.

## Headline numbers (c/share after the 0.05 fee; 95% CI = +-1.96 se, clustered by game)

### Protocol variants, soccer (`out/variants.csv`)

| variant | part | trades | games | avg price | hold to resolution | markout 5 min |
|---|---|---|---|---|---|---|
| E3 | early | 183 | 43 | 0.76 | +2.1 (-4.6..+8.8) | +2.3 (+0.7..+3.8) |
| E3 | late | 164 | 34 | 0.72 | -0.8 (-6.8..+5.3) | +2.5 (0.0..+5.1) |
| E10 | early | 182 | 43 | 0.76 | +0.9 (-6.6..+8.4) | +1.8 (-0.2..+3.8) |
| E10 | late | 164 | 33 | 0.73 | 0.0 (-5.2..+5.3) | +2.4 (-0.4..+5.2) |
| E60 | early | 204 | 43 | 0.76 | -1.2 (-6.8..+4.3) | +1.5 (-0.2..+3.1) |
| E60 | late | 179 | 34 | 0.73 | +2.6 (-4.2..+9.4) | +0.9 (-0.2..+1.9) |
| T3 | early | 190 | 43 | 0.75 | +0.3 (-6.6..+7.1) | +3.0 (+1.4..+4.6) |
| T3 | late | 172 | 34 | 0.73 | -0.2 (-7.4..+6.9) | +3.7 (+1.0..+6.3) |
| T10 | early | 176 | 43 | 0.76 | +2.8 (-5.2..+10.7) | +2.2 (+0.6..+3.8) |
| T10 | late | 168 | 33 | 0.73 | +2.0 (-4.2..+8.1) | +2.7 (+0.3..+5.1) |
| T60 | early | 197 | 43 | 0.76 | -2.2 (-7.6..+3.3) | +1.3 (-0.1..+2.7) |
| T60 | late | 179 | 34 | 0.75 | +0.4 (-5.8..+6.7) | +0.7 (-1.0..+2.4) |

Average fee 0.66-0.73 c/share; average stake $10.7-14.0 (the 20 USD cap is often cut by the size of the print).
Net per trade, hold to resolution, all 77 games: E3 +$0.14, E10 +$0.09, E60 +$0.11, T3 +$0.00, T10 +$0.47,
T60 -$0.19, all with CIs that include zero by a wide margin.

### Protocol variants, NFL

| variant | part | trades | games | hold | markout |
|---|---|---|---|---|---|
| E3 | early / late | 52 / 38 | 10 / 5 | -3.0 (t -0.7) / +3.0 (t 0.3) | +0.7 (t 0.5) / +1.6 (t 1.6) |
| E10 | early / late | 41 / 34 | 10 / 5 | -8.3 (t -2.8) / -13.5 (t -1.1) | -1.9 / -3.3 |
| E60 | early / late | 41 / 38 | 10 / 5 | -7.2 (t -1.5) / +4.3 (t 0.4) | -1.3 / -4.1 |
| T3 | early / late | 31 / 23 | 7 / 5 | -8.2 (t -4.1) / -5.7 (t -0.4) | -0.6 / -1.8 |
| T10 | early / late | 31 / 23 | 6 / 5 | -6.8 (t -6.0) / +20.5 (t 2.7) | -0.3 / +0.3 |
| T60 | early / late | 29 / 20 | 8 / 5 | -13.4 (t -3.0) / +9.9 (t 0.9) | -5.2 (t -3.3) / -5.0 |

Most NFL scores barely move the moneyline (median move 3 c; only 40 of 114 event-markets moved 5 c or more).

### Stale pool (descriptive; `out/report.txt`, `out/diag.txt` (b))

Measured from the first +3 c print (the market's own reaction), favoured side bought at <= halfway:

| sport | part | event-markets / games | $ bought stale | of which 0-1 s | >= 4 s after first move | wallets (all / >= 4 s) |
|---|---|---|---|---|---|---|
| soccer | early | 107 / 36 | $201,233 | $159,366 | $39,409 | 187 / 116 |
| soccer | late | 104 / 32 | $41,641 | $30,678 | $9,810 | 118 / 73 |
| NFL | early | 13 / 7 | $499,613 | $497,385 | $1,931 | 41 / 7 |
| NFL | late | 8 / 4 | $16,873 | $8,047 | $8,754 | 46 / 31 |

Soccer profit locked against the later level: $103K in total (95% CI by game $27K..$233K). It is concentrated: one
match (Barcelona-Villarreal, 22 Nov) holds $160K of the $382K counted by the ESPN-clock definition, and two prints of
$28K and $27.5K come 4-5 s before ESPN's time. The wallet 0x2c335066… is first in both sports ($43.7K soccer, $619.8K
NFL). Flaznorp (0x821dab05…, the largest sports account in NOTES.md) is fourth in soccer ($27.2K). Soccer dollars by
second after the first move: 0-1 s $190.0K, 2-3 s $3.6K, 4-6 s $8.8K, 7-10 s $4.1K, 11-30 s $7.9K, 31-60 s $3.0K,
over 60 s $25.3K.

Mean share of the eventual move reached after the first +3 c print (soccer, 411 goal-markets): +0 s 0.59, +5 s 0.75,
+10 s 0.78, +30 s 0.89, +60 s 0.93, +120 s 0.96, +300 s 1.02.

### Attacks on the positive soccer markout (post-hoc)

- (e) Reference from sell-side prints only (removes the bias of a reference made of post-goal buy prints): T3
  +3.2 c/share (t 3.9), T10 +2.3 (t 3.1), T60 +0.9 (t 1.5). The markout survives this attack.
- (d) Real round trip, buy as in the protocol and sell at the first bid print 300-360 s later with a second fee:
  T3 +3.0 (t 3.2; early +2.6, late +3.4), T10 +2.0 (t 2.5), T60 -0.3 (t -0.3).
- (f) Look-ahead in the trigger: trigger T is chosen with ESPN's knowledge that a goal happened and stood. With the
  same trigger on the tape alone (in-play, either direction, one per market per 5 minutes, d = 3), there were
  1,123 filled triggers in 81 matches (187 a day). The 803 not near an ESPN goal lost 2.6 c/share on the round trip
  (t -2.8; early -3.0, late -2.3). The 320 near a goal made +4.2 (t 2.0; early +0.4, late +7.3). All together:
  -1.1 c/share (t -1.3), hold +0.5 (t 0.2). A follower without a goal feed faster than ESPN has no edge. Goals ruled
  out by VAR (at least 6 in these matches, listed in ESPN commentary with no wallclock) are missing from the protocol
  sample by construction.

## Opportunities, net per trade, capacity

- Opportunities: soccer goals in the five big leagues plus UEFA, about 60 goals on a full weekend day (Sat 21 Nov:
  26 matches, 66 goals; Sun: 16, 61), each moving 2-3 markets; NFL Sundays about 100 scoring plays, most of which move the
  moneyline under 5 c. A protocol variant gets 50-65 filled trades a day in soccer.
- Net per trade at 5-20 USD: zero within noise for every protocol variant (soccer -$0.19 to +$0.47 per trade held to
  resolution, CI including zero). The tape-only version a real follower could run: -$0.27 per trade round trip,
  +$0.11 held.
- Capacity for a 200 EUR account: $0 a day of demonstrated edge. If a faster-than-ESPN goal feed existed, the
  conditional round trip (+3 c on about 14 shares, roughly 60 trades on a weekend day) would be about $25 a day before
  competition. That is an upper bound for a feed this lab does not have, not a forecast.

## Reaction time a trader needs

The stale dollars are taken in the first second of the market's reaction (78% in soccer, 98% in the NFL), and in
soccer the market moves a median 5 s before ESPN even records the goal. Taking stale quotes needs an event feed
faster than the broadcast plus sub-second order entry through the 1 s taker delay. A few seconds of reaction is far
too slow.

## Live micro-test

Nothing here deserves a live micro-test. The decision rule fails for all 12 variants. The only positive number
(the +3 c drift after a confirmed goal) needs a goal signal within about 4 s of the first price move, which no free
source gives (ESPN is about 5 s behind the market before any API delay). The tape-only version is negative.

## Limitations

- One week (20-27 Nov), 81 soccer matches and 17 NFL games. The NFL part (12 early, 5 late games) is too small for
  any claim; its stale pool is dominated by one wallet in one game.
- Fills come from the tape at block time minus 3 s. They show that a price printed, not that our order would have
  been first: the 0-1 s pool is not reachable for a slow trader in any case, and later fills assume we could take
  the printed size.
- ESPN's `wallclock` is the only free second-level clock found. Its own delay against the stadium is unknown, and
  so is the delay of its API (a live poller sees each event later than the `wallclock` stamp). The NFL wallclock
  seems to be the play's start.
- P_post (2-5 minutes after the event) uses the future and appears only in descriptive tables. A median over
  post-goal prints can be pulled by one-sided flow (checked by the sell-side reference).
- Only moneyline markets; totals, spreads, "next goal" and halftime markets were not looked at. NBA, tennis
  (sets), esports and cricket were not sampled.
- The 0.05 rate was applied to the one 0.03 market (more conservative). The pre-Nov-20 fee regime of other
  traders is not modelled.
- No audit yet (`audit.md` must be written by an independent agent).

## Ideas, not tested

- Measure ESPN API publication lag live (poll the summary every 2 s during a weekend match and compare first-seen
  time with `wallclock` and with the tape). If the API lags `wallclock` by more than a few seconds, even trigger E
  is out of reach.
- The slow drift after confirmed goals (+3 c over 5 minutes) could be a maker idea instead of a taker one: rest a
  bid on the moved side after the VAR check is over. This needs a pre-registered protocol with "trade through"
  fills and a clean list of overturned goals with times.
- Soccer "other" tape jumps (803 triggers that lost 2.6 c on a follow) suggest fading non-goal jumps. Post-hoc
  observation only; needs its own protocol.
- Tennis set or break-of-serve markets and NBA (`secondsDelay` 0) have a different microstructure from soccer and
  NFL and were not sampled.
- The wallet 0x2c335066… (largest stale taker in both sports) deserves a wallet study: how fast it is relative to
  the first move and what it keeps after fees.
