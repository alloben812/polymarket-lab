# w2 — GitHub: public Polymarket bots and tools, read at the code level

Researcher pass of 2026-11-27. Everything below was read, never executed. Clones are shallow
(`git clone --depth 1`) under `data/repos/<owner>__<repo>/`. "Last commit" is the date of the HEAD
commit in the shallow clone. GitHub HTML pages and the search API return 403 from this sandbox, so
star counts are NOT verified by me; where a star count appears it is quoted from a third-party page.

## 0. How repositories were found, and what could not be opened

WebSearch queries used (11): polymarket trading bot github 2026 market maker arbitrage; 5 minute BTC up
down bot; weather bot NOAA; malware / key stealer warning; kalshi arbitrage / negrisk; rewards farming /
sports in-play / resolution sniper; official repos; Oct/Nov 2026 new fees py-sdk; "laikalabs" repo lists;
copy trading; sports live score latency; TWAP settlement bots.

Cloned and read (19):

| repo | last commit | what it is |
|---|---|---|
| warproxxx/poly-maker | 2026-07-09 | maker-only reward/rebate market maker, political markets, CLOB V2 |
| matthewnyc2/arbitrage | 2026-11-27 (bot commit refreshing an events snapshot) | negRisk complete-set arbitrage scanner |
| yangyuan-zhen/PolyWeather | 2026-10-14 | weather-intelligence product for temperature markets (AGPL; trading code withheld) |
| abrownfox0/abrownfox001-twap60-prediction-trigger-system | 2026-09-09 | BTC 5m directional bot, ships a closed 100 MB .exe |
| Jon-Becker/prediction-market-analysis | 2026-10-29 | dataset (36 GiB) + analysis framework, Polymarket and Kalshi |
| ent0n29/polybot | 2026-02-21 | Java/ClickHouse stack that reverse-engineers the gabagool22 complete-set strategy |
| doge-8/btc5m-web | 2026-05-31 | BTC 5m order tool + three bundled strategies |
| humanplane/cross-market-state-fusion | 2026-01-03 | PPO agent, Binance futures -> Polymarket 15m, paper only |
| suislanchez/polymarket-kalshi-weather-bot | 2026-03-01 | GFS-ensemble weather + BTC 5m indicator bot, simulation only |
| meloner3/poly-kalshi-sports-bot | 2026-01-18 | Kalshi x Polymarket NBA arbitrage scanner (Rust) |
| CarlosIbCu/polymarket-kalshi-btc-arbitrage-bot | 2026-05-04 | Kalshi x Polymarket BTC 1-hour strike arbitrage |
| realfishsam/prediction-market-arbitrage-bot | 2026-01-16 | educational Kalshi x Polymarket "synthetic arbitrage" on pmxt |
| Sparmon7/polymarket | 2025-12-18 | sportsbook odds (The Odds API) vs Polymarket, 4 files |
| HODAKdev/PolyKiller | 2026-05-25 | copy-trading bot reading on-chain OrderFilled logs |
| gnanam1990/polymarket-copy-bot | 2026-03-27 | copy-trading bot polling the activity API |
| Polymarket/py-sdk | 2026-11-26 | official unified Python SDK (`polymarket-client` 0.20.1, 2026-11-20) |
| Polymarket/clob-client-v2 | 2026-11-17 | official TypeScript CLOB V2 client |
| Polymarket/rs-clob-client-v2 | 2026-11-12 | official Rust CLOB V2 client |
| Polymarket/agents, Polymarket/poly-market-maker | 2024-11-05, 2024-03-11 | official but stale: LLM agent demo; bands/AMM keeper |

NOT obtainable on 2026-11-27 (git refs endpoint 401 and raw README 404, i.e. the name does not resolve to
a public repo today: deleted, taken down, renamed or made private — I cannot tell which):
hu553in/polybot, joicodev/polymarket-bot, Xeron2000/wedge, spfunctions/polymarket-sports-mm,
Gabagool2-2/polymarket-trading-bot-python, Benjamin-Cup|Benjamin-cup|Benjam1nCup/Polymarket-trading-bot-python-V2,
dev-protocol/polymarket-copytrading-bot-sport, lorine93s/dfdsf, lorine93s/polymarket-market-maker-bot,
vladmeer/polymarket-copy-trading-bot, alteregoeth-ai/weatherbot, MrFadiAi/Polymarket-bot, n9xdev/poly-alpha-lab,
marcolunapaim/polymarket-5min-arbitrage-trading-bot, PolyBullLabs/Polymarket-Weather-Bot,
apechurch/polymarket-arbitrage-trading-bot, PolybaseX/Polymarket-Trading-Bot-Rust,
PolyScripts/polymarket-market-maker-bot, SnipeRun/polymarket-copy-trading-bot, txbabaxyz/polyrec,
goldspanlabs/weatherbot, serenorg/seren-skills, MalcolmMcGough/polymarket-trading-bot-scalping,
ruudkoeyvoets/polymarket-trading-bot-twap, casatrick/polymarket-arbitrage-bot.
Observation: nearly every repo that is pushed through dev.to / IndieHackers articles is in this list. The
same article is posted under two accounts in at least three cases (dev.to/benjamin_cup and
dev.to/benjamin_martin_749c1d57f share slugs such as `...-4lbc`, `...-17m1`, `...-24em`;
dev.to/nevosaynevo and dev.to/abrownfox001 share `...-28o7`; dev.to/soulcrancerdev and dev.to/xniiinx
share `...-5h09`). Treat that whole promotion network as advertising, and several of its repos as probable
malware carriers (section 1).

Also blocked: github.com HTML (403), awesome.ecosyste.ms (403 through WebFetch).

## 1. Malware and key-exfiltration findings

### 1.1 abrownfox0/abrownfox001-twap60-prediction-trigger-system — closed executable that asks for wallet credentials (treat as hostile)
- URL: https://github.com/abrownfox0/abrownfox001-twap60-prediction-trigger-system ; last commit 2026-09-09,
  author `abrownfox0`. Linked from https://dev.to/abrownfox001/what-actually-changed-for-bots-63l
- File: `Abrownfox001.exe` at the repo root, 100,974,592 bytes, `PE32+ executable (console) x86-64`,
  sha256 `b8e0dff7af7ffe19a0592f1f4a7735b5fa9e6fdd6980aedf70d4f9614809f4d4`.
