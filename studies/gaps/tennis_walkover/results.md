# Tennis walkovers: can a follower buy the cheap side below 0.50 before the book reaches 50-50? — results

Study finished 2026-11-27. Protocol: `protocol.md` (written before any tape was read; not changed). Code, in order:
`s1_events.py`, `s2_universe.py`, `s3_tapes.py`, `s4_measure.py` (W1, W2, W4, W5, W6), `s4b_stavenson.py` (his share of
W6), `s5_rule.py` (the four delays in every cell of 2.10), `s5b_by_type.py` (diagnostic split by market type),
`s6_fetch_x.py`, `s6_wta.py`, `s6_public.py` (W3). Raw outputs: `out/s4_tables.txt`, `out/s4b_stavenson.txt`,
`out/s5_tables.txt`, `out/s5b_by_type.txt`, `out/s6_public.txt`, `out/events_A.json`, `out/events_B.json`,
`out/w4_prints.json`, `out/public_times.json`; per-event rule results `data/gaps_tennis_wo/rule_events.json` (3.7 MB,
kept out of git).

## Question

Tennis match markets on Polymarket resolve 50-50 when a player withdraws before the start (walkover). When that news
breaks, the underdog is still priced at, say, 0.29 and is worth 0.50. How long does the gap between the first
reaction on the tape and a 50-50 book last, how many dollars below 0.45-0.46 can be bought inside it, who takes them,
and would a follower who buys at a fixed delay after the first move (10 s, 60 s, 5 min, 15 min) make money after the
0.05 sports taker fee once the look-alike moves that do NOT end 50-50 are counted?

## Verdict: NO EDGE for a follower (tape or the public sources found); the gap is a 2-second race

- **What a tape follower would have made: nothing, slightly negative.** The causal rule (a follower sees a pre-start
  move of 5+ cents toward 0.50 and buys <= 0.46 for 30 minutes, $300 per match) run on walkover moneylines plus the
  scaled control sample: -$6,422 (d = 10 s), -$6,471 (60 s), -$17,103 (300 s), -$25,494 (900 s) over 86 days,
  t -0.26 / -0.27 / -0.70 / -1.10 by match, 22,702 moneylines represented. Reporting period (moneylines closing
  from 2026-10-26 13:35, 274 walkovers + 956 x 8 controls): +$629 / +$716 / +$1,868 / -$15,433, t 0.05 / 0.05 / 0.13
  / -1.25. Only 9.5% of the pre-start move episodes are walkovers (266 of 266 + 2,528 scaled control markets).
- **If you somehow knew it was a walkover (hindsight start time), the money left after the first seconds is small.**
  Class A, all markets, d = 10 s: +$3,025 over 830 events in 86 days ($35/day), 90 events with a fill, t 5.2 by
  match. Reporting period: +$534 on 274 events (25 with a fill), $17.6/day, t 3.6, 95% CI of net per event
  [$0.88, $3.02]; without its three best events +$324. At d = 60 s the reporting period is +$273 ($9.0/day, 17
  events with a fill). At 5 and 15 minutes no period is significant (t 1.0-1.8). This line uses the hindsight
  definition of t_first: it is an upper bound for a trader with a perfect walkover feed, not a rule anyone can run.
- **The public notices found come after the book.** For 25 walkovers with a second-precision notice, the book moved a
  median 36 s BEFORE the earliest notice found (17 of 25 before, 4 within 60 s after, 4 later). EntryLists' "OUT: X,
  IN: lucky loser" posts on X came 12-77 s after the first move in all 6 same-day cases. Starting from the notice,
  the rule made +$288 (d = 10 s, 7 fills of 28 events, t 1.2), +$192 (60 s), -$10 (5 min), -$29 (15 min) in 86 days.
- **Where the money goes.** $479,681 of the underdog (and opposite sides of side markets) was taken below 0.45 in
  the 30 minutes after t_first on 209 walkovers; 75% of it in the first 2 s of block time (41.6% in the same second
  as the first move, 33.3% 1-2 s later). 229 distinct takers; the top three took 55%; 97 different wallets were the
  first taker in at least one event; Stavenson was first in 28 of 209 and took 6.3% of the dollars, all of it in the
  first seconds (0% of what was still available from t_first + 10 s). Those takers grossed $228,205 at the 0.50
  payout and paid $15,293 in fees: a real, large business, but for whoever sees the withdrawal first.
