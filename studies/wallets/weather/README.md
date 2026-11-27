# Weather: how the profitable accounts make money (study of 2026-11-27)

Window: fills of 2026-11-13 15:37 .. 2026-11-27 15:37 UTC (14 days, no account truncated). Read-only, public data.
Protocol and the three pre-registered tests are in `protocol.md` (written before the data was looked at).
All money figures are after the calibrated taker fee (0.05 before Nov 21, 0.01 after, see "Fees") and with rebates = 0,
unless a line says "API".

## Short answer

There is not one weather strategy, there are four, and they sit at different points of the market's life:

| # | Mechanism | Who (studied) | When they trade | Edge in the window | Could we copy it |
|---|-----------|---------------|-----------------|--------------------|------------------|
| 1 | Forecast-update taker | WrongBy1Degree | only BEFORE the station's local day starts, in four bursts a day (01, 07, 13, 19 UTC) | +12.1% of turnover; already +10.4% marked at local midnight (t 5.9 over ~400 events) | Maybe. Needs a per-station forecast model. One good month out of seven. |
| 2 | Latency snipe on the deciding METAR | HighTempTation | 5-40 s after the routine report that makes a bucket impossible; flips at 0.99 six seconds later | 133 wins / 0 losses, +8-9% on the buy leg | No with public NOAA feeds: 58/58 of its fills came BEFORE aviationweather.gov had the report. Niche is about $0.5K a day for everybody. |
| 3 | Intraday nowcast (running max vs the buckets) | 241532532432, haiwenxiang, Lex-tang | inside the local day, mostly 09:00-15:00 local, hours before the bucket is decided | +3.3% (241..., t 2.9), +9.7% and +18% on small size for the other two | Yes in principle: free data, minutes not seconds. Thin. |
| 4 | Passive quoting days ahead | OnlyLuckNoBrain, edgewarehouse | resting orders from 1.5 days before the local day | not distinguishable from zero in 14 days; lifetime +5.7% / +2.3% of volume | Not as a first project: adverse selection from #1, rebates are now zero for small makers. |

The owner's "time gap" exists in weather in two forms. The short one (station report -> price) is seconds long and
already owned by somebody with a faster feed than the official source. The long one (new forecast run -> price, and
morning temperatures -> afternoon bucket) is minutes to hours long and is where a small trader could plausibly compete.

## Market facts verified in this study

- Daily "highest temperature in <city>" events: 48 stations, 1 degree C buckets (2 degree F for US cities), neg-risk, tick
  0.001, minimum order 5 shares. Resolution: the highest value in any ROUTINE METAR (SPECI excluded) of the station's local
  day as shown by `aviationweather.gov/api/data/metar`; T-group tenths of a degree C when present, otherwise the whole
  degree in the body; rounded half up; F = C*9/5+32 then rounded. (Hong Kong events use the Hong Kong Observatory.)
- gamma `endDate` is 12:00 UTC of the target date for every station. It is NOT the end of the local day.
  `eventStartTime` is the station's local midnight in UTC; the local day is [eventStartTime, +24 h). The
  "time left to the market end" table of `pmlab.wallet` is therefore misleading for weather ("after end" is the afternoon
  in the Americas). Everything below uses the local day.
- My reconstruction of the daily maximum (Iowa Mesonet routine reports merged with the AWC JSON feed) agrees with the
  official resolution in 3,170 of 3,198 markets (99.1%), 645 event-days. The 28 misses are stations where the archive
  lacks a half-hourly report.
- Fees. API daily fee charge / sum(shares*p*(1-p)) of taker fills (WrongBy1Degree, HighTempTation, haiwenxiang):
  0.04-0.06 on Nov 14-20, 0.006-0.02 on Nov 23-27. Weather was a 0.05 category until Nov 20 and is 0.01 now.
  `pmlab.wallet` applies 0.01 to the whole window and under-counts fees 3-4 times (WrongBy1Degree: tool 421, API 1,768,
  calibrated here 1,643).