- README.md lines 36-49: "### Run the bot" / "**`Abrownfox001.exe`** — standalone Windows build" /
  line 42 "First launch prompts for required Polymarket credentials and settings" / "2-day trial ... contact
  me on Telegram to arrange extended access".
- I did not analyse the binary, so I cannot prove it steals keys. A closed 100 MB binary that asks for a
  wallet private key, distributed from a marketing repo, is exactly the drainer delivery pattern. Never run it.
- The TypeScript in `src/` (995 lines) is clean on a static read: outbound hosts are only polymarket.com
  (gamma, data-api, clob), stream.binance.com, api.binance.com, api.coinbase.com; dependencies are
  `@polymarket/clob-client-v2`, `dotenv`, `viem`, `ws`. README itself says the source is "not a drop-in replica"
  and "The calibrated signal is private".
- Irony worth recording: the same handle authored the article "Why Almost Every Polymarket Trading Bot on
  GitHub Is Malicious" (dev.to/abrownfox001/...-28o7, posted May 27, year not shown; also mirrored under
  dev.to/nevosaynevo).
- Wallet named in the README: profile `abrownfox001`, proxy `0x12b712029efeee7efc4066e98e4e1b6beb8b1b0b`
  ("active since Jan 12, 2026"). Checked in section 3.5.

### 1.2 dev-protocol/polymarket-copytrading-bot-sport — confirmed stealer (from StepSecurity; repo no longer resolves)
- Source: https://www.stepsecurity.io/blog/malicious-polymarket-bot-hides-in-hijacked-dev-protocol-github-org-and-steals-wallet-keys
  (Varun Sharma, 2026-03-15), read through WebFetch.
- Repo created 2026-02-18 inside the hijacked verified org `dev-protocol`; 366 stars / 307 forks "likely inflated".
- Exact locations: `src/constant/index.ts` line 1 `import { from_str } from "ts-bign";` and
  `src/trading/exit.ts` line 3 `import { from_str } from "big-nunber";`. package.json pins
  `"ts-bign": "1.2.8"` and `"big-nunber": "5.0.2"` (second source: dev.to article above).
  Chain 1: `ts-bign` -> `levex-refa` (`node_modules/levex-refa/index.js`, obfuscated) steals `.env`, `*.env`,
  `id.json`, `config.toml`. Chain 2: `big-nunber` -> `lint-builder`, `"postinstall": "node test.js"`
  (`node_modules/lint-builder/test.js`) opens SSH (`sudo ufw allow 22/tcp`, chown of `~/.ssh`).
- Exfiltration: POST to `cloudflareguard.vercel.app/api/v1` and `cloudflareinsights.vercel.app/api/v1`.
- Related repo names: `polymarket-trading-bot-new`, `polymarket-sports-trading-bot`,
  `polymarket-copy-trading-bot-sports`; accounts `insionCEO`, `wizardev-sol`; "20+ Polymarket scam repos".
- My check: the repo does not resolve on 2026-11-27, so I could not confirm the lines myself.

### 1.3 Other campaigns (search snippets only, pages not opened)
- OSV MAL-2026-4209 .. 4215 and MAL-2026-11115: npm packages that "masquerade as legitimate Polymarket CLOB
  trading tools while exfiltrating Ethereum private keys to a Cloudflare Worker"; `polymarket-claude-code`
  impersonates official tooling; May 2026 campaign of 9 packages by maintainer `polymarketdev`; July 2026 set
  of 25 typosquats (mitrade/cryptopolitan 2026-07-01). December 2025: SlowMist flagged a popular
  copy-trading bot that read config files and sent private keys to a remote server (kucoin/mexc news flash).
- Rule for this lab: only `@polymarket/clob-client-v2`, `polymarket-client` (py-sdk), `py-clob-client-v2`,
  `polymarket_client_sdk_v2` (Rust) from the official org; any other package that touches a key is unreviewed.

### 1.4 Static scan of the 15 non-official clones
Grep for eval/exec/child_process/base64/postinstall/webhooks/workers.dev/pastebin and for every private-key
read site, plus the list of distinct outbound hostnames per repo. Result: no exfiltration found. Details:
- All outbound hosts are the expected ones (polymarket gamma/data/clob/relayer/ws, Binance, Coinbase, Kraken,
  Bybit, Kalshi, Open-Meteo, api.weather.gov, the-odds-api, Telegram bot API, public Polygon RPCs).
- doge-8/btc5m-web `scripts/claim-relayer.ts:124-127` builds a `curl` command containing `RELAYER_API_KEY`
  and runs it with `execSync` — it targets Polymarket's own relayer (debug retry), not a third party.
  `tunnels/tunnel-arl-2t4.sh` hard-codes the author's VPS `ubuntu@34.249.106.114` (harmless, do not run).
  README carries affiliate links: `polymarket.com/?r=yue188888x`, `t.me/KreoPolyBot?start=ref-188888x`,
  `omni.variational.io/?ref=OMNI88888`.
- realfishsam bot hands `POLYMARKET_PRIVATE_KEY` to the third-party library `pmxtjs ^0.4.4` (not reviewed).
- CarlosIbCu uses `eval()` on gamma JSON strings (`backend/fetch_current_polymarket.py:59-60`) — sloppy, and a
  code-execution risk if the API response were hostile; not exfiltration.
- HODAKdev/PolyKiller pins `py_clob_client==0.34.6` (the archived V1 client). README: "Not working after v2
  update, only backtest should work."

## 2. Official Polymarket repositories that matter for building

