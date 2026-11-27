# Finance category wallet study — protocol (written 2026-11-27, before looking at any wallet's fills)

Question: how do the consistently profitable accounts in the Polymarket "finance" category (stocks, indices,
commodities, earnings, IPO, "close above X") make money, and can a solo trader with a few hundred dollars and one
small server copy any of it?

## Selection rule (fixed before the screen)
1. `tools/leaders.py finance --top 60` -> leaders.txt / leaders.json (139 accounts on the merged boards).
2. Screen (`screen.py`): last 7 days of fills (cap 5,000 rows) for every board account that has >=100 markets or
   >=1,000 fills all-time. Per account: share of turnover by sub-family (finance up/down daily, close-above/range,
   earnings, hit-price, IPO/other finance, non-finance), fills per market, median price, buy share, maker share is
   measured later by pmlab.wallet.
3. Choose 5-7: kept_all > 0, at least two of the last three months positive, rebate share < 40%, >= 100 markets,
   and a real share of recent turnover in finance markets. Prefer accounts that cover different sub-families.
   Skip and name: whales (few markets, big fills, one month), rebate accounts, accounts whose money is in another
   category.

## Hypotheses to separate, per account (decided before the data)
H-gap     buys the already decided outcome after the deciding observation is public (official close 16:00 ET,
          earnings release time) and before the price reaches ~1; lag measured against the reference quote.
H-late    buys the nearly decided outcome (>= 0.90) shortly BEFORE the close and holds (a tail-risk carry, not a gap).
H-model   trades thresholds/up-down hours-days ahead when the price disagrees with a distribution implied by the
          underlying (spot + vol); holding period hours to days.
H-mm      two-sided maker, maker share > 70%, earns spread.
H-dir     directional view in a few markets (not copyable; record and move on).

## Measurements
- `python3 -m pmlab.wallet <acct> --days 14 --max-fills 60000 --json <name>.json`; compare with "API says".
- `deep.py`: per fill in finance markets: seconds to the market's deciding time (16:00 ET close of the target day,
  from gamma endDate / rules), price, role, side; per market PnL after fee (rate 0.05 finance; 0.04 before
  2026-11-20; zero 2026-10-20..31). Unit = market; errors clustered by market.
- Reference quotes: whichever public source answers from this sandbox (stooq CSV, Yahoo chart API, Nasdaq API);
  record which answered. With 1-minute or 5-minute bars: was the outcome already locked (distance to strike in
  units of remaining-time sigma) when the account bought?
- Stories: 10-20 markets per account: rules/source, deciding time, fills, later prices, outcome.
- Falsification per account, stated before the number. For H-gap: share of fills AFTER the deciding time
  (fill ts - 3 s > close) vs before; for H-late: share of >=0.90 buys that lost and whether the win rate beats the
  price paid plus fee; for H-model: edge by time-to-end bucket and whether the edge survives excluding the top 3
  markets.
- Persistence: `tools/wallet_check.py --monthly`.

## Counting
Every variant/table run is listed in README ("what was run"), including dead ends.

## Added before running the market-level gap tests (after the wallet tables, before any tape was pulled)
G1 hit markets. Universe: hit-week and hit-month markets on equity/ETF tickers (Yahoo 1-minute bars as proxy for the
   Pyth candles) traded by any studied account in the 21-day window and resolved Yes. Touch time = end of the first
   regular-session Yahoo candle whose High >= K*(1+0.001) (Low <= K*(1-0.001) for LOW) after max(market start, period
   start); the 10 bp margin is there so that the Pyth candle has certainly touched too. Stale take = taker BUY of Yes
   at <= 0.97 or taker SELL of No at >= 0.03 with match time (block time - 3 s) >= touch time. Report count, dollars
   locked net of the 0.05 fee, delay buckets, top wallets. One variant.
G2 close markets. Universe: close-day and updown-day markets (same tickers), resolved. Trades with match time after
   the session close: count, dollars, price vs outcome; and the last 5 minutes before the close. One variant.
G3 direction check for the model accounts: split every account's buys into bearish/bullish and by week and ticker;
   the "edge" explanation fails if the profit is one direction on one ticker.
