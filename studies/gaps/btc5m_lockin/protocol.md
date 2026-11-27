# BTC 5-minute markets: is the nearly decided side underpriced in the last minute?

Written 2026-11-27 BEFORE any outcome-dependent number was computed. Only outcome-free checks were done before this
file (window count = 1,728, reading the toolkit code, format of one cached metadata file). Nothing below changes
after results are seen; deviations forced by data problems are listed in results.md under "Deviations".

## Protocol as fixed by the lab lead

**Question.** Settlement is a 60-second average, so during the last minute the result becomes progressively fixed.
Does the market underprice the nearly decided side late in the window by more than the 0.05 taker fee? (Earlier
278-market sample: the only profitable taker bucket was buying at 0.90-1.00, +0.41 cents per share after fees, not
significant.)

**Period.** All BTC 5m windows starting 2026-11-21 00:00 UTC to 2026-11-26 23:55 UTC (1,728 windows, current fee
regime, rate 0.05). Tune on 21-24 Nov, report 25-26 Nov separately.

**Data.** `pmlab.updown.windows('5m', start, end)`, `load_market('btc','5m',t0)` for the official outcome (`up_won`)
and `price_to_beat`; `pmlab.updown.tape(condition)` for the whole-market tape; `pmlab.updown.buyable(rows)` for what
could be bought when (match time = block time - 3 s); `pmlab.px.Px.load('BTCUSDT', days)` for Binance 1-second
closes; `pmlab.fair.fair_up(px, t, t0)` for P(Up) with the averaging-window lock-in.

**Descriptive table (no rule).** All taker BUY prints with match time in the last 60 s, by price bucket
(0.50-0.80, 0.80-0.90, 0.90-0.95, 0.95-0.98, 0.98-1.00): shares, realised win rate, fee per share, net per share,
t clustered by market, on all 1,728 markets.

**Basis risk.** Proxy error in dollars per window: `(px.twap(t1,60) - final_price) - (px.twap(t0,60) - price_to_beat)`.
Report its distribution; E99 = 99th percentile of its absolute value.

**Rule family.** 18 variants = 3 entry windows (L = 60, 30, 15 s) x 2 probability floors (0.97, 0.99) x 3 margins
(0.02, 0.04, 0.08), all with information delay D = 1 s; then D = 2 s for the best three by tuning-period result
only. For each buyable print with match time m in the last L seconds and m <= t1 - 2: f = model probability of the
favoured side using Binance data up to m - D; trade when f >= floor and price q <= f - margin and q >= 0.50;
size = min(print size, 100 shares), at most 500 shares per market; fee 0.05 * q * (1 - q) per share; hold to
official settlement. Every variant is run twice: with and without the exclusion "skip when the absolute distance
between the expected settlement average and the price to beat is below E99".

**Report per variant, tuning and reporting periods separately.** Trades, markets, shares, average price, win rate
with a Wilson interval, net cents per share, dollars per day at this size, t clustered by market. State the total
number of variants run.

## Concrete implementation choices (mine, fixed here)

### Universe and periods
1. Windows: `t0` in `windows('5m', 1795219200, 1795219200 + 6*86400)` = 1,728 windows; `t1 = t0 + 300`.
   Tuning = t0 < 1795564800 (2026-11-25 00:00 UTC; 1,152 windows, 4 days). Reporting = the rest (576 windows, 2 days).
2. A window is usable when `load_market` returns `up_won` in {True, False} and a condition id, and the tape is
   non-empty. Windows that are missing, unresolved, or without tape are counted and listed, never imputed.
   The outcome used everywhere is the official `up_won` (never the Binance proxy).
3. Binance: `Px.load('BTCUSDT', ['2026-11-20', ..., '2026-11-27'])` (the day before is needed for the 900 s
   volatility lookback of the first windows). If a dump for an edge day is unavailable, the toolkit's mirror
   fallback is used; if the model returns NaN for a print, that print is not traded (counted).

