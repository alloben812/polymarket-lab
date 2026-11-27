# BTC 5-minute markets: is the nearly decided side underpriced in the last minute? — results

Study run 2026-11-27. Protocol: `protocol.md` (written before any outcome number). Code: `fetch.py`, `build.py`,
`sanity.py`, `analyze.py` (protocol runs), `diag.py`, `ws_extract.py`, `ws_timing.py` (post-hoc diagnostics, marked as
such below), `make_tables.py`. Raw outputs: `out/report.txt`, `out/variants.csv`, `out/descriptive.csv`,
`out/basis.csv`, `out/calibration.csv`, `out/diag.txt`, `out/ws_timing.txt`, `out/extra.txt`.

## Verdict: INCONCLUSIVE

- **Without the basis filter there is no edge.** Buying the model's favourite 2-8 cents under the model value made
  -7.3..+3.7 c/share in tuning (L = 60: +1.3..+3.7, L = 30: -1.5..+1.7, L = 15: -4.0..-7.3; no t above 1.1) and
  lost 3.4..22 c/share in the reporting period (all 18 runs negative, t -0.1..-1.0). Every run has 1-2 losing markets
  per period out of 4-73 traded. Across the unfiltered D = 1 runs there are four losing markets in total: in three
  Binance called the official result wrong (Chainlink/Binance basis, distance $7-11 from the strike), in one the
  price really reversed (distance $12, 19 s left).
- **With the basis filter (|expected average - strike| >= E99 = $18.63) no traded market lost at D = 1 s**, in either
  period: the variant that was best in tuning (L = 60 s, floor 0.99, margin 0.02) made +5.30 c/share on 34 markets in
  tuning ($105/day at <= 500 shares per market) and +3.58 c/share on 5 markets in the reporting period ($30/day).
  The widest filtered variant (floor 0.97, margin 0.02): 49 markets, +5.23 c, $163/day in tuning; 10 markets,
  +6.43 c, $90/day in reporting.
- **Why this is not an OPPORTUNITY yet.** The reporting period has 5-11 traded markets, far below the 100 the verdict
  rule requires. The large t values (3.6-13) come from a sample with zero losses and say nothing about the one event
  that matters: a lost market at the 500-share cap costs about $470, as much as 34-39 average winning markets
  ($12-14 each). Break-even is one lost market in about 19 (5.0-5.4%). With 0 losses in 39 markets (judged
  variant) the 95% upper bound on the loss rate is 7.4%; with 0 in 59 (widest) it is 5.0%. If the prices paid were fair probabilities, "all win" would still
  happen 14% (judged) or 3.7% (widest) of the time, and that is before counting 42 runs. The D = 2 s re-runs with
  floor 0.97 did lose one bet (-$143 on 150 shares of Up bought at about 0.95 with 56 s left, model 0.985, expected
  average $78 above the strike; the expected average fell $105 in the next 28 s and the same run then bought Down).
- **The literal question** ("is the nearly decided side underpriced late in the window?"): in the last 15 s, no: once
  the distance is outside the basis band nothing prints 2 c under the model (0 trades in all six L = 15 filtered runs),
  and what does print cheap is basis risk and loses. No filtered D = 1 run traded inside the last 22 s. All
  filtered trades sit 22-60 s before the end (median 44-46 s), they come in single-block bursts (median 1 distinct
  second per market), and 30-51% of the volume is within 1 s of the moment the Binance signal appeared. This is the
  familiar stale-quote race after a Binance move, not a slow lock-in mispricing.
- **Size if it were real.** About 10 markets a day in the widest filtered variant (19, 13, 6, 11, 6, 4 on
  21..26 Nov: falling), a median of $205-220 spent per market, and on the tape-fill assumption at <= 500 shares per
  market $105/day (tuning) and $30/day (reporting) for the judged variant, $163 and $90 for the widest. A real-time
  check on 21-22 Nov (below) says only about half of that volume was still a valid signal 1 s before the actual
  match, so a realistic ceiling is roughly $15-80/day before competition, and less for an account that can only buy
  50-300 shares. It could also be zero or negative: see "What would have to be true".

## What was measured

- Universe: all 1,728 BTC 5m windows starting 2026-11-21 00:00 .. 2026-11-26 23:55 UTC. All 1,728 were resolved and
  had a tape (2,653,763 fills; tape shares equal gamma `volume` in 1,572 of the 1,575 markets where gamma reports
  one, the other three show a volume of 2-46, so the tapes are complete). Fee rate on metadata 0.05 for all. Tuning 1,152 windows (21-24 Nov), reporting 576 (25-26 Nov).
- Outcome: official `up_won`. Official prices agree with it (`final >= price_to_beat`) in all 1,727 markets that
  have both prices.
- Binance 1 s closes for 20-27 Nov (no gaps). 260,072 tape rows have a match time in the last 60 s.
- Sanity slice (first 48 windows, before the full run): BUY prints at 0.45-0.55 won 48.0% (n = 6,048, t = -0.8 by
  market), fee 1.25 c at 0.50 and 0.1455 c at 0.97, 94% of rows stamped inside [t0, t1+10], proxy = official in 45/48.

## Descriptive table (no rule)

### T1. Taker BUY prints with match time in the last 60 s (m < t1), all 1,728 markets

