# Calibration map: does buying an outcome at the price then shown pay after the taker fee?

Written 2026-11-27 ~18:30 UTC BEFORE any outcome-based number of this study was computed. Before writing it I looked
only at metadata: the gamma listing of two days (Aug 5, Nov 19; family counts, slug and tag patterns, field names) and
whether `prices-history` still returns points for markets of different ages (no prices were compared with outcomes).
Earlier lab results that touch this question (NOTES.md lines on weather calibration, mentions blind buys, BTC 5m late
favourites, resolution bonds) are known from NOTES.md; the `resolution_bonds` tables were not opened. After this file
is saved the rules below are frozen; later ideas go to "Ideas, not tested" in results.md.

## Question

Across resolved Polymarket markets of the last ~3 months, by market family, entry price bucket and time before the
scheduled end: does buying an outcome at the price then shown, held to resolution, return more than the taker fee
plus a fixed slippage? Is there a systematic favourite / long-shot bias in short-dated repeating families (crypto
up/down 15m/1h/4h, daily crypto strike ladders, daily temperature, sports before the start, mentions, post counters)?
Deliver the table and a shortlist of at most five cells worth a live micro-test (or "nothing").

## Data availability (checked, metadata only) and the resulting period

`prices-history` returned nothing for markets ending 2026-08-05 (any bucket), only 30-minute points for 2026-09-01 and
2026-09-25, and 5-minute points for 2026-10-15 and 2026-11-10. So four months is not possible; the period is
**anchor time in [2026-08-29 00:00, 2026-11-27 00:00) UTC** (90 days). Markets with anchor >= 2026-09-28 00:00 are
fetched at 300-second buckets, older ones at 1800-second buckets.

## Universe

1. Listing: `pmlab.gamma.iter_markets(closed='true', end_date_min=D 00:00:00Z, end_date_max=D 23:59:59Z,
   volume_num_min=500, include_tag='true')` for every day D from 2026-08-25 to 2026-12-03 (wider than the period
   because the anchor of sports markets is the game start, not endDate). Rows slimmed and stored in
   `data/gaps_calibration_map/listing/`.
2. Keep binary markets (2 outcomes, 2 token ids) whose `outcomePrices` is a resolved vector: (1,0), (0,1) or
   (0.5,0.5). Anything else (unresolved, other values) is dropped and counted.
3. Excluded families: `*-updown-5m` (a 5-minute window has no usable horizon at 5-minute price buckets; the lab
   studied it on tapes in btc5m_lockin / btc5m_tails / crypto_lowfee).

## Families (first match wins; slug = market slug, tags = gamma tag slugs)

| family | rule | anchor (the scheduled end the horizons count back from) | fee rate |
|---|---|---|---|
| updown-15m | slug `<asset>-updown-15m-<epoch>`, asset not xau/wti/other commodity | endDate | 0.05 if asset btc, else 0.01 |
| updown-1h | slug `*-updown-1h-*` (crypto) | endDate | 0.01 |
| updown-4h | slug `*-updown-4h-*` (crypto) | endDate | 0.01 |
| crypto-hit | `pmlab.gamma.family`=crypto and (tag `hit-price` or slug contains `reach`/`dip`/`hit`) | endDate | 0.01 |
| crypto-level | other `family`=crypto (daily/weekly above, between, less than; up/down daily) | endDate | 0.01 |
| weather-temp | slug starts `highest-temperature-in` or `lowest-temperature-in` | eventStartTime + 24 h if present, else endDate | 0.01 |
| weather-other | other `family`=weather | endDate | 0.01 |
| mentions | any tag containing `mention`, or whole-word say/said/says/mention in slug | endDate | 0.01 |
| counters | slug contains `tweets` or `-posts-` or `truth-social-post` | endDate | 0.01 |
| esports | tag `esports` or a tag of the esports titles (counter-strike-2, dota-2, valorant, league-of-legends) | gameStartTime if present, else endDate | 0.05 |
| sports-ml | `family`=sports, sportsMarketType moneyline or empty | gameStartTime if present, else endDate | 0.05 |
| sports-line | `family`=sports, sportsMarketType spreads / totals | gameStartTime if present, else endDate | 0.05 |
| sports-other | other `family`=sports | gameStartTime if present, else endDate | 0.05 |
| finance | `family`=finance, including xau/wti up/down | endDate | 0.05 |
| economics | `family`=economics | endDate | 0.01 |
| politics | `family`=politics | endDate | 0 if tag `geopolitics`; 0.05 if any tag contains `election`; else 0.01 |
| other | everything else (culture, tech, other) | endDate | 0.01 if family culture, else 0.05 |

Fee rates are today's (since 2026-11-20) from NOTES.md / `pmlab.fees.CURRENT`, applied to the whole period: the
question is what the owner would pay now. Rebates 0.

## Sample (fits the 110-minute budget)

