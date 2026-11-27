# Pair accumulation on crypto up/down (resting bids on both outcomes) — results

## Verdict: NO EDGE. Nothing here deserves a live micro-test.

- Resting one buy order on EACH outcome at the same fixed price (0.45/0.45, 0.40/0.40, 0.30/0.30, 0.05/0.05) from
  the start of the window to its end loses money in **all 48 cells** (12 series x 4 levels) over the six days under
  the conservative fill rule, and in 46 of 48 under the optimistic one (the other two, BTC 15m and BTC 1h at 0.30,
  are +0.10 and +0.21 $ per window, t +0.2). No cell passes the decision rule of `protocol.md` 9, and no cell
  qualifies for the "depends on queue position" route.
- Pooled over all 12 series, 7,200 markets, $10 per leg, conservative fills: **-1.31 $ per window at 0.45**
  (95% CI -1.51 to -1.10, t -12.3), -1.33 at 0.40 (t -10.6), -1.46 at 0.30 (t -8.2), -3.74 at 0.05 (t -8.1).
  Early part (21-24 Nov, 4,800 markets) and late part (25-26 Nov, 2,400) are both negative at every level; all six
  days are negative at every level, the weekend included (Sat 21 and Sun 22 Nov were the worst days at 0.45).
- Completed pairs are frequent (35% of windows at 0.45, 44% at 0.40) and do pay 1 - 2L, but the windows where only
  one leg fills lose more than the pairs earn. The cause is adverse selection on the fill: a bid at 0.45 is hit by a
  print at about 0.41-0.43 and the market then trades at about 0.39-0.42, i.e. the trader is filled at a price
  3-4 cents above what the outcome is worth at that moment. Prices themselves are calibrated (prints at 0.45-0.55
  won 47-51%), so this is not a mispricing the maker can harvest; it is the toll a stale resting bid pays.
- The longer BTC 5m history (Sep 1 - Nov 20, every 4th window, 5,825 markets) is negative too: -0.79 / -1.10 / -1.30
  $ per window at 0.45 / 0.40 / 0.30 (t -7.3 / -9.9 / -8.9), every month negative.
- For a 200 EUR account: capacity **$0 a day**. The least bad series is BTC 15m (0.45: -0.25 $ per window, CI -0.83 to
  +0.33, 576 markets) and BTC 1h (0.30: -0.12, CI -2.0 to +1.8, 144 markets): zero at best, never positive with
  any significance.

Answer to the owner's broader question, as far as this study reaches: crypto up/down markets run 24/7, weekends
included (Nov 21-22 are in the sample), so the weekend is not the problem; this particular structure (patient bids on
both sides, no outside information) simply does not pay on any day.

## Question

Two-outcome short-dated crypto markets (Up/Down on BTC, ETH, SOL, XRP over 5 minutes, 15 minutes and 1 hour). A
patient maker rests one bid on each outcome at the same fixed price L when the window opens and leaves both until the
window ends. If both fill, the pair costs 2L < 1 and pays exactly 1 whichever side wins; if only one fills, it is a
directional position bought at L. How often do both legs fill inside one window, what do single legs return, what is
the net per window after fees, and do the published claims of the catalog family `pair-accumulation`
(`catalog/candidates.json`) survive? The one-cent TAKER side of BTC 5m is not repeated here: it is in
`studies/gaps/btc5m_tails/results.md` (no edge; tails are overpriced). The maker tail level 0.05 here is a different
order type and is reported as one of the four levels.

## Data

- Period: every window starting 2026-11-21 00:00 to 2026-11-26 23:59 UTC (after the 2026-11-20 fee and rebate
  change). Early part 21-24 Nov, late part 25-26 Nov.
- Markets (all found, resolved and with a tape; none excluded): BTC 5m 1,728, ETH 5m 1,728, SOL 5m 432 and XRP 5m 432
  (every 4th window, fixed in the protocol because their volume is near zero), BTC/ETH/SOL/XRP 15m 576 each,
  BTC/ETH/SOL/XRP 1h 144 each: **7,200 markets** (the protocol's "7,104" was an arithmetic slip; the list of series
  and grids is as written). 4.29M tape rows, 3.85M of them inside the windows.
