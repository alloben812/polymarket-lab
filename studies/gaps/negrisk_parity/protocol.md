# Structural (parity / neg-risk / ladder) arbitrage for a small account — protocol

Written 2026-11-27 18:25 UTC, before any outcome-based number was computed. Catalog family `negrisk-arb`.
Inspected before writing (formats only, no outcome statistic): one hour of the PendulumFlow V3.1 archive
(2026-11-25T14: politics and weather lean files, `opening_state`, `x_market_index`, manifest), the
`data/rec_rest` file layout, one gamma `/events` page (field names). Frozen after saving; new ideas go to
"Ideas, not tested" in `results.md`.

## Question

Does Polymarket show price-identity violations that a small account (5-20 USD per trade, about 200 EUR in
total, a program on a Mac in Serbia that reacts in a few seconds, no rebates) can take after taker fees:
(a) binary parity (best ask YES + best ask NO < 1, or bids > 1), (b) neg-risk complete sets (sum of best
YES asks over all outcomes < 1, or sum of best YES bids > 1, taken as a basket of NO and converted), (c)
ladders that violate monotonicity (strike ladders "above K", date ladders "by date D")? How often per day,
how large, how long in seconds, and does the gap last at least 5 s?

## Data and sample (fixed now)

1. Order books: HF `chitoyuuri/polymarket-l2-v3-1-archive` (PendulumFlow V3.1, CC BY-NC, research use only),
   lean category files + `opening_state` (book of every asset at the hour start). Sample hours: 2026-11-21 ..
   2026-11-26, hours 02, 06, 10, 14, 18, 22 UTC = 36 hours (6 of every 24, spread over the day). All after the
   2026-11-20 fee change. Only the files that the hour's `x_market_index` lists for universe markets are
   downloaded; raw files are deleted after extraction. If downloads do not fit the budget, hours are dropped
   from the END of the list in the order 22, 18, 02 (each day), and that is said under Limitations.
2. Event universe (gamma, read 2026-11-27): (i) the 500 open events with the highest `volume24hr`; (ii) the 500
   events closed with `end_date` in [2026-11-21 00:00, 2026-11-27 12:00) with the highest `volume`; (iii) all
   closed events in that end-date range with tag `weather`; (iv) all events (open or closed in the range) with
   tag `multi-strikes`. Union, deduplicated by event id.
   - Family B (neg-risk): events with `negRisk = true` and at least 2 markets.
   - Family C1 (strike ladder): `multi-strikes` events whose markets are "above K" questions (K parsed from the
     question/`groupItemTitle`); P(above K) must not increase in K.
   - Family C2 (date ladder): non-negRisk events with >= 3 markets whose every question contains " by " and whose
     every `groupItemTitle` parses as a date; P(by D) must not decrease in D.
   - Family A (binary parity): every market of the universe where the archive has rows for BOTH tokens at the
     same moment (mirror exceptions), plus all REST snapshots in `data/rec_rest` (BTC 5m, Up and Down books
     fetched separately).
3. `prices-history` is NOT used for any headline (mid snapshots are not tradable, NOTES 2026-11-27). It is used
   only as a fallback coarse screen if the archive cannot be read.

## Book reconstruction

Per market, one YES book. Rows of the NO token are mirrored (price -> 1 - price, bid <-> ask, same size); the
archive drops exact mirror twins (`mirror_dropped`), so either token's rows update the same YES book. Start from
`opening_state`, apply `book` rows as full replacement of that token's side(s), `price_change` rows as "level
price now has size" (0 = remove). Time = receive time = `timestamp + recv_lag_ms` (what a WebSocket listener
sees). A market with `resolved = true` in `opening_state`, or a gamma `closedTime` before the hour start, is
dropped from its event for that hour (for family B the remaining outcomes form the set only if every dropped
market resolved NO; otherwise the event is skipped for the hour).

## Variants (6, all counted)

