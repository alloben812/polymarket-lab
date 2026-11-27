# Protocol — tennis walkovers: how long does the book take to reach 50-50 and what can be bought on the way?

Written 2026-11-27 before any tape was downloaded and before any final price of the study universe was read.
Looked at so far: NOTES.md, the verification note in `catalog/raw/x2_practitioners.md` (two example matches of
Stavenson), the field layout of gamma tennis events (one page of futures events, one page of doubles events of
2026-10-27, all of them resolved 1/0) and the rule text of one doubles market. After this file the rules do not
change; anything thought of later goes under "ideas" in results.md.

## 1. Protocol as given by the lab lead (verbatim in substance)

Background. Tennis match markets carry the rule "If the match ends in a walkover (player withdraws before the
start and the other advances automatically), this market will resolve to 50-50"; a retirement after the start
resolves to the player who advances. Stavenson (0xf5fe759cece500f58a431ef8dacea321f6e3e23d) takes the underdog
at 0.15-0.45 when a withdrawal becomes known and afterwards rests bids at 0.49 on both sides. Sports taker fee
rate 0.05.

Question. How long is the gap between a withdrawal becoming public and the book reaching 0.50, how much can be
bought inside it, who competes for it, and how often does a look-alike situation resolve otherwise?

Universe. All tennis markets (ATP, WTA, Challenger, ITF; match winner and side markets of the same match) whose
outcomes resolved 0.5 / 0.5 between 2026-09-01 and 2026-11-25. Events through gamma (tag tennis), final prices
through `pmlab.dataapi.resolutions`. Read the rule text of a few markets from different tours. Control group:
tennis markets that collapsed toward 0.50 at some point but resolved 1 / 0.

Per walkover (match level; whole-market tape; taker BUY of X at p = X was on offer at p; taker SELL of X at p =
the other outcome was on offer at 1 - p; match time = block time - 3 s):
- W1 prices of favourite and underdog before the news;
- W2 t_first = match time of the first print that takes the underdog at least 0.05 toward 0.50 (or the
  favourite at least 0.05 down toward 0.50);
- W3 public notice time for at least 40 walkovers (official tournament and tour accounts on X through
  `tools/xread.py`, order-of-play updates, news pages, any reachable live-score API; document what works);
  t_first - t_public;
- W4 what could be bought: shares and dollars of the underdog on offer below 0.45 (and of the favourite's
  opposite side) in t_first..+10 s, 10 s-1 min, 1-5 min, 5-30 min, with volume-weighted prices; the wallets
  that took them (number, share of the top three, whether one wallet is always first);
- W5 time from t_first to resolution;
- W6 the resting-bid leg: dollars that traded at 0.48-0.495 after the book reached 0.50 and before resolution.

Rule (4 variants, d = 10 s, 60 s, 300 s, 900 s after t_first): buy the side trading below 0.50 at every print
priced 0.46 or less until 300 dollars per match are spent or 30 minutes pass; fee 0.05 * p * (1 - p) per share;
hold to resolution. Report events, events with a fill, average price, net dollars per event and per month, t
clustered by match. Repeat measured from t_public where known.

False positives: describe the control group and what the rule would have lost there. Capacity: total dollars
per month available at each delay and how many distinct takers share it. State the number of variants run and
what a follower cannot know in real time.

## 2. Concrete choices (fixed now)

### 2.1 Universe and classes

- Enumerate closed gamma events with `tag_slug=tennis` (`pmlab.gamma.iter_events(closed='true',
  tag_slug='tennis', limit=50 or 100 with keyset walk)`), event `endDate` >= 2026-08-20 (event endDate is the
  scheduled start + 7 days; the local filter below decides membership). Save compact metadata under
  `data/gaps_tennis_wo/`.
- A MATCH event = an event that has at least one market with `sportsMarketType == 'moneyline'` (futures,
  props and season markets are dropped). Singles and doubles are both kept and flagged; tour = the event's
  `seriesSlug` (atp, wta, challenger, itf, doubles variants as gamma names them).
- A market is in the period if its `closedTime` is in [2026-09-01 00:00:00, 2026-11-25 23:59:59] UTC.
- First pass on final prices: gamma `outcomePrices`. A market counts as 50-50 when both prices are 0.5. Every
  market shortlisted as 50-50, and every control market used, is confirmed with `pmlab.dataapi.resolutions`
  (`final` 0.5/0.5 or 1/0, `resolved` true). Disagreements are listed and the Data API value is used.
- Class A (walkover or cancelled match): a match event whose moneyline market resolved 0.5/0.5. This is the
  headline group. I cannot distinguish "walkover" from "cancelled, not played at all" from the price alone (the
  rule text sends both to 50-50); W3 sources tell them apart for the events that get a public time, and the
  split is reported.
