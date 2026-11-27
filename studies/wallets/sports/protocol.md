# Sports wallet study: protocol (written 2026-11-27 BEFORE any wallet table was read)

Question: how do the consistently profitable small-fill accounts in "sports" make money, and can a solo trader
with a few hundred dollars and one VPS copy it?

Selection rule (applied to `leaders_top60.txt` only, before any per-wallet data): >= 1,500 distinct markets all-time,
average fill <= ~$550, rebate share <= 20%, kept > 0 in at least two of the last three months including November.
Whales (few markets, fills >= $1K, or one giant month) are skipped and listed.

Hypotheses per account, each with the test fixed in advance:
- H1 pre-game model: most dollars bought BEFORE gamma `gameStartTime`/`eventStartTime`; held to settlement.
  Test: share of buy $ before start; edge per share by "before/after start".
- H2 in-play latency: taker buys during the game clustered within seconds after a scoring play.
  Test: for sampled games, ESPN play-by-play wall clock of scoring plays vs fill time (block time minus ~3 s);
  count fills inside [play, play+30 s] against a placebo window [play-60 s, play-30 s] of the same length.
- H3 post-game sweep: buys at >= 0.97 after the game is final and before resolution.
  Test: fills at >= 0.97 vs ESPN final-play wall clock (or vs the first tape print >= 0.99 if no ESPN game);
  count how many were after the final whistle, and how many of those markets lost.
- H4 market making: maker share > 70%, both outcomes of the same market bought, low net exposure.
  Test: maker share; share of markets with both sides; pair cost; markout of maker fills (price 1 and 5 minutes
  later from the market tape).
Falsification, at least one per account: the explanation must predict something the tables did not already show
(e.g. "post-game" must hold on timestamps for sampled markets; "model" must show no clustering after plays).

Accounting: fees in (0.05 * p * (1-p) per taker share since 2026-11-20; `pmlab.wallet` estimates), rebates = 0
for a copier. Unit of analysis = market; errors clustered by market (event where noted).
Variants are counted in README.md ("Variant count").
