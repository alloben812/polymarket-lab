# Copy trading of selected wallets with a delay — protocol

Written 2026-11-27 ~18:30 UTC, before any outcome-based number was computed. Only data formats were inspected
before this file was saved (trades feed, market tape, user-pnl, leaderboard response shapes). Frozen after saving:
changes go to "Deviations" in results.md, new ideas to "Ideas, not tested".

## Question

If a small account chooses wallets by a rule fixed in advance on an early window and then, in a later window, copies
each of their BUY entries 10 s, 60 s or 5 min after the wallet's fill is visible, at a price the tape shows was
buyable after that delay, size about 10 USD, held to resolution or closed when the wallet closes, does it keep money
after taker fees? Separately for entries the wallet made as a taker and as a maker (a maker entry cannot be copied at
the wallet's price), by wallet type and by category. How many copyable entries per day are there?

## Windows (UTC)

- Early (selection and in-sample copy run): entries 2026-11-07 00:00 (1794009600) .. 2026-11-21 00:00 (1795219200).
- Late (out-of-sample, the reported window): entries 2026-11-21 00:00 .. 2026-11-26 00:00 (1795651200). It contains a
  weekend (21-22 Nov), which is reported per day.
- Outcomes and wallet exits are read up to the data cut (2026-11-27, time of download).

## Wallet pool and selection rule (fixed)

Pool = union of
1. `leaderboard?category=C&time_period=month&sort_by=PNL`, top 25, for C in crypto, sports, politics, weather,
   economics, mentions, culture, tech, finance, esports (the board is labelled with the category it came from);
2. every address in `catalog/raw/x1_wallets.md`;
3. every 0x address found in `studies/wallets/*/README.md` and `studies/wallets/*/*.json`.

Selection metric (early window only): from `user-pnl` daily points, the change from the point at or before
1794009600 to the point at or before 1795219200 of `economic_pnl - maker_rebate - taker_rebate - reward_income -
sponsored_income - referral_income` (= trading result without rebates or rewards, which a new account would not get).
Eligible: metric > 0 and `trade_count` increase in the early window >= 30.
Chosen: for each leaderboard category, the top 3 eligible wallets of that board by the metric (a wallet already
chosen is skipped and the next one taken); then the top 6 eligible wallets of sources 2+3 not already chosen. At most
36 wallets. Wallet type (taker-style / maker-style / mixed) is fixed from the early window: share of the wallet's
BUY dollars in its early-window fetched fills that were taker fills (full feed minus `taker_only=true` feed, as in
NOTES.md): >= 60% taker-style, <= 40% maker-style, otherwise mixed.

Known bias, accepted: source 1 is today's month board, so pool membership uses late-window information
(survivorship in favour of copying). A negative result is therefore conservative; a positive one is suspect.

## Entries and sample (fixed, to fit the 110-minute budget)

- For each chosen wallet and window: BUY fills from `trades?user=W&taker_only=false&side=BUY&start&end`, newest first,
  at most 4,000 rows per wallet and window. If the cap is hit, the window is covered only from the oldest fetched row
  on; per-day counts use the covered span.
- An entry = the wallet's first BUY fill in a token (outcome of a market) inside the window. Its time `tb` = block time.
- Sample: at most 25 entries per wallet in the late window and 15 in the early window, uniform random without
  replacement (Python `random.Random(20261127)`, entries sorted by (tb, token) before sampling).
- Per sampled entry: the wallet's fills in that market (`trades?user=W&condition=C&taker_only=false`, to the data
  cut) and the whole-market tape (`trades?condition=C`, walked from newest back past `tb - 60`, at most 25 pages =
  25,000 rows; if the walk cannot reach `tb`, the entry is "not evaluable" and counted as such).
- Entry type: TAKER if the tape has a row with taker wallet = W, same block time, same outcome, side BUY; else MAKER.

## Fill rule (conservative)

- Match time of a tape row = block time - 3 s. Buyable evidence for outcome X: a taker BUY of X at price p, or a
  taker SELL of the other outcome Y at q (X buyable at 1 - q), with its size (as `pmlab.updown.buyable`).
- The copier learns of the entry at `tb` (block time) and sends a marketable order at `tb + d`, d in {10, 60, 300} s.
  Fill = the first block (one block time) whose match time is in [tb + d, tb + d + 30]; all buyable rows of X in that
  block are aggregated at their VWAP; shares = min(10 USD / VWAP, shown shares). If no such block or the fill is under
  1 USD: not filled (counted). No other price is used.
- Taker fee on the copier's buy: `rate * p * (1 - p)` per share, rate from the gamma market `feeSchedule` (current
  rates; fallback: `pmlab.fees.CURRENT` by category). Rebates 0. The same current rates are applied in both windows
  (what a copier pays today).

## Exits (two variants per delay)

- HOLD: held to resolution, payoff = `final_price` of the token from `tokens?condition=` (1, 0 or 0.5). If the market
  is not resolved at the data cut, the position is marked at the last tape price of that token (last row in token
  terms) and flagged; results are also shown on resolved entries only.
- MIRROR: if after `tb` the wallet's cumulative SELL shares of that token reach 50% of its cumulative BUY shares of
  that token (from `tb` up to that moment), at that block time `tc` the copier sells at the first block with match
  time in [max(tc + d, fill time), +30 s] that shows a resting bid for X (taker SELL of X at p, or taker BUY of the
  other outcome at q -> X sellable at 1 - q; `pmlab.updown.sellable`), up to the shown size, paying the taker fee;
  anything not sold is held as in HOLD.

## Variants (6) + 1 reference

3 delays x 2 exits = 6 copy variants, size 10 USD. Reference (counted as a 7th run, not a strategy): the wallet's own
entry price, 10 USD, taker fee only if the entry was TAKER, HOLD exit. No other variant will be run.

## Statistics

- Unit of clustering: the market (condition id). Main number per variant and window: net return per dollar spent =
  sum(net) / sum(cost), with the cluster-robust standard error of `pmlab.stats.ratio_cluster` by market, 95% CI =
  +-1.96 se; also mean net USD per filled trade, fill rate, number of entries / markets / wallets.
- Breakdowns (reported, not separate variants): entry type TAKER / MAKER; wallet type; category
  (`pmlab.gamma.family`, mentions by tag, crypto up/down separated); resolved-only.
- Robustness: clustering by wallet; dropping the 5 best markets.
- Opportunities per day: all late-window entries of the chosen wallets per UTC day (not only the sample), times the
  sample fill rate per delay.

## Decision rule (fixed)

A live micro-test is proposed only if, in the LATE window, a (delay, exit) variant has, overall or in one subgroup
among {TAKER entries, MAKER entries, taker-style wallets, maker-style wallets, a category with >= 30 markets}:
return per dollar > 0 with t >= 2.0 (overall) or t >= 3.0 (subgroup, for multiple testing), >= 50 markets, the same
sign in the early window, still > 0 after dropping its 5 best markets, and t >= 1.5 when clustered by wallet.
Otherwise the verdict is "nothing here deserves a live test". The reference row never qualifies.