- Secondary history: BTC 5m, every 4th window, 2026-09-01 .. 11-20, 5,825 markets (the cached grid of `btc5m_tails`).
- Sources (read 2026-11-27): official outcome and metadata from gamma events (`pmlab.updown.load_market`; for 1h the
  same code in `common.py`, slug `<asset>-updown-1h-<t0>`); whole-market tapes from Data API v2 `trades?condition=`
  (`pmlab.updown.tape`). 5m/15m BTC/ETH/SOL/XRP tapes were already cached by earlier studies; SOL/XRP 5m and all 1h
  tapes (1,440 markets) were downloaded for this study (`fetch.py`, 3 threads, about 4 minutes).
- Sanity (`out/tables.md`, "Sanity"): tape shares / gamma volume median 1.0000 in every series; every market has
  prints inside its window; share-weighted win rate of buyable prints at 0.45-0.55 inside windows 0.466-0.520 in 11
  series (BTC 5m 0.498 on 5.95M shares) and 0.606 in XRP 1h (9.8K shares, 144 markets: small).

## What was run (everything counted)

- Trading rule (protocol 3-4): at t0 a GTC buy of Up at L and a GTC buy of Down at L, size $10 / L shares per leg,
  cancelled at the window end, held to settlement; no re-quote, no taker top-up. Maker fee 0, rebates 0, rewards 0.
  A leg is skipped when its ask was already at or below L in the 30 s before t0 (it would have been a taker).
- Variants: 4 levels x 12 series = **48 cells**, each under 2 fill scenarios = **96 cell-scenarios**, each in
  early / late / whole period; plus the BTC 5m history: 4 levels x 2 scenarios = 8. Nothing was tuned.
- Fill scenarios: conservative (primary) = filled at L when a print strictly through L (below L on the sellable side)
  occurs inside the window, match time = block time - 3 s; optimistic = filled at L at the first print AT or below L
  (full queue share).
- Post-hoc and descriptive only (written after seeing the cells, not rules): `extra.py` (loss by time of fill, by
  day, pair vs single contributions, through-size) and `fillcheck.py` (price of the filling print and of the prints
  5-15 s later, 1,431 sampled legs).
- Code: `common.py`, `fetch.py`, `build.py`, `analyze.py`, `extra.py`, `fillcheck.py`. Outputs: `out/tables.md`
  (every cell, sanity, history, decision table), `out/cells.csv`, `out/extra.md`, `out/fillcheck.txt`. Leg-level
  tables: `data/gaps_pair_accumulation/legs_main.parquet`, `legs_hist.parquet`, `markets_*.parquet`.

## Headline numbers (net $ per window at $10 per leg, 95% CI clustered by UTC hour)

Pooled over the 12 series (clusters = clock hours, because the four coins move together):