| price bucket | prints | markets | shares | avg price | win rate (share-w.) | fee c/sh | net c/sh | se | t (by market) | net c/sh tune (t) | net c/sh report (t) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| <0.50 | 71,642 | 1525 | 8,178,122 | 0.051 | 0.043 | 0.189 | -0.93 | 0.34 | -2.77 | -1.51 (-4.3) | +0.26 (+0.4) |
| 0.50-0.80 | 31,585 | 387 | 673,466 | 0.660 | 0.652 | 1.084 | -1.87 | 1.63 | -1.14 | +1.56 (+0.8) | -8.85 (-3.1) |
| 0.80-0.90 | 21,244 | 484 | 439,631 | 0.852 | 0.870 | 0.628 | +1.26 | 1.77 | +0.71 | +2.84 (+1.6) | -1.30 (-0.4) |
| 0.90-0.95 | 20,284 | 602 | 414,189 | 0.925 | 0.949 | 0.345 | +2.07 | 0.99 | +2.08 | +3.21 (+3.6) | +0.17 (+0.1) |
| 0.95-0.98 | 23,598 | 729 | 626,979 | 0.965 | 0.982 | 0.170 | +1.53 | 0.51 | +3.02 | +2.23 (+5.1) | +0.16 (+0.1) |
| 0.98-1.00 | 36,273 | 910 | 2,400,744 | 0.988 | 0.994 | 0.058 | +0.55 | 0.28 | +1.97 | +0.86 (+5.2) | -0.23 (-0.3) |
| 0.90-1.00 (pooled) | 80,155 | 912 | 3,441,911 | 0.976 | 0.987 | 0.113 | +0.91 | 0.35 | +2.62 | +1.35 (+6.2) | -0.09 (-0.1) |
| 0.50-1.00 (pooled) | 132,984 | 912 | 4,555,008 | 0.918 | 0.926 | 0.306 | +0.53 | 0.52 | +1.02 | +1.51 (+3.3) | -1.59 (-1.2) |

The same table restricted to m <= t1-2 differs only in the third decimal (`out/descriptive.csv`).

Reading: over all six days favourites bought at 0.90-1.00 in the last minute earned +0.91 c/share after fees
(t = 2.6 by market), which matches the sign of the earlier 278-market number (+0.41 c). But it is entirely the
tuning days (+1.35 c, t = 6.2); on 25-26 Nov it is -0.09 c (t = -0.1). Buying the 0.50-0.80 zone lost 8.8 c/share on
25-26 Nov. A blind "buy the favourite late" rule therefore has no stable edge; it is a small premium paid for
carrying reversal and basis risk, and it flips sign between adjacent days.

## Basis risk (Binance proxy vs official Chainlink average)

Proxy error = (Binance end TWAP - final_price) - (Binance start TWAP - price_to_beat), USD, 1,727 windows (one
window, t0 = 1795494600, has no `finalPrice` in gamma). Mean BTC price $60,075.

| statistic | value |
|---|---|
| mean / sd | -0.03 / 5.64 |
| signed percentiles 1 / 5 / 25 / 50 / 75 / 95 / 99 | -14.33 / -8.82 / -2.84 / 0.00 / +2.94 / +8.46 / +13.80 |
| abs percentiles 50 / 90 / 95 / 99 / max | 2.92 / 8.71 / 10.96 / **18.63 (E99)** / 61.37 |
| abs in basis points 50 / 90 / 95 / 99 / max | 0.49 / 1.44 / 1.84 / 3.12 / 9.66 |
| E99 on tuning windows only / reporting only | 20.46 / 12.46 |
| proxy outcome differs from the official one | 33 of 1,727 (1.91%) |
| abs Binance end-start difference in those 33 misses, 50 / 90 / max | 2.55 / 6.55 / 15.83 |
| windows whose official abs(final - price_to_beat) is below E99 | 19.3% |

E99 used in the rules is the all-window value, $18.63, as the protocol says. With the tuning-only value ($20.46)
25 of 449 trades of the judged variant (56 of 744 for the widest) would have been skipped; all of them won, so the
look-ahead in E99 does not create the result.

**Post-hoc finding (added after the protocol; not a trading rule): the official average is about 4-5 s behind
Binance.** If the Binance 60 s TWAP is ended s seconds earlier at both ends of the window, the proxy error is:

| shift s | -8 | -6 | -5 | -4 | -3 | -2 | -1 | 0 (toolkit) | +1 |
|---|---|---|---|---|---|---|---|---|---|
| sd of error, USD | 4.65 | 3.00 | **2.54** | 2.55 | 3.02 | 3.78 | 4.69 | 5.64 | 6.56 |
| p99 abs error, USD | 15.57 | 10.35 | **9.90** | 10.40 | 10.78 | 12.46 | 15.27 | 18.63 | 22.35 |
| proxy outcome wrong | 1.16% | 0.69% | **0.69%** | 0.81% | 0.81% | 1.39% | 1.68% | 1.91% | 2.03% |

The minimum is at -4..-5 s in both periods separately (sd 2.78 / 1.95). In Binance time the settlement average
effectively covers roughly (t1-65, t1-5]: the result is known on Binance about 5 s before the window ends, to within
~$10 (1.7 bp). `pmlab.fair.fair_up` and `px.twap(t, 60)` assume the average ends at t1, which makes the model ~4.5 s
late in its lock-in schedule and nearly doubles the basis band. The protocol rules were run with the toolkit as it is.

## Rule family (42 runs = (18 + 3) parameter sets x exclusion on/off)

