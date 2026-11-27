# BTC 5m tail sniper: protocol

Written 2026-11-27 18:35 UTC, before any outcome-based statistic of this study was computed. What had been done
before this file: reading `studies/gaps/btc5m_tails/{results,audit,protocol}.md` and its published T3 tables
(`out/full/t3.md`, tercile cuts); listing the caches under `data/`; downloading the PMData/mileswangs files
(`markets.parquet`, `l2` and `trades` for 2026-08-14..21) and reading their schema and the first row group of one
day (one market's event types, no prices compared with outcomes). Nothing below changes after this point. New ideas
go to "Ideas, not tested" in `results.md`. Budget: one agent, about 110 minutes of wall-clock (18:29-20:20 UTC).

## 1. Question

`btc5m_tails` found that buying every 1-5 c tail in seconds 225-285 of a BTC 5-minute window loses 27-46% of stake,
while the wallet Vega7 made money there by choosing moments: its picks follow a Binance move toward the tail and a
small model distance to the strike. Turn that into a rule fixed in advance and test it (a) on months not used to
form the hypothesis (it was formed on 2026-09-01..11-26 BTC 5m) and (b) with a reaction delay against recorded order
books: after the Binance trigger, was the cheap offer still there 0.15 / 0.5 / 1 / 2 / 5 s later? Apply the same rule
to BTC 15m and ETH/SOL/XRP 5m and 15m where data exist. Decide whether a live micro-test (and a server next to the
exchange) is worth it.

## 2. The rule (fixed; thresholds are the published T3 tercile cuts of the pooled cell "price <= 0.05, seconds 225-285")

All times UTC seconds. `P` = Binance 1-second closes (`pmlab.px.Px`, BTCUSDT / ETHUSDT / SOLUSDT / XRPUSDT);
`P.price(T)` is the close of the kline that opens at second T, known at wall time `tau = T + 1`.

For a window `[t0, t0 + D]` (D = 300 for 5m, 900 for 15m), at every decision second T with
`D - 75 <= T - t0 < D - 15` (seconds 225..284 of a 5m window, 825..884 of a 15m window):

1. `g = pmlab.fair.gap_in_sigmas(P, T, t0, D, 60)` (defaults: K = Binance 60 s TWAP at t0, sigma_mult 1.3).
   The TAIL is the outcome the model puts behind: Down if g > 0, Up if g < 0 (g == 0 or NaN: no signal).
   `dist = |g|`.
2. `mv30 = (P.price(T) / P.price(T - 30) - 1) * 1e4` in bp, signed so that + means Binance moved toward the tail
   (for a Down tail the sign is flipped).
3. Signal when `dist < 2.61` AND `mv30 >= 0.00122` (published cuts: lowest tercile of dist, top tercile of mv30).
4. Price: the tail must be offered at or below Z. Two caps (the two published cells): **Z1 = 0.015** and
   **Z2 = 0.05**. Both are co-primary.

Order: a fill-and-kill limit BUY of the tail at limit Z, budget **$5 of stake** (shares x price), sent at tau and
matched against the book at `tau + d`. It takes ask levels <= Z, best first, for no more than the shown size, until
the budget is used. A fill under 5 shares counts as no fill (minimum order). At most ONE filled ticket per market
and variant; if an attempt does not fill, the next signal second of the same market is tried (attempts never
overlap a filled ticket). Held to settlement. Payoff 1 per share if the tail wins.

Fee: taker `rate * p * (1 - p)` per share with **today's rate** as the primary (BTC 5m and 15m 0.05; ETH/SOL/XRP
up/down 0.01, per NOTES / `pmlab.fees`); for BTC data before 2026-11-21 the historical rate (0.07) is reported next to
it as a sensitivity. Rebates 0. Net per ticket = shares x hit - stake - fee.

Delays: d in {0 (idealised), 0.15, 0.5, 1, 2, 5} seconds. d = 0 is an upper bound nobody reaches (the crypto taker
delay is 150 ms today; it was 0 before 2026-08-17 and 50 ms from 2026-08-17 to 09-04).

Variants run in total: 2 caps x 6 delays on the book data = 12 book variants; 2 caps x 3 delays (1, 2, 5 s) for the
tape fill rule (2.4) on each tape dataset. Every one is reported. No other threshold, window or size is tried.

## 3. Data and splits

### 3.1 OOS-BOOK (primary out-of-sample test with real books)

- BTC 5m windows with t0 in [2026-08-14 00:00, 2026-08-22 00:00) (8 days, 288 a day = 2,304 windows). The hypothesis
  was formed on Sep-Nov; August is out of sample. 2026-08-14 is the first day of the current settlement rule
  (60 s TWAP); the earlier days of the dataset (08-08..13) are excluded because their settlement rule differed.