- **Polymarket/py-sdk** (https://github.com/Polymarket/py-sdk, last commit 2026-11-26, `pip install
  polymarket-client`, v0.20.1 of 2026-11-20). One client for public data, account, trading, relayer.
  Modules under `src/polymarket/_internal/actions/`: `clob.py`, `data.py`, `gamma.py`, `orders/`,
  `order_heartbeats.py`, `rewards.py` (current rewards, market rewards, order-scoring check, user earnings,
  reward percentages, reward markets, current rebates), `rfq.py`, `combos.py`, `combo_rfq.py`, `perps/`
  (README: "All Perps APIs are currently experimental"), `session_keys.py`, `relayer`.
  `examples/crypto_twap_stream.py` streams the 30-second and 60-second Chainlink TWAP for btc/usd and eth/usd
  with "No credentials required" (the Spec class is marked deprecated in the example's pyright comments).
  CHANGELOG 0.20.0 (2026-11-16): "Prepare for the December 14 order-query changes"; open-order filters by
  asset now require the market condition id. README shows `merge_multiple_positions` (batch merges).
- **Polymarket/clob-client-v2** (TS, 2026-11-17) and **Polymarket/rs-clob-client-v2** (Rust, 2026-11-12;
  has a `heartbeats` feature: if the client disconnects, all open orders are cancelled; examples for RFQ,
  deposit-wallet orders, AWS-authenticated clients). `examples/account/rewards.ts` shows
  `getEarningsForUserForDay`, `getCurrentRewards`, `getRawRewardsForMarket`, `getRewardPercentages`.
- **Polymarket/py-clob-client** and **rs-clob-client** (V1): archived read-only since May 2026 per the org
  page snippet; the py-clob-client README says it no longer works. Any bot still on them is dead code
  (PolyKiller, matthewnyc2/arbitrage `py-clob-client>=0.20.0`, meloner3 `py-clob-client>=0.17.0`).
- **Polymarket/poly-market-maker** (2024-03-11): "Market maker keeper for the Polymarket CLOB"; two
  strategies, Bands (`config/bands.json`: three bands at 1/2/3 cent margin, 10-30 size) and AMM. Useful only as
  a reading example of a cancel/replace keeper; V1 client.
- **Polymarket/agents** (2024-11-05; "1,869 stars" per an Odaily roundup of Jan 2026, not verified): LLM +
  Chroma RAG + news search picks "one best trade"; the order call is commented out
  (`agents/application/trade.py:59-60` "Please refer to TOS before uncommenting"). No strategy content.
- New API fact found while testing (2026-11-27): gamma `/events` with `limit` above 50 answers
  `406 {"error":"gzip_required"}` unless `Accept-Encoding: gzip` is sent.

## 3. Repositories with real mechanics

### 3.1 warproxxx/poly-maker v2.0.0 — reward-band maker on political markets (best-documented repo)
- URL https://github.com/warproxxx/poly-maker ; last commit 2026-07-09, Daniel Sapkota; MIT; ~6,000 lines of
  typed Python, 83 tests, strict mypy. Depends on `py-clob-client-v2==1.0.2`. Forks seen in search:
  itgoyo/poly-maker, quenos/poly-maker.
- README warning: "Market making on Polymarket is competitive and can lose money. This is a reference
  implementation and a research harness, not a guaranteed-profitable product."
- Strategy (README "Strategy", `strategy/quoting.py`, `strategy/regime.py`, `catalog/scoring.py`):
  - every order post-only; quotes are two bids: BUY-YES at `r - delta` and BUY-NO at `(1 - r) - delta`, where
    fair value = depth-weighted microprice (3 levels) nudged by an EWMA of signed trade flow,
    `r = FV - skew(inventory)`, `delta = base + c_vol*sigma + c_tox*toxicity`. A filled pair merges to USDC at
    locked edge `1 - p - q`.
  - regime machine per market: QUIET (rest inside the reward band), TRENDING (half size, wider), EVENT (sweep or
    jump -> pull quotes, cool off 30 s), REDUCE_ONLY, HALTED. Heartbeat dead-man switch every 5 s.
  - market selection score = (reward share + rebate pool x our share) x extremity/spread penalty x viability
    (`liquidity_num/2000`); rebate pool = `vol24 * fee_rate * (1 - mid) * rebate_rate`.
  - sizes in the shipped profiles: `newsom-mm` $100 per side in 2 layers, net cap $200; `romania-pm` $22 per
    order (the 50-share reward minimum), cap $100; `live-tiny` $5 orders, $12 cap, total exposure $40, daily
    loss kill $12 (`livecfg/config.toml` comment: "CONSERVATIVE live-test config (Fable autonomous run, ~$50
    mandate)").
- Market facts recorded in `config/strategy.toml` (live sample 2026-07-06): Newsom 2028 Dem nomination —
  price ~0.195, tick 0.001, 2-tick spread, "VERY quiet tape (~0.1 trades/min)", rewards "min 100 shares/order,
  5.5c band, ~$52/day rate, 25% maker-rebate pool". "Next PM of Romania" (Nazare leg) — price ~0.487, 1-tick
  spread, "~$4k/day tape", rewards "min 50 shares/order, 4.5c band, ~$257/day rate, 25% rebate".
- Results the author reports (TIPS.md, "Written from a real supervised session (Newsom 2028 + Romania PM)"):
  "Session result: Newsom −$5.27, Romania −$10.24 (one bad adverse fill), total ≈ −$15.51". The Romania loss:
  "We rested $75 / 159-share orders on Romania; a seller gapped the market 0.478→0.442 and filled our whole
  bid". Exit cost: "the Newsom close reported a gross 126.97 but only 122.86 landed (~$4.1 fee)".
  No reward income figure for the session is given. No wallet is named.
- Lessons quoted (TIPS.md): rest only the `rewardsMinSize` on thin books; below-min orders "earn zero";
  `rewardsMinSize` changed live (50 -> 100); churn loses queue position and rewards; "On 0.001-tick markets ...
  profit is rewards + rebates, not spread capture"; the positions API lags during fast moves; "Liquidity
  rewards = a fixed daily pool split by your Qmin share ... past ~a third of the pool you're fighting yourself".
- Stale parts as of 2026-11-27: TIPS says "Maker rebates = 25% (most markets) or 20% (high-fee) of taker fees,
  uncapped" and fee `rate` 0.04. NOTES.md (docs, since 2026-11-20): maker rebate is tiered 0/3/7/10/15% by
  30-day maker volume and a new account gets 0; political rate is 0.01 (elections 0.05). So for a small account
  the rebate term in `scoring.py` is zero today and only the liquidity-reward term remains.
- "Not yet built" (README): a replay backtester, external data feeds (polls/news/cross-venue), merge through a
  proxy wallet.
- Idea worth testing: reward income per dollar of resting size vs adverse-selection loss, per market, using
  `rewardsMinSize` / `rewardsMaxSpread` / daily rate from gamma plus the market tape (who gets hit when the
  price gaps). The pure functions `strategy/quoting.py` and `regime.py` can be replayed offline.

### 3.2 sfmm / spfunctions/polymarket-sports-mm — sports reward quoting (PyPI page only; repo did not resolve)
- URL https://pypi.org/project/sfmm/ (v0.1.0 released 2026-04-05, author "SimpleFunctions", alpha, MIT).
- Mechanics as described: bid = mid − 1 tick, ask = mid + 1 tick ("prices for score, sizes for view"); size
  skew by view and inventory; pre-game engine polls every 5 s; live engine polls every 1 s with a circuit
  breaker (mid jump beyond a threshold -> pull all quotes, 10 s cooldown, requote), live quoting symmetric
  only. Reward score `S(v,s) = ((v − s)/v)^2`; "Two-sided quoting (bid + ask) scores 3x vs single-sided".
  Limits: 1000 contracts per market, $5,000 exposure, $500 daily loss.
- Claimed context (author's, unverified): Polymarket "pays $5M+/month" on sports; per-game pools April 2026:
  Champions League QF $24,000 ($6,750 pre / $17,250 live), EPL $10,000, NBA $7,700, CS2 A-tier $5,500, IPL
  $4,500, La Liga/Serie A $3,300, MLB $1,650, NHL $1,500. No performance results, no wallet, backtesting "on
  the roadmap", no handling of goals other than the mid-jump breaker. REST polling at 1 s in live sports is far
  too slow against score feeds: the quoted orders are the ones picked off.

### 3.3 ent0n29/polybot — "gabagool22" complete-set maker on crypto up/down, with the author's own failed replication
- URL https://github.com/ent0n29/polybot ; last commit 2026-02-21, Antonio Stano. Analysis script header:
  "GABAGOOL22 STRATEGY ANALYSIS - FINAL FINDINGS, December 16, 2025".
- Spec (`docs/EXAMPLE_STRATEGY_SPEC.md`): markets BTC/ETH 15m and 1h up/down. Signal:
  `complete_set_edge = 1 − (bid_up + bid_down) >= 0.01`. Maker GTC bids on both legs at
  `min(bestBid + improve_ticks, mid)`, never crossing; one order per token, replace no faster than 5 s; tick
  loop 500 ms; TOB stale after 2 s -> cancel. Inventory skew of at most 1 tick at 200 shares imbalance.
  Sizes copied from the target wallet: BTC 15m 11-20 shares by time-to-end bucket, ETH 15m 8-14, BTC 1h 9-18.
  Taker top-ups of the lagging leg at the ask when imbalance >= 10 shares: in the last 60 s, or 3-120 s after
  a lead fill if `1 − (leadFillPrice + laggingAsk) >= 0.01`. Suggested live bankroll in the doc: $200.
- Their own numbers (`research/backtest/backtest_report.json`): 31,107 clean target trades; replica would
  quote 23.4%, match 16.9%; `"gabagool_total_pnl": 4275.91`, `"gabagool_pnl_on_matches": 680.20`,
  `"our_simulated_pnl": -126.80`. I.e. the replica LOSES where the original wins. Script text: "X% of PnL comes
  from EXECUTION, not direction", "15min-BTC is the best market (70% of total PnL)", "Do NOT hardcode
  directional bias".
- Wallet check (mine, 2026-11-27, `tools/wallet_check.py gabagool22 --monthly`):
  `0x6031b6eed1c97e853c6e0f03ad3ce3529351f96d`, joined 2025-10-29, 28,620 markets, 12.9M fills, volume $71.4M.
  profile P/L (before fees) 867,687; taker fees −1,674,493; rebates 50,511 (all maker).
  By month — gross / fees / rebates / net: 2025-10 5,224/0/0/5,224; 2025-11 134,488/0/0/134,488;
  2025-12 299,558/0/0/299,558; 2026-01 276,285/−828,024/25,116/−526,623; 2026-02 152,133/−846,469/25,395/−668,941;
  no activity from 2026-03 to 2026-11. Gross is +1.22% of volume; the fee charge of Jan-Feb 2026 is 3.2-4.3%
  of volume, larger than the gross edge.
  CAVEAT: the tool's all-time line prints "ECONOMIC PnL 865,310" while trade_pnl + fees + rebates = −756,295 and
  the monthly NET column sums to −756,294. The two cannot both be right; `economic_pnl` from the API may not
  subtract fees recorded before mid-2026, or the tool's fee series overstates them. Needs a check before either
  figure is quoted. What is unambiguous: the gross edge was ~1.2% of volume, fees arrived in January 2026, and
  the wallet stopped completely after February 2026.
- Reading: same conclusion the lab already reached on x-MoneyForWhiskas — "pair cost under $1" is an execution
  outcome, a passive replica without queue priority loses, and the fee is larger than the edge.

### 3.4 doge-8/btc5m-web — late-window Binance-vs-book rules on BTC 5m (concrete, testable, pre-TWAP)
- URL https://github.com/doge-8/btc5m-web ; last commit 2026-05-31; MIT; TypeScript; X @x_188888_x.
  Feeds: Polymarket order book WS, Polymarket live-data WS (Chainlink price), Binance and Coinbase WS; strategy
  tick every 250 ms; FOK market buys; optional GTC take-profit. README: "Binance price reacts faster than the
  Chainlink oracle, providing a leading signal". Disclaimer: "The built-in strategies are framework examples
  only and cannot guarantee profits."
- `diff` = Binance price − window price-to-beat (USD, offset-calibrated).
  - `strategies/d1.ts` "Tail-Scalp": only when 0 < remaining <= 30 s; buy Up if `diff > +40` and Up prob < 80%;
    buy Down if `diff < −40` and Down prob < 80%; stop if diff crosses 0; hold to settlement. In-code claim:
    "Backtest 24 days: ~7 trades/day / 86% win rate / $0.70 per trade (passed all 5 validations)" (stake size
    not stated).
  - `strategies/p1.ts`, `p2.ts` "Prob Chase": between 90 s and 30 s remaining, when diff crosses ±25 and
    (historical fair probability from a diff x remaining-time table − current probability) >= 10 points
    (p2 also requires current prob < 65%) -> buy; stop when diff crosses ∓5; no take-profit.
  - STRATEGY-GUIDE: "Polymarket waives the taker fee (~1.56%) for makers ... a complete buy+sell using maker
    orders saves ~3% in fees"; "once BTC commits to a direction it reaches 99-100% at settlement".
- `backtest-data/README.md` (Chinese): they record one tick per second `{ts, windowStart, diff, upPct, rem}`
  (~4 MB/day) and build a (diff bucket of $5, remaining-time bucket) -> median probability map; no data shipped.
- Caveats: written before the 2026-08 changes (60-second TWAP settlement, 50 ms taker delay). With TWAP
  settlement the last 30 s price is averaged, so "diff > $40 with 30 s left" means something different now.
  Fee at the time ~1.56% of notional at 50c; the lab measured the 0.07 rate until 2026-11-20 and 0.05 after.
  No wallet named. The claim is an in-sample backtest by the author.
- Testable with lab data: `data/binance_1s` + `data/tape_btc5m_nov` — for every market take trades in the last
  30 s (and 90-30 s), condition on Binance diff vs price-to-beat and on the trade price, compute settlement
  payoff minus fee. The lab's own tape result (takers buying at 0.90-1.00 were the only positive bucket,
  +0.41c/share, not significant) is the same region.

### 3.5 abrownfox0 — "TWAP-anchored" BTC 5m directional at ~50c with scratch exits (claims do not survive the wallet check)
- Repo and red flags: section 1.1. README claims (sample "Jul 2026", "150 markets"): "Held-side win rate 60.7%
  (91W / 59L)", "ROI on staked capital at resolution ≈ +24.5%", "~90.6% of trades in 45–55¢", 5,000 trades over
  ~126 days (~40/day), buy:sell 3,643:1,357, median notional $57.75, "~930 markets show buy and sell at
  essentially the same price (avg buy 0.504, avg sell 0.503)", buys median 47 s after open, sells median 226 s.
- Reference signal (`src/signal.ts`): `raw = 0.7*(clip(twap_slot_return_bps/8) + 0.3*clip(twap_20s_momentum_bps/5))
  + 0.2*clip(cex_20s_momentum_bps/5) + 0.1*time_term`; `pUp = sigmoid(2.5*raw)`; trade when |pUp − 0.5| >= threshold;
  scratch when edge decays. Uses the 30-second Chainlink TWAP stream (settlement has been the 60-second TWAP
  since 2026-08-14, so the README is describing the Aug 7-14 rule).
- Wallet check (mine, 2026-11-27): `0x12b7…1b0b`, joined 2026-01-12, 5,610 markets, 67,802 fills, volume
  $1,559,579. profile P/L before fees 19,353 (+1.24% of volume); taker fees −78,291; rebates 5,784 (taker 760,
  maker 5,024). Monthly net (gross+fees+rebates): 2026-01 −4,372; 02 −18,076; 03 −26,963; 04 −8,601; 05 +1,274;
  06 +1,601; 07 +836; 08 +463; 09 +479; 10 −9; 11 +218. Volume fell from $250K/month (May-June) to $13K
  (November). Tier 0 on both ladders now.
  Same tool caveat as 3.3: all-time "ECONOMIC PnL 7,617" (+0.49% of volume, 76% of it rebates) vs −53,154 from
  the monthly columns. Under either reading the account is not a 61%-win, +24.5%-ROI machine: a 60.7% win rate
  at 50c would be roughly +21% gross on stake, the wallet shows +1.24% gross on volume. In the lab's window
  (Sep-Nov 2026) it nets between −9 and +479 dollars a month.
- Verdict: marketing for a paid/closed executable. Credibility 1.

### 3.6 matthewnyc2/arbitrage — negRisk complete-set scanner (mechanics clear, no results, fee model wrong)
- URL https://github.com/matthewnyc2/arbitrage ; HEAD 2026-11-27 12:30 UTC is an automated
  "chore(events): refresh snapshot"; MIT; 60 tests. Demo pages on github.io.
- Rule: for a negRisk categorical event, if `Σ best_ask(outcome_i) < $1`, buy one of each and redeem for $1 via
  `NegRiskAdapter.redeemPositions`. Engine walks depth on every leg, picks basket size maximising net profit,
  FAK orders in parallel, unwinds partial fills. Defaults: min net edge 50 bps, $50 per basket, 3 open baskets,
  paper latency penalty 250 ms, gas $0.10 per basket (hard-coded).
- Flaw: `arbitrage/engine/opportunity.py:48-49` — "CLOB taker fee is typically 0 on Polymarket; keep a hook for
  non-zero. fees_per_share_usd=Decimal("0.0")". Not true in 2026. Also uses the archived V1 client. STATUS.html
  admits "Depth is shallow at the edge" and "Gas is hardcoded". No P&L, no wallet.
- Second flaw (conceptual): the sum-to-one identity holds only when the listed outcomes are exhaustive. Most
  large negRisk events are `negRiskAugmented` (unnamed "other" outcomes can be added), where Σ asks < 1 is not
  an arbitrage.
- My check (2026-11-27, script in scratchpad, rule written before running, one variant): top 400 open events by
  24h volume from gamma, 176 are negRisk with >= 2 open legs, 159 have every leg quoted. Median Σ bestAsk =
  1.036, median Σ bestBid = 0.965. Σ asks < 1 before fees: 13 events, of which 12 are `negRiskAugmented`
  (e.g. presidential-election-winner-2028, 58 legs, Σ asks 0.92) and the one non-augmented case costs
  0.996 + 0.0051 fee = 1.0011. Short side (buy NO on every leg, needs Σ bids > 1): 6 events before fees
  (max 1.02, nba-2027-champion), 0 after fees (fees 0.016-0.046 per set). So: 0 of 176 executable at top of
  book on this snapshot. Caveat: gamma bestBid/bestAsk fields, not live books; one moment in time.

### 3.7 Cross-venue: Kalshi x Polymarket and sportsbook x Polymarket (four thin repos)
- CarlosIbCu/polymarket-kalshi-btc-arbitrage-bot (2026-05-04), `thesis.md`: BTC 1-hour markets. If Poly strike >
  Kalshi strike, buy Poly DOWN + Kalshi YES: pays >= $1 always and $2 if price lands between strikes; buy when
  combined cost < $1. Not addressed: the two venues settle on different price sources and timestamps, so the
  "guaranteed" $1 can become $0 when the settle prices straddle a strike; fees on both sides are ignored.
- meloner3/poly-kalshi-sports-bot (2026-01-18, Rust, Chinese README, "131 stars" per a third-party listing):
  NBA game matching between venues; `core/calculator.rs` charges only the Kalshi fee
  `ceil(0.07 × C × P × (1−P))`, Polymarket fee omitted (sports rate is 0.05 now); skips prices <= 0.01 or >= 0.99.
- realfishsam/prediction-market-arbitrage-bot (2026-01-16): buy YES on one venue and NO on the other when the
  sum leaves >= 1 cent; README: "Ignores gas fees, trading fees, and slippage", "Not optimized for real-world
  profitability".
- Sparmon7/polymarket (2025-12-18): compares The Odds API sportsbook prices with gamma `outcomePrices` (not the
  book) for two-way arbitrage; batch script.
- None claims results or names a wallet. A practitioner note surfaced by search (dev.to, page not opened):
  "870 cross-venue price gaps in one 24-hour window, median time open about 9 seconds", and another titled
  "Built a prediction market arbitrage, no sizable arbitrage found" (dev.to/michaelmustopo).
- Extra obstacle for this lab: Kalshi does not onboard Serbian residents as far as I know (not checked here).

### 3.8 Weather
- **yangyuan-zhen/PolyWeather** (https://github.com/yangyuan-zhen/PolyWeather, v1.5.1, last commit 2026-10-14,
  AGPL-3.0, site polyweather.top, paid membership with on-chain checkout). It is a product, not a bot: README
  "Not included in this repository: ... internal mispricing strategy, position sizing rules, and trading bot
  execution code." What is public and useful:
  - 51 cities; settlement anchor for airport-linked contracts is "the METAR / airport primary observing site"
    (examples in README: Shenzhen ZGSZ, Denver KBKF Buckley, Ankara/Istanbul airport METAR; Hong Kong HKO).
  - High-frequency observation feeds that are faster than hourly METAR (`docs/DATA_SOURCES_ZH.md`):
    NOAA MADIS HFMETAR, 5-minute, one decimal, anonymous access
    (`madis-data.ncep.noaa.gov/madisPublic1/data/LDAD/hfmetar/`, NetCDF) for 11 US airports (KLGA, KLAX, KORD,
    KBKF, KATL, KMIA, KSFO, KHOU, KDAL, KAUS, KSEA); Singapore MSS 1-minute (`api.data.gov.sg`, station S24);
    Hong Kong CoWIN 1-minute + HKO 10-minute; JMA AMeDAS 10-minute (Tokyo Haneda); FMI 10-minute (Helsinki);
    KNMI 10-minute (Amsterdam, registration). Tiering in the doc: Tier 1 <= 1 min, Tier 2 5 min (MADIS), Tier 3
    10-15 min, Tier 4 METAR only (Moscow UUWW; Munich "DWD delayed ~1 hour").
  - Forecast side: "DEB" blend of the Open-Meteo model suite with inverse-MAE weights, 14-day recency-weighted
    city bias, integer-degree bucket probability `P(T==τ)=Φ((τ+0.5−μ)/σ)−Φ((τ−0.5−μ)/σ)`; "July's 4-6C systematic
    over-prediction" is mentioned as a corrected failure; ">=37C cov90 0.820 -> 0.893". TAF (FM/TEMPO/BECMG/PROB)
    used as a confirmation layer. "market-signal difference = model probability − market-implied probability".
  - No trading results, no wallet.
  - The time-gap idea it implies: the daily-high bucket is a function of the running maximum at the settlement
    station; a 1-5-minute feed shows the running max (and when the peak has passed) before the hourly METAR or
    the market reflects it. Weather fee rate is 0.01.
- **suislanchez/polymarket-kalshi-weather-bot** (2026-03-01): 31-member GFS ensemble from Open-Meteo, probability
  = fraction of members beyond the threshold, trade when |model − market| > 8%, 15% fractional Kelly capped at 5%
  of bankroll / $100. README: "This is a simulation tool ... It does not place real trades". Its
  VALIDATED_RESEARCH.md is a useful correction list: NWS API is deterministic only; NBM (National Blend of
  Models, `s3://noaa-nbm-grib2-pds/`) has MaxT/MinT percentiles 5..95 and "is the correct source for
  probabilistic US forecasts"; HRRR is deterministic; "Kalshi settles on NWS Daily Climate Report". Same repo has
  a BTC 5m indicator strategy (RSI/momentum/VWAP composite, edge > 2%) that is plain technical-analysis noise.
- Not obtainable: Xeron2000/wedge (GFS ensemble + fractional Kelly), alteregoeth-ai/weatherbot,
  goldspanlabs/weatherbot ("WeatherBet", 20 cities), PolyBullLabs/Polymarket-Weather-Bot. Title seen in search
  and not opened: "Found the weather trading bots quietly making $24,000 on Polymarket and built one myself for
  free" (blog.devgenius.io) — typical promotion headline, unverified.

### 3.9 Copy trading
- HODAKdev/PolyKiller (2026-05-25): one 3,000-line file; subscribes to Polygon logs over WSS
  (`eth_subscribe` `logs`, decodes `OrderFilled`, `polykiller.py:1697-1767`) to see a leader's fills at block
  time, then sends its own order with `MAX_SLIPPAGE = 0.01`; has a wallet backtester and `find_good_address()`.
  README: "Polymarket copy trading bot faster than polygun. Not working after v2 update, only backtest should work."
- gnanam1990/polymarket-copy-bot (2026-03-27): polls `data-api.polymarket.com/activity?user=` every 2 s per
  wallet (v1 endpoint, retired 2026-11-02), copies only if implied ROI >= 30% (entry <= ~77c), dedup 60 s, paper
  mode default. No results.
- Structural point: NOTES.md says Data API rows appear 2-3 s after the match with 1-2 s jitter; on-chain logs
  arrive at block time (~2 s). A copier is therefore always seconds behind the leader and pays the taker fee,
  while the leader's edge on crypto up/down is ~1 cent a share. Copying only makes sense for slow markets
  (hours-days horizon) where a few seconds do not matter — and there the question becomes whether the leader's
  past P&L predicts anything.

### 3.10 humanplane/cross-market-state-fusion — RL on Binance futures -> Polymarket 15m (paper, not credible)
- URL https://github.com/humanplane/cross-market-state-fusion ; 2026-01-03. PPO, 18 features (Binance futures
  returns 1/5/10 m, book imbalance, CVD, Polymarket spread, time remaining), 3 actions. Claims: "~$50K PnL,
  2,500% ROI in Phase 5" in a "10+ hour paper trading session", "wins only 23% of trades". The README itself:
  "Paper trading assumes instant fills at mid-price", "Expect 20-50% performance degradation", "A single session
  isn't enough". PnL is `(exit − entry) × shares` marked at mid, no fees. Worthless as evidence.

