# r3 — Structural edges from Polymarket's own rules and incentive programs

Researcher pass of 2026-11-27. All API calls are read-only and public. Scripts: `tools_scratch/r3_*.py`,
raw pulls in `data/r3/`. Docs pages are saved under `data/pm_docs/` (file name = docs path with `/` -> `_`).

## 0. Protocol written BEFORE measuring (liquidity-rewards yield)

Question: what does a new account earn per day from the Liquidity Rewards program with $200 of two-sided quotes?

Rule fixed in advance (variant 1, the only one planned):
- Universe: every market returned by `GET https://clob.polymarket.com/rewards/markets/multi` whose `rewards_config`
  has an allocation with `start_date <= 2026-11-27 <= end_date`. Sample = top 150 by `rate_per_day` + 150 drawn at
  random (seed 3) from rate 10..200 + 100 at random from rate 2..10.
- Book: one snapshot per market from `POST https://clob.polymarket.com/books` (YES token; the NO book is its mirror).
- Adjusted midpoint (docs say "size-cutoff-adjusted midpoint" without defining it): midpoint between the best bid
  level and best ask level after dropping levels smaller than `rewards_min_size`. This is my approximation.
- Competing score: S = ((v - s)/v)^2 per share for each level with size >= min size and s < v, v = `rewards_max_spread`
  cents. Q_one = sum over bids, Q_two = sum over asks. Per-maker Q_min is not observable (book is aggregated), so
  the competing total is taken as min(Q_one, Q_two) (all makers balanced), with bounds
  [max(Q_one,Q_two)/3 , Q_one+Q_two].
- Our quotes: $200 of collateral, N shares bid on YES at mid - s and N shares bid on NO at (1 - mid) - s, with
  N = 200 / (1 - 2s); s = max(1 tick, 1 cent, half the adjusted spread) i.e. we join the inside or sit 1 cent
  away, never improve it. Not eligible if N < min size or s >= v.
- Reward/day = rate * Q_us / (Q_us + Q_comp), assuming we are on the book for all 1,440 samples. Yield = reward/200.
- Risk side: 5-minute `prices-history` for the last 7 days (data-api v2). Report the 5-minute and 1-hour standard
  deviation of price changes in cents, and a crude adverse-selection cost: a maker that re-centres every 5 minutes
  and is run over whenever the 5-minute move exceeds s loses N * (|move| - s) each time (no spread income counted,
  no inventory carried). Reported per day next to the reward. For a random sub-sample of 90 markets (30 per tier).
- A minimum payout of $1/day applies (docs): rewards below $1 are counted as 0.
- Variants run are counted in section 2.

### Protocol addendum (written before running variant 3)

Variants 1 and 2 model a hypothetical maker from 5-minute prices and both over-penalise thin books where the
quoted price flickers. Variant 3 uses real fills instead: **aggregate maker markout vs the reward pool**.
For 15 markets per tier (first 15 of the 30 already drawn), pull the market tape
`GET data-api/v2/trades?condition=C` for the last 7 days (cap 5,000 rows), convert every taker fill to YES-space,
and compute the makers' P&L per share against the price 1 hour later (5-minute `prices-history`; last price if
the market has no later bucket): taker buys YES at P -> makers earn P - P_1h; taker sells -> P_1h - P.
Compare makers' aggregate markout per day with the pool `rate_per_day`. If pool + markout > 0 the program pays
makers in aggregate more than takers take from them. This says nothing about how a small slow maker does
relative to the aggregate (he is likely worse).

### Protocol addendum 2 (written before running variant 4)

Bug found in variants 2-3: rows were matched on the first 60 characters of the question, which collides for the
"Ornn ... rental price" family (different strikes share the prefix). Variant 1 was not affected. Variant 4 keys
on `condition_id` and widens the screen:
- all active reward markets with rate >= 20/day; one book snapshot each; same $200 scoring as section 0, with the
  competing score reported as a range [max(Q1,Q2)/3 .. Q1+Q2] and central = min + (max-min)/3 (min only when the
  midpoint is outside 0.10-0.90);
- pre-specified "quiet pool" rule: rate >= 100/day AND `volume_24hr` < $5,000 AND eligible with $200. For every
  market passing it (cap 60, highest rate first) pull the 7-day tape and compute aggregate maker markout (1 h)
  exactly as in variant 3, plus the number of distinct taker wallets and fills per day.

### Protocol written before the resolution-window study (variant R1, the only one planned)

Question: do takers who buy a near-certain outcome in the last 24 hours before on-chain resolution make money
after fees, and how much could a resting bid for the eventual winner have bought from impatient sellers?
- Universe: gamma `markets?closed=true&end_date_min=2026-11-17&volume_num_min=10000` (paged, cap 500), excluding
  crypto up/down series (slug contains `updown` or `up-or-down`) which settle by Chainlink with no window.
