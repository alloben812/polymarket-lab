# BTC 5-minute tails: protocol

Written 2026-11-27 before any outcome statistic of this study was computed. Only non-outcome plumbing had been
run at this point: three sample `load_market` + `tape` calls to time the download, the start of the tape download
(`fetch.py`, which records row counts only), and a three-row peek at the row format of Vega7's fill feed.
After this file the rules do not change. Follow-ups go under "ideas" in the results, not into this study.

## 1. Protocol as given by the lab lead (verbatim in substance)

Background (catalog/raw/x1_bot_posts.md). One small account (Vega7, 0x6ba25c9f2fe6e9e5dd47983b629c00cd59958d0e)
reportedly makes 10-14K dollars a month buying the abandoned side of BTC 5-minute markets at about 1 cent, 10-25
dollars a ticket, mostly between seconds 225 and 285 of the 300-second window. Its fills at 5 cents or less earned
+1.85 cents a share net over 90 days (t 4.5 over 3,653 markets) while its fills at 5-15 cents earned nothing. Against
that, the whole-market tape of 278 markets showed takers losing heavily below 0.10 in aggregate. Settlement is a
60-second average over seconds 240-300.

Question. Is the tail really underpriced in some part of the window (a structural mispricing a small trader could
use), or is Vega7 one lucky or selective wallet?

Data. BTC 5m windows from 2026-09-01 to 2026-11-26; every 4th window (about 6,200 markets). Official outcome and
price_to_beat from `pmlab.updown.load_market('btc','5m',t0)`; tape from `pmlab.updown.tape(condition)`; what could be
bought when from `pmlab.updown.buyable(rows)` (match time = block time minus 3 s); Binance 1-second closes from
`pmlab.px.Px.load('BTCUSDT', days)`; model probability from `pmlab.fair.fair_up`; fee rate by date from
`pmlab.fees.btc_updown_rate(ts)`.

- T1 Descriptive, no rule. For all buyable prints priced at 0.10 or less: a table by price band (up to 0.015,
  0.015-0.03, 0.03-0.05, 0.05-0.10) x seconds-left band (300-180, 180-75, 75-45, 45-15, 15-0, after the end): shares,
  dollars, realised hit rate with a Wilson interval, average price, net per share after the fee, return on stake,
  t clustered by market. Separately for September, October and November.
- T2 The published rule, tested as stated (2 variants, nothing tuned): buy every buyable print priced at 0.02 or less
  (variant A) or 0.05 or less (variant B) whose match time is between seconds 225 and 285, up to 25 dollars per
  market. Report by month: tickets, markets, stake, hits, return on stake, net dollars, t.
- T3 What does Vega7 select? Pull its fills for the same period (`pmlab.wallet.fetch_fills`) and compare, inside the
  same seconds band and price band, the markets where it bought with all markets where a tail print existed: the
  distance of the expected settlement average from the price to beat in model standard deviations
  (`pmlab.fair.gap_in_sigmas`), realised volatility over the previous 5 minutes, the size of the move in the last
  30 seconds, the hour of the day. Is its hit rate higher than the all-prints hit rate in the same cell? If so, which
  variable separates them? Written as a hypothesis for a later out-of-sample test; no trading rule is fitted here.
- T4 Mirror check. For the favourite side priced at 0.95 or more in the same seconds bands: realised win rate against
  price. An underpriced tail implies an overpriced favourite in the same cell; report both and say whether they agree.
- Report the number of cells examined. With about 30 cells one near t = 2 is expected by chance; say which results
  survive a correction for the number of cells.

## 2. Concrete choices (mine, fixed now)

### 2.1 Universe and missing data

- Windows: `t0` from 1788220800 (2026-09-01 00:00:00 UTC) up to but excluding 1795737600 (2026-11-27 00:00 UTC),
  `t0 % 1200 == 0` (every 4th window of `updown.windows('5m', ...)`, starting with the first). 6,264 windows.
- Month = UTC calendar month of `t0`. November = 2026-11-01 .. 2026-11-26.
- A window is used when `load_market` returns a market with `up_won` not None and a condition id, and its tape has at
  least one row. Missing / unresolved / empty-tape windows are dropped and counted. No other market filter.
- Tape completeness check: sum of tape shares against gamma `volume` (NOTES say they are equal). If the sanity slice
  confirms that (median ratio within 0.98-1.02), tapes with a share count under 90% of `volume` are excluded and
  counted; if the slice does not confirm the relationship, no such filter is applied and that is reported.