### 3.11 Jon-Becker/prediction-market-analysis — data, not a strategy (the most useful tool repo)
- URL https://github.com/Jon-Becker/prediction-market-analysis ; last commit 2026-10-29. "the largest publicly
  available dataset of Polymarket and Kalshi market and trade data"; `make setup` downloads
  `https://s3.jbecker.dev/data.tar.zst` ("36GiB compressed") — parquet of markets and trades (API + chain
  indexers). Analyses included: Kalshi maker-vs-taker returns, mispricing by price, longshot volume share,
  returns by hour, calibration by bucket; Polymarket calibration by bucket and win rate by price. Reachability of
  s3.jbecker.dev from this sandbox was not tested; size fits the 60 GB disk only barely.

## 4. What the code base as a whole says (my reading)

1. Not one public repo ships verifiable live profit. The only author who reports real fills honestly
   (poly-maker) reports a loss of $15.51 on ~$200 of quotes; the only one who backtests a replica of a known
   winner (polybot vs gabagool22) gets −$126.80 against the original's +$4,275.91.
2. Everything written before 2026 assumes zero taker fees (matthewnyc2, meloner3, realfishsam, Sparmon7,
   humanplane). Every fee-free "arbitrage" disappears once `rate*p*(1-p)` is charged; my negRisk snapshot shows 0
   of 176 events executable after fees.