- Official feed lag: `receiptTime - reportTime` on aviationweather.gov, median per station: 4-8 min for most
  international stations (UUWW 369 s, ZBAA 328, RJTT 480, WMKK 499, CYYZ 490, EGLC 304, LEMD 260, ZHHH 384), under
  100 s for OEJN, WSSS, OPKC; US stations are received about 3.5 min after the :53 observation. One snapshot of 10
  stations: `tgftp.nws.noaa.gov` station files carry the same time as the AWC receipt (0-30 s earlier), so the lag is
  in NOAA's ingestion, not in the API.
- Books (snapshot 15:58 UTC, 16 events, `out/depth.txt`): top of book is 5-500 shares, within 3 cents of the best ask
  there is $15-300 per bucket. But on the favourite buckets somebody rests very large YES bids 2-3 cents under the best
  bid (Seoul Nov 29, 7 C: 50,066 shares at 0.31 with best bid 0.33; rewards band 4.5 c, minimum 20 shares). So buying NO
  (selling YES) has capacity in the tens of thousands of dollars a few cents through the top; buying YES does not.

## Selection (step 1)

`tools/leaders.py weather --top 60` listed 127 accounts (`leaders.json`). Rule (protocol): >= 1,000 lifetime markets,
average fill under ~$50, rebates under 25% of what was kept, at least two of the last three months positive, plus one
larger-ticket account as a contrast.

Chosen: WrongBy1Degree (the pilot), OnlyLuckNoBrain, 241532532432, haiwenxiang, edgewarehouse, Lex-tang, and
HighTempTation as the larger-ticket contrast ($204 a fill, 5,118 markets).

Skipped, with reasons:
- xtxpleasecallme (first by category month PnL, 53K): 132K markets in all categories, 53% of what it kept is
  rebates. A volume-tier market maker, not copyable.
- 1DVSBSTD: +17K on the weather board but -0.4K kept in November over all categories and 2.4K all-time.
- Sylar012, quqqq, russell110320, bearbees2, balerinacapuchina, 8q-6a1f1, DogeMaster1, 0x62D56a...: $128-782 per
  fill and/or a handful of markets, i.e. a few large directional bets.
- Car, e46m3, flawfence, balthazar, Lucerys, 0xb0c858...: whales whose money comes from other categories.
- Bilberry (35K -> 12.6K -> 2.8K, fading), BeginnersLuck2 (negative November), sbel (negative all-time).
- OnlyLuckNoBrain3 and LowTempTation: by name the second wallets of two accounts already in the set.
- shamubronze3, 0xyahn, twobonclay, AlexD87, windy-weather, NeverSnipe fit the rule and were left out for budget only.

## Step 2: tool totals against the API (same 14 days)

| account | tool gross | API gross | tool fees (0.01) | API fees | calibrated fees | why they differ |
|---|---|---|---|---|---|---|
| WrongBy1Degree | 13,017 | 16,478 | 421 | 1,768 | 1,643 | 99 unresolved markets, positions opened before the window, old fee rate |
| OnlyLuckNoBrain | 560 | 2,143 | 0 | 0 | 0 | NOT reconciled: it buys 1-2 days ahead, so the API window contains settlements of positions opened before Nov 13; per-market noise is large (t 0.2) |
| 241532532432 | 6,331 | 4,889 | 534 | 1,874 | 1,673 | 132 incomplete + 386 unresolved markets, 7,170 merges |
| haiwenxiang | 1,325 | 1,404 | 52 | 209 | 194 | fee rate |
| edgewarehouse | 1,404 | 1,528 | 0 | 0 | 0 | weather is $17K of its $96K turnover (rest is esports/sports) |
| Lex-tang | 2,311 | 3,173 | 69 | 248 | 226 | 32 unresolved, carried positions |
| HighTempTation | 1,687 | 1,828 | 17 | 56 | 53 | fine |

Monthly kept (`tools/wallet_check.py --monthly`, full text in `out/monthly.txt`), thousands of dollars:

