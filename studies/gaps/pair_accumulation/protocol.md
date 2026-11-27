# Pair accumulation on crypto up/down: resting bids on both outcomes — protocol

Written 2026-11-27 18:15 UTC, before any outcome-based statistic of this study was computed. Seen before writing:
the list of cached files (`data/updown_meta`, `data/tape`), the format of one metadata file and of the first two
rows of one tape, gamma metadata of five 1h events (slug format `<asset>-updown-1h-<t0>`, fee 0.01, TWAP-60
settlement, tick 0.001/0.01), and the row counts printed by the download log. No price path, fill or outcome of
this study's universe was tabulated. After this file is saved it is frozen; new ideas go to "Ideas, not tested" in
`results.md`.

## 1. Question

On two-outcome short-dated crypto markets (Up/Down, 5 minutes, 15 minutes and 1 hour; BTC, ETH, SOL, XRP) a patient
maker rests one buy order on EACH outcome at the same fixed price L when the window opens and leaves them until the
window ends. If both fill, the pair costs 2L < 1 and pays exactly 1 (profit 1 - 2L per share, no matter who wins).
If one fills, the trader holds a single leg bought at L. Questions: (a) how often do both legs fill inside one window,
(b) what do single filled legs return, (c) what is the net per window, after fees (makers pay none, rebates are 0),
and (d) do the published claims of the catalog family `pair-accumulation` survive (section 7).

The one-cent TAKER side of BTC 5m is already measured in `studies/gaps/btc5m_tails/results.md` (no edge, tails
overpriced); it is not repeated. The maker tail level here (L = 0.05) is a different order type and is kept as one
of the four levels, reported with a pointer to that study.

## 2. Data (all public, cached under `data/`)

- Universe: every window with start t0 in [2026-11-21 00:00, 2026-11-27 00:00) UTC (6 days, all after the
  2026-11-20 fee and rebate change and after the 1h move to Chainlink TWAP on 11-18):
  - 5m: BTC and ETH every window (1,728 each); SOL and XRP only every 4th window (t0 % 1200 == 0, 432 each),
    fixed in advance because their volume is near zero and downloads must fit the budget;
  - 15m: BTC, ETH, SOL, XRP every window (576 each);
  - 1h: BTC, ETH, SOL, XRP every window (144 each).
  Total planned: 7,104 markets.
- Metadata (official outcome, condition id, volume in shares) from gamma events via `pmlab.updown.load_market`
  (5m/15m) or the same code extended to 1h in `common.py` (cache `data/updown_meta/<asset>/1h/`).
- Whole-market tapes from the Data API v2 (`trades?condition=`) via `pmlab.updown.tape` (cache `data/tape/`).
- Secondary history (BTC 5m only): the every-4th-window grid of `btc5m_tails` from 2026-09-01 to 2026-11-20
  (already cached). Market behaviour then had maker rebates, which do not change our P&L formula (we credit none).
- Exclusions (counted and reported): market missing, unresolved, or without a tape; tape shares inside +-0.5% of
  gamma volume is NOT required (volumes are missing on some markets), but completeness is reported.

## 3. The trading rule and its variants

Per market and per outcome X in {Up, Down}: one GTC limit BUY of X at price L, placed at t0, cancelled at t1 (the
window end). Size S = 10 USD / L shares per leg (22.2 shares at 0.45, 25 at 0.40, 33.3 at 0.30, 200 at 0.05);
results are also given per share. No re-quoting, no taker top-up, no selling, hold to settlement.

Variants (the only ones): L in {0.45, 0.40, 0.30, 0.05}, the same L on both legs, applied to each of the 12 series:
48 cells. Each cell is evaluated under two fill scenarios (below): 96 cell-scenarios. Secondary history: 4 levels x
2 scenarios on BTC 5m Sep 1 - Nov 20 = 8 more. Nothing is tuned.

Placement check: a leg is NOT placeable (skipped and counted) if a print in [t0 - 30 s, t0) shows X buyable at
<= L (its ask was already at or below our price, so the order would have been a taker). Prints are put on the match
clock: match time = block time - 3 s (`pmlab.updown.BLOCK_LAG`).

## 4. Fill rules and P&L

Tape convention (`pmlab.updown.sellable`): a taker SELL of X at p, or a taker BUY of the other outcome at 1 - p,
means a resting bid for X at >= p was hit.