- A1 binary: YES ask + NO ask < 1, or YES bid + NO bid > 1, taken directly from both tokens' own rows.
- B1 YES basket: complete, non-augmented negRisk events (`negRiskAugmented` not true, no `negRiskOther`
  placeholder market missing a book). Cost per set = sum_i (ask_i + f(ask_i)); payout 1 at resolution. Every
  outcome must have an ask.
- B2 NO basket: every negRisk event (augmented allowed: the NO basket pays at least k-1 whatever wins). Legs =
  outcomes with a YES bid; buy NO_i at 1 - bid_i; k NO convert at once to k-1 USDC. Net per set =
  sum_i bid_i - 1 - sum_i f(1 - bid_i).
- C1 strike ladder: any pair K_lo < K_hi with bid(K_hi) > ask(K_lo): buy YES K_lo, buy NO K_hi (at 1 - bid);
  payout >= 1. Net per set = bid_hi - ask_lo - f(ask_lo) - f(1 - bid_hi).
- C2 date ladder: any pair D1 < D2 with bid(D1) > ask(D2): buy YES D2, NO D1. Same formula.
- (A1 is also run on `data/rec_rest`, counted as the same variant A1 on a second source.)
Fee f(p) = rate * p * (1 - p) per share, rate = gamma `feeSchedule.rate` of that market (reliable after
2026-11-20), else the category rate in `pmlab.fees.CURRENT`. Rebates 0. Gas/conversion cost ignored (stated).

## Fill rule, episodes, reaction

- Taker only, top of book: set size = min over legs of the size shown at the best level. Depth beyond the best
  level is reported as a descriptive extra only.
- Opportunity moment: net per set > 0 with set size >= 5 shares. Episode: a maximal run of consecutive book
  states of one event (one ladder pair for C) with net > 0 and size >= 5; it ends at the first state with net <= 0
  or size < 5, or at the hour end (censored, flagged).
- Duration = receive time of the end state - receive time of the start state.
- Takeable with reaction R: the book state at start + R seconds (the state in force at that moment) still has net
  > 0 and size >= 5; the fill is that state's prices and sizes. R = 5 s is the headline; R = 1, 2, 10 s are
  reported alongside (same variants, not new variants).
- Trade size: sets = min(size at start + R, floor(S / cost per set)) for S = 5 and 20 USD (B2 cost per set =
  sum_i (1 - bid_i) + fees, capital back at once after conversion; B1/C cost is locked until resolution).
  Minimum order 5 shares per leg (NOTES: unit ambiguous; stated as a limitation).

## Split, unit, clustering

Early = sample hours of 2026-11-21..23 (18 h), late = 2026-11-24..26 (18 h). Nothing is tuned (all thresholds
fixed above); both parts are reported, the verdict uses the late part. Unit = event (ladder event for C);
confidence intervals by bootstrap over events (2,000 resamples). Per-day rates = count in sampled hours x 24 /
number of sampled hours.

## Attacks on any positive result (all run before reporting a positive)

1. Stale book: does the archive's own `best_bid`/`best_ask` field agree with the replayed book at the episode
   start? Episodes where it does not are reported separately and excluded from the headline.
2. Was the price real: share of R = 5 s episodes with at least one trade print (`last_trade_price`) on any leg
   at or through the quoted price during the episode.
3. Leg asymmetry: which leg made the gap (the one that moved last), and whether the gap closed by that leg
   reverting (i.e. a stale quote that a 5-second taker would hit just before it is cancelled).
4. Concentration: share of net from the top event and top 3 events.

## Decision rule

Live micro-test only if, in the LATE part, for some variant: (1) at least 1 takeable (R = 5 s) episode per day
on average, (2) from at least 10 distinct events, (3) mean net per takeable episode at the 20 USD size > 0 with
the 95% bootstrap CI (by event) above 0, (4) attack 1 leaves the result standing and attack 2 shows prints in at
least half of the episodes. Otherwise the verdict is "nothing to test here" for that variant (or
"inconclusive" if (1)-(3) hold but (4) cannot be checked).