3. The two repos that are still maintained in the lab's window (PolyWeather, Oct 2026; py-sdk, Nov 2026) are a
   data product and the official SDK. PolyWeather's data-source map is the best concrete "time gap" lead found
   here: minute-level settlement-station observations vs a market with a 0.01 fee.
4. Reward farming (poly-maker; sfmm) is the only family where the income source does not depend on speed, but
   the documented failure mode is adverse selection on thin books and the old flat 20-25% maker rebate is gone
   for small accounts.

## 5. Tool issue found
`tools/wallet_check.py`: for gabagool22 and for 0x12b7…1b0b the all-time "ECONOMIC PnL" line disagrees with
`trade_pnl + fees + rebates` and with the sum of the monthly NET column (865,310 vs −756,295; 7,617 vs −53,154).
For x-MoneyForWhiskas the identity holds (NOTES.md). Both failing wallets have large fees in Jan-Apr 2026, so
the suspect is fee accounting for that period (fees taken in shares and already inside trade_pnl?). Until that is
resolved, "net" for any wallet active before ~May 2026 is uncertain by the size of its fee line.

## Verification pass

Sceptic's check of this catalog, 2026-11-27 (about 15:30-16:10 UTC). Nothing was executed from any clone. Scripts
I wrote are in `catalog/raw/w2_verify_scripts/` (`scan.py`, `scan2.py`, `hf_vs_routine.py`); each has its rule in
the header, written before the run. Variants run: negRisk scan 2 (the second only changes how "fully quoted" is
counted), weather feed-vs-settlement 1.

