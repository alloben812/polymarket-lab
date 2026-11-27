# news_latency — protocol (written 2026-11-27, before any price or outcome data was read)

What had been looked at when this was written: NOTES.md, the toolkit source, the gamma market list (metadata only:
tags, fee types, dates, volumes), the shape of one `prices-history` response and of two tape rows. No jump had been
detected and no outcome of any rule had been computed.

## Protocol as given by the lab lead (unchanged)

**Question.** Unscheduled news is the purest form of the time gap. How fast do Polymarket prices absorb it, who takes
the first seconds, and is anything left for a trader who needs 30 seconds to 10 minutes?

**Event list.** (a) Try to obtain the dated events released with arXiv 2610.36639 (208 geopolitical events with
first-report times); use it if found. (b) Independently build a list from the market side for 2026-09-01 to
2026-11-25: binary markets in the geopolitics, world, politics and breaking-news style categories with
volumeNum >= 50,000 whose YES price moved by at least 0.40 within 10 minutes and had not reverted by more than half
of the move 2 hours later. Detect candidates on `prices_history` (300-second buckets, 60-second where still
available), then time them on the tape: t0 = the match time (block time minus 3 s) of the first print at least 0.10
beyond the pre-jump price. Exclude scheduled events (elections, votes, court dates and data releases with a known
time) into a separate group.

**News timing check.** For 40 jumps drawn at random, find the earliest public report (WebSearch, X posts through
tools/xread.py, wire timestamps) and record how many seconds t0 falls before or after it.

**Data.** Tapes from `pmlab.dataapi.iter_trades(condition=...)`. A taker BUY of outcome X at p means X was on offer
at p at the match time; a taker SELL of X at p means the other outcome was on offer at 1 - p. If the order-book
archive `chitoyuuri/polymarket-l2-v3-1-archive` is practical for the jump hours, use the real asks for a subset of
30 jumps and compare with the tape-based figures.

**Measurements per jump.** Price before, price 2 hours after and at settlement; time from t0 to 50 percent and
90 percent of the move and to 0.95 (or 0.05); dollars traded and volume-weighted price in t0..+10 s, 10-30 s,
30 s-2 min, 2-10 min, later; the wallets active in the first 10 seconds (number, share of the top three, whether
the same wallets are first across events).

**Rule (4 variants, one per delay d in 10 s, 30 s, 120 s, 600 s).** Starting at t0 + d, buy the side the jump
favours at every print priced at 0.90 or less, until 200 dollars are spent or 10 minutes have passed; hold to
settlement; fee = the market's own rate (0 for geopolitics, 0.01 for other politics, 0.05 for elections). Report by
category and delay: events, events with a fill, average entry price, share of jumps that later reversed, net
dollars per event and in total, t clustered by event; first half of the period against the second half.

Also: qualifying jumps per week; how many were still buyable at 2 minutes; what cannot be measured from here.

## Concrete choices (mine; fixed now)

### 0. Order of operations
1. `s1_markets.py`: dump gamma markets (done before this file: metadata only).
2. `s2_screen.py`: prices-history screen -> candidate jumps.
3. `s3_tapes.py`: tapes of candidate markets; `s4_jumps.py`: t0, tape confirmation, 2-hour test, settlement.
4. Scheduled / unscheduled labels are written to `out/labels.csv` from the question text, tags, description and
   jump date ONLY, before `s6_rule.py` is run for the first time. They are not changed afterwards.
5. `s5_measure.py` (speed, buckets, wallets), then `s6_rule.py` on a small slice (first 20 jumps by date) for sanity
   checks, then the full period. One run of four variants. No variant is added after results are seen.
6. News timing sample (seeded draw), L2 comparison if practical, results.md.

### 1. Universe
- gamma `/markets/keyset` with `volume_num_min=50000`, `end_date_min=2026-06-01`, closed and open. The endpoint
  ignores `tag_slug` (checked), so tags are filtered here.
- Keep a market when: it has exactly two outcomes; at least one tag in {politics, geopolitics, world, world-affairs,
  elections, global-elections, world-elections, breaking-news, middle-east}; no tag in {tweets-markets, elon-tweets,
  mention-markets, sports, games, esports, crypto-prices, up-or-down, hit-price, multi-strikes, weather} and the slug
  does not contain a whole word say/said/mention/tweet(s)/post(s) (count and word markets move mechanically, not on
  headlines); it was alive inside the window (open, or closedTime >= 2026-09-01, and startDate <= 2026-11-25).
- "YES" = the first listed outcome. Prices of the second outcome are 1 - YES.
- volumeNum is the lifetime volume as reported today (the only one available); a market that reached $50K only
  after its jump is therefore included. Stated as a limitation, not corrected.

