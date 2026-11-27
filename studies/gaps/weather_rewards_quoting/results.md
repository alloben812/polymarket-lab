# Liquidity rewards on daily temperature buckets: does the minimum two-sided quote pay for a 200-dollar account? — results

Study finished 2026-11-27. Protocol: `protocol.md` (written before any outcome number, executed as written; the one
data deviation, books from the PendulumFlow V3.1 mirror instead of Houroux, is its section 3). Code, in order:
`s1_fetch.py` (Houroux reward-universe snapshots), `s1b_fetch_pflow.py` (L2 books and prints), `s2_meta.py` (gamma
metadata, settlement), `s2b_metar_times.py` (routine METAR times), `s3_build.py` (book replay, quote prices, reward
shares per minute), `s4_sim.py` (seven variants, breakdowns, the 200-dollar account), `s5_live.py` (live state on
2026-11-27), `s6_tapecheck.py` (feed vs Data API tape), `s7_report.py` (tables, today's-rates scenario).
Outputs: `out/variants.csv`, `out/account.json`, `out/breakdowns.csv`, `out/checks.json`, `out/live.json`,
`out/october_comp.json`, `out/tapecheck.json`, `out/report.md` (all tables below come from it). Large per-fill and
per-minute files are in `data/gaps_weather_rewards/` (not in git).

## Verdict: INCONCLUSIVE for October 2026; no usable edge for a 200-dollar account at today's reward rates

- **The question in one paragraph.** Polymarket pays daily liquidity rewards to resting two-sided quotes near the
  midpoint; makers pay no fee. Daily highest-temperature bucket markets carry such pools. If a small account rests
  the minimum size (20 or 100 shares) on both sides, k ticks behind the best bid of each side, does the reward it
  collects pay for the losses on the fills it gets (informed traders hitting it before the price moves), and how many
  dollars a day is that for about 200 EUR?
- **The pre-registered test (the 200-dollar account, rules fixed on 2-6 Oct, evaluated on 7-11 Oct)** brackets zero:
  fill model P (fill only when a print goes through our price) **+$13.44/day** (95% CI by event -21.60..+48.47, t 0.75,
  166 markets, 125 events, 231 fills); fill model O (fill also when our level trades) **-$25.50/day** (CI
  -61.52..+10.53, t -1.39 by event, t -2.12 by day, 160 markets, 652 fills). Neither is positive with t above 2,
  neither is clearly negative under both fill models -> INCONCLUSIVE by the protocol's rule.
- **At today's rates the account earns no reward at all.** The pre-registered today's-rates scenario (protocol 4.10)
  rescales every minute's income by 0.206 (live median rate of the 406 rewarded highest-temperature markets $14/day,
  October median over quoted minutes $68/day). Every market-day of the account then earns less than $1 and the
  $1-minimum removes it: reward $0.00/day, net = settlement only, **+$0.20/day (P) and -$32.16/day (O)** in the
  reporting period. The scenario still assumes October competition; the live books are thicker (median conservative
  competitor score in band 355 on 18 live books vs 127 in October).
- **Why the per-market rows look better than the account.** Quoting every rewarded market independently (no capital
  limit), k = 0 earned $2.60-3.03 reward per market-day. Under model O the fills cost nothing (-0.02 c/share to
  settlement in the late period) and the net is +$2.44 per market-day (t 3.99, 829 markets, 320 events). Under model P
  the fills lose 1.1-1.9 c/share and the net is +$0.62 (t 1.07) late and -$1.20 (t -1.89) early, -$0.30 (t -0.72) over
  10 days. The account cannot reproduce even the P row: with $200 it holds about 10 markets at a time, its greedy
  "highest reward share per dollar" rule rotates through 37-39 markets a day, and **78-89% of its market-days earn
  under $1** (median $0.37-0.44), so the $1 minimum removes $55.9-58.3 of $92-122 of raw reward in the reporting
  week. What is left ($6.66-13.23/day) is about what one bad settlement day costs.
