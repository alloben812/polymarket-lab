# Protocol — scheduled economic releases: how fast does Polymarket absorb the number?

Written 2026-11-27 before any tape was downloaded or any outcome was read. Until this file was written only
market metadata (slugs, rules text, volumes, closing times) and the official calendars had been looked at.
After this point the rules do not change; anything thought of later goes under "ideas" in results.md.

## 1. Protocol as given by the lab lead

Question. For markets decided by a scheduled data release the truth appears at a known second. How long do
stale prices survive, how much money trades at them, and what could a taker have made acting at +5 s, +30 s,
+2 min or +10 min? The fee rate for economics markets is 0.01.

Events. US releases and decisions between 2026-09-01 and 2026-11-26: CPI, PPI, employment report (payrolls,
unemployment rate), GDP, PCE, retail sales, FOMC rate decisions, weekly jobless claims; plus any other
scheduled releases with liquid Polymarket markets (other central banks, inflation in other countries). Build
the calendar from official sources (bls.gov, bea.gov, federalreserve.gov; note postponements) and record the
exact scheduled time in UTC. Confirm each release time against the market itself: the first large price move
should fall within a minute of it; if it does not, investigate before using the event.

Markets. Polymarket markets that resolve on each release, found through the gamma API; read the rules to map
the published number to the winning outcome (many are multi-bucket events: one market per bucket). Keep
markets with volumeNum >= 5,000. Verify the winner with pmlab.dataapi.resolutions.

Data. Whole-market tape per market: pmlab.dataapi.iter_trades(condition=...) (taker side, block time = match
time + about 3 s). Every print is converted to "what could be bought": a taker BUY of outcome X at p means X
was offered at p; a taker SELL of X at p means the opposite outcome was offered at 1 - p.

Measurements per (event, market):
- E1 last traded price of the eventual winner before the release;
- E2 time from the release second to the first print of the winner at >= 0.90, >= 0.95 and >= 0.99;
- E3 dollars that changed hands after the release at prices more than 5 cents short of the outcome (winner
  bought below 0.95 or loser sold above 0.05), split into first 5 s, 5-30 s, 30 s-2 min, 2-10 min, later; and
  which wallets took them (count, share of the top three);
- E4 a taker who starts at release + d (d = 5 s, 30 s, 120 s, 600 s; match times, i.e. block time minus 3 s)
  and buys the winner at every later print priced <= 0.97, up to the printed size and at most 500 dollars per
  market: shares, average price, net profit after the 0.01 fee. This uses the outcome, which a real trader
  knows from the published number; flag events where mapping the number to the outcome needed judgement or
  arrived later.

Aggregate E2-E4 by release type and by market size, with the number of events and markets behind each figure.
The unit for any statistical statement is the release event, not the market. State how many events and markets
entered, and which were dropped and why.

## 2. Calendar (fixed in `release_calendar.py` before the tapes)

- Tier A, official US calendars fetched today: BLS 2026 schedule page (Employment Situation, CPI, PPI at 8:30
  ET; JOLTS at 10:00 ET), BEA full 2026 schedule and `release_dates.json` (Personal Income and Outlays; GDP
  advance estimate Q3 on 2026-10-29), Federal Reserve FOMC calendar (Sept 15-16, Oct 27-28; statement 14:00
  ET). ET -> UTC: +4 h until 2026-10-31, +5 h from 2026-11-01. No postponement notice was found on any page.
- Tier B, everything else: the DATE is the one printed in the market's rules text (which cites the publisher's
  calendar); the CLOCK TIME is the publisher's standing publication time (ISM and Michigan: 10:00 ET printed in
  the rules; central banks and statistics offices: from the analyst's knowledge, listed per row in
  `release_calendar.py`, not fetched from the publisher today). Tier B is therefore only usable if the tape
  confirms the time (section 4).
- Retail sales and weekly jobless claims: no Polymarket market found (tags economy, fed, inflation, jobs,
  macro-indicators, gdp, cpi, unemployment, jobs-report plus text search "retail sales", "jobless claims",
  "initial claims"). Recorded as "no market", nothing to measure.
