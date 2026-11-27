# Protocol (written 2026-11-27 before looking at any wallet table)

Question: how do the consistently profitable "weather" accounts make money and could a small trader copy it.

Hypotheses to be tested per account (stated before data):
- H1 "late / time gap": profit comes from fills made after the station's observed max/min already fixed the bucket
  (fill timestamp > timestamp of deciding observation). Test: for sampled daily-temperature markets, pull the station's
  observations (Iowa Mesonet ASOS, report types 3+4), compute the time when the running max first reached its final
  value, compare with every fill; split PnL into "before determined" and "after determined".
- H2 "forecast / model edge": profit comes from fills more than ~12 h before the local day ends, bought on forecast.
  Test: PnL by time-to-end bucket from pmlab.wallet; for the sample, price at fill vs final outcome.
- H3 "market making": profit from maker fills on both sides. Test: maker share and maker/taker edge tables.

Rules: fees in (weather rate 0.01*p*(1-p), rebates zero); unit of analysis = market (condition) or event-day;
numbers by time bucket are per fill but confidence statements are per market/day. Window: 14 days ending 2026-11-27
(shorter if truncated). Every script variant run is counted in README.md.
Selection rule for accounts: >= 1000 lifetime markets, average fill < ~$50, rebates < 25% of kept, at least 2 of last
3 months positive, plus one larger-ticket account as a contrast.

## Addendum 2 (written before fetching any price history, 2026-11-27)
H4 "pre-day mispricing": WrongBy1Degree's profit is concentrated in buying NO at ~0.65 before the local day starts.
If that is a market-wide bias and not this account's model, then for ALL temperature markets in our set (the union of
markets touched by the 7 accounts, ~3.7K), the YES price at the station's local midnight (est) in the band 0.20-0.60
should exceed the realised YES frequency by more than 3 cents. Test: YES price = last 30-min prices-history point at or
before est-24h, est, est+9h, est+13h; calibration table by price band; cluster by event; report first half (event dates
<= Nov 19) and second half (>= Nov 20) separately. Naive rule to cost: buy NO at (1 - YES mid) + 2c slippage, fee
0.01*p*(1-p) (current rate), hold to settlement. One variant only; anything else is reported as exploratory.
Known bias: the set contains only markets that at least one of the 7 accounts traded (far-tail buckets are missing).

## Addendum 3 (written before pulling any market tape, 2026-11-27)
H5 "latency niche size and what is left for the official feed". Unit: a kill = (market, first routine report whose value
is above the bucket top), local days from Nov 22 on (AWC receipt times available). From the full market tape take every
taker fill that is long NO (BUY No or SELL Yes) at an effective NO price < 0.985 in three windows:
  A [report time - 5 min, AWC receipt), B [AWC receipt, receipt + 60 s), C [receipt + 60 s, receipt + 15 min).
Profit of a fill = shares * (1 - NO price) - fee(0.01). Report $ and profit per window, number of kills with any fill,
top wallets. Prediction if a slow copier (polling the official source) has a chance: window C holds a material share
(> 20%) of the profit. Prediction if it is a pure speed race: > 80% in window A. One variant.