| L | scenario | early (4,800 mkts) | late (2,400 mkts) | all (7,200) | t (all) | P(0 / 1 / 2 legs) | net per filled leg |
|---|---|---|---|---|---|---|---|
| 0.45 | conservative | -1.46 (-1.73, -1.19) | -1.00 (-1.30, -0.70) | -1.31 (-1.51, -1.10) | -12.3 | 0.15 / 0.50 / 0.35 | -1.09 $ (-10.9%) |
| 0.40 | conservative | -1.40 (-1.70, -1.09) | -1.19 (-1.59, -0.79) | -1.33 (-1.57, -1.08) | -10.6 | 0.09 / 0.48 / 0.44 | -0.98 $ |
| 0.30 | conservative | -1.59 (-2.02, -1.15) | -1.20 (-1.75, -0.65) | -1.46 (-1.80, -1.11) | -8.2 | 0.02 / 0.63 / 0.35 | -1.09 $ |
| 0.05 | conservative | -3.48 (-4.64, -2.32) | -4.26 (-5.71, -2.82) | -3.74 (-4.65, -2.83) | -8.1 | 0.01 / 0.96 / 0.03 | -3.67 $ |
| 0.45 | optimistic | -1.30 (-1.57, -1.02) | -0.83 (-1.12, -0.54) | -1.14 (-1.35, -0.93) | -10.7 | 0.14 / 0.50 / 0.36 | -0.94 $ |
| 0.40 | optimistic | -1.17 (-1.48, -0.86) | -0.97 (-1.38, -0.56) | -1.11 (-1.35, -0.86) | -8.8 | 0.09 / 0.46 / 0.45 | -0.81 $ |
| 0.30 | optimistic | -1.18 (-1.63, -0.72) | -0.82 (-1.40, -0.24) | -1.06 (-1.42, -0.70) | -5.8 | 0.02 / 0.61 / 0.37 | -0.78 $ |
| 0.05 | optimistic | -2.35 (-3.63, -1.08) | -2.50 (-4.20, -0.80) | -2.40 (-3.42, -1.39) | -4.6 | 0.01 / 0.95 / 0.04 | -2.33 $ |

By series, conservative, whole period (net $ per window, t; all cells in `out/tables.md`):

| series (markets) | 0.45 | 0.40 | 0.30 | 0.05 | P(both legs) at 0.45 / 0.40 |
|---|---|---|---|---|---|
| BTC 5m (1,728) | -0.79 (-4.1) | -1.06 (-5.6) | -0.90 (-3.4) | -4.39 (-5.9) | 11% / 33% |
| ETH 5m (1,728) | -0.90 (-4.4) | -0.87 (-4.7) | -1.26 (-4.7) | -3.40 (-4.2) | 29% / 40% |
| SOL 5m (432) | -2.15 (-6.6) | -2.44 (-6.6) | -1.95 (-3.5) | -3.63 (-2.3) | 40% / 43% |
| XRP 5m (432) | -2.07 (-5.8) | -1.77 (-4.4) | -2.15 (-3.9) | -2.87 (-1.6) | 38% / 41% |
| BTC 15m (576) | -0.25 (-0.8) | -0.54 (-1.8) | -0.42 (-0.9) | -3.73 (-2.6) | 44% / 56% |
| ETH 15m (576) | -0.96 (-3.5) | -0.70 (-2.7) | -0.87 (-1.9) | -2.67 (-1.7) | 52% / 59% |
| SOL 15m (576) | -1.78 (-7.0) | -1.65 (-5.1) | -2.11 (-4.3) | -3.84 (-2.9) | 54% / 52% |
| XRP 15m (576) | -2.73 (-10.7) | -2.55 (-8.2) | -2.43 (-5.6) | -2.85 (-2.0) | 51% / 47% |
| BTC 1h (144) | -0.76 (-1.4) | -0.31 (-0.5) | -0.12 (-0.1) | -3.40 (-1.2) | 62% / 65% |
| ETH 1h (144) | -1.87 (-3.8) | -1.98 (-3.2) | -2.38 (-2.6) | -2.08 (-0.7) | 65% / 54% |
| SOL 1h (144) | -2.96 (-5.9) | -2.50 (-4.0) | -3.84 (-4.5) | -7.85 (-5.9) | 58% / 50% |
| XRP 1h (144) | -3.92 (-7.4) | -4.10 (-6.6) | -4.91 (-6.0) | -8.26 (-5.9) | 47% / 38% |

Decision rule (protocol 9): 0 of 48 cells pass conservatively; 0 of 48 pass optimistically. The only cells with a
positive late-part mean are BTC 15m at 0.45 (+0.25, t +0.56, 192 markets) and 0.30 (+0.09), ETH 15m at 0.40/0.30,
and BTC 1h at 0.05 (+1.88, t +0.28, 48 markets); each is negative in the early part and far from t 3.3 overall.