Implementation as fixed in `protocol.md`: candidate fills from `buyable()`, match time m = block time - 3, model
called at t = m - D - 1 (last Binance second fully closed by m - D), favoured side only, f >= floor, q <= f - margin,
q >= 0.50, print >= 5 shares, min(print, 100) per fill, 500 shares per market, fee 0.05 q (1-q), hold to official
settlement. No print had a missing model value. "t" is `ratio_cluster` by market. "win (markets)" counts a market
as won when at least half of its shares won. Ranking for the D = 2 step (tuning rows only, exclusion on, >= 30
traded markets): only two triples had 30+ markets — (60, 0.99, 0.02) at +5.30 c and (60, 0.97, 0.02) at +5.23 c —
the third slot went to (60, 0.97, 0.04) by number of markets, as the protocol prescribes. **Judged variant:
L = 60, floor 0.99, margin 0.02, D = 1, exclusion on.**

### T3. Rule family, tuning period (21-24 Nov, 1,152 markets, 4 days)

| L | floor | margin | D | excl. | trades | markets | shares | avg price | win (trades) [Wilson] | win (markets) [Wilson] | lost mkts (of them proxy miss) | net c/sh | se | t | net $ | $/day |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 60 | 0.97 | 0.02 | 1 | on | 626 | 49 | 12,509 | 0.945 | 1.000 [0.994, 1.000] | 1.000 [0.927, 1.000] | 0 (0) | +5.23 | 0.39 | 13.2 | +654 | +163 |
| 60 | 0.97 | 0.02 | 1 | off | 1117 | 73 | 23,250 | 0.923 | 0.964 [0.952, 0.974] | 0.973 [0.905, 0.992] | 2 (2) | +3.05 | 2.76 | 1.1 | +709 | +177 |
| 60 | 0.97 | 0.04 | 1 | on | 264 | 25 | 5,378 | 0.914 | 1.000 [0.986, 1.000] | 1.000 [0.867, 1.000] | 0 (0) | +8.19 | 1.03 | 7.9 | +440 | +110 |
| 60 | 0.97 | 0.04 | 1 | off | 716 | 45 | 14,935 | 0.893 | 0.940 [0.920, 0.955] | 0.956 [0.852, 0.988] | 2 (2) | +3.64 | 4.33 | 0.8 | +544 | +136 |
| 60 | 0.97 | 0.08 | 1 | on | 97 | 9 | 1,652 | 0.859 | 1.000 [0.962, 1.000] | 1.000 [0.701, 1.000] | 0 (0) | +13.55 | 1.54 | 8.8 | +224 | +56 |
| 60 | 0.97 | 0.08 | 1 | off | 410 | 25 | 8,565 | 0.840 | 0.907 [0.875, 0.932] | 0.920 [0.750, 0.978] | 2 (2) | +3.68 | 7.15 | 0.5 | +315 | +79 |
| 60 | 0.99 | 0.02 | 1 | on | 387 | 34 | 7,922 | 0.944 | 1.000 [0.990, 1.000] | 1.000 [0.898, 1.000] | 0 (0) | +5.30 | 0.68 | 7.8 | +420 | +105 |
| 60 | 0.99 | 0.02 | 1 | off | 766 | 52 | 16,306 | 0.920 | 0.956 [0.939, 0.968] | 0.962 [0.870, 0.989] | 2 (2) | +1.55 | 3.79 | 0.4 | +252 | +63 |
| 60 | 0.99 | 0.04 | 1 | on | 183 | 15 | 3,659 | 0.917 | 1.000 [0.979, 1.000] | 1.000 [0.796, 1.000] | 0 (0) | +7.90 | 1.38 | 5.7 | +289 | +72 |
| 60 | 0.99 | 0.04 | 1 | off | 517 | 32 | 11,000 | 0.891 | 0.936 [0.912, 0.954] | 0.938 [0.799, 0.983] | 2 (2) | +1.32 | 5.66 | 0.2 | +145 | +36 |
| 60 | 0.99 | 0.08 | 1 | on | 61 | 6 | 1,119 | 0.852 | 1.000 [0.941, 1.000] | 1.000 [0.610, 1.000] | 0 (0) | +14.15 | 2.28 | 6.2 | +158 | +40 |
| 60 | 0.99 | 0.08 | 1 | off | 315 | 20 | 6,725 | 0.827 | 0.914 [0.878, 0.940] | 0.900 [0.699, 0.972] | 2 (2) | +1.78 | 8.92 | 0.2 | +120 | +30 |
| 30 | 0.97 | 0.02 | 1 | on | 125 | 8 | 2,928 | 0.943 | 1.000 [0.970, 1.000] | 1.000 [0.676, 1.000] | 0 (0) | +5.46 | 1.01 | 5.4 | +160 | +40 |
| 30 | 0.97 | 0.02 | 1 | off | 653 | 35 | 13,995 | 0.907 | 0.939 [0.918, 0.955] | 0.943 [0.814, 0.984] | 2 (2) | +1.74 | 4.59 | 0.4 | +243 | +61 |
| 30 | 0.97 | 0.04 | 1 | on | 60 | 5 | 1,642 | 0.924 | 1.000 [0.940, 1.000] | 1.000 [0.566, 1.000] | 0 (0) | +7.26 | 1.34 | 5.4 | +119 | +30 |
| 30 | 0.97 | 0.04 | 1 | off | 521 | 28 | 11,208 | 0.890 | 0.917 [0.891, 0.938] | 0.929 [0.774, 0.980] | 2 (2) | +1.68 | 5.73 | 0.3 | +189 | +47 |
| 30 | 0.97 | 0.08 | 1 | on | 26 | 1 | 320 | 0.871 | 1.000 [0.871, 1.000] | 1.000 [0.207, 1.000] | 0 (0) | +12.34 | - | - | +39 | +10 |
| 30 | 0.97 | 0.08 | 1 | off | 323 | 18 | 6,855 | 0.838 | 0.882 [0.843, 0.913] | 0.889 [0.672, 0.969] | 2 (2) | +1.02 | 8.85 | 0.1 | +70 | +17 |
| 30 | 0.99 | 0.02 | 1 | on | 63 | 7 | 1,564 | 0.961 | 1.000 [0.943, 1.000] | 1.000 [0.646, 1.000] | 0 (0) | +3.74 | 0.38 | 9.9 | +59 | +15 |
| 30 | 0.99 | 0.02 | 1 | off | 435 | 25 | 9,763 | 0.905 | 0.922 [0.893, 0.944] | 0.920 [0.750, 0.978] | 2 (2) | -1.10 | 6.31 | -0.2 | -107 | -27 |
| 30 | 0.99 | 0.04 | 1 | on | 19 | 2 | 553 | 0.951 | 1.000 [0.832, 1.000] | 1.000 [0.342, 1.000] | 0 (0) | +4.71 | 0.10 | 48.6 | +26 | +7 |
| 30 | 0.99 | 0.04 | 1 | off | 362 | 20 | 8,031 | 0.886 | 0.909 [0.875, 0.934] | 0.900 [0.699, 0.972] | 2 (2) | -1.52 | 7.70 | -0.2 | -122 | -30 |
| 30 | 0.99 | 0.08 | 1 | on | 0 | 0 | 0 | - | - | - | - | - | - | - | 0 | 0 |
| 30 | 0.99 | 0.08 | 1 | off | 242 | 14 | 5,356 | 0.819 | 0.888 [0.843, 0.922] | 0.857 [0.601, 0.960] | 2 (2) | -1.27 | 11.17 | -0.1 | -68 | -17 |
| 15 | 0.97 | 0.02 | 1 | on | 0 | 0 | 0 | - | - | - | - | - | - | - | 0 | 0 |
| 15 | 0.97 | 0.02 | 1 | off | 141 | 9 | 3,244 | 0.845 | 0.851 [0.783, 0.900] | 0.778 [0.453, 0.937] | 2 (2) | -4.01 | 15.10 | -0.3 | -130 | -32 |
| 15 | 0.97 | 0.04 | 1 | on | 0 | 0 | 0 | - | - | - | - | - | - | - | 0 | 0 |
| 15 | 0.97 | 0.04 | 1 | off | 126 | 8 | 2,838 | 0.818 | 0.810 [0.732, 0.869] | 0.750 [0.409, 0.929] | 2 (2) | -3.97 | 17.20 | -0.2 | -113 | -28 |
| 15 | 0.97 | 0.08 | 1 | on | 0 | 0 | 0 | - | - | - | - | - | - | - | 0 | 0 |
| 15 | 0.97 | 0.08 | 1 | off | 93 | 7 | 2,178 | 0.770 | 0.774 [0.679, 0.847] | 0.714 [0.359, 0.918] | 2 (2) | -6.10 | 22.45 | -0.3 | -133 | -33 |
| 15 | 0.99 | 0.02 | 1 | on | 0 | 0 | 0 | - | - | - | - | - | - | - | 0 | 0 |
| 15 | 0.99 | 0.02 | 1 | off | 140 | 9 | 3,242 | 0.879 | 0.879 [0.814, 0.923] | 0.778 [0.453, 0.937] | 2 (2) | -7.30 | 16.39 | -0.4 | -237 | -59 |
| 15 | 0.99 | 0.04 | 1 | on | 0 | 0 | 0 | - | - | - | - | - | - | - | 0 | 0 |
| 15 | 0.99 | 0.04 | 1 | off | 120 | 8 | 2,840 | 0.849 | 0.867 [0.794, 0.916] | 0.750 [0.409, 0.929] | 2 (2) | -7.18 | 18.90 | -0.4 | -204 | -51 |
| 15 | 0.99 | 0.08 | 1 | on | 0 | 0 | 0 | - | - | - | - | - | - | - | 0 | 0 |
| 15 | 0.99 | 0.08 | 1 | off | 88 | 7 | 2,176 | 0.777 | 0.886 [0.803, 0.937] | 0.714 [0.359, 0.918] | 2 (2) | -6.78 | 22.53 | -0.3 | -148 | -37 |
| 60 | 0.99 | 0.02 | 2 | on | 326 | 28 | 6,877 | 0.948 | 1.000 [0.988, 1.000] | 1.000 [0.879, 1.000] | 0 (0) | +4.92 | 0.56 | 8.8 | +338 | +85 |
| 60 | 0.99 | 0.02 | 2 | off | 700 | 46 | 15,097 | 0.927 | 0.976 [0.961, 0.985] | 0.957 [0.855, 0.988] | 2 (2) | +2.95 | 3.43 | 0.9 | +446 | +111 |
| 60 | 0.97 | 0.02 | 2 | on | 616 | 47 | 12,858 | 0.945 | 0.992 [0.981, 0.997] | 1.000 [0.924, 1.000] | 0 (0) | +4.10 | 1.12 | 3.6 | +527 | +132 |
| 60 | 0.97 | 0.02 | 2 | off | 1122 | 71 | 23,929 | 0.927 | 0.963 [0.951, 0.973] | 0.972 [0.903, 0.992] | 2 (2) | +2.17 | 2.87 | 0.8 | +518 | +130 |
| 60 | 0.97 | 0.04 | 2 | on | 274 | 27 | 5,750 | 0.915 | 0.993 [0.974, 0.998] | 1.000 [0.875, 1.000] | 0 (0) | +7.91 | 0.96 | 8.2 | +455 | +114 |
| 60 | 0.97 | 0.04 | 2 | off | 751 | 48 | 15,756 | 0.900 | 0.951 [0.933, 0.964] | 0.958 [0.860, 0.988] | 2 (2) | +3.17 | 4.32 | 0.7 | +499 | +125 |