Per family, markets whose anchor is in the period are sampled with seed 20261127, stratified by anchor day (equal
quota per day, random inside the day, a day with fewer markets gives up its remainder to nobody). Caps:
updown-15m 1,400; updown-1h 900; updown-4h 600; crypto-level 1,000; crypto-hit 400; weather-temp 1,400;
weather-other 200; mentions 700; counters 400; esports 400; sports-ml 1,200; sports-line 800; sports-other 300;
finance 500; economics 300; politics 500; other 400 (total cap 11,300). The sampled markets are fetched in one random
order (seed) across families. **Download stop rule:** whatever is fetched by 19:35 UTC is analysed; because the order
is random the fetched part is a random subsample; the shortfall per family is reported.

One `prices-history` request per market for the first token (outcome index 0), span [anchor - 25 h, anchor]; the
second outcome's price is 1 - p (mirror books). Missing/failed requests are counted.

## Observation, entry and outcome

- Horizons H: 24 h, 6 h, 1 h, 10 min before the anchor. The 10-min horizon only for markets fetched at 300 s.
- No look-ahead from the bucket convention: the price used at observation time o = anchor - H is the last point with
  timestamp <= o - bucket (bucket = 300 or 1800 s), and it must be no older than o - 3 * bucket; otherwise no
  observation. The observation also needs o < closedTime (market still trading) and o >= market startDate.
- Favourite = the outcome with the higher price p (>= 0.5; tie -> outcome 0). Observations with p > 0.995 are
  dropped (nothing to buy). Buckets on p: [0.50,0.60) [0.60,0.70) [0.70,0.80) [0.80,0.90) [0.90,0.95) [0.95,0.98)
  [0.98,0.995]. Long-shot = the other outcome at 1 - p.
- Screening entry price for a side with shown price q: e = q + s, s = 0.01 if 0.10 <= q <= 0.90, else 0.005. Fee
  per share = rate * e * (1 - e). Payoff W = final price of that outcome (1, 0, or 0.5).
- Net per share: fav = W_fav - e_fav - fee(e_fav); long = W_long - e_long - fee(e_long). Also reported (descriptive):
  gross edge W_fav - p (before slippage and fee).
- `prices-history` is a mid-like snapshot, not a quote (NOTES: only 23% of "mid + 1c" entries had a print at that
  price in crypto ladders). The screen is therefore only a screen; the tape stage decides buyability.

## Statistics, split, clustering

- Unit / cluster: the gamma event (`events[0].slug`; each up/down market is its own event). Net per share per cell =
  `pmlab.stats.ratio_cluster` over events (sum of net / number of markets, by event), with t.
- Split by anchor time: EARLY = anchor < 2026-10-28 00:00 UTC (60 days, used for selection), LATE = anchor >=
  2026-10-28 (30 days, reported separately, used for confirmation).
- Cells = family x horizon x bucket x side (fav / long). Every cell computed counts as a variant; the count is reported.

## Decision rule (fixed now)

A cell is a **candidate** if in EARLY: >= 100 events, net > 0, t >= 2.0 (same side).
A candidate is **confirmed by price** if in LATE: >= 200 events, net > 0, t >= 3.0 clustered by event, and t >= 2.0
clustered by anchor day (robustness against same-day correlation, e.g. one crypto move or one sports slate).
At most five confirmed cells (highest LATE t first) go to the **tape stage**:

- Up to 150 random LATE markets of the cell (seed). Whole-market tape via `pmlab.dataapi.iter_trades(condition=)`,
  read newest-first until rows are older than o - 600 s (at most 40 pages). Match time = block time - 3 s.
- A print shows our outcome was buyable at price x if it is a taker BUY of our outcome at x, or a taker SELL of the
  other outcome at y (resting bid on the other outcome = ask on ours at 1 - y). Window [o, o + W],
  W = min(30 min, H / 6). Qualifying prints: x <= e (the screening entry price). Fill = prints in time order at their
  own prices, each for no more than its shown size, until 5 USD (cap 20 USD). A market is "filled" if >= 5 USD.
- Net per share on filled markets = W - vwap - fee(vwap); t by event. **Tape-confirmed** if fill rate >= 50% of the
  markets tried, net > 0 and t >= 2.0. Only tape-confirmed cells go to "Live micro-test".
- If no cell is confirmed by price, there is no tape stage and results.md says nothing here deserves a live test.
- Resting (maker) entries are not tested here (no queue data); any maker idea goes to "Ideas, not tested".

## Descriptive extras (no decisions are taken from them)

- Calibration by family pooled over buckets and horizons (win rate vs mean price), early and late.
- Share of sampled markets whose anchor falls on Saturday/Sunday (UTC) per family, and for confirmed cells the net
  split weekday / weekend (the owner asked what works on weekends).
- Opportunities per day = markets per day in the full listing of that family (not just the sample) times the share
  of sampled markets that land in the cell.