- **Adverse selection is real and measured.** With fill model P every k loses 1.4-1.9 c/share 5 minutes after the
  fill (t -8.7 to -18 by event, 1,524-5,365 fills per period). Model O's extra fills are the benign ones (price touched
  our level and bounced): k0O is +0.18-0.32 c/share at 5 minutes. A new 20-share order joins the back of the queue at a level
  that often holds thousands of shares, so the truth sits close to P on the toxic side.
- **For the owner:** this is not a strategy to paper-trade tomorrow with 200 EUR. In October, at four to five times
  today's reward rates, it was at best a few dollars a day with a confidence interval that covers a loss; today the
  reward a minimum quote earns per market mostly falls under the $1 payout floor.

## Data

- Period: 2026-10-02 00:00 .. 2026-10-11 23:59 UTC (10 days; marks and settlement of 10-11 fills use data to
  10-12 02:59). Choice period 10-02..10-06, reporting period 10-07..10-11.
- Reward universe: HF `Houroux/polymarket-l2-history`, `markets` discovery table, all 871 snapshots of the 10 days that
  list a highest-temperature market (about every 15 minutes, p99 gap 58 min, one gap of 153 min). 1,550 markets in 565
  events (city x target date), 49 cities, rate $50-410/day per market (median $78), minimum size 20 (52% of rows) or
  100 (48%), band 4.5 c everywhere; total temperature pool about $7.5K/day (median snapshot).