- Lifecycle: `data-api/v2/resolutions?condition=` -> `reporter`, `resolved_at`, `was_disputed`.
- Tape: `data-api/v2/trades?condition=C&start=resolved_at-86400` (cap 3,000 rows), rows up to `resolved_at`.
- Winner = outcome whose gamma `outcomePrices` is 1 (markets with a 0.5/0.5 payout are reported separately).
- Taker-buy test: every taker BUY at price >= 0.90: P&L per share = payout - price - rate*p*(1-p), rate = the
  market's `feeSchedule.rate` (current schedule; all sampled markets closed after the Nov 20 fee change or the
  rate is flagged). Buckets: price 0.90-0.95 / 0.95-0.98 / 0.98-0.99 / 0.99-1; time to resolution <2h / 2-6h /
  6-24h. Unit of analysis = market (mean of per-market returns, plus pooled $-weighted).
- Maker-bid capacity: taker SELLs of the eventual winner at price >= 0.90 in the same window: shares, $ and the
  maker's gain (1 - price) per share, zero maker fee.
- Loss tail: taker BUYs at >= 0.90 of the eventual LOSER (count of markets and $).

### Protocol addendum (R2, written after seeing only the composition of R1, before any P&L number)

R1's universe sorted by volume turned out to be 239 sports/esports games out of 259 (they resolve minutes after
the game, so "last 24 h" there is in-play betting, not a resolution window). R1 is reported split into
game markets vs the rest. R2 repeats the identical rule on non-game markets only: same gamma query paged to
6,000 rows, dropping slugs that end in a date `-2026-MM-DD` (optionally followed by `-suffix`) or contain
`updown`; cap 500 by volume. Two variants in total for this study.


---

## 1. Sources (official docs, read 2026-11-27; author = Polymarket; kind = official documentation)

All at `https://docs.polymarket.com/<path>.md`; local copy in `data/pm_docs/`. Undated pages are "as served on 2026-11-27".

| Page | What matters |
|---|---|
| `programs/liquidity-rewards` | Paid daily at midnight UTC, **minimum payout $1**. Order scores S = ((v - s)/v)^2 * b (v = max spread in cents, s = distance from the "size-cutoff-adjusted midpoint", b = in-game multiplier). Q_one = bids on m + asks on m'; Q_two = asks on m + bids on m'. Midpoint in [0.10, 0.90]: Q_min = max(min(Q_one,Q_two), max(Q_one/c, Q_two/c)) with c = 3.0; outside that band Q_min = min(Q_one,Q_two) (two-sided only). Book sampled once a minute at a random offset (1,440 samples per UTC day); share of each sample summed over the day, then normalised; reward = share * market's daily rate. Sports after game start: an order counts only after resting for the taker delay; crypto/finance: no minimum age. The "$1M crypto TWAP rewards" of August 2026 have ended. Public list of rewarded markets: `GET https://clob.polymarket.com/rewards/markets/multi` (`order_by=rate_per_day`, `page_size` <= 500, cursor). |
| `programs/maker-rebates` | Since 2026-11-20 23:59 UTC: tiers by 30-day maker weighted volume (shares * p * (1-p)): < $200K 0%; 3% / 7% / 10% / 15% of the taker fee your fills generated at $200K / $1M / $4M / $10M. Zero-fee markets and combos earn nothing. Min payout $1. "An applicable maker rebate campaign can replace the standard rate." |
| `programs/taker-rebates` | Weighted volume = trade $ * (1 - entry price) * bonus. Gold $200K 10%, Platinum $1M 25%, Diamond $4M 40%, Obsidian $10M 50%, Onyx $75M 60%. Fee-free markets earn nothing. Polymarket may remove rebates for wash trading / self-matching. |
| `trading/fees` | fee = C * rate * p * (1-p), taker only. Rates: BTC 5m/15m up-down 0.05; other crypto 0.01; sports 0.05; finance 0.05; tech 0.05; elections 0.05; other politics 0.01; economics 0.01; culture 0.01; weather 0.01; mentions 0.01; geopolitics 0; combos 0.05; other 0.05. Fees rounded to 5 decimals. |
| `concepts/positions-tokens` | **Holding Rewards: 4.00% annualised** on total position value in eligible markets, value sampled randomly once an hour, paid daily, rate variable. Split 1 pUSD -> 1 Yes + 1 No; merge back; binary markets can settle on a split payout, negative-risk markets never do. |
| `concepts/negative-risk` | 1 No share of outcome A converts (atomically) into 1 Yes share of every other outcome. Augmented neg-risk: placeholder outcomes plus an explicit "Other" whose meaning changes; "only trade named outcomes". |
| `concepts/resolution` | UMA Optimistic Oracle: proposer posts a bond ("typically $750 pUSD"), **2-hour challenge period**; one dispute -> new proposal round; second dispute -> UMA DVM vote (24-48 h debate + ~48 h vote; 4-6 days total). Wrong or too-early proposal loses the whole bond; a correct undisputed one gets bond + reward (reward size not stated). Possible 50/50 outcome. Up/down markets settle on Chainlink TWAP with no dispute step (Up if final >= price to beat). |
| `concepts/order-lifecycle`, `trading/place-orders` | Taker delay: "selected crypto and finance up/down markets ... held for 250 ms" (the changelog of 2026-08-17 says crypto is now **50 ms** - the page is stale). Sports/game delay: a configured `secondsDelay` around live games. During a delay the marketable order is pending and **cannot be cancelled**; resting orders can. |
| `changelog/predictions` | 2026-11-20 fee and rebate change (above); 2026-09-28 `/v2/resolutions` gained `expected_settlement_time`; 2026-08-17 crypto taker delay 250 -> 50 ms; 2026-08-07/14 Chainlink TWAP settlement; 2026-07-02 World Cup markets moved to a 0.0025 tick; 2026-11-16 Chainlink API key needed for PolyBolt from 2026-11-30. |
| `trading/combos/overview`, `market-makers`, `collateral-return` | RFQ auction: request -> market makers have **400 ms** to send signed quotes -> best quote returned -> user has **10 s** to accept -> optional **Last Look** (1 s; offered to makers with about $2,500 of combo notional) -> execution. Combo fee rate 0.05, no maker rebate. Collateral return nets offsetting combo positions back into pUSD. |
| `programs/referral-program` (terms effective 2026-05-28) | Referrer needs $10,000 lifetime volume. Earns **10% of the net fees** of direct referrals (5% indirect) for the referral's first 30 days or until the referral reaches Platinum. Self-referral and linked accounts are clawed back. |
| `programs/builders/overview`, `fees`, `tiers` | A "builder" routes other people's orders with a builder code and may charge **up to 1.00% of notional on taker orders and 0.50% on maker orders**, on top of platform fees, paid daily (min $0.10). Verified builders can get weekly USDC rewards by volume and grants. Unverified: 100 relayer transactions/day. |
| `perps/learn-about-trading/fees`, `funding`, `markets/compute`, `perps/liquidity-rewards`, `trading-competitions` | Perps fee at the $0 tier: taker 0.05%, maker 0.02% of notional; maker rebates only from $500M of 30-day volume. Funding hourly, premium sampled every 5 s, non-crypto scale 0.5, cap 4%/h. **Compute perps**: `H100-USD` live since 2026-11-26, `B200-USD`/`B300-USD` planned for 2026-11-27; index = 24-hour average of Ornn hourly prints. Perps liquidity rewards: $325 or $100 per market per day (ANT $3,000/day until 2026-11-30) but a firm must hold **>= 1% of the tier's maker volume** and quote >= $1,000-5,000 per side within 10 bps. Competitions score = PnL * sqrt(boosted volume). |