How to read: "net $ per window" is the result of one market with $10 on each leg (22.2 shares at 0.45, 25 at 0.40,
33.3 at 0.30, 200 at 0.05), 0 when nothing fills. Results scale linearly with size: at $5 per leg halve them, at $20
double them.

## Where the loss comes from (post-hoc, descriptive)

- **Pairs earn, single legs lose more** (`out/extra.md` 3). 5m at 0.45: pairs in 24% of windows add +0.53 $ per
  window, single-leg windows (55%) take -1.63; 15m: +1.12 vs -2.55; 1h: +1.29 vs -3.67. At 0.30 pairs add +4.7 $ but
  single legs -6.0 to -6.9. With both bids far below 0.5, a single leg is almost always the side that collapsed, so
  single legs rarely win (at 0.30: 21 of 4,513 single-leg windows won); single legs at 0.45 won more often only
  because their twin leg was skipped by the placement check.
- **The fill itself is the problem.** Most fills come in the first half of the window (0.45: 4,009 of 4,427 5m
  fills), and those legs won 40.0% (5m), 40.9% (15m), 36.3% (1h) against 45% paid: -5.0, -4.1, -8.7 c a share (t -7.4,
  -5.7, -6.1). In the sampled legs the filling print was at 0.413 / 0.423 / 0.404 / 0.427 on average (BTC 5m / BTC 15m
  / ETH 15m / BTC 1h) and the outcome traded at 0.405 / 0.417 / 0.389 / 0.405 five to fifteen seconds later
  (`out/fillcheck.txt`, 1,431 legs). The book jumps through a resting bid when the coin moves; the bid is filled
  exactly when it is worth less than it pays.
- **The tail level is worse.** At 0.05 the losing side passes through 5 c in 95% of windows (usually in the last
  quarter of the window) and pays out in 10 of 6,888 single-leg windows: -3.7 $ per window. This agrees with
  `btc5m_tails` (cheap tails are overpriced, here bought even dearer, at the bid above the trade).

## Opportunities, size, capacity, reaction time

- Opportunities: 288 5m windows, 96 15m windows and 24 1h windows a day per coin; at 0.45 about 1,440 legs a day
  are filled across the 12 series (BTC 5m 236, ETH 5m 319, each 15m series about 130-145, each 1h series 35-40).
  Plenty of repetitions, all with a negative expectation.
- Net per trade at 5-20 USD: pooled -0.85 to -1.20 $ per filled $10 leg (about -9% to -12% of the leg); at $5 about
  -0.5 $, at $20 about -2 $. Through-size is not the constraint: median 31 shares (p25 10) printed through 0.45 within
  10 s of the first through print, i.e. about $14.
- Capacity for a 200 EUR account: **$0 a day** (the sign is negative everywhere; size only scales the loss).
- Reaction time: none is needed to place these orders (they are placed at the window start and left alone). The
  losses come exactly from NOT reacting: avoiding the toxic fills would mean pulling the bid within about a second of
  a Binance move, which is the sub-second race the lab already ruled out (`NOTES.md`: book absorbs a Binance move in
  0.5-2 s; resting quotes 1-2 s stale lose 2-8%).

## Published claims (catalog family `pair-accumulation`)

- C1, gude Spec A ("the one-sided residual is uninformed, hit rate about 49%"): not supported for fixed-level bids. A
  residual leg is the side that fell through the bid and stayed down; at 0.40 single legs won 355 of 3,419, at 0.30
  21 of 4,513. The spec's own bids follow the book, so its residual is a different object, but the economics are the
  same: the residual is where the money is lost.
- C2, gude Spec A / RetroValix ("pairs under $1 at maker prices"): pairs under $1 are indeed common (35-44% of
  windows at 0.45-0.40, up to 65% in BTC/ETH 1h), but the pair edge is an outcome conditional on the path; per window,
  including the windows where the pair does not complete, the structure loses 1.1-1.5 $ per $10 leg pair.
