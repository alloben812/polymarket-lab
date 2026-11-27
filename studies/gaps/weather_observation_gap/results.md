# Weather observation gap: dead and locked temperature buckets after the airport's own reports — results

Study finished 2026-11-27 (resumed after an interruption; protocol, scripts, observations, the market table and about
two thirds of the price and tape downloads were already there). Protocol: `protocol.md` (written before any outcome,
price or tape was looked at; not changed). Code: `s1_events.py` .. `s7_measure.py` (protocol steps), `s8_extra.py`
(written by the first researcher after the protocol, descriptive), `s9_summary.py` and `s10_receipt.py` (written
in this session after seeing the s7 output; descriptive only, no rule and no variant). Raw outputs in `out/`:
`s4_validate.txt`, `s6_awc_check.txt`, `s7_slice.txt`, `s7_full.txt`, `s8_extra.txt`, `s9_summary.txt`,
`s10_receipt.txt`, `o4_detail.txt`. Large files (observations, 6,776 price histories and tapes, `out_full.json`)
are in `data/gaps_weather_obs/` (not in git).

## Verdict: NO EDGE (nothing to test live)

- **After the official report appears, the stale price is gone.** On 3,335 bucket-killing events (616 city-days,
  11 US cities, 1 Oct - 24 Nov) traders took $9,765 of stale profit from dead buckets in total (YES sold at >= 2 c, or NO
  bought at <= 98 c, before fees). 87% of it was taken within 180 s of the observation time. The protocol's
  public time is the observation time + 5 minutes. After it, all takers together got $926 in October ($29/day) and
  $200 in November ($8/day). Most of the October money is from two cities with old-rule confusion (Denver's
  Buckley station and Chicago, $921 of it). For 714 kill events of 12-24 Nov I have the real official receipt
  time (aviationweather.gov `receiptTime`, median 211 s after the observation). 97.8% of the stale profit there
  was taken *before* the official source showed the report. After it, everyone together got **$39 in 13 days
  (about $3/day across 11 cities)**.
- **The 12 pre-registered trading rules hardly trade.** Rule A (buy NO of a dead bucket at <= 0.97, 5/15/60 min after
  the public time) traded 9 / 2 / 0 times in 56 days. Rule B (buy the "locked" bucket at 19/21/23 h local under a cap
  of 0.80/0.90/0.95) traded 0-5 times per variant. The variant picked on October (A d=5: 8 entries on 6 city-days, all
  of them Denver under the old Buckley-station rule, +11.9% on stake, t 2.8) has **1 entry in November (+$7.15)**. The
  verdict rule needs >= 100 markets in November with t > 2; the best variant has 1. In dollars every variant is
  between -$1.54 and +$0.70 a day.
- **The cheap prints that exist are the dangerous ones.** Of the 27 rule fills in total, 8 lost. Every loser was a
  Rule B entry bought below 0.95 on a day where the risk was real: Chicago 15 Oct (old rule; the official value
  came from a special report, 66 °F, which the routine reports never showed) and NYC 22 Nov (night warming from 59 °F
  at 19 h to 62 °F). The market prices the "locked" bucket at 0.996 on average at 21 h and 23 h (median 1.000,
  264 November city-days); it won 100% of those days. Buying it pays nothing.
- **For the owner's question (weekends, a seconds-reaction program):** these markets run every day, weekends
  included, and the structure is the same on weekends. The stale money before publication was $106-120/day on
  weekends against $150-197/day on weekdays, all of it taken before publication. A program that reacts within
  seconds *of the official publication* is too late on any day of the week. The race is won 30-180 s after the
  observation by traders who have the reading before aviationweather.gov shows it.

## Question

Daily "highest temperature in <city>" markets settle on the highest routine airport report (METAR) of the local day.
Once a report prints, every bucket wholly below that value can no longer win ("dead"). Late in the evening the
bucket holding the day's maximum is nearly certain ("locked"). Can a trader with a reaction time of a few seconds,
working from the official public source, still buy NO of a dead bucket, or YES of the locked bucket, at a stale
price after paying the fee? How often, and how much?

## Data

