# Protocol: liquidity rewards on daily temperature buckets (minimum two-sided quote, 200-dollar account)

Written 2026-11-27, before any fill, reward share, markout or settlement number was computed. Only the layout of the
data was inspected before this point (schemas, which markets exist, how often the reward table changes, what a trade
row looks like). Nothing below changes after the first outcome number is seen. Follow-ups go under "ideas".

## 1. Question

Does resting the minimum two-sided quote in rewarded daily highest-temperature bucket markets pay after adverse
selection, for an account of 200 dollars?

## 2. Protocol as given by the lab lead (unchanged)

Polymarket pays daily liquidity rewards to resting two-sided quotes inside a band around the midpoint. Makers pay no
fee. Daily highest-temperature markets settle on the routine hourly METAR reports of one station.

- Program rules (data/pm_docs/programs_liquidity-rewards.md), implemented exactly: order score ((v - s)/v)^2 per share,
  v = maximum spread, s = distance from the adjusted midpoint; two-sided requirement (score = the smaller of the two
  sides; a single side counts one third, only while the midpoint is between 0.10 and 0.90); sampled every minute; paid
  daily; 1 dollar minimum payout.
- Simulated quoter: for each rewarded daily-temperature bucket market and each minute, one quote of exactly the minimum
  size on each side (a bid for YES and a bid for NO), k ticks behind the best bid on that side, k in 0, 1, 2, only
  while both quotes are inside the reward band; refreshed once a minute; capital = minimum size x (YES bid + NO bid).
- R1 reward: our share of the score each minute from the real book (every resting order in the band is a competitor);
  dollars per day per market and per dollar of capital; order-of-magnitude check against the daily reward_income of a
  known rewards farmer.
- R2 fills and adverse selection: fill model P (a trade prints strictly through our price) and fill model O (also when
  the level we joined trades). Mark each fill against the mid 5, 30 and 120 minutes later and against settlement.
  After a fill the quoter stops adding on that side and keeps the other side until the pair completes (a pair is worth
  1 dollar).
- R3 net result = reward income minus mark-to-settlement losses per market-day; broken down by hours to the end of
  the local day, distance of the bucket from the leading bucket, minute of the hour, city.
- R4 one protection rule: no quotes from 10 minutes before to 10 minutes after each routine report and none in the last
  3 hours of the local day; recompute R1-R3.
- Seven variants: 3 values of k x 2 fill models, plus the protection rule on the best of the six, chosen on the first
  5 days. A 200-dollar account that picks markets by a rule fixed on the first 5 days is evaluated on the last 5:
  dollars per day, percent per day on capital, markets quoted, fills, pairs completed, worst day; t clustered by
  city-day.
- Verdict rule: OPPORTUNITY only if the reporting period is positive after fees with t above 2 across at least 100
  markets; NO EDGE if clearly negative or zero; otherwise INCONCLUSIVE.

## 3. Deviation forced by the data (found while checking the layout, before any outcome)

The protocol names HF `Houroux/polymarket-l2-history` as the source of books and trades. Its `events` and
`book_levels` tables do not contain a single order-book row for a temperature market (all 107 market_ws files of
2026-10-02 and six files spread over 10-06, 10-09 and 10-11: zero rows; the web-socket capture covers sports,
politics and similar markets only). The temperature markets are present only in its `markets` discovery table, which
records the reward universe (about 500 markets with the highest daily rate; for temperature markets this means a rate
of 50 dollars a day or more) with `daily_reward`, `rewards_max_spread_cents`, `rewards_min_size`, about every 25
minutes.

Replacement, same days:
- Reward parameters: Houroux `markets` table, every discovery snapshot of 2026-10-02 .. 2026-10-11 (the 10 most
  recent processed days).
- Books and trades: HF `chitoyuuri/polymarket-l2-v3-1-archive` (PendulumFlow V3.1 mirror, all markets, full L2,
  exchange millisecond timestamps), hourly `weather` files of 2026-10-02T00 .. 2026-10-12T02 (the last three hours
  only to mark fills of 10-11 forward). Rows of sub_tag `highest-temperature` whose market is in the reward universe
  are kept; the raw hourly files are deleted after filtering.