| account | Jun | Jul | Aug | Sep | Oct | Nov | note |
|---|---|---|---|---|---|---|---|
| WrongBy1Degree | 0.2 | -0.1 | 1.2 | 3.2 | -2.9 | 27.2 | 27 of its 30 lifetime comes from November |
| OnlyLuckNoBrain | 10.8 | 0.5 | 7.8 | 2.0 | 4.9 | 17.3 | positive every month since March; Jul and Sep negative without rebates |
| 241532532432 | - | 0 | 0 | 0.3 | 17.8 | 8.6 | two months old at this size |
| haiwenxiang | 0.1 | 0.0 | 1.2 | 2.0 | 3.3 | 2.9 | never a negative month since April, small |
| edgewarehouse | - | - | 17.7 | 11.2 | 7.9 | 5.8 | fading, mostly not weather |
| Lex-tang | 2.0 | 4.1 | -3.1 | -0.2 | 6.5 | 5.1 | mixed |
| HighTempTation | 21.9 | 27.0 | 20.7 | 14.5 | 9.1 | 3.6 | fading with volume ($550K a month -> $96K) |

## Step 3-4: where the money comes from (information state at fill time)

`analyse.py` puts every fill of a highest-temperature market into the state of the station at that moment
(`out/analyse_lag0.txt`, and `out/analyse_lag300.txt` for a 5-minute publication lag; two variants run, same picture).
"pre" = before the local day starts; "day-open" = in the day, the running maximum has not yet reached its final value;
"day-peak-in" = running maximum already equals the final one; "day-dead" = running maximum already above the bucket.
Net $ / % of turnover / t clustered by event-day:

| account | pre >24h | pre <24h | day-open | day-peak-in | day-dead / after |
|---|---|---|---|---|---|
| WrongBy1Degree | +1,129 / 9.3% / 1.0 | +10,290 / 14.2% / 2.3 | no fills | no fills | no fills |
| OnlyLuckNoBrain (maker) | -776 / -8.1% / -1.4 | +1,646 / 3.0% / 0.5 | no fills | no fills | no fills |
| 241532532432 | - | -1,223 / -1.0% / -0.6 | +6,221 / 3.3% / 2.9 | -261 | about 0 |
| haiwenxiang | - | +85 | +717 / 9.7% / 3.4 | +346 / 6.7% / 2.9 | 0 |
| edgewarehouse (maker, weather only) | +151 | -331 / -4.5% | +488 / 10.9% / 1.0 | +445 / 26.7% / 0.6 | 0 |
| Lex-tang | -32 | +859 / 11.5% / 1.1 | +1,835 / 18.4% / 1.9 | -1,015 / -10.4% / -1.7 | 0 |
| HighTempTation | - | - | (see below: the "open" fills are seconds after the kill report) | | |

Nobody in the set earns anything from "the day is over, the market has not resolved yet": by then NO trades at 0.99+.

### WrongBy1Degree: forecast-update taker (confidence 4 on the mechanism, 2 on persistence)

- 1,401 fills, 851 markets, 476 events, 44 events touched per day. 100% taker, 100% buys, never sells, redeems.
  Median fill $53, p90 $90, per event median $128, p90 $458.
- Timing: 0 of 1,252 resolved fills are inside the local day (falsification attempt of the "late" hypothesis: fails,
  the count is 0). By hours before local midnight: 36+ h $4.7K (+563), 24-36 h $7.4K (+566), 12-24 h $41.4K (+7,762),
  6-12 h $15.7K (+2,071), 0-6 h $15.5K (+458).
- Fills by UTC hour: 97 at 01h, 111 at 07h, 128 at 13h, 158 at 19h and ZERO at 00h, 06h, 12h, 18h. It runs four
  times a day, one hour after each synoptic hour, and then works the book for the next five hours. That is a schedule
  tied to numerical weather model cycles, not to observations.
- What it buys: YES at an average 0.31 (38% of YES dollars on the exact winning bucket, 53% one bucket off) and NO at
  an average 0.65. NO is the profitable leg: +19-20% (t 2.4-2.8 by event-day) against +3.5-8.6% (t < 1) for YES.
- Attack on "it is just lucky at settlement" (`drift.py`): marked at the mid price at local midnight, before any
  observation of the day, its 1,206 pre-day buys are already +$8,561 = +10.4% of cost, t 5.9 clustered by event
  (settlement: +16.1%). The market moves to where it bought within hours. This is the strongest single number in the
  study and it says the edge is information arriving earlier (a forecast update), not variance.
