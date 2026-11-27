# Results: do thin, low-fee crypto up/down series lag exchange prices enough to trade?

Study run 2026-11-27 under `protocol.md` (written before any tape or outcome was loaded). Code: `fetch.py` (download),
`build.py` (flat tables), `sanity.py` (slice checks), `analyze.py` (M1-M5, proxy check), `extra.py` (re-aggregations),
`report_tables.py`. Raw tables: `out/*.csv`, `out/tables.md`.

## Answer

**No tradable edge.** The thin series do not lag Binance by more than BTC 5m does. In every one of the six series
the tape follows the Binance-based fair value with a peak lag of 2 seconds over the six days, which is no more than the
on-chain block delay, and trade prices fit the model best at a lag of 1 second in the thin series against 2 seconds in
the BTC 5m reference. What looks like slowness in SOL and XRP is sparse trading (a fill in 4-6% of seconds), not
stale quotes that can be hit.

None of the 90 taker variants (60 M4, 30 M5) is positive after fees with t above 2 across 100 markets in the
reporting period. The M4 variants picked on 21-24 Nov returned, on 25-26 Nov at the protocol's size (up to 50 shares
per print, 300 per side per market): eth 5m -$987 per day (t -1.3), eth 15m +$266 (t +0.6), sol 15m +$666 (t +1.3),
xrp 15m -$979 (t -3.1), btc 15m -$813 (t -1.6). The two positive ones were negative in tuning; pooled over all six
days every selected M4 variant is within one standard error of zero (-0.87 to +0.60 cents per share). The late
lock-in rule (M5) hardly ever fires in the 15m series (at most 18 markets in six days) and loses in eth 5m out of sample
(-20 to -38 cents per share, 6-20 markets).

The one place where a delay matters is the zero-delay variant in the two most liquid series during tuning (btc 15m
+1.2 cents per share at D=0 against -0.0 to -0.4 at D >= 1 s; eth 5m +0.2 against -0.0 to -0.2). That is the same
sub-second race as BTC 5m, not a gap a trader without co-location can use, and it is within the timestamp jitter of
the data.

Lower fees do help takers, but not enough: all takers together lose 1.0-1.4% of turnover after fees in the four
0.01-fee series, against 1.8% in btc 15m and 2.4% in btc 5m. Before fees they lose 0.36-0.61 cents per share to
makers in the low-fee series.

## What was measured

Universe: every window starting 2026-11-21 00:00 to 2026-11-26 23:45 UTC: 1,726 eth 5m, 576 each of eth 15m, sol 15m,
xrp 15m, btc 15m, plus 300 btc 5m windows spread evenly as the reference. All 4,330 markets were found, resolved and
traded; none was dropped. Tuning = 21-24 Nov (1,152 / 384 markets), reporting = 25-26 Nov (574 / 192).
1,512,241 tape rows in total. Fee rates in the metadata were 0.01 for eth, sol, xrp and 0.05 for btc in every
market; `twap_lookback` was 60 everywhere; the official outcome agreed with `final_price >= price_to_beat` in every
market; no tape row had to be dropped; no second of Binance data was missing.

Slice checks before the full run (first day of eth 5m and btc 15m, then repeated on everything): equivalent buys
priced 0.45-0.55 (mean price 0.50-0.51) won 48-51% of the time (table below), tape prices are calibrated by decile,
hand-computed fees equal `fees.taker_fee`, 92-96% of taker dollars trade inside the window.

| series | fills at q 0.45-0.55 | markets | mean price | win rate | se |
|---|---|---|---|---|---|
| eth-5m | 78,415 | 1,724 | 0.505 | 0.509 | 0.005 |
| eth-15m | 24,594 | 576 | 0.504 | 0.495 | 0.009 |
| sol-15m | 8,378 | 572 | 0.506 | 0.49 | 0.012 |
| xrp-15m | 4,270 | 537 | 0.504 | 0.48 | 0.023 |
| btc-15m | 67,047 | 576 | 0.504 | 0.509 | 0.013 |
| btc-5m | 72,546 | 300 | 0.505 | 0.509 | 0.008 |

### M1 Size of the pond

| series | markets (all traded) | fills | taker $ / day (mean) | taker $ / day (median day) | taker $ total | median $ / market | fills / market | seconds with a fill | median fill $ | fills < 5 sh | taker wallets | top-5 share |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| eth-5m | 1,726 | 415,563 | 578,582 | 552,980 | 3,471,491 | 1,766 | 216 | 30.3% | 3.45 | 20% | 3,255 | 20% |
| eth-15m | 576 | 149,438 | 251,327 | 247,943 | 1,507,965 | 2,442 | 246 | 14.8% | 4 | 17% | 1,690 | 32% |
| sol-15m | 576 | 47,963 | 58,714 | 56,203 | 352,286 | 517 | 77 | 6.4% | 3.7 | 19% | 978 | 46% |
| xrp-15m | 576 | 29,071 | 41,243 | 40,194 | 247,459 | 325 | 48 | 4.0% | 4.24 | 15% | 686 | 44% |
| btc-15m | 576 | 411,812 | 1,235,583 | 1,210,093 | 7,413,500 | 11,591 | 682 | 29.5% | 4.95 | 17% | 5,081 | 15% |
| btc-5m | 300 | 458,394 | 6,607,679 | 6,655,655 | 39,646,071 | 21,372 | 1,436 | 54.3% | 4.3 | 22% | 11,129 | 13% |

btc 5m is a 300-window sample; its per-day and total dollars are scaled up by 1726/300. "Taker $" is price times
size of every tape row. eth 5m is a real market ($0.58M of taker flow per day, 3,255 taker wallets in six days).
sol 15m and xrp 15m are ponds of $41-59K per day in which five wallets do 44-46% of the taker volume; a median
market trades $325-517. A fifth of all fills are below the 5-share minimum order size (partial fills).

### M2 Who pays whom (all taker fills, clustered by market)

| series | period | fills | markets | shares | taker $ | gross c/sh | fee c/sh | net c/sh | se | t | net % turnover | net $ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| eth-5m | all | 415,563 | 1,726 | 7,087,956 | 3,471,491 | -0.405 | 0.147 | -0.551 | 0.144 | -3.822 | -1.126 | -39,073 |
| eth-5m | tune | 272,366 | 1,152 | 4,633,032 | 2,210,643 | -0.393 | 0.141 | -0.534 | 0.173 | -3.091 | -1.119 | -24,738 |
| eth-5m | report | 143,197 | 574 | 2,454,924 | 1,260,848 | -0.427 | 0.157 | -0.584 | 0.259 | -2.252 | -1.137 | -14,335 |
| eth-15m | all | 149,438 | 576 | 2,868,992 | 1,507,965 | -0.437 | 0.157 | -0.594 | 0.245 | -2.423 | -1.13 | -17,041 |
| eth-15m | tune | 96,844 | 384 | 1,842,272 | 985,045 | -0.614 | 0.153 | -0.767 | 0.316 | -2.429 | -1.434 | -14,130 |
| eth-15m | report | 52,594 | 192 | 1,026,720 | 522,920 | -0.117 | 0.166 | -0.284 | 0.382 | -0.742 | -0.557 | -2,911 |
| sol-15m | all | 47,963 | 576 | 692,892 | 352,286 | -0.357 | 0.153 | -0.51 | 0.447 | -1.141 | -1.004 | -3,536 |
| sol-15m | tune | 30,469 | 384 | 469,871 | 247,553 | -1.171 | 0.151 | -1.322 | 0.493 | -2.68 | -2.509 | -6,210 |
| sol-15m | report | 17,494 | 192 | 223,021 | 104,733 | 1.357 | 0.158 | 1.199 | 0.9 | 1.332 | 2.553 | 2,674 |
| xrp-15m | all | 29,071 | 576 | 459,380 | 247,459 | -0.613 | 0.147 | -0.759 | 0.496 | -1.529 | -1.409 | -3,487 |
| xrp-15m | tune | 19,130 | 384 | 308,888 | 167,071 | -0.639 | 0.139 | -0.777 | 0.631 | -1.232 | -1.437 | -2,401 |
| xrp-15m | report | 9,941 | 192 | 150,491 | 80,388 | -0.559 | 0.163 | -0.722 | 0.789 | -0.915 | -1.351 | -1,086 |
| btc-15m | all | 411,812 | 576 | 14,888,626 | 7,413,500 | -0.205 | 0.676 | -0.881 | 0.242 | -3.634 | -1.768 | -131,101 |
| btc-15m | tune | 281,207 | 384 | 10,032,369 | 4,936,471 | -0.369 | 0.663 | -1.031 | 0.266 | -3.871 | -2.096 | -103,472 |
| btc-15m | report | 130,605 | 192 | 4,856,257 | 2,477,030 | 0.133 | 0.702 | -0.569 | 0.495 | -1.15 | -1.115 | -27,629 |
| btc-5m | all | 458,394 | 300 | 13,883,489 | 6,890,974 | -0.542 | 0.645 | -1.187 | 0.238 | -4.98 | -2.391 | -164,737 |
| btc-5m | tune | 302,573 | 200 | 8,830,442 | 4,393,696 | -0.699 | 0.64 | -1.339 | 0.316 | -4.236 | -2.691 | -118,234 |
| btc-5m | report | 155,821 | 100 | 5,053,047 | 2,497,278 | -0.266 | 0.654 | -0.92 | 0.352 | -2.612 | -1.862 | -46,503 |