- Consequences to state in the results: (a) the universe is the top of the reward table of early October 2026 (rate
  >= 50 dollars a day per market), not the 630 weather markets with a median pool of 10 dollars a day seen on
  2026-11-27; (b) the weather taker fee was 0.05 then and is 0.01 now, so taker flow may differ today.

## 4. Concrete choices

### 4.1 Universe and time
- Market: slug starts with `highest-temperature-in-`, listed in at least one Houroux universe snapshot of the 10 days.
  Lowest-temperature and other weather markets are out.
- Minute grid: UTC minute boundaries t_m of 2026-10-02 00:00 .. 2026-10-11 23:59. First 5 days = 10-02..10-06 (choice
  period), last 5 days = 10-07..10-11 (reporting period).
- In the universe at t_m: the latest discovery snapshot received at or before t_m is at most 45 minutes old and lists
  the market. Rate R, minimum size and band v are read from that snapshot (as of t_m, no look-ahead). Not in the
  universe -> no quotes, no reward.
- Market-day = (market, UTC date). City-day (cluster) = the event: city x target date of the market. All buckets of
  one event share one outcome, so t-statistics are computed on per-event sums/means (pmlab.stats.mean_se,
  ratio_cluster), never per fill.
- Local day: [eventStartTime, eventStartTime + 24 h) from gamma (station local midnight). If gamma has no
  eventStartTime for a market the city's UTC offset from its other markets is used.

### 4.2 Book
- Everything is expressed on the YES token: a row on the NO token is mirrored (price -> 1 - price, BUY <-> SELL).
  YES bids = buy YES / sell NO orders; YES asks = sell YES / buy NO orders. Our NO bid at q rests on the YES ask side
  at 1 - q.
- Replay per market in venue-time order (timestamp, then book snapshots before price changes, then file hour, then
  row_ordinal). A `book` row replaces the whole book; a `price_change` row sets one level. The state before the first
  book row of a market is unknown (the opening_state file of the first hour is used as the starting book if its layout
  allows a direct read; otherwise the first book row).
- Quality gate per sampled instant: the book must have both sides, best bid < best ask, and the rebuilt best bid and
  best ask must equal the latest best_bid/best_ask carried by the feed rows of that market at that instant. Otherwise
  the instant is invalid: no quote is placed at an invalid t_m and no reward is counted at an invalid sample. The share
  of invalid instants is reported.
- Tick: 0.01; 0.001 once a `tick_size_change` row to 0.001 has been seen (and back if it changes back); if the first
  book of a market has a price that is not a multiple of 0.01 the tick starts at 0.001.

### 4.3 Reward score (R1)
- Adjusted midpoint: midpoint of the best bid and best ask among price levels whose size is at least the minimum size
  (the lab's reading of "size-cutoff-adjusted midpoint"; individual orders are not visible, so a level counts when
  its total size reaches the minimum). Our own live quotes are included (a level we rest on always qualifies).
- Competitors: every level with size >= minimum size and distance s < v from the adjusted midpoint counts with its
  full size (conservative: small orders inside a large level are counted too). Q1c = sum over bid levels of
  size x ((v - s)/v)^2, Q2c the same over ask levels.
- The split of the book between makers is not public. Conservative bound used in all seven variants: the competitors'
  summed Q_min is the largest value any split can give, C = min(Q1c, Q2c) + |Q1c - Q2c| / 3 when the adjusted midpoint
  is in [0.10, 0.90], and C = min(Q1c, Q2c) outside. Sensitivity reported for R1 only (not a variant): all competitors
  as one maker, C' = max(min(Q1c, Q2c), max(Q1c, Q2c)/3) inside [0.10, 0.90], min(Q1c, Q2c) outside.
