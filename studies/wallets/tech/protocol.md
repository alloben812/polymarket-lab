# Protocol — tech category wallet study (written 2026-11-27 before looking at any wallet's fills)

Question: how do consistently profitable accounts in Polymarket "tech" markets (AI model releases, leaderboard
rankings such as "which company has the best AI model on <date>", product launches, company events) make money,
and is it copyable with a few hundred dollars and one small server? Taker fee 0.05*p*(1-p) (0.04 before 2026-11-20,
zero on 2026-10-20..31 per NOTES); rebates = 0 for us.

Hypotheses to separate (fixed before the data):
- H1 source sniping: taker buys within seconds/minutes of a public update of the deciding source (leaderboard
  refresh, official announcement, release blog post) while the book is stale. Test: for sampled markets find the
  price jump (first minute where the market tape crosses a large move) and place the account's fills relative to
  it; share of buy $ in [0, 60 s], [1, 10 min], [10 min, 6 h] after the jump and before it.
- H2 post-outcome carry ("bonding"): buys the already-determined (or nearly certain) outcome at >= 0.95 late and
  holds to resolution. Test: share of buy $ at >= 0.95, time left to end, loss rate of those positions.
- H3 informed / model long positions: buys days-weeks before the end at mid prices and holds; profit comes from the
  outcome. Test: fills far from end at 0.1-0.9, edge vs final, few markets carry the result.
- H4 market making / reward farming: high maker share, both sides, sells as well as buys, small edge per share,
  many markets at once.
- H5 not a tech account: tech is a minor part of its turnover (category board number is a by-product).

Selection rule (fixed before screening): from `tools/leaders.py tech --top 60` take accounts with
(mkts >= 150 or fills >= 1500), kept_all > 0, at least two of the last three months positive (accounts younger than
three months: all months positive), rebate share < 40%. Screen = last 30 days of fills (cap 4,000 rows); tech share
of turnover by gamma tags (tech / ai / big-tech and related) on the account's top markets. Study the five to seven
with the largest tech turnover that also look systematic (many markets, small fills). Whales (few markets, fills in
the thousands of dollars, profit from one or two bets) are skipped and listed with the reason.

Falsification (at least one per account): the stated mechanism must predict an ordering or a count that the data
can contradict (e.g. "buys after the outcome is determined" -> fill timestamp after the market's decisive price
jump in >= 80% of sampled markets; "market maker" -> both buy and sell fills as maker in most markets it touches).

Rules: read-only; unit of analysis is the market; block timestamps are 2-3 s after the match; profile numbers are
before fees; `feeSchedule` reliable only after 2026-11-20. Every variant run is counted in README.md.