- C3, the lab's earlier finding (x-MoneyForWhiskas: leftover one-sided inventory lost in 3 of 4 samples): confirmed
  and generalised: single-leg windows are negative in every series and level (all 48 cells).
- C4, gabagool-style complete-set maker on 15m/1h: our fixed far-from-mid bids lose in every 15m and 1h series; BTC
  15m and BTC 1h are the closest to zero. The best-bid, re-quoting version of that spec needs queue position and L2
  data and is not tested here.

## Attacks on the result

- Fill rule too harsh? The optimistic scenario (filled at the touch, full queue share) is negative in 46 of 48
  cells (pooled -1.06 to -2.40 $ per window, t -4.6 to -10.7); the two non-negative cells (BTC 15m and BTC 1h at
  0.30, +0.10 and +0.21 $, late-part t +0.65 and +0.12) are noise. Queue priority does not rescue it.
- Settlement or look-ahead error? Outcomes are the official gamma results; the rule uses only t0, t1 and prints after
  placement; tapes are complete (shares = gamma volume in every series). Prints at 0.45-0.55 are calibrated.
- One bad stretch? Every day is negative at every level (`out/extra.md` 2); the BTC 5m history from September is
  negative in every month at 0.45, 0.40 and 0.30 (at 0.05 September is +0.21, October -0.95, November -2.03; the
  optimistic 0.05 history is +0.94, t +1.6, with only 4 single legs won in 5,453: lottery noise, not a passing cell).
- Small samples: the 1h cells have 144 markets (48 in the late part); none of them is close to the pass line anyway.
- Placement skips: at 0.45, 3,486 of 14,400 legs were skipped because the ask was already at or below 0.45 just
  before t0 (24%, mostly 5m). This changes how many windows have two legs, not the per-leg loss of -4 to -9 c a share
  on legs that did fill.

## Live micro-test

Nothing in this study deserves a live micro-test: every level loses in every series under the conservative fill rule
(46 of 48 cells under the optimistic one, the other two at t +0.2), pooled in both halves of the period and on every
day. A live test would only confirm a loss of about 10% of every filled leg.

## Limitations

- Six days of data (21-26 Nov) for the main universe; only BTC 5m has a longer history (Sep 1 - Nov 20, 1 window in
  4). SOL and XRP 5m are a 1-in-4 grid (432 markets each).
- Tape fills cannot show queue position; the two scenarios bracket it (strictly through vs touch). Prints are taker
  orders aggregated to a VWAP, so a "through" print may hide partial fills at L (this favours the strategy, if
  anything, in the optimistic scenario).
- Only one order per leg per window at fixed levels; dynamic quoting (best bid, re-quote, cancel on a Binance move)
  and liquidity rewards (none credited) are not in scope.
- `audit.md` (independent check) does not exist yet; per AGENTS.md the result is not accepted until it does.

## Ideas, not tested

1. Cancel the second leg (or both) after the first fill, or cancel all bids in the last N% of the window: the
   descriptive split shows the loss is mostly in early fills, so this alone is unlikely to help; needs its own
   protocol.
2. Cancel-on-move: pull both bids when Binance moves by X bp in a second. This is the sub-second race (150 ms taker
   delay, book absorbs moves in 0.5-2 s); testable only on recorded L2 + Binance data (HF `Fahri-5/updown-5m-polymarket-raw`,
   `ithiria894`).
3. In 1h markets, legs filled in the 50-80% part of the window at 0.45 were +7.2 c a share (92 legs, t +1.2,
   post-hoc): a separate pre-registered test on more 1h windows (they are cheap to download) if anyone wants it.
4. Follow 0x885278f0…c569 (pure maker on BTC/ETH 15m, +$733 on $88K in 22-27 Nov, t 0.47) for 30+ days: is there a
   maker style on 15m that does not lose? Our fixed-level version loses least on BTC 15m.
5. L2 replay of best-bid quoting (the gabagool spec) with a queue model.
