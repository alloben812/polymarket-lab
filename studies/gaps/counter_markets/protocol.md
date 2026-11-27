# Counter-settled markets: does a simple counter model beat bucket prices hours or days before the end? — protocol

Written 2026-11-27 ~18:50 UTC, before any outcome-based number of this study was computed. Inspected before
writing (availability and formats only, no outcomes): xtracker `/api/users` (10 handles, 8 with markets),
`/trackings` per handle (windows, slugs), one `/posts` page, three gamma events (bucket slugs, `culture_fees`
0.01, negRisk), one whole-market tape (row format; `start`/`end` are ignored for `condition=`), gamma tag
listings (box-office, billboard, spotify, rotten-tomatoes, app-store, youtube). Frozen after saving: changes go to
"Ideas, not tested" in results.md.

## Question

Markets that settle on one public counter: does a simple model of the counter (the rate so far, optionally with
the account's hour-of-week pattern) find bucket prices that are wrong by more than the 0.01 taker fee, when the
entry is hours or days before the end (not seconds)? How many such markets run per week?

## Families and what is tested

- **A. Post-count markets (tested).** Events whose resolution counter is `xtracker.polymarket.com` (the counter
  has a public JSON API with every counted post, `createdAt` and `importedAt`). Handles with events: elonmusk
  (2-day and 7-day; monthly excluded), realDonaldTrump, WhiteHouse, ZelenskyyUa, NYCMayor, cz_binance, tedcruz,
  khamenei_ir (7-day). Bucket ladders of 20-25 posts, negRisk, fee type `culture_fees`, rate 0.01.
- **B. Other counter/table families (counted only, no model test).** Box office (weekend / domestic gross),
  Billboard / Spotify chart positions, Rotten Tomatoes scores, App Store ranks, YouTube view counts. Reason: no
  free, timestamped history of the counter's intermediate values is available here within the budget (box-office
  daily numbers arrive once a day and The Numbers is blocked; chart and rank markets are not counts). Output for
  B: number of events and volume per week, Oct 1 - Nov 27, from gamma tag listings. The earlier culture study's
  box-office results are cited, not re-run.

## Data (family A)

- Events: xtracker trackings with a `marketLink`, duration 2 or 7 days, window end in
  [2026-10-01 00:00, 2026-11-27 17:00] UTC. Bucket markets from gamma `events?slug=`; bucket bounds parsed from the
  market slug (`-lo-hi`, `-Nplus`, `less-than-N`). Events whose buckets cannot all be parsed are dropped (counted).
- Posts: `/api/users/<h>/posts` for each handle, 2026-08-26 .. now (28 days before the earliest window), 5-day
  chunks, cached in `data/gaps_counter/`. Information at time t = posts with `importedAt <= t`; the final count F
  = posts with `createdAt` in [start, end+1 s).
- Tapes: whole-market taker tapes (`trades?condition=`), cached in `data/gaps_counter/tapes/`.
- Outcome: gamma `outcomePrices` of the closed bucket market (1/0). A market not resolved 1/0 is dropped
  (counted). The tracker's F against the resolved bucket is reported (match rate); events are kept either way.
- Budget rule: download events newest-first; downloads stop at 19:40 UTC whatever is reached; the sample is the
  events fully downloaded by then. Said under Limitations if it bites.

## Models (two)

Window [s, e); decision time t; N = imported count at t; remaining R = F - N.
- **M1 pace:** mu = N * (e - t) / (t - s).
- **M2 profile:** hour-of-week profile from the 28 days before s (posts by `createdAt`, per hour-of-week slot,
  divided by 4); E(a, b) = profile integrated over [a, b); mu = E(t, e) * (N + 1) / (E(s, t) + 1).
- R ~ negative binomial with mean mu and dispersion k (variance mu + mu^2 / k). k is fitted by maximum likelihood
  on the EARLY events only, separately for each model and each horizon, over the grid
  {1, 2, 3, 5, 8, 12, 20, 30, 50, 100, 1000}, using counts only (no prices). Bucket probability
  q = P(lo <= N + R <= hi); NO token probability 1 - q.

## Entry and fill rule

- Decision times t = e - h for h in {72, 24, 12, 6} hours, only if t - s >= 24 h (2-day events: 24, 12, 6;
  7-day events: all four).
- Fill window: prints with match time (block time - 3 s) in [t, t + 30 min]. Every taker print shows one token
  that could be bought at that moment: taker BUY of token X at price p -> X at p; taker SELL of X at p -> the other
  token of that market at 1 - p (books are mirror images). Available size = the print's size.
- For each print in time order, q is recomputed with N at the print's match time. Fee per share
  f = 0.01 * c * (1 - c) (rate 0.01 applied to all dates: the question is about trading today). Enter when
  q - c - f >= theta and 0.02 <= c <= 0.97. At most one entry per (event, bucket, token, h): the first qualifying
  print. Shares = min(print size, 20 / c) (the "$20 cap"); a "$5 cap" run uses min(size, 5 / c).
- PnL per share = payoff (1 or 0) - c - f, held to resolution. No exits, no maker orders in this study.

## Variants (four, all reported)

{M1, M2} x theta in {0.05, 0.10}. Selection on the EARLY part: the variant with the highest net PnL per dollar
spent ($20 cap); ties -> theta 0.10. All four are reported on both parts.

## Time split and clustering

Events sorted by end time; EARLY = first half (by count), LATE = second half. Unit = event (all buckets and
horizons of one event form one cluster). Headline: net cents per share and net % of dollars spent with an
event-clustered standard error (`pmlab.stats.ratio_cluster`), t, and a 95% bootstrap interval of the total by event.
Descriptive sub-cuts of the LATE part (not variants): events ending on or after 2026-11-21 (current fee regime);
entries whose decision time falls on a Saturday or Sunday UTC; by handle group (elonmusk vs others); by h.

## Decision rule

- **LIVE MICRO-TEST** if the selected variant on LATE: net > 0, t >= 2.0 (by event), >= 15 LATE events with
  trades, still net > 0 after removing the single best LATE event, and net > 0 on EARLY.
- **INCONCLUSIVE** (no live money; at most a forward paper log) if LATE net > 0 but any other condition fails.
- **NOTHING TO TEST** if LATE net <= 0.

## Outputs

Opportunities per day (qualifying entries per day in LATE), net per trade at $5 and $20 caps, capacity in $/day
(sum of capped dollars per day and net $/day), reaction time (entries are hours before the end; the window is
30 min, so the needed reaction is minutes; also reported: share of entries whose print is within 60 s of a price
move of >= 5 c in the same token). Attacks before reporting a positive: look-ahead (importedAt, not createdAt),
fills (print size cap, mirror rule), concentration (best event removed), sample size.
