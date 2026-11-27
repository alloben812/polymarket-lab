# Sudden political and geopolitical news: how long do stale prices stay buyable? — results

Study resumed and finished 2026-11-27 (18:23-18:55 UTC) from the interrupted run. Protocol: `protocol.md` (sections 0-11,
Amendment 1, and Amendment 2 = execution budget, appended at 18:30 before any tape of the full list or any rule output
was read). Code, in order: `s1_markets.py`, `s2_fetch_ph.py`, `s2_screen.py`, `s3_tapes.py` / `s3p_tapes.py` (same
logic, 3 workers), `s4_jumps.py`, `s4b_prelabel.py`, `s4c_labels.py` (hand labels, frozen before the rule ran),
`s5_measure.py`, `s6_rule.py`, `s7_l2.py`, `s8_report.py`, `s9_news_sample.py`, `tg.py`, `s10_attack.py` (post-hoc,
written after the tables were seen). Outputs: `out/tables.md` (all protocol tables), `out/attack.md`, `out/l2_compare.txt`,
`out/news_timing.csv`, `out/labels.csv`, `out/jumps.json`, `out/rule.json`, `out/fills.json`.

## Verdict: INCONCLUSIVE, and the positive number does not survive the look-ahead attack. Nothing here deserves a live test yet.

- **Pre-registered result (protocol section 10).** Unscheduled jumps that were confirmed on the tape and held for 2 hours
  ("main"), reporting period 14 Oct - 25 Nov: buying the favoured side at prints <= 0.90 from t0 + 30 s for 10 minutes,
  $200 per jump, held to settlement, made **+$2,436 after fees on 47 jumps** (43 markets, 34 news clusters, 25 jumps
  with a fill; 95% cluster-bootstrap CI +$801..+$4,557; t 2.53 by cluster, 2.32 by day). At t0 + 120 s: +$1,042
  (CI +$529..+$1,673, t 3.40). The early half points the same way (+$1,237 at 30 s, t 2.01, 29 jumps). The verdict
  rule needs at least 100 markets in the reporting period and there are 43, so the verdict is **INCONCLUSIVE**. The
  look-ahead check (main + reverted, reporting period) does not contradict it: +$2,287 at 30 s (t 2.29).
- **Why the positive number should not be believed.** The sample is chosen with information from after the entry. A
  candidate exists only if the price moved 0.40 within 10 minutes. A jump is "confirmed" only if the price is still
  0.40 up 10 minutes after t0, which is inside the buying window. It is "main" only if it held for 2 hours. Removing
  the 2-hour filter is the protocol's check. Removing the 10-minute filter as well is the post-hoc attack (A5,
  `out/attack.md`). On the 159 jumps from the same screen that were *not* confirmed at +10 min, the same rule made
  **+$7 at 30 s and -$26 at 120 s in the reporting period** (48 jumps, 31 / 27 with a fill, t 0.01 / -0.04). All
  tape-timed jumps together in the reporting period: +$1,146 at 120 s (112 clusters, t 1.12). The edge sits in knowing
  that the jump will stick, and a follower at t0 + 30 s does not know that.
- **Real order book (10 jumps, L2 archive).** Sweeping the real asks once at t0 + d (instead of the cheapest prints of
  the next 10 minutes) gives +$752 / +$479 / -$82 / -$254 before fees at d = 10 / 30 / 120 / 600 s. The tape rule shows
  +$952 / +$869 / +$212 / +$133 on the same 10 jumps. At 2 minutes and later, the tape rule's profit comes from
  picking the cheap prints out of the next 10 minutes after the fact.
- **The news is not the trigger. The Polymarket price is.** In 9 of the 10 distinct sampled news items that could be
  timed to the minute, the jump came 7.5 to 141 minutes *before* the first Telegram news-aggregator post (median
  -16 min). In one case (press secretary fired) it came 109 s after. A program that watches news feeds and then buys
  is always late. A program that watches Polymarket prints can react, but it competes with whoever moved the price.