Takers lose in every series; makers collect the "gross" column with the opposite sign. The loss after fees is
significant in eth 5m, eth 15m, btc 15m and btc 5m; in sol and xrp the sign is the same but two to six days are not
enough to pin it (sol was -1.3 cents in tuning and +1.2 in reporting). The btc 5m sample reproduces the lab's
earlier whole-tape number (-2.4% of turnover after fees here, -2.67% on 278 markets before).

Net cents per share (t) by time of the window, by match time:

| time | eth-5m | eth-15m | sol-15m | xrp-15m | btc-15m | btc-5m |
|---|---|---|---|---|---|---|
| pre | +1.14 (+1.4) | +1.32 (+0.8) | -1.36 (-0.7) | -1.74 (-0.6) | -0.45 (-0.4) | +0.02 (+0.0) |
| Q1 | -0.36 (-0.7) | -1.28 (-1.6) | -1.23 (-1.2) | -0.37 (-0.3) | -0.50 (-0.6) | -2.52 (-3.0) |
| Q2 | -0.43 (-1.0) | -1.38 (-1.4) | +0.97 (+0.7) | -0.61 (-0.6) | -2.16 (-3.7) | -1.15 (-2.5) |
| Q3 | -1.32 (-3.7) | +0.15 (+0.3) | -0.17 (-0.2) | -0.95 (-1.0) | -1.62 (-4.2) | -0.88 (-2.6) |
| Q4 | -0.60 (-3.3) | -0.49 (-1.5) | -0.99 (-1.8) | -0.92 (-1.8) | -0.18 (-0.5) | -0.75 (-2.4) |
| post | -0.21 (-3.8) | -0.16 (-4.8) | +0.24 (+0.5) | -0.34 (-1.1) | +2.24 (+0.9) | -0.73 (-4.8) |

Net cents per share (t) by price of the equivalent buy (a SELL of X at p is a buy of the other side at 1 - p):

| price(eq.buy) | eth-5m | eth-15m | sol-15m | xrp-15m | btc-15m | btc-5m |
|---|---|---|---|---|---|---|
| 0-0.10 | -0.60 (-2.1) | -0.13 (-0.1) | +1.56 (+0.9) | -0.60 (-0.5) | -0.57 (-1.0) | -0.37 (-0.6) |
| 0.10-0.30 | -2.45 (-2.7) | +0.40 (+0.2) | -1.11 (-0.7) | -1.49 (-0.8) | +1.02 (+0.6) | -1.27 (-0.6) |
| 0.30-0.50 | -0.36 (-0.5) | -1.95 (-1.5) | -0.98 (-0.7) | -2.19 (-1.0) | -1.41 (-1.0) | +0.20 (+0.1) |
| 0.50-0.70 | -0.40 (-0.6) | -0.84 (-0.8) | -2.09 (-1.8) | -1.81 (-0.9) | -1.54 (-1.1) | -2.40 (-2.0) |
| 0.70-0.90 | +0.29 (+0.3) | -0.24 (-0.1) | +0.64 (+0.4) | +0.80 (+0.4) | -3.94 (-2.1) | -2.87 (-1.3) |
| 0.90-1 | +0.24 (+0.6) | -0.37 (-0.4) | -0.39 (-0.3) | +0.54 (+0.4) | +0.48 (+0.8) | -0.94 (-0.9) |

By taker side:

| side | eth-5m | eth-15m | sol-15m | xrp-15m | btc-15m | btc-5m |
|---|---|---|---|---|---|---|
| BUY | -0.52 (-3.1) | -0.65 (-2.3) | -0.54 (-1.0) | -0.50 (-0.9) | -0.87 (-3.0) | -0.97 (-3.4) |
| SELL | -0.88 (-2.0) | -0.22 (-0.3) | -0.41 (-0.9) | -3.68 (-2.2) | -0.97 (-1.5) | -2.67 (-4.3) |

No time or price bucket is profitable for takers with t above 2 in any series. The best-looking cells (pre-window
fills in eth, +1.1 to +1.3 cents; favourites at 0.70-1.00 in eth 5m and xrp) are all inside one and a half standard
errors.

### M3 Reaction lag

Second-by-second changes of the last trade-implied Up price (block time) against changes of the model fair value,
lags -5..+30 s, pooled Pearson correlation; peak interval from 300 bootstrap resamples of markets.

| series | period | markets | second pairs | peak lag s | peak corr | mean lag s (positive part) | 50% lag s | peak 5% | peak 95% |
|---|---|---|---|---|---|---|---|---|---|
| eth-5m | all | 1,726 | 512,196 | 2 | 0.33 | 1.979 | 2 | 2 | 2 |
| eth-5m | tune | 1,152 | 341,489 | 2 | 0.378 | 2.523 | 2 | 2 | 2 |
| eth-5m | report | 574 | 170,707 | 1 | 0.403 | 1.313 | 1 | 1 | 1 |
| eth-15m | all | 576 | 516,048 | 2 | 0.246 | 3.498 | 2 | 2 | 2 |
| eth-15m | tune | 384 | 343,951 | 2 | 0.286 | 4.116 | 3 | 2 | 2 |
| eth-15m | report | 192 | 172,097 | 1 | 0.319 | 2.547 | 1 | 1 | 1 |
| sol-15m | all | 576 | 511,536 | 2 | 0.117 | 6.276 | 3 | 2 | 3 |
| sol-15m | tune | 384 | 340,269 | 3 | 0.131 | 7.164 | 4 | 2 | 3 |
| sol-15m | report | 192 | 171,267 | 1 | 0.172 | 4.764 | 2 | 1 | 1 |
| xrp-15m | all | 576 | 500,642 | 2 | 0.108 | 7.329 | 4 | 2 | 3 |
| xrp-15m | tune | 384 | 331,586 | 2 | 0.115 | 7.555 | 5 | 2 | 3 |
| xrp-15m | report | 192 | 169,056 | 1 | 0.132 | 6.88 | 4 | 1 | 1 |
| btc-15m | all | 576 | 517,095 | 2 | 0.307 | 2.479 | 2 | 2 | 2 |
| btc-15m | tune | 384 | 344,620 | 2 | 0.327 | 3.024 | 3 | 2 | 3 |
| btc-15m | report | 192 | 172,475 | 1 | 0.396 | 1.889 | 1 | 1 | 1 |
| btc-5m | all | 300 | 89,690 | 2 | 0.332 | 2.56 | 2 | 2 | 3 |
| btc-5m | tune | 200 | 59,793 | 3 | 0.392 | 3.071 | 3 | 3 | 3 |
| btc-5m | report | 100 | 29,897 | 1 | 0.414 | 2.264 | 1 | 1 | 1 |

Correlation by lag, all six days:

| lag | eth-5m | eth-15m | sol-15m | xrp-15m | btc-15m | btc-5m |
|---|---|---|---|---|---|---|
| -5 | 0.004 | -0.004 | -0.001 | -0 | 0.001 | 0.005 |
| -4 | 0.008 | 0.003 | 0.002 | 0.005 | 0.008 | 0.016 |
| -3 | 0.016 | 0.014 | 0.006 | 0.009 | 0.008 | 0.029 |
| -2 | 0.033 | 0.02 | 0.008 | 0.006 | 0.028 | 0.027 |
| -1 | 0.055 | 0.033 | 0.012 | 0.014 | 0.05 | 0.049 |
| 0 | 0.141 | 0.121 | 0.047 | 0.045 | 0.122 | 0.111 |
| 1 | 0.253 | 0.19 | 0.096 | 0.072 | 0.221 | 0.249 |
| 2 | 0.33 | 0.246 | 0.117 | 0.108 | 0.307 | 0.332 |
| 3 | 0.245 | 0.186 | 0.108 | 0.096 | 0.259 | 0.307 |
| 4 | 0.097 | 0.102 | 0.063 | 0.066 | 0.13 | 0.158 |
| 5 | 0.042 | 0.065 | 0.042 | 0.046 | 0.055 | 0.08 |
| 6 | 0.016 | 0.041 | 0.036 | 0.045 | 0.03 | 0.03 |
| 7 | 0.009 | 0.031 | 0.027 | 0.033 | 0.01 | 0.01 |
| 8 | -0.001 | 0.025 | 0.026 | 0.033 | 0.01 | 0.005 |
| 9 | -0.001 | 0.018 | 0.019 | 0.02 | 0.006 | -0 |
| 10 | -0.002 | 0.013 | 0.019 | 0.022 | 0.002 | 0.002 |
| 11 | -0.002 | 0.011 | 0.017 | 0.021 | -0.002 | 0.002 |
| 12 | 0.003 | 0.009 | 0.012 | 0.015 | 0.006 | 0.006 |
| 13 | 0.003 | 0.012 | 0.01 | 0.017 | 0.003 | 0.013 |
| 14 | -0.001 | 0.007 | 0.012 | 0.014 | -0.003 | 0.002 |
| 15 | -0.001 | 0.003 | 0.013 | 0.018 | -0.002 | -0.001 |
| 16 | 0.003 | 0.003 | 0.011 | 0.01 | -0.001 | -0.004 |
| 17 | 0.001 | 0.004 | 0.009 | 0.01 | -0.005 | 0.001 |
| 18 | 0.004 | 0.003 | 0.006 | 0.01 | 0.001 | 0.004 |
| 19 | 0.002 | 0.003 | 0.005 | 0.007 | -0.003 | -0 |
| 20 | 0.001 | 0.003 | 0.008 | 0.011 | -0.001 | 0.007 |
| 21 | 0.002 | 0.003 | 0.009 | 0.01 | -0.002 | 0.006 |
| 22 | -0.001 | 0.003 | 0.006 | 0.01 | 0.006 | -0.003 |
| 23 | -0 | 0.004 | 0.008 | 0.013 | 0.001 | 0.002 |
| 24 | -0.002 | 0.003 | 0.009 | 0.01 | 0 | 0 |
| 25 | -0.002 | -0.002 | 0.008 | 0.007 | 0.002 | 0.004 |
| 26 | 0.001 | 0.001 | 0.01 | 0.007 | -0.001 | 0.002 |
| 27 | -0 | 0.004 | 0.002 | 0.004 | 0 | -0.005 |
| 28 | 0 | -0.001 | 0.003 | 0.003 | 0.004 | -0.002 |
| 29 | -0.006 | 0.001 | 0.003 | 0.01 | 0.001 | -0.006 |
| 30 | -0.001 | 0.003 | -0.001 | 0.005 | -0.002 | -0.006 |

Reading: the peak is at 2 s in every series and in the reference, so the difference between each series and btc 5m
is 0 s (1 s earlier than btc 5m in tuning for eth, xrp, btc 15m; equal in reporting). The absolute 2 s is the block
delay. sol and xrp have a lower peak (0.11-0.12 against 0.25-0.33) and a long positive tail out to about 25 s, which
gives them a mean lag of 6-7 s. That tail is what sparse trading produces mechanically: the price can only update
when somebody trades, and in these two series a fill happens in 4-6% of seconds (the caveat written into the
protocol before the run).

M3b, the level fit that separates "stale" from "sparse": RMS distance between the price of each traded second (Up
price 0.05-0.95) and the fair value L seconds earlier.

| series | trade seconds | markets | best lag s | RMS at best | RMS lag 0 | RMS lag 3 | RMS lag 10 | RMS lag 30 | best 5% | best 95% |
|---|---|---|---|---|---|---|---|---|---|---|
| eth-5m | 113,276 | 1,723 | 1 | 0.073 | 0.077 | 0.081 | 0.125 | 0.188 | 1 | 1 |
| eth-15m | 63,792 | 576 | 1 | 0.061 | 0.062 | 0.066 | 0.093 | 0.134 | 1 | 1 |
| sol-15m | 27,526 | 576 | 1 | 0.087 | 0.088 | 0.091 | 0.113 | 0.147 | 1 | 1 |
| xrp-15m | 16,458 | 576 | 1 | 0.076 | 0.077 | 0.082 | 0.111 | 0.153 | 0 | 1 |
| btc-15m | 124,404 | 576 | 1 | 0.052 | 0.054 | 0.055 | 0.078 | 0.118 | 1 | 2 |
| btc-5m | 32,152 | 300 | 2 | 0.065 | 0.07 | 0.068 | 0.107 | 0.169 | 2 | 2 |

If resting quotes were stale by x seconds, trades would fit the fair value of block delay + x seconds ago. They fit
best at 1 s in all thin series and at 2 s in btc 5m, and the fit gets steadily worse with every extra second. The
prices at which people actually trade in sol and xrp are as current as in BTC; they are just further from the model
(RMS 0.076-0.087 against 0.052-0.073 in the other four), which is spread and noise, not delay.

Side finding, by UTC day (peak lag in seconds, peak correlation in brackets):

| series | 11-21 | 11-22 | 11-23 | 11-24 | 11-25 | 11-26 |
|---|---|---|---|---|---|---|
| eth-5m | 2 (0.35) | 2 (0.36) | 2 (0.40) | 2 (0.40) | 1 (0.42) | 1 (0.38) |
| eth-15m | 2 (0.29) | 2 (0.31) | 2 (0.29) | 2 (0.25) | 1 (0.33) | 1 (0.31) |
| sol-15m | 3 (0.14) | 3 (0.18) | 2 (0.13) | 2 (0.12) | 1 (0.21) | 1 (0.14) |
| xrp-15m | 3 (0.11) | 2 (0.14) | 2 (0.11) | 2 (0.11) | 1 (0.13) | 1 (0.13) |
| btc-15m | 3 (0.33) | 3 (0.33) | 2 (0.37) | 2 (0.36) | 1 (0.41) | 1 (0.38) |
| btc-5m | 3 (0.38) | 3 (0.42) | 3 (0.41) | 2 (0.40) | 1 (0.43) | 1 (0.40) |

The lag fell from 2-3 s on 21-24 Nov to 1 s on 25-26 Nov in all six series at once. A change that hits BTC and XRP
alike is infrastructure (block timestamps, the settlement pipeline, or what the API reports as the timestamp), not
makers getting faster. Consequence: the toolkit's `BLOCK_LAG = 3` is about right for 21-22 Nov and probably 1-2 s
too long for 25-26 Nov, so in the reporting period every rule saw
exchange data 1-2 s older than the protocol intended. That errs on the conservative side (no look-ahead).

### Proxy check (Binance 60 s TWAP against the official Chainlink values)

d = [(Binance twap(t1) - final_price) - (Binance twap(t0) - price_to_beat)] / price_to_beat, in basis points:

| series | windows | mean bp | sd bp | mean abs bp | p1 | p5 | p25 | p50 | p75 | p95 | p99 | proxy wrong | wrong % | Wilson 95% | official move in misses, median / max bp | median official move bp | windows with move < 2 bp |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| eth-5m | 1,726 | -0.01 | 1.01 | 0.68 | -2.49 | -1.44 | -0.5 | -0.01 | 0.49 | 1.47 | 2.62 | 31 | 1.8 | 1.3-2.5 | 0.25 / 3.1 | 9.2 | 12.3% |
| eth-15m | 576 | -0.02 | 1.11 | 0.75 | -2.96 | -1.51 | -0.59 | -0.01 | 0.49 | 1.58 | 2.77 | 8 | 1.39 | 0.7-2.7 | 0.78 / 1.59 | 14.20 | 8.5% |
| sol-15m | 576 | -0.02 | 1.27 | 0.91 | -3.29 | -1.95 | -0.7 | -0.05 | 0.66 | 2.05 | 3.06 | 11 | 1.91 | 1.1-3.4 | 0.51 / 3.0 | 17.30 | 6.8% |
| xrp-15m | 576 | -0.02 | 1.04 | 0.78 | -2.53 | -1.62 | -0.62 | -0.06 | 0.63 | 1.62 | 2.49 | 8 | 1.39 | 0.7-2.7 | 0.26 / 0.88 | 17.40 | 6.4% |
| btc-15m | 576 | -0.02 | 1.04 | 0.74 | -2.62 | -1.58 | -0.56 | -0.03 | 0.51 | 1.6 | 2.67 | 5 | 0.87 | 0.4-2.0 | 0.46 / 1.09 | 14.90 | 7.8% |
| btc-5m | 300 | -0.08 | 0.99 | 0.65 | -2.41 | -1.41 | -0.51 | -0.04 | 0.42 | 1.22 | 2.18 | 3 | 1 | 0.3-2.9 | 1.11 / 1.65 | 8.6 | 12.7% |