- Verdict by the QUEUE rule: tape follower = "преимущества нет" (zero within noise, negative overall); notice
  follower = "неясно" but small (28 events, t 1.2) and below 100 events; hindsight line positive but not executable.

## Data

- Gamma walk: 32,760 closed tennis events with `endDate` >= 2026-08-20, 328,251 markets (`data/gaps_tennis_wo/
  events.jsonl.gz`). Period: markets with `closedTime` 2026-09-01 .. 2026-11-25 (86 days).
- Class A (moneyline resolved 0.5/0.5): 830 events. Series: ITF 443, ATP (incl. Challenger) 137, ATP doubles 134,
  WTA 69, WTA doubles 37, Davis Cup 10. Moneyline volume $13.7M. 647 have any traded market, 561 a moneyline tape,
  350 a t_first (330 from the moneyline, 20 from a side market). No t_first: 183 events had no trade at all, 86 no
  moneyline trade, 211 no qualifying move (160 of them: the first moneyline print was already within 5 cents of
  0.50, i.e. the market traded only after the news; 33 never came within 5 cents).
- Class B (moneyline 1/0, some side market 0.5/0.5): 735 events, 67 with a t_first.
- Control: 21,849 moneylines that resolved 1/0 with a volume; deterministic sha1 sample k = 8 -> 2,734, every total
  multiplied by 8.
- Final prices confirmed through the Data API `tokens` endpoint for all 17,579 class A/B markets and all 2,734
  controls: 0 disagreements with gamma, all resolved.
- Whole-market tapes (`trades?condition=`, cached in `data/tape/`): 2,463 class A markets, 2,034 class B, 2,734
  controls. The previous researcher had downloaded 4,750 of 7,155; this run fetched the remaining 2,155 controls.
- Notice times: WTA live-scoring API (18 W/O records in 42 WTA tournaments, 2,506 matches, 24 Aug - 25 Nov), X
  timelines of 46 accounts through the fxtwitter mirror (1,227 posts). Details under W3.

## Sanity checks (before the full run)

- The two known Stavenson matches: t_first 2026-11-03 09:37:58 (expected 09:38) and 2026-11-18 11:15:55 match time =
  11:15:58 block time (expected 11:15:58). Both from the moneyline, underdog 0.26 and 0.29 before.
- Fee 0.05 * p * (1 - p) per share in `common.fee_ps`; zero on events without fills.
- Payoffs: every class A market pays 0.5 except the `tennis_completed_match` market ("will the match be completed"),
  which resolves No = 1.0 on a walkover (508 events), and one set-winner market. The rule uses each market's actual
  final price, which is why 67 event-variants of the class A rule have a payoff other than 0.5 per share.
- 78 of 350 t_first are after the scheduled start (walkovers announced when the match was due or after a delay).

## What was run (24 rule runs)

Four delays (10, 60, 300, 900 s) in each of six cells: class A from t_first, all markets; class A moneyline only;
class A from t_public; class B; causal follower (class A + controls); C-pin controls. Monthly and early/late splits are
cuts of the same runs. Diagnostics outside the count: market-type split of class A (`s5b_by_type.py`), Stavenson's
own fills (`s4b_stavenson.py`). No threshold was changed. Reporting additions to `s5_rule.py` (no effect on fills):
a 95% CI column, per-day figures over each part's own days, and the per-event file moved to `data/`.

## Measurements (W1-W6)

- **W1** (330 moneyline t_first): underdog before the news median 0.29 (p10 0.10, p90 0.41); <0.15: 62, 0.15-0.30:
  107, 0.30-0.40: 106, 0.40-0.45: 55. The first move print is a median 0.482 in underdog terms: the first taker
  sweeps straight to about 0.48-0.50.
- **W2** (t_first to the first print inside 0.48-0.52, n = 333 of 350): median 0 s, p75 2.3 min, p90 3.6 h; within
  10 s in 222, 60 s in 242, 5 min in 259, 30 min in 282.