- A release event (the statistical unit) = one scheduled second. Polymarket events decided at the same second
  (for example the four CPI events plus eggs; GDP and PCE on 2026-10-29; ISM manufacturing and JOLTS on
  2026-09-01 14:00 UTC) form ONE cluster for errors, but are shown under their own release type in the tables.
- The scheduled time T is never moved to fit the tape. An event whose time the tape does not support is
  flagged or dropped, never re-timed.
- Excluded before any tape (list with reasons in `release_calendar.py`, `EXCLUDED`): families with no fixed
  announcement second (BoJ, Copom, Colombia, SARB, RBI, Bank of Korea), China CPI (rules give only the
  month), deadline / ladder / price-level markets, events released before 2026-09-01.

## 3. Markets and data — concrete choices

1. Discovery: `gamma.iter_events(closed='true', tag_slug=..., end_date_min=2026-08-28, end_date_max=2026-11-27)`
   over the tags above; events are assigned to a calendar row by slug pattern.
2. A market enters if: volumeNum >= 5,000; binary Yes/No; `dataapi.resolutions` says resolved with final
   prices exactly {1, 0}; its gamma `closedTime` is later than T (a market closed before T was decided
   earlier and is dropped as "closed before the release"). Winner = the outcome with final price 1.
3. Tape: `dataapi.iter_trades(condition=...)`, newest first; paging stops after the first page that contains
   a row with block time < T - 7,203 s (two hours before the release) or when the tape ends. Hard cap 600
   pages; a market whose download hits the cap before reaching T is dropped ("tape too long"). Cached under
   `data/gaps_econ/tapes/`. Sequential downloads only.
4. Times: match time = block time - 3 s. All offsets below are match time minus T. Block-time jitter is 1-2 s,
   so the "first 5 s" bucket and the d = 5 s variant are fuzzy by that much; said in the results.
5. Winner price of a print: p if the print is in the winner token, 1 - p if it is in the loser token.
   "Winner buyable" prints (liquidity a taker could have bought the winner from): taker BUY of the winner at p
   (price p), taker SELL of the loser at p (price 1 - p). The other two kinds (taker SELL of the winner, taker
   BUY of the loser) show a resting BID for the winner, not an offer; they are never used as fills.
6. Fee: 0.01 * p * (1 - p) per share on every hypothetical fill, in all markets, also where the gamma
   `feeSchedule` says 0 (the US GDP event) — the conservative reading. Rebates 0.

## 4. Confirming the release time against the tape (done before E1-E4, uses no winner information)

Per market: Yes-price of a print = p for outcome index 0, 1 - p for index 1. Reference = Yes-price of the last
print with offset < -60 s. Large move = first print with offset >= -60 s whose Yes-price differs from the
reference by >= 0.10. Event move offset = the earliest such print over the event's kept markets.
- Confirmed: -5 s <= move offset <= +60 s.
- No market moves by 0.10 (the number was priced in): fall back to activity — the busiest 60-second window of
  prints in [T - 1 h, T + 1 h] must start within [-5 s, +60 s] of T. Otherwise "unconfirmed".
- Move offset outside the window: investigate by reading the tape around T (written up per event in
  results.md). Possible verdicts: "kept, official time, drift/noise before" or "dropped".
- Tier A events that stay unconfirmed are kept (the official calendar is authoritative) but shown as a separate
  row and flagged. Tier B events that stay unconfirmed are dropped.

## 5. Measurements — exact definitions

For each kept (release, market), using prints with offset >= 0 as "after the release":
- E1: winner price of the last print with offset < 0, and its age in seconds. Missing if no earlier print.
- E2: offset of the first print (any side) with winner price >= 0.90 / 0.95 / 0.99. If never reached before the
  tape ends: censored, reported as "never" and counted separately (medians are over markets that reached it,
  with the count next to them). Markets whose E1 was already >= the level are counted as "already there".