The Binance proxy drifts against the official values by about 1 bp (sd) per window in every series and calls the
outcome wrongly in 0.9-1.9% of windows; all misses are windows that officially moved by 3.1 bp or less (medians 0.25-1.1 bp). 6-13% of
windows end within 2 bp of the strike, the zone where the proxy cannot be trusted. Binance trades about 13.5 bp
above the official price in all four assets (median basis), which cancels in the difference.

### Model diagnostic (descriptive)

| series | at | markets | Brier model | Brier last trade | corr | mean abs diff |
|---|---|---|---|---|---|---|
| eth-5m | 25% | 1,726 | 0.191 | 0.188 | 0.979 | 0.041 |
| eth-5m | 50% | 1,726 | 0.139 | 0.135 | 0.986 | 0.044 |
| eth-5m | 75% | 1,726 | 0.077 | 0.078 | 0.99 | 0.039 |
| eth-5m | t1-30 | 1,726 | 0.022 | 0.02 | 0.99 | 0.028 |
| eth-15m | 25% | 576 | 0.205 | 0.205 | 0.974 | 0.037 |
| eth-15m | 50% | 576 | 0.169 | 0.165 | 0.982 | 0.043 |
| eth-15m | 75% | 576 | 0.106 | 0.103 | 0.991 | 0.041 |
| eth-15m | t1-30 | 576 | 0.01 | 0.005 | 0.992 | 0.019 |
| sol-15m | 25% | 575 | 0.209 | 0.213 | 0.953 | 0.061 |
| sol-15m | 50% | 576 | 0.161 | 0.161 | 0.967 | 0.071 |
| sol-15m | 75% | 576 | 0.102 | 0.097 | 0.981 | 0.069 |
| sol-15m | t1-30 | 576 | 0.015 | 0.009 | 0.987 | 0.03 |
| xrp-15m | 25% | 567 | 0.21 | 0.222 | 0.932 | 0.063 |
| xrp-15m | 50% | 574 | 0.158 | 0.157 | 0.951 | 0.075 |
| xrp-15m | 75% | 576 | 0.099 | 0.102 | 0.975 | 0.062 |
| xrp-15m | t1-30 | 576 | 0.015 | 0.017 | 0.987 | 0.028 |
| btc-15m | 25% | 576 | 0.216 | 0.217 | 0.982 | 0.03 |
| btc-15m | 50% | 576 | 0.162 | 0.16 | 0.99 | 0.031 |
| btc-15m | 75% | 576 | 0.106 | 0.103 | 0.993 | 0.034 |
| btc-15m | t1-30 | 576 | 0.015 | 0.012 | 0.993 | 0.018 |
| btc-5m | 25% | 300 | 0.199 | 0.194 | 0.984 | 0.037 |
| btc-5m | 50% | 300 | 0.134 | 0.13 | 0.987 | 0.045 |
| btc-5m | 75% | 300 | 0.072 | 0.07 | 0.991 | 0.038 |
| btc-5m | t1-30 | 300 | 0.013 | 0.015 | 0.992 | 0.025 |

Official Up frequency by model bucket (number of observations), pooled over the four sample times:

| model bucket | eth-5m | eth-15m | sol-15m | xrp-15m | btc-15m | btc-5m |
|---|---|---|---|---|---|---|
| [0.0, 0.03) | 0.003 (1155) | 0.003 (325) | 0.000 (274) | 0.000 (312) | 0.006 (357) | 0.000 (231) |
| [0.03, 0.1) | 0.045 (331) | 0.048 (105) | 0.000 (96) | 0.010 (97) | 0.061 (114) | 0.061 (66) |
| [0.1, 0.3) | 0.137 (923) | 0.182 (313) | 0.099 (302) | 0.152 (322) | 0.179 (302) | 0.176 (159) |
| [0.3, 0.5) | 0.398 (1099) | 0.391 (404) | 0.395 (481) | 0.354 (421) | 0.357 (417) | 0.351 (171) |
| [0.5, 0.7) | 0.641 (1005) | 0.634 (423) | 0.651 (470) | 0.617 (426) | 0.605 (382) | 0.635 (170) |
| [0.7, 0.9) | 0.864 (909) | 0.868 (310) | 0.904 (311) | 0.848 (310) | 0.805 (298) | 0.862 (152) |
| [0.9, 0.97) | 0.963 (320) | 0.981 (106) | 0.988 (85) | 0.990 (96) | 0.959 (98) | 0.960 (50) |
| [0.97, 1.0) | 0.997 (1162) | 1.000 (318) | 1.000 (285) | 1.000 (320) | 0.997 (336) | 1.000 (201) |

The last trade price predicts the outcome better than the model in 16 of 24 cells (differences of 0.000-0.012); the model has
nothing the tape lacks. With the default volatility multiplier 1.3 the model is under-confident on these days in every
series (it says 0.20 where Up happens 10-18% of the time, 0.80 where it happens 80-90%), so "cheap against the
model" mostly means "underdog": M4 bought at an average price of 0.23-0.47.

### M4 Taker rule: all 60 variants

f from Binance data up to m - D; buy when f - q - fee(q) >= thr; min(print, 50) shares; 300 per side per market;
held to settlement; fees in. D = delay in seconds, thr = threshold. Net cents per share and t are clustered by
market; $/day is the period total divided by 4 (tuning) or 2 (reporting) days.

