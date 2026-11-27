# live_goals — protocol (frozen before any live result was looked at)

Written 2026-11-27 19:20-19:31 UTC, before `paper.py` existed and before any trigger, confirmation or fill on the
live data had been computed or looked at. Up to then only data arrival was checked: file sizes, message counts,
poll status codes, clock offsets. The sha256 of this file and the UTC time it was frozen are in
`data/live_goals/protocol_frozen.txt`. Any later change is a new, dated section at the end ("Amendment N: date,
reason"). The rules above it are never edited.

## Question

After a goal in a live soccer match, how fast does any source available to us confirm the new score, measured
against the Polymarket book's first move? At that moment plus 1 s or 3 s of reaction, what is still on offer in the
real recorded book? Does a hypothetical 10 USD taker buy of the scoring team make money after two 0.05 sports fees?
The previous study (`studies/gaps/sports_score_lag`, tapes only) showed +3.0 c/share only post hoc, with goal
knowledge a follower did not have. This study puts a real confirmation source in front of the trade.

## Data (recorder.py)

- Universe: every soccer match event on gamma (`tag_slug=soccer`, base event = home / draw / away moneyline
  markets) whose kickoff (`startTime`) falls in the recording. A token is subscribed from kickoff - 20 min to kickoff +
  3 h. Totals 1.5 / 2.5 / 3.5 and both-teams-to-score are recorded too. They are not traded in this protocol.
- Book: one book per token, rebuilt from the market WebSocket. A `book` message replaces the book.
  `price_change` sets the level to `size`, and size 0 removes it. BUY changes bids, SELL changes asks. Each
  message is applied in receive order and stamped with its exchange `timestamp` (ms). "Book at exchange time T" =
  the state after every message of that token with timestamp <= T.
- Clocks. All lags are measured on the local receive clock (`r`, ms): the WebSocket message that marks the
  market's move and the poll that shows the score are both stamped by this machine. To convert a local time to
  exchange time: exchange = local - offset. The offset is the median `binance_off_ms` of the clock lines within +-2 h
  (Binance serverTime, midpoint of the fastest of 5 requests). The WebSocket latency (local receive - exchange
  timestamp - offset) is reported as a sanity check.
- Score sources (local receive time of the first poll that shows a change):
  `pm_sports` (Polymarket sports WebSocket), `espn_sb` (ESPN scoreboard per league, every 2 s), `espn_sum` (ESPN
  summary per live match, round robin, at most 2 requests/s), `livescore`, `s365` (365Scores), `bbc`
  (all every 2 s). Sources that answered 403/404 from this sandbox on 2026-11-27: SofaScore (403), TheSportsDB
  (403), FotMob (404); Flashscore needs a signed header (not used).
- Match linking. `pm_sports` links by `gameId` equal to the gamma event `gameId`. If no message carries that id, it
  falls back to the name rule below. Other sources link by team names: normalised names (accents and club
  suffixes dropped). Both teams must reach a similarity >= 0.6 (difflib ratio, or containment, or a shared word >= 4
  letters), and the Polymarket match must be inside its live window at the time of the source record. Home and away
  are assigned by name, not by position.

## Market move and trigger (computed on the home and away "Yes" tokens)

- Mid = (best bid + best ask) / 2. It is defined only when both sides exist and the spread is <= 0.10. The mid is
  sampled once per second of exchange time (last book state of that second).
- Reference P_pre(t) = median of the 1-s mid samples in [t - 65 s, t - 5 s]. At least 20 samples are required.
- In play: t within [kickoff, kickoff + 2 h 30 min] (gamma `startTime`).
- Trigger at the first book update t with mid(t) - P_pre(t) >= thr, where thr = 0.03 + 0.10 x (1 - P_pre) and
  0.03 <= P_pre <= 0.95. One trigger per token per 180 s. P_pre is frozen at the trigger.
- First move t_move = the first book update after the last update before t whose mid was < P_pre + 0.02 (search
  back at most 30 s). Its local receive time `r` is the zero point of every lag.

## Confirmation

- A source confirms a trigger when its record for the linked game shows the trigger team's goals larger than in that
  source's previous record for the game. The receive time must fall in [t_move - 120 s, t_move + 600 s].
  Lag_source = r(source record) - r(t_move), in seconds. A negative lag means the source showed the goal before
  the book moved.
- Confirmation time t_conf = the earliest such record over all sources. Decision time t_dec = max(r(trigger),
  t_conf).
- A trigger that no source confirms is a false trigger (logged with its size). A source goal with no trigger within
  the same window is a missed goal (logged).
- Score before the goal (h, a) = the confirming record's score minus the goal.

## Hypothetical trade (primary: d = 3 s, f = 0.5, exit A; all 8 combinations are reported)

- Reaction d in {1 s, 3 s}: the order leaves at local time t_dec + d. It reaches the exchange 0.10 s later (exchange
  clock via the offset). It matches after the market's `secondsDelay` (1 s if missing): t_x = t_dec + d + 0.10 +
  delay, in exchange time. Only liquidity in the book at exchange time t_x counts. Anything added and pulled during
  the delay does not.
- Side: BUY the scoring team's "Yes" token.
- Price cap L = P_pre + f x (P_post_hat - P_pre), f in {0.5, 0.8}, rounded down to the tick. P_post_hat is ex
  ante, not the later market price. It comes from an independent-Poisson model of the remaining goals. (lambda_h,
  lambda_a) in [0.005, 5] are fitted so that the model's P(home win) and P(away win) match the three pre-goal
  mids (normalised to sum 1) at score (h, a). P_post_hat is the same model's win probability for the scoring team
  at the new score. No trade if any of the three pre-goal mids is missing or P_post_hat <= P_pre.
- Fill: walk the asks upward while price <= L, until 10 USD of notional (shares x price). No trade if the fill is
  under the market's `orderMinSize` shares (5 if missing).
- Fee on every taker leg: rate x p x (1 - p) per share. The rate is gamma `feeSchedule.rate` (0.05 if missing). No
  rebates.
- Exit A (round trip): sell all shares by walking the bids at exchange time t_x + 300 s + delay, with a second fee.
  Shares the bids cannot take are worth 0.
- Exit B (hold): 1 per share if the team won, else 0. The outcome comes from the WebSocket `market_resolved`
  event (winning asset). Until it is known, the trade is "pending" and left out of exit B.
- Excluded and logged: trades whose t_x falls in a WebSocket gap of that token (between a `ws_down` and the next
  `book` snapshot), or with no book message for the token in the 120 s before t_x.

## Descriptive measures (they use the later price, so they are look-ahead and not a strategy)

- P_post_real = median 1-s mid in [t_move + 120 s, t_move + 300 s].
- Stale dollars at t_x (d = 1 and d = 3): the sum of price x size of the asks priced at or below P_pre + 0.5 x
  (P_post_real - P_pre). The same at 0.8. Also the dollars at or below the ex-ante cap L.
- Source lag distribution per source: n, p10, median, p90, and the share of goals the source confirmed at all.
- WebSocket latency and the clock offset over the recording.

## Statistics and decision rule

- Unit = match. Net per trade = total net / trades, with a cluster-robust standard error by match
  (`pmlab.stats.ratio_cluster` with numerator = net USD per match, denominator = trades per match). 95% CI = +-1.96
  se. Also in c/share (numerator net USD, denominator shares).
- Split by time: early = kickoff before 2026-11-29 00:00 UTC (Friday 27 and Saturday 28 Nov); late = kickoff on
  or after it (Sunday 29 Nov onward). The first 45 minutes (Friday evening) are a pilot. They only show that the
  pipeline works and say nothing about profit.
- A micro-test is worth discussing only if the primary combination (d = 3 s, f = 0.5, exit A) has net per trade > 0
  in both parts, t >= 2 on the pooled sample, and >= 30 trades in the late part. Anything else is a negative or
  inconclusive result. The number of combinations looked at (8) is always reported next to the primary.

## Amendment 1 (2026-11-27 19:36 UTC, before any P&L, stale-dollar or lag table was computed)

Implementation details the frozen text left open. No rule above is changed.

- Clock offset: the paper trader runs in real time, so it uses the median of the clock checks received so far (at most
  the last 48 checks, i.e. 4 hours), not a window centred on the trade. A replay uses the same rule.
- "No book message for the token in the 120 s before t_x" counts any message that changed that token's book
  (`book` or a `price_change` entry for it).
- LiveScore (and possibly other CDN-cached sources) can flip between the old and the new score for a few polls.
  A source's confirmation is its first record showing the new score. A later re-appearance is not a new goal. The
  goal count dedups on (match, team, new score).
- An extra descriptive lag is reported, marked as such: source record time minus the trigger time (`r_trig`).
  t_move can lie well before a sharp jump when the price drifted up first.

## Amendment 2 (2026-11-27 19:46 UTC, before any P&L, stale-dollar or lag table was computed)

Book check: every `price_change` entry carries the exchange's own best_bid / best_ask. On 19:42-19:47 UTC the
rebuilt book disagreed with them on 2.7% of 447K entries. The disagreements were transient: 10,403 episodes,
median 24 ms, p90 0.6 s, every one cleared by a later message, and only 2.5% within 3 s of a trade. To stay
conservative, a fill or exit uses no ask priced below, and no bid priced above, the exchange's best quote from the
token's last `price_change`. A `book` snapshot resets this. The share of mismatches is reported as a data-quality
line.