### T4. Rule family, reporting period (25-26 Nov, 576 markets, 2 days)

| L | floor | margin | D | excl. | trades | markets | shares | avg price | win (trades) [Wilson] | win (markets) [Wilson] | lost mkts (of them proxy miss) | net c/sh | se | t | net $ | $/day |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 60 | 0.97 | 0.02 | 1 | on | 118 | 10 | 2,790 | 0.933 | 1.000 [0.968, 1.000] | 1.000 [0.722, 1.000] | 0 (0) | +6.43 | 1.80 | 3.6 | +179 | +90 |
| 60 | 0.97 | 0.02 | 1 | off | 307 | 21 | 7,409 | 0.903 | 0.889 [0.849, 0.920] | 0.905 [0.711, 0.973] | 2 (1) | -4.19 | 7.72 | -0.5 | -310 | -155 |
| 60 | 0.97 | 0.04 | 1 | on | 72 | 7 | 1,573 | 0.905 | 1.000 [0.949, 1.000] | 1.000 [0.646, 1.000] | 0 (0) | +9.12 | 2.33 | 3.9 | +143 | +72 |
| 60 | 0.97 | 0.04 | 1 | off | 254 | 16 | 5,870 | 0.884 | 0.870 [0.823, 0.906] | 0.875 [0.640, 0.965] | 2 (1) | -5.89 | 9.64 | -0.6 | -345 | -173 |
| 60 | 0.97 | 0.08 | 1 | on | 28 | 2 | 562 | 0.846 | 1.000 [0.879, 1.000] | 1.000 [0.342, 1.000] | 0 (0) | +14.72 | 1.27 | 11.6 | +83 | +41 |
| 60 | 0.97 | 0.08 | 1 | off | 169 | 10 | 3,580 | 0.809 | 0.769 [0.700, 0.826] | 0.800 [0.490, 0.943] | 2 (1) | -9.52 | 15.74 | -0.6 | -341 | -170 |
| 60 | 0.99 | 0.02 | 1 | on | 62 | 5 | 1,664 | 0.962 | 1.000 [0.942, 1.000] | 1.000 [0.566, 1.000] | 0 (0) | +3.58 | 0.43 | 8.3 | +60 | +30 |
| 60 | 0.99 | 0.02 | 1 | off | 191 | 12 | 4,400 | 0.917 | 0.791 [0.727, 0.842] | 0.833 [0.552, 0.953] | 2 (1) | -10.20 | 11.10 | -0.9 | -449 | -224 |
| 60 | 0.99 | 0.04 | 1 | on | 32 | 3 | 648 | 0.940 | 1.000 [0.893, 1.000] | 1.000 [0.438, 1.000] | 0 (0) | +5.77 | 0.52 | 11.0 | +37 | +19 |
| 60 | 0.99 | 0.04 | 1 | off | 157 | 10 | 3,267 | 0.897 | 0.745 [0.672, 0.807] | 0.800 [0.490, 0.943] | 2 (1) | -14.54 | 14.61 | -1.0 | -475 | -238 |
| 60 | 0.99 | 0.08 | 1 | on | 0 | 0 | 0 | - | - | - | - | - | - | - | 0 | 0 |
| 60 | 0.99 | 0.08 | 1 | off | 95 | 6 | 1,978 | 0.811 | 0.579 [0.478, 0.673] | 0.667 [0.300, 0.903] | 2 (1) | -22.08 | 25.40 | -0.9 | -437 | -218 |
| 30 | 0.97 | 0.02 | 1 | on | 38 | 3 | 1,080 | 0.906 | 1.000 [0.908, 1.000] | 1.000 [0.438, 1.000] | 0 (0) | +8.98 | 4.72 | 1.9 | +97 | +49 |
| 30 | 0.97 | 0.02 | 1 | off | 244 | 15 | 6,112 | 0.895 | 0.861 [0.812, 0.899] | 0.867 [0.621, 0.963] | 2 (1) | -6.28 | 9.36 | -0.7 | -384 | -192 |
| 30 | 0.97 | 0.04 | 1 | on | 37 | 3 | 946 | 0.888 | 1.000 [0.906, 1.000] | 1.000 [0.438, 1.000] | 0 (0) | +10.72 | 3.77 | 2.8 | +101 | +51 |
| 30 | 0.97 | 0.04 | 1 | off | 222 | 13 | 5,242 | 0.880 | 0.851 [0.799, 0.892] | 0.846 [0.578, 0.957] | 2 (1) | -7.54 | 10.78 | -0.7 | -395 | -198 |
| 30 | 0.97 | 0.08 | 1 | on | 21 | 1 | 464 | 0.838 | 1.000 [0.845, 1.000] | 1.000 [0.207, 1.000] | 0 (0) | +15.48 | - | - | +72 | +36 |
| 30 | 0.97 | 0.08 | 1 | off | 153 | 9 | 3,277 | 0.803 | 0.745 [0.671, 0.808] | 0.778 [0.453, 0.937] | 2 (1) | -11.60 | 16.97 | -0.7 | -380 | -190 |
| 30 | 0.99 | 0.02 | 1 | on | 17 | 2 | 616 | 0.957 | 1.000 [0.816, 1.000] | 1.000 [0.342, 1.000] | 0 (0) | +4.07 | 1.34 | 3.0 | +25 | +13 |
| 30 | 0.99 | 0.02 | 1 | off | 146 | 9 | 3,352 | 0.902 | 0.726 [0.649, 0.792] | 0.778 [0.453, 0.937] | 2 (1) | -14.42 | 14.46 | -1.0 | -483 | -242 |
| 30 | 0.99 | 0.04 | 1 | on | 16 | 2 | 481 | 0.936 | 1.000 [0.806, 1.000] | 1.000 [0.342, 1.000] | 0 (0) | +6.11 | 0.73 | 8.4 | +29 | +15 |
| 30 | 0.99 | 0.04 | 1 | off | 141 | 9 | 3,101 | 0.894 | 0.716 [0.637, 0.784] | 0.778 [0.453, 0.937] | 2 (1) | -15.58 | 15.44 | -1.0 | -483 | -242 |
| 30 | 0.99 | 0.08 | 1 | on | 0 | 0 | 0 | - | - | - | - | - | - | - | 0 | 0 |
| 30 | 0.99 | 0.08 | 1 | off | 95 | 6 | 1,978 | 0.811 | 0.579 [0.478, 0.673] | 0.667 [0.300, 0.903] | 2 (1) | -22.08 | 25.40 | -0.9 | -437 | -218 |
| 15 | 0.97 | 0.02 | 1 | on | 0 | 0 | 0 | - | - | - | - | - | - | - | 0 | 0 |
| 15 | 0.97 | 0.02 | 1 | off | 86 | 4 | 1,797 | 0.905 | 0.779 [0.681, 0.854] | 0.750 [0.301, 0.954] | 1 (1) | -7.44 | 17.26 | -0.4 | -134 | -67 |
| 15 | 0.97 | 0.04 | 1 | on | 0 | 0 | 0 | - | - | - | - | - | - | - | 0 | 0 |
| 15 | 0.97 | 0.04 | 1 | off | 86 | 4 | 1,687 | 0.899 | 0.779 [0.681, 0.854] | 0.750 [0.301, 0.954] | 1 (1) | -7.95 | 18.29 | -0.4 | -134 | -67 |
| 15 | 0.97 | 0.08 | 1 | on | 0 | 0 | 0 | - | - | - | - | - | - | - | 0 | 0 |
| 15 | 0.97 | 0.08 | 1 | off | 64 | 4 | 1,311 | 0.800 | 0.703 [0.582, 0.801] | 0.750 [0.301, 0.954] | 1 (1) | -3.42 | 25.81 | -0.1 | -45 | -22 |
| 15 | 0.99 | 0.02 | 1 | on | 0 | 0 | 0 | - | - | - | - | - | - | - | 0 | 0 |
| 15 | 0.99 | 0.02 | 1 | off | 76 | 4 | 1,523 | 0.900 | 0.750 [0.642, 0.834] | 0.750 [0.301, 0.954] | 1 (1) | -9.93 | 20.03 | -0.5 | -151 | -76 |
| 15 | 0.99 | 0.04 | 1 | on | 0 | 0 | 0 | - | - | - | - | - | - | - | 0 | 0 |
| 15 | 0.99 | 0.04 | 1 | off | 74 | 4 | 1,452 | 0.897 | 0.743 [0.633, 0.829] | 0.750 [0.301, 0.954] | 1 (1) | -10.57 | 20.98 | -0.5 | -153 | -77 |
| 15 | 0.99 | 0.08 | 1 | on | 0 | 0 | 0 | - | - | - | - | - | - | - | 0 | 0 |
| 15 | 0.99 | 0.08 | 1 | off | 56 | 4 | 1,208 | 0.793 | 0.661 [0.530, 0.771] | 0.750 [0.301, 0.954] | 1 (1) | -4.67 | 28.11 | -0.2 | -56 | -28 |
| 60 | 0.99 | 0.02 | 2 | on | 74 | 6 | 1,896 | 0.955 | 1.000 [0.951, 1.000] | 1.000 [0.610, 1.000] | 0 (0) | +4.29 | 0.81 | 5.3 | +81 | +41 |
| 60 | 0.99 | 0.02 | 2 | off | 173 | 13 | 3,755 | 0.937 | 0.913 [0.862, 0.947] | 0.846 [0.578, 0.957] | 2 (1) | -0.68 | 4.66 | -0.1 | -26 | -13 |
| 60 | 0.97 | 0.02 | 2 | on | 164 | 11 | 3,445 | 0.927 | 1.000 [0.977, 1.000] | 1.000 [0.741, 1.000] | 0 (0) | +7.02 | 1.51 | 4.7 | +242 | +121 |
| 60 | 0.97 | 0.02 | 2 | off | 345 | 22 | 7,893 | 0.903 | 0.901 [0.865, 0.929] | 0.909 [0.722, 0.975] | 2 (1) | -3.34 | 7.29 | -0.5 | -263 | -132 |
| 60 | 0.97 | 0.04 | 2 | on | 88 | 7 | 1,973 | 0.898 | 1.000 [0.958, 1.000] | 1.000 [0.646, 1.000] | 0 (0) | +9.72 | 1.74 | 5.6 | +192 | +96 |
| 60 | 0.97 | 0.04 | 2 | off | 248 | 16 | 5,981 | 0.882 | 0.867 [0.819, 0.904] | 0.875 [0.640, 0.965] | 2 (1) | -5.38 | 9.49 | -0.6 | -322 | -161 |