| series | variant | tune trades | tune mkts | tune net c/sh | tune t | tune % turn | tune $/day | report trades | report mkts | report net c/sh | report t | report % turn | report $/day |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| eth-5m | D0_thr0.01 | 44,042 | 1,152 | 0.12 | 0.25 | 0.31 | 152 | 21,072 | 574 | -0.82 | -1.42 | -2.04 | -1,072 |
| eth-5m | D0_thr0.02 | 39,646 | 1,151 | 0.27 | 0.47 | 0.72 | 306 | 19,240 | 574 | -0.82 | -1.27 | -2.13 | -987 |
| eth-5m | D0_thr0.04 | 30,652 | 1,146 | 0.25 | 0.37 | 0.76 | 231 | 15,591 | 571 | -0.77 | -1.01 | -2.14 | -786 |
| eth-5m | D1_thr0.01 | 44,983 | 1,152 | -0.02 | -0.05 | -0.05 | -27 | 21,431 | 574 | -0.72 | -1.35 | -1.8 | -964 |
| eth-5m | D1_thr0.02 | 41,032 | 1,152 | 0 | 0 | 0 | -2 | 19,833 | 574 | -0.69 | -1.17 | -1.77 | -859 |
| eth-5m | D1_thr0.04 | 33,452 | 1,150 | -0.43 | -0.73 | -1.24 | -432 | 16,633 | 572 | -0.77 | -1.12 | -2.13 | -832 |
| eth-5m | D2_thr0.01 | 46,169 | 1,152 | -0.12 | -0.3 | -0.29 | -154 | 21,650 | 574 | -0.86 | -1.69 | -2.12 | -1,157 |
| eth-5m | D2_thr0.02 | 42,571 | 1,152 | -0.23 | -0.53 | -0.6 | -286 | 20,233 | 574 | -0.86 | -1.56 | -2.2 | -1,089 |
| eth-5m | D2_thr0.04 | 35,707 | 1,151 | -0.28 | -0.55 | -0.8 | -304 | 17,477 | 574 | -0.91 | -1.45 | -2.5 | -1,032 |
| eth-5m | D5_thr0.01 | 48,014 | 1,152 | 0.05 | 0.13 | 0.11 | 63 | 22,269 | 574 | -0.65 | -1.39 | -1.6 | -901 |
| eth-5m | D5_thr0.02 | 45,014 | 1,152 | 0 | -0.01 | -0.01 | -6 | 21,119 | 574 | -0.64 | -1.28 | -1.64 | -851 |
| eth-5m | D5_thr0.04 | 39,684 | 1,151 | -0.11 | -0.26 | -0.31 | -132 | 18,933 | 574 | -0.73 | -1.31 | -1.97 | -879 |
| eth-15m | D0_thr0.01 | 12,901 | 384 | -0.26 | -0.29 | -0.64 | -112 | 6,718 | 192 | 0.59 | 0.63 | 1.43 | 266 |
| eth-15m | D0_thr0.02 | 11,235 | 384 | -0.33 | -0.31 | -0.86 | -127 | 5,960 | 192 | 0.51 | 0.47 | 1.3 | 209 |
| eth-15m | D0_thr0.04 | 8,024 | 376 | -1.93 | -1.38 | -5.75 | -535 | 4,478 | 192 | 0.57 | 0.39 | 1.63 | 185 |
| eth-15m | D1_thr0.01 | 13,413 | 384 | -0.38 | -0.47 | -0.92 | -169 | 6,891 | 192 | 0.79 | 0.9 | 1.89 | 361 |
| eth-15m | D1_thr0.02 | 11,910 | 384 | -0.69 | -0.74 | -1.76 | -274 | 6,219 | 192 | 1 | 1.04 | 2.53 | 428 |
| eth-15m | D1_thr0.04 | 8,935 | 379 | -1.77 | -1.52 | -5.11 | -541 | 4,844 | 192 | 0.82 | 0.66 | 2.24 | 288 |
| eth-15m | D2_thr0.01 | 13,781 | 384 | -0.32 | -0.43 | -0.76 | -144 | 7,105 | 192 | 0.85 | 1.04 | 2.05 | 397 |
| eth-15m | D2_thr0.02 | 12,525 | 384 | -0.49 | -0.6 | -1.23 | -202 | 6,514 | 192 | 0.89 | 0.99 | 2.22 | 389 |
| eth-15m | D2_thr0.04 | 9,806 | 381 | -1.47 | -1.42 | -4.13 | -484 | 5,117 | 192 | 0.97 | 0.85 | 2.62 | 355 |
| eth-15m | D5_thr0.01 | 14,741 | 384 | -0.46 | -0.75 | -1.08 | -214 | 7,383 | 192 | 1.23 | 1.66 | 2.92 | 591 |
| eth-15m | D5_thr0.02 | 13,580 | 384 | -0.37 | -0.53 | -0.9 | -160 | 6,949 | 192 | 1.4 | 1.79 | 3.43 | 641 |
| eth-15m | D5_thr0.04 | 11,299 | 383 | -0.94 | -1.13 | -2.54 | -349 | 5,849 | 192 | 0.97 | 0.99 | 2.53 | 382 |
| sol-15m | D0_thr0.01 | 8,478 | 383 | -1.37 | -1.16 | -5.17 | -377 | 5,577 | 192 | 2.47 | 1.55 | 8.83 | 779 |
| sol-15m | D0_thr0.02 | 7,820 | 383 | -1.44 | -1.13 | -5.77 | -368 | 5,127 | 192 | 2.29 | 1.35 | 8.59 | 666 |
| sol-15m | D0_thr0.04 | 6,373 | 380 | -1.69 | -1.22 | -7.5 | -364 | 4,186 | 192 | 2.61 | 1.35 | 10.66 | 629 |
| sol-15m | D1_thr0.01 | 8,520 | 383 | -1.78 | -1.59 | -6.59 | -493 | 5,607 | 192 | 2.43 | 1.56 | 8.64 | 775 |
| sol-15m | D1_thr0.02 | 7,873 | 383 | -1.8 | -1.49 | -7.02 | -464 | 5,187 | 192 | 2.35 | 1.43 | 8.7 | 694 |
| sol-15m | D1_thr0.04 | 6,551 | 380 | -1.69 | -1.28 | -7.29 | -373 | 4,253 | 191 | 2.55 | 1.36 | 10.19 | 627 |
| sol-15m | D2_thr0.01 | 8,601 | 383 | -1.53 | -1.38 | -5.55 | -427 | 5,595 | 192 | 2.18 | 1.43 | 7.67 | 693 |
| sol-15m | D2_thr0.02 | 7,968 | 383 | -1.5 | -1.27 | -5.74 | -393 | 5,223 | 192 | 2.44 | 1.53 | 9.02 | 732 |
| sol-15m | D2_thr0.04 | 6,616 | 381 | -1.51 | -1.18 | -6.36 | -338 | 4,354 | 192 | 2.38 | 1.33 | 9.36 | 597 |
| sol-15m | D5_thr0.01 | 8,607 | 383 | -1.54 | -1.47 | -5.56 | -433 | 5,644 | 192 | 2.13 | 1.45 | 7.48 | 683 |
| sol-15m | D5_thr0.02 | 8,065 | 383 | -1.36 | -1.23 | -5.09 | -361 | 5,291 | 192 | 2.08 | 1.33 | 7.59 | 631 |
| sol-15m | D5_thr0.04 | 6,800 | 383 | -1.58 | -1.32 | -6.43 | -364 | 4,485 | 192 | 2.16 | 1.24 | 8.39 | 567 |
| xrp-15m | D0_thr0.01 | 5,825 | 382 | 0.19 | 0.14 | 0.73 | 36 | 2,934 | 192 | -4.29 | -2.38 | -13.72 | -785 |
| xrp-15m | D0_thr0.02 | 5,206 | 377 | -0.06 | -0.04 | -0.24 | -10 | 2,636 | 192 | -4.74 | -2.48 | -16.10 | -776 |
| xrp-15m | D0_thr0.04 | 3,949 | 365 | -0.75 | -0.46 | -3.28 | -96 | 2,002 | 187 | -5.27 | -2.6 | -19.87 | -634 |
| xrp-15m | D1_thr0.01 | 5,911 | 382 | 0.76 | 0.61 | 2.8 | 146 | 2,913 | 191 | -4.39 | -2.48 | -13.95 | -807 |
| xrp-15m | D1_thr0.02 | 5,341 | 377 | 0.7 | 0.51 | 2.68 | 120 | 2,631 | 191 | -4.68 | -2.57 | -15.68 | -780 |
| xrp-15m | D1_thr0.04 | 4,104 | 366 | 0.04 | 0.03 | 0.16 | 5 | 1,997 | 187 | -5.6 | -3 | -20.75 | -680 |
| xrp-15m | D2_thr0.01 | 5,933 | 380 | 1.27 | 1.02 | 4.58 | 245 | 2,883 | 191 | -5.47 | -3.14 | -17.48 | -979 |
| xrp-15m | D2_thr0.02 | 5,358 | 376 | 1.01 | 0.76 | 3.77 | 176 | 2,615 | 191 | -5.8 | -3.26 | -19.49 | -942 |
| xrp-15m | D2_thr0.04 | 4,174 | 370 | 0.03 | 0.02 | 0.1 | 3 | 2,035 | 187 | -5.43 | -3 | -20.03 | -672 |
| xrp-15m | D5_thr0.01 | 5,966 | 381 | 0.98 | 0.82 | 3.44 | 189 | 2,913 | 192 | -5.16 | -3.16 | -15.82 | -955 |
| xrp-15m | D5_thr0.02 | 5,418 | 379 | 0.66 | 0.52 | 2.45 | 116 | 2,655 | 192 | -5.51 | -3.32 | -17.84 | -924 |
| xrp-15m | D5_thr0.04 | 4,384 | 373 | 0.46 | 0.32 | 1.81 | 66 | 2,119 | 190 | -6.38 | -3.77 | -22.83 | -835 |
| btc-15m | D0_thr0.01 | 12,299 | 384 | 0.66 | 0.81 | 1.49 | 320 | 6,207 | 192 | -1.1 | -1.11 | -2.38 | -544 |
| btc-15m | D0_thr0.02 | 10,764 | 384 | 1.03 | 1.04 | 2.47 | 444 | 5,587 | 192 | -1.25 | -1.04 | -2.82 | -563 |
| btc-15m | D0_thr0.04 | 7,433 | 369 | 2.21 | 1.69 | 5.91 | 704 | 4,206 | 189 | -2.31 | -1.61 | -5.84 | -813 |
| btc-15m | D1_thr0.01 | 12,856 | 384 | -0.3 | -0.4 | -0.65 | -147 | 6,485 | 192 | -1.22 | -1.42 | -2.6 | -621 |
| btc-15m | D1_thr0.02 | 11,651 | 384 | -0.36 | -0.41 | -0.84 | -163 | 5,868 | 192 | -1.64 | -1.54 | -3.64 | -768 |
| btc-15m | D1_thr0.04 | 8,403 | 382 | 0.78 | 0.68 | 2.06 | 268 | 4,588 | 191 | -1.69 | -1.27 | -4.2 | -649 |
| btc-15m | D2_thr0.01 | 13,236 | 384 | -0.39 | -0.61 | -0.85 | -201 | 6,705 | 192 | -1.37 | -1.76 | -2.92 | -713 |
| btc-15m | D2_thr0.02 | 12,154 | 384 | -0.62 | -0.82 | -1.41 | -294 | 6,190 | 192 | -1.44 | -1.57 | -3.2 | -702 |
| btc-15m | D2_thr0.04 | 9,353 | 384 | -0.29 | -0.29 | -0.73 | -108 | 5,003 | 192 | -1.8 | -1.5 | -4.38 | -738 |
| btc-15m | D5_thr0.01 | 13,958 | 384 | -0.44 | -0.91 | -0.94 | -238 | 7,081 | 192 | -0.86 | -1.37 | -1.82 | -463 |
| btc-15m | D5_thr0.02 | 13,074 | 384 | -0.35 | -0.61 | -0.77 | -178 | 6,616 | 192 | -1.14 | -1.51 | -2.49 | -583 |
| btc-15m | D5_thr0.04 | 11,194 | 384 | -0.22 | -0.29 | -0.51 | -96 | 5,703 | 192 | -1.75 | -1.82 | -4.13 | -795 |