- **W4** (buyable below 0.45, all markets of the 209 events with a print after t_first):

| window after t_first | events | shares | dollars | VWAP | moneyline $ | takers | top-3 share |
|---|---|---|---|---|---|---|---|
| 5 min before | 98 | 648,199 | 182,832 | 0.282 | 164,354 | 138 | 0.44 |
| 0-10 s | 193 | 1,144,226 | 375,103 | 0.328 | 324,605 | 111 | 0.59 |
| 10-60 s | 29 | 77,505 | 31,517 | 0.407 | 12,321 | 49 | 0.80 |
| 1-5 min | 36 | 103,032 | 41,813 | 0.406 | 38,030 | 72 | 0.78 |
| 5-30 min | 46 | 93,615 | 31,248 | 0.334 | 28,669 | 105 | 0.39 |

  Within 0-10 s: same second $199,427 (174 events), 1-2 s $159,566 (62), 3-5 s $6,084, 6-10 s $10,026. The "5 min
  before" row is ordinary pre-news trading at the old price plus early sweeps; it is descriptive only.
- **W5**: t_first to resolution median 5.0 h (p25 107 min, p75 14.0 h, p90 30.4 h); scheduled start minus t_first
  median 89 min (p25 9 min, p75 17.7 h).
- **W6** (resting-bid leg, t_50 to resolution, all markets): makers bought at 0.48-0.495 for $2,313,665 ($229,497 via
  taker sells, $2,084,168 via taker buys of the other side at 0.505-0.52) in 321 events, $818,930 a month.
  Stavenson's own maker buys at 0.48-0.495 after t_50 in class A: $369,025 in 77 events (about 16% of the pool).

## Rule results (net after the 0.05 fee; $300 cap per match; t clustered by match)