- Tape rows with size <= 0 or price outside (0, 1) are dropped. No de-duplication.
- Download order is interleaved (t0 % 4800 == 0, then 2400, 1200, 3600) so that a prefix is an even sample. If the
  download cannot be completed, the analysis is run on the largest complete sub-grid and the results say so.

### 2.2 Prints, time, price, outcome, fee

- A "buyable print" is a tuple from `updown.buyable(rows)` with the default lag 3: taker BUY of X at p -> X buyable
  at p for the row's size; taker SELL of X at p -> the other outcome buyable at 1 - p for the row's size.
  Source is recorded (B = a taker really bought this outcome; S = a taker sold the other outcome into a bid).
- Assumed fill: the print's own price, at most the print's own size, at the print's match time. No extra delay can be
  simulated on the tape; the hypothetical trader replaces the taker who really got that liquidity. This is the
  limit of what the tape can show and is stated as a caveat.
- `e` = match time - t0 (seconds into the window), `left` = 300 - e. Seconds-left bands (left-open, right-closed in
  `left`): 300-180 = 180 < left <= 300 (0 <= e < 120); 180-75 = 75 < left <= 180; 75-45 = 45 < left <= 75;
  45-15 = 15 < left <= 45; 15-0 = 0 < left <= 15; after the end = left <= 0. Prints before the window opens
  (left > 300) are excluded from every table and counted.
- "Between seconds 225 and 285" = 225 <= e < 285 = the two bands 75-45 and 45-15 together.
- Price is rounded to 6 decimals. Tail bands: (0, 0.015], (0.015, 0.03], (0.03, 0.05], (0.05, 0.10].
  Favourite bands for T4 are the mirror images: [0.985, 1), [0.97, 0.985), [0.95, 0.97).
- A print hits when its outcome is the official winner (`up_won`). Payoff 1 per share on a hit, else 0.
- Fee per share = `btc_updown_rate(block time) * p * (1 - p)` (0.07 before 2026-11-20 23:59 UTC, 0.05 after).
  Rebates zero. Net per share = hit - p - fee. Stake = shares * p (the fee is not in the denominator, it is in the net).

### 2.3 T1 statistics per cell (price band x seconds-left band), for Sep, Oct, Nov and pooled

- shares, dollars (stake), number of prints, number of markets;
- hit rate at the market level: units are (market, outcome) pairs with at least one print in the cell, k = pairs whose
  outcome won, with the Wilson 95% interval; next to it the equal-weight mean over those pairs of (share-weighted
  price + fee), which is the break-even for that hit rate, and a one-sided binomial z of k against it;
- share-weighted hit rate (shares that hit / shares), average price = dollars / shares;
- net per share after fee with `stats.ratio_cluster(net dollars by market, shares by market)` -> value, se, t
  (primary t of the cell); return on stake with `ratio_cluster(net dollars by market, stake by market)` -> value, t.
  Clusters are markets (both outcomes of a market are one cluster).
- Declared decomposition (not a rule): the pooled T1 table is also shown for source B only (prints where a taker
  really bought the tail), because the lab's earlier "takers lose below 0.10" number is about that flow.

### 2.4 T2 rule mechanics

- Per market, walk the buyable prints in tape order (block time, ties in tape order). A print qualifies when
  225 <= e < 285 and price <= 0.02 (A) or <= 0.05 (B), either outcome. Buy min(print size, remaining budget / price)
  shares at the print price. Budget: 25 dollars of stake per market (both outcomes share it); the fee is paid on top
  and is in the net. No minimum ticket. A ticket = one print taken (fully or partly).
- Per month and pooled: tickets, markets with a ticket, stake, hit markets and hit tickets, return on stake =
  `ratio_cluster(net by market, stake by market)` with its t (primary), net dollars, `mean_se` of net dollars per
  traded market, and a cluster bootstrap 95% interval of the net (`stats.bootstrap_sum_ci`).
- Dollars per day at the stated size = net dollars / days in the period x 4 (the grid is one window in four).
- Primary variant is A (the post says "1c or less"); B is secondary. Reporting period = November 2026 (the latest
  month; nothing is tuned, so September and October are simply the earlier periods).
- Verdict rule: OPPORTUNITY only if variant A in November has net > 0, clustered t > 2 and at least 100 traded
  markets, and variant A pooled over September-November is also positive. NO EDGE if the November return on stake is
  <= 0 for both variants, or the pooled return is <= 0 for both variants. Otherwise INCONCLUSIVE.

### 2.5 T3 (Vega7)