## Attacks on the positive (filtered) result

1. **Look-ahead through the time stamps: ruled out.** Post-hoc check with WebSocket trade events that carry the
   exchange time in ms (HF `ithiria894/polymarket-l2-orderbook`, 21 Nov 00:00 - 22 Nov 11:00, 410 of our markets):
   324,953 tape rows (56%) match one-to-one. Block time minus real match time: 1.06 / 1.69 / **2.09** / 2.47 / 3.33 s
   (1 / 25 / 50 / 75 / 99th percentile), 3.4% above 3 s and none above 4 s; same in the last minute. So the real match is 0.9 s LATER
   than the toolkit's `block time - 3`, and at D = 1 the model used Binance data that was 0.6-3.0 s old at the real
   match. No fill used information from after the match.
2. **But the signal was often stale by the time of the print.** For the traded prints with a real match time
   (93-131 prints, 14-20 markets), the rule condition recomputed on the Binance second closed just before the real
   match held for only 36% (judged) / 46% (widest) of the shares; with 1 s of delay 45% / 58%; with 2 s 64% / 79%.
   In the rest Binance had already moved back and the cheap print was the market being fresher than the model.
   Those prints still won here, but they are adverse selection, not edge; the D = 2 loss above is exactly this case.
   Only the part where the signal is still true about 1 s before the match (about half) is something a trader
   watching Binance could have bought on purpose.
