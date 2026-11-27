# Protocol: lag of thin, low-fee crypto up/down series against exchange prices

Written 2026-11-27, before any tape, outcome or result of this study was loaded. Part A is the protocol fixed by
the lab lead, copied as given. Part B lists every concrete choice needed to implement it. After this file is
written the rules do not change; anything thought of later goes under "ideas" in results.md.

## A. Protocol as given

**Question.** BTC 5-minute markets are a speed race with a 0.05 fee. The other series are thinner and four of them
carry a fee five times lower. Do they lag exchange prices enough to trade without co-location?

**Series and period.** eth 5m, eth 15m, sol 15m, xrp 15m (fee rate 0.01) and btc 15m (0.05); windows starting
2026-11-21 00:00 UTC to 2026-11-26 23:45 UTC. Tune on 21-24 Nov, report 25-26 Nov separately. As a reference for the
lag measurement also load 300 btc 5m windows spread evenly over the same days.

**Data.** pmlab.updown.windows / load_market (official up_won, price_to_beat, final_price, fee_rate),
pmlab.updown.tape and buyable (match time = block time minus 3 s), pmlab.px.Px.load('ETHUSDT' | 'SOLUSDT' |
'XRPUSDT' | 'BTCUSDT', days), pmlab.fair.fair_up(px, t, t0, dur=300 or 900, lookback=60).

**M1 Size of the pond.** Per series: markets with at least one trade, median and total taker dollars per day,
distinct taker wallets, share of the five largest takers.

**M2 Who pays whom.** For all taker fills, gross edge per share (BUY: outcome minus price; SELL: price minus
outcome), fee, net; by series, by quarter of the window, by price bucket; clustered by market.

**M3 Reaction lag.** Per series build, second by second, the last trade-implied Up price (a trade in Down at p
implies Up at 1 - p) on block time, and correlate its changes with changes of the model fair value at lags from -5
to +30 seconds; report the lag of maximum correlation and compare with the btc 5m reference measured the same way.
The absolute lag includes the 2-3 s block delay; the difference between series is what matters.

**M4 Taker rule (12 variants = 4 delays x 3 thresholds, per series).** For each buyable print with match time m in
[t0 + 5, t1 - 5]: f from Binance data up to m - D, D in 0, 1, 2, 5 seconds; buy when f - q - fee(q) >= thr, thr in
0.01, 0.02, 0.04; size = min(print size, 50 shares); at most 300 shares per side per market; hold to official
settlement. Report net cents per share, percent of turnover, dollars per day, trades, markets, t clustered by
market, for tuning and reporting periods.

**M5 Late lock-in rule (6 variants, per series).** For prints with m >= t1 - 45 and m <= t1 - 2, f from data up to
m - 1: buy the favoured outcome when f >= 0.97 and q <= f - margin, margin in 0.03, 0.05, 0.08; each with and
without the extra condition that the expected settlement average is at least 2 basis points away from the price to
beat. Same sizing. Report win rate with a Wilson interval, net cents per share, dollars per day, trades, markets, t.

**Proxy check.** Per series report the distribution of (px.twap(t1, 60) - final_price) - (px.twap(t0, 60) -
price_to_beat) in basis points of price, and the share of windows where the Binance proxy calls the official outcome
wrongly.

State the total number of variants run.

General rules (NOTES.md): fees always in, rebates zero, a fill is assumed only when the tape shows the price was
available at that moment, errors clustered by market (pmlab.stats.ratio_cluster / mean_se), every variant reported.

## B. Implementation choices (fixed here)

### B1. Universe and periods

- Window starts t0 with 1795219200 (2026-11-21 00:00:00 UTC) <= t0 <= 1795736700 (2026-11-26 23:45:00 UTC),
  inclusive on both ends, on the series grid (`pmlab.updown.windows`). That is 576 windows per 15m series and 1726
  for eth 5m (the 23:50 and 23:55 starts of 26 Nov fall after the stated end and are left out).
- Tuning period: t0 < 1795564800 (2026-11-25 00:00 UTC), 4 days. Reporting period: t0 >= that, 2 days. A market
  belongs to the period of its start.
- btc 5m reference: of the 1726 windows on the same grid, the 300 with index round(i * 1725 / 299), i = 0..299.
  Used for M3, for the proxy check, and as a pipeline sanity check of M2 against the lab's earlier whole-tape
  numbers. No rule variants (M4, M5) are run on it.
- A market enters the study when `load_market` returns it closed with a non-null `up_won`. Windows with no market,
  unresolved markets and markets without `condition` are counted and reported, not replaced.
- Outcome = official `up_won` (gamma outcome prices). I also count how often it disagrees with
  `final_price >= price_to_beat`; nothing is changed if it does.
- Fee rate = `fee_rate` from the market's metadata. If it is missing, the protocol's rate for the series is used
  (0.01, btc 0.05) and the count of such markets is reported. Disagreements with the expected rate are reported.
  Fee per share = rate * q * (1 - q), no rounding, rebates zero.

### B2. Tape