- **Conservative (primary):** the X leg fills at L, in full, at the first print with match time in [t0, t1) whose
  sellable price for X is strictly below L (L - 1e-9). Rationale: a taker order that prints below L has consumed every
  bid at L, including ours wherever it stood in the queue.
- **Optimistic (separate scenario):** the leg fills at L, in full, at the first print in [t0, t1) whose sellable
  price for X is at or below L (L + 1e-9), i.e. "filled at the price with a full queue share".
- P&L per filled leg = S x (1{X won} - L). Maker fee 0, rebates 0, liquidity rewards 0 (not credited even where they
  exist). No taker leg exists in this rule, so no taker fee arises; if any derived number involves a taker trade it
  uses `pmlab.fees` with rate 0.05 (BTC 5m/15m) or 0.01 (the rest).
- Net per window = sum over the two legs (0 when nothing fills). Capital per window = filled legs x 10 USD.

## 5. Time split and clustering

- Early part: t0 in [11-21, 11-25); late part: t0 in [11-25, 11-27). Both are reported separately; nothing is
  tuned on either.
- Within one series the unit is the market (one window). Standard errors of the mean net per window are clustered by
  UTC clock hour of t0 (adjacent windows of one series share the same hour of price action); with 1h markets this
  equals the market.
- Pooled across series (per level): clusters are UTC clock hours (BTC, ETH, SOL and XRP move together).
- 95% intervals = mean +- 1.96 clustered SE. Single-leg win rates get Wilson intervals by market.

## 6. Statistics reported per cell (series x level x scenario x period)

Markets, placeable legs, P(no leg / one leg / both legs filled), net per window in USD at 10 USD a leg (mean,
clustered SE, t, 95% CI), net per filled leg, return on filled capital, single-leg (pair not completed) win rate vs
its break-even L, net of single legs and of completed pairs separately, fills per day, median time from t0 to the
first and the second fill. Capacity per fill (descriptive): shares that printed strictly through L in the 10 s after
the first through print (median); capacity $/day = max(0, net per share) x min(S, that median) x fills per day.

## 7. Published claims to check (catalog/candidates.json, family `pair-accumulation`)

- C1 (gude Spec A, BTC 5m): the one-sided residual is uninformed, hit rate about 49%. -> single-leg win rate.
- C2 (gude Spec A, RetroValix): pairs below 1 are bought often enough as a maker to give +2.9-3.8% "pair edge";
  posted pair costs 0.946-0.98 (5m), 0.91-0.99 (longer windows). -> P(both) at 0.45/0.40 and its contribution.
- C3 (lab, x-MoneyForWhiskas study): the leftover one-sided inventory lost in 3 of 4 samples. -> sign of single-leg
  net per cell.
- C4 (gabagool-style spec, 15m/1h): passive complete-set bids make money without outside information. -> sign of
  the 15m/1h cells (our fixed levels are a far-from-mid version; the best-bid version is not tested).

## 8. Sanity checks (allowed before the main run, reported)

Prints at 0.45-0.55 inside windows win about 50% (equal-share weights, by series); tape shares vs gamma volume
(median ratio); share of markets with at least one print inside [t0, t1); placement-check skip counts.

## 9. Decision rule (fixed now)

- A cell PASSES if, under the conservative scenario: (i) mean net per window > 0 in the early part and in the late
  part; (ii) late-part t >= 2.0; (iii) whole-period t >= 3.3 (about a 5% family-wise level for 48 cells); (iv) at
  least 20 late-part markets with a filled leg; (v) for BTC 5m cells, the Sep 1 - Nov 20 history is not negative with
  t <= -2. A passing cell gets a live micro-test proposal (rule, order type, size, repetitions, stop rule).
- If no cell passes conservatively, but a cell satisfies (i)-(iv) under the optimistic scenario AND its conservative
  mean is >= 0 in both parts, the result is "depends on queue position" and a live micro-test may be proposed only to
  measure the real fill rate at the touch (its purpose is measurement, not profit; size at the 5-share minimum).
- Otherwise: "nothing to test here".
- A passing result is attacked before it is reported: concentration (result without the best 3 markets), by-day
  signs, fill feasibility (median through-size vs S), look-ahead (none by construction: only t0, t1 and prints
  after placement are used).

## 10. Budget

About 110 minutes in total. Downloads: 5m SOL/XRP grid and 1h series (about 1,500 markets, small tapes), 3 worker
threads under `pmlab.http` throttling. If they do not finish by minute 60 of the study, the missing markets are
dropped by series (whole series, never by outcome) and listed under Limitations.
