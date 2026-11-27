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