- Universe: gamma closed weather events `highest-temperature-in-<city>-on-<date>-2026` for the 11 US cities
  (Fahrenheit buckets), closedTime in [1 Oct, 26 Nov) UTC: **616 city-days (56 per city), 6,776 bucket markets**, all
  cleanly resolved (one YES winner each). Observation dates 30 Sep - 24 Nov. Tuning "October" = 352 city-days (32
  dates); reporting "November" = 264 city-days (24 dates). Weekend dates: 16 of 56.
- Observations: Iowa Mesonet ASOS archive, raw METAR text, routine (`report_type=3`) and special (`=4`) reports, 12
  stations (KBKF for Denver up to 22 Oct, KDEN after). Validation of my rebuilt maximum against the official winner:
  **615 / 616 (99.8%)**; old rule 252/253, new rule 363/363; no city-day with fewer than 20 routine reports. The one
  miss is Chicago 15 Oct (old rule): routine maximum 65 °F, official 66-67 °F; a special report at 02:17Z shows 66 °F,
  and the old rule text (weather.gov time series) did not exclude specials.
- Cross-check against the official source (`s6`): 3,864 routine reports of 12-27 Nov in the aviationweather.gov JSON
  are all in the archive with identical values (one is filed as special there). Receipt lag after the observation
  time: median 211 s, p90 268 s, 95.6% within 300 s. So "public time = observation + 300 s" is slightly late for
  most reports.
- Prices: `prices-history` 300 s, YES and NO token of all 6,776 markets. Tapes: whole-market `trades?condition=`, all
  6,776 (4 empty). No download failed. Fee 0.01 (current weather rate); 0.05 re-pricing as a sensitivity line.

## Sanity slice and checks (before the full run)

- NYC 10-16 Nov (7 city-days, 77 markets): daily maxima match all 7 winners. YES + NO = 1.000 at every sampled point
  (n = 231; on the full run n = 20,328). So the NO history is the complement of YES and is not an independent check.
  No entries in the slice; no entry print outside [T, T + 1800 s]. The fee formula matches on every fill.
- Calibration: taker BUY-Yes prints at 0.40-0.60 won 53.6% in the slice (n = 617, 7 city-days). On the full run they
  won 50.7% at an average price of 0.488 (n = 61,226 prints, 616 city-days; +2.8 c/share, se 1.4).
- Meaning of the prices-history stamp: the point at stamp t is closer to the last trade at or before t (mean absolute
  gap 0.014) than to the last trade before t + 300 (0.020). It is a snapshot at about t. The points are 5 minutes
  apart, so "price at the public time" is the snapshot up to 5 minutes earlier. All tradability claims below come
  from the tape, not from the price history.

## What was run

- Protocol O1 (dead buckets: prices and tape), O2 (lock-in at 17/19/21/23 h), O3 (12 rule variants: A d = 5/15/60 min;
  B h = 19/21/23 x cap 0.80/0.90/0.95), O4 (risk cases), plus the fee-0.05 re-pricing of the same fills.
  **Variants run: 12** (+ 1 fee re-pricing). Each was run once on the full data and once on the slice.
- Descriptive, not variants: `s8` (stale profit by seconds since observation, top takers); `s9` (same fills as return
  on stake, at a fixed $10 stake, weekday/weekend split); `s10` (stale profit relative to the official receipt time).

## O1: how fast dead buckets reprice

Dead-bucket YES price (prices-history), share of buckets still >= 0.02 / >= 0.05. "Live before kill" = YES >= 0.05 at
the observation time.

| subset | n | at obs time | at public time (obs+5 min) | +5 min | +15 min | +60 min |
|---|---|---|---|---|---|---|
| Oct, all dead buckets | 1,905 | 22.6% / 14.9% | 6.9% / 4.9% | 1.2% / 0.9% | 0.3% / 0.2% | 0.1% / 0.1% |
| Nov, all dead buckets | 1,430 | 26.9% / 15.2% | 6.7% / 3.9% | 0.1% / 0.1% | 0.1% / 0.1% | 0.0% / 0.0% |
| Oct, live before kill | 283 | 100% / 100% (median 0.145) | 36.7% / 32.2% | 6.7% / 6.4% | 1.8% / 1.1% | 0.7% / 0.4% |
| Nov, live before kill | 218 | 100% / 100% (median 0.179) | 28.0% / 24.3% | 0.5% / 0.5% | 0.5% / 0.5% | 0.0% / 0.0% |