### Time conventions
4. Match time of a tape row: `m = block_time - 3` (toolkit BLOCK_LAG, integer seconds).
5. "Last L seconds": `t1 - L <= m`. Upper bound for the rule family: `m <= t1 - 2` (as written).
   Descriptive table: `t1 - 60 <= m < t1` (prints stamped at or after the end are excluded: the result is public
   by then). Because block times jitter by 1-2 s, the same table is also given for `t1 - 60 <= m <= t1 - 2`.
6. Information delay, conservative reading. A Binance 1 s kline with open time s closes at s + 1. "Data up to
   m - D" = only klines fully closed by m - D, i.e. open time <= m - D - 1. The model is therefore called as
   `fair_up(px, t = m - D - 1, t0)` with every default (K = `px.twap(t0, 60)` from Binance, sigma = trailing 900 s
   realised vol x 1.3, lookback 60). The model clock is t, so it believes 1 s more remains than really does (this
   only widens its uncertainty). The official price to beat is NOT fed to the model: the basis measure above is
   defined for the Binance-vs-Binance difference, and the E99 exclusion is applied in the same space.

### Descriptive table
7. Rows: raw tape rows with side == BUY (the taker bought outcome o at price p). Taker SELL rows are not converted
   for this table. Buckets are half-open [lo, hi) except the last, [0.98, 1.00]. BUY prints below 0.50 are shown in
   one extra row for completeness. Per row: shares; win rate share-weighted (and print-weighted); fee per share =
   sum(z * 0.05 p (1-p)) / shares; gross per share = sum(z * (win - p)) / shares; net = gross - fee;
   se and t from `pmlab.stats.ratio_cluster(net dollars per market, shares per market)`.
   Given for all usable markets (headline, as the protocol asks) and split tuning / reporting.

### Basis risk
8. Computed for every window that has `price_to_beat`, `final_price` and both Binance TWAPs. Reported: n, mean, sd,
   percentiles (1, 5, 25, 50, 75, 95, 99) of the signed error, percentiles (50, 90, 95, 99, max) of |error|, also in
   basis points of price, plus the share of windows where the Binance proxy outcome
   (`px.twap(t1,60) >= px.twap(t0,60)`) disagrees with `up_won`. E99 = 99th percentile (numpy linear interpolation)
   of |error| over ALL windows, as written. This uses reporting-period basis data inside a rule parameter (mild
   look-ahead, accepted because the protocol says "across all windows"); E99 from the tuning period alone is printed
   next to it so the size of that look-ahead is visible.

### Rule family
9. Candidate fills: `pmlab.updown.buyable(rows)` over the whole tape (taker BUY of X at p -> X buyable at p; taker
   SELL of X at p -> the other outcome buyable at 1 - p), in tape order (block time ascending, stable), restricted
   to `t1 - L <= m <= t1 - 2`.
10. Favoured side at a print: Up if `f_up >= 0.5` else Down; `f = max(f_up, 1 - f_up)`. Only prints whose outcome is
    the favoured side are eligible. Conditions: `f >= floor`, `q <= f - margin` (+1e-9 tolerance for float noise),
    `q >= 0.50`, print size >= 5 shares (exchange minimum order).
11. Size: `min(print size, 100)`, capped so that the market total never exceeds 500 shares; when the remaining
    capacity is below 5 shares the market is closed for the variant. Each print is used at most once. No selling;
    payoff 1 per share if the bought outcome is the official winner, else 0. Net per share = payoff - q -
    0.05 q (1 - q). Rebates = 0.
12. Exclusion (run with and without): expected settlement average as in `pmlab.fair` at the same model time
    t = m - D - 1: `EA = S_t` when t <= t1 - 60, else `(e/60) * mean_between(t1 - 60, t) + (r/60) * S_t` with
    e = t - (t1 - 60), r = t1 - t. Skip the print when `|EA - px.twap(t0, 60)| < E99`.
