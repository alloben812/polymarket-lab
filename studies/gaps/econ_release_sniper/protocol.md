# Protocol — macro release sniper: what share of the release race could a fast, well-placed small taker take?

Written 2026-11-27 ~20:58 UTC, before any outcome-based statistic of this study was computed. Before writing it I
looked only at data formats and counts (the cached market list of `studies/gaps/econ_release_lag`: 268 kept
markets, 229 of them with a mechanical mapping, 51 release seconds; tape row format) and read that study's
results.md and audit.md, whose published aggregates I know (pool about $350/day, 81% within 7 s, 98% within 30 s,
110 wallets, top three 47%). This protocol is frozen after it is saved; new ideas go to "Ideas, not tested".

## 1. Question

Polymarket prices absorb a scheduled US macro number in about 5 s (block time) and nothing is left after 30 s.
The source is public and timed to the second. Could a trader who reads the number from the official source within
tens to hundreds of milliseconds and sends prepared orders from AWS eu-west-1 (Ireland; 11-13 ms to the matching
servers in eu-west-2; no taker delay on economics markets, `secondsDelay` absent; taker fee 0.01 x p x (1 - p),
no rebates, makers pay nothing) take a meaningful share? How many dollars is that per release and per month, for an
account of about 200 EUR (orders of 20-50 USD) and one of 2,000 USD (orders up to 200 USD)?

## 2. Data

- Part 1 sample: the 268 markets / 51 release seconds (2026-09-01 .. 2026-11-25) that `econ_release_lag` kept
  (its `release_status.json`, tapes in `data/gaps_econ/tapes/`, audited: complete against gamma volume, winners
  verified on `tokens`). Mapping flags as in that study: 229 markets "mechanical" (unflagged), 39 flagged.
  Fresh data: a gamma check for closed release-decided events that ended 2026-11-25..27 (after the cached set) with
  the same tags; any new scheduled release with markets >= 5,000 volume is added with the same rules. Jobless
  claims / retail sales: re-check by gamma text search that no market exists; if one exists, it is added.
  No other re-download (the audit reproduced the cache row for row against a fresh download).
- Part 2: live HTTP measurements from this sandbox of the agencies' pages and APIs (response times, cache headers,
  update behaviour), at most ~10 requests per URL spaced >= 1.5 s. Nothing is measured at a release (none falls in
  the study window); the sandbox is not in Ireland, which is stated with every number.
- Part 3: official December 2026 calendars (BLS, BEA, Federal Reserve, DOL; WebFetch where curl is refused) and
  open Polymarket events from gamma (metadata only).

## 3. Time and block resolution

- Every print has block time b (seconds, offset from the scheduled second T). The lab rule: match time m = b - 3.
  Measured lag block - match: median 2.09 s, 1st-99th percentile 1.06-3.33 s (NOTES.md). So a print at b <= 1 was
  matched before T (for any lag >= 1.06 s); b = 2 was matched between T - 1.3 and T + 0.9.
- All windows below are stated on m (lab rule) AND, for the earliest-print question, on raw b.

## 4. Definitions

- Winner-buyable print: taker BUY of the eventual winner at p (winner offered at wp = p), or taker SELL of the loser
  at p (winner offered at wp = 1 - p). Loser-buyable: the reverse.
- Stale print: winner-buyable, b >= 0, wp < 0.95. Stale dollars = z x wp; gap dollars = z x (1 - wp); taker profit
  after fee = z x (1 - wp) - 0.01 x wp x (1 - wp) x z.
- Pool windows (per release second, all kept markets, and separately mechanical-only): first block (the earliest
  block b >= 0 of that release second that contains a stale print), m <= 2 s (b <= 5), m <= 5 s (b <= 8),
  m <= 10 s (b <= 13), and all after T. For each: stale dollars, profit after fee, distinct taker wallets, share of
  the top three wallets.
- Early-print test: stale (winner-buyable, wp < 0.95) vs loser-buyable (loser bought at < 0.95 equivalent, i.e.
  wp > 0.05) dollars at b = 0..1 and b = 2, against the same ratio for b in [-60, -1]. Informed early trading shows
  as winner-buyable dollars far above the pre-release ratio. Prints at b <= 1 cannot come from reading the page.

## 5. Strategy simulation (the variants)

One prepared taker order per market, mechanical markets only (unflagged), buying the eventual winner (known to the
trader from the published number; wrong-mapping risk is not modelled by this method and is reported from the
audit's tape measurement). Limit price 0.95 (only stale prices). The order arrives (is matched) at match time a and
consumes winner-buyable prints with wp <= 0.95 whose match time is in [a, a + 2 s] (b in [a + 3, a + 5]),
cheapest first, each at most its printed size, until the budget B is spent. Fee 0.01 x p x (1 - p) per share.
Net = shares - cost - fee (settlement at 1).

- Arrival a: A1 = +1 s (Ireland server, number read from the official source in <= ~0.5 s); A2 = +3 s (slower
  source or a home machine).
- Budget per order B: 20, 50, 200 USD.
- Fill scenario: U (upper bound) = we displace whoever really took the print; S (shared) = we get z / (k + 1) of
  each print, k = distinct real taker wallets that took stale prints in that market in the same window.
- 2 x 3 x 2 = 12 cells, all reported. PRIMARY: A1, B = 50, S.
- No other parameter is tuned.

## 6. Split, unit, errors

- Early part: release seconds before 2026-10-15 00:00 UTC (21 clusters); late (reporting) part: from 2026-10-15
  (30 clusters). Nothing is tuned on either; both reported.
- Unit: release second (cluster). Mean net per cluster with standard error over all clusters (zeros included),
  95% bootstrap interval of the total by resampling clusters (10,000 draws, seed 1).
- Per month = mean per cluster x clusters per month (clusters / days of the period x 30.4). US-only (BLS, BEA, Fed,
  ISM, Michigan) reported separately.

## 7. Decision rule (fixed now)

- LIVE MICRO-TEST worth running only if, in the late part, the primary cell has a mean net per cluster > 0 with the
  bootstrap 95% lower bound > 0, the expected net is >= $30 a month, AND Part 2 shows that an official source can
  be read within about 1 s of T from a server (no CDN cache of tens of seconds on the only free source).
- PAPER TEST ONLY if the U cells are positive but S fails the rule, or the source latency is unproven.
- NOTHING TO TEST if A1 U at B = 50 is below $30 a month in the late part.
- Running cost assumed: $80/month server (docs/speed-infrastructure.md); the verdict states net of it.

## 8. Attacks to run before reporting a positive

Leave-one-cluster-out (best cluster removed), best ten markets removed, lag 2 s / 4 s instead of 3 s for the
primary, and the order of prints inside one block (cheapest-first is the book-walk assumption; dearest-first as a
bound). These are robustness checks of the primary, not new variants.