Prints considered and prints skipped because the delayed fair value would need data from before the window start:

| series | prints_considered | no_fair_D0 | no_fair_D1 | no_fair_D2 | no_fair_D5 |
|---|---|---|---|---|---|
| eth-5m | 362,922 | 0 | 0 | 0 | 2,257 |
| eth-15m | 138,734 | 0 | 0 | 0 | 622 |
| sol-15m | 43,830 | 0 | 0 | 0 | 207 |
| xrp-15m | 26,893 | 0 | 0 | 0 | 100 |
| btc-15m | 387,966 | 0 | 0 | 0 | 1,303 |

Share-weighted net cents per share by delay (the three thresholds pooled):

| series | period | D=0 | D=1 | D=2 | D=5 |
|---|---|---|---|---|---|
| eth-5m | tune | 0.21 | -0.13 | -0.2 | -0.02 |
| eth-5m | report | -0.81 | -0.73 | -0.88 | -0.67 |
| eth-15m | tune | -0.72 | -0.86 | -0.7 | -0.57 |
| eth-15m | report | 0.55 | 0.87 | 0.9 | 1.21 |
| sol-15m | tune | -1.49 | -1.76 | -1.52 | -1.49 |
| sol-15m | report | 2.45 | 2.44 | 2.33 | 2.12 |
| xrp-15m | tune | -0.14 | 0.55 | 0.84 | 0.72 |
| xrp-15m | report | -4.7 | -4.8 | -5.58 | -5.61 |
| btc-15m | tune | 1.19 | -0.03 | -0.44 | -0.34 |
| btc-15m | report | -1.48 | -1.49 | -1.52 | -1.22 |

If there were a lag to exploit, results would decay as the delay grows. They do not in eth 15m, sol or xrp in either
period, and not in any series in the reporting period. Only btc 15m and eth 5m in tuning show an advantage for D=0
that is gone at D=1. Between tuning and reporting eth 15m and sol flip from minus to plus, xrp from
plus to minus, and eth 5m and btc 15m go from about zero to minus; that is what noise around zero looks like for a
rule that buys underdogs.

### M5 Late lock-in rule: all 30 variants

Last 45 s, f from data up to m - 1, buy the favoured side when f >= 0.97 and q <= f - margin; "_2bp" adds the
condition that the expected settlement average is at least 2 bp from the strike. Win rate is per (market, side)
position with a Wilson 95% interval.

| series | variant | tune trades | tune mkts | tune win rate [Wilson] positions | tune net c/sh | tune t | tune % turn | tune $/day | report trades | report mkts | report win rate [Wilson] positions | report net c/sh | report t | report % turn | report $/day |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| eth-5m | mrg0.03 | 501 | 50 | 80% [68-89] n=51 | 6.57 | 1.38 | 8.72 | 116 | 172 | 20 | 68% [47-84] n=22 | -20.40 | -2.04 | -30.49 | -236 |
| eth-5m | mrg0.03_2bp | 209 | 25 | 92% [75-98] n=25 | 8.8 | 1.74 | 11.23 | 59 | 104 | 13 | 77% [50-92] n=13 | -23.72 | -1.34 | -29.10 | -132 |
| eth-5m | mrg0.05 | 402 | 42 | 77% [62-87] n=43 | 7.2 | 1.35 | 9.98 | 110 | 137 | 13 | 50% [27-73] n=14 | -21.98 | -1.72 | -36.90 | -208 |
| eth-5m | mrg0.05_2bp | 159 | 20 | 90% [70-97] n=20 | 10.28 | 1.81 | 13.72 | 58 | 85 | 8 | 62% [31-86] n=8 | -30.89 | -1.42 | -39.72 | -134 |
| eth-5m | mrg0.08 | 312 | 33 | 70% [53-83] n=33 | 9.15 | 1.39 | 13.90 | 112 | 88 | 10 | 36% [15-65] n=11 | -24.36 | -2.02 | -49.90 | -179 |
| eth-5m | mrg0.08_2bp | 126 | 14 | 86% [60-96] n=14 | 15.85 | 2.7 | 23.29 | 72 | 44 | 6 | 50% [19-81] n=6 | -38.24 | -1.76 | -53.84 | -111 |
| eth-15m | mrg0.03 | 41 | 7 | 100% [65-100] n=7 | 6.44 | 4 | 6.89 | 11 | 7 | 2 | 100% [34-100] n=2 | 5.41 | 24.72 | 5.72 | 2 |
| eth-15m | mrg0.03_2bp | 36 | 6 | 100% [61-100] n=6 | 6.49 | 3.63 | 6.95 | 10 | 6 | 1 | 100% [21-100] n=1 | 5.3 | - | 5.6 | 2 |
| eth-15m | mrg0.05 | 14 | 4 | 100% [51-100] n=4 | 15.34 | 3.83 | 18.15 | 5 | 1 | 1 | 100% [21-100] n=1 | 12.89 | - | 14.81 | 0 |
| eth-15m | mrg0.05_2bp | 11 | 3 | 100% [44-100] n=3 | 16.11 | 3.59 | 19.23 | 4 | 0 | 0 | - [---] n=0 | - | - | - | - |
| eth-15m | mrg0.08 | 9 | 2 | 100% [34-100] n=2 | 17.73 | 3.29 | 21.58 | 4 | 1 | 1 | 100% [21-100] n=1 | 12.89 | - | 14.81 | 0 |
| eth-15m | mrg0.08_2bp | 9 | 2 | 100% [34-100] n=2 | 17.73 | 3.29 | 21.58 | 4 | 0 | 0 | - [---] n=0 | - | - | - | - |
| sol-15m | mrg0.03 | 57 | 5 | 43% [16-75] n=7 | -17.24 | -2.14 | -35.58 | -44 | 18 | 1 | 100% [21-100] n=1 | 12.09 | - | 13.77 | 13 |
| sol-15m | mrg0.03_2bp | 33 | 3 | 75% [30-95] n=4 | -7.07 | -0.41 | -9.24 | -7 | 17 | 1 | 100% [21-100] n=1 | 10.80 | - | 12.12 | 11 |
| sol-15m | mrg0.05 | 50 | 5 | 33% [10-70] n=6 | -19.70 | -1.96 | -45.77 | -45 | 14 | 1 | 100% [21-100] n=1 | 14.45 | - | 16.91 | 12 |
| sol-15m | mrg0.05_2bp | 26 | 3 | 67% [21-94] n=3 | -11.03 | -0.47 | -15.78 | -8 | 13 | 1 | 100% [21-100] n=1 | 12.91 | - | 14.85 | 10 |
| sol-15m | mrg0.08 | 44 | 5 | 33% [10-70] n=6 | -23.05 | -1.85 | -62.44 | -47 | 14 | 1 | 100% [21-100] n=1 | 14.45 | - | 16.91 | 12 |
| sol-15m | mrg0.08_2bp | 22 | 3 | 67% [21-94] n=3 | -17.11 | -0.67 | -27.26 | -10 | 13 | 1 | 100% [21-100] n=1 | 12.91 | - | 14.85 | 10 |
| xrp-15m | mrg0.03 | 13 | 4 | 40% [12-77] n=5 | -7.21 | -0.88 | -12.88 | -6 | 2 | 2 | 50% [9-91] n=2 | 3.23 | 0.1 | 4.17 | 0 |
| xrp-15m | mrg0.03_2bp | 6 | 2 | 100% [34-100] n=2 | 6.94 | 10.08 | 7.46 | 3 | 0 | 0 | - [---] n=0 | - | - | - | - |
| xrp-15m | mrg0.05 | 11 | 3 | 25% [5-70] n=4 | -8.19 | -0.87 | -15.67 | -6 | 2 | 2 | 50% [9-91] n=2 | 3.23 | 0.1 | 4.17 | 0 |
| xrp-15m | mrg0.05_2bp | 4 | 1 | 100% [21-100] n=1 | 7.61 | - | 8.24 | 2 | 0 | 0 | - [---] n=0 | - | - | - | - |
| xrp-15m | mrg0.08 | 9 | 3 | 25% [5-70] n=4 | -12.24 | -1.41 | -30.97 | -7 | 2 | 2 | 50% [9-91] n=2 | 3.23 | 0.1 | 4.17 | 0 |
| xrp-15m | mrg0.08_2bp | 2 | 1 | 100% [21-100] n=1 | 10.16 | - | 11.32 | 2 | 0 | 0 | - [---] n=0 | - | - | - | - |
| btc-15m | mrg0.03 | 191 | 14 | 71% [45-88] n=14 | -4.83 | -0.32 | -6.66 | -40 | 42 | 4 | 75% [30-95] n=4 | -35.29 | -1 | -37.60 | -129 |
| btc-15m | mrg0.03_2bp | 139 | 8 | 62% [31-86] n=8 | -22.53 | -1.29 | -28.09 | -121 | 24 | 2 | 100% [34-100] n=2 | 5.64 | 36.80 | 6 | 11 |
| btc-15m | mrg0.05 | 143 | 12 | 67% [39-86] n=12 | -6.74 | -0.34 | -10.49 | -42 | 26 | 3 | 67% [21-94] n=3 | -72.64 | -2.81 | -79.25 | -135 |
| btc-15m | mrg0.05_2bp | 116 | 7 | 57% [25-84] n=7 | -27.14 | -1.38 | -36.17 | -119 | 1 | 1 | 100% [21-100] n=1 | 7.63 | - | 8.3 | 0 |
| btc-15m | mrg0.08 | 129 | 9 | 56% [27-81] n=9 | -8 | -0.36 | -13.41 | -44 | 13 | 2 | 50% [9-91] n=2 | -82.18 | -6.89 | -93.54 | -61 |
| btc-15m | mrg0.08_2bp | 109 | 6 | 50% [19-81] n=6 | -30.35 | -1.39 | -42.16 | -119 | 0 | 0 | - [---] n=0 | - | - | - | - |