Web search (2026-11-27, WebSearch tool, 2 queries): no article with a concrete rewards-farming method was found; results were the official docs plus a KuCoin/Odaily piece titled "Polymarket LP Incentive Mechanism: four key insights and cost traps" (https://www.odaily.news/en/post/5209869 - not opened, date unknown). The second query surfaced that Kalshi lists the same H100 monthly-average product (series `KXH100MS`), which I then pulled from Kalshi's public API (section 5).

## 2. Liquidity rewards: measurement (all on 2026-11-27, about 15:30-17:00 UTC)

Variants run: 4 on the yield question (V1 crude loss model, V2 inventory model, V3 markout on a random sample,
V4 wide screen + "quiet pool" rule). One formula error was corrected between V1 and V4 (the competing score in V1
ignored the single-sided credit; V4 uses the range and a consistent central value). V2 and V3 matched markets on a
60-character question prefix, which collides inside the Ornn family; V4 does not.

### 2.1 The program as it stands (call: `GET clob.polymarket.com/rewards/markets/multi?order_by=rate_per_day&position=DESC&page_size=500`, 41 pages)

- 20,373 distinct markets listed; **8,802 have an allocation active today; total configured pool $144,132 per day**.
- Concentration: top 10 markets $9.7K/day, top 100 $51K, top 500 $95K, top 1,000 $111K. 187 markets pay >= $200/day,
  278 pay $50-200, 1,493 pay $10-50, 3,517 pay $2-10, 3,325 pay under $2.
- Settings (min size in shares, max spread in cents): (20, 4.5) 3,710 markets; (20, 6.5) 2,363; (50, 4.5) 492;
  (30, 4.5) 492; (200, 4.5) 407; (100, 1.5) 336; (200, 1.5) 181.
- Highest rates today: Taipei mayor (Puma Shen $1,081, Chiang Wan-an $1,019; min 300 shares), seven "average Ornn
  H200 rental price" markets at $960 each, Spain PM $873 / $727, Fed December +25 bps $750, dozens of Ornn
  H100/B200/B300 markets at $640.
- Allocation `start_date` is 2026-11 for 1,127 of 1,137 screened markets (mostly 24-27 Nov): configurations are
  re-issued often, so the pools seen today are days old.

### 2.2 Pool versus resting depth (V4: 1,362 markets with rate >= $20/day, one book each via `POST clob/books`)

- 1,137 of them can be quoted with $200 (the rest need more than $200 to meet the minimum size on both sides, or
  have a one-sided book).
- Sum of pools $108,318/day against **$18.76M resting inside the reward band -> 0.58% per day** of in-band depth
  (about $173 of resting quotes per $1/day of pool).
- By family (pool/day, in-band depth, pool per $ of depth per day, median 24h volume):
  Ornn GPU prices 466 markets, $51.8K, $6.58M, 0.79%, $73 | other 411, $35.2K, $4.16M, 0.85%, $974 |
  daily temperature 151, $9.9K, $1.43M, 0.69%, $882 | politics 72, $8.4K, $5.01M, 0.17%, $9.0K |
  economics 28, $2.6K, $1.52M, 0.17%, $509 | crypto 7 | sports games 2.
- What $200 of two-sided quotes at the inside (or 1 cent from the midpoint) would be credited, per market per day:
  pessimistic / central / optimistic median **$1.74 / $3.37 / $11.73** (p10 $0.46 / $0.75 / $2.62; p90 $12.9 /
  $18.6 / $40.4). On the pessimistic estimate 30% of markets pay under the $1 minimum (i.e. nothing).
  The quadratic score favours tight quotes, which is why $200 at the inside is credited more than its pro-rata
  $1.16/day; it is also the first to be hit.
- First sample (V1, 400 markets): eligible with $200 = 147/150 top, 122/150 mid (rate 10-200), 65/100 low (rate
  2-10); in the low tier 51% of markets would pay under $1/day.
- `market_competitiveness` (a field in the API with no documentation) correlates only 0.52 (log-log) with my
  competing score, so it was not used.

### 2.3 What the pool is paying for: price moves and adverse selection

- Volatility of rewarded markets (V1, 90 markets, 5-minute `data-api/v2/prices-history?interval=1w`): median
  5-minute s.d. 0.94 c / 1-hour s.d. 2.05 c / 7-day range 27.5 c in the top tier; 0.80 / 2.41 / 25.9 in the mid
  tier; 0.19 / 0.47 / 8.0 in the low tier. Daily-temperature markets: 5-minute s.d. 1.6-2.4 c, 20-40 c range in 1.5 days.
- V1 (maker re-centres every 5 minutes, loses N*(|move| - s) whenever the 5-minute move exceeds s; deliberately
  pessimistic): median loss $37.6/day (top), $23.2 (mid), $2.0 (low) against median central reward $4.3 / $2.3 /
  $0.6. Reward > loss in 2/30, 4/30, 11/30 markets.
- V2 (inventory model; meant to be optimistic but still fills against a stale 5-minute quote): median trading P&L
  -$25.5/day (top), -$9.5 (mid), -$0.03 (low). Both V1 and V2 overstate the damage where the printed price
  flickers without trades; they are bounds, not estimates.
- V3 (real fills: makers' aggregate 1-hour markout vs the pool; 43 markets with trades): median markout
  -1.4 c per share (top -0.2, mid -1.4, low -2.7). Pool + markout per day: top 15 markets +$6,155 on $556K of
  in-band depth (**+1.1%/day**), mid 14 markets -$1,720 on $132K (-1.3%/day), low 14 markets -$1,546 on $17.7K
  (-8.8%/day). Low-rate pools do not cover what takers take from makers.
- V4 "quiet pool" rule fixed in advance (rate >= $100/day, 24h volume < $5,000, eligible with $200): 127 markets
  pass (62 other, 34 Ornn, 22 temperature, 6 politics). First 60 by rate: pools $20,364/day, makers' aggregate
  1-hour markout -$6,273/day, in-band depth $2.30M -> **net +0.61% per day on depth** (Ornn +0.48%, other
  +0.91%, temperature +0.80%). Median 7-day price range 27-40 c, median markout -0.9 to -2.3 c/share,
  median 18-53 fills per market in the window, markets 1-4.5 days old. $200 in every one of the 60 would be
  credited $191 (pessimistic) to $346 (central) per day in total - which nobody can do with $200; per market the
  median is $1.6 / $3.9 / $7.2.
- Caveats that matter: one book snapshot (depth at other hours unknown; the docs score every minute); pools 1-3
  days old (depth normally follows the money); markout over a few days and few fills; `prices-history` price may
  be a midpoint or a last trade; a small maker at the inside is hit first and by the best-informed taker, so his
  markout is worse than the aggregate; payouts cannot be verified without an account.

### 2.4 Who harvests it (wallets found as holders in the quiet-pool markets; `data-api/v2/holders`, then `user-stats`)

`tools_scratch/r3_reward_wallets.py` -> `data/r3/reward_wallets.json` (45 wallets). All-time, USD:

| profile | wallet | trade P&L | fees | maker rebate | **reward income** | economic P&L |
|---|---|---|---|---|---|---|
| ArmageddonRewardsBilly | 0xc8ab97a9089a9ff7e6ef0688e6e591a066946418 | +350,086 | -253,988 | 86,721 | 1,207,786 | 1,627,040 |
| Haradwaith | 0x21ffd2b7a212a6f277ed3eca1a9f8efcbca90d71 | -496,318 | -57,180 | 74,026 | 912,799 | 489,837 |
| pootytherewardfarmer | 0xa3e22cd32aa9238ef7dbcfb4761e33b9eaa1fdf8 | -353,798 | -9,910 | 12,602 | 669,554 | 328,084 |
| AiBird | 0xa58d4f278d7953cd38eeb929f7e242bfc7c0b9b8 | +140,491 | -30,404 | 4,156 | 201,441 | 322,779 |
| xtxpleasecallme | 0xad5353afe30c2da57709e2704ef3ccdcf67eef24 | +231,871 | -65,941 | 20,515 | 160,202 | 361,894 |
| 0x49F206 | 0x49f206f4fb2210a28af4795e4e0b6532cf0bd7b4 | -47,140 | -32,743 | 11,436 | 120,906 | 79,511 |
| LornaPredicts | 0x74957ea27ac4fbdee46d861fdae357859ff67fcf | +34,172 | -6,106 | 10,336 | 102,089 | 145,538 |
| needleladder | 0x4462e46cf0d31466693058893f4913e2411fbfdf | -43,197 | -5,110 | 1,598 | 47,591 | 1,092 |
| zhaocaimao8888 | 0xbbca3e86a17c383ac291890d56359e75eaa2c369 | -27,794 | -6,228 | 1,085 | 38,919 | 6,258 |
| Laribobibo | 0x721a29613c653d9430532402784c8b25ad5d9295 | -39,837 | -91 | 1,285 | 35,476 | -3,136 |
| pupka-zalupka | 0x0b14f8c4de241192f042a6bc2897d5532fd0f1f5 | -12,304 | -1,659 | 534 | 18,194 | 4,900 |
| balabalababalabala | 0x277989790d4a8c782d7a4992e13c2dcaa031239a | -48,394 | -12,607 | 2,685 | 14,472 | -39,278 |
| verybadtrader | 0x02e564adb4c1647520fa398f1bc432e2d2dd98aa | -16,468 | -132 | 788 | 9,274 | -6,527 |
| pootythetemperaturefarmer | 0x486c8e5df09352620636b38e849ac10272126799 | -6,751 | 0 | 599 | 7,869 | 1,718 |
| pootythefinancefarmer | 0xe2a3b5b5f39dc6c46ac6d59672052282abb48e01 | -3,854 | 0 | 176 | 7,141 | 3,465 |
| automatedmm | 0x5b9e7fd7b867467b7c16d88f11c24027af1f3423 | -8,386 | 0 | 49 | 1,414 | -6,907 |
| rewardspopeye. | 0xe7ae3f162cf31233039a0555041004dcce0e4f1f | -785 | 0 | 0 | 97 | -688 |

`wallet_check.py --monthly` (gross = trade P&L, rebates column = rebates + rewards, NET = change in economic P&L):

- **pootytherewardfarmer**: gross negative in every one of 22 months; 2026-09 gross -43,112 / rewards 47,712 / net
  +4,600; 2026-10 -21,051 / 35,934 / +14,608; 2026-11 -17,513 / 19,139 / +1,610. Kept 20% of Sep-Nov rewards.
  Monthly fill volume $200-370K.
- **pootythetemperaturefarmer** (joined 2026-09-26, zero taker fees, maker tier 0): Sep -541 / 1,045 / +505; Oct
  -3,769 / 4,680 / +912; Nov -2,441 / 2,743 / +302. Kept 20% of rewards on $16-84K of monthly fills.
- **pootythefinancefarmer** (joined 2026-10-01, the Ornn/finance markets): Oct -2,289 / 3,914 / +1,625; Nov
  -1,565 / 3,403 / +1,840. Kept 47%. $31-34K of monthly fills.
- **needleladder**: Oct -12,764 / 11,027 / -2,139; Nov -27,522 / 37,960 / +6,034 (taker fees 4,403); still tier 0 on
  both rebate ladders with $1.0M of November volume.
- **Haradwaith**: Sep -14,067 / 140,402 / +126,194; Oct -153,039 / 135,466 / -18,112; Nov -51,442 / 81,610 / +30,180.
- **ArmageddonRewardsBilly**: Sep +578,915 gross (a directional win) / 60,935 / +633,136; Oct -8,339 / 30,108 /
  +22,173; Nov +22,857 / 26,934 / +49,287. Rewards were $160-220K per month in May-June 2026 and are $27-61K now.

Reading: rewards are real money (single wallets have been paid $0.7-1.2M), the trading leg of a reward farmer
loses in almost every month, and the specialised small farmers keep 20-47% of what they are paid. Several small
ones are under water. Capital deployed by these wallets is not visible.

## 3. Resolution timing and near-certain outcomes (study R1/R2; 2 variants)

Calls: `gamma/markets?closed=true&end_date_min=2026-11-17&volume_num_min=10000&order=volumeNum`,
`data-api/v2/resolutions?condition=`, `data-api/v2/trades?condition=&start=&end=`. Fills at price >= 0.90 in
the 24 h before `resolved_at`. Scripts `tools_scratch/r3_resolution_window*.py`, `r3_resolution_analyze.py`.

- Sample problem: of 500 markets by volume only 259 returned a `resolved_at`, and 239 of those are sports/esports
  games. Gamma refuses `offset` above 2,000 ("use /markets/keyset"), `end_date_min` filters the scheduled end, not
  the close, and `reporter` came back empty on condition-keyed rows. **The non-game part (R2: 23 markets, 20 of
  them one Nobel Peace Prize event) is not evidence of anything** and its 2% "return" is pre-announcement risk
  inside one event. A proper version needs keyset paging on close time and proposal timestamps.
- Sports/esports games (239 markets, fee rate 0.05, none disputed; resolution lands about 2-3.4 h after the listed
  `endDate`, which for games is close to the start):
  - Taker buys at **0.99-1 within 2 h of resolution**: 219 markets, $4.44M bought, gross +0.247%, **net +0.227%**
    after the fee (0.05 * 0.99 * 0.01 = 0.05 c per share); 1 market of 219 lost (-$6.7K). Whole 24 h: 223
    markets, $10.3M, net +0.157%.
  - Taker buys at 0.98-0.99 (<2 h): 214 markets, $2.23M, pooled net -1.59%, per-market mean +0.87%.
    At 0.95-0.98: $5.07M, pooled -0.15%, per-market +1.44%. At 0.90-0.95: $5.69M, pooled -1.41%, per-market
    +1.78%. All prices >= 0.90, last 24 h: $27.0M, **pooled net -2.81%**, per-market mean -0.06%. In 32 of 239
    games takers bought the eventual loser at >= 0.90 ($1.58M; Bayern 2026-11-20 $587K, Eagles-Cowboys $422K,
    Hornets-Lakers $366K). No taker edge in backing in-play favourites at a 0.05 fee.
  - Resting bids (taker sells at >= 0.90, zero maker fee): at 0.99-1, $17.36M of the eventual winner was sold in
    237 markets (about $73K per game), maker gain $24.6K, against $1.2K of an eventual loser in 1 market ->
    **+0.135% on turnover**. At 0.90-0.95 (<2 h): $1.06M of winners (+$88.4K) vs $26.9K of losers in 17 of 197
    markets -> +5.7% dollar-weighted, but by market count 8.6% of games had loser fills against about 7.5%
    implied by the price: the dollar weighting is a duration effect (a winner sits above 0.90 for a long time),
    not an edge. All >= 0.90: $20.2M, +0.50%.
- Lifecycle facts from the docs: undisputed UMA market settles about 2 h after the proposal, disputed 4-6 days;
  `/v2/resolutions` exposes `status` (proposed / challenged / disputed / resolved), `was_disputed` and an
  `expected_settlement_time` with its basis.

## 4. Other structural items

- **Holding rewards**: 73 open events carry the `earn-4` tag (call: `gamma/events?tag_slug=earn-4&closed=false`),
  $171.6M of liquidity: the 2028 nominee and election events, "What price will Bitcoin hit in 2026?", and all 32
  Ornn GPU-price events. Market field `holdingRewardsEnabled`. 4% a year on $200 is $8.
- **Fee holiday**: the Ornn markets have `feeSchedule.rate = 0`, `feeType = "zero_fees"` although they are tagged
  finance/tech (0.05 in the table). Zero fee also means no maker rebate and no taker weighted volume.
- **Negative risk**: complete-set arbitrage exists when the Yes asks of all outcomes sum below 1 (buy all, one
  pays $1) or the Yes bids sum above 1 (buy one No, convert to Yes of every other outcome, sell them). NOTES.md
  already records the snapshot: 176 open neg-risk events, 0 arbitrage after fees, median sum of asks 1.036, sum of
  bids 0.965; sums under 1 were all augmented events (unnamed "Other"). Not repeated here.
- **Ticks and sizes seen in the books**: `min_order_size` 5 shares; tick 0.01 on Ornn markets, 0.001 on the
  Taipei mayor market; World Cup markets were moved to 0.0025 on 2026-07-02.
- **Rebate tiers in practice**: needleladder with $1.01M of volume in November has 30-day weighted volume of 91K
  (taker) and 126K (maker): tier 0 on both. A $200 account is nowhere near $200K.

## 5. Compute (GPU rental price) markets: a new product with three venues

- Polymarket events `h100|h200|b200|b300-average-rental-price-in-<month>-<year>` created 2026-11-23; 30 events
  found by `gamma/public-search?q=Ornn rental price`, Dec 2026 to Dec 2028, binary "Above $X" ladders, not
  neg-risk. Rule (quoted from the event): resolves on "the arithmetic mean of the finalized daily settled values
  of the Ornn OCPI-H100 index dated within December 2026, as published by Ornn, rounded to the nearest cent",
  source data.ornn.com. Zero fee, liquidity rewards $240-960 per market per day, holding rewards on.
- Polymarket perp `H100-USD` (call `GET https://api.perpetuals.polymarket.com/v1/info/tickers`, 2026-11-27 ~16:00
  UTC): index 3.1775, mark 3.177, last 3.125, mid 3.127, open interest 10,530 GPU-hours, 24 longs / 14 shorts,
  funding 0.000625%/h (the fixed interest leg only). `B300-USD` index 10.866, `B200-USD` index 9.763 (1 long, 1
  short each). `ANT-USD` index 89.87, OI 7,671.
- Polymarket ladder, H100 December 2026 (bid/ask): >$2.80 0.82/0.83, >$2.90 0.66/0.67, >$3.00 0.57/0.58, >$3.10
  0.44/0.45, >$3.20 0.37/0.38, >$3.30 0.21/0.22, >$3.40 0.12/0.13, >$3.50 0.10/0.11. Implied median about $3.05
  against an index of $3.18. January 2027: >$3.00 0.50/0.51, >$3.50 0.19/0.20.
- Kalshi series `KXH100MS` (call `GET https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXH100MS&status=open`,
  94 open markets). **November 2026** (closes 2026-12-01): >$3.00 bid 0.96 / ask 0.99; >$3.25 bid 0.00 / ask 0.05 -
  with four days left the monthly average is pinned between $3.00 and $3.25. December 2026: >$3.00 0.55/0.87,
  >$3.25 0.38/0.87, >$3.50 0.18/0.53, >$3.75 0.07/0.41, >$4.00 0.01/0.36; open interest 27-1,523 contracts per strike.
- Cross-venue gap at that moment: Polymarket Yes >$3.50 offered at 0.11 while Kalshi bids 0.18 for the same strike
  (buy PM Yes 0.11 + buy Kalshi No 0.82 = 0.93 for a $1 payoff if both settle on the same number), and PM Yes
  >$3.20 at 0.38 dominates Kalshi Yes >$3.25 bid 0.38. Sizes behind the Kalshi bids were not pulled, Kalshi's
  rule text here says only "average value of NVIDIA H100 compute per hour", and whether the owner can open a
  Kalshi account from Serbia is unknown.

## 6. Things I could not do

- No account: reward payouts, the `rewards/user/total` endpoint, the combos RFQ stream and Last Look cannot be observed.
- No WebSockets: the per-minute reward sampling cannot be replicated; everything in section 2 is one REST snapshot.
- Reddit / Medium not opened; the Odaily article on LP incentives was not opened.
- UMA proposer rewards and proposal timestamps were not pulled (would need the UMA subgraph or on-chain logs).
- Ornn's own daily index history (data.ornn.com) was not fetched, so the "monthly average becomes known" idea is
  supported only by the Kalshi November ladder.

## Verification pass

Sceptic's check of this catalog, 2026-11-27 (evening UTC). 24 tool calls, no sub-agents, read-only. Everything below
was re-pulled by me; inline scripts were not saved, the calls are named so they can be repeated.

### What I checked

1. **Docs re-fetched live** (`https://docs.polymarket.com/<path>.md`, 14 pages) and compared byte-for-byte with
   `data/pm_docs/`: all 14 identical. Numbers confirmed in the text: rewards minimum payout $1, c = 3.0, 1,440 samples,
   single-sided rule inside 0.10-0.90; maker tiers 0/3/7/10/15% from $200K; taker tiers 10/25/40/50/60%; fee table;
   holding reward 4.00%; resolution (bond "typically $750", 2-hour challenge, 4-6 days disputed); referral 10% / 5%,
   $10,000 threshold, 30 days; builder caps 100 bps / 50 bps; combos 400 ms / 10 s / Last Look at about $2,500
   notional; perps reward pools $325 / $100 / ANT $3,000 to Nov 30 and the 1% rule; compute perp index definition.
   Not found by my grep: the "1 s" length of Last Look.
2. **All 12 named wallets** through `python3 -I tools/wallet_check.py <address> --monthly` (addresses, names from
   `data/r3/reward_wallets.json`). The researcher's table holds up to within a day's drift. Daily series
   (`data-api/v2/user-pnl?interval=all&fidelity=1d`) and the first 1,000 open positions for the four small farmers.
3. **Rewards list**: saved pull re-counted (20,500 listed, 8,819 active, $144,263/day) and the live top-100 page
   compared with it.
4. **Ornn / Kalshi / perps**: gamma event `h100-average-rental-price-in-december-2026`, Kalshi `KXH100MS` open and
   settled markets plus daily candlesticks, perps tickers, and Ornn's own free history.
5. **Sports resolution study**: recomputed from `data/r3/resolution_fills.json` with finer time buckets.

### What changed

- **Stale fact in section 1**: the crypto taker delay is 150 ms since 2026-09-04 14:00 UTC (changelog line 199); the
  notes say 50 ms. `secondsDelay` and `customLiveness` were already in NOTES.md (1 s on most sports, 0 on NBA;
  challenge window 900 s on sports and daily temperature, 600 s on crypto levels, 2 h default; bonds $250 / $500),
  so "2 hours" and "$750" are the docs' defaults, not what sports and weather markets use.
- **Reward pools are re-set daily, they are not "days old"**: $112.1K of the $144.3K/day carries an allocation
  `start_date` of Nov 26 or 27, including the Taipei mayor market created in August. 13 of the top 100 rates changed
  between the researcher's pull and mine a few hours later (Spain PM 873/727 -> 800/800, Taipei 1,081 -> 1,066).
  `start_date` is the last re-configuration. A screen on today's rate does not tell tomorrow's rate.
- **The second reward asset** (0xc011a7e1..., 151 allocations) has `rate_per_day` 0 in every row: nothing was missed.
- **Pools do pay** (new evidence): pootythefinancefarmer's daily reward income was $41-82 on Nov 17-24 and $977 /
  $271 / $192-277 on Nov 25-27 after the Ornn pools started; needleladder went from $1.0-1.9K/day to $3.8-4.9K/day
  on Nov 25-27 (trading leg -$1.7K to -$2.7K a day, kept $1.2-3.1K a day).
- **"Quiet" is wrong for the strikes that carry the money**: in the H100 December ladder the four near-the-money
  strikes pay $640/day and traded $21-102K each in 24 h (event $279K); the eight wing strikes pay $27/day. Minimum
  size there is 200 shares (not 20-50), so $200 quotes exactly one market on both sides.
- **Wallet reading, added**: ArmageddonRewardsBilly lost net in May and June 2026 (-136K, -43K) while receiving
  $160-220K of rewards a month; rewards of the three large farmers have fallen 3-8 times since June. xtxpleasecallme
  is not a farmer: Gold taker tier (wv 648,965), October gross +144,550 is directional, and 201,931 of its 386,805 is
  an unrealized LOSS already inside the figure. chessplayer has positive trading net in Oct-Nov (+6.2K, +9.6K
  without rewards), so its result says nothing about Ornn pinning. Negative days: pootythefinancefarmer 20 of 57,
  pootythetemperaturefarmer 26 of 62, needleladder 47 of 88. pootythefinancefarmer holds more than $15.4K of
  inventory (first 1,000 positions only) to keep about $1.8K a month.
- **Selection**: farmers were found through holder lists, i.e. makers who ended up with inventory. Makers who quote
  and cancel in time are under-represented, so the "kept 20-47%" range is not the distribution of outcomes.
- **Ornn daily values are public and free**: `https://data.ornn.com/api/public-index/gpu/H100%20SXM/index-history`
  returns three months of daily settled values without a key (91 rows, 2026-08-28 .. 11-26). Monthly means: Sep
  2.8270, Oct 2.9403, Nov 3.1492 after 26 of 30 days. Daily values are noisy: median absolute day-to-day change
  $0.10, p90 $0.27, range 2.46-3.53 in three months.
- **Kalshi settled Sep and Oct at 2.83 and 2.94** (`expiration_value`), equal to the mean of Ornn's daily settled
  values rounded to the cent, although Kalshi's rule text says "arithmetic mean of hourly values". Two months of two.
- **Pinning on Kalshi's settled months gave no cheap decided side on the Yes side**: for strikes that settled Yes the
  daily closing ask was 0.98-1.00 from about the 20th on while only the bid lagged (0.59-0.95); for strikes that
  settled No a stale Yes bid of about 50 contracts occasionally stood at 0.09-0.15 in the last third of the month.
  Volume was zero on most days. My "decided" date used a crude 30-day range bound and is not reliable.
- **Cross-venue gap, re-measured**: Polymarket Yes above $3.50 ask 0.11, Kalshi bid 0.17 for 50 contracts: 0.94 per
  $1 before a Kalshi fee of about 1 cent, on $50 of notional. The "$3.20 vs $3.25" dominance is gone (Kalshi bid 0.35).
- **Sports 0.99+ study reproduces** ($4.44M taker buys within 2 h, net +0.227%), but the time split changes its
  meaning. Taker BUYS at 0.99+: none at all in the last 15 minutes before resolution (the post-proposal window);
  $2.44M at 15-30 min (+0.285% net), $1.73M at 30-60 min (+0.476%), $0.27M at 1-2 h (-1.88%, the Eagles-Cowboys
  reversal, -$6.7K, 90 minutes before resolution). Since NBA games resolve 16-19 minutes after the last play, that
  buying is the end of the game, not a settlement discount. Only the resting-bid leg exists after the game:
  $5.32M in 232 markets in the last 15 minutes at +0.101%, $9.23M at 15-30 min at +0.144%, no loser. Also 84 of
  the 239 tapes hit the 3,000-row cap, so every "last 24 h" total in section 3 is a lower bound taken from the end
  of the tape.
- **Referral rate**: docs say 10% / 5%; NOTES.md (X sweep) says affiliates earn 20%+ since 2026-10-23. Not
  reconciled; probably a separate affiliate deal.
- **$1 minimum payout**: the docs sentence does not say "per market". The yield model applies it per market; if it
  is per account per day, the "30% of markets pay nothing" line is too pessimistic for a multi-market account and
  irrelevant for a one-market one.

### Credibility changes

- Liquidity-rewards farming 4 -> 3: the subsidy is real and is being paid, but the net-of-adverse-selection figure
  rests on one book snapshot and pools re-set daily; the two newest small entrants are net negative.
- Ornn pinning stays 3 for the arithmetic and the data source, with the edge itself unproven (see above).
- Sports post-game discount 3 -> 2 as a strategy: the taker leg is in-play risk, the maker leg is 0.10-0.14% a turn
  under price-time priority.
- UMA proposer 2 -> 1: bonds seen by the lab are $250-500, at or above the whole stake, and no reward size is known.
- Everything else unchanged. Nothing dropped: every cited source exists and says what is claimed.

### Not checked

Combos RFQ and perps rewards beyond the docs text; negative-risk snapshot (taken from NOTES.md again); the V1-V4
yield and markout scripts were not re-run, only their saved inputs were re-counted; no X or Reddit source exists in
this catalog to open.