### What I checked
- Sources. Fetched seven files from `raw.githubusercontent.com/<owner>/<repo>/HEAD/...` and compared them byte for
  byte with the clones: poly-maker `TIPS.md`, abrownfox `README.md`, doge-8 `strategies/d1.ts`, polybot
  `research/backtest/backtest_report.json`, PolyWeather `docs/DATA_SOURCES_ZH.md`, matthewnyc2
  `arbitrage/engine/opportunity.py`, humanplane `README.md`. All identical, so the clones are what is public today.
  Every quoted number I grepped for is at the stated place (TIPS.md lines 30, 68, 76-77, 85; strategy.toml lines 4,
  46-47; backtest_report.json lines 68-70; d1.ts lines 10-12 and 34; abrownfox README lines 18, 42, 45, 129-130,
  162-163; opportunity.py lines 48-49; suislanchez README line 261; meloner3 `rust-backend/src/core/calculator.rs`
  lines 14, 33, 67 — note the path has a `rust-backend/` prefix; realfishsam README lines 163, 165; PolyKiller
  README line 3; humanplane README lines 23, 27, 37, 39, 69, 73).
- sfmm: PyPI JSON API confirms v0.1.0 uploaded 2026-04-05, the pool table, "3x", mid ± 1 tick, 1 s live polling,
  10 s cooldown. Its GitHub repo returns 404.
