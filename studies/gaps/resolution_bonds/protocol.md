# Resolution bonds: how long do prices stay below 1 after an event is decided, and does the near-certain side pay?

Written 2026-11-27 BEFORE any outcome or price data was analysed. Only metadata (field names, timestamp formats,
one market's price path and tape to learn what a price-history bucket is) was looked at to make the choices below.
After this file is saved the rules do not change; anything thought of later goes under "ideas" in results.md.

## Protocol as given by the lab lead

Question. The simplest time gap is the one between an outcome becoming known and the market settling. How large is
it, in which categories, and is buying the near-certain side profitable after the taker fee?

Universe. Binary markets with closedTime between 2026-10-20 and 2026-11-25 and volumeNum >= 10,000, excluding
recurring crypto up/down series (slug contains '-updown-'). Listed with `pmlab.gamma.iter_markets(closed='true',
end_date_min=..., end_date_max=..., volume_num_min=10000, include_tag='true')`. If more than 5,000 qualify, a random
sample of 5,000 with a fixed seed. Category from `pmlab.gamma.family`; fee rate from the market's `feeSchedule`
(reliable after 2026-11-20; the same rate is applied to earlier dates and flagged).

Price paths. `pmlab.dataapi.prices_history` at 300-second buckets for both outcome tokens (token ids from
`clobTokenIds`, outcomes from `outcomes`, the winner from `pmlab.dataapi.resolutions`).

- B-a Calibration near the end. At T-24 h, T-6 h, T-1 h, T-10 min before endDate and at endDate: the higher-priced
  outcome (the favourite) and its price. Table by category x price bucket [0.80-0.90), [0.90-0.95), [0.95-0.98),
  [0.98-0.995), >= 0.995: markets, win rate with a Wilson interval, expected net return per share after the taker
  fee (win rate minus price minus fee), mean time from the observation to closedTime, return per day of lock-up.
- B-b The post-event window. Markets with closedTime - endDate >= 30 min: the favourite's price at endDate, +10 min,
  +1 h; share still below 0.99, 0.98, 0.95 at each; what those favourites went on to do.
- B-c Capacity. For 300 randomly chosen markets from the best-looking cells, pull the tape and measure the dollars
  that actually traded on the eventual winner inside the cell's price bucket during the relevant interval.
- B-d The losers. Every market where a favourite priced at 0.95 or more lost (slug, category, price, what happened
  according to the rules text).
- Pre-registered claim: buying the favourite at 0.95-0.98 within the last hour before endDate or after it returns
  more than the fee. Per category, earlier two thirds and last third of the period (by closedTime) separately, t
  clustered by event (event slug).
- State the total number of cells and variants examined.

## Concrete choices (mine, fixed now)

### Universe and sample
1. Listing: `iter_markets(closed='true', end_date_min='2026-09-29T00:00:00Z', end_date_max='2026-12-09T00:00:00Z',
   volume_num_min=10000, include_tag='true')`, walked in daily endDate windows. The endDate window is wider than the
   closedTime window on both sides because markets close before or after endDate. The lower bound is the 5-minute
   price-history retention (60 days); the upper bound is +14 days. A market whose endDate is outside this window
   is not in the listing (it could not give an observation: closing more than 24 h before endDate leaves no valid
   observation time, see 9). This limit is reported.
2. Kept: `closedTime` parsed and 2026-10-20T00:00:00Z <= closedTime < 2026-11-25T00:00:00Z; `volumeNum >= 10000`;
   exactly two outcomes and two `clobTokenIds`; slug does not contain `-updown-`; `endDate` present. Duplicated
   conditionIds are dropped. Nothing else is excluded (hourly "bitcoin-up-or-down-..." markets do not contain
   `-updown-` and stay in, under family `crypto`).
3. If more than 5,000 qualify: sort by conditionId, `random.Random(20261127).sample(ids, 5000)`.
4. Category = `pmlab.gamma.family(market)` unchanged (known limits: mentions fall into other families; Elon
   post-count markets are "politics"). One extra label, because in sports game markets `endDate` is the scheduled
   START of the game, not its end: `sports/start` = family sports with `gameStartTime` within 60 s of `endDate`,
   `sports/other` = the remaining sports markets. Tables show `sports` (all) and these two sub-rows; sub-rows are
   counted as extra cells. For weather, `endDate` is 12:00 UTC of the target day for every station (NOTES.md), so
   "at endDate" is not "after the local day": flagged, not changed.
5. Event cluster = slug of `events[0]`; if absent, the market slug.
6. Fee rate = `feeSchedule.rate`; 0 when `feesEnabled` is false; 0.05 (the highest current rate) when fees are
   enabled but the rate is missing. Fee per share = rate * p * (1-p) at the purchase price. The same rate is used
   for all dates (flag: Oct 20-31 promotions charged zero in several categories; weather and economics charged about
   0.04-0.05 before Nov 21 against 0.01 now; sports v2 schedules say 0.03). Rebates = 0.
7. Outcome: `pmlab.dataapi.resolutions` by conditionId, matched to the gamma `outcomes` by outcome NAME (not by
   token id). Payoff of an outcome = its final price (1, 0, or 0.5 for 50-50 resolutions). Markets not resolved, or
   with a missing final price, are dropped and counted. "Win" = payoff 1; a 50-50 resolution counts as not-win in win
   rates and as payoff 0.5 in returns.
8. Period split by closedTime: early = before 2026-11-13T00:00:00Z (first 24 of 36 days), late = from then on.

### Prices
9. For each sampled market with closedTime > endDate - 24 h 15 min: price history of BOTH tokens, 300 s buckets, from
   endDate - 24 h 15 min to closedTime + 5 min (requests chunked to <= 14 days). Markets that closed earlier than that
   have no valid observation and no claim window; they are counted and not downloaded.
10. A bucket is usable only if `resolution_seconds == 300` and its timestamp < closedTime (the series ends with a
    settlement point at 0/1, which must never be used as a price). From the one-market check a bucket at time t is
    the midpoint at t (the two tokens mirror each other), not a traded price and not a forward-looking bar.
11. Price of an outcome at observation time x = its last usable bucket with timestamp in (x - 900, x]. If only one
    token has such a bucket, the other is taken as 1 minus it (counted). If neither: the observation is missing.
    An observation is valid only if x < closedTime. Favourite = the outcome with the higher price; exact ties are
    dropped (they can only occur below 0.80).
12. Observation times x: endDate-24 h, -6 h, -1 h, -10 min, endDate (B-a); endDate, +10 min, +1 h (B-b).

### B-a
13. Cells: 5 observation times x category rows (families + `sports/start` + `sports/other` + ALL) x 5 price buckets.
    Per cell: markets, events, wins, win rate, Wilson 95% interval (per market, not cluster-adjusted), mean price,
    mean fee, net return per share = mean(payoff - price - fee), its standard error and t clustered by event
    (`ratio_cluster` with per-event sums of net return over per-event market counts), mean and median hours from the
    observation to closedTime, return on capital per day = [mean net / mean(price + fee)] / mean lock-up days.
    Purchase price here is the mid (no spread): optimistic, stated.
14. Sanity table (not a result): the same calibration for favourite buckets 0.50-0.60, 0.60-0.70, 0.70-0.80.

### B-b
15. Markets with closedTime - endDate >= 1800 s. At endDate, +10 min, +1 h (valid only if before closedTime): number
    with a favourite, share with favourite price < 0.99, < 0.98, < 0.95; for the favourites in [0.80,0.95),
    [0.95,0.98), [0.98,0.99) and >= 0.99 at that time: win rate, net return per share after fee (mid), hours to
    closedTime. By category rows as in 13. Also the distribution of closedTime - endDate by category.

### Pre-registered claim
16. Entry: the FIRST usable bucket time t with endDate - 3600 <= t < closedTime at which the favourite (higher mid at
    t, both tokens per rule 11 with x = t and no staleness allowance beyond the bucket itself) has mid in
    [0.95, 0.98). One entry per market, one share.
17. Fill variants (both reported, both pre-registered):
    - C-mid: bought at the mid at t (the protocol's letter; optimistic, no spread, no delay).
    - C-cons: marketable order 5 minutes later: bought at that outcome's mid at t+300 plus 0.005 (half a cent for
      the spread), capped at 0.999; if there is no usable bucket at t+300 before closedTime there is no fill and the
      market drops out of C-cons (counted).
    Net per share = payoff - price - fee(price). Reported per category row and ALL, early and late period
    separately: markets, events, losers, mean price, net per share, SE and t clustered by event, mean lock-up hours.
18. C-tape (only on the B-c tape sample): every taker BUY row on the tape of the entry-time favourite token with
    price in [0.95, 0.98) and block time in [endDate - 3600, closedTime]; net per share = payoff - price - fee;
    `ratio_cluster` over markets and over events (profit / shares), early and late period. This is the only variant
    in which the price was demonstrably available (someone bought there), still without queue or latency.

### B-c
19. "Best-looking cells" defined mechanically from the claim on the EARLY period, C-mid: category rows (families
    only, not ALL, not sub-rows) with >= 30 entry markets and positive net per share. If fewer than two such
    categories exist, the three categories with the highest early net per share among those with >= 30 entries.
    Tape sample: 300 markets drawn with `random.Random(20261127)` from the claim-entry markets (both periods, winners
    and losers alike) of those categories, equal quota per category, unused quota redistributed; if fewer than 300
    exist, all of them.
20. Tape: `iter_trades(condition=...)`, newest first, at most 60,000 rows per market (if the cap is hit and the oldest
    row is later than endDate - 3600 the market is flagged as truncated). Interval = [endDate - 3600, closedTime];
    bucket = [0.95, 0.98). Measured per market: dollars (price * size) on the eventual WINNER token inside the bucket
    and interval, split into taker BUY rows (asks that were lifted: what a taker could have had by being first) and
    taker SELL rows (bids that were hit: what a resting bid could have had); the same for the eventual loser's
    mirror is NOT added. Reported per category: markets with any such dollars, median and mean dollars per market,
    total, and the dollars per day scaled to the whole universe by the sampling fractions.
21. Dollars per day "at the stated size": $100 per entry (a few-hundred-dollar account holding up to three positions),
    capped per market by the taker-BUY dollars seen on the tape in the bucket; profit = size * C-tape net return per
    dollar; opportunities per day = late-period entries scaled by the sampling fraction. Also the bankroll-limited
    figure for $300: positions per day = 3 * 24 h / mean lock-up hours.

### B-d
22. Every sampled market in which, at any usable bucket in [endDate - 24 h, closedTime), an outcome had mid >= 0.95
    and that outcome's payoff was below 1 (including 50-50). Listed with slug, category, the highest such price, when
    it was seen relative to endDate and closedTime, and what happened according to the market description (read by
    hand; if there are more than 60 such markets, all go to a CSV and the 60 with the highest price are read).

### Order of operations
listing -> filter -> sample -> resolutions -> price histories -> sanity checks on a 300-market slice (calibration
near 0.50-0.80, fee formula, timestamps inside the window, mirror of the two tokens) -> B-a, B-b, claim (C-mid,
C-cons) on the full sample -> B-d -> B-c tape sample and C-tape -> results.md.

### Verdict rule (given)
OPPORTUNITY only if the reporting (late) period is positive after fees with t above 2 across at least 100 markets;
NO EDGE if clearly negative or zero; otherwise INCONCLUSIVE. The verdict is read on the claim (ALL and per category),
with C-cons and C-tape deciding when they disagree with C-mid.