| cell | delay | events | with fill | dollars | avg price | net $ | net/event | t | net/day |
|---|---|---|---|---|---|---|---|---|---|
| A, all markets, all 86 d | 10 s | 830 | 90 | 10,459 | 0.360 | 3,025 | 3.64 | 5.2 | 35.2 |
| | 60 s | 830 | 72 | 7,955 | 0.356 | 2,277 | 2.74 | 4.5 | 26.5 |
| | 300 s | 830 | 53 | 5,611 | 0.322 | 1,111 | 1.34 | 2.0 | 12.9 |
| | 900 s | 830 | 44 | 4,788 | 0.287 | 1,079 | 1.30 | 1.6 | 12.6 |
| A, all markets, earlier 67% (to 26 Oct, 55 d) | 10 s | 556 | 65 | 7,577 | 0.346 | 2,491 | 4.48 | 4.5 | 44.8 |
| | 60 s | 556 | 55 | 5,816 | 0.337 | 2,005 | 3.61 | 4.0 | 36.1 |
| | 300 s | 556 | 41 | 3,954 | 0.309 | 563 | 1.01 | 1.4 | 10.1 |
| | 900 s | 556 | 34 | 3,604 | 0.275 | 577 | 1.04 | 1.1 | 10.4 |
| **A, all markets, reporting 33% (26 Oct-25 Nov, 30 d)** | 10 s | 274 | 25 | 2,881 | 0.405 | 534 | 1.95 [0.88, 3.02] | 3.6 | 17.6 |
| | 60 s | 274 | 17 | 2,139 | 0.423 | 273 | 0.99 [0.39, 1.60] | 3.2 | 9.0 |
| | 300 s | 274 | 12 | 1,657 | 0.359 | 548 | 2.00 [-0.73, 4.73] | 1.4 | 18.0 |
| | 900 s | 274 | 10 | 1,184 | 0.331 | 502 | 1.83 [-0.89, 4.56] | 1.3 | 16.5 |
| A, moneyline only, 86 d | 10 s | 830 | 59 | 8,504 | 0.382 | 2,366 | 2.85 | 4.7 | 27.5 |
| | 60 s | 830 | 44 | 6,158 | 0.389 | 1,579 | 1.90 | 4.2 | 18.4 |
| | 300 s | 830 | 30 | 4,042 | 0.374 | 1,246 | 1.50 | 2.8 | 14.5 |
| | 900 s | 830 | 27 | 3,569 | 0.352 | 1,395 | 1.68 | 2.5 | 16.2 |
| A from t_public (28 events) | 10 s | 28 | 7 | 913 | 0.333 | 288 | 10.29 [-6.3, 26.9] | 1.2 | 3.4 |
| | 60 s | 28 | 4 | 416 | 0.272 | 192 | 6.85 | 0.9 | 2.2 |
| | 300 s | 28 | 2 | 125 | 0.273 | -10 | -0.37 | -0.4 | -0.1 |
| | 900 s | 28 | 1 | 28 | 0.090 | -29 | -1.03 | -1.0 | -0.3 |
| Class B (side market 50-50) | 10 s | 735 | 60 | 10,427 | 0.018 | 2,712 | 3.69 [-4.9, 12.3] | 0.8 | 31.5 |
| | 60 s | 735 | 59 | 9,520 | 0.014 | 1,728 | 2.35 | 0.6 | 20.1 |
| | 300 s | 735 | 58 | 8,244 | 0.024 | 1,012 | 1.38 | 0.4 | 11.8 |
| | 900 s | 735 | 55 | 6,725 | 0.035 | -450 | -0.61 | -0.2 | -5.2 |
| **Causal follower, A + 8 x control** | 10 s | 22,702 | - | 168,217 | - | -6,422 | -2.30 per triggered | -0.26 | -74.7 |
| | 60 s | 22,702 | - | 161,042 | - | -6,471 | -2.32 | -0.27 | -75.2 |
| | 300 s | 22,702 | - | 156,721 | - | -17,103 | -6.12 | -0.70 | -198.9 |
| | 900 s | 22,702 | - | 146,894 | - | -25,494 | -9.12 | -1.10 | -296.4 |
| Causal follower, reporting period | 10 s | 274 A + 956 x 8 | | | | 629 | | 0.05 | 20.7 |
| | 60 s | | | | | 716 | | 0.05 | 23.5 |
| | 300 s | | | | | 1,868 | | 0.13 | 61.4 |
| | 900 s | | | | | -15,433 | | -1.25 | -507 |
| C-pin controls (84 of 2,734) | 10 s | 84 | 56 | 12,880 | 0.370 | 3,761 | 44.8 | 1.4 | (x8) |
| | 60 s | 84 | 56 | 12,778 | 0.370 | 3,809 | 45.4 | 1.5 | |
| | 300 s | 84 | 56 | 12,755 | 0.370 | 6,677 | 79.5 | 2.4 | |
| | 900 s | 84 | 54 | 12,698 | 0.341 | 2,029 | 24.2 | 0.8 | |

Monthly (class A, all markets, d = 10 s): Sep +$1,537 (287 events), Oct +$1,036 (310), Nov +$451 (233). The
reporting-period edge per dollar fell from 33% to 18.5% (d = 10 s) and the average price paid rose from 0.346 to
0.405: what is left after 10 s is shrinking and closer to 0.50. Causal-follower pieces: walkover moneylines alone
+$2,882 (d = 10 s), control sample -$1,163 x 8; in the control fills (136 markets) only 46 were profitable; the ten
largest control losses are full -$300 losses on pre-start moves of 5-8 cents that were real price changes (favourite
won). Market-type split (`out/s5b_by_type.txt`): the moneyline is 77% of the class A net at d = 10 s; the
completed-match market adds +$337 at 10-60 s and loses -$247 / -$404 at 5 / 15 min (the rule also buys its "Yes").

## W3: public notice time (protocol 2.7)

- Attempted: all 830 class A events by moneyline volume against every source. Found a second-precision notice for
  28 (3.4%); 25 of them have a t_first. The protocol target of 40 was not reached.
- Sources: WTA live-scoring API `api.wtatennis.com` works (16 matched events; `LastUpdated` of the W/O record used as
  t_public, `MatchTimeStamp` shown in `out/s6_public.txt`). X through the fxtwitter mirror: deep cursors return 404,
  so timelines reach back only days to weeks for busy accounts (josemorgado 178 posts, TickTockTennis none);
  12 matched events, mostly @EntryLists lucky-loser posts. ESPN site API: reachable, gives scheduled time and result
  only, no notice time. ATP, ITF and tournament order-of-play pages: not tried (time).