13. D = 2 step: the 18 (L, floor, margin) triples are ranked by tuning-period net cents per share of the
    exclusion-ON run, among triples with at least 30 traded markets in the tuning period (if fewer than three
    qualify, the list is filled with the remaining triples ordered by number of traded tuning markets). The top
    three are re-run with D = 2, with and without the exclusion. Total runs = (18 + 3) x 2 = 42. Reporting-period
    numbers are not looked at for this choice (the script computes the ranking from tuning rows only).
14. Per variant and period: trades (prints taken), markets, shares, share-weighted average price, win rate
    (per trade) with a Wilson 95% interval on trades AND the market-level win rate (a market is a win when at least
    half of its shares won) with a Wilson interval on markets (the per-trade interval treats fills in one market as
    independent, so the market-level one is the honest one); net cents per share; total net dollars; dollars per
    day = total / calendar days in the period (4 or 2); se and t from `ratio_cluster(net $ per traded market,
    shares per traded market)`.
15. Verdict rule (from the task): OPPORTUNITY only if the reporting period is positive after fees with t > 2 across
    at least 100 markets; NO EDGE if clearly negative or zero; otherwise INCONCLUSIVE. Because 42 runs are compared,
    a single variant passing is read against that multiplicity; the variant judged in the reporting period is the
    one that was best in tuning (same ranking as item 13, D = 1), the others are shown for completeness.

### Sanity checks on a small slice before the full run (first 48 windows of 21 Nov)
- BUY prints priced 0.45-0.55 at any time in the window: win rate near 50%.
- Fee per share equals 0.05 p (1-p) (1.25 c at 0.50, 0.145 c at 0.97).
- Block times of tape rows: share inside [t0, t1 + 10]; how much trading is stamped after t1.
- Proxy outcome vs official outcome agreement near the 96.5% in NOTES.md.
- Model calibration at 30 s before the end (bucketed f_up vs realised) is printed for information only.

### Order of operations
1. `fetch.py`: metadata + tapes for all windows (sequential, throttled by the toolkit), compact per-market extract
   under `data/gaps_btc5m_lockin/`. No outcome statistics.
2. `sanity.py` on the small slice.
3. `analyze.py`: descriptive table, basis risk and E99, the 36 D = 1 runs, ranking on tuning rows, the 6 D = 2
   runs; writes `out/*.csv` and `out/report.txt`.
4. `results.md`.

### What the data cannot show (known in advance)
- A tape print proves the price was available at about m, to the taker who took it. Taking it ourselves means
  being there before that taker; queue/latency cannot be checked. Depth beyond the printed size is unknown, which
  is why size is capped by the print.
- Block-time jitter (1-2 s) is comparable to D; the D = 2 re-run is the only guard against it.
- Binance closes are a proxy for the Chainlink average (basis section).

### Addendum (written while the download was running, before build.py / analyze.py were first run)
Two diagnostics that are not trading rules and are not counted as variants; they use no market prices for selection:
- Model calibration per market at fixed model times t1-45, t1-30, t1-15, t1-5: for f >= 0.97 and f >= 0.99, the
  realised win rate of the favoured side, with and without the E99 exclusion, tuning and reporting periods.
- For every run, losing trades are split into "Binance proxy called the final outcome wrong" (basis miss) and
  "proxy right at the end, the price really reversed after the trade".
Sanity slice result (first 48 windows, recorded before the full run): BUY prints at 0.45-0.55 won 48.0% (n = 6,048
prints in 41 markets, net -1.77 c/share, t = -0.79); fee 1.25 c at 0.50 and 0.1455 c at 0.97; 94.0% of tape rows
are stamped inside [t0, t1+10], 5.9% before t0 (pre-open trading), 0.1% later; proxy outcome agreed with the
official one in 45/48. Block times fall on a 1.5 s grid (offsets -5, -4, -2, -1, +1, +2, +4, ... from t1), so match
times are only known to about +-1.5 s.