Dead buckets killed by the first report of the day were almost never live (3.3% >= 0.05). The "at public time"
column uses the 5-minute snapshot taken 2-4 minutes after the observation. The tape below shows the real timing.

**Stale profit taken by all takers on dead buckets** (taker SELL Yes at >= 0.02 or BUY No at <= 0.98; profit =
shares x YES price, before fee), by match time (block time - 3 s) after the observation:

| seconds after observation | Oct $ (share) | Nov $ (share) |
|---|---|---|
| 0-60 s | 1,460 (26.7%) | 1,010 (23.5%) |
| 60-120 s | 1,121 (20.5%) | 1,184 (27.5%) |
| 120-180 s | 1,860 (34.0%) | 1,904 (44.3%) |
| 180-300 s | 100 (1.8%) | 0 (0.0%) |
| 5-10 min | 489 (8.9%) | 15 (0.3%) |
| 10-20 min | 140 (2.6%) | 86 (2.0%) |
| 20-65 min | 277 (5.1%) | 99 (2.3%) |
| > 65 min | 20 (0.4%) | 0 |
| total | 5,467 over 32 days ($171/day) | 4,298 over 24 days ($179/day) |

The first stale take per bucket comes a median 65 s (Oct, n = 258) and 61 s (Nov, n = 199) after the observation
(p90 164 / 142 s). After the public time it is $926 in October, of which Denver (old rule, Buckley) $634 and Chicago
(old rule) $287. Under the new rule (33 dates) it is $202, about $6/day for all takers in 11 cities.

**Relative to the real official receipt time** (`s10`, the 714 kill events of 12-24 Nov that have a `receiptTime`,
92 of them with any stale print): > 60 s before receipt $903 (50.2%), 60-10 s before $857 (47.6%), 10-0 s before $1,
0-10 s after $19 (1.1%), 10-30 s after $9, 30-120 s after $11, later $0. **After the official publication: $39 in 13
days, all takers together.** Before publication the prints were small (median 20 shares, $1.40 profit per print, p90
$10.58).

Takers paying for dead YES after the public time (protocol measure O1a): $1,423 in Oct (658K shares, about 0.2 c a
share) and $562 in Nov. These are penny buyers of the impossible. The money goes to whoever rests asks there.

## O2: the locked bucket

Bucket holding the running maximum of the reports public by local hour h. Share of city-days where it won (Wilson 95%)
and its YES price (mean / median):

| hour | Oct (n = 352) | Oct YES | Nov (n = 264) | Nov YES |
|---|---|---|---|---|
| 17 | 98.6% [96.7-99.4] | 0.965 / 0.992 | 97.3% [94.6-98.7] | 0.982 / 0.997 |
| 19 | 99.4% [98.0-99.8] | 0.995 / 1.000 | 99.6% [97.9-99.9] | 0.991 / 1.000 |
| 21 | 99.4% [98.0-99.8] | 0.997 / 1.000 | 100.0% [98.6-100] | 0.996 / 1.000 |
| 23 | 99.7% [98.4-99.9] | 0.996 / 1.000 | 100.0% [98.6-100] | 0.996 / 1.000 |

The market already prices the lock: at 21-23 h the median YES is 1.000 in every city. Days where the snapshot price
was <= 0.95 at 21 h: 1 in Oct (lost) and 3 in Nov (won).

## O3: the 12 rules (fee 0.01; fills = first qualifying print in [T, T + 30 min], <= $50, held to settlement)