- Lags (t_first - t_public, n = 25): median -36 s; min -14.8 h; max +29.4 h (Blockx-Struff: Blockx was out the day
  before, the market's first prints came 29 h later). WTA API: book within 5 s of `LastUpdated` in 3 events
  (Rybakina-Fernandez 0 s, Liu-Siniakova +5 s, Laron/Sawant -2 s), 25-40 s after in 2, 2.7-5.4 min after in 3
  doubles, 5-28 min BEFORE in 3 singles and 2.7 / 14.8 h before in 2 doubles. 3 X matches rejected by hand (listed in
  `s6_public.py`).

## Attacks on the positive lines

- Look-ahead: the class A lines start from a t_first chosen because the move "stuck"; the causal follower, which
  cannot use that, is negative. The positive class A numbers are a ceiling for a perfect walkover feed.
- Impossible fills: the follower takes the printed size at the printed price after a real taker took it; the tape
  does not show whether that liquidity would have been there for a second buyer, and tennis has a 1 s taker delay.
- Concentration: reporting d = 10 s rests on 25 events with a fill; without the top three it is +$324.
- Multiple testing: 24 runs; the one positive non-walkover cell (C-pin at 300 s, t 2.4, 84 markets, mostly in play)
  is what one expects by chance among 24 and is not a candidate.
- Survivorship: none in the universe (all resolved markets in the window, Data API confirmed); 183 class A events had
  no trade at all and enter as zeros.

## Capacity for an account of about 200 EUR

- Realistic: $0-5 a day. The tape follower loses; the notice follower made $288 in 86 days at a $300 cap (about
  $3/day, t 1.2, 28 events found; there are more walkovers than notices found, so this is a lower bound on events,
  not on edge).
- Ceiling with a perfect walkover feed within 10 s: reporting period $17.6/day at $300 per match, about $13/day at
  ~$230 per match. Capital is not the limit (about 0.8 filled events a day, median 5 h to resolution).
- Whole market, uncapped: $46,074 a month was still buyable <= 0.46 from t_first + 10 s ($34,207 gross at 0.50,
  $3,855 fees, 188 takers); $189,742 a month from t_first + 0 s.

## What a trader would need to run it live

- A withdrawal feed faster than the book: the WTA live-scoring API (and its ATP / ITF / tournament equivalents)
  polled every second, order-of-play pages, lucky-loser sign-ins; public X posts are too slow (median 36 s late).
- Reaction under 1-2 s from the feed to a matched order (the competition is 100+ wallets; three take 55%), a mapping
  from player names to all markets of the match, and REST order entry (WebSockets are not available in this sandbox).
- Capital: $200-300 per event is enough; the binding constraint is speed, not money.

## Limitations

- Notice times exist for 28 of 830 walkovers (target was 40): the X mirror is shallow, ATP/ITF sources were not
  tried, `LastUpdated` is the record's last edit (an upper bound on when the W/O was visible).
- The tape shows fills, not the book; block time has 1-2 s jitter; taker rows are per-order VWAP.
- The completed-match market resolves 1/0 on a walkover, so "class A pays 0.5" holds for all markets but that one.
- QUEUE items outside this folder (`audit.md` by an independent agent, `studies/results.json`, `HANDOFF.md` line)
  were not done: this run could write only in the study folder and `data/`.

## Ideas, not tested

- The `tennis_completed_match` market pays No = 1.0 on a walkover: a direct walkover instrument with twice the payoff
  of the 50-50 legs; measure its book around t_first.
- Poll `api.wtatennis.com` live scoring every second for a week and measure the latency from `LastUpdated` to the
  first move (three events coincide within 5 s, which suggests some takers already poll it).
- The resting-bid leg (W6, Stavenson's 0.49 bids): measure adverse selection on look-alikes; only 26% of C-pin
  markets (240 of 912 scaled) are walkovers, so a 0.49 bid on every pinned market would mostly fill on real matches.
- ATP / ITF / Challenger live-scoring feeds and lucky-loser entry lists as notice sources.