| series | prints_last45 | no_fair | prints_in_favoured_side | favoured_prints_mean_q | favoured_prints_mean_f |
|---|---|---|---|---|---|
| eth-5m | 29,904 | 0 | 2,047 | 0.901 | 0.988 |
| eth-15m | 3,699 | 0 | 238 | 0.974 | 0.989 |
| sol-15m | 1,717 | 0 | 128 | 0.791 | 0.991 |
| xrp-15m | 896 | 0 | 139 | 0.945 | 0.991 |
| btc-15m | 15,168 | 0 | 1,139 | 0.887 | 0.987 |

In the 15m series the favoured side almost never trades 3 cents below the model in the last 45 seconds (eth 15m:
9 markets in six days, all won, $690 of turnover in total, about $8 per day; sol, xrp, btc 15m: 6-18 markets, of
which the favoured side mostly won only 40-75%). In eth 5m it happens in about 12 markets a day, and there the tape is right and the model is
wrong: positions bought at a 3-8 cent "discount" to a model value of 0.97+ won 70-80% of the time in tuning and
36-68% in reporting. Adding the 2 bp condition lifted tuning to 86-92% and reporting only to 50-77%, at prices
of 0.71-0.82. A discount to the Binance-based model in the last seconds is information (the official feed is not
Binance), not a gift.

### Selected variants (tuned on 21-24 Nov, reported on 25-26 Nov)

Selection rule from the protocol: highest clustered t in tuning among variants with at least 30 tuning markets
("eligible"); if none, the variant with the most markets.

| series | family | variant | eligible | tune mkts | tune trades | tune net c/sh | tune t | tune $/day | report mkts | report trades | report net c/sh | se | report t | report % turn | report $/day | report win rate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| eth-5m | M4 | D0_thr0.02 | 12 | 1,151 | 39,646 | 0.268 | 0.474 | 306.2 | 574 | 19,240 | -0.821 | 0.647 | -1.27 | -2.133 | -986.9 | 0.47 |
| eth-5m | M5 | mrg0.08 | 3 | 33 | 312 | 9.148 | 1.389 | 112.0 | 10 | 88 | -24.36 | 12.08 | -2.016 | -49.90 | -179.3 | 0.364 |
| eth-15m | M4 | D0_thr0.01 | 12 | 384 | 12,901 | -0.263 | -0.286 | -112.3 | 192 | 6,718 | 0.588 | 0.93 | 0.632 | 1.428 | 265.9 | 0.481 |
| eth-15m | M5 | mrg0.03 | 0 | 7 | 41 | 6.44 | 4.003 | 10.61 | 2 | 7 | 5.409 | 0.219 | 24.72 | 5.722 | 2.125 | 1 |
| sol-15m | M4 | D0_thr0.02 | 12 | 383 | 7,820 | -1.442 | -1.131 | -368.3 | 192 | 5,127 | 2.291 | 1.702 | 1.346 | 8.593 | 665.7 | 0.432 |
| sol-15m | M5 | mrg0.03 | 0 | 5 | 57 | -17.24 | -2.141 | -44.09 | 1 | 18 | 12.09 | - | - | 13.77 | 12.71 | 1 |
| xrp-15m | M4 | D2_thr0.01 | 12 | 380 | 5,933 | 1.272 | 1.016 | 245.1 | 191 | 2,883 | -5.473 | 1.744 | -3.138 | -17.48 | -979.5 | 0.427 |
| xrp-15m | M5 | mrg0.03 | 0 | 4 | 13 | -7.206 | -0.879 | -5.591 | 2 | 2 | 3.23 | 33.32 | 0.097 | 4.166 | 0.169 | 0.5 |
| btc-15m | M4 | D0_thr0.04 | 12 | 369 | 7,433 | 2.21 | 1.687 | 703.8 | 189 | 4,206 | -2.315 | 1.437 | -1.612 | -5.843 | -812.5 | 0.456 |
| btc-15m | M5 | mrg0.03 | 0 | 14 | 191 | -4.835 | -0.316 | -39.93 | 4 | 42 | -35.29 | 35.23 | -1.002 | -37.60 | -128.6 | 0.75 |

Net dollars per UTC day for the same variants, and all six days pooled (a re-aggregation of the trades above, not a
new variant):

| series | family | variant | 11-21 | 11-22 | 11-23 | 11-24 | 11-25 | 11-26 |
|---|---|---|---|---|---|---|---|---|
| eth-5m | M4 | D0_thr0.02 | 394.0 | 1,063 | -333.7 | 101.7 | -1,077 | -896.8 |
| eth-5m | M5 | mrg0.08 | -96.53 | 300.2 | 49.88 | 194.4 | -104.7 | -253.9 |
| eth-15m | M4 | D0_thr0.01 | 309.9 | 145.5 | -586.8 | -317.7 | 1,327 | -795.0 |
| eth-15m | M5 | mrg0.03 | 30.88 | 1.981 | 1.887 | 7.677 | 0.148 | 4.102 |
| sol-15m | M4 | D0_thr0.02 | -704.3 | -1,353 | 798.7 | -214.3 | 1,306 | 25.66 |
| sol-15m | M5 | mrg0.03 | -6.615 | 13.45 | -183.1 | -0.069 | 25.41 | - |
| xrp-15m | M4 | D2_thr0.01 | -126.6 | -803.5 | 270.6 | 1,640 | -774.5 | -1,184 |
| xrp-15m | M5 | mrg0.03 | - | 4.375 | -19.95 | -6.783 | -1.683 | 2.021 |
| btc-15m | M4 | D0_thr0.04 | 1,798 | -87.56 | 36.79 | 1,068 | -54.41 | -1,571 |
| btc-15m | M5 | mrg0.03 | 380.9 | -364.4 | -248.0 | 71.80 | 19.87 | -277.1 |

