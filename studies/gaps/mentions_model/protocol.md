# Protocol: mentions markets, base-rate rules before the event (written 2026-11-27, before any outcome statistic)

Frozen once saved. New ideas go to "Ideas, not tested" in results.md, not into this file.

## Question

Markets "will person X say word Y during event Z" (gamma tag `mention-markets`, taker fee 0.01 since 21 Nov 2026).
Does a simple rule that a small program can run before the event (a few seconds of reaction are irrelevant here)
beat the price after the taker fee? Two rules are tested:

- V1, the lead of the earlier wallet study (`studies/wallets/mentions/pre_event.txt`, "Variant 4", exploratory):
  single-mention markets priced 0.05-0.50 on Yes before the start resolve Yes less often than the price says, so
  buying No pays. That lead was found on events of 29 Sep - 23 Nov 2026; here it gets fresh data on both sides.
- V2, a "transcript frequency" rule: the base rate of the same word for the same speaker in earlier resolved
  mention markets (Polymarket's own resolution history is used as the transcript record; no external transcripts).

Also answered (descriptive, no tuning): how many such markets run per week, how much is buyable at the rule's
prices, how many events fall on weekends, and who earns in the category (from the existing wallet study).

## Data

- Market metadata and outcomes: gamma `/events/keyset?tag_slug=mention-markets&closed=true` (1,392 events, 24,745
  markets, Jun 2024 - Nov 2026), saved as `data/gaps_mentions_model/events_closed_raw.json`; parsed by
  `universe.py` into `data/gaps_mentions_model/universe.json`. Only binary Yes/No markets resolved exactly 0/1.
- Tapes: Data API `trades?condition=` whole-market tapes, cached in `data/mentions_tapes/` (2,530 of the sample
  already there, the rest fetched by `fetch.py`, newest first).
- Event start: the gamma EVENT `startTime`. It is used only when it is at least 1 h after the event's creation time
  and not later than the first `closedTime` among the event's markets (otherwise the event is dropped: it is
  known to be wrong in some events). This filter uses closing times, not outcomes.
- Event type from the slug: `earnings` (slug contains "earnings"), `period` (this-week / in-<month> / this-month /
  headlines / week-of / by- / this-year) and `live` (everything else). Period events are excluded (their start time
  is the end of the counting period).

## Sample

Live and earnings events with a valid start in [2026-08-01, 2026-11-28) UTC: 4,215 markets in 272 events at the
time of writing (count from metadata only). If not all tapes can be fetched in time, the sample is cut by date
(newest kept, since the fetch runs newest first) and the cut is reported under Limitations.

Segments by event start:
- S1 = [1 Aug, 29 Sep): early, not seen by the earlier study. Fresh for V1.
- S2 = [29 Sep, 24 Nov): the discovery sample of V1 (overlaps the earlier study's universe).
- S3 = [24 Nov, 28 Nov): late, fresh, and the only part traded under today's 0.01 fee.
Early part = S1, late part = S2 + S3 (S3 also shown alone). Nothing is tuned: all thresholds are fixed here.

## Fills and fees

- Entry window W = [start - 24 h, start - 5 min] in match time (block time - 3 s).
- A side S (Yes or No) is "buyable at price x with size s" at a tape row that shows it: a taker BUY of S at x
  (the S ask was x), or a taker SELL of the other outcome at 1 - x (that outcome's bid at 1 - x is the S ask at x,
  the books are mirrors). Size s = the row's shares. Nothing else counts as available.
- The rule buys at the FIRST buyable row in W at which the rule's condition holds, at that row's price, for
  min(row size, 20 USD / price) shares. One entry per market per variant. Held to resolution.
- Fee: 0.01 x shares x p x (1 - p) on every entry (today's rate, applied to all segments; historical prices were
  formed under the old 0.04 fee, see Limitations). Rebates 0. No maker scenario is run in this study.
- Sensitivity (counted as a variant run): the same entries at price + 0.01.

## Variants (exactly two rules, plus the one sensitivity)

- V1: market has no "N+ times" count in the question; type live or earnings; buy No at the first No-buyable row
  in W with No price in [0.50, 0.95] (Yes 0.05-0.50).
- V2: key = (event type, speaker, sorted quoted terms, count N or 0). Speaker = the text between "Will" and
  "say/mention" (lower case, "donald/president/the" stripped); when it is missing or is "anyone", "announcers",
  "someone", the speaker is replaced by the normalised "during ..." phrase of the question (digits, month names,
  "next/first/the/episode/week of" removed). Priors = markets with the same key in OTHER events, resolved 0/1,
  closedTime before the entry row, from the whole 2024-2026 universe, live/earnings only. Needs n >= 3 priors.
  b = (k + 1) / (n + 2). Buy Yes at the first Yes-buyable row in W with price <= b - 0.15, or buy No at the first
  No-buyable row with price <= (1 - b) - 0.15, whichever comes first; prices restricted to [0.03, 0.97].
- R-sens: V1 and V2 entries at price + 0.01.

## Statistics and unit

- Per trade: pnl = shares x 1{side won} - shares x price - fee; stake = shares x price.
- Headline: return on stake = sum pnl / sum stake, standard error clustered by EVENT (`pmlab.stats.ratio_cluster`),
  95% interval = +-1.96 se; bootstrap of the total pnl by event as a second interval. Reported per segment, with
  number of trades, events, win rate, mean price, net per trade at the 20 USD cap and scaled to 5 USD.
- Descriptive (no decisions taken on them): markets and events per week; weekday of event start (UTC) and the
  weekend share; V1/V2 split by weekend vs weekday; buyable dollars at the qualifying rows.

## Decision rule (fixed now)

A variant earns a live micro-test only if ALL hold:
1. return on stake after fee > 0 in the early part (S1) AND in the late part (S2+S3) separately;
2. for V1: the 95% lower bound on the fresh data (S1 + S3) is above 0; for V2: the pooled 95% lower bound is above 0;
3. pooled at least 30 events and 150 trades;
4. attacks: still positive after removing the 3 best events, and still positive at price + 0.01.
Otherwise the verdict is "nothing to test" (negative or no edge) or "inconclusive" (positive point estimate that
fails 2-4), and no live test is proposed.