- Class B: a match event whose moneyline resolved 1/0 but at least one side market resolved 0.5/0.5 (expected:
  retirements, pushes). Reported separately from class A, never mixed into the headline.
- One match = one cluster. If the same two players have two events on consecutive days (reschedule), they stay
  separate events but are flagged.

### 2.2 Tape conventions

- Tape per market through `pmlab.updown.tape(condition)` (cached in `data/tape/`), rows sorted by block time,
  match time = block time - 3 s. Second resolution: prints in the same second are simultaneous.
- Price of a print in terms of outcome[0]: a = p if the row's outcome is outcome[0], else 1 - p.
- Buyable: taker BUY X at p -> (X, p, size); taker SELL X at p -> (other outcome, 1 - p, size).
- Reference price at print i: R_i = median of a_j over prints j with match time in [t_i - 6 h, t_i - 120 s];
  if that window holds fewer than 3 prints, the last 3 prints at or before t_i - 120 s (fewer if fewer exist,
  at least 1); if there is none, R_i is undefined. Underdog at i = the outcome with reference below 0.5;
  r_i = min(R_i, 1 - R_i); x_i = the print's price in underdog terms.
- MOVE print: r_i <= 0.45 and x_i >= r_i + 0.05 (the underdog printed at least 5 cents closer to 0.50 than the
  reference; a favourite print 5 cents lower is the same thing in these terms).

### 2.3 W1, W2 on walkovers (hindsight allowed: these are measurements, not the trading rule's knowledge)

- On the moneyline market of a class A event: t_first = match time of the EARLIEST move print i such that
  every later print of that market has underdog price (underdog fixed as of i) >= r_i + 0.03, with at most two
  stray prints tolerated. W1 = (favourite 1 - r_i, underdog r_i) at that print.
- If the moneyline has no such print (no tape, underdog already within 5 cents of 0.50, market only traded
  after the news), the same definition is tried on the event's other 50-50 markets and the earliest t_first
  among them is used; W1 is then "not available". If there is none either, the event has no t_first: it stays
  in every count as an event without a fill (0 dollars), and is listed.
- Descriptive extra, not a rule: what printed in [t_first - 300 s, t_first) on the cheap side, because the
  first mover may sweep stale asks at the old price before any print is 5 cents away from it.
- t_50 ("book reached 0.50") = first print at or after t_first priced within [0.48, 0.52] (moneyline; else the
  market that supplied t_first).

### 2.4 W4, W5, W6

- W4 over ALL markets of the event (moneyline and side markets reported separately and together): buyable
  prints with price < 0.45 in [t_first, t_first + 10 s], (10 s, 60 s], (60 s, 300 s], (300 s, 1800 s]: shares,
  dollars (shares * price), volume-weighted price, per event and summed. Wallets = taker wallets of those
  prints: distinct count, dollar share of the top three overall, and for each event the wallet(s) of the
  earliest such print (same-second prints are co-first); "always first" is judged on that table.
- W5 = moneyline `closedTime` - t_first. Also scheduled start (`gameStartTime`) - t_first.
- W6 from t_50 to `closedTime`, all markets of the event: maker purchases at 0.48-0.495 = taker SELL prints
  priced in [0.48, 0.495] (dollars = shares * p) plus taker BUY prints priced in [0.505, 0.52] (the maker
  sold at p = held the other side at 1 - p; dollars = shares * (1 - p)). Both parts shown. The tape does not
  name the maker; Stavenson's share is measured separately from his own fill feed (`taker_only=false`).

### 2.5 The rule

- Start time s = t0 + d, t0 = t_first (and separately t_public), d in {10, 60, 300, 900} s. Buying window
  [s, s + 1800 s]. In time order (block time, then tape order) over ALL markets of the event, at every buyable
  print with price <= 0.46 buy min(printed shares, what the remaining budget buys) of that outcome at the
  printed price. Budget 300 dollars per match including fees (cost = shares * (p + fee)); the last fill may be
  partial; the 5-share minimum is ignored.
- Fee per share 0.05 * p * (1 - p), no rebate. Payoff per share = the market's actual final price of that
  outcome (0.5 in a 50-50 market, 1 or 0 otherwise), confirmed through the Data API. Net = payoff - cost.
- Fill assumption: the follower gets the printed size at the printed price, i.e. takes the place of the taker
  who actually got it. This is the lab's standard and is an upper bound for a late follower in a race.
- Reported per variant: events, events with a fill, shares, dollars, average price, net dollars, net per
  event (all events, zeros included; `mean_se` over events, t clustered by match), net per dollar spent
  (`ratio_cluster`), net per month (period = 86 days = 2.83 months), by calendar month, and the time split:
  class A events sorted by moneyline closedTime, first 67% = earlier part, last 33% = reporting period
  (`stats.split_by_time`). The verdict uses the reporting period.