- Ours: Q1u = size x ((v - s_bid)/v)^2 if our YES bid is live and s_bid < v, else 0; Q2u likewise for our NO bid.
  Q_min_u = max(min(Q1u, Q2u), max(Q1u, Q2u)/3) when the adjusted midpoint is in [0.10, 0.90], min(Q1u, Q2u) outside.
- Sample: one per minute at t_m + 30 s (the expected position of a random offset), with the book of that instant and
  our quotes as placed at t_m; a quote filled before the sample is gone. Share = Q_min_u / (Q_min_u + C).
- Income of a minute = R / 1440 x share (R = daily rate in force at t_m). This equals the documented epoch formula
  when somebody scores in every one of the 1,440 samples and is lower otherwise.
- 1 dollar minimum: a market's reward for a UTC day below 1 dollar is counted as 0 (conservative reading: the
  minimum applied per market per day). The amount removed is reported.

### 4.4 Quotes
- At each t_m with a valid book and the market in the universe: size = minimum size in force. YES bid = best YES bid
  - k x tick. NO bid = best NO bid - k x tick, i.e. a YES-side ask at best YES ask + k x tick. Best bid/ask are the
  raw best prices (any size). A quote needs a price in [tick, 1 - tick].
- Flat (no unpaired inventory): both quotes are placed only if both are strictly inside the band around the adjusted
  midpoint at t_m (computed with our quotes included); otherwise none.
- Unpaired inventory (YES shares != NO shares): only the bid for the side we hold less of is placed, k ticks behind
  that side's best bid, and only while it is inside the band; it scores as a single side. Equal amounts of YES and NO
  are a completed pair (1 dollar per share pair; merging is assumed free and instant, gas ignored).
- A quote placed at t_m is live on (t_m, t_m + 60 s] and is then replaced. The state machine runs continuously per
  market over the 10 days; inventory left at the end is settled at the official outcome.
- Capital of a market-minute = size x (YES bid + NO bid) while flat; inventory cost plus the live bid otherwise.

### 4.5 Fills (R2)
- Prints: `last_trade_price` rows (one row per match). Bid-side print = taker sold YES or bought NO; ask-side print =
  taker bought YES or sold NO; price converted to the YES token.
- Model P: our YES bid at b fills at the first bid-side print with price < b during its life; our NO bid (YES ask at
  a) at the first ask-side print with price > a.
- Model O: the same with <= b and >= a (the level we rest on traded).
- A fill is always for the full quote size at our price (maker, fee 0, rebate 0). No partial fills. Whether the first
  qualifying print came before or after the reward sample of that minute (t_m + 30 s) decides whether the quote still
  scores in that sample.
- Marks: YES-token raw mid (best bid + best ask)/2 from a valid book at the first minute boundary at or after fill
  time + 5 / 30 / 120 minutes; if that instant is invalid, the last valid mid of the preceding 10 minutes; after the
  market's last data row, the settlement value; otherwise missing (counted). Markout per share = mark - price for a
  YES fill, (1 - mark) - q for a NO fill.
- Settlement: pmlab.dataapi.resolutions. PnL of a YES fill = (final_yes - b) x size, of a NO fill = (1 - final_yes -
  q) x size. Markets without a 0/1 resolution are dropped from R2-R4 and counted.

### 4.6 Net result and breakdowns (R3)
- Net of a market-day = reward of that UTC day (after the 1-dollar rule) + settlement PnL of the fills that happened
  on that day. Reported as dollars per market-day, per dollar of capital-day (mean capital of quoted minutes x share
  of the day quoted), with mean_se over events.
- Hours to the end of the local day at the minute: > 24, 24-12, 12-6, 6-3, 3-0, after the end.
- Distance from the leading bucket at the minute: leader = the market of the same event with the highest YES mid at
  t_m among the event's markets in this study (those ever in the reward universe); classes 0 (is the leader), 1, 2+
  bucket steps, "alone" (no other market of the event has a valid mid).
- Minute of the hour: six 10-minute groups, and "within 10 minutes of a routine report" versus the rest.
- City. For breakdowns the reward is attributed to the minute it was earned in (before the 1-dollar rule) and the
  settlement PnL to the minute of the fill.