3. **Fills.** Each trade is a print that somebody else took: 212-275 different wallets, the top 10 took 38-39% of
   the printed size. The price was demonstrably there, but to get it one has to arrive before that taker; with a
   median of one distinct second of fills per market and no market with fills in 5 or more seconds, a late order
   finds nothing. Depth beyond the print is unknown. Only 8-14 markets filled the 500-share cap.
4. **Multiplicity and sample.** 42 runs; the filtered ones overlap heavily, so there are really 64 distinct
   traded markets in six days (59 at D = 1) and 12 in the reporting period. Zero losses in 59 markets is compatible with a loss
   rate up to 5%, which is the break-even rate.
5. **Decay.** Traded markets per day (widest filtered variant): 19, 13, 6, 11, 6, 4. The first days after the
   20 Nov fee change carry most of the result.
6. **E99 is in-sample.** One window had a $61 proxy error (9.7 bp), three times E99; the filter is a 99% band, not
   a guarantee, and the Chainlink feed needs an API key from 30 Nov, so the band cannot be re-measured the same way.

## Model calibration (diagnostic; favoured side at a fixed model time, no prices involved)

With the E99 filter the favoured side at f >= 0.97 lost once in the whole sample at any of the four model times
(tuning, t1-45: 1 of 798); without it there are 19 + 7 losses at t1-5, all inside the basis band. So the filtered
model is right about 99.9% of the time per market, and the market mostly prices those states at 0.98-0.99 already:
the rule only finds a print 2 c cheaper in about 3% of markets.

