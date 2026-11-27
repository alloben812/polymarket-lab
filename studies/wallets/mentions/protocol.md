# Protocol - mentions category (written 2026-11-27 BEFORE running any wallet table)

Question: how do the consistently profitable "mentions" accounts make money, and can a solo trader with a few
hundred dollars and one VPS do the same.

Hypotheses per account, stated before data:
- H1 "live reaction / speech-to-text": profit comes from taker fills made DURING the event within seconds-minutes
  of the word being said. Test: on the whole-market tape find the jump moment (first fill at >= 0.90 on the Yes side
  after which the price never falls back below 0.80, for markets that resolved Yes); compute fill time minus jump time
  for each of the account's fills; count fills in [-120 s, +120 s] and whether the account is among the first takers.
- H2 "base rate / pre-event": profit comes from fills made before the event starts (eventStartTime / first jump in the
  event family), priced from how often the speaker uses the word. Test: PnL split by fill time relative to event
  start; typical signature = buys No at 0.6-0.95 or sells overpriced Yes long before the event, holds to resolution.
- H3 "after it, before settlement": buys the determined side at 0.95-0.999 after the word was said / the event ended
  without it. Test: share of buys at >= 0.95 that came after the jump time or after the event end; edge per share
  after fee.
- H4 "market making": maker share high, both sides, edge in maker fills.

Rules: fees in (mentions 0.01*p*(1-p), rebates zero for us); unit of analysis = market (condition) or event; window =
14 days ending 2026-11-27 (shorter if TRUNCATED); persistence from tools/wallet_check.py --monthly. Every script
variant is counted in README.md.

Selection rule (fixed before looking at wallet tables): from leaders.py mentions --top 60, take accounts with
>= 400 lifetime markets, average fill <= ~$200, rebates < 25% of kept_all, kept_all > 0 and at least 2 of the last 3
months positive, ranked by mentions month PnL; then drop any whose 14-day window shows < 30 mentions markets (they
make their money elsewhere) and record them as skipped. Whales (avg fill > $400 or few markets) are skipped by rule
but named.

## Addendum (written after split.py = variant 1, before deep.py = variant 2 was run)

Observation from variant 1: pmlab.wallet's "family" never says "mentions" (the gamma tag is `mention-markets`, and
politics/tech/sports tags win first). Mentions markets are therefore identified as: tag slug contains "mention" OR
slug matches (say|says|said|mention*) as a whole word. Only 5 leaderboard accounts that pass the selection rule had
>= 13 mentions markets in the 14-day window, so the deep window is widened to 45 days (fills API; tapes are complete).
Deviation from the selection rule, declared here: 0xtrador (rebates 48% of kept) and AiBird (64%) are added as
maker/rebate contrasts, clearly labelled.

Operational definitions (fixed before running):
- yes_px of a tape row = price if outcome is Yes else 1 - price.
- Yes-resolved market: T_det = time of the earliest tape row with yes_px >= 0.90 after which yes_px never prints
  below 0.70; T_pre = time of the last row before it with yes_px < 0.60. Jump window = (T_pre, T_det].
- No-resolved market: T_det = earliest row with yes_px <= 0.10 after which yes_px never prints above 0.30 (proxy
  for "event over / word clearly not coming"; soft).
- Event start = gamma event `startTime` (scheduled), fallback market `eventStartTime`/`gameStartTime`.
- Phase of a fill: PRE (t < start); LIVE (start <= t <= T_pre for Yes markets, start <= t < T_det for No markets);
  JUMP (Yes markets only: T_pre < t <= T_det + 60 s); POST (later). NOSTART when no scheduled start and t before
  T_pre/T_det.
- Fill PnL = shares * (final - price) for buys, shares * (price - final) for sells, minus 0.01*p*(1-p)*shares when
  the account was taker (today's rate; makers pay nothing; rebates ignored).
- Falsification tests: (a) "post-determination sniper" claim holds only if >= 80% of its buy-USD at price >= 0.95 is
  in JUMP/POST; (b) "live speed" claim holds only if it has taker fills inside the jump window at prices < 0.90 in a
  meaningful share (>= 20%) of the Yes-resolved markets it traded; (c) "base-rate" claim holds only if PRE fills carry
  the majority of the mention PnL and it is positive across >= 2/3 of events.

## Addendum 2 (written after variants 1-2b, before category.py = variant 3 was run)

What variants 1-2b showed (per-account, 45 days): four behaviours - (i) buying the already-decided side at 0.95-0.99
around/after the jump (oidocrop, QuantDeLaFugazi), (ii) buying No (sometimes Yes) a day or more before the event
(jkerkela, Faston), (iii) live discretionary trading inside the event (-Dominus-), (iv) small two-sided maker with
sniping at 0.99 (0xtrador). Variant 3 asks whether these edges exist for ANYONE who follows the same rule, on the
full set of sibling markets of every event these accounts touched (to reduce the "they picked the winners" bias).

Universe: every market of every event slug that appears in deep_*.json (8 accounts), resolved 0/1, with a tape.
Event types by slug: earnings ("earnings-call"), period ("this-week", "in-october", "in-november", "post-this-week",
"headlines"), live (the rest). Scheduled start = gamma event startTime; ignored if it is after the market closed.
Split: events sorted by scheduled start (or first tape time); earlier half = TUNE, later half = TEST. Errors by event.

Rules tested (all fixed here):
- R1 calibration: last tape print within 48 h before scheduled start (live + earnings events only) -> yes_px bucket
  (0-.1,.1-.25,.25-.4,.4-.6,.6-.75,.75-.9,.9-1) vs share resolved Yes.
- R2 "pre-event No": buy No at (1 - yes_px) + 0.02 for every market whose pre price is in a bucket chosen on TUNE
  (the bucket set with positive mean on TUNE); report TEST. Also the mirror "pre-event Yes". $1 stake per market.
- R3 "follow the confirmation": at the first print >= L seconds after the first in-event print where the bought
  outcome's price >= 0.95, if that later print is on the same outcome at 0.90 <= p <= 0.99, buy at min(p + 0.005, 0.995),
  hold to resolution, fee 0.01*p*(1-p). L in {0, 5, 30, 120, 600}. Report per-market return, win rate, total on TEST.
- R4 false-confirmation rate: share of markets with an in-event Yes print >= 0.95 that resolved No, and share with an
  in-event No print >= 0.95 (yes_px <= 0.05) that resolved Yes; plus $ lost on those prints.
- R5 jump capacity: for Yes-resolved markets with first_move - T_pre <= 30 min: seconds from first_move to first print
  >= 0.95; USD of taker long-Yes prints at yes_px < 0.90 and < 0.95 at lag >= L after first_move (L = 0,3,10,30,60,300)
  and the profit they locked in; who printed first (wallet counts).
Count of variants so far: 1 (split), 2 (deep, 8 accounts), 2b (stories), 3 (category) - no reruns with changed rules.

## Addendum 3 (before variant 4 = pre_event.py; exploratory, declared as such)
Variant 3 found no stable blind pre-event mispricing (R1 flips sign between halves). Variant 4 asks two narrower
questions, fixed here: (a) is there a Yes-overpricing in specific market kinds - threshold markets ("N+ times") vs
single-mention, live vs earnings - using only two price buckets (yes_px < 0.5, >= 0.5) and the same fill rule
(print + 0.02, fee in), per half; (b) do jkerkela's and Faston's PRE picks beat "buy the same side on every sibling
market of the same events at the pre price" (selection skill vs event luck)? Result is a lead for a backtest, not a
finding: the sample is ~50 events.