| variant | per | entries | city-days | avg px | win | return on stake [95% CI, clustered by city-day] | t | net $ | $/day | net $ at fee 0.05 |
|---|---|---|---|---|---|---|---|---|---|---|
| A d=5 | Oct | 8 | 6 | 0.893 | 8/8 | +11.9% [+3.5, +20.3] | +2.8 | +22.5 | +0.70 | +21.8 |
| A d=5 | Nov | 1 | 1 | 0.712 | 1/1 | +40.2% (n = 1) | - | +7.1 | +0.30 | +6.9 |
| A d=15 | Oct | 1 | 1 | 0.942 | 1/1 | +6.1% | - | +0.6 | +0.02 | +0.6 |
| A d=15 | Nov | 1 | 1 | 0.712 | 1/1 | +40.2% | - | +7.1 | +0.30 | +6.9 |
| A d=60 | Oct / Nov | 0 / 0 | | | | | | 0 | 0 | 0 |
| B 19 h, cap 0.80 | Oct | 1 | 1 | 0.714 | 0/1 | -100% | - | -14.3 | -0.45 | -14.5 |
| B 19 h, cap 0.80 | Nov | 2 | 2 | 0.432 | 2/2 | +131% [-50, +312] | +1.4 | +4.4 | +0.18 | +4.3 |
| B 19 h, cap 0.90 | Oct | 1 | 1 | 0.714 | 0/1 | -100% | - | -14.3 | -0.45 | -14.5 |
| B 19 h, cap 0.90 | Nov | 3 | 3 | 0.747 | 2/3 | -58.8% [-161, +43] | -1.1 | -11.0 | -0.46 | -11.1 |
| B 19 h, cap 0.95 | Oct | 2 | 2 | 0.793 | 1/2 | -57.3% [-157, +43] | -1.1 | -13.8 | -0.43 | -14.0 |
| B 19 h, cap 0.95 | Nov | 3 | 3 | 0.747 | 2/3 | -58.8% [-161, +43] | -1.1 | -11.0 | -0.46 | -11.1 |
| B 21 h, cap 0.80 / 0.90 | Oct | 1 | 1 | 0.747 | 0/1 | -100% | - | -49.4 | -1.54 | -49.9 |
| B 21 h, cap 0.80 / 0.90 | Nov | 0 | | | | | | 0 | 0 | 0 |
| B 21 h, cap 0.95 | Oct | 1 | 1 | 0.747 | 0/1 | -100% | - | -49.4 | -1.54 | -49.9 |
| B 21 h, cap 0.95 | Nov | 1 | 1 | 0.950 | 1/1 | +5.2% | - | +0.1 | +0.00 | +0.1 |
| B 23 h, all caps | Oct / Nov | 0 / 0 | | | | | | 0 | 0 | 0 |

- October-selected variant (highest October net $): **A d=5**. Its November line is the headline: 1 entry, +$7.15,
  no interval possible. The verdict rule needs >= 100 November markets with t > 2.
- Why so few entries: of 3,335 dead-bucket candidates, Rule A d=5 found no NO-buyable print at all in the 30 minutes
  in 3,087 (once a bucket is dead nobody trades it), and 239 more first printed above 0.97. Rule B at 21 h found no
  YES print on the locked bucket in 594 of 616 city-days; 20-21 first printed above the cap.
- Attack on the October A d=5 positive: all 8 entries are Denver, 30 Sep - 20 Oct, under the old rule that named
  Buckley Space Force Base (KBKF). The stale Denver prices were most likely traders watching the wrong station
  (Denver International). That rule ended on 22 Oct, so the result cannot repeat. The only November entry (Seattle
  10 Nov, NO at 0.712 about 22 minutes after the public time) is a single print of 25 shares.
- Losses: 8 of 27 fills lost, all in Rule B: Chicago 15 Oct (the validation miss, decided by a special report) and
  NYC 22 Nov (late warming). A lock bucket priced under the cap is a warning, not a bargain.
- At a fixed $10 per entry (same fills): A d=5 +$1.80 per entry in Oct (n = 8), +$4.02 in Nov (n = 1). Rule B
  -$10.0 to +$14 per entry on 1-3 entries. The weekday/weekend split has nothing to show: all Rule A entries are on
  weekdays, and Rule B has 1-2 weekend entries.

## O4: risk cases

