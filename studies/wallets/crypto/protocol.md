# Crypto category wallet study — protocol (written 2026-11-27, before looking at any wallet's fills)

Question: how do the consistently profitable accounts in the Polymarket "crypto" category make money, and can a
solo trader with a few hundred dollars and one small server copy any of it?

## Selection rule (fixed before the screen)
1. `tools/leaders.py crypto --top 60` -> leaders.txt / leaders.json.
2. Screen (`screen.py`): last 3 days of fills (cap 4,000 rows) for every board account that has >=150 markets or
   >=1,500 fills all-time. Per account: share of turnover by sub-family (asset x up/down duration, above-X,
   range, hit-price, non-crypto), fills per market, median price, buy share.
3. Choose 5-7 accounts: kept_all > 0, at least two of the last three months positive, rebate share < 40%,
   >= 200 markets, and at least half of recent turnover outside BTC 5m (unless it does something different there).
   Prefer accounts that between them cover different sub-families. Whales (few markets, big fills, one month) and
   rebate accounts are skipped and named.

## Hypotheses to separate, per account (decided before the data)
H-speed   taker fills right after an exchange move: fill price on the side the Binance price moved to in the
          previous 1-10 s; edge decays with delay.
H-late    buys the nearly decided outcome (price >= 0.90) late in the window and holds to settlement.
H-model   buys/sells thresholds or up/down away from the end when the Binance-based fair value (pmlab.fair) or
          option-implied probability disagrees with the price; holding period minutes to days.
H-mm      two-sided maker: both outcomes in the same market, maker share > 70%, earns spread, inventory small.
H-dir     directional view held for days (not copyable; record and move on).

## Measurements
- `python3 -m pmlab.wallet <acct> --days 14 --max-fills 60000` (fewer days if TRUNCATED); compare with "API says".
- `deep.py`: for up/down fills: seconds from window start/end, Binance-based fair value at (fill time - 3 s) and at
  (fill time - 3 s - d) for d in 1,2,5,10 s; signed gap to the price to beat in sigmas; edge per share = final - price
  (buys) net of taker fee at rate 0.01 (0.05 BTC 5m/15m; 0.07 BTC 5m before 2026-11-20 23:59 UTC).
  Unit of analysis = market; errors clustered by market (pmlab.stats.ratio_cluster).
- Stories: 10-20 markets per account, with rules/source, deciding time, fills, later prices, outcome.
- Falsification per account, stated in README before the number: e.g. for H-late "the outcome was already decided
  when it bought" is tested as: share of late buys where Binance-fair at fill-3 s >= 0.95, and what share of them won.
- Persistence: `tools/wallet_check.py --monthly`.

## Counting
Every variant/table run is listed in README ("what was run"), including dead ends.