- Attack on "the market is simply biased and anybody can do it" (H4, pre-registered, `calib.py`, one variant): YES
  prices at local midnight are well calibrated. Blanket rule "buy NO on every bucket priced 0.20-0.60 at local
  midnight, 2 c slippage, 0.01 fee": -3.1% (first half, 309 events), -3.5% (second half, 291 events), t -2.7
  overall. So the edge is in choosing the bucket, i.e. a model. The blanket rule is dead.
- Other side: only 3% of its dollars were filled by the makers in this set (241532532432 $2.9K, edgewarehouse $0.7K).
  The book snapshot suggests the large rewards-band YES bids are what its NO purchases hit.
- Sampled events (14, `out/stories_WrongBy1Degree.txt`): Tokyo Nov 21 bought NO 14 C at 0.687 and YES 15 C at 0.448
  19 h before the day, max 15 C, +$226; Dallas Nov 21 NO 76-77 at 0.871 (40 h), NO 74-75 at 0.596 (28 h), YES 72-73
  at 0.293 (4 h), max 72 F, +$287; Busan Nov 19 NO 10 C at 0.595 four times from 25 h to 5 h before, max 10 C, -$292;
  Wellington Nov 16 YES 20 C at 0.241, max 18 C, -$133. 7 of the 14 sampled events lost money: it is a 12% edge with
  large variance, which is also what the monthly history shows.
- Copying: forecast feeds (GFS/ECMWF/ICON are free), a station-level bias correction, a mapping from forecast
  distribution to bucket probabilities with the market's rounding rule, a cron four times a day. No speed needed.
  Capital: it carries about $7K a day. Fee now 0.01*p*(1-p) = 0.2 c a share at these prices (was 1.2 c).
  Risks: one month of proof, a model we do not have, positions held through the whole day (it does not need to: the
  mark at midnight already holds two thirds of the profit).

### HighTempTation: latency snipe on the deciding report (confidence 5 on the mechanism)

- 284 fills, 135 markets, 118 events, 8 events a day, international stations (79 of 81 timed purchases). Pattern in every market: take
  NO at 0.76-0.98 ($50-830), then sell the same NO at 0.99 a median 6 s later (p90 8 s; 135 of 135 markets) to the
  slower bots that arrive bidding 0.99. No settlement risk, capital recycled within seconds.
- 133 purchases won, 0 lost, 5 unresolved. Buy leg +9.1 c a share on an average price of 0.908; the 0.99 sale gives
  1 c back. Net $1,635 in 14 days on $18.3K of purchases.
- Timestamp test (`htt.py`, `race.py`): of 106 NO purchases, 96 have a kill report in my series; 35 were filled
  0-2 min after the report's time stamp, 15 at 2-5 min, 14 in the 10 min before it (reports are issued a few
  minutes before their nominal time), 3 later than 5 min. The 29 "early" ones are half-hourly reports missing from
  the archive before Nov 19 (e.g. Moscow Nov 13: fill 19:30:16 UTC, the 19:30 report is not in Iowa Mesonet).
- The decisive check: for the 58 purchases where aviationweather.gov states when it RECEIVED the report, 58 of 58
  were filled before that moment, median 286 s before (p10 420 s, p90 12 s). Example: Moscow Nov 25, report 00:00Z,
  bought 828 NO at 0.795 at 00:00:16, sold at 0.99 at 00:00:22; the official source received the report at 00:06:10.
  It reads a source that is minutes faster than the resolution source (which one is unknown; NOAA's own tgftp files
  are not faster).
- Whole-market test H5 (pre-registered, `niche.py`, one variant): 268 kills from Nov 22 with a known receipt time,
  full tapes. Stale NO taken below 0.985: 644 fills, $33.9K, profit $3,037, ALL of it before the official receipt
  time; zero fills in the 60 s after receipt and zero in the following 15 min. 129 of 268 kills had any stale fill;
  median profit per kill 0, p90 $36, max $236; 211 wallets, HighTempTation first with $455, then 0xf76253...
  ($320), 0xf3618b... ($180), 0x1bd1c0... ($153). US stations: nothing. That is roughly $550 a day for the whole
  crowd, and a trader who polls the official feed gets exactly nothing.
