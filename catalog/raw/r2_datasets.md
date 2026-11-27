# r2 — Inventory of public Polymarket datasets (checked 2026-11-27)

Scope: what historical data exists that this lab can test strategies on, what exactly is in it, and what I
verified by reading a sample. All checks were made on 2026-11-27 from the sandbox (HuggingFace API + range
reads of parquet files; nothing was executed from any repo).

How to read the "verified" column: **S** = I opened a real data sample and inspected columns/timestamps;
**C** = dataset card + file tree only (claims are the author's, not checked); **X** = could not read.

Local artefacts (all under `data/datasets/`, 296 MB in total):
- `_api/` — HF search results (`search_*.json`, `hf_index.json`), and for every dataset below
  `<owner>__<name>.README.md`, `.tree.json`, `.info.json`.
- `houroux/` — manifest (90 MB) + 6 sample parquet files of 2026-10-11.
- `polydata5/README.md` — the card of the gated set (the only readable file).
- `ligengxin96/` — markets, trades, book, TWAP files of the one-day sample.
- `gude/`, `kinzikdza/` — strategy reports that ship inside two datasets.
- `web/` — rocklabs README, Telonex pages, PMData public markets catalog (37.8 MB parquet), PMData GitHub README.
- `phobia76/manifest_2026-10-30T17.json` — one hourly manifest of the PendulumFlow V3 capture.
- Tools I wrote and left in `tools/`: `rpq.py` (peek at a remote HF parquet file with HTTP range requests: schema +
  one row group, no full download) and `hf_info.py` (card + paginated file tree + sizes for a list of datasets).

HF search: `https://huggingface.co/api/datasets?search=<q>&limit=100&full=true` for q = polymarket, kalshi,
"prediction market", updown, plus two-word queries (polymarket sports / weather / nba / orderbook / l2 / 250ms).
258 distinct ids for the one-word queries; the two-word queries surfaced another ~25 that the one-word query
truncated (limit 100) — so the HF list below is not exhaustive.

---

## 1. Summary table

Abbreviations: PM = Polymarket; ex-ts = exchange (Polymarket `timestamp`) time; rx-ts = collector receive time;
L2 = full depth (book snapshots + price_change deltas); TOB = top of book only.

| # | Dataset | Ver. | Markets | Dates (UTC) | What is recorded | Clock | Size / format | Licence | Still updated | Main gaps / caveats |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `chitoyuuri/polymarket-l2-v3-1-archive` (PendulumFlow V3.1 mirror) | S | ALL PM markets, split per category per hour (ai, business, crypto, earnings, economy, elections, esports, finance, geopolitics, politics, pop-culture, science, sports, sports.cfb, tech, weather, world, uncategorised) | 2026-08-18 06:00 -> 2026-11-26 20:00, 101 days, no missing day | L2: book, price_change, best_bid_ask, last_trade_price (with tx hash, fee_rate_bps), tick_size_change, new_market, market_resolved; plus `opening_state` per hour | ex-ts (ms) + `recv_lag_ms` (int ms) | 2.64 TB used storage; hourly parquet. One hour on 2026-10-20 18h: sports 207 MB, crypto 75 MB, elections 74 MB, esports 45 MB, weather 17 MB, economy 6.5 MB | CC BY-NC 4.0 | yes (card modified 2026-11-27 02:09) | binary market/asset ids; "reconstructed complementary-token rows" flagged by `mirror_dropped`; per-hour coverage audit lives upstream (archive.pendulumflow.com/audit, not read); did not verify that 5m up/down markets are in `crypto` |
| 2 | `phobia76/polymarket-l2-orderbook-archive` (PendulumFlow V3 + PMXT v1/v2 + devpyle) | S | ALL PM markets (v3, pmxt v2); pmxt v1 ~half of markets; devpyle = crypto up/down 5m/15m/1h | v3: 2026-08-18 -> 2026-10-30 18:00; pmxt v1 2026-02-21 -> 04-16; pmxt v2 2026-04-13 -> 08-10; devpyle 2026-08-15 -> 08-18 | L2 as above, three recorders merged ("witness" sets) | ex-ts (ms) + `timestamp_received` (microseconds) | 2.6 TB; v3 = one parquet of 1.5-1.9 GB per hour (148 M rows in the hour I opened) | "other" (upstream CC BY-NC; pmxt part CC BY 4.0) | no — "static historical archive" | whole-hour files only (no category split) -> heavy; receive latency buckets in the manifest are mostly 10-50 ms |
| 3 | `Houroux/polymarket-l2-history` | S | Liquidity-REWARDED markets only (top 500 by reward rate + all sponsored): on 2026-10-11 the universe was 501 slugs = 156 NFL, 21 EPL, 13 CFB, 68 "highest-temperature", precipitation, ~170 "will ..." politics/geopolitics, etc. NO crypto up/down markets | 2026-07-22 -> 2026-10-11 processed so far (82 days); the ETL is still back-filling (manifest `updated_at` 2026-11-27 15:22) | `events` (every WS message normalised: price_change 2.09 B, best_bid_ask 98 M, book 13.1 M, last_trade_price 5.3 M with tx hash, new_market, tick_size_change, market_resolved), `book_levels` (snapshots exploded to levels), `markets` (discovery with reward config, fees, tags). ALSO `rtds` (Binance + Chainlink prices for 7 coins, ~1/s each) and `sports_ws` (PM live score feed: gameId, score, period, elapsed, status; 4.4 M rows) | ex-ts ms + rx-ts ns + monotonic ns + `capture_latency_ms` | 411 GB used storage; parquet in `analytics/{events,book_levels,markets}/date=.../`; one day 2026-10-11 = 3.0 GB events | "other" (card: subject to PM terms) | yes (processing lags the calendar by ~6.5 weeks) | card says "gzip JSONL" but the repo only has the parquet analytics layer; capture latency median 61 ms (p99 94 ms) in my sample, RTDS latency ~300 ms; reconnect/stale events are logged (5.3 K disconnects over 82 days) |
| 4 | `Fahri-5/updown-5m-polymarket-raw` | S | BTC 5m up/down only | 2026-10-17 -> 2026-11-08 (23 daily files) | `polymarket/`: L2 (book with full `bids`/`asks`, price_change, last_trade_price with tx hash). `btc/`: Binance BTCUSDT trades + bookTicker and Chainlink btc/usd via RTDS | ex-ts ms + rx-ts ms on ONE collector for all three feeds | 107.8 GB parquet; PM 2.8-5.6 GB/day (53.9 M rows on 11-08, 391 row groups), btc 0.12-0.34 GB/day | CC0 | stopped: last data file 2026-11-08, last commit 2026-11-11 (README only) | Binance bookTicker rows have no exchange timestamp (rx only); "well under 1%" duplicate rows; last tens of seconds of a market often quote-less; ends before the 2026-11-20 fee change |
| 5 | `polydata5/polymarket-updown-5m-ws` | X (card only) | 5m up/down for BTC, ETH, SOL, XRP, DOGE, BNB, HYPE | BTC clob 2026-08-21..22 then 2026-09-09 -> 2026-11-26; others from 08-28 / 09-09; "92 days with data" | raw WS frames: L2 (book, price_change), last_trade_price, tick_size_change + RTDS Chainlink price and 30 s / 60 s TWAP. No Binance | ex-ts ms inside `raw` + `recv_ts` (float s) + monotonic | 598.6 GB gz JSONL; BTC_clob ~2-3.7 GB/day | CC BY 4.0 | yes, daily | **GATED (auto): every data file, `manifest.json` and `coverage.png` return HTTP 401 without a logged-in HF account that accepted the terms; only README.md is readable (via `/resolve/main/README.md`; `/raw/` is 401).** Gaps: 2026-10-12 13:15 -> 10-14 10:47 all series, 2 h on 11-01, first 0.5-12 s of each market can be missing (reconnect per market) |
| 6 | `mileswangs/polymarket-btc-updown-5m-orderbook-tick-data` (PMData free sample) | S | BTC 5m up/down, all 4,032 markets | 2026-08-08 -> 2026-08-21 (14 days) | L2 (457 M events), trades (6.7 M), on-chain fills with maker AND taker wallet (21.3 M), Chainlink Data Streams price + 60 s TWAP, markets with outcome | ex-ts + rx-ts, microseconds; collector co-located in AWS eu-west-2 | 5.6 GB parquet (l2 ~0.53 GB/day) | CC BY 4.0 | sample is fixed; vendor archive continues (paid/free-tier, account needed) | no Binance prices (join with data.binance.vision); 42 markets without `market_resolved`; older than our window but spans the TWAP change (Aug 14) and the taker delay (Aug 17) |
| 7 | `ithiria894/polymarket-l2-orderbook` | S | `crypto_updown`: 5m and 15m up/down (all coins); `crypto_all`: every crypto-tagged market (~4,600 tokens) | crypto_updown 2026-11-16 -> 11-22; crypto_all 2026-11-16 -> 11-17 in the tree; sample hour 2026-07-14 12h | L2 (books, price_changes) + trades | ex-ts ms + rx-ts (float s); two independent vantage points | 93.6 GB parquet, hourly; trades files 0.3-0.4 MB/hour | CC BY 4.0 | last commit 2026-11-22 | author's own replay check reproduced the next snapshot only 92.8% of the time; hours can be missing; no exchange prices. It is the only open set I found that straddles the 2026-11-20 fee change |
| 8 | `Ligengxin96/polymarket-predict-fun-tick-data` (outcometick sample) | S | BTC 5m on PM + BTC 5m on Predict.fun | one day, 2026-10-18 | PM: book (132,930 snapshots, full depth), price_change (3.80 M), best_bid_ask (1.14 M), trades (386,998), markets with strike + outcome, Chainlink instant + 60 s TWAP; Predict.fun order-book snapshots + settlement feed | ex-ts ms + rx-ts ms | 0.39 GB gz JSONL/CSV | CC BY 4.0 | one-off sample | one day only; good for prototyping a replay |
| 9 | `Joseph3222/polymarket-orderbook` (pmxt mirror, normalised) | C | ALL markets (v1 era ~half) | 2026-02-22 -> 2026-08-10 (06-12..06-17 absent) | raw WS stream (book, price_change, last_trade_price, tick_size_change) + 1-minute full-depth rollup | source timestamps 1 s (ms field present but intra-ms order not guaranteed) | 1.37 TB parquet (8 GB/day raw; 1.2 GB/day 1-min) | CC BY 4.0 | no (source stopped 2026-08-10) | 5-15% of hourly source files unreadable; 10-15% crossed books in naive replay; outside our window |
| 10 | `DineshKumar8399/polymarket-orderbook-dataset` | C | 314,123 markets | 2026-07-10 -> 2026-09-13 | quote observations (484 M), labels, a separate trade-price feed | not checked | 0.22 GB?? (tree shows 70 files / 0.22 GB — much smaller than the card implies; likely sampled) | CC BY 4.0 | no | card itself lists a 4-day outage, a column that dies, censored labels |
| 11 | `polyorderbooks/*` (crypto-updown-orderbooks-l2, crypto-btc-5min-250ms-l2, sports-250ms-l2, ...) | C | small promo samples: 805 crypto markets at 1 s; BTC 5m 862 markets at 250 ms (2026-10-03..06); sports: last 5 minutes of 63,081 markets resolved 2026-10-18..20 at 250 ms | see left | L2 ladder snapshots on a grid, winning outcome on each row | capture time on a grid (no ex-ts) | 14-207 MB parquet each | CC BY 4.0 | samples for a paid API | snapshots, not deltas; 3.2% crossed, 17% one-sided snapshots on 5m |
| 12 | `whodisidk/polymarket-btc-updown-exchange-data` | C | BTC up/down 5m/15m/1h | 2026-05-25 -> 2026-08-29 (67 of ~97 days) | 100 ms grid: PM + Hyperliquid book snapshots, Binance/Hyperliquid trades and reference price, features, lifecycle, resolutions | grid timestamps | 41.6 GB (daily tar.gz of parquet) | none stated | no | Binance bid/ask missing; snapshots may repeat stale state; trades incomplete |
| 13 | `whodisidk/polymarket-btc-updown-market-data` | C | BTC up/down 5m/15m/1h/4h | 2026-03-27 -> 2026-05-24 | ~125 ms book snapshots + oracle price; NO trade prints | irregular ~125 ms | 17.4 GB | none stated | no | "not execution-complete history" |
| 14 | `trentmkelly/polymarket_crypto_derivatives` | C | BTC/ETH/SOL/XRP 5m and 15m, 46,990 episodes | 2026-02-21 -> 2026-03-24 | ~100 ms decision snapshots with `chainlink_price` AND `binance_price` on the same row, CLOB events (3.64 B), full depth per step | ms | large (tree > 40 K files, not sized) | CC BY-SA 4.0 | no | old (before fees/TWAP/taker-delay changes) |
| 15 | `kachoio/polymarket-5-minute-crypto-up-down-markets` | S | 5m up/down, 7 coins, ~89 K markets | BTC 2026-03-24 -> 05-18; others from 04-05 | 1-second TOB (bid/ask + sizes + depth totals) | sample second | 0.73 GB parquet | CC0 | no | outcome inferred from last tick, not from resolution; write-up at kacho.io/polymarket-5min-crypto-dataset (not read) |
| 16 | `aliplayer1/polymarket-crypto-updown` | S | 7 coins x 5m/15m/1h/4h | data ends 2026-04-26 (card claims "updated every 3 hours"; last data commit 2026-04-26) | TOB with sizes (`local_recv_ts_ns`), on-chain + WS trade ticks with Binance spot at trade time, Binance + Chainlink spot at 1 s | ex-ts ms + rx ns | 29 GB (orderbook 23.6 GB; BTC 5m file 9.4 GB, 3.9 B rows) | MIT | no | TOB only; stale |
| 17 | `marketlens/polymarket-btc-5m-l2-depth` | C | BTC 5m, 288 markets | one day 2026-06-15 | snapshots + 41.6 M level deltas + 681 K trades | ms | 0.31 GB | CC BY 4.0 | sample | one day |
| 18 | `MAICHEN/polymarket-btc1h` | X | BTC 1-hour up/down + `binance_btcusdt_1s` | 2025-10 -> 2026-08 | per-market `_full` and `_trades` parquet | ? | 95 GB | MIT | modified 2026-11-25 | gated (manual approval) |
| 19 | `SII-WANGZJ/Polymarket_data` | C | ALL markets (4.0 M), on-chain | 2022-11-21 -> 2026-10-04 | every OrderFilled event (V1 + V2 exchanges), trades with market linkage, per-user view, markets metadata (with `neg_risk`) | Polygon block time (s) | 279 GB, five parquet files (trades.parquet 45.8 GB) | MIT (GitHub) | periodic releases (last 2026-10-05) | single huge files (range reads work); block time is 2-3 s after the match |
| 20 | `TimeSeventeen/Polymarket-v1` (arXiv 2606.04217) | C | ALL markets on the V1 exchange | 2022-11-21 -> 2026-04-28 | OrderFilled tape (1.2 B rows), cleaned daily layers (binary / neg-risk), CTF splits/merges/redemptions/resolutions | block time | 52.7 GB | CC BY 4.0 | CTF layer touched 2026-11-24; trade tape ends with V1 | stops at the V2 migration (2026-04-28) |
| 21 | `vgregoire/polymarket-users` (Akey, Gregoire, Harvie, Martineau, SSRN 6443103) | C | ALL users | 2022-11-11 -> 2026-03-29 | trades, daily PnL per user (with/without fees, by category), 87 behavioural features, OHLCV 5m/1h/1d | block time | 118.7 GB | CC BY 4.0 | no | ends March 2026 |
| 22 | `epinnock/polymarket-nba` | C | every NBA market (66,056 markets) | 2024-04 -> snapshot 2026-10-08 | price points (82.9 M) + trades from the Data API (10 M) | Data API time | 1.14 GB | CC BY 4.0 | snapshot | prices, not books |
| 23 | `paperswithbacktest/PredictionMarkets-*` | X | PM trades / prices (daily, hourly) | 2022-11 -> 2026-11 | monthly trade parquet etc. | ? | 16.7 GB (trades) | "other" | yes | gated (manual): data 401, README readable |
| 24 | `gude/polymarket-wallet-activity` | S (reports) | BTC/ETH/SOL/XRP 5m; five wallets | activity exports to 2026-07 | per-wallet activity JSONL + strategy-decode reports + backtests | Data API | 24 GB | "other" | no | PnL figures in its reports contradict the Data API (see section 4) |
| 25 | `kinzikdza/polymarket-updown-microstructure` | S (FINDINGS.md) | up/down 5m/15m, 4 coins | to 2026-06 | book snapshots, PM trades, slots + a negative-results report | ? | 2.2 GB | CC BY 4.0 | no | see section 4 |
| 26 | Kalshi: `TimeSeventeen/Kalshi` | C | all Kalshi trades by day | 2021-06-30 -> 2026-11-24 | daily trade parquet (~0.5 GB/day now) | Kalshi time | 77.5 GB | none stated | yes | trades only |
| 27 | Kalshi: `KalshiEye/kalshi-order-book-sample` | C | KXBTC15M, KXETH15M, KXFEDDECISION, KXHIGHNY, KXINXU, KXMLBGAME, KXNFLGAME | 2026-10-13 and 2026-10-25 | BBO + trades | ? | 1.28 GB | CC BY-NC 4.0 | sample | two days |
| 28 | Kalshi: `RooseveltHonaker/kalshi-trades-data` | C | Kalshi trades | to 2026-11-27 | raw JSONL | ? | 247.8 GB | none | yes | undocumented (README 794 bytes) |
| 29 | `Coyevans/mlb-polymarket-kalshi-matched-book-sample`, `Coyevans/polymarket-kalshi-scoresync-orderbook-sample` | C | one MLB game (2026-06-21) PM vs Kalshi; one NBA game with score-synced Kalshi TOB | single games | matched TOB quotes; score state per row | ? | < 1 MB | CC BY-NC 4.0 | promo for a paid archive (ZenHodl) | tiny |

Other HF ids seen but not opened (name / downloads / last modified): `lowskillcoding/pdata-prediction-markets`
(resolved + open markets snapshot, 11-23), `od2961/polymarket-full-market-dataset` (184 GB JSON, 07-13),
`yamalalaxman/btc-updown-5m-trades` (26 GB, 04-29..05-20), `papylove/kalshi-15m-data`, `DegenHedge/kalshi-btc-15m`
("signals.csv", promo-looking), `thePredictables/kalshi-live-news` (230 MB news + labels, 10-30),
`iiiitips/prediction-market-pro-stats`, `dvegenen883/polymarket-btc-updown-btc-chainlink`, `phobia76/pmxt-l2-dump`,
`kartikbathla/polymarket-crypto-up-down-5min-15min-market-orderbook-l2-data`, `MAICHEN/Polymarket-Sports-L5`,
`MAICHEN/Polymarket-EPL-NBA-Quotes`, `Karmane/polymarket-sports-lines-and-player-props`, `wangdx25/*` (TsFile copies
of paid-vendor previews), `astrnvk/polymarket-orderbook-data-preview`, `kishan51/polymarket-l2-research`.

---

## 2. What I verified by reading samples (numbers)

### 2.1 Houroux/polymarket-l2-history (sample: 2026-10-11)
- Card (https://huggingface.co/datasets/Houroux/polymarket-l2-history, author "Houroux", created 2026-07-22):
  "Append-only archives of public Polymarket CLOB WebSocket messages for markets eligible for liquidity rewards...
  No wallet data".
- `analytics/manifest.json` (90 MB, `updated_at` 2026-11-27T15:22:29Z): 36,717 processed source files:
  market_ws 16,632 (115.7 GB raw gz), rtds 7,746, sports_ws 7,730, discovery 4,609. Totals: events 2,300,728,273
  rows, book_levels 1,037,046,984, markets 8,588,670. Days 2026-07-22 .. 2026-10-11 (82, none missing).
  `processed_at` ranges 2026-07-31 .. 2026-11-27 -> still being back-filled.
- Event counts (whole manifest): price_change 2,085,023,220; best_bid_ask 98,116,177; rtds update 91,556,097;
  book 13,107,148; last_trade_price 5,294,038; sports_ws 4,412,166; new_market 2,331,374; tick_size_change 130,991;
  market_resolved 33,612; market_ws disconnected 5,345; rtds stale 2,210.
- `events` schema (42 columns): sequence, received_at_ns, received_monotonic_ns, connection_id, event_type,
  exchange_timestamp_ms, capture_latency_ms, market, asset_id, side, price, size, best_bid, best_ask, spread,
  tick_size, last_trade_price, fee_rate_bps, transaction_hash, book_hash, symbol, reference_value, game_id, slug,
  status, score, period, elapsed, live, ended, payload_json (the raw message).
- One market_ws file (12.3 MB): 160,109 rows covering 2026-10-11 00:26:54 -> 00:29:02 (2 minutes), 44 markets /
  81 tokens; price_change 155,042, best_bid_ask 4,824, book 178, last_trade_price 49. `capture_latency_ms`
  p1 / p50 / p99 = 59.3 / 60.8 / 93.6 ms (so the collector sits ~60 ms from London).
- `book_levels` schema: sequence, received_at_ns, exchange_timestamp_ms, market, asset_id, side, price, size,
  source_rank — full ladders (I saw rank 30 at 0.51 with 121,200 shares).
- rtds file: 12,500 rows / 15 minutes; symbols btcusdt, ethusdt, solusdt, xrpusdt, bnbusdt, dogeusdt (topic
  `crypto_prices`, i.e. Binance) and btc/usd, eth/usd, sol/usd, xrp/usd, bnb/usd, doge/usd, hype/usd, zec/usd (topic
  `crypto_prices_chainlink`); one update per second per symbol per source; latency ~300 ms.
- sports_ws file: 421 rows / 15 minutes; payload example
  `{"awayTeam":"MIN","homeTeam":"NO","leagueAbbreviation":"nfl","period":"Q4","elapsed":"7:01","score":"23-13","status":"InProgress","live":true,...}`.
  This is Polymarket's own score feed stamped on the same receive clock as the books -> score-to-book lag is
  measurable for NFL/EPL/CFB without any other data source (the lag of that feed versus the real event is NOT
  measurable from it).
- `markets` (discovery) table: 60+ columns incl. daily_reward, rewards_max_spread_cents, rewards_min_size,
  market_competitiveness, volume_24hr, fee_rate, neg_risk, taker_order_delay_enabled, tags. Example row:
  "US x Iran ceasefire continues through October 31?" daily_reward 3000, max spread 4.5 c, min size 200.
- File rotation is at most 15 minutes; on 2026-10-11 there were 248 market_ws files, max gap between file
  starts 901 s, five collector ids.

### 2.2 Fahri-5/updown-5m-polymarket-raw (sample: 2026-11-08)
- Card (author Fahri-5, pipeline https://github.com/fahri-05/updown-5m-predictor, not opened): "Raw, tick-level
  market data collected to build machine learning models that predict the UP / DOWN outcome... No trading is
  executed". "Daily publication starts on 2026-10-17". "The last tens of seconds of each market often have no
  Polymarket quotes, because market makers pull liquidity before resolution."
- `polymarket/2026-11-08.parquet`: 3.10 GB, 53,934,795 rows, 391 row groups, 28 columns (timestampMs, conditionId,
  tokenId, outcome, bestBid, bestAsk, exchangeTimestampMs, receivedTimestampMs, eventType, hash, bidPrice/Size,
  askPrice/Size, tradePrice, tradeSize, tradeSide, transactionHash, bids[], asks[]).
  Row group 40 (142,630 rows, 02:46:39 -> 02:50:50, 2 markets): price_change 141,721, last_trade_price 907, book 2;
  received - exchange = p5 / p50 / p95 = 11 / 13 / 44 ms. Book snapshot had the full ladder (0.01 .. 0.99).
- `btc/2026-11-08.parquet`: 118 MB, 4,604,885 rows, 28 row groups. Row group 0 = 107,684 rows for 00:00-01:00
  (~30 rows/s). Sources: binance `book` (bookTicker: bid/ask price + qty, updateId, receive time only), binance
  `trade` (price, qty, tradeId, exchange ms and receive ms; receive - exchange ~128 ms in my small sample),
  chainlink `ticker` (1/s; receive - price time ~1.4 s).
- All three feeds share `receivedTimestampMs` from one machine -> the lag of the PM book behind Binance can be
  measured directly on the receive clock at ~10 ms resolution.

### 2.3 mileswangs/polymarket-btc-updown-5m-orderbook-tick-data (sample: 2026-08-21)
- Card (PMData, pmdata.dev; last commit 2026-11-22): "Collected colocated with Polymarket in AWS London at 4.6 ms
  median latency, over two redundant WebSocket connections per market"; "From 2026-08-14 on, the TWAP reproduces
  2,263 of 2,265 recorded outcomes".
- `l2/date=2026-08-21/part-0.parquet`: 532 MB, 49,664,958 rows, 100 row groups. Row group 50 (500,000 rows,
  11:43:02 -> 12:02:32, 4 markets): price_change 494,497, book 5,496; local - exchange p5 / p50 / p95 =
  3.6 / 5.0 / 26.3 ms (matches the card's 4.9 ms).
- `onchain_fills`: 1,961,902 rows that day; columns market_slug, timestamp (block), maker, taker, outcome,
  maker_side, taker_side, price, usd_amount, token_amount, transactionHash, _log_index.
- Vendor terms quoted from the card: free account = "600 downloads at sign-up, then 50 per month, for data older
  than 3 weeks"; coverage "crypto Up/Down markets from 2026-03-28 and every other Polymarket market from 2026-05-01".
- The free catalog `https://public-data.pmdata.dev/v1/polymarket/markets.parquet` needs no key; I downloaded it
  (5,308,862 markets). By top-level series: sports 3,829,469; updown 864,995; strike 218,809; weather 176,012;
  none 132,267; gs 77,769; elections 6,073; culture 2,613; earnings 855. Last record day 2026-11-26 for all.
  (Using the archive itself needs an account -> owner decision, not done here.)

### 2.4 PendulumFlow archives
- `phobia76/...` v3 hour 2026-10-30T17: 1.53 GB, 148,017,101 rows, 569 row groups, 30 columns (event_type,
  timestamp_received [us], sequence, timestamp [ms], market, asset_id, best_bid, best_ask, spread, bids[], asks[],
  price, size, side, fee_rate_bps, transaction_hash, question, slug, winning_outcome, witness_set, arrival_skew,
  source_witness...). Manifest of that hour: price_change 129.4 M rows, best_bid_ask 18.2 M, book 261 K,
  last_trade_price 64.8 K, new_market 3,255, market_resolved 1,187; three recorders (i, o, p); latency buckets
  dominated by 10-20 ms and 20-50 ms.
- `chitoyuuri/...` V3.1 (card: "mirrored from the PendulumFlow Polymarket Orderbook Archive", CC BY-NC 4.0):
  day directories 2026-08-18 .. 2026-11-26 with no missing day; 2026-11-26 has hours 00..20. Weather file of
  2026-10-20 18h: 16.7 MB, 2,597,119 rows, 29 columns incl. `category`, `sub_tag` (saw "highest-temperature",
  "brazil", "volcano"), `recv_lag_ms` (21-33 ms in the rows I saw), `mirror_dropped`, `row_ordinal`.
  A full day of weather L2 is therefore ~0.4 GB, sports ~5 GB, crypto ~1.8 GB.
- Upstream: https://archive.pendulumflow.com/ (formats, audit) and https://x.com/pendulumflow — not opened.

### 2.5 Ligengxin96 one-day sample (2026-10-18)
- trades: 386,998 rows; recv - event p5 / p50 / p95 = 6 / 9 / 45 ms. markets: 292 rows with `strike_value`
  (1e18-scaled) and `outcome_prices`. book: 132,930 snapshots (34 bid / 65 ask levels in the row I opened).
  TWAP csv: feed_ts_ms, value, full_accuracy_value, server_ts_ms, recv_ms (recv ~1.3 s after the price time).

### 2.6 Others opened
- ithiria894 trades 2026-11-22 08h: columns capture, asset_id, ev_ts (ms), market, price, recv_ts, side, size;
  recv - ev ~54 ms.
- kachoio btc_ticks: 4,704,518 rows, last tick 2026-05-18 10:34:59; columns bu/au/bd/ad (best bid/ask up/down),
  su/sd/sau/sad (sizes), du/dd (depth).
- aliplayer1 BTC 5-minute orderbook: 3,939,746,464 rows, last ts 2026-04-25/26; TOB only.

---

## 3. Recommendation

### (a) Reaction lag of the crypto up/down books to exchange prices, sub-second
1. **Fahri-5** is the only open set with Binance trades + bookTicker, Chainlink and the full PM book on one
   receive clock inside our window (2026-10-17 .. 11-08, 23 days, BTC 5m). One PM day is 3-5.6 GB but is
   row-group addressable (`tools/rpq.py` reads a 4-minute slice for ~10 MB). Suggested protocol: Binance mid jumps
   of >= X bp within 100 ms -> time until PM best bid/ask on the corresponding side moves, measured on
   `receivedTimestampMs`; cluster by market.
   Limits: ms resolution, collector ~13 ms from PM and ~130 ms from Binance (a co-located player sees Binance
   earlier relative to PM than this collector did only if it is nearer to Binance; the measured lag is the lag
   *as seen from that server*), stops before the Nov 20 fee change.
2. **mileswangs/PMData sample** (2026-08-08..21) for the cleanest PM-side timing (5 ms, microseconds) and for
   on-chain maker/taker attribution; join Binance from `data.binance.vision` aggTrades (exchange timestamps, so the
   comparison is exchange-time vs exchange-time, which removes collector distance). Covers the day the taker delay
   went live (Aug 17) -> before/after comparison.
3. **ithiria894** (2026-11-16..22) for the same measurement after the fee change (join Binance dumps).
4. **polydata5** would be the longest BTC/ETH/SOL/XRP series (to 2026-11-26) but is gated; reading it needs the
   owner's own HF account (click-through, automatic approval). Not possible from this sandbox.
5. Prototyping day: **Ligengxin96** (0.39 GB).
   Older regimes only (mechanism reference): trentmkelly (Feb-Mar, Binance and Chainlink price on each 100 ms row),
   whodisidk (May-Aug, 100 ms grid).

### (b) Fills against real depth
- Crypto 5m: mileswangs (L2 + trades + on-chain fills with both wallets: one can check whether a resting order at
  a given level would have been reached and who actually got the fill), Fahri-5, ithiria894.
- Everything else: **PendulumFlow V3.1** (per-category hourly files, to 2026-11-26) and **Houroux** (rewarded
  markets, with reward parameters per market -> rewards-farming simulations; to 2026-10-11 for now).
- None of these gives queue position; a maker fill can only be asserted when a later trade printed THROUGH the
  level (rule 4 of NOTES.md), and the taker delay of 50 ms on crypto must be added by hand.

### (c) Other categories (sports, weather, economics, elections)
- **PendulumFlow V3.1**: weather ~17 MB/hour, sports ~207 MB/hour, economy ~6.5 MB/hour, with `sub_tag`.
  Join weather to Iowa Mesonet / api.weather.gov observations, sports to ESPN play-by-play (both reachable).
- **Houroux**: NFL/EPL/CFB + temperature markets with the PM `sports_ws` score feed on the same clock.
- On-chain trade tapes for wallet-level work: **SII-WANGZJ** (to 2026-10-04, V2 exchange included) and the Data
  API for anything later.
- Kalshi side for cross-venue: TimeSeventeen/Kalshi (trades to 2026-11-24), KalshiEye sample (two days of BBO).

### Not found / not available
- No Kaggle dataset turned up in WebSearch (one author's repo contains an `upload_to_kaggle.py`, so mirrors
  may exist; none located).
- No open dataset with Binance + PM book on one clock AFTER 2026-11-08.
- Vendors (not free in bulk): Telonex (telonex.io: trades/quotes/books "from Oct 11, 2025", Binance spot "from Feb
  6, 2026", "5 trial downloads"), PMData (above), PolyOrderbooks (paid API, HF samples), Rocklabs
  (github.com/rocklabs-io/polymarket-dataset: "34B+ records", tick-level "Feb 2026 – Present", "free access ... for
  students and academic researchers" on request by e-mail), outcometick.com, Apify actor `dirtycode/polymarket-api`.

---

## 4. Strategy descriptions that ship inside datasets

### 4.1 gude/polymarket-wallet-activity (HF, last modified 2026-07-14; author "gude")
Files read: `README.md`, `wallet_uuddlrlr/reports/STRATEGY_DECODE_BTC_82d.md`,
`Codex_Experiment/docs_src_preserved/reports/{CROSS_WALLET_SYNTHESIS,RECONSTRUCTED_STRATEGY_SPEC,BACKTEST_RESULTS}.md`
(generated 2026-06-09), `.../03_live_execution_sim/REPLAY_RESULTS_TIER_1_2.md` (2026-04-26). Copies in
`data/datasets/gude/`. Not read: PER_WALLET_SUMMARY, LIVE_TRADING_SPEC_EEBD_CLONE, RULE_MINING_REPORT, ETH decode.

Wallets named in the README: 0xb27bc932bf8110d8f78e55da7d5f0497a18b5b82, 0xeebde7a0e019a63e6b476eb425505b7b3e6eba30,
0xe1d6b51521bd4365769199f392f9818661bd907c, 0x885278f0e304bc2d53f805af2ab779cb6011c569,
0xa8ccda0419f357f819271437efb61022f01341a9 ("UUDDLRLR").

Claims (quoted / closely paraphrased):
- UUDDLRLR, BTC 5m, 82 days, 17,839 sessions: "Total trade P&L (post-fees) $19,269.03; Pre-fees $99,654.32;
  Estimated fees paid $80,385.29"; win rate 53.2%; buys only, no sells, no merges; classes: pair_arb 10,169
  sessions -$5,737, pair_with_lean 5,557 sessions +$11,197, skewed_pair +$7,198, directional 1,072 sessions +$6,106;
  "Average pair edge -0.006%"; directional hit rate 84.09%; L2 cross-reference on 75 sessions: maker share 47.9%,
  taker 44.2%; trades spread evenly over the 5 minutes.
- Cross-wallet synthesis: all three big wallets "enter within seconds of window open", are "maker-heavy (57-62%
  maker share)", keep trading through the last 30 s, redeem after resolution.
  - 0xe1d6 "passive pair-arb maker": pair edge +2.9-3.8%, residual lean uninformed (hit ~49%); "stopped trading BTC
    2026-05-04". Spec A: quote maker bids on the deficit side while `yes_bid + no_bid <= 0.95`, t < 270 s, stop when
    worst-case PnL >= +$5..15, never pay pair cost > 1.0, hold to resolution.
  - 0xb27b "micro-unit maker pair+MERGE recycling machine": $0.1-0.6 clips, buys the cheap side first, MERGE to
    recycle capital. "Prior 'oracle-lag exploit' claim REFUTED on full data (median gap at trade $4-12, not $52.8;
    first-dir side has zero alpha vs winner at 49.7%)". "backtest with taker-ish fills and no rebates is NEGATIVE
    (-$3.7/session): do not copy without that stack."
  - 0xeebd "conviction-sized directional trader": opens at ~6 s on the side winning vs strike on the Chainlink
    oracle ("80-82% behavioral match from sign(chainlink − strike) alone"), ~60% of fills maker. "P(winner ==
    strike-sign) rises 55%→64% between t=5s and t=60s, but the ask on that side reprices in lockstep — gross edge
    ≈ +2-3 cents/$1 at ALL entry times, ≈ +1 cent after taker fees." Backtests: "dominance-chasing v1 = −$84/session;
    decoded strike-rule taker v2 = −$5/session".
  - "Taker-only replication of maker edges: naive taker pair-arb nets +$0.10 per session (fees consume the edge)".
- Their backtest table (pessimistic fill model): recon_e1d6 +$6.76/session over 1,358 sessions (first fill at
  114 s vs the wallet's 18 s; win rate 62.9% vs 90.9%), recon_b27b -$3.83, recon_eebd -$104.96,
  recon_eebd_v2 -$5.49, "clone_eebd_v3" +$128.28/session (99.6 fills per session — not credible without a queue
  model; the same file calls its fills Bernoulli p=0.30 at top of book).
- Their wallet PnL table claims IS / OOS PnL of $1.44 M / $5.33 M (0xb27b), $4.42 M / $0.83 M (0xe1d6),
  $13.8 M / $18.4 M (0xeebd).

My checks (`python3 -I tools/wallet_check.py <addr> --monthly`, 2026-11-27):

| wallet | profile PnL (before fees) | taker fees | after fees | rebates + rewards | "economic_pnl" field | volume | active |
|---|---|---|---|---|---|---|---|
| 0xa8cc (UUDDLRLR) | 114,560 | -114,612 | -53 | 14,894 (all taker rebate) | 14,842 | $4.82 M | 2026-04 .. 07, nothing since |
| 0xeebd | 1,467,139 | -2,524,009 | -1,056,869 | 679,046 (taker 513 K, maker 162 K) | 530,523 | $170.4 M | 2026-03 .. 11 (still active, Diamond tier) |
| 0xb27b | 809,914 | -3,512,985 | -2,703,071 | 770,368 (maker 661 K, rewards 65 K) | 1,257,760 | $140.2 M | 2026-03 .. 09 |
| 0xe1d6 | 781,581 | -1,718,946 | -937,365 | 40,754 | 326,092 | $35.7 M | 2026-03 .. 05 |
| 0x8852 | 320,366 | -177,655 | 142,711 | 42,918 | 363,267 | $15.5 M | 2025-12 .. 2026-11 (still active) |

Monthly net (gross + fees + rebates), from the tool:
- 0xa8cc: Apr -97; May +15,742; Jun -10,701 (-17,008 before rebates); Jul +9,897 (+1,310 before rebates).
- 0xeebd: Mar -166 K; Apr -742 K; May +141 K; Jun +38 K; Jul +92 K; Aug +121 K; Sep +55 K; Oct +37 K; Nov +46 K.
  Net WITHOUT rebates is negative in every month from June on (-54 K, -60 K, -65 K, -34 K, -8 K, -17 K).
- 0xb27b: Mar -1,407 K; Apr -1,219 K; May +98 K; Jun +143 K; Jul +80 K; Aug +191 K; Sep +182 K. Without rebates:
  +59 K, +37 K, -21 K, -27 K, +45 K (May..Sep).
- 0xe1d6: Mar -294 K; Apr -628 K; May +25 K.
- 0x8852: zero taker fees from May on (pure maker); gross by month May..Nov: +34.6 K, +48.4 K, +24.1 K, -2.5 K,
  +8.4 K, +2.8 K, +8.1 K; rebates only 0.7-6.8 K per month; monthly volume falling from $2.06 M to $0.37 M.

What this shows:
- The dataset's PnL table is wrong by an order of magnitude (it claims $18.4 M in 30 days for 0xeebd; the Data API
  shows $1.47 M before fees over the wallet's whole life). Treat every dollar figure in those reports as unreliable;
  the behavioural descriptions (timing, maker share, side rule) are the usable part.
- UUDDLRLR is exactly break-even after fees (-$53 on $4.8 M); everything it kept is taker rebate, and it stopped
  in July.
- 0xeebd (directional on the oracle sign) lives on rebates since June.
- The only one of the five that is positive before rebates in most months and still trading is 0x8852, a
  zero-fee (maker-only) account whose monthly result is shrinking.

**Tool caveat found while doing this:** for four of the five wallets `trade_pnl + fees + rebates` does NOT equal
the API's `economic_pnl` (0x8852: 185,629 vs 363,267; 0xe1d6: -896,611 vs 326,092; 0xb27b: -1,932,703 vs
1,257,760; 0xeebd: -377,823 vs 530,523). For 0x8852 the gap (177,638) equals its total fees (177,655), all of
which were charged before May 2026; the gaps of the others are of the size of their March-April 2026 fees. So
either the `fees` series before the V2 exchange (live 2026-04-28 per the SII-WANGZJ card) is not a real cash
charge, or `economic_pnl` ignores it. Until that is settled, the March-April "net" rows above and any wallet_check
result for accounts active before May 2026 should be read with that doubt. For 0xa8cc (active May-July) the
identity holds to the dollar.

### 4.2 kinzikdza/polymarket-updown-microstructure — FINDINGS.md (dated 2026-06-25)
A negative-results report shipped with the data. Quotes: "Across an exhaustive search of taker signals, a full
physics-regional sweep of the maker side, an active cancel-race simulation, and replication against two independent
external corpora, no signal-based strategy clears the realizable bar — taker or maker, passive or active."
"Paper-fills at the displayed quote overstate edge ~10× via fill self-selection (you fill the losers, get rejected
on the winners)." Taker grid of 5,161 configurations: one survivor, n = 63, ~1 trade/day. Passive maker against
the real tape, 17 regions: "Zero of 17 regions are positive. A resting bid always fills ~10–20pp below its true win
probability" (e.g. favourite, distance < 20 bp, <= 60 s to close: bid 0.957, P(win | fill) 85.4%, edge -0.089).
"every directional taker we shipped died live (momentum, entropy, velrider, flip)". Not re-computed by me; it
agrees with this lab's own BTC 5m findings in NOTES.md. Pre-dates the TWAP settlement, taker delay and fee changes.

---

## 5. Sources (URL, date, author)

- https://huggingface.co/datasets/Houroux/polymarket-l2-history — created 2026-07-22, modified 2026-11-27, Houroux.
- https://huggingface.co/datasets/polydata5/polymarket-updown-5m-ws — created 2026-10-24, modified 2026-11-27, polydata5 (gated).
- https://huggingface.co/datasets/Fahri-5/updown-5m-polymarket-raw — created 2026-10-18, last commit 2026-11-11, Fahri-5.
- https://huggingface.co/datasets/mileswangs/polymarket-btc-updown-5m-orderbook-tick-data — created 2026-10-14, modified 2026-11-22, mileswangs (PMData); https://raw.githubusercontent.com/mileswangs/polymarket-historical-data/main/README.md; https://public-data.pmdata.dev/v1/polymarket/markets.parquet.
- https://huggingface.co/datasets/chitoyuuri/polymarket-l2-v3-1-archive — modified 2026-11-27, PendulumFlow mirror.
- https://huggingface.co/datasets/phobia76/polymarket-l2-orderbook-archive — modified 2026-11-24, PendulumFlow / pmxt mirror.
- https://huggingface.co/datasets/ithiria894/polymarket-l2-orderbook — modified 2026-11-22.
- https://huggingface.co/datasets/Ligengxin96/polymarket-predict-fun-tick-data — created 2026-09-11, modified 2026-10-22 (outcometick.com).
- https://huggingface.co/datasets/Joseph3222/polymarket-orderbook — modified 2026-09-02 (source https://archive.pmxt.dev/).
- https://huggingface.co/datasets/DineshKumar8399/polymarket-orderbook-dataset — modified 2026-09-13.
- https://huggingface.co/datasets/polyorderbooks/polymarket-crypto-updown-orderbooks-l2 (2026-08-25, DOI 10.5281/zenodo.22084114), .../polymarket-crypto-btc-5min-250ms-l2 (2026-10-06), .../polymarket-sports-250ms-l2 (2026-10-20).
- https://huggingface.co/datasets/whodisidk/polymarket-btc-updown-exchange-data and .../polymarket-btc-updown-market-data — 2026-09-12.
- https://huggingface.co/datasets/trentmkelly/polymarket_crypto_derivatives — 2026-05-12, trentmkelly.
- https://huggingface.co/datasets/kachoio/polymarket-5-minute-crypto-up-down-markets — 2026-06-17, kachoio.
- https://huggingface.co/datasets/aliplayer1/polymarket-crypto-updown — data to 2026-04-26, card edited 2026-09-17.
- https://huggingface.co/datasets/marketlens/polymarket-btc-5m-l2-depth — 2026-09-17.
- https://huggingface.co/datasets/MAICHEN/polymarket-btc1h — modified 2026-11-25 (gated, manual).
- https://huggingface.co/datasets/SII-WANGZJ/Polymarket_data — release 2026-10-05, Zhengjie Wang et al. (Shanghai Innovation Institute).
- https://huggingface.co/datasets/TimeSeventeen/Polymarket-v1 — Boka Qin, Rui Yang, arXiv 2606.04217; modified 2026-11-24.
- https://huggingface.co/datasets/vgregoire/polymarket-users — Akey, Gregoire, Harvie, Martineau (SSRN 6443103); modified 2026-07-06.
- https://huggingface.co/datasets/epinnock/polymarket-nba — 2026-10-08.
- https://huggingface.co/datasets/paperswithbacktest/PredictionMarkets-Daily-Trades — modified 2026-11-27 (gated, manual).
- https://huggingface.co/datasets/gude/polymarket-wallet-activity — modified 2026-07-14, gude.
- https://huggingface.co/datasets/kinzikdza/polymarket-updown-microstructure — 2026-06-25, kinzikdza.
- https://huggingface.co/datasets/TimeSeventeen/Kalshi (2026-11-25), .../KalshiEye/kalshi-order-book-sample (2026-11-13), .../RooseveltHonaker/kalshi-trades-data (2026-11-27), .../Coyevans/mlb-polymarket-kalshi-matched-book-sample (2026-07-09), .../Coyevans/polymarket-kalshi-scoresync-orderbook-sample (2026-07-06).
- https://raw.githubusercontent.com/rocklabs-io/polymarket-dataset/main/README.md — Rocklabs, undated.
- https://telonex.io/datasets and https://telonex.io/data/polymarket — Telonex, read 2026-11-27.
- WebSearch (two queries, 2026-11-27) for Kaggle / GitHub dumps: results pointed to the HF sets above, Telonex,
  PolyOrderbooks (pypi.org/project/polyorderbooks), Apify `dirtycode/polymarket-api`, rocklabs, Envio, Bitquery; no
  Kaggle dataset.

---

## Verification pass (sceptic check, 2026-11-27)

Scope: the four candidates of section 4 and the five wallets behind them. The dataset inventory (sections 1-3) was
NOT re-checked; its S/C/X marks stand as the researcher's.

### What I opened myself
- `gude/polymarket-wallet-activity` straight from HuggingFace (`/resolve/main/...`): README, CROSS_WALLET_SYNTHESIS,
  RECONSTRUCTED_STRATEGY_SPEC, BACKTEST_RESULTS, STRATEGY_DECODE_BTC_82d (all four byte-identical to the copies in
  `data/datasets/gude/`), plus three files the researcher did not read: `METHODOLOGY.md`,
  `00_reference_audit/METRIC_AUDIT.md`, `wallet_0xeebd/reports/EEBD_CLONE_REPORT.md`. HF API: created 2026-06-13,
  last modified 2026-07-14, not gated. All quoted numbers in the four candidates are in the files as quoted.
- `kinzikdza/.../FINDINGS.md` live copy = local copy; "Zero of 17 regions", 5,161 configurations, n=63 are there.
- `wallet_check.py --monthly` on all five addresses; gamma `/tiers` and `/v1/maker-tier/tiers`; `pmlab.wallet` on
  0x8852 (5 days) and 0xeebd (3 days); gamma public-search (UUDDLRLR -> 0xa8cc...41a9, exact name match).

### Corrections
1. **The March-April "net" rows of section 4.1 are wrong, and so is the "after fees" column of its table.** The
   researcher computed net = gross + fees + rebates. Fees charged in Mar-Apr 2026 were mostly REFUNDED (the tool prints
   `fees refunded` and a "NET kept" column; NOTES.md already explains this). Correct figures:

   | wallet | gross | fees charged | refunded | rebates+rewards | KEPT (economic_pnl) | kept % of volume | rebate share | kept w/o rebates |
   |---|---|---|---|---|---|---|---|---|
   | 0xe1d6 | 781,581 | -1,718,946 | 1,222,704 | 40,754 | 326,092 | +0.91% | 12% | +285K |
   | 0xb27b | 809,914 | -3,512,985 | 3,190,463 | 770,368 | 1,257,760 | +0.90% | 61% | +487K |
   | 0xeebd (Bonereaper) | 1,467,617 | -2,524,168 | 906,915 | 679,046 | 530,841 | +0.31% | 128% | -150K |
   | 0x8852 | 320,129 | -177,655 | 177,638 | 42,918 | 363,031 | +2.34% | 12% | +320K |
   | 0xa8cc (UUDDLRLR) | 114,560 | -114,612 | 1 | 14,894 | 14,842 | +0.31% | 100% | -53 |

   Monthly NET kept (K; in brackets without rebates):
   - 0xe1d6: Mar +73.0 (+70.7), Apr +228.0 (+194.3), May +25.1 (+20.4); nothing since. NOT "-294K, -628K".
   - 0xb27b: Mar +329.9 (+289.9), Apr +234.0 (+105.1), May +98.1 (+58.9), Jun +143.5 (+37.2), Jul +79.6 (-20.9),
     Aug +190.9 (-27.4), Sep +181.8 (+44.5); nothing since. NOT "-1,407K, -1,219K".
   - 0xeebd: Mar +74.0 (+73.0), Apr -74.2 (-100.3), May +140.9 (+116.7), Jun +38.4 (-54.1), Jul +92.7 (-59.3),
     Aug +121.4 (-65.1), Sep +54.9 (-33.8), Oct +36.8 (-8.5), Nov +45.7 (-17.1). NOT "-166K, -742K".
   - 0x8852: May..Nov +41.5 (+34.6), +53.3 (+48.4), +30.2 (+24.1), +2.3 (-2.5), +14.3 (+8.3), +6.0 (+2.8), +8.8 (+8.1).
   - 0xa8cc: unchanged (Apr -0.1, May +15.7, Jun -10.7 (-17.0), Jul +9.9 (+1.3)).
   The "tool caveat" paragraph in 4.1 and the matching line the researcher added to NOTES.md are therefore resolved:
   the gap IS `fees_refunded`. Consequence: all three big wallets made most of what they kept in March-April, when
   their taker fees were refunded, i.e. in a regime that no longer exists.
2. **0xeebd is Bonereaper**, a wallet the lab had already catalogued (`catalog/raw/x1_wallets.md`, row Bonereaper;
   advertised with referral / copy-trading links by @RetroValix and @Dan1ro0). It shares the Diamond taker volume
   4,583,181 and maker volume 629,191 with wzbbb (one fee group; its own maker volume is only 68,070). The dataset's
   "anonymous" directional wallet is the promoted one.
3. **0xb27b did not stop in September; the operator moved.** Its tier lookup still returns Gold 348,873 / maker
   2,406,060 (700 bps) with `own_wv_30d` = 0; ply-pm0 (0x764f...c347, joined 2026-09-25) and ply-pm2 (0x43e7...472a,
   joined 2026-09-28) return exactly those values. Per x1_wallets.md they kept +48K / +38K and +25K / +4K in Oct / Nov
   (+27K / +21K and +17K / -5K without rebates), rebate share 44-58%.
4. **Candidate 3 misdescribed the late-window behaviour.** Spec C says "late window: repair-only buys <= 0.30", but
   the deeper decode written 40 minutes later in the same dataset (EEBD_CLONE_REPORT) says the opposite: "directional
   volume is concentrated LATE — the final-60s bucket carries ~13x the USD of the first-10s bucket, at prices up to
   0.99, where P(winner == sign) reaches 0.83-0.91"; stake-weighted agreement with sign(chainlink - strike) 0.91.
   Live check, 24-27 Nov (48.9K fills, 904 markets, $2.09M): 75% taker (source: 60% maker, no longer true); taker
   edge +0.89 c/share before a 0.73 c fee = +0.16 c (t 0.66, clustered by market); 57% of the dollars are bought at
   >= 0.95 ($669K as taker, $509K as maker; taker +0.6-0.7 c/share after fee, maker +1.0 c at 0.95-0.99, t 0.9-1.7); net of fees +0.29% of
   turnover (t 0.84). The API for the same days: gross 30.7K, fees 23.4K, rebates 10.2K, kept 17.5K.
5. **0x8852 is not evidence for Spec A.** The source never describes it. Live check, 22-27 Nov: 100% maker, buys
   only, no merges, BTC 15m ($57.7K, +1.77%) and ETH 15m ($30.5K, -0.95%) - not 5m; 7,960 fills of $11 on 885
   markets, both outcomes in 395; +$733 on $88K (t 0.47, not distinguishable from zero); heaviest at 0.85-0.99 and
   in 1-5 c tails. Tier 0, not in a fee group (maker volume 64,413 all its own), so its maker rebate is 0 since
   Nov 22 (658 for the whole of November). It is the only one of the five that is alive, small and unsubsidised.
6. **Why the source's dollar figures are 10x too high (reading, not a re-computation).** METHODOLOGY.md defines
   `pnl_if_up = max(net_up, 0) - (cash_out - cash_in)` with `cash_in = sell + merge + redeem` and `net_up` reduced
   by merges but not by redemptions: a redeemed winner looks counted twice. METRIC_AUDIT gives 0xeebd BTC pre-fee
   P&L $11.7M by 25 Apr against $1.47M lifetime on the profile. The UUDDLRLR report comes from a different
   pipeline and agrees with the API (BTC pre-fee 99.7K and fees 80.4K vs all-coin 114.6K and 114.6K).
7. Internal contradictions in the source that bear on Spec A: its own audit attributes 96.8% of 0xe1d6's BTC P&L to
   the "residual" and 3.2% to the deterministic pair edge, while the synthesis calls the residual uninformed (hit
   49%); the wallet's median pair VWAP sum is 1.001 (BACKTEST_RESULTS similarity table), not the <= 0.95 of the spec.
8. UUDDLRLR time gap: the "+$39.68 Binance-Chainlink gap at trade" is a 75-session sample; the same author's
   75-session figure for 0xb27b ($52.82) collapsed to $4-12 on full data. Treat it as unproven.

### Credibility changes
- Candidate 3 (oracle-sign directional, Bonereaper): 2 -> 1. Promoted wallet, negative before rebates in every
  month since June, source's own taker backtests negative, mechanism text was partly wrong.
- Candidate 4 (UUDDLRLR): 3 -> 2. The report is honest and matches the API, but what it documents is a break-even
  account (-$53 after fees on $4.8M) that stopped in July.
- Candidates 1 and 2: stay at 2, evidence text replaced. Nothing dropped: every source exists and says what is quoted.

### Not checked
The lag measurement and fill simulations proposed under "testability"; the per-wallet JSONL exports; the ETH decode;
LIVE_TRADING_SPEC_EEBD_CLONE and RULE_MINING_REPORT; whether 0xa8cc's non-zero taker volume (1,079 with no own
trades since July) points to a sibling wallet.