- **Weekends (the owner's question).** These markets do not depend on stock-exchange hours, and news arrives on
  weekends too: 14 of the 92 unscheduled confirmed jumps (15%, 10 news clusters) fell on Saturday or Sunday, against
  29% of calendar days. That is about one cluster every weekend or two. Weekends are thinner, not empty.

## The question

After a sudden headline in a politics or geopolitics market, for how many seconds do stale prices stay buyable, how
many dollars trade at them, who takes them, and does a follower with a delay of 10 s to 10 min make money after fees?

## Data

- Universe: gamma markets with lifetime `volumeNum` >= $50K, two outcomes, a politics / geopolitics / world /
  elections / breaking-news / middle-east tag, no count/word/sports/crypto/weather tag, alive inside 1 Sep - 25 Nov 2026:
  **2,482 markets** (dump `data/gaps_news/markets_all.jsonl.gz`, 16:43 UTC 27 Nov).
- Prices-history of the YES token for all 2,482 markets (1,800 s buckets before 27 Sep, 300 s after, 60 s for
  20-26 Nov), fetched 27 Nov 16:4x-18:37 UTC, `data/gaps_news/ph/`. Screen: **396 candidates in 321 markets**.
- Whole-market tapes of those 321 markets from 25 h before the earliest candidate to 27 Nov (Data API v2
  `trades?condition=`), fetched 27 Nov 16:5x and 18:37 UTC, `data/gaps_news/tapes/`. All 321 reached their stop, none
  hit the 600,000-row cap.
- Settlement: Data API `tokens` (27 Nov 18:38); unresolved markets marked at gamma `outcomePrices` from the 16:43 dump.
- L2: HF `chitoyuuri/polymarket-l2-v3-1-archive` (CC BY-NC, research use only), hourly files for 10 jumps
  (`data/gaps_news/l2/`, read with pyarrow under `python3 -I`).
- News times: Telegram public channel previews (15 aggregator channels, `tg.py`, read 27 Nov 18:43-18:51) and WebSearch.
  arXiv 2610.36639 (protocol (a)): one web search and the arXiv API found no released event list, so list (b) only.

Funnel (`out/tables.md`): 396 candidates -> 77 without a first print 0.10 beyond the pre-price -> 149 not confirmed
(move at +10 min < 0.40) -> 10 pre-price artefacts (Amendment 1) -> **160 confirmed jumps**: 136 held 2 h (main), 24
reverted (R). Hand labels (frozen before the rule): main 76 unscheduled + 60 scheduled (26 of them "doubt" -> scheduled),
R 16 unscheduled + 8 scheduled. **Unscheduled main: 76 jumps, 70 markets, 59 news clusters, 36 days**; first half 29,
second half 47; geopolitics 35, other politics 24, elections 17 (the 17 "election" ones are mostly 2028-nominee markets
with an empty book: pre-price 0.505 = mid of nothing, first print 0.99; they never fill and only add to the count).

## What was run (every variant)

- Pre-registered: the rule at 4 delays (10, 30, 120, 600 s), $200 cap, prints <= 0.90, one full run (plus the
  20-jump sanity slice). Tables by category x delay for unscheduled main, both halves, R, main + R, scheduled.
- Post-hoc attacks (`s10_attack.py`, after seeing the tables; they do not enter the verdict): A1 cluster bootstrap CIs;
  A2 dropping the best 1/3/5 clusters (d = 30, 120); A3 one jump per news cluster; A4 doubt labels counted as
  unscheduled; A5 the rule on all 319 tape-timed jumps incl. not confirmed (every label), A5b not-confirmed only;
  A6 the same 4 delays at a $20 cap (owner's size), A6b / A6c at $20 on all / not-confirmed jumps; A7 the share of all
  buyers' realised profit the rule claims. L2 one-shot sweep comparison on 10 jumps x 4 delays.
- Count: **8 rule variants** (4 delays x {$200, $20}) and 12 re-cuts of the sample. No threshold was changed.

Sanity slice (first 20 jumps, before the full run): 201 fills, all inside [t0 + d, t0 + d + 600] and <= 0.90; spend per
jump <= $200; settlement values {0, 1}; fee recomputed by hand (0.01 x 0.4993 x 0.5007 x 68.1 = $0.170, as coded).
Fills at 0.40-0.60 won 45 of 52 (Wilson 75-93%, only 8 markets). That is far above 50%, as expected on a sample
selected for jumps that stuck.

## Speed of absorption (unscheduled main, n = 76; `out/tables.md`)

| measure | p25 | median | p75 |
|---|---|---|---|
| favoured-side price before | 0.21 | 0.36 | 0.51 |
| first print (t0) | 0.43 | 0.65 | 0.95 |
| price at +10 min | 0.82 | 0.92 | 0.98 |
| seconds to 90% of the move | 0 | 48 | 176 |
| seconds to 0.95 | 0 | 209 | 752 |

- The first print already carries half the move (median 0 s to 50%). 0.95 is reached within 30 s in 23 of 76 jumps,
  within 2 min in 27, within 10 min in 42; 12 never print 0.95 within 24 h.
- **Still buyable at 2 minutes** (a print <= 0.90 between t0 + 120 s and + 720 s): 39 of 76 jumps (24 of 59 clusters);
  36 with at least $50 fillable.
- Dollars that showed the favoured side on offer at <= 0.90, all 76 jumps together: 0-10 s $71K (median per jump $35),
  10-30 s $19K (median $0), 30-120 s $73K (median $1), 2-10 min $238K (median $8). Realised profit of everyone who
  bought: +$41.8K in the first 10 s, -$0.7K at 10-30 s, +$12.0K at 30-120 s, +$40.9K at 2-10 min (main sample only:
  biased up by the selection; in R the same buckets lose -$1.3K, -$1.3K, -$0.6K, -$0.7K).
- **Who takes the first 10 s:** a median of 1 buying wallet per jump (p75 2), top-3 share 1.00, median $75. 123 distinct
  wallets over 59 clusters; 19 appear in 2+ clusters, none in 5+. The most frequent (0x853c37a9) is first in 4 clusters
  with 13% of first-10-s dollars. There is no dominant sniper: whoever is awake on that market at that moment.
- Scheduled jumps behave alike (median 90 s to 90% of the move, 293 s to 0.95).

## Headline numbers after fees (unscheduled main, $200 cap; 95% CI by cluster bootstrap)

| period | delay | jumps / markets / clusters | with fill | $ spent | avg entry | net $ | 95% CI | t (cluster) | t (day) |
|---|---|---|---|---|---|---|---|---|---|
| first half (1 Sep - 13 Oct) | 10 s | 29 / 28 / 25 | 16 | 2,659 | 0.612 | +1,335 | +166..+2,622 | 2.03 | 2.19 |
| first half | 30 s | 29 / 28 / 25 | 16 | 2,659 | 0.635 | +1,237 | +125..+2,441 | 2.01 | 2.26 |
| first half | 120 s | 29 / 28 / 25 | 14 | 2,395 | 0.678 | +891 | -46..+1,899 | 1.73 | 2.06 |
| first half | 600 s | 29 / 28 / 25 | 10 | 1,720 | 0.784 | +216 | -386..+707 | 0.78 | 2.19 |
| **second half (14 Oct - 25 Nov)** | 10 s | 47 / 43 / 34 | 27 | 5,400 | 0.573 | +3,140 | +1,061..+5,818 | 2.57 | 2.40 |
| **second half** | **30 s** | 47 / 43 / 34 | 25 | 5,000 | 0.607 | **+2,436** | +801..+4,557 | 2.53 | 2.32 |
| **second half** | 120 s | 47 / 43 / 34 | 25 | 4,836 | 0.781 | +1,042 | +529..+1,673 | 3.40 | 3.66 |
| **second half** | 600 s | 47 / 43 / 34 | 17 | 3,077 | 0.760 | +611 | +5..+1,492 | 1.60 | 1.65 |

Fees are tiny here (geopolitics 0, other politics 0.01): $3.55-8.06 in total in the second half. By category (second
half, 30 s): geopolitics +$895 (11 clusters, t 1.22), other politics +$1,541 (13 clusters, t 2.58), elections no fills.

Attacks (`out/attack.md`), second half unless noted:

| check | 30 s | 120 s |
|---|---|---|
| without the best 1 / 3 / 5 clusters | +1,752 / +901 / +426 (t 2.41 / 1.93 / 1.22) | +849 / +562 / +334 (t 3.31 / 2.99 / 2.74) |
| one jump per news cluster | +1,420 (34 clusters, t 2.44) | +675 (t 3.44) |
| doubtful labels counted as unscheduled | +2,464 (t 2.35) | +1,035 (t 1.96) |
| R only (reverted in 2 h), whole period | -606 (16 jumps, t -1.65) | -371 (t -1.16) |
| **all tape-timed jumps incl. not confirmed, every label** | +3,453 (133 jumps, 112 clusters, t 2.12) | **+1,146 (t 1.12)** |
| **not confirmed / artefact only** | **+7 (48 jumps, t 0.01)** | **-26 (t -0.04)** |
| same, whole period | +1,998 (159, t 1.51) | +1,626 (t 1.30) |
| rule's share of all buyers' profit in its window | 10% | 7% |

The only delay at which the 10-minute confirmation is already known at entry is 600 s. There the honest sample is
main + R: +$611 in the second half (17 fills, t 1.60) and +$501 over the whole period (31 fills, t 0.80). Not significant.

## Opportunities, size, capacity

- Unscheduled confirmed news clusters: 4.8 a week over the period (59 in 12.3 weeks), 0.79 a day in the reporting
  period (34 clusters in 43 days). Jumps with a fill at 30 s: 25 in 43 days = **0.6 a day**, one per cluster: 13 = 0.3 a day.
- **Net per trade at $20** (A6, $20 cap, second half): +$13.1 per filled jump at 30 s (25 fills, +$327, t 2.84), +$4.8
  at 120 s (+$119, t 3.39) on the selected sample. With not-confirmed jumps included (A6b): +$7.9 at 30 s (85 fills,
  t 2.90), +$4.9 at 120 s (75 fills, t 2.10). Not-confirmed only (A6c): +$5.6 at 30 s (31 fills, t 1.09). At $5 these
  scale down linearly. The minimum order size is per market and was not checked per market.
- **Capacity for a ~200 EUR account** (at most $20 a trade): selected sample $7.6 a day at 30 s, $2.8 a day at 120 s.
  Without the hindsight selection the expected value is between about $0 and $4 a day, and the screen still carries
  some selection, so it may be zero. All takers together realised about $590 a day from these prints at <= 0.90 after
  30 s in the reporting period, on the selected sample.
- **Reaction time needed:** the money is in the first 10 s after the first print (+$41.8K of buyer profit vs -$0.7K at
  10-30 s). A follower at 30-120 s gets a price on the right side of the move only when the jump sticks, and whether it
  sticks is not knowable then. A few seconds is enough for the first 10 s only if the program watches Polymarket prints
  on all ~2,500 markets itself (WebSocket); a news feed is minutes late.

## Live micro-test

**Nothing here deserves a live micro-test yet.** Three reasons:

1. The positive result depends on information from after the entry. Without the +10 min confirmation it is zero in
   the reporting period at $200 (+$7, -$26), and only t 1.1 at $20.
2. The trigger used in the backtest (a 0.40 move in prices-history plus the first 10-cent print) cannot be computed in
   real time. A live program would need its own trigger ("a print at least 10 cents above the last print in a politics
   market"), and that trigger has never been tested. It would also catch every thin-book wobble that the screen
   filtered out with hindsight.
3. Volume is about 0.3-0.6 trades a day. If the true edge per $20 trade were the optimistic +$5 with a spread of about
   $10 per trade, about 20-30 trades would show it (t 2). An edge of +$1-2 needs about 100-400 trades, i.e. one to
   two years of this flow.

What would change this: a zero-money step first. Pre-register a real-time trigger on the cached tapes of the 321
markets (`data/gaps_news/tapes/`, no new downloads). For example: the first print at least 0.10 above the last print of
the previous 30 minutes, in a market with at least $50K volume; buy $20 at prints <= 0.90 from trigger + 3 s for 60 s;
hold. Evaluate it on the late half. Only if that is positive with t > 2 over at least 100 triggers is a micro-test worth
the money. The test would then be: same trigger, limit buy at the best ask (FOK, $10, never above 0.90), 30
repetitions, stop after 10 consecutive losses or a -$60 drawdown.

## Limitations

- Hindsight selection (see the verdict), only partly undone by A5: every jump in this study passed a screen that
  needs a 0.40 mid-price move within 10 minutes.
- Tape fills assume we could take liquidity that another taker took. Tape time is block time (about 2 s after the
  match). The L2 check covers only 10 jumps (first 10 of the seeded draw of 30, per Amendment 2), 4 of which had no
  ask <= 0.90 or almost none ($9).
- The reporting period has 43 markets, below the 100 required, in 34 clusters. One cluster (the Nov 3 US-Iran
  ceasefire ladder, 8 markets) carries $684 of the $2,436 at 30 s (28%). The top five clusters (ceasefire, Paris
  curfew, press secretary, FAA ground stop, Machado) carry $2,011 (83%).
- Labels were read from question, date and deadline only. 26 of 60 scheduled main jumps are "doubt". The 2028-nominee
  "jumps" are empty-book mid artefacts that Amendment 1 does not catch when no print exists in the previous 24 h.
- `volumeNum` is the lifetime volume as of today. The 1,800 s buckets before 27 Sep can miss fast reversals. 19
  unscheduled main jumps are unresolved and marked at today's price.
- News timing: 34 of the 40 drawn clusters were searched (time cap). 10 distinct items were timed to the minute. They
  were timed against Telegram aggregators (minutes behind X and wires), so "before the first report" means before the
  first aggregator post, not before the first public signal. No X timelines older than late October were available.
- `results.json`, `HANDOFF.md` and `audit.md` were not written: this run may write only inside the study folder and
  `data/`. The independent audit (AGENTS.md rule 7) is still owed.

## Ideas, not tested

- The real-time trigger backtest above (the next step, zero money).
- Sibling legs: ladders (ceasefire "through Nov 2/3/4/5/6/8/15", pipeline "by Sep 22/30, Oct 15/31") jump within
  1-2 minutes of each other. The later legs might be the slow part. See the politics wallet note (median 12 s, p90 133 s).
- Selling into the jump as a maker: resting offers on the favoured side 2-5 cents above the pre-price are run over in
  the first seconds. This is the losing side of the trade studied here, and the L2 archive could measure how often.
- Weekend-only subset: too few events (10 clusters) to test now.