| series | family | variant | markets | trades | shares | net_c | se_c | t_mkt | usd_per_day | days_positive | days | t_by_day |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| eth-5m | M4 | D0_thr0.02 | 1,725 | 58,886 | 696,525 | -0.108 | 0.433 | -0.248 | -124.8 | 3 | 6 | -0.378 |
| eth-5m | M5 | mrg0.08 | 43 | 400 | 6,369 | 1.404 | 6.409 | 0.219 | 14.90 | 3 | 6 | 0.177 |
| eth-15m | M4 | D0_thr0.01 | 576 | 19,619 | 260,901 | 0.032 | 0.682 | 0.046 | 13.78 | 3 | 6 | 0.044 |
| eth-15m | M5 | mrg0.03 | 9 | 48 | 737.4 | 6.33 | 1.403 | 4.511 | 7.779 | 6 | 6 | 1.642 |
| sol-15m | M4 | D0_thr0.02 | 575 | 12,947 | 160,292 | -0.088 | 1.024 | -0.086 | -23.60 | 3 | 6 | -0.06 |
| sol-15m | M5 | mrg0.03 | 6 | 75 | 1,233 | -12.24 | 8.856 | -1.382 | -25.16 | 2 | 5 | -0.781 |
| xrp-15m | M4 | D2_thr0.01 | 571 | 8,816 | 112,864 | -0.867 | 1.03 | -0.842 | -163.1 | 2 | 6 | -0.389 |
| xrp-15m | M5 | mrg0.03 | 6 | 15 | 320.8 | -6.865 | 7.517 | -0.913 | -3.671 | 2 | 5 | -1.02 |
| btc-15m | M4 | D0_thr0.04 | 558 | 11,639 | 197,614 | 0.602 | 0.992 | 0.607 | 198.4 | 3 | 6 | 0.422 |
| btc-15m | M5 | mrg0.03 | 18 | 233 | 4,033 | -10.34 | 14.10 | -0.733 | -69.50 | 3 | 6 | -0.607 |

No selected variant meets the lab's bar (positive in reporting, t above 2, at least 100 markets). eth 15m M5 has a
t of 4.5 pooled, but on 9 markets and 737 shares in six days; nine wins out of nine (Wilson lower bound 70%) at about $8 a day is a curiosity, not a
strategy.

## Variants run

90 rule variants, each evaluated on both periods: M4 4 delays x 3 thresholds x 5 series = 60; M5 3 margins x 2 x 5
series = 30. All are in the tables above. The analysis script was run twice: once on the first-day slice of eth 5m
and btc 15m to check the code (its M4/M5 output for that day was on screen; no rule, filter or parameter was changed
afterwards, only two crashes were fixed), and once on the full period. Measurements that are not rules: M1, M2, M3,
M3b, proxy check, model diagnostic, and the per-day re-aggregations in `extra.py` (written after the full run, to
date the block-delay drift and to show the selected variants by day).

## What would have to be true for an edge here to be real

1. Resting quotes in a thin series would have to stay unchanged for seconds after Binance moves. The trade prices
   say they do not (M3b), and a rule that pays up whenever the tape is cheap against a 0-5 s old fair value earns
   nothing (M4). An edge of under one second may exist in btc 15m and eth 5m; it belongs to whoever is fastest.
2. The Binance model would have to know more than the tape. It does not (Brier scores), and where the two disagree
   most confidently, in the last 45 s, the tape wins (M5).
3. For sol 15m and eth 15m the reporting-period plus would have to be the truth and the tuning-period minus the
   noise. Nothing in the data favours that reading; the same variants are at -0.09 and +0.03 cents per share over
   six days.

## What could not be checked

- **Quotes.** Only trades are visible. A stale quote that nobody hit leaves no trace, and in sol/xrp 94-96% of
  seconds have no trade. M3b and M4 argue against stale quotes at the moments when trades happen; they cannot rule
  out stale quotes at other moments. That needs the L2 archive.
- **Whether we would get the fill.** Every simulated fill takes liquidity that a real taker took in that same print;
  we would have been racing that taker, with a 50 ms taker delay and no co-location. Real fills would be worse.
  About a fifth of prints are below the 5-share minimum order.
- **Timing to the second.** Block time is 1-3 s after the match with jitter, and the delay drifted from 3 to 1 s
  during the sample. D=0 and D=1 cannot be told apart from timestamp error; in tuning D=0 may contain up to a second
  of look-ahead.
- **Power.** Two reporting days give a standard error of 0.5-0.8 cents per share in eth 5m, 0.6-1.4 in eth 15m and
  btc 15m, and 1.5-2.0 in sol and xrp. An edge of a cent or two per share in sol or xrp cannot be excluded by this sample; it also
  cannot be shown, and the pond is $41-59K of taker flow per day.
- **Dependence between series.** Markets are treated as independent clusters. Windows of different assets at the same
  time move together, so adding up series would overstate significance; nothing here relies on that.
- **Other series and regimes.** doge, hype and the 5m sol/xrp series were not in the protocol. All six days come
  after the fee change of 20 Nov, in one volatility regime.
- **The official feed.** Chainlink prices were not used; the Binance proxy misses 1-2% of outcomes and is unreliable
  within about 2-3 bp of the strike.
- **Makers.** The other side of M2 (0.36-0.61 cents per share before any adverse-selection accounting per maker) was
  not tested as a strategy.

## Toolkit notes (nothing under pmlab/ was edited)

- `updown.BLOCK_LAG = 3` is not a constant: measured the same way in six series, the tape-vs-Binance peak lag was 2-3 s
  on 21-24 Nov and 1 s on 25-26 Nov. Timing-sensitive studies should estimate it per day.
- `Px.price(t)` is the close of the 1 s kline that opens at t, i.e. the price at t + 1, so `fair_up(px, t, ...)` uses
  information up to t + 1. This study used `fair_up(px, x - 1)` for "data up to x". Worth a line in the docstring.
- `fair_up` with the default `sigma_mult = 1.3` is under-confident in all six series on these days (calibration
  table above).
- `Px.load` falls back to downloading a whole day from the mirror, uncached, when a daily dump is missing; the study
  fetched the 180 seconds it needed from 27 Nov itself (`common.load_px`).
- `updown.tape` writes its temporary file as `<condition>.jsonl.tmp`; two studies fetching the same market at the
  same moment would write the same file. Not observed, but the btc 5m cache is shared with another study.

## Ideas (not run)

1. Measure quote staleness directly in sol 15m and xrp 15m from the L2 archive (HF `chitoyuuri/polymarket-l2-v3-1-archive`,
   crypto about 75 MB per hour): seconds until best bid/ask moves after a Binance move of a given size, and the depth
   that sits there meanwhile. The tape cannot see this.
2. Maker study on eth 5m and eth 15m at the 0.01 fee: takers give up 0.4 cents per share before fees. Test a passive
   quote with `updown.sellable`, 1-2 s of staleness and realistic queue position (needs L2), per-maker adverse
   selection included.
3. Rerun this exact protocol on the next two weeks of data for power, with the block lag estimated per day.
4. Recalibrate the fair value per series (volatility multiplier, official price to beat rescaled by the basis)
   under a new protocol on fresh days; with the current model the taker rule is mostly an underdog-buying rule.
5. Explain the M5 failures in eth 5m: when the Binance model says 0.97+ and the tape is 3+ cents cheaper, who is
   selling and what do they see? Needs the Chainlink stream next to Binance (the official feed needs a key from
   30 Nov).
6. Pre-window fills in eth 5m/15m (takers +1.1 to +1.3 cents per share after fees, t 0.8-1.4): too weak to act on,
   cheap to re-measure on a longer sample.