- Copying: a METAR source that shows international reports within about 10 s of issue, a poller for ~40 stations,
  an order sent within a few seconds. Capital is trivial ($1-2K, recycled in seconds). The income has fallen from
  $27K (July) to $3.6K (November). Risks: a corrected or mis-parsed report, being second.

### 241532532432: two-sided intraday bot that merges (confidence 3)

- 40,594 fills, 3,594 markets, 744 events (the whole universe), 117 events a day, median fill $4.6. 65% taker.
  Buys both outcomes in 2,154 markets and MERGES (7,170 merge events) instead of selling: matched 162K share pairs at
  an average pair cost of 0.966, which locks $5.5K before fees; the two legs are a median 9.9 h apart, so this is
  inventory closed later, not an instant arbitrage (an instant one does not exist: asks sum to 1.04-1.26).
- By state: pre-day -1.0% (it pays to get positions on), in the day before the peak +3.3% (t 2.9, 611 event-days),
  which is where all of its profit is. By local hour: 00-09h +$4.7K, 09-12h +$2.6K, 12-15h -$1.2K. Its long-NO
  taker fills inside the day come more than 30 min before the bucket is killed in 1,992 of 2,120 cases ($51K,
  +$6.5K): it sells buckets the day is about to pass, from the morning temperatures, not from the deciding report.
- It also sits at 0.85-0.99 buying near-certain NO (maker +2-3 c, taker +1.3-2.8 c a share on $126K).
- API for the window: gross 4,889, fees -1,874, rebates +2,289, net 5,304. 43% of the net is rebates/rewards, which a
  new account does not get. Without them it made about 1% of $366K turnover.
- Copying: needs the full quoting and inventory engine across ~120 events a day. Not a first project.

### haiwenxiang: small intraday swing trader (confidence 3)

- 1,887 fills, 506 markets, 240 events, 21 events a day, median fill $3.4, $15 a market. 78% taker, sells as much as it
  buys (round trips inside the day), active 22:00-15:00 UTC and silent 16:00-21:00 UTC: Asian cities during their
  daytime, probably one person or one small bot in an East Asian time zone.
- Profit: selling YES / buying NO in the day before the peak +$1,079 (+30%, t 3.9, 154 event-days); buying the bucket
  that holds the running maximum once the peak is in +$411 (+19.8%, t 2.8). Buying YES before the peak loses (-9.5%).
  95% of its long-NO taker fills precede the kill report by more than 5 minutes (236 of 248), so it is a nowcast, not
  a snipe.
- Sampled (12 events, `out/stories_haiwenxiang.txt`): Madrid Nov 14 bought YES 14 C at 0.21 at 09:30-10:40 local when
  14 had just been reached, sold at 0.88 at 15-16:30 local; Tokyo Nov 16 bought 20 C at 0.50 at 10:30-11:00 right after
  20 was reached at 10:00, sold at 0.999; Wellington Nov 23 bought 19 C at 0.23 at 13:48, sold at 0.88 at 14:30.
- $1.1K in two weeks on $14K turnover, +7.7%; positive every month since April but never above $3.3K. The trade is
  right and the size is what the books allow at these prices.

### Lex-tang: intraday, Chinese cities, lottery bids (confidence 3)

- 4,139 fills, 380 markets, 179 events, 16 events a day. 54% maker by dollars. Same clock as haiwenxiang.
- Profit sits in taker buys at 0.30-0.85 (about +$2.4K before the fee correction, 13-23 c a share) and in long-NO before the peak
  (+43.7%, t 2.4). It loses on a stream of resting penny bids for YES at 0.01-0.05 (-$478, t -11.7) and on maker
  fills once the peak is in (-$1,077, t -2.0): its resting orders get picked off by faster nowcasters.
- Monthly history is mixed (-3.1K in August). Weak evidence of a durable edge.

### OnlyLuckNoBrain: passive quoting 6-36 h ahead (confidence 3)

- 7,288 fills, 1,181 markets, 559 events, 60 events a day, 100% maker, median fill $4, never trades inside the day.
- 14 days: +$869 on $71.8K (1.2%), t 0.2: nothing can be said from the window. Marked at local midnight its buys are
  +4.0% (t 1.7). API for the window: gross 2,143 plus 1,031 of rebates and rewards.
