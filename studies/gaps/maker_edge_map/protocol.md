# Maker edge map — protocol (frozen 2026-11-27, before any outcome statistic)

## Question

For every market family on Polymarket: what does a passive (maker) fill earn, marked to the final outcome and to the
mid price 30 seconds and 5 minutes after the fill, per share and per dollar, by price bucket and by time to
resolution? Where is a small maker with a reaction time of seconds paid, and where is he picked off (adverse
selection)? What could a ~200 EUR account quoting 5-20 USD clips expect? The owner also asks whether anything works
at the weekend: the map is reported for weekend days (Sat/Sun UTC) separately as a descriptive cut.

Prior: BTC 5m makers in aggregate earned +0.66 c/share on 278 markets of 21-26 Nov (research/2026-11-27-whiskas/tape_A.py).

## Data

- Universe: gamma `/markets/keyset`, `closed=true`, `endDate` in [2026-11-20 00:00, 2026-11-27 00:00) UTC,
  `volumeNum >= 1000` (server filter), `include_tag=true` (`universe.py`, cached under `data/gaps_maker_edge/`).
- Resolved only: `outcomePrices` must be {1,0} or {0.5,0.5}; others are dropped and counted.
- Tapes: data API `trades?condition=` through `pmlab.updown.tape` (cache `data/tape/`, reused where present).
  Cap 20,000 rows per market (newest first, so a capped tape loses its oldest part); capped markets are flagged
  and counted. Tape time = block time; match time = block time - 3 s.

## Families (fixed rule, first match wins)

1. `btc-5m`: slug `btc-updown-5m-*`. 2. `btc-15m`: `btc-updown-15m-*`. 3. `alt-updown-5m15m`: any other asset
`*-updown-5m-*` / `*-updown-15m-*`. 4. `crypto-updown-long`: `pmlab.gamma.family` ends in `updown-1h|4h|...`, or slug
contains `up-or-down` with a crypto tag. 5. `crypto-other`: family `crypto` (levels, hit price, etc.).
6. `mentions`: any tag containing `mention`. 7. `post-counts`: slug or any tag contains `tweet`, or the slug contains
`-posts-` (xtracker post-count markets). 8. `sports`. 9. `weather`. 10. `economics`. 11. `finance`.
12. `politics`. 13. `tech`. 14. `culture`. 15. `other` (all remaining). Families 8-15 use `pmlab.gamma.family`.

## Sample (fixed before any tape is read)

Per family: split by `endDate` into EARLY (Nov 20-23, tuning) and LATE (Nov 24-26, reporting). In each half take up
to 25 markets, chosen by ascending sha1(conditionId) (a fixed pseudo-random order). Max 50 markets per family,
750 in all. If downloads do not fit in the time budget, the narrowing rule is: keep all families and lower the
per-half count to the first K of the same sha1 order for every family equally (K reported). Markets whose tape
download fails are skipped and counted.

## Price normalisation

Token0 = `outcomes[0]`. A print (side, outcome, p) becomes x in token0 price: x = p if outcome is token0 else 1 - p.
Direction: aggressor bought token0 (ask-side print) if (BUY, token0) or (SELL, token1); else bid-side print.
Mid at time T: mean of the last ask-side x and the last bid-side x with match time <= T, each no older than 3,600 s;
undefined otherwise (counted). If T >= resolution time (gamma `closedTime`), the mark is the final payout.

Maker fill = maker BUYS token X at price q (a maker sale of token0 at x is a purchase of token1 at 1 - x).
Markouts per share: final = payout_X - q; m30 = mid_X(t+30) - q; m300 = mid_X(t+300) - q (mid_X = mid0 or 1 - mid0).
Per dollar = sum(markout * shares) / sum(q * shares).

## Variants (three, all reported)

- **V1 aggregate makers (optimistic for a newcomer).** Every print; the maker side is the opposite of the taker at
  the print price (VWAP of the taker order). Shares = print size. This is what the resting book as a whole earned.
- **V2 small touch-maker, conservative.** Decision grid every 10 s (match-time axis) from the first print to the
  resolution time. At each decision time tau the maker sees prints with match time <= tau and sets
  b = last bid-side x, a = last ask-side x, both no older than 900 s, each rounded to the market's tick (`orderPriceMinTickSize`, default 0.01),
  and requires a > b after rounding. He rests a bid for token0
  at b and an offer of token0 at a (= bid for token1 at 1 - a), live for match times in (tau + 2, tau + 10].
  The bid fills only if a bid-side print in that window has x < b strictly (a trade printed through his price);
  the offer only if an ask-side print has x > a strictly. Fill price = his limit; at most one fill per side per
  window; shares = min(clip, print size) with clip = 10 USD / q for capacity numbers (per-share stats do not
  depend on size). No fees (maker), no rewards, no rebates.
- **V2o small touch-maker, optimistic.** Same as V2 but a print AT his price also fills him ("filled at the price
  with a queue share"; queue position is not observable, so this is an upper bound).

## Buckets

Price of the token bought q: [0,0.05), [0.05,0.20), [0.20,0.40), [0.40,0.60), [0.60,0.80), [0.80,0.95), [0.95,1].
Time to resolution at fill (closedTime - fill time): <5 min, 5-60 min, 1-6 h, 6-24 h, 1-3 d, >3 d.

## Statistics

Unit = market. Per-share markouts are ratios of sums with cluster-robust SE by market (`pmlab.stats.ratio_cluster`);
95% CI = +-1.96 SE. Every number is given with markets and fills.

## Decision rule

- Family labels (descriptive, per half): "paid" if V2 final AND V2 m300 have CI above zero; "picked off" if V2 m30
  or m300 has CI below zero and final is not above zero; else "unclear".
- Candidate cells for a live test are chosen on EARLY only: (family x price bucket) with V2 final mean > 0,
  t >= 2, and >= 8 markets with fills. On LATE a candidate PASSES only if V2 final mean > 0 with t >= 2 on
  >= 8 markets with fills AND the expected profit at 10 USD clips is >= 1 USD/day (fills/day x clip x per-dollar
  markout, fills/day from LATE scaled to the whole family's market count in the universe).
- A live micro-test is proposed only for a PASSING cell (if several pass, the one with the most fills/day). If none
  passes, the result is "nothing to test here" for maker quoting, whatever V1 shows.
- V1 and V2o are context; they cannot promote a cell.

## Attacks to run on any positive cell (before it is reported as positive)

Look-ahead (the quote uses only prints before tau); survivorship (resolved markets only: flag that markets resolved
50/50 or disputed are kept); impossible fills (strict-through rule; compare V2 with V2o); concentration (share of
the cell's profit from its best market; result without it); weekend vs weekday.

## Variant count

3 fill variants x 3 markouts, reported for 15 families. Nothing else is run except descriptive counts; anything new
goes to "Ideas, not tested".