| model time | period | floor | excl. | markets (share of all) | favoured side won | Wilson 95% | losses |
|---|---|---|---|---|---|---|---|
| t1-45 | tune | 0.97 | off | 805 (0.70) | 0.9988 | [0.9930, 0.9998] | 1 |
| t1-45 | tune | 0.97 | on | 798 (0.69) | 0.9987 | [0.9929, 0.9998] | 1 |
| t1-45 | tune | 0.99 | off | 717 (0.62) | 0.9986 | [0.9921, 0.9998] | 1 |
| t1-45 | tune | 0.99 | on | 715 (0.62) | 0.9986 | [0.9921, 0.9998] | 1 |
| t1-45 | report | 0.97 | off | 409 (0.71) | 1.0000 | [0.9907, 1.0000] | 0 |
| t1-45 | report | 0.97 | on | 406 (0.70) | 1.0000 | [0.9906, 1.0000] | 0 |
| t1-45 | report | 0.99 | off | 383 (0.66) | 1.0000 | [0.9901, 1.0000] | 0 |
| t1-45 | report | 0.99 | on | 382 (0.66) | 1.0000 | [0.9900, 1.0000] | 0 |
| t1-30 | tune | 0.97 | off | 960 (0.83) | 1.0000 | [0.9960, 1.0000] | 0 |
| t1-30 | tune | 0.97 | on | 912 (0.79) | 1.0000 | [0.9958, 1.0000] | 0 |
| t1-30 | tune | 0.99 | off | 912 (0.79) | 1.0000 | [0.9958, 1.0000] | 0 |
| t1-30 | tune | 0.99 | on | 883 (0.77) | 1.0000 | [0.9957, 1.0000] | 0 |
| t1-30 | report | 0.97 | off | 486 (0.84) | 0.9979 | [0.9884, 0.9996] | 1 |
| t1-30 | report | 0.97 | on | 452 (0.78) | 1.0000 | [0.9916, 1.0000] | 0 |
| t1-30 | report | 0.99 | off | 462 (0.80) | 1.0000 | [0.9918, 1.0000] | 0 |
| t1-30 | report | 0.99 | on | 441 (0.77) | 1.0000 | [0.9914, 1.0000] | 0 |
| t1-15 | tune | 0.97 | off | 1086 (0.94) | 0.9963 | [0.9906, 0.9986] | 4 |
| t1-15 | tune | 0.97 | on | 942 (0.82) | 1.0000 | [0.9959, 1.0000] | 0 |
| t1-15 | tune | 0.99 | off | 1071 (0.93) | 1.0000 | [0.9964, 1.0000] | 0 |
| t1-15 | tune | 0.99 | on | 942 (0.82) | 1.0000 | [0.9959, 1.0000] | 0 |
| t1-15 | report | 0.97 | off | 543 (0.94) | 0.9982 | [0.9896, 0.9997] | 1 |
| t1-15 | report | 0.97 | on | 458 (0.80) | 1.0000 | [0.9917, 1.0000] | 0 |
| t1-15 | report | 0.99 | off | 528 (0.92) | 0.9981 | [0.9894, 0.9997] | 1 |
| t1-15 | report | 0.99 | on | 458 (0.80) | 1.0000 | [0.9917, 1.0000] | 0 |
| t1-5 | tune | 0.97 | off | 1141 (0.99) | 0.9833 | [0.9741, 0.9893] | 19 |
| t1-5 | tune | 0.97 | on | 944 (0.82) | 1.0000 | [0.9959, 1.0000] | 0 |
| t1-5 | tune | 0.99 | off | 1139 (0.99) | 0.9851 | [0.9762, 0.9907] | 17 |
| t1-5 | tune | 0.99 | on | 944 (0.82) | 1.0000 | [0.9959, 1.0000] | 0 |
| t1-5 | report | 0.97 | off | 573 (0.99) | 0.9878 | [0.9750, 0.9941] | 7 |
| t1-5 | report | 0.97 | on | 461 (0.80) | 1.0000 | [0.9917, 1.0000] | 0 |
| t1-5 | report | 0.99 | off | 572 (0.99) | 0.9878 | [0.9750, 0.9941] | 7 |
| t1-5 | report | 0.99 | on | 461 (0.80) | 1.0000 | [0.9917, 1.0000] | 0 |