- Books: HF `mileswangs/polymarket-btc-updown-5m-orderbook-tick-data` (PMData, CC BY 4.0), `l2` table: `book`
  snapshots and `price_change` deltas with Polymarket event timestamps (ms), recorded in AWS London. The book of a
  market is rebuilt from the last snapshot plus deltas. The token of the recorded book is identified before the run
  from the `trades` table (prices of buys of each outcome vs the book's best ask / 1 - best bid), not from outcomes.
  The other outcome's ask = 1 - this book's bid, size = bid size (Polymarket's books of the two outcomes are mirror
  images). Book state "at time x" = all events with Polymarket timestamp <= x.
- The "offer visible" condition of step 4 is checked on the book at tau (event timestamp <= tau); the fill on the
  book at tau + d.
- Outcome: the dataset's `winning_outcome` (Polymarket `market_resolved` message); where null, `pmlab.updown.
  load_market` (gamma); still unknown -> dropped and counted.
- Binance BTCUSDT 1 s dumps 2026-08-13..08-21 from data.binance.vision.
- Early / late halves: t0 in Aug 14-17 vs Aug 18-21, reported separately.

### 3.2 OOS-TAPE (second out-of-sample period, tape only)

- BTC 5m windows t0 in [2026-08-22 00:00, 2026-09-01 00:00) (10 days, 2,880 windows), `pmlab.updown.load_market` and
  `tape`. Downloaded in four interleaved sub-grids ((t0 / 300) mod 4 = 0, 2, 1, 3, each spanning all 10 days), at
  most 3 parallel workers. Hard stop for downloads at 19:35 UTC; the analysis uses the union of COMPLETE sub-grids
  (if none is complete, the completed markets of the first sub-grid), and the results say how many.
- Early / late: Aug 22-26 vs Aug 27-31.

### 3.3 FORMATION (in-sample, shown for comparison, never used to change anything)

- The tails study's grid: BTC 5m, every 4th window 2026-09-01..11-26, 6,244 markets, cached buyable prints
  (`data/gaps_btc5m_tails/prints_full.parquet`) and Binance 1 s. Tape fill rule. This is the period the hypothesis
  came from: a good number here is expected and proves nothing.

### 3.4 OTHER FAMILIES (out of sample in the asset/duration dimension; tape only)

- 2026-11-21..11-26, all windows with cached meta and tapes: BTC 15m (576), ETH 5m (1,728), ETH 15m (576), SOL 5m
  (432), SOL 15m (576), XRP 5m (432), XRP 15m (576). Binance 1 s ETHUSDT / SOLUSDT / XRPUSDT / BTCUSDT cached.
  Same cuts (2.61 sd, 0.00122 bp), no rescaling. Fees at today's rates (BTC 15m 0.05, others 0.01).

### 3.5 Tape fill rule (used where there is no book: 3.2, 3.3, 3.4)

The tape cannot show the book. Its proxy: an attempt at tau + d is filled by the first buyable print of the tail
outcome (`pmlab.updown.buyable`, match time = block time - 3 s) with price <= Z and match time in
[tau + d, tau + d + 2), at that print's price, for at most min(print size, remaining $5 budget). Several prints in
that interval may be taken in tape order until the budget is used. The "offer visible at tau" condition is not
checkable and is dropped. Block time jitters 1-2 s, so only d = 1, 2, 5 s are reported on the tape and they are
rough. Same one-ticket-per-market logic and 5-share minimum.

## 4. Statistics

Per dataset x variant (cap, delay): signal markets, attempts, filled tickets (= markets with a ticket), fill share
relative to d = 0 (book) or d = 1 (tape), shares, stake, average price, hits (tickets that won), hit rate with a
Wilson 95% interval, equal-weight break-even (mean of (stake + fee) / shares over tickets), exact one-sided binomial
p of the hits against that break-even, net $, net per ticket with a 95% interval (normal, by market: one ticket per
market, so markets are the clusters) and a day-cluster bootstrap 95% interval of net $ (2,000 draws), return on stake.
Also: tickets per day, net $ per day, and the net per ticket scaled to $1, $5 and $20 tickets (scaling assumes the
shown size; the share of tickets whose $20 order would have been cut by the shown size is reported).

Reported for each period half (early / late) separately.

## 5. Decision rule (fixed now)

- **EDGE (worth a live micro-test):** on OOS-BOOK, at d = 2 s (what a Mac in Serbia polling a WebSocket can do), for
  Z1 or Z2: net > 0, at least 5 winning tickets, exact binomial p < 0.025 (two caps: Bonferroni), and the same cap
  at d = 2 s on OOS-TAPE has net > 0.
- **FAST-ONLY (a nearby server could matter):** the EDGE conditions fail at d = 2 s but hold at d = 0.15 or 0.5 s on
  OOS-BOOK (net > 0, >= 5 wins, p < 0.025). Then the answer to "rent a server next to the exchange" is "only worth a
  further, separate test"; no micro-test from Serbia.
- **NO EDGE:** neither. Then the live micro-test section says that nothing here deserves one.
- FORMATION and OTHER FAMILIES never decide; they are reported as context (OTHER FAMILIES: whether the sign agrees).

## 6. Attacks to run before reporting a positive

Look-ahead (Binance kline T is used only from tau = T + 1; book state uses event times <= the decision time);
clock offset between Binance and Polymarket timestamps (re-run the primary variant with tau shifted +0.5 s as a
sensitivity, counted as a variant); concentration (result without the best day and without the best 3 tickets);
the book's token mapping (Up vs Down) checked on trades; impossible fills (shown size, 5-share minimum); comparison
of the fill volume with the whole pie of cheap tail prints.