- `pmlab.updown.tape(condition)`, whole market, cached. Block time t; match time m = t - 3 (`updown.buyable`).
- Rows with price <= 0 or >= 1 or size <= 0 are dropped (counted).
- Every taker fill is also expressed as an equivalent buy, exactly as `buyable` does: BUY X at p stays (X, q = p);
  SELL X at p becomes (other outcome, q = 1 - p). Gross edge per share is identical in both forms
  (SELL: p - outcome_X = outcome_other - (1 - p)) and so is the fee (p(1-p)).
- Time buckets by match time m: `pre` (m < t0), Q1..Q4 (quarters of [t0, t1)), `post` (m >= t1).
- The tape is processed in ascending block time, ties in file order.

### B3. Exchange prices and the fair value

- `Px.load(symbol, ['2026-11-20', ..., '2026-11-26'])` (the 20th is needed for the 900 s volatility lookback and the
  first strike). The first 180 seconds of 27 Nov (needed only for `twap(t1)` of the windows ending at 00:00) are
  fetched once from the public mirror, cached under data/, and appended in study code.
- A 1-second kline with open time s closes at s + 1, and `Px.price(s)` returns that close. Therefore
  `G(s) = fair_up(px, s, t0, dur, lookback=60)` (default strike k = Binance `twap(t0, 60)`, default sigma: 900 s
  realised, multiplier 1.3; the official price to beat is not passed, as the protocol's call is written) uses
  information up to time s + 1. "f from data up to time x" is therefore G(x - 1). G is computed once per market for
  integer s in [t0, t1 - 1]. For s < t0 it is undefined (the strike is not known yet): prints that need it are
  skipped. G = NaN (missing price data) -> the print is skipped; such skips are counted.
- All markets are expected to have `twap_lookback` = 60; exceptions are reported and still processed with 60.

### B4. M1

Per series over the whole period: windows on the grid; markets found and resolved; markets with at least one tape
row; markets with at least one row inside [t0, t1) by match time. Taker dollars = sum of price * size over tape
rows (all rows of the market, including pre-window rows). Reported: median taker dollars per market, taker dollars
per UTC day (by window start) as median over the 6 days and mean, period total, share of dollars traded inside the
window, number of fills, median fill size in shares and dollars, share of fills below 5 shares (the minimum order
size), distinct taker wallets, share of dollars of the five largest taker wallets, and the median time between
consecutive in-window fills.

### B5. M2

All tape rows of all study markets (pre and post rows included, shown as their own bucket). Per fill:
gross = BUY: outcome - p, SELL: p - outcome (outcome of the row's token, 1 or 0); fee = rate * p * (1 - p);
net = gross - fee. Aggregates are share-weighted: sum of dollars / sum of shares via
`stats.ratio_cluster(num per market, den per market)` (cents per share with clustered se and t), and the same with
taker dollars as denominator (percent of turnover). Tables: by series (all, tuning, reporting); by series x time
bucket; by series x price bucket of the equivalent buy q: [0, 0.10), [0.10, 0.30), [0.30, 0.50), [0.50, 0.70),
[0.70, 0.90), [0.90, 1]; by series x taker side (BUY / SELL). Clusters = markets with at least one fill in the
cell. Makers in aggregate earn minus the takers' gross.

Sanity checks reported with M2: realised win rate of equivalent buys with q in [0.45, 0.55] (expected near 50%),
calibration of q by decile, sum of computed fees against rate * p(1-p) on a hand-checked slice, share of rows per
time bucket.

### B6. M3

Per market, on block-time seconds s in [t0, t1]:
- U(s) = size-weighted mean implied Up price (Up row: p; Down row: 1 - p; BUY and SELL alike) of the rows in the
  latest second <= s that has rows with block time >= t0. Undefined before the first such row (pre-window rows are
  not carried in).
- F(s) = G(s - 1): model fair value from Binance information up to time s.
- dU(s) = U(s) - U(s - 1), dF(s) = F(s) - F(s - 1), where both terms are defined.
- For each lag L in -5..30: pooled Pearson correlation, over all markets and seconds of the series, of dU(s + L)
  with dF(s) (pairs where both exist and s + L <= t1). Positive L = the tape follows Binance.
- Reported per series (all six days; tuning and reporting separately as a stability check): the full correlation
  curve, the lag of maximum correlation, the correlation-weighted mean lag over lags with positive correlation,
  the smallest lag at which the cumulative positive correlation reaches 50% of its total, and a 90% interval for
  the peak lag from 300 bootstrap resamples of markets. Same for the btc 5m reference; differences are peak lag of
  the series minus peak lag of the reference.
- Known weakness, stated in advance: in a thin market U only moves when somebody trades, so a move of F is picked
  up at the next trade, whenever that is. Sparse trading alone smears the correlation towards longer lags, even if
  resting quotes are fresh. To separate "quotes are stale" from "nobody traded", a second, level-based measure is
  reported (M3b): for every in-window tape row with block time s in [t0 + 35, t1 - 1] and implied Up price u in
  [0.05, 0.95], the root-mean-square of u - F(s - L) for L in -5..30; the L with the smallest RMS is the lag at
  which trade prices fit the model best. M3b is a measurement, not a rule; no trading variant depends on it.

### B7. M4 (12 variants per series, 5 series, 60 variants)

For each equivalent-buy print (m, outcome o, q, z) of a study market with t0 + 5 <= m <= t1 - 5:
1. f_up = G(m - D - 1), D in {0, 1, 2, 5}; skip if m - D - 1 < t0 or NaN. f = f_up for Up, 1 - f_up for Down.
2. Buy when f - q - rate * q * (1 - q) >= thr, thr in {0.01, 0.02, 0.04}.
3. Shares = min(z, 50), further cut to what is left of the 300-share cap of that (market, outcome); nothing is
   bought when the cap is used up. No minimum-size filter (as the protocol is written; a 5-share minimum order
   exists and the share of smaller prints is reported in M1).
4. Each print is used at most once per variant; Up and Down positions are not netted; held to official settlement.
   PnL = shares * (won - q) - shares * rate * q * (1 - q).
5. Reported per series, variant and period: trades, markets traded, shares, dollars spent, net cents per share with
   clustered se and t (`ratio_cluster`, clusters = markets with at least one trade), net as percent of turnover
   (dollars spent), net dollars per day (period total / 4 or 2 days), gross cents per share.

The fill assumption is the protocol's: our order takes (part of) the liquidity that the real taker took in that
print. It ignores that we would be racing that taker and anyone faster; this is a limit of the data and is stated
in the results.

### B8. M5 (6 variants per series, 5 series, 30 variants)

For each equivalent-buy print with t1 - 45 <= m <= t1 - 2:
1. f_up = G(m - 2) (data up to m - 1). The favoured outcome is Up when f_up >= 0.97, Down when 1 - f_up >= 0.97,
   otherwise there is none and the print is skipped. Only prints in the favoured outcome are considered; f is its
   fair value.
2. Buy when q <= f - margin, margin in {0.03, 0.05, 0.08}. The fee is not part of the entry condition (as written)
   but is charged in the PnL.
3. Extra condition (variants "2bp"): |E[A] - K| / K >= 0.0002, where at s = m - 2 (always inside the last 60 s):
   E[A] = (e / 60) * px.mean_between(t1 - 60, s) + (r / 60) * px.price(s), e = s - (t1 - 60), r = t1 - s, and
   K = px.twap(t0, 60): the same quantities `fair_up` uses.
4. Sizing, cap, holding and PnL as in M4.
5. Reported per series, variant and period: trades, markets, win rate with a Wilson 95% interval where the unit is
   the (market, side) position (all fills of one position win or lose together; a per-fill interval would be too
   narrow), share-weighted win rate, net cents per share with clustered se and t, percent of turnover, dollars per
   day.

### B9. Tuning, selection and verdict

- Every variant is reported for both periods. "Tuning" means: per series and per rule family (M4, M5) the selected
  variant is the one with the highest clustered t of net per share in the tuning period among variants with at
  least 30 markets traded there (if none has 30, the one with the most markets). The headline for the series is the
  reporting-period result of the selected variant. That gives up to 10 selected results; with 10 looks one |t| > 2
  by chance has a probability of roughly one in three, and the results say so.
- Total rule variants: 60 (M4) + 30 (M5) = 90, each evaluated on both periods.
- Verdict rule as given by the lab: OPPORTUNITY only if a selected variant is positive after fees in the reporting
  period with t above 2 across at least 100 markets; NO EDGE if clearly negative or zero; otherwise INCONCLUSIVE.

### B10. Proxy check and model diagnostic

- Per series (and the btc 5m reference): d = [(px.twap(t1, 60) - final_price) - (px.twap(t0, 60) - price_to_beat)]
  / price_to_beat * 1e4 in basis points: n, mean, sd, mean |d|, percentiles 1, 5, 25, 50, 75, 95, 99. Share of
  windows where (px.twap(t1, 60) >= px.twap(t0, 60)) differs from the official `up_won`, with a Wilson interval, and
  the size of the official move |final/ptb - 1| in the missed windows. Windows with missing official values or
  missing Binance data are counted and left out.
- Model diagnostic (descriptive, no rule depends on it): G at t0 + 25%, 50%, 75% of the window and at t1 - 30 against
  the official outcome: calibration by fair-value bucket and Brier score, next to the Brier score of the last trade
  price U at the same moment (markets where U exists).

### B11. Order of operations

1. Download metadata, tapes and prices for all series (single sequential downloader, toolkit throttle, cached).
2. Small slice first (one day of eth 5m and of btc 15m): the sanity checks of B5, timestamps inside the window, fee
   against the formula. Bugs found there are fixed in code; rules above are not touched.
3. Full run of M1, M2, M3, proxy check, M4, M5 in one script; all tables written to `out/`.
4. results.md.

Nothing in `pmlab/` is edited; toolkit problems are worked around in study code and reported.