- "Not obtainable" list: re-tested 5 of the 25 names (spfunctions/polymarket-sports-mm,
  dev-protocol/polymarket-copytrading-bot-sport, Xeron2000/wedge, vladmeer/polymarket-copy-trading-bot,
  hu553in/polybot): raw README 404 and `git ls-remote` asks for credentials, while the control (warproxxx/poly-maker)
  answers. Confirmed for those five.
- dev.to: opened through the dev.to API. `michaelmustopo/...-36cf` (published 2026-07-08, outside the three-month
  window) does say "870 cross-venue price gaps in one 24-hour window, median time open about 9 seconds, 96 percent
  closed inside 30", and also "barely any sizable arbitrage" and "$439 net of fees across the whole match against
  $20.8 million" for one football match. `abrownfox001/what-actually-changed-for-bots-63l` exists (2026-09-10) and
  links the repo, Telegram and the profile; it states the taker delay went 50 ms -> 150 ms on Sep 4.
- Wallets: re-ran `python3 -I tools/wallet_check.py <w> --monthly` on both (the tool now prints refunds).
  Gamma resolves profile `abrownfox001` (pseudonym Wretched-Notice) to 0x12b7…1b0b, same as the README.
- X: `xread.py timeline` works (appledog_xyz is posting on 2026-11-27) but returns 404 for `x_188888_x` (doge-8) and
  `warproxxx`, so neither author's recent statements could be read.