### 2. Screen on prices-history (YES token)
- Rows with `resolution_seconds == 0` (a terminal marker row the API appends) are dropped.
- 300-second buckets where the API still serves them (from about 2026-09-27; 60-second buckets are requested for
  the last 7 days and used only if returned). Screen: two points at most 600 s apart with |change| >= 0.40.
- Before that only 1,800-second buckets exist. Screen there: two points at most 3,600 s apart with
  |change| >= 0.35 (looser on purpose; the tape decides). A jump of 0.40 that half-reverts inside the same half
  hour can be missed in September; stated as a limitation.
- Requests are chunked to 15 days and limited to each market's life. Consecutive detections in one market within
  2 hours are merged into one candidate (the earliest start). p_pre = the price of the earlier point of the first
  detecting pair; T_pre its timestamp.
- Window: T_pre between 2026-09-01 00:00 and 2026-11-25 23:59:59 UTC.

### 3. Timing and confirmation on the tape (one definition for the whole period)
- Tape rows are converted to a YES-equivalent trade price: p for the YES token, 1 - p for the other token.
  Match time = block timestamp - 3 s (`pmlab.updown.BLOCK_LAG`). All delays below are differences of block times,
  so the constant drops out; the 1-2 s block jitter remains (it matters for the 10 s variant only).
- dir = sign of the screened change. Favoured side F = YES if dir > 0 else the other outcome. All prices below are
  expressed for F (pF = YES price if dir > 0, else 1 - YES price).
- t0 = match time of the first print in [T_pre - 5 s, T_post + one bucket] whose F-price is >= pF_pre + 0.10,
  where T_post is the later point of the detecting pair. No such print -> candidate dropped ("no tape jump").
- p10 = F-price of the last print at or before t0 + 600 s. The jump is CONFIRMED when p10 - pF_pre >= 0.40.
  Otherwise it is dropped as "not confirmed on tape" (counted and reported).
- p2h = prices-history YES point (finest bucket available) at the first timestamp >= t0 + 7,200 s, converted to F;
  if the market closed earlier, the settlement value. HELD when p2h - pF_pre >= 0.5 * (p10 - pF_pre).
  Jumps that are confirmed but not held form group R ("reverted within 2 hours").
- Main sample per protocol = confirmed and held. Because "held at 2 hours" is information a trader does not have at
  t0 + d, the same four variants are also computed on group R and on main + R together and shown next to the main
  table as the look-ahead check. This is the same rule on a wider sample, not a new variant.
- A market can contribute several jumps (at least 2 hours apart). A later jump in the same market in the opposite
  direction does not remove the earlier one.

### 4. Scheduled vs unscheduled, categories, fees
- SCHEDULED when the jump coincides with something whose time was known in advance: an election or referendum count
  (jump between the opening of polls and 3 days after election day in a market about that election), a
  parliamentary / council / board vote announced beforehand, a court ruling or hearing date, a data release, a
  central-bank decision, a scheduled award announcement (Nobel etc.), a scheduled speech, debate or summit whose
  occurrence itself settles the market, or the expiry of the market's own deadline (a "by <date>" market collapsing
  or being resolved at its deadline with no new event). Everything else is UNSCHEDULED. Doubtful cases go to
  SCHEDULED (the conservative side for the headline group) and are marked "doubt".
- Method: keyword pre-label from tags / question / jump date, then every confirmed jump is read once by me. Labels
  are frozen in `out/labels.csv` before the rule is run.
- Category of a market (for the tables): `elections` if feeType is `politics_elections_fees` or it has a tag in
  {elections, global-elections, world-elections, midterms, primaries}; else `geopolitics` if it has the tag
  geopolitics or feeType `zero_fees` with a tag in {world, middle-east, world-affairs}; else `other politics`.
- Fee rate used by the rule: the rate recorded on the market (`feeSchedule.rate`) when present; when the market has
  no fee schedule (older markets), today's category rate: geopolitics 0, elections 0.05, other politics 0.01.
  Fee per share = rate * p * (1 - p), charged on the purchase only (held to settlement). Rebates zero. Past fee
  holidays (e.g. 20-31 Oct) are NOT applied: the question is what the rule would pay today.

### 5. Measurements
- move = p10 - pF_pre. Time to 50% / 90%: first print at or after t0 with F-price >= pF_pre + 0.5 / 0.9 * move
  (seconds after t0, block-time difference). Time to 0.95: first print with F-price >= 0.95, searched up to 24 h.