- Lifetime: +$61K on $1.08M (5.7%), 20% of it rebates/rewards, positive in every month since March. It is filled by
  241532532432 (207 transactions) more than by anyone else in the set, and hardly ever by WrongBy1Degree (3).
- Copying needs a fair-value model good enough not to be the stale quote, plus the rewards programme. Maker rebates
  for small accounts are zero since Nov 22 (NOTES).

### edgewarehouse: generalist maker, weather is the side line that paid (confidence 2)

- 8,817 fills of which 1,849 in weather ($17.4K of $96K turnover); the rest is esports and sports at about zero.
  Weather net +$1,236 (7.1%) but t about 1; most of it is two or three winning buckets bought at 0.03-0.15.
- Monthly income is falling (17.7K -> 5.8K). Nothing here to copy for weather specifically.

## What the winners have in common

1. All of them trade the whole grid of cities every day (16-117 events a day) in small clips ($2-90 a fill, $15-370
   a market). The profit per event is $2-30. Nobody in the systematic group makes a big bet.
2. Nobody earns from waiting for resolution. After the deciding report the NO is at 0.99 within a minute.
3. The NO side carries the profit almost everywhere (WrongBy1Degree +19%, haiwenxiang +30%, Lex-tang +44%, 241... the
   near-certain NOs). Buyers of cheap YES tails are the losers: at 13:00 local a YES priced 0.02-0.10 wins 2.3% of the
   time against an average price of 4.9 c (n 486, t 4.0, exploratory); the day before, YES at 0.10-0.20 wins 10.3%
   against 14.3 c (n 663, t 3.5, exploratory, stronger in the second half).
4. Information ladder, fastest to slowest: a private-speed METAR feed (seconds), morning observations against the
   afternoon buckets (hours), forecast cycles against tomorrow's buckets (hours). Prices at local midnight are
   otherwise well calibrated, so without one of these three there is no edge.
5. Rebates and rewards are a material part of the net for the two-sided accounts (20-43%) and are not available to a
   new small account.

## What was checked and what was not

Checked: fee rate from real charges; the day boundary convention; the reconstruction of the outcome (99.1%); state of
the station at every fill for 7 accounts (57K fills, 3.7K markets); timing of HighTempTation against the official
receipt time; whole-market tapes for 268 kills; calibration of prices for 3,198 markets at four points of the day;
drift to local midnight; book depth snapshot; monthly persistence.
Script variants run, all reported: analyse (2 lags), race (1), niche/H5 (1), calib/H4 (1), drift (1), deep (1),
htt (1), feecal (1). H1 (late/time gap) holds only for HighTempTation; H2 (forecast) holds for WrongBy1Degree; H3
(market making) is not demonstrated in 14 days.

Not checked or weak:
- Which source HighTempTation reads. Only one snapshot compares tgftp with AWC.
- Half-hourly reports before Nov 19 are missing for about 20 stations in the archive, so "day-dead" is late there.
- AWC returns at most 400 rows per station, so receipt times cover Nov 19-27 only (Nov 22-27 for Moscow).
- The set of markets is the union of what the 7 accounts traded: far-tail buckets nobody touched are missing from the
  calibration tables.
- `prices-history` points are 30-minute values of the API's price, not executable quotes. Real fills need the book.
- Two weeks, and the first of them under a fee five times higher than today's. WrongBy1Degree has one good month.
- OnlyLuckNoBrain's window total does not reconcile with the API (positions carried into the window).
- Lowest-temperature and Hong Kong markets (78 of 3,775) were left out.

## Files

`protocol.md`, `build.py` (fills, metadata), `obs.py` + `awc.py` (observations, receipt times), `feecal.py`,
`analyse.py`, `race.py`, `htt.py`, `deep.py`, `stories.py`, `niche.py`, `pxfetch.py` + `calib.py`, `drift.py`,
`depth.py`; outputs in `out/` (`*.txt` are the tables quoted above, `stories_<account>.txt` hold 12-14 events each);
`<account>.json` are the `pmlab.wallet` results, `leaders.json` the leaderboard.