- Fills: `pmlab.wallet.fetch_fills(wallet, 1788220800, 1795737600)`; keep slug `btc-updown-5m-<t0>`, side BUY (maker
  and taker, role reported). Match time = block time - 3. Vega7 trades all windows, not only the grid: its own hit
  rate and features use ALL its markets in the period (metadata via `load_market` for off-grid windows); the
  in-grid subset is shown next to it as a like-for-like check, and its in-grid fills are looked up in the tape
  (same block time, outcome, price, size) as a completeness check.
- First a count/dollar/net table of Vega7's own fills over the T1 cells (plus a band 0.10+).
- Comparison cells: price bands (0, 0.015], (0.015, 0.03], (0.03, 0.05] x seconds bands 75-45 and 45-15 (6 cells),
  plus the pooled cell "price <= 0.05, 225 <= e < 285" (the cell the posts describe). A cell is reported whatever its
  size; cells with fewer than 30 Vega7 markets are marked as too small to read.
- Unit: (market, outcome) with at least one fill (Vega7) / at least one buyable print (baseline = all grid markets)
  in the cell. Hit rate of each with Wilson intervals; difference tested with a two-proportion z. The baseline
  includes the markets Vega7 bought (it is "all markets where a tail print existed").
- Features, computed at the match time of every fill / print in the cell and averaged with equal weight inside the
  (market, outcome) unit:
  1. `dist` = distance of the tail from winning in model sd: `gap_in_sigmas(px, t, t0, 300, 60)` (default K = Binance
     60 s TWAP at t0, sigma_mult 1.3), sign flipped for an Up tail so that positive = the tail is behind;
     `dist5` = the same with the window shifted 5 s earlier (`t0 - 5`), following the lock-in study's finding that
     the official average lags Binance by about 5 s (sensitivity only);
  2. `vol5` = `px.sigma(t, 300)`, in basis points per 5 minutes (x sqrt(300) x 1e4);
  3. `mv30` = Binance move over the 30 s before the print, in bp, signed towards the tail (+ = moving the tail's
     way); `amv30` = its absolute value;
  4. `hour` = UTC hour of t0 (compared as a distribution, 4 six-hour blocks);
  plus price paid and e (not selection variables of the protocol, shown for context).
  Missing Binance data -> feature NaN, the unit is left out of that feature's comparison only; counts reported.
- Separation: for each feature, mean and median in Vega7 units and in baseline units, standardised mean difference,
  and a rank-sum z. Then, on the baseline only, the hit rate by tercile of each feature (terciles of the baseline
  in that cell). The answer is written as a hypothesis; no thresholds are chosen and no rule is evaluated.

### 2.6 T4 (mirror)

- Buyable prints (both sources) of an outcome priced in [0.95, 1), same seconds bands, bands [0.95, 0.97),
  [0.97, 0.985), [0.985, 1). Same statistics as T1 (win rate at the market level with Wilson, share-weighted win
  rate, average price, net per share after fee, t clustered by market), pooled and by month.
- Agreement test per mirrored cell: the tail is "underpriced" when its net per share is > 0, the favourite
  "overpriced" when its net per share is < 0. They agree when the signs are opposite. Both prints populations are
  shown; they are different prints (tail asks vs favourite asks), so this is a consistency check, not an identity.

### 2.7 Multiple comparisons

- Families: T1 pooled 24 cells (each also by 3 months = 72 cell-months, and by source B = 24), T2 2 variants
  (x 4 periods), T3 7 cells, T4 pooled 18 cells (x 3 months = 54). All are counted in the results.
- A T1 or T4 cell "survives" when pooled |t| >= 3.1 (Bonferroni, two-sided 5% over 24 cells; 3.25 when T1 and T4 are
  taken together as 42) AND the sign of net per share is the same in all three months. Cells whose t rests on fewer
  than 10 hit markets are marked: with 50-100:1 payoffs the clustered t is unreliable there, and the binomial z of
  2.3 is shown next to it.

### 2.8 Order of operations

1. `fetch.py` (tapes and metadata; sequential), then Vega7 fills and off-grid metadata in the same queue; Binance
   dumps in parallel (different host).
2. `build.py`: tapes -> one table of buyable prints (all prices) per market with e, outcome, price, size, source.
3. `sanity.py` on the first few hundred downloaded markets, using only prices between 0.10 and 0.90 and non-outcome
   checks: win rate of prints at 0.45-0.55 near 50%; calibration by decile between 0.10 and 0.90; fee formula values;
   distribution of e; Binance proxy vs official outcome; tape shares vs gamma volume. Fix plumbing only.
4. Full run: `t1_t4.py` (T1, T4), `t2.py`, `t3.py`; `results.md`.
