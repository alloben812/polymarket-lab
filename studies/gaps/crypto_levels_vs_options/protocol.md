# Crypto price-level markets vs option-implied probabilities — protocol

Written 2026-11-27 before any gap, calibration or rule result was computed. Only metadata had been looked at
(event/series lists, rule texts, volumes, one price-history response and one tape to learn the data formats; while
listing one hit-price event its resolved outcomes were printed by accident — no model value or rule was involved).
After this file the rules do not change; anything else goes under "ideas" in results.md.

## Protocol as given by the lab lead

Question. A published study (arXiv 2606.19517) found Polymarket Bitcoin threshold prices 5-6 percentage points away
from option-implied digital probabilities, with a half-life of about four hours. Does a gap like that exist in late
2026, and does trading it pay after the 0.01 fee?

Universe. Polymarket markets on BTC and ETH price levels that resolved between 2026-10-27 and 2026-11-26: daily and
weekly "above X on <date>" ladders and "what price will X hit" markets, volumeNum >= 5,000. "Above at time T"
(European digital) is treated separately from "hits level before T" (one-touch); the one-touch group needs a barrier
formula and is done only if time allows.

Fair value. P = N(d2), lognormal, zero drift, spot from Binance, time to the exact resolution time, volatility from
(a) Deribit DVOL history scaled to the horizon, (b) realised volatility of the previous 24 h as a cross-check,
(c) for a subset, Deribit listed options (call spreads) and how far (a) is from it.

Polymarket prices. `pmlab.dataapi.prices_history`, 300-second buckets, YES token, market open to resolution.

Measurements. L1 gap by moneyness and time to resolution + calibration of model and market; L2 persistence
(autocorrelation 1 h / 4 h / 12 h, half-life); L3 trading rule, 9 variants = gap threshold (0.05, 0.08, 0.12) x
horizon band (2-12 h, 12-48 h, 48 h-7 d), buy the side the model favours at the NEXT 5-minute bucket price + 1 cent,
one entry per market per 12 hours, 20 dollars per entry, hold to settlement, fee 0.01 p (1-p) per share, tune on
markets resolving 27 Oct-15 Nov, report 16-26 Nov separately, cluster by resolution date and asset; L4 fill realism on
150 random entries (print at or better than the assumed entry within 10 minutes of the signal), share confirmed, L3
redone on confirmed entries.

## Concrete choices (mine, fixed now)

### Universe

1. Discovery: gamma `/events/keyset`, `closed=true`, tag slugs `multi-strikes` and `hit-price`, event end date
   2026-10-20 .. 2026-12-05 (`studies/.../discover.py`; `limit=50` because the toolkit default of 100 gets HTTP 406).
2. European group ("above at T"): series `btc-multi-strikes-weekly`, `ethereum-multi-strikes-weekly` (one ladder of
   11 strikes per asset per day, listed 7 days ahead; rule: Binance spot BTC/USDT or ETH/USDT 1-minute candle
   "closing at 12:00 ET", Close strictly higher than the strike) and `bitcoin-multi-strikes-hourly`,
   `ethereum-multi-strikes-hourly` (Binance 1-hour candle close; these open under 2 h before resolution, so they can
   only contribute to the "under 2 h" cells of L1 and never to L3). Range ("price on <date>", neg-risk) and up/down
   markets are not threshold markets and are out.
3. One-touch group ("hit"): series `bitcoin-hit-price-daily|weekly|monthly`, `ethereum-hit-price-daily|weekly|monthly`
   (rule: any Binance 1-minute candle High >= level for "reach", Low <= level for "dip", from 00:00 ET of the first
   day to 23:59 ET of the last). Membership is by the SCHEDULED end date (market `endDate`), not by the actual
   resolution time, because a touched market resolves early and selecting on that would select on the outcome.
4. Filters, both groups: market `endDate` (UTC) from 2026-10-27 00:00:00 to 2026-11-26 23:59:59; `closed` true;
   `outcomePrices` exactly {0,1}; `volumeNum >= 5000`. Outcome = gamma `outcomePrices` (official). Markets failing a
   filter are counted and dropped.
5. Strike = number parsed from `groupItemTitle` (cross-checked with the question text). Resolution time T = market
   `endDate` (12:00 ET for the daily ladders: 16:00 UTC until 31 Oct, 17:00 UTC from 1 Nov). The rule's "1 minute
   candle closing at 12:00" is ambiguous by 60 s (candle opening 11:59 or opening 12:00); I use T = 12:00:00 for the
   model (60 s is immaterial at >= 2 h) and report which candle reproduces the official outcomes.
6. Split: tune = resolution date (UTC date of `endDate`) 2026-10-27 .. 2026-11-15; report = 2026-11-16 .. 2026-11-26.
7. Cluster = (asset, UTC date of `endDate`), for both groups.