- Books and prints: HF `chitoyuuri/polymarket-l2-v3-1-archive`, hourly `weather` files, 243 hours, filtered to the
  universe (raw files deleted). 1,227,564 in-universe market-minutes; 99.5% of them have a valid rebuilt book (the
  rebuilt best bid/ask agreed with the feed's on all but 0.00-0.02% of checked instants).
- Settlement: Data API resolutions, all 1,550 markets resolved 0/1 (532 Yes). Metadata from gamma (local day from
  `eventStartTime`). Routine METAR times: Iowa Mesonet ASOS archive, report_type 3, 45 stations; 123 markets (Moscow,
  Hong Kong, Istanbul, Tel Aviv) have no station in `resolutionSource` and are fully blocked in the protection variant.
- Live state (`out/live.json`, pulled 2026-11-27 17:07 UTC): gamma reward fields of 2,704 open weather markets, 24
  CLOB books, daily `reward_income` of three known rewards farmers.

## Checks before the full run (protocol 4.11)

- One-day slice (10-02) first, then the full run. Kept rows all inside the requested hours (0.0% outside).
- Feed prints vs the Data API tape (`out/tapecheck.json`, three busiest markets of 10-02 14:00-15:00 UTC): 89/89,
  71/71 and 70/70 rows, share totals equal to the sixth decimal. The feed time is the match time: the Data API (block)
  time is a median 2.27-2.36 s later (p10 1.3-1.6 s, p90 3.0-3.1 s). Fills here use the feed's match time.
- Fill calibration: YES fills priced 0.40-0.60 (k0O, all days): 7,022 fills in 528 events at mean price 0.4997 won
  51.3% by fill, 48.3% by event (Wilson 44.1-52.6%); NO fills 0.40-0.60: 7,072 at 0.4985 won 48.7%.
- Reward share always in [0, 1]; the largest market-day income is 15.1% of that market's daily rate. Maker fee 0
  (no taker trade exists in this strategy, so the taker-fee formula is not exercised; rebates 0).
- Universe timing: 99.7% of in-universe minutes are more than 6 h before the end of the local day (>24 h: 33%,
  24-12 h: 51%, 12-6 h: 15%, 6-0 h: 0.3%). Rewards sit on the next day's markets and are withdrawn as the day
  approaches, so the "last 3 hours" part of the protection rule hardly binds; the report-time part blocks 40.3% of
  minutes.

## What was run (every variant)

Seven pre-registered variants, all reported: V1-V6 = k in {0, 1, 2} x fill model {P, O}; V7 = the best of the six
on the first 5 days (k0O, +$3.42 per market-day) with the protection rule. The 200-dollar account (protocol 4.9) uses
the best of the seven on the first 5 days (k0O, no protection) and a class filter fixed on the first 5 days (kept:
hours-to-end >24 h, 24-12 h, 6-3 h, 3-0 h, after end; leader distance 0, 1, 2+; minimum size 20 and 100; dropped:
12-6 h and "alone"), run under both fill models in both periods (4 runs; no auxiliary run was needed). The today's-
rates scenario and the one-maker sensitivity are computations on those runs, not variants. A one-day slice of the same
pipeline was run first as the sanity check. Nothing was added after seeing results. Total: 7 variants + 4 account runs.

## Headline numbers after fees

### Per market-day, every rewarded market quoted independently (no capital limit)

95% CI = net +- 1.96 se, se clustered by event (city x target date). "settle c/share" = settlement value minus our
price, share-weighted, per fill. Markouts are against the mid 5/30/120 minutes after the fill.

| variant | period | market-days | markets | events | reward $/md | settlement $/md | net $/md | 95% CI | t | net per $ capital-day | fills | settle c/share | markout 5/30/120 min, c/share |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| k0P | first5 | 1308 | 841 | 325 | 3.03 | -4.23 | -1.20 | [-2.44, 0.05] | -1.89 | -0.075 | 5365 | -1.87 | -1.41 / -1.62 / -1.79 |
| k0P | last5 | 1279 | 829 | 320 | 2.93 | -2.31 | 0.62 | [-0.51, 1.76] | 1.07 | 0.043 | 5204 | -1.13 | -1.38 / -1.30 / -1.42 |
| k0O | first5 | 1308 | 841 | 325 | 2.67 | 0.75 | 3.42 | [2.24, 4.60] | 5.70 | 0.223 | 18150 | 0.10 | 0.32 / 0.19 / 0.12 |
| k0O | last5 | 1279 | 829 | 320 | 2.60 | -0.16 | 2.44 | [1.24, 3.64] | 3.99 | 0.175 | 17096 | -0.02 | 0.18 / 0.11 / -0.08 |
| k1P | first5 | 1303 | 838 | 325 | 2.02 | -2.79 | -0.77 | [-1.96, 0.43] | -1.26 | -0.049 | 2674 | -2.55 | -1.89 / -2.20 / -1.96 |
| k1P | last5 | 1276 | 827 | 320 | 2.02 | -0.31 | 1.70 | [0.57, 2.83] | 2.96 | 0.120 | 2554 | -0.32 | -1.82 / -1.57 / -1.60 |
| k1O | first5 | 1303 | 838 | 325 | 1.74 | -1.95 | -0.21 | [-1.44, 1.03] | -0.33 | -0.013 | 4977 | -0.90 | -0.49 / -0.68 / -0.87 |
| k1O | last5 | 1276 | 827 | 320 | 1.68 | -0.28 | 1.40 | [0.22, 2.57] | 2.34 | 0.101 | 4774 | -0.15 | -0.49 / -0.36 / -0.45 |
| k2P | first5 | 1292 | 832 | 325 | 0.93 | -0.85 | 0.08 | [-1.08, 1.24] | 0.14 | 0.006 | 1586 | -1.30 | -1.84 / -2.08 / -1.60 |
| k2P | last5 | 1270 | 823 | 320 | 1.04 | 0.09 | 1.13 | [-0.00, 2.26] | 1.95 | 0.096 | 1524 | 0.15 | -1.78 / -1.38 / -1.11 |
| k2O | first5 | 1292 | 832 | 325 | 0.81 | -1.86 | -1.05 | [-2.19, 0.08] | -1.82 | -0.081 | 2240 | -1.99 | -1.11 / -1.18 / -1.03 |
| k2O | last5 | 1270 | 823 | 320 | 0.86 | 0.20 | 1.06 | [-0.07, 2.20] | 1.83 | 0.090 | 2140 | 0.24 | -1.09 / -0.77 / -0.88 |
| V7 k0O+prot | first5 | 1187 | 769 | 298 | 1.74 | 0.24 | 1.98 | [0.80, 3.16] | 3.28 | 0.195 | 10761 | 0.05 | 0.33 / 0.08 / 0.10 |
| V7 k0O+prot | last5 | 1156 | 756 | 294 | 1.74 | 0.25 | 1.99 | [0.76, 3.21] | 3.18 | 0.210 | 10442 | 0.05 | 0.27 / 0.11 / 0.10 |

How to read: a market-day is one market quoted for (part of) one UTC day at the minimum size, on average $51-58 of
capital while quoted (100-share markets dominate the capital). The reward column already has the $1 rule applied
(removed $374-559 of $2.7-8.1K over 10 days per variant). Counting all competitors as one maker (protocol's R1
sensitivity) would raise the reward by 7-13%.

Attack on the positive rows (k0O, V7, k1P/k1O late):
- **Impossible fills (model O).** O counts a fill whenever our level trades, as if we were first in the queue. A new
  20-share order sits behind the whole level. O's fills are 3.3x as many as P's at k = 0 and their 5-minute markout
  is +0.2-0.3 c/share against -1.4 c for P: O's advantage is exactly the fills a back-of-queue order would not get.
  O is an upper bound on the quality of fills, not a plausible case.
- **Not a few lucky events.** Dropping the three best events of each period: k0O +$3.12 (t 5.4) early and +$2.07
  (t 3.6) late per market-day; V7 +$1.65 (t 2.9 / 2.8); k0P -$1.54 (t -2.5) early, +$0.37 (t 0.65) late.
- **Instability across periods.** k0P, k1P, k1O and k2O flip from negative in the choice period to positive in the
  reporting period (k2P from +0.08 to +1.13). The weather moved differently in the two weeks; a 5-day period is too short to say which
  week is typical. The variant chosen in the choice period (k0O) is positive in both, but only under model O.
- **Look-ahead:** the universe, rate, minimum size and band are read as of each minute (snapshot at most 45 minutes
  old); quotes use the book at t_m; the account's market choice uses the reward share at t_m. The leader-distance
  class uses mids at t_m only. No outcome enters any decision.

### The 200-dollar account (pre-registered evaluation), k = 0, no protection, class filter as above

| period | fill model | $/day | 95% CI (by event) | t events | t days | %/day on $200 | reward $/day | settlement $/day | markets | market-days | events | fills | pairs (shares) | worst day | best day | removed by $1 rule (5 days) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2-6 Oct (choice, reference) | P | 1.40 | [-39.27, 42.07] | 0.07 | 0.08 | 0.70 | 15.81 | -14.42 | 153 | 184 | 120 | 209 | 960 | -51.89 | 35.76 | 46.73 |
| 2-6 Oct (choice, reference) | O | 2.74 | [-31.82, 37.29] | 0.16 | 0.08 | 1.37 | 5.93 | -3.19 | 149 | 184 | 123 | 679 | 4,120 | -106.83 | 90.56 | 51.59 |
| **7-11 Oct (reporting)** | **P** | **13.44** | [-21.60, 48.47] | 0.75 | 0.73 | 6.72 | 13.23 | 0.20 | 166 | 196 | 125 | 231 | 1,060 | -27.63 | 75.13 | 55.88 |
| **7-11 Oct (reporting)** | **O** | **-25.50** | [-61.52, 10.53] | -1.39 | -2.12 | -12.75 | 6.66 | -32.16 | 160 | 184 | 125 | 652 | 3,820 | -66.22 | -1.84 | 58.28 |

Reporting-period days, model P: +26.82, -20.39, -27.63, +13.26, +75.13 (reward 7.67-20.05 a day, settlement
-39.96..+55.08). Model O: -3.15, -1.84, -66.22, -19.26, -37.01 (settlement -69.42..-4.20, worst three events -$68).
The account used about $184 of the $200 on average and almost only 20-share markets in the reporting week (a
100-share market needs a $100 reserve). Its fills settled at +0.02 c/share (P) and -1.23 c/share (O); the 5-minute markout was -1.53 c/share under P.

If the $1 minimum applied per account rather than per market (unknown from public data), the raw reward of the
reporting week would be $24.41/day (P) and $18.32/day (O): net about +$24.6/day (P) and -$13.8/day (O). Still no
positive result under both fill models, and the scaled-to-today version of that best case is about $4-5/day of reward
before any fill loss.

### Today's-rates scenario (protocol 4.10, fixed in advance)

Factor 0.206 = $14.0 (median live rate, 406 rewarded highest-temperature markets, 2026-11-27) / $68.0 (October median
over quoted minutes). Fills unchanged, $1 rule re-applied per market-day.

| period | fill model | October rates $/day | today's rates $/day | reward $/day today | t events |
|---|---|---|---|---|---|
| 7-11 Oct | P | 13.44 | 0.20 | 0.00 | 0.01 |
| 7-11 Oct | O | -25.50 | -32.16 | 0.00 | -1.74 |
| 2-6 Oct | P | 1.40 | -14.17 | 0.24 | -0.70 |
| 2-6 Oct | O | 2.74 | -3.19 | 0.00 | -0.18 |

Live cross-check of competition (not part of the scenario): five of the six highest-rate markets on 2026-11-27 ($263-311
a day; the sixth had nothing in the band) give a 20-share quote at the best price a conservative share of 0.2-3.2%,
i.e. $0.5-8.5/day each (median of the
18 scored live books $1.58/day at a median rate of $27.50). Only 53 of today's 406 rewarded temperature markets pay
$50/day or more (all 406 had minimum 20, band 4.5 c, fee 0.01). Known farmers: xtxpleasecallme's daily
`reward_income` (all categories) was $1.6-2.8K a day on 2-11 Oct and $0.7-1.5K on 23-27 Nov; pootytherewardfarmer
$0.9-1.5K then and $0.37-0.51K now. The pools shrank and the professionals' income with them. Order of magnitude
check for R1: the simulated minimum quoter, if run on every rewarded market at once, would have taken $7.7K (k0P,
10 days) of roughly $74K paid to the temperature universe, about 10%: plausible for a quote that always sits at the best
price, which the score weights most, but it is also the share most exposed to fills.

### Breakdowns (R3), reporting period, k0P (closest to a back-of-queue order); full tables in `out/breakdowns.csv`

- Hours to the end of the local day: 24-12 h +$1,309 net (t 1.5 by event), >24 h -$37, 12-6 h -$277 (reward $606,
  fills -$882). Under O the 12-6 h class is also negative (-$516).
- Within 10 minutes of a routine METAR: -$730 (reward $1,256, fills -$1,987, t -0.7); the rest +$1,713 (t 1.5). Same
  sign under O (-$1,462 vs +$4,768). The protection rule (V7) removes most of that loss but also 40% of quoting time.
- Minimum size: 100-share markets +$1,385 (t 1.3), 20-share markets -$403 (t -0.7). The account can afford at most
  two 100-share markets.
- Leader distance: leader -$46, one step +$914, two or more steps and "alone" small.
- City (10 days, k0O): 43 of 49 cities positive under O; the six negative ones (Moscow, Sao Paulo, Karachi, Hong Kong,
  Istanbul, Shenzhen) lost $35-310 each.

## Capacity for about 200 EUR

- October, pre-registered account: -$25.50 to +$13.44 a day (fill models O and P), confidence intervals from about
  -$62 to +$48 a day. Best single estimate: about zero.
- Today: reward income for a minimum quoter falls under the $1 per-market payout floor almost everywhere; expected net
  about $0/day or negative. Even under the most generous reading (floor per account, October competition) the reward
  would be about $4-5/day, which one adverse fill day (-$20 to -$70 observed) wipes out.
- The per-market-day figures (+$0.62 P / +$2.44 O late) need $51-58 of capital per market for 20-100 share quotes;
  the account shows that $200 cannot hold enough markets all day to clear the $1 floor in most of them.

## What a trader would need to run it live

- Data: the CLOB WebSocket market channel (book and trades for every rewarded temperature market; the sandbox cannot
  open WebSockets, a VPS or the Mac can), the gamma reward fields (rate, minimum size, band) refreshed at least every
  15 minutes because rates are re-set daily, and routine METAR times per station (aviationweather.gov) for the
  protection rule.
- Reaction: re-quote at least once a minute and cancel within seconds of a report time or a sharp move; the measured
  adverse selection is 1.3-1.9 c/share within 5 minutes, i.e. the loss happens fast. Seconds, not milliseconds.
- Capital: $20-100 per market per side pair at minimum size; to keep each market's daily reward above the $1 payout
  floor an account must stay in the same markets all day, which with $200 means about 5-10 markets.
- Accounts and keys (an API key, a funded wallet, a non-restricted country for the sending machine). None of that was
  used here: this study is public data only.

## Limitations

- Queue position is not observable; models P and O bracket it. P is closer to a new order at the back of a large
  level, O treats every touch of our level as our fill.
- Every fill is for the full quote size (protocol 4.5). A print smaller than our 20 shares still fills all 20, which
  overstates inventory taken on small prints (and the number of completed pairs). No partial fills.
- Zero latency: quotes are placed on the book state at t_m and can be filled by a print a fraction of a second later;
  a real quoter reacts in hundreds of milliseconds to seconds.
- The reward universe is the top of the October reward table (rate >= $50 per market), not the whole program; the
  Houroux snapshots stop on 10-11, so the study is 10 days, two 5-day halves, 565 events. The $1 minimum is applied
  per market per day (unknown whether per market or per account; both shown). Who owns which resting order is unknown,
  so competitors are bounded conservatively (one-maker sensitivity +7-18% reward). The exact sampling instants of the
  program are unknown (we sample at t_m + 30 s).
- Weather fee was 0.05 in October and is 0.01 now; this strategy pays no taker fee, but the taker flow that fills
  makers may differ today. Competition in the band today is thicker than in October (live median score 355 vs 127),
  which the today's-rates scenario does not include, so the scenario is optimistic.
- 123 markets in four cities have no station in `resolutionSource` and are excluded from V7 by the rule.
- The protocol's 0.10-0.90 single-side rule and score formula follow the docs as read by the lab; any change to the
  program (rates are re-set daily) changes the answer.
- Merging YES + NO pairs is assumed free and instant (gas ignored).

## Ideas, not tested

- A sticky account rule: hold the same few markets for the whole rewarded window instead of re-ranking every minute,
  so that each market-day clears the $1 floor; a rate-matched (not median-scaled) today's scenario on the 53 markets
  that still pay $50/day or more.
- Measure queue position directly: record the WebSocket book on the Mac for a few days and replay our order's place in
  the queue (FIFO) instead of bracketing with P and O.
- Pull quotes for the 12-6 h-to-end window and around report times only (the two classes that lost under both fill
  models), and quote only 100-share markets; would need a fresh pre-registration and out-of-sample days.
- Compare with the farmers' own fills (xtxpleasecallme, pootytherewardfarmer) in temperature markets: how much of
  their reward income they give back on fills.
- Repeat on November data from the same PendulumFlow archive (the reward universe would have to come from live gamma
  polling, since the Houroux table ends 10-11).