- A second line "moneyline only" (same rule restricted to the moneyline market) is reported because the
  control group is evaluated on moneylines only.
- Class B gets the same four delays with t_first defined per event as the earliest t_first (2.3 definition)
  among its 50-50 markets; separate table.

### 2.6 Control group and the causal follower

A follower cannot use the hindsight in 2.3. Two control definitions, both on moneyline markets that resolved
1/0 in the period:

- Sample. If there are more than 3,000 such moneyline markets with a non-null `volumeNum`, use the
  deterministic sample int(sha1(conditionId), 16) % k == 0 with k = ceil(N / 3000) and multiply control totals
  by k; otherwise use all.
- Causal trigger (what a tape follower sees): an episode starts at a move print that has no other move print
  in the previous 30 minutes. Only episodes that start before the scheduled start (`gameStartTime`; event
  `startTime` if missing; markets with neither are dropped from this check) are acted on, because in-play
  swings are a different, known thing and a follower can see that a match is live. The rule of 2.5 runs from
  each such episode start (delay d, 30-minute window), moneyline only, with ONE 300-dollar budget per match
  across episodes.
- C-broad = control moneylines with at least one pre-start episode. The same causal procedure is run on the
  class A moneylines (not the hindsight t_first), and "walkovers + scaled controls" is reported as the causal
  follower's result for each delay. This is the number that answers "is there an edge for a tape follower".
- C-pin (strict look-alike, any time including in play): control moneylines where, within 30 minutes after an
  episode start (no pre-start restriction), there is a run of at least 5 consecutive prints spanning at least
  5 minutes all priced within [0.47, 0.53]. For these: count, share of triggered markets, what the rule would
  have made or lost (moneyline, from that episode start), and a description of the largest cases.
- For both: describe what happened in the ten largest losses (when relative to the scheduled start, price path).

### 2.7 W3 public notice time

- Order of work: class A events sorted by moneyline volume, descending, tour-level (ATP/WTA) and Challenger
  first; continue until at least 40 have a timestamp or the sources are exhausted. Every attempted event is
  listed with the result (found / not found), so the hit rate is visible.
- Sources tried, in this order, and documented (reachable or not): X timelines through `tools/xread.py`
  (tournament account, tour accounts, accounts that track withdrawals and order-of-play changes), X status
  lookups of posts found through WebSearch, news pages, live-score APIs reachable from the sandbox (ESPN site
  API first; others are tried and the outcome recorded).
- t_public = the earliest timestamp found that states the withdrawal / walkover / lucky-loser replacement of
  that match. Precision is recorded (second for X posts; minute; day). Day-precision sources are not used for
  the lag. Lag = t_first - t_public (negative = the book moved before the earliest notice I found).
  The earliest notice I can find is an upper bound on the true first public moment.
- The rule from t_public uses the same four delays on the events with a second- or minute-precision time.

### 2.8 Capacity and competitors

- Capacity at delay d = dollars of buyable prints priced <= 0.46 in [t_first + d, t_first + d + 1800 s] over
  all class A events and all their markets, without the 300-dollar cap, per month; distinct taker wallets in
  those prints and the top-three share.

### 2.9 Order of operations

1. `s1_events.py` gamma walk -> metadata. 2. `s2_universe.py` classes A, B, control list; Data API
confirmation; rule text of markets from different tours. 3. `s3_tapes.py` tapes (class A and B: all markets of
the event; controls: moneyline). 4. Sanity on a small slice (the two known Stavenson matches must come out at
09:38 UTC on 2026-11-03 and 11:15:58 UTC on 2026-11-18; all payoffs of 50-50 markets are 0.5; fee formula;
timestamps inside the event's life). 5. `s4_measure.py` W1, W2, W4, W5, W6. 6. `s5_rule.py` the four variants
on class A (t_first), class B, the causal follower on A + controls, C-pin. 7. `s6_public.py` + notes for W3,
then the rule from t_public. 8. results.md.

### 2.10 Counting

Four rule variants (the delays). Each is evaluated on: class A from t_first (all markets, and moneyline only),
class A from t_public, class B, causal follower (class A + control), C-pin. Every cell is reported. No
threshold (0.46, 0.45, 0.05, 300 dollars, 30 minutes, the reference window) is changed after results are seen.

### 2.11 Known limits, stated in advance

- The tape shows fills, not the book: resting liquidity that nobody took is invisible, and so is whether the
  follower's order would have been matched before the maker cancelled (tennis markets carry a 1-second taker
  delay, `secondsDelay = 1`).
- Taker rows are aggregated per taker order (price is the order's average), block time has 1-2 s of jitter.
- t_first on walkovers is defined with hindsight (the move "sticks"); only the causal follower lines are free
  of it.
