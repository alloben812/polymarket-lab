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