- Own data checks: negRisk snapshot re-run; current reward terms from gamma for politics, sports and weather; the
  text of a live weather market's resolution rule; MADIS and aviationweather reachability; 87 days of KLGA
  observations from the Iowa Mesonet archive (5-minute feed vs routine METAR).

### What I changed, and why
1. **Both wallet readings in sections 3.3 and 3.5 are wrong and the "tool caveat" in section 5 is resolved.**
   The fee line is the gross charge; 97% of gabagool22's and 77% of abrownfox001's fees were refunded
   (`fees_refunded`), all of it in January-April 2026.
   - gabagool22: gross 867,687; fees charged −1,674,493, refunded +1,619,798; maker rebates 50,511; yield and
     referral 1,805; kept 865,310 = +1.21% of $71.4M; rebates are 6% of what was kept. NET kept by month:
     2025-10 5,224; 11 134,488; 12 299,558; 2026-01 270,156; 02 154,079; then 287-641 a month of yield until
     June and zero fills from March on. The figures "−526,623" and "−668,941" must not be quoted. The wallet
     did not stop because fees ate it: it stopped at the end of February 2026 while its fees were still being
     refunded. It never traded under fees that stuck, so it says nothing about today's rules either way.
   - abrownfox001: gross 19,353; fees charged −78,291, refunded +60,639 (none after April); rebates 5,784
     (taker 760, maker 5,024); kept 7,617 = +0.49% of $1.56M; 76% of what was kept is rebates. NET kept by
     month Jan..Nov 2026: 517, 111, 1,540, 459, 1,274, 1,601, 836, 463, 522, 62, 236. Without rebates the eleven
     months sum to +1,838 (0.12% of volume). From May, when refunds ended, fees are about equal to gross (May
     3,419 gross vs 3,263 fees; Jul 3,637 vs 3,975). Volume fell from $250K (May) to $13K (November). The
     series "−4,372, −18,076, −26,963, −8,601" must not be quoted. Verdict unchanged (the +24.5% ROI story is
     not in the wallet), numbers replaced.
2. **Weather candidate: the mechanism as written does not match how the markets settle.** The live NYC market
   (highest-temperature-in-nyc-on-november-27-2026) says the qualifying value is the highest temperature in the
   hourly T-group remark of any ROUTINE METAR (SPECI excluded), in tenths of a degree C, converted with
   F = C*9/5+32 and rounded half-up, source `aviationweather.gov/api/data/metar`; Weather Underground is only the
   fallback. So about 24 readings a day count, and a 5-minute or 1-minute feed's running maximum is not the
   settlement value. Test (rule first, one variant): KLGA, 87 local days 2026-09-01..11-26, IEM archive, routine
   reports (2,087) vs MADIS HFMETAR (24,907 five-minute reports): the feed's daily maximum gives a different
   whole-degree F than the routine maximum on 64 of 87 days (74%) and a different 2 F bucket on 45 days (52%);
   it is higher on 57 days; median gap +0.72 F, largest +3.24 F. A bucket is therefore certain only when a routine
   METAR prints it. The useful version of the idea: the fast feed nowcasts the next routine print to a few tenths
   and shows when the afternoon peak has passed. I rewrote the candidate that way and lowered credibility 3 -> 2
   (data product, no trading results, premise half wrong). Still the best time-gap lead in this file.
   MADIS is reachable from this sandbox (hourly `.gz` files rewritten every few minutes), and the IEM `asos.py`
   endpoint serves the same 5-minute reports as `report_type=1`, so the backtest can be built here.
3. **Reward terms re-measured (gamma, 2026-11-27).** Newsom 2028 nomination leg: 0.093/0.094, minimum 200
   shares (was 100 in July), band 5.5c, $67/day, fee rate 0.05. Both Romania events are closed. A two-sided quote
   at minimum size there is 200 YES at ~0.09 ($19) plus 200 NO at ~0.90 ($181): one market takes the whole
   stake, not "2-4 markets". EPL match today: minimum 1,000 shares, band 2.5c, $100/day per moneyline leg, $200
   on the main total and spread; the 40 largest open sports events carry $839/day in total over 31 markets. I
   could not find anything like sfmm's "$10,000 per EPL game" in these fields. Sports variant dropped (repo gone,
   pool figures not confirmed, 1,000-share minimum is beyond the lab's stake, 1 s REST polling in play).
   Credibility of the remaining politics variant 4 -> 3: the only live evidence is a loss and reward income was
   never measured.
4. **negRisk snapshot replicated.** 174 negRisk events with >= 2 open legs in the top 400 by 24h volume; all 174
   have every ask, median sum of asks 1.031; 13 below 1 before fees, 12 of them augmented, the one left is the
   same Jensen Huang event at 0.996 + 0.0051 = 1.0011. Short side: only 45 events have every bid, median 0.98,
   none above 1 (the researcher saw 6 before fees). 0 executable. Unchanged.
5. **Cross-venue credibility 2 -> 1.** The one practitioner measurement cited (and now opened) concludes there is
   no sizable arbitrage; fees on both venues exceed the usual gap; Kalshi access from Serbia is still unverified
   (Kalshi publishes no list of supported countries; third-party pages list 55 restricted jurisdictions and I could
   not see whether Serbia is one).
6. **gabagool22 candidate credibility 3 -> 2.** The wallet is real and kept 1.2% of volume, but under refunded
   fees, it has been idle for nine months, and the repo's own replica loses.
7. Taker delay corrected in the BTC 5m candidates: 50 ms from 2026-08-17, 150 ms since 2026-09-04 (NOTES.md).

### Missed by the first pass
- Weather markets carry liquidity rewards: 630 of 2,880 open weather markets have a daily rate, $14.7K/day in
  total, median $10/day per market, minimum 20 shares, band 4.5c, median book liquidity of a rewarded market
  $471, taker fee 0.01. This is the only reward programme whose minimum size fits a couple hundred euros. The
  HF dataset `Houroux/polymarket-l2-history` has temperature markets with L2 and trades, so reward share and
  adverse selection around each routine METAR print can be measured.
- The settlement rule of the weather markets (above) was not read; neither was any current reward term.
- Capital for two-sided quoting was understated (the NO bid on a 9-cent market costs 90 cents a share).