### Data

8. Spot: Binance spot 1-minute klines (public mirror `data-api.binance.vision`), BTCUSDT and ETHUSDT. Spot at time t
   = close of the last 1-minute candle that ended at or before t. Missing minute -> last close up to 5 minutes old,
   otherwise the observation is dropped.
9. DVOL: Deribit `get_volatility_index_data`, BTC and ETH, resolution 3600. At time t use the close of the last
   hourly candle that ended at or before t (never the candle in progress); up to 6 h stale, otherwise dropped.
   sigma_a = DVOL / 100 (annual), variance to the horizon = sigma_a^2 * tau, tau in years of 365 days x 24 h.
10. Realised vol (b): sum of squared 1-minute log returns over the 1,440 minutes ending at t, annualised (x 365).
    Needs >= 1,300 valid minutes, otherwise dropped.
11. Polymarket: `prices_history(yes_token, market startDate - 600 s, T + 600 s, 300)`. The series is a 5-minute
    mid-price series (it moves without trades). Only points with `resolution_seconds == 300` and timestamp < T are
    used. No forward filling: a missing bucket is a missing observation. Bucket-label alignment (does the point at t
    show the book at t or at t+300) is measured by a lead-lag check against the model (diagnostic L0) and reported;
    the rule below is safe either way because the model only uses spot up to t and the entry price comes from a
    later bucket.
12. Tapes: `trades?condition=` whole-market tape, cached under `data/gaps_levels/tape/`.

### Fair value

13. European: d2 = (ln(S/K) - v/2) / sqrt(v), v = sigma^2 * tau, P = N(d2). ("Zero drift" = the price is a
    martingale, so the log has drift -sigma^2/2.) No rates, no skew.
14. One-touch, driftless, continuous monitoring, b = |ln(K/S)|, v = sigma^2 * tau:
    reach (K > S): P = N((-b - v/2)/sqrt(v)) + (S/K) N((-b + v/2)/sqrt(v));
    dip   (K < S): P = N((-b + v/2)/sqrt(v)) + (S/K) N((-b - v/2)/sqrt(v)).
    tau = scheduled end - t. The barrier is "already hit" from the first 1-minute candle whose High/Low crosses it
    after max(market startDate, period start 00:00 ET); all buckets at or after that minute are dropped (the
    outcome is known and public). If spot is beyond the barrier without a recorded hit the bucket is dropped.
15. Primary fair value for L1-L4 is (a) DVOL. (b) is reported next to it in L1 (gap summary and calibration).
16. (c) Deribit listed options, subset: BTC only, the most recent 10 daily expiries (08:00 UTC) inside the window for
    which `get_tradingview_chart_data` returns candles; hourly candles over the 24 h before expiry down to 2 h
    before expiry; strikes on a 500-dollar grid within +-6,000 of spot, calls and puts. Only candles with volume > 0
    (a real trade in that hour) are used. Option USD price = close (in BTC) x Binance spot at the candle end.
    Digital from adjacent traded strikes in the same hour: P(S_T > Kmid) = (C(K1) - C(K2)) / (K2 - K1) for calls,
    1 - (P(K2) - P(K1)) / (K2 - K1) for puts, K2 - K1 <= 1,000, clipped to [0,1]. Compared with model (a) for the
    same Kmid, hour and the Deribit expiry time: mean / median / mean absolute difference, overall and by moneyness.
    Second, sturdier comparison: Black implied vol from traded candles with |ln(K/S)| <= 1.5% and 2 h <= tau <= 24 h,
    ratio IV / (DVOL/100): median and quartiles. This says how wrong "30-day DVOL scaled to the horizon" is for
    one-day horizons. Polymarket resolves at 16:00/17:00 UTC, Deribit at 08:00 UTC, so (c) checks the model, not
    Polymarket directly.

### L0 sanity (before the full run, on the first 3 resolution dates of the tune period)

- official outcome vs Binance candle close (both candle readings); share of markets reproduced;
- model probability at the last bucket before T vs outcome; timestamps inside [startDate, T];
- fees: recompute 0.01 p (1-p) by `pmlab.fees.fee_per_share` for a handful of fills;
- market-price calibration near 0.50 (buckets with price 0.45-0.55: outcome rate near 50%);
- lead-lag: correlation of 5-minute changes of the Polymarket price with 5-minute changes of the model at lags
  -2..+2 buckets (near-the-money observations) to learn the bucket labelling.

### L1 gap and calibration

