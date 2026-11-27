# Esports wallet study: protocol (written 2026-11-27 BEFORE any wallet table was read)

Question: how do the consistently profitable accounts in "esports" make money, and can a solo trader with a few
hundred dollars and one VPS copy it?

Selection rule (applied to `leaders_top60.txt` plus a blind screen of the last fills, before any PnL table):
>= 400 distinct markets all-time, average fill <= ~$800, rebate share <= 25%, kept > 0 in November and in at least
one more of the last three months (or every month of its life if younger), and >= 50% of its recent dollars in
esports markets (CS2, LoL, Dota 2, Valorant, other game titles). Whales, sports generalists that only touch esports,
and rewards farmers are skipped and listed.

Hypotheses per account, test fixed in advance:
- H1 pre-match model: most buy dollars BEFORE the match start (gamma `gameStartTime` / `eventStartTime`), held to
  settlement. Test: share of buy $ before start; edge per share before vs after start.
- H2 in-play latency: taker fills during the match bunched right after game events. No reachable play-by-play is
  assumed, so the event clock is the market tape itself: a "jump" = the mid of the tape moves >= 8 c within 30 s.
  Test: where do the account's taker fills sit relative to the jump (lead = account's fill is among the first
  prints of the jump, i.e. it trades at the OLD price; lag = it pays the new price)? Markout of taker fills at
  +10 s, +60 s, +300 s from the whole-market tape, against the same markout for all other takers in those markets.
- H3 post-match sweep: buys at >= 0.97 after the outcome is decided and before resolution. Test: fill time vs the
  first tape print >= 0.99 (proxy for "decided") and vs `closedTime`; count losers.
- H4 market making: maker share > 70%, both outcomes bought in the same market, low net exposure. Test: maker
  share, both-sides share, pair cost, markout of maker fills at +60 s / +300 s.
- H5 map/series structure: trades of map-winner or series markets right after a map ends (child market resolves ->
  parent series reprices). Test: timing of fills in the series market vs the last print of the map market.
Falsification, at least one per account: the explanation must predict something the summary tables did not already
show (H2: positive short markout and fills at the old price; H1: no clustering after jumps; H4: maker markout >= 0).

Accounting: taker fee 0.05 * p * (1-p) per share (pmlab.wallet estimate), rebates = 0 for a copier. Unit = market
(or match/event where stated); errors clustered by market. Every variant run is counted in README.md.