- Dead buckets (by my reconstruction) that resolved YES: **0** of 3,335.
- Locked bucket lost: 12 city-days at 17 h, 3 at 19 h (all later routine reports higher: late warming), 2 at 21 h, 1
  at 23 h. The 21 h / 23 h cases (`out/o4_detail.txt`): Chicago 15 Oct (official 66-67 °F from the 02:17Z special
  report at 18.9 °C, routine maximum 65 °F; old rule) at 21 h and 23 h, and NYC 13 Oct (old rule; routine reports at
  01:51Z and 02:51Z read 22.2 °C = 72 °F after a 71 °F lock at 21 h: late warming). Under the new rule, no lock at
  21 h or 23 h lost (363 city-days).

## Opportunities, size, capacity, reaction time

- **Opportunities per day:** Rule A d=5 0.25/day in Oct (8 in 32 days), 0.04/day in Nov (1 in 24). Rule B 0-0.12/day.
  For context, the 11 cities produce about 60 dead buckets a day. About 9 of them were live (YES >= 0.05) before the
  kill, and none of those is still stale once the source publishes.
- **Net per trade at $5-20:** Rule A d=5 averaged +$1.80 per $10 entry in October (n = 8, all Denver old rule) and
  +$4.02 on the single November entry. Rule B is negative on average (-$10 to +$14 per $10 entry, 1-3 entries).
- **Capacity for a ~200 EUR account:** under $1/day. Upper bound: all takers together got about $3/day after the
  official receipt (12-24 Nov) and $6-8/day after obs + 5 min under the current rule. A new account would get a
  share of that.
- **Reaction time needed:** to reach the stale money you must trade within 30-180 s of the observation time (median
  first take 61-65 s), i.e. before the official source publishes (median 211 s). That needs a source faster than
  aviationweather.gov. A few seconds of reaction to the official source is not enough on any day of the week.

## Live micro-test

Nothing here deserves a live money test. No rule has more than 1 November entry, the realistic pool after
publication is about $3/day for everyone, and the only cheap prints were adverse (Rule B) or tied to a rule that
no longer exists (Denver/KBKF). A test could not tell an edge from noise in any useful time: at 0.04 qualifying entries a day, even 30 entries
would take about two years.

## Limitations

- Price history is a 5-minute snapshot, so O1 price shares at fixed offsets are coarse. The tape-based tables are
  the real evidence. Tape time is block time - 3 s (about 1 s of slack, per the BTC 5m calibration).
- Fills are "first print in 30 minutes" with no book depth. Resting orders were not simulated: the protocol has none.
- The official receipt times (`s10`) exist only for 12-24 Nov (the AWC JSON holds the last ~400 reports per
  station). For October, obs + 300 s stands in for publication. Real receipts are a median 89 s earlier, which makes
  the protocol's after-publication numbers an upper bound.
- The weather fee was 0.05 until 20 Nov and zero on 20-31 Oct. Headline numbers use today's 0.01; 0.05 changes
  nothing material (table).
- 56 days, 11 US cities. Celsius cities (37 others) were outside the protocol. The earlier time-gap pass found the
  same picture there: 53 of 53 first sells before the official receipt.
- `s9` and `s10` were written after seeing the s7 output. They are descriptive re-cuts of the same data and add no
  trading rule.

## Ideas, not tested

1. **A faster observation feed.** The winners trade 30-180 s after the observation, before aviationweather.gov.
   Candidates to time against the tape without money: MADIS hfmetar, api.weather.gov station observations, NOAA
   tgftp, Synoptic, and the 5-minute ASOS values. Only interesting if some public feed delivers the routine report
   in under ~60 s. Even then the pool is about $106-197/day for all takers (median print $1.40), shared with
   established bots (HighTempTation and others).
2. **Resting asks on dead YES (penny sellers).** Takers paid $23-44/day for impossible YES at about 0.2 c. Selling to
   them means holding NO bought near 0.998 and earning about 0.2% per fill. This needs queue and capital modelling
   (an L2 replay) and looks like a cents-a-day business.
3. **Old-rule style confusions.** The October residue came from a station mismatch (Denver/KBKF). A watcher for rule
   or station changes in new weather events might find similar windows. They are rare and cannot be planned.
