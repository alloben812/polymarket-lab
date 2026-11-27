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
