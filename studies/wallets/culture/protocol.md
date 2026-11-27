# Protocol (written 2026-11-27 before looking at any wallet table)

Question: how do the consistently profitable "culture" accounts (box office, awards, charts, celebrity news,
post-count markets) make money, and could a trader with a few hundred dollars and one VPS copy it.

Hypotheses per account, stated before data:
- H1 "late / time gap": profit comes from fills made AFTER the deciding observation is public (the counted post
  exists, the chart/box-office number is published, the award is announced) but before the price reaches 0/1.
  Test: for sampled markets take the first time the market price crossed 0.95/0.05 for good ("price-determined
  time", from the tape) and, where the source is a count, the time the count left/entered the bucket; compare with
  every fill of the account; split PnL into before/after.
- H2 "counting / model edge" (post-count buckets): profit from buying buckets early at mid prices on a rate model.
  Test: PnL by time-to-end and price bucket; for sampled events, entry price vs final outcome, and whether entries
  cluster right after count changes.
- H3 "near-certain carry": buys 0.95-0.999 outcomes and holds to settlement (or sells NO-hopers at 0.001-0.05).
  Test: share of PnL from fills at p>=0.95 or p<=0.05, loss frequency per market.
- H4 "market making": two-sided maker fills, PnL from spread/rewards. Test: maker share, buy/sell balance per
  market, maker vs taker edge.

Rules: fees in (culture taker rate 0.01*p*(1-p); rebates = 0 for us); unit of analysis = market (condition) or
event; per-fill tables are descriptive only. Window: 14 days ending 2026-11-27 (shorter if truncated). Persistence
is judged on monthly `economic_pnl` changes, not on the window. Every script variant run is counted in README.md.

Selection rule (fixed before running pmlab.wallet): lifetime >= 500 markets (or >= 250 with all of the last three
months positive), average fill <= ~$250, rebates <= 20% of kept, at least 2 of the last 3 calendar months positive
and kept_all > 0. Skip: accounts whose result is a few large directional bets, rebate-dependent market makers,
accounts with a large losing month in the last three.

## Addendum 1 (written 2026-11-27 after the wallet tables and lead/lag, BEFORE running copy.py / jumps.py)

Seen so far: cat-dog and shovelingdigging are takers in quiet markets and the independent price moves ~6 c their
way within 10 minutes. Two follow-up rules, fixed now:

C. Copy rule (copy.py). Signal = a cluster (same market, same direction, within 30 min) of the account's TAKER
   fills, >= $200 notional, prices 0.05-0.95. We trade the same direction. Our fill = the WORST independent print
   (other wallets only) inside [t_first + 60 s, t_first + 15 min]; no print -> no trade (counted). Hold to final.
   Taker fee 0.01*p*(1-p). Unit = market (mean of its clusters). Split: first half / second half of the window by
   time. Variant 2: window [5 min, 30 min]. Two variants in total, both reported.
J. Jump-follow rule (jumps.py). Universe = box-office markets cat-dog traded in 60 days (selection bias noted).
   Jump = last print moves >= 10 c between consecutive 10-minute bars, >= 3 trades in the bar, both prices inside
   0.05-0.95. Enter in the jump's direction at the WORST print of the NEXT 10-minute bar (none -> no trade); hold to
   final; fee in; unit = market; split by time. One variant. Also report when (weekday, hour UTC) jumps happen.

## Addendum 2 (2026-11-27, before running elon.py)

xtracker.polymarket.com (the resolution source of the post-count markets) has a public JSON API with every counted
post (`createdAt`, `importedAt`). Rules fixed before looking:
- Data check first: the tracker count inside each tracking window must land in the bucket that resolved Yes; events
  where it does not are listed and excluded.
- "Pace projection" at time t = N(t) + (N(t)/elapsed) * remaining. A bucket's offset = (bucket midpoint - projection)
  / bucket width. For each account: USD and PnL by offset class (<= -2, -1, 0, +1, >= +2) and by hours to the end.
- H-late (time gap): fills after the bucket is already arithmetically dead or after the window closed.
- Market description (no account): price of the eventual winning bucket 24 h, 12 h, 6 h, 2 h before the end.

## Addendum 3 (2026-11-27, before running elon_all.py) - unconditional look at the Elon post-count events

elon.py only showed events where hixlz held the winner (selection). Now ALL Elon tracker events that ended inside
the cached post range (since 2026-09-21), whatever anyone traded:
- Projection error of (a) naive pace and (b) a diurnal model (remaining = sum of hour-of-week mean rates from the
  28 days before the event start) at T-24h, T-12h, T-6h: bias and RMSE in posts.
- Price (prices-history, 5-minute) of the eventual winner at T-24/12/6/2 h.
- Exploratory rules, 9 variants = {pace bucket, pace+1, pace-1} x {T-24h, T-12h, T-6h}: buy 1 share at the
  prices-history price + 1 cent, taker fee 0.01*p*(1-p), hold to the end. prices-history is a mid/last price, not an
  ask, so this is NOT a fill test - it only says whether the idea deserves a real order-book test. Unit = event.
  Skip a variant in an event if the bucket does not exist or its price is outside 0.01-0.95.