- Dollar buckets [0,10), [10,30), [30,120), [120,600), [600,7200) seconds after t0: all prints (dollars = shares *
  trade price of the token traded) and, separately, "buyable" dollars = prints that show F on offer (taker BUY of F
  at p, or taker SELL of the other outcome at q -> F offered at 1 - q), with their volume-weighted F-price and the
  part of them priced <= 0.90.
- First-10-second wallets: takers on the buy-F side in [t0, t0 + 10 s): number, dollar share of the top three, and
  across the unscheduled main sample the number of distinct news clusters in which each wallet appears.
- Settlement: `tokens` endpoint (`resolved`, `final_price`). Unresolved on the day of the run: marked at today's
  gamma `outcomePrices` and flagged.

### 6. Rule
- For delay d: walk tape rows with block time in [t0_block + d, t0_block + d + 600] in time order. A row is a
  fill opportunity when it shows F on offer at a price <= 0.90 (definition above). Buy min(row shares, remaining
  dollars / price) at that price; stop at $200 spent. No fill is assumed anywhere else. (This is an upper bound on
  what a real order gets: the print was consumed by the taker who made it; we assume we could have taken that
  liquidity instead of them. Stated in the results.)
- Payoff 1 per share if F settles as the winner, else 0 (0.5/0.5 resolutions pay 0.5). Unresolved markets are
  valued at today's price and shown separately; the headline includes them at that mark.
- net = shares * payoff - cost - fee. Jumps without a fill count as 0 in "net dollars per event".
- "Reversed" = F did not win at settlement (unresolved: today's F-price below pF_pre + 0.5 * move).
- Clustering: a news cluster = jumps of the same gamma event (ladder) with t0 within 30 minutes of each other
  (single linkage). t-statistics are reported with clusters = news clusters (`pmlab.stats.mean_se` on cluster
  sums) and, as the stricter check, with clusters = UTC days. The number of distinct markets is reported too.
- Split: first half 2026-09-01 .. 2026-10-13, second half (reporting period) 2026-10-14 .. 2026-11-25, by t0.
- Tables: category x delay for UNSCHEDULED main; the same for SCHEDULED; the look-ahead check (R, main + R).

### 7. Sanity checks on the slice before the full run
- Fills priced 0.40-0.60 across all groups: realised win rate with a Wilson interval (reported whatever it is).
- Fee recomputed by hand for three fills. Every fill has block time inside [t0 + d, t0 + d + 600] and price <= 0.90.
- Dollars spent per jump <= 200. Settlement value in {0, 0.5, 1} for resolved markets.

### 8. News timing sample
- 40 jumps drawn with `random.Random(20261127).sample` from the UNSCHEDULED main sample, one per news cluster
  (the earliest t0 in the cluster). For each: earliest public report found, its timestamp, its precision (X post
  ids give milliseconds; wire and news-site stamps usually minutes), and t0 - report in seconds. Where only a
  minute-level or coarser stamp exists it is recorded as such; no precision is invented. Jumps for which no dated
  report is found are counted as "not found".

### 9. L2 comparison
- If one hour of the relevant archive category can be read by range requests in reasonable size, take 30 jumps
  (seeded draw from the unscheduled main sample inside the archive's dates) and compare, per delay, the dollars
  buyable at <= 0.90 from real asks in the 10-minute window with the tape-based figure. If not practical, say why.

### 10. Verdict rule (from the lab lead)
OPPORTUNITY only if the reporting period (second half) is positive after fees with t above 2 across at least 100
markets; NO EDGE if clearly negative or zero; otherwise INCONCLUSIVE. The verdict is read on the unscheduled main
sample, all categories pooled, at the best pre-registered delay a slow trader can use (d >= 30 s), and the
look-ahead check (main + R) must not contradict it.

### 11. Paper data (a)
The local copy of arXiv 2610.36639 gives no URL for its release and its sample ends in September 2026. One web
search and the arXiv metadata will be checked; if nothing is found the study rests on list (b) only.

## Amendment 1 (2026-11-27, after the first screen output on 174 of 2,482 markets; before any tape was read)
The first candidate list shows pre-jump prices of exactly 0.50 followed by 0.045 or 0.01: prices-history is a
mid-price and reads 0.50 when a book is empty or one-sided. To keep such artefacts out, a confirmed jump must also
show the move on the tape itself: when a print exists in the 24 hours before t0, p10 minus the F-price of the last
such print must be >= 0.25. Jumps failing only this test are dropped as "pre-price artefact" and counted.
Nothing else changes.

## Note on bucket requests (same time)
Requests per market: 1,800 s for 31 Aug .. 27 Sep 02:00, 300 s for 27 Sep .. 26 Nov 00:00, 60 s for
20 Nov .. 26 Nov 12:00 (one page). The 60 s series is used in the screen and for the 2-hour price of late jumps.