### 4.7 Protection rule (R4)
- Routine report times: observation timestamps of routine METARs (Iowa Mesonet ASOS archive, report_type 3) of the
  station named in the market's resolution source. A minute t_m is blocked when (t_m, t_m + 60 s] touches
  [T - 10 min, T + 10 min] of any routine report T, or when t_m is within the last 3 hours of the local day or after
  it. Blocked = no quote on either side (also not the pairing side).
- A station without report times in the archive: all its minutes are blocked in the R4 variant (reported).
- Stations that report every 30 minutes lose 40 of every 60 minutes under this rule; that is the rule as written.

### 4.8 Variants (seven, all reported)
V1-V6 = k in {0, 1, 2} x {P, O}, no protection. "Best of them on the first 5 days" = highest mean net per market-day
over 10-02..10-06. V7 = that (k, fill model) with the protection rule.

### 4.9 The 200-dollar account
- Parameters fixed on 10-02..10-06 only: (i) k and protection on/off = those of the variant among V1-V7 with the
  highest first-5-day mean net per market-day; (ii) a class filter: a class of {hours-to-end bucket}, of {distance
  from leader} or of {minimum size 20 / 100} is excluded when its first-5-day net (reward earned in those minutes plus
  settlement PnL of fills in those minutes, chosen k and protection, fill model O) is negative. A minute is eligible
  only when all three of its classes are kept. No city filter (too many levels for 5 days).
- Simulation on 10-07..10-11 (and, for reference only, on 10-02..10-06), run under both fill models. Budget 200
  dollars, no compounding. Reserve per market in a slot = minimum size x 1 dollar (two bids never sum above 1).
  Every minute: (1) a held market that is not eligible this minute (out of universe, filtered class, minimum size no
  longer affordable) is dropped: quotes cancelled, slot freed; unpaired inventory stays to settlement and its cost
  stays locked until the market's gamma closedTime (local day end + 3 h if missing); (2) free capital is filled
  greedily: first markets in which the account holds unpaired inventory, then by estimated reward per reserved dollar
  = R x share_at_t_m / reserve, where share_at_t_m uses the book at t_m with both our quotes in (information available
  at t_m). A market stays in its slot while eligible, also through minutes with an invalid book or quotes out of band.
- Reported: dollars per day and percent per day on 200 dollars, distinct markets and market-days quoted, fills, pairs
  completed, worst day, t over city-days (events) and over the 5 calendar days. The 1-dollar rule per market per day
  applies.

### 4.10 Current state (not a variant)
- Live reward fields of open weather markets from gamma (rate, minimum size, band) and a few live books: rate
  distribution today versus October, in-band competing score today versus October for a like-for-like set.
- "Today's rates" scenario, fixed now: the income of every market-minute is rescaled by (median live daily rate of
  rewarded highest-temperature markets) / (median October rate over quoted market-minutes); fills are unchanged. It
  assumes competition in the band stays as it was in October, which a few live books can only roughly check.

### 4.11 Sanity checks before the full run (one day first)
- Timestamps of kept rows fall in the requested hours; rebuilt best bid/ask agree with the feed's on most instants.
- Print side convention: BUY prints sit at the ask, SELL prints at the bid (checked on one hour: yes).
- Prints of one market against the Data API tape for the same hours (count and prices).
- Realised YES win rate of fills priced 0.40-0.60 near 50 percent (pooled, with a Wilson interval).
- Maker fee is 0 by rule; no taker trade exists in this strategy, so the fee formula is not exercised.
- Reward share is in [0, 1]; the income of a market-day never exceeds its daily rate.

### 4.12 What public data cannot tell (to be repeated in the results)
Queue position (model P and model O bracket it); whether rewards under a dollar a day are paid per market or per
account; how competitors react to a new quote; which maker owns which order (hence the conservative bound in 4.3);
the exact sampling instants; whether a 20-share order inside a level that the feed shows as one number scores.
