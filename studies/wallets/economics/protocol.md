# Protocol — economics category wallet study (written 2026-11-27 before looking at any wallet's fills)

Question: how do consistently profitable accounts in Polymarket "economics" markets (CPI, jobs, GDP, Fed and other
central banks) make money, and is it copyable with a few hundred dollars and one small server?

Hypotheses to separate (decided before the data):
- H1 release sniping: taker buys in the seconds/minutes after a scheduled release (BLS 08:30 ET, FOMC 14:00 ET, ...)
  at prices that have not yet moved. Test: distance of each economics fill to the nearest scheduled release of the
  event it references; share of volume and of profit inside [0, 60 s], [1, 10 min], [10 min, 6 h] after it.
- H2 post-outcome carry ("bonding"): buys the already-determined outcome at 0.95-0.999 after the release and holds
  to resolution. Test: fills at >= 0.95 after the release timestamp, outcome known; order (release < fill) must hold.
- H3 pre-positioning from nowcasts/futures-implied odds: fills days/hours BEFORE the release, profit comes from the
  outcome. Test: fills before release, edge vs final.
- H4 market making: maker share high, both sides, sells as well as buys, small edge per share.
- H5 not really an economics account: economics is a minor part of its turnover.

Selection rule (fixed before screening): from `tools/leaders.py economics --top 60`, screen candidates with >= 150
markets or >= 1,500 fills all-time, kept_all > 0, at least two of the last three months positive, rebate share < 40%.
Screen = last 30 days of fills (cap 4,000 rows), share of turnover in economics-keyword markets. Take the five to
seven with the largest economics share and enough fills. Whales (few markets, fills in the thousands of dollars,
profit from one or two bets) are skipped and listed.

Rules: read-only; taker fee 0.01*p*(1-p) on economics (current rate; older rate not verified, flagged), rebates 0
for us; unit of analysis is the market; timestamps are block times ~2-3 s after the match.
Variants run are counted in README.md.