- E3: prints with offset >= 0 and winner price < 0.95.
  - (a) taker-informed: taker BUY of the winner or taker SELL of the loser — the protocol's "winner bought below
    0.95 or loser sold above 0.05". Dollars = shares * price paid/received by the taker in that token; gap
    dollars = shares * (1 - winner price) (what the stale side gave away before fees). Wallet statistics
    (number of distinct taker wallets, share of the top three by gap dollars) are computed on (a), pooled per
    release event and over the whole study.
  - (b) reported separately: taker SELL of the winner below 0.95 and taker BUY of the loser above 0.05 (the
    taker was on the wrong side; the gain went to resting orders). Same two dollar measures.
  - Buckets by offset: [0, 5), [5, 30), [30, 120), [120, 600), >= 600 s.
- E4, for d in {5, 30, 120, 600}: walk the winner-buyable prints with offset >= d in time order; at each print
  priced <= 0.97 buy min(print size, remaining budget / price) shares; budget 500 dollars of cost per market
  (fees not counted in the budget). Hold to resolution (payout 1). Net = shares * (1 - price) - fee. A market
  with no qualifying print contributes zero shares and zero profit. No end cap: prints up to the end of the
  tape count (most markets close about two hours after the release); the offset of the last E4 fill is
  recorded so late "carry" fills can be told from fast ones.
- E4 assumes the outcome is known at T + d. Families flagged in advance as needing judgement or arriving later
  (shown separately and inside the totals): eggs (FRED update), FOMC dissent count (vote paragraph), the two
  "Fed decisions" combination events, and any market whose gamma closedTime is more than 6 hours after T
  (delayed or disputed resolution). Everything else maps the headline number to a bucket mechanically.
- E4 is an upper bound on what one extra taker could have had: the prints are fills that other takers actually
  got; taking them means displacing those takers, at the same price, with no market impact.

## 6. Aggregation and statistics

- Release types: Employment, CPI, PPI, PCE, GDP (US), FOMC, JOLTS, ISM, UMich, central bank (non-US),
  inflation (non-US), GDP (non-US). Market size by volumeNum: 5K-20K, 20K-100K, 100K-1M, > 1M.
- Per release cluster (one scheduled second): sum of E4 net profit and of E4 cost over its markets.
  Reported: total dollars, return on cost with `stats.ratio_cluster` (clusters = release seconds), mean profit
  per release with `stats.mean_se`, both with t. The same ratio clustered by market is printed next to it for
  reference only. Every figure carries the number of releases and markets behind it.
- Time split: nothing is tuned, so the split is only for reporting: early part = releases before 2026-10-15
  00:00 UTC, reporting part = releases from then to 2026-11-26. The verdict uses the reporting part.
- Primary variant, declared now: E4 with d = 30 s on all kept markets. d = 5 s, 120 s, 600 s are the other
  three variants. Variants run = 4; no others will be added.
- Dollars per day = total E4 net over a period / calendar days in it (2026-09-01..2026-11-26 = 87 days;
  reporting part 2026-10-15..2026-11-26 = 43 days).
- Verdict rule: OPPORTUNITY only if the reporting part of the primary variant is positive after fees with
  t > 2 (clustered by release) across at least 100 markets; NO EDGE if clearly negative or zero; otherwise
  INCONCLUSIVE.

## 7. Order of operations

1. `discover.py` (done, metadata only) -> `release_calendar.py` (done) -> this file.
2. `build_markets.py`: market table, volume filter, resolutions, closed-before-T filter.
3. `fetch_tapes.py`: tapes.
4. Sanity slice on one release (US CPI of 2026-09-11): timestamps inside the window, fee formula, and over
   pre-release prints the realised win rate of tokens bought at 0.40-0.60 should be near one half.
5. `confirm_times.py` (section 4), investigations written down.
6. `measure.py` (E1-E4) on everything, `report.py` tables -> results.md.

## 8. Missing data

- No print before T: E1 missing, market still used for E2-E4.
- No print after T: E2 "never", E3 = 0, E4 = 0 (zero profit, zero cost; the market still counts in the
  number of markets).
- Resolution not {1, 0} or not resolved: dropped.
- Wallet missing on a print: counted under one "unknown" wallet.