## What would have to be true for the filtered edge to be real

1. A taker who is not co-located (order arrives 0.2-1 s after the Binance second, plus the 50 ms taker delay) still
   finds the ask at <= f - 0.02. The tape cannot show this; an L2 replay can (see ideas).
2. The loss rate of the selected bets stays well under 5% out of sample, including sharp reversals with 25-60 s
   left (one seen at D = 2) and basis events beyond E99 (one $61 window in six days).
3. The frequency does not keep falling (19 -> 4 markets per day inside the sample).
4. Fees, the TWAP rule and access to prices stay as they are (four rule changes in four months).
5. For a few-hundred-dollar account: each bet risks the whole stake of that market (buy at 0.95 to win 0.05), so a
   $300 account doing 300 shares per market loses nearly everything on one bad market. Sensible sizing (say 50
   shares, about $47 at risk) scales the tape-fill estimate to roughly $5-15/day.

## What I could not check

- Whether the asks existed at the moment the signal appeared and for how long (needs the L2 book, not the tape).
- Queue position / who gets the fill among several takers in the same block.
- Sub-second Binance moves (1 s closes only) and real feed latency from a VPS.
- Anything outside six days of one regime; the reporting period has only 2 days and 5-11 traded markets.
- The Chainlink stream itself: the basis is measured only through the two official numbers per window.

## Deviations from the protocol

None in the rules. Additions made after seeing the protocol results, all diagnostics without new trading variants:
the TWAP shift scan, the anatomy of filtered trades (`out/diag.txt`), the real-match-time check
(`out/ws_timing.txt`), binomial bounds (`out/extra.txt`). Total trading runs: **42**.

## Toolkit notes (pmlab was not edited)

- `updown.BLOCK_LAG = 3`: measured lag is 2.09 s median (1.06-3.33 s, 1st-99th pct) on 21-22 Nov; `block - 3` is
  about 0.9 s before the real match. Conservative for look-ahead, but it labels prints a second early.
- `px.twap(t, 60)` / `fair.fair_up`: the official average lines up with Binance closes ended 4-5 s earlier (table
  above). Using the shift would cut the proxy error by half and the proxy-miss rate from 1.9% to 0.7%.
- `updown.load_market`: `volume` is None in 153 of 1,728 cached markets and is in shares, not dollars;
  three markets have a wrong tiny volume (2, 12, 46); one market has no `final_price`.
- NOTES.md says the proxy calls 96.5% of outcomes; on 21-26 Nov it is 98.1% (99.3% with the -5 s shift).
- Block times of fills sit on a 1.5 s grid (offsets ..., -5, -4, -2, -1, +1, +2, +4 from t1).

## Ideas (not run)

1. Rebuild the lock-in model on the shifted clock (average ends ~5 s before t1 in Binance time, band ~$10) and
   re-test on fresh days, with the rule and band fixed on 21-26 Nov. At t1-10 on that clock five sixths of the
   average is fixed.
2. L2 replay on 21-22 Nov (`ithiria894` books, ms exchange time) with Binance aggTrades: at the first moment the
   filtered condition is true, what ask is in the book, how much, and for how many ms; then add 200/500/1000 ms.
   This is the decisive test of fills for this study.
3. Require the signal to be still true on the freshest Binance second (drops the adverse-selection half) and to have
   persisted for a few seconds; measure how many markets remain and whether any lose, on new data only.
4. Maker version: rest a bid on the favoured side at f - 0.02 when the filtered condition holds (no fee); test
   whether SELL prints trade through it and who they are (a seller who knows more is the risk).
5. Same measurement on BTC 15m (same 0.05 fee, 60 s average is a smaller part of the window) and on ETH 5m (fee
   0.01, thinner): where is the stale-quote burst slowest to be taken?
6. Track the daily count of filtered opportunities over the next weeks: if it keeps falling from 19 to 4 per day
   the question answers itself.
7. A cheap live paper check from the VPS: poll Binance and `POST /books` once a second in the last 70 s and log
   every time the filtered condition holds with the ask <= f - 0.02, then count how often the ask is still there at
   the next poll.