Observation = one market at one full hour (bucket timestamp divisible by 3600), from open to T. gap = Polymarket
price - model probability. Cells: model probability [0,0.1), [0.1,0.3), [0.3,0.7), [0.7,0.9), [0.9,1] x time to
resolution < 2 h, 2-12 h, 12-48 h, >= 48 h. Per cell: number of market-hours, markets and clusters, mean, median,
standard deviation and inter-quartile range of the gap, mean absolute gap; mean outcome, mean model probability,
mean market price; (outcome - model) and (outcome - market) with standard errors clustered by (asset, date)
(`pmlab.stats.ratio_cluster`, numerator = sum of differences, denominator = count per cluster). Also per time band:
Brier score of the model and of the market, and the encompassing regression
(outcome - market) = beta * (model - market), no intercept, cluster-robust SE: beta near 0 means the gap is model
error, beta near 1 means the gap is market error. Same tables for volatility (b). Whole window, and the two periods
separately. One-touch group: same tables, separately, if done.

### L2 persistence

Hourly observations as in L1; "active" = model probability in [0.05, 0.95] at t. Pairs (t, t+lag) inside one
market. (i) pooled Pearson autocorrelation of the gap at lags 1, 4, 12 h (active at t), plus the same after removing
each market's mean gap; (ii) decay slope b(lag) = sum(gap_t * gap_{t+lag}) / sum(gap_t^2) over observations with
|gap_t| >= 0.05 and active, lags 1, 2, 3, 4, 6, 8, 12, 24 h; half-life = lag * ln(0.5) / ln(b(lag)) from the 1 h and
4 h slopes and the first lag with b < 0.5; (iii) who moves: over the next 4 h, slope of the change in the market
price on gap_t and of the change in the model on gap_t (same observations). Market closing the gap = first slope
negative; model coming to the market = second slope positive.

### L3 rule (primary: European group, model (a), 9 variants)

For each market, walk the 5-minute buckets in time order. Signal at bucket t when |gap_t| >= g and tau = T - t is in
the band (2 h <= tau < 12 h; 12 h <= tau < 48 h; 48 h <= tau <= 168 h) and the market has no entry in this variant
during the previous 12 h. Side: gap < 0 (market below model) -> buy YES; gap > 0 -> buy NO. Entry price
P_e = price of that side at bucket t+300 (YES: mid; NO: 1 - mid) + 0.01. If the bucket t+300 is missing, or P_e is
outside [0.01, 0.99], there is no entry and no lock-out. Stake 20 dollars: shares = 20 / P_e. Fee = shares * 0.01 *
P_e * (1 - P_e). Hold to settlement: PnL = shares * (payout - P_e) - fee, payout 1 or 0 from the official outcome.
Variants are simulated independently. Reported per variant and period: entries, markets, clusters, stake, PnL after
fees, return on stake with cluster-robust SE and t (`ratio_cluster`: PnL and stake per cluster), win rate, mean entry
price, mean |gap| at signal, PnL per calendar day (20 days tune, 11 days report), share of YES/NO entries.
Selection: the variant with the highest tune-period t among those with >= 30 tune entries is "the tuned variant";
the verdict is its reporting-period result. All nine are shown for both periods.

Secondary runs, declared now, counted as variants, never used for the verdict:
- R-b: the same 9 variants with volatility (b) instead of (a) (9 more);
- OT: the same 9 variants on the one-touch group with model (a), only if time allows (9 more).

### L4 fill realism

Pool = distinct (market, signal time, side) entries of the nine primary variants over both periods. Draw 150
without replacement, `random.Random(20261127)`; if the pool is smaller, take all. For each, the tape confirms the
entry if between signal time t (exclusive) and t + 600 s (inclusive), using match time = block time - 3 s, there is
a row showing the side could be bought at <= P_e: a taker BUY of that outcome at price <= P_e, or a taker SELL of
the opposite outcome at price >= 1 - P_e (mirror book). Reported: share confirmed (Wilson interval), share
confirmed with cumulative such size >= the entry's shares, and by variant. L3 is recomputed on confirmed entries
only (entry price stays P_e even when the print was better). If downloading the tapes of all markets with entries is
affordable (a few thousand requests), the same check is also applied to every entry and L3-confirmed is reported on
the full set as well; the 150-sample numbers are reported regardless.

### Order of operations

discover -> select universe (metadata only) -> download spot, DVOL, price histories -> L0 on the first 3 tune dates
-> full L1, L2 -> L3 tune, then L3 report -> L4 -> (c) Deribit subset -> one-touch if time allows -> results.md.

### Verdict rule

OPPORTUNITY only if the tuned variant is positive after fees in the reporting period with t > 2 across >= 100
markets (and survives L4). NO EDGE if clearly negative or zero. Otherwise INCONCLUSIVE.

### Known limits fixed in advance

- The fee rate before 2026-11-20 for these markets is not verified (gamma `feeSchedule` is not reliable history);
  the protocol's 0.01 is applied to the whole window.
- `prices_history` is a mid, not an ask; the spread is covered only by the +1 cent and the L4 tape check.
- 22 clusters at most in the reporting period (11 dates x 2 assets): ladders of one date are one bet.
