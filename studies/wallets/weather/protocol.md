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
