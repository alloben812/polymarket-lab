# W3 — Long-form material: articles, blogs, newsletters, vendor research (collected 2026-11-27)

Scope: Substack / personal blogs / data-vendor research / affiliate "strategy guide" sites / dev.to bot posts /
post-mortems. Window of interest 2026-09-01 .. 2026-11-27; older pieces kept only where they explain a mechanism.
Every wallet named by a source was run through `python3 -I tools/wallet_check.py <name> --monthly` (outputs are in
section 9, raw files in `data/w3_pages/wallets/`). Downloaded pages are in `data/w3_pages/` (git-ignored).

Legend: FULL = I opened and read the page; SNIPPET = only what WebSearch returned (page blocked or not opened).

## 0. Access: what worked and what did not

- Opened with curl: telonex.io, casatrick.substack.com (+ its `/api/v1/archive`), dev.to, startpolymarket.com,
  leolabs.me, thedatascientist.com, odaily.news, crypto.news, blockjuice.asof.sh, raw.githubusercontent.com,
  docs.polymarket.com, news.bloomberglaw.com (first paragraphs only, paywall).
- Blocked: dune.com/blog (403 with curl, 404 through WebFetch), ccn.com (403), mexc.com/news (403),
  levelup.gitconnected.com (403, Medium family), gamingamerica.com (403), papers.ssrn.com (403),
  depthy.io (no connection with curl, 503 through WebFetch), polymarkets.co.il (no connection / 503),
  datdiego.github.io/posts/polymarket-arbitrage (404), dev.to/pmtraderadam/... (404, post removed).
- Substack's global search API (`substack.com/api/v1/post/search`) returns empty results without a session, so
  Substack coverage is what WebSearch surfaced plus one publication archive read in full.
- WebSearch returned no YouTube videos for any query I tried (it favours dev.to). YouTube is NOT covered.

## 1. Post-mortems with real numbers (the most useful class of source)

### 1.1 Leo (@runes_leo), "25 Directions Tested, 4 Survived: A Polymarket Strategy Post-Mortem" — FULL
- URL: https://leolabs.me/blog/pm-strategy-graveyard/en/ — `datePublished` 2026-03-25 (page also carries
  2026-08 dates, probably edits). Author sells a paid course ("PMQuant", "Leo Insider") and every Polymarket link
  is a referral link (`?r=runesleo&via=runes-leo`). No wallet is named, so nothing could be verified on chain.
- Old (March 2026: fee quoted as "1.5%" / "2%", i.e. before the current schedule) but it is the densest list of
  tested-and-killed directions found. Numbers as written:
  - Whale following, 5 iterations: following taker orders > $1,000 gave a 42.9% win rate. Filtered 287K addresses
    for an "elite pool": third-party win rates are wrong (SPLIT costs underestimated, redeemed positions counted
    as wins) — "One address claimed 83.5% win rate. Actual: 50.9%" against the official Data API. Many top
    "whales" are market makers holding both sides. Information coefficient "came to zero". "Live trading: +$770.
    Shadow trading: -$148."
  - BTC 5-minute, five plays. Latency arbitrage: "got slapped with 75.9 basis points of adverse selection — those
    orders I snagged were mostly deliberate baits left by the maker ... Lost $6.34 and stopped". Taker momentum
    (follow Binance with FOK): "294 live trades. Started with 81% win rate, decayed to 63% ... Risk-reward ratio:
    0.34x. Add 1.5% taker fees and the whole thing nets $39." Mean reversion: 4 wins, 10 losses. CVD: too few signals.
  - Tail buy-in (contracts under $0.05): "0.2% win rate. Break-even needs 2.4%."
  - Settlement harvesting (UMA wait): "Loose: entry $0.97+, 22 trades, 9-0 record, made $5.09. Strict: entry
    $0.9975+, 20 trades, 13-0 record, lost $2.32 ... Taker fee 2% kills you."
    (My note: under today's formula the fee at 0.9975 is rate*p*(1-p) = 0.05*0.9975*0.0025 = 0.0125 cents per
    share against 0.25 cents gross, so the "2% fee" death is specific to the fee model he assumed or paid then.)
  - Soccer favourite-longshot (buy favourites 0.50-0.85, top-5 leagues): 116 signals, 86 held, 4-9 record;
    sample too small.
  - Rebate farming on the 5-minute market with $217: "Redemption cooldown: 30 minutes. Candle cycle: 5 minutes ...
    Orphan order ratio exploded. Minimum viable: $400. Sweet spot: $800+. Final loss: $165.75."
  - Market making (two-sided quotes on one culture market): worked, "competition crushes it", died with the market.
  - News -> AI -> auto-execute, 2 iterations: "from news hit to signal generation to risk management to fill, the
    pipeline's too long. By the time your order lands on the CLOB, market's already priced it in." Shelved.
  - Killed in research: CTF mint arbitrage (12 markets, bid-side totals under 0.04, "-97%+ loss"); binary
    arbitrage ("1-3 seconds, then gone"); BTC daily direction (one address, 5,036 trades, 52.6% win rate, Z=1.46,
    p=0.072); SPLIT arbitrage (an address "claiming $38K profit. Leaderboard says: actually down $611").
  - Survivors (no parameters given): "Weather markets are running at break-even right now. Hit the
    season-transition gotcha"; crypto up/down "still iterating ... regime dependence"; "Niche categories — social
    media prediction markets for instance — actually generate the most profit. Fewer players, worse pricing,
    limited capacity but stable"; "one strategy, multiple accounts".
  - His summary rule: "your opponent isn't 'the market' — it's casual traders and small players in specific
    categories. Finding weak opposition beats finding a clever algorithm."
  - Unsourced closing numbers: "92% of traders on Polymarket lose money. Bots capture 73% of arbitrage profits."

### 1.2 Tanuj-07, `polymarket-market-making` (results-only repository) — FULL (README)
- URL: https://github.com/Tanuj-07/polymarket-market-making (README read from raw.githubusercontent.com). In window:
  the bot ran 2026-09-05 .. 2026-10-18. IMPORTANT: this is **Polymarket US** (the CFTC venue), not the
  international exchange this lab targets; the mechanism transfers, the incentive numbers do not.
- Mechanism: post-only two-sided quotes on every bracket of the daily high-temperature markets (New York, Miami,
  Chicago, Los Angeles, San Francisco). Fair value = the middle of Kalshi's price for the same bracket ("Kalshi
  lists the same contracts with deeper books"). Quotes pulled "as soon as Kalshi moves"; dead-man switch at 3
  minutes of silence; from Oct 2 only same-day markets; 1-3 contracts per quote; capital cap $20 -> $40 -> $60.
- Results (author's numbers, checked by him against the account balance, off by $0.23): 44 days, 23,628 fills,
  37,931 contracts. "Trading +$4.75; Maker rebates +$52.53; Liquidity rewards (rare after Sep 23) +$11.36" =
  +$68.64 on $33.80 average capital in use. Days up 29 of 44; days up on trading only 23 of 44.
  By city (trading only): Chicago -$10.10, Los Angeles +$25.97, Miami -$3.37, New York +$7.57, San Francisco -$15.31.
  "Most of the losses came from getting picked off by traders who knew something before the market did."
- Why it stopped: "On September 23 Polymarket cut the daily reward pool for weather markets from $750 to $185,
  without notice. A side only earns money once 7,500 contracts are resting on it ... From October 19, makers that
  trade less than $10 million a month no longer get a maker rebate". "The percentage return ... didn't scale with
  size ... Bigger orders barely added fills."
- Raw data in the repo: `data/daily.csv`, `data/versions.csv`, `data/series.csv` (not downloaded).
- Cross-check of the Oct 19 date: X post by @billsperos, 2026-10-13
  (https://x.com/billsperos/status/2109828872346730862, read with xread.py): "Upcoming @Polymarket fee structure
  begins October 19. It eliminates all rebates for traders who do less than $10M in monthly market maker volume.
  The new top tier MM rebates are less than the old flat rate." The quoted post says "Poly US", so this is the US
  venue's schedule; the international change came on Nov 20 (NOTES.md).

### 1.3 Hiberius, `polymarket-bot-graveyard` — FULL (README only)
- URL: https://github.com/Hiberius/polymarket-bot-graveyard. Six bots, 2026-03-29 .. 2026-06-28. Out of window,
  kept for the failure patterns. "Real money lost: roughly $45 ... after which the Polymarket wallet was banned
  for order-spam" (v0 sent "56,000+ rejected orders").
- v2 BTC 5-min with a 3-LLM consensus: "The '+profit' was BTC beta, not alpha". v3 LLM scanner over 480+ slow
  markets: "13,860 signals -> 0 fills. AI latency (2-11s) >> opportunity window (<1s)". v4 Chainlink fair-price
  maker on BTC 5m/15m/1h with the maker rebate: "55 days of paper, adjusted P&L negative ... Rebates don't cover
  adverse selection". v5 forward measurement before risking money: "sport Brier 0.2377 ~ coin-flip; BTC-Deribit
  win-rate 49%".
- Not opened: `docs/AUTOPSY.md`, `journey/`.

### 1.4 Kampakis, Sun, Firoozye, "Why Most Polymarket Trading Bots & Arbitrage Strategies Lose Money (Backtest of
1,233 Order Books)" — FULL
- URL: https://thedatascientist.com/why-polymarket-trading-bots-arbitrage-lose-money-backtest/ — published
  2026-11-03 (in window). Authors: Dr Stylianos Kampakis (The Data Scientist / Tesseract Academy), Jiaqi Sun and
  Nikan Firoozye (UCL CS). Companion study (not opened):
  https://thedatascientist.com/polymarket-efficiency-study-766-million-trades-machine-learning-microstructure/
- Data: Hugging Face SII Polymarket dataset, 766,412,707 OrderFilled trades, 491,202 resolved markets
  (2022-11-21 .. 2026-04-30), plus a Telonex export of 1,233 L2/L3 order books (exported 2026-06-26).
- Numbers:
  - Calibration at T-7d, count-weighted vs volume-weighted gap (realised minus price): [0.05,0.10] +3.4 pp vs
    +1.1 pp; [0.80,0.90] -6.6 pp vs +9.0 pp; [0.90,0.95] -12.3 pp vs +6.3 pp ("18.6 pp sign swing ($37 median
    sports volume)"); >=0.95: -1.3 pp vs +0.2 pp. I.e. the "favourites are overpriced" result lives in tiny
    sports contracts and flips sign when weighted by dollars.
  - "equal-stake proxy bots return +25.0% (fade-favourite) and +20.6% (back-longshot), but pre-entry liquidity
    weighting collapses them to -50.7% and -25.5%".
  - Price-only ML: 2026 holdout N = 228,809: raw market price AUC 0.9563 / Brier 0.07710; leakage-safe LightGBM
    AUC 0.9554 / Brier 0.07784. The model does not beat the price.
  - Taker families on real books, out of sample, with a flat 2% fee assumption: order-book imbalance -19.3%
    (N=209) / -14.6% (full depth, N=203); wide-spread reversal -19.7% (N=146); thin-book favourite -50.2% (N=30).
  - Passive maker capacity: "+11.93% ($10) -> -4.94% ($20) -> -24.43% ($100)" per market; "Above $15 per market,
    informed traders sweep resting orders".
- Caveats (mine): the fee model is a flat 2% of notional, which is wrong for today's p(1-p) schedule (overstates
  the fee near the extremes and in 0.01 categories); N for the book tests is small; the site sells courses.

### 1.5 Anton (dev.to/anton41), "Four ways prediction-market 'arbitrage' numbers lie" — FULL
- URL: https://dev.to/anton41/four-ways-prediction-market-arbitrage-numbers-lie-kao — posted 2026-07-29.
- (1) CLOB `asks` come back in DESCENDING price order: `asks[0]` is the worst ask (use min/max). (2) Top of book
  covers a handful of shares; walk the ladder for your stake. (3) Fees: `fee = shares x rate x p x (1-p)` on both
  venues; "A 1% gross spread on a 50/50 market can be entirely consumed by fees on both legs". (4) Model-free
  arbitrage inside single-game events via payoff bitmasks: "roughly 20,000 live order-book pulls over 18 rounds
  ... On mid prices: about 5% of constraints appeared violated. On real asks: every single one of them died.
  Executable profit: exactly zero." Validated the scanner by injecting a fabricated violation. Reason given: "a
  single market maker quotes both sides of every binary one tick apart and prices the whole ladder off one
  internally consistent model."
- Cross-venue matching pitfalls: fuzzy titles pair "on the ballot" with "pass", "rate increase" with "rate cut",
  deadlines a month apart, strikes off by 10x.
- Agrees with the lab's own snapshot (NOTES.md: 0 of 176 negRisk events had a complete-set arbitrage after fees).

## 2. Data-vendor research (Telonex) — old, but the standard reference with reproducible notebooks

### 2.1 Telonex, "$270K in One Week: Inside the Strategies of Polymarket's Top Crypto Traders" — FULL
- URL: https://telonex.io/research/top-crypto-traders-polymarket-15m — 2026-02-13. Notebook:
  https://github.com/telonex/research/blob/main/research/top_15m_crypto_traders/top_15m_crypto_traders.ipynb
- Data: every resolved 15-minute crypto market 2026-02-02..08: 2,688 markets, 15.3M fills, $153M, 46,945 wallets.
  PnL is pre-fee.
- "just 36.8% finished the week in profit. The median wallet PnL was roughly -$3." Top wallet $270,569; top 5
  $811,403; biggest loser -$139,971, "a majority-maker wallet that traded 142 markets".
- "Takers come out ahead on 53% of individual trade executions but lose money overall. Meanwhile, makers win only
  47% of individual fills but net +$728,501 for the week."
- Volume by price is concentrated near $0 and $1 and by minute in the final minutes; fill count is highest at
  minute 0.
- Edge table (PnL / volume, min $10K volume): two archetypes — "snipers" with < 15 markets (0x5e2b...f439: 155%,
  $67.7K on 8 markets; 0x7780...03ed: 137%, $119.7K on 11 markets) and 100%-maker bots over 2,000+ markets
  (0x7163...a9e5: 81%, $14.5K on $18.0K volume, 2,060 markets; 0xf49a...f9ba: 80%, $23.0K, 2,666 markets).
  Addresses are truncated in the article, so I could NOT run wallet_check on them (full addresses are in the notebook).
- Matches the lab's own tape result (takers lose, makers earn) and predates the TWAP settlement, the 50 ms taker
  delay and the Nov 20 fee/rebate change.

### 2.2 Telonex, "How Sponsored Liquidity Rewards Rewired Polymarket's Jesus Market" — FULL
- URL: https://telonex.io/research/sponsored-liquidity-rewards-jesus-market — 2026-02-22.
- On 2026-02-17 a sponsor added ~$70,000 of rewards to "Will Jesus Christ return before 2027?". "Within seconds,
  the orderbook transformed." Top-of-book depth x23.5, first 5 levels x12.4, 25 levels x15.0; cost to move the
  price 1 cent up x7.8, down x12.7. Spread was already at the tick (~$0.001) and did not change.
  Active makers 302 -> 639, maker HHI 0.164 -> 0.041, top-5 maker share 56.5% -> 36.9%.
  "Professional market makers monitor reward pools and respond to new incentives in real time."
- Reading for reward farming: a new pool is competed away within minutes; the pie per maker shrinks as makers double.

## 3. Affiliate "strategy guide" site that is actually kept up to date: startpolymarket.com (Tom Hill, @selectedadverse)

All pages carry affiliate links ("If you sign up through them, we may earn a commission"). The author says he runs
"an automated market-making bot on Polymarket sports and politics markets" but names no wallet. His X timeline
since 2026-09-01 shows one post (a site announcement). Pages read in FULL:

- In-play trading — https://startpolymarket.com/strategies/in-play-trading/ — updated 2026-11-21.
  "Some sports markets apply a short matching delay to orders that take liquidity, which stops traders watching a
  faster feed from picking off resting orders. When we checked on 27 October 2026, Premier League markets carried
  a 1-second delay and NBA markets showed none. The setting is per market and can change."
  Sports taker fee example: selling 1,000 shares at $0.68 costs 1,000 x 0.05 x 0.68 x 0.32 = $10.88.
  "Mid-match on a Premier League or NBA game, you can typically get tens of thousands of dollars on at a fair price."
  "A limit order sitting on the book when a goal goes in can be filled at the old price, against you."
- Reward farming — https://startpolymarket.com/strategies/reward-farming/ — updated 2026-11-21.
  Score per order `S(v,s) = ((v - s)/v)^2 x b` (v = market max spread, s = distance from the adjusted midpoint,
  b = in-game multiplier, NOT order size). With v = 3 cents: 2c away scores 11%, 1c 44%, 0.5c 69%, 0.1c 93%.
  Two-sided score = min(yes-side, no-side); one-sided is divided by c = 3.0 while the midpoint is in 0.10-0.90,
  and scores zero outside that band. Paid daily at midnight UTC in pUSD, per market, pro rata to score.
  "Minimum payout is $1. If your share of a market's pool comes to less than $1, it is not distributed, and it is
  not carried forward." ($200 pool needs 0.50% of the score; $1,000 needs 0.10%.) Orders below the market's minimum
  size score zero. "Of 1,000 sampled Polymarket markets, 583 used a tick of 0.01 and 417 used a tick of 0.001."
  Risk arithmetic: bid 53c for 100 shares, news takes fair value to 2c -> loss $51; "a $500 daily pool where you
  hold 10% of the score pays $50.00 per day. One adverse fill erases an entire day of rewards".
- Market making — https://startpolymarket.com/strategies/market-making/ — updated 2026-11-21.
  "I run an automated market-making bot on Polymarket sports and politics markets. This change really hurts small
  makers. My bot will now move between the 0% and 3% tiers, which is a long way from the old per-category pools
  that paid makers 15% to 25% of taker fees ... My strategies are still profitable without rebates, because the
  spread is how I make most of my money." Reaching the $200,000 maker tier "takes about 800,000 shares filled at
  50 cents". Top-tier rebate per 100 shares at 50c: $0.1875 in a 0.05 category, $0.0375 in a 0.01 category.
  Fee rounding: fees are rounded to 5 decimals, smallest fee 0.00001.
- Rebates & rewards — https://startpolymarket.com/learn/polymarket-rebates-rewards/ — updated 2026-11-21.
  Nov 20 change: maker rebates moved from daily per-category pools to account tiers (0 below $200,000 of 30-day
  maker weighted volume); Bronze and Silver taker tiers removed, Onyx 60% added, Gold/Platinum/Diamond cut to
  10/25/40%; "Liquidity Rewards, Holding Rewards, and the referral terms did not change."
  **Holding Rewards: "3.25% annualized ... on your total position value in eligible markets ... randomly sampled
  once each hour ... distributed daily in pUSD."** (The lab's local copy of the official docs,
  `data/pm_docs/concepts_positions-tokens.md` line 119, says **4.00%** annualized; the rate is variable. Which
  markets are "eligible" is not stated in either place.)
  Referral program: 10% of net fees from direct referrals, 5% from indirect — this is why most "strategy" pages exist.
- News trading — https://startpolymarket.com/strategies/news-trading/ — updated 2026-09-12.
  Speed hierarchy: Bloomberg Terminal > fast X accounts (@DeItaone) > primary sources (Truth Social) > mainstream
  media ("Polymarket has almost certainly already repriced"). "Economics and finance markets tied to data releases
  ... are almost impossible to news-trade manually ... automated systems reprice the market within milliseconds."
  Claimed residual edge: "interpretation — understanding what a piece of news actually means for a specific
  market's resolution criteria when the bots cannot parse the nuance". No numbers.
- Bonding — https://startpolymarket.com/strategies/bonding/ — updated 2026-03-25.
  Buy outcomes "informally decided but not yet formally resolved" at $0.93-0.99. Example: Warsh Fed-chair
  nomination traded ~$0.95 for "a couple of months" between the public announcement and the formal submission.
  "one failed bond wipes out 19 successful ones" at 0.95, ~32 at 0.97. No track record given.
- Copy trading — https://startpolymarket.com/strategies/copy-trading/ — updated 2026-03-30: "mechanically copying
  trades is structurally unprofitable due to slippage, information lag, and manipulation risk".
- Quantitative analysis — updated 2026-11-21: generic ("inefficiency in smaller markets is not subtle"), no numbers.

## 4. Weather

### 4.1 "Top 7 Most Profitable Weather Traders on Polymarket" (dev.to/fatherson, shown as ABROWNFOX001) — FULL
- URL: https://dev.to/fatherson/top-7-most-profitable-weather-traders-on-polymarket-2f9b — posted 2026-06-15.
  Same account family as the `abrownfox0` repo that w2 flagged as hostile (closed .exe asking for wallet keys);
  ends with a Telegram contact. Treat as lead-generation. The sister post at dev.to/pmtraderadam/... is a 404.
- Claims: ColdMath +$124,896, 81.7% win rate, "sophisticated automated trading bot built on Clawdbot", "buys
  Yes/No shares at extremely low prices (often 0.01-0.02) when it detects even tiny mispricings"; VibeTrader
  +$132,854 (New York/Miami temperatures plus Elon Musk tweet counts); BeefSlayer +$62,064 ("buying extremely
  cheap, mispriced outcomes"); HenryTheAtmoPhD +$55,838 ("retired professor of atmospheric science"); HondaCivic
  +$55,408, 84.2% win rate; russell110320 +$43,936 (monthly anomalies, "hottest on record"); Maskache2 +$34,106
  (Seoul, Hong Kong, Wellington, New York).
- My wallet checks (section 9): the profile numbers are roughly right as all-time gross, fees are small (weather
  is a 0.01 category), rebates are negligible — but **most of the money was made between Dec 2025 and Apr 2026 and the edge has
  decayed**: ColdMath kept +137K in Dec-Apr and has lost about 30K since May (-30.4K in October 2026 alone);
  HondaCivic +56K in Feb-Apr, almost inactive since (one +9K month in August); VibeTrader made +100K in Dec-Jan
  and has been negative in every month from April to September; HenryTheAtmoPhD peaked in April (+20K) and
  stopped trading in August.
  Still positive in the window: BeefSlayer (+7.7K Sep, +6.2K Oct, -0.4K Nov on $25-54K monthly volume) and
  russell110320 (+16.9K Oct, +6.5K Nov, but 31K of its 101K is unrealized).

### 4.2 Other weather material
- Leo (1.1): weather is one of his 4 survivors, "running at break-even", "season-transition gotcha".
- Tanuj-07 (1.2): Kalshi-anchored maker on Polymarket US temperature brackets: trading flat, income was incentives.
- dev.to/cryptodeploy "How Polymarket weather markets actually work" (downloaded, not read in full; search
  snippet: markets resolve "on one exact airport station"; using city-centre coordinates "can introduce a 3-8
  degree error").
- "$88K weather bot" / "$6k/month blueprint" posts (dev.to/fatherson, youmind.com reposts of X articles):
  SNIPPET only; promotional.
- r1_papers.md 2.10 and 3.1 have the academic side (Crosier; Qiu & Qiu).

## 5. "Who profits" pieces

### 5.1 Odaily (translation of "The Best Traders on Polymarket") — FULL
- URL: https://www.odaily.news/en/post/5210641 — data "current as of May 5th" 2026.
- Top-10 wallets by category: politics $94M, sports $60M, crypto $25M. Theo4 $22M on 18 positions (100%
  politics); swisstony $7.8M on 150,000+ positions (97% sports, "averaging just $45 per trade"); kch123 top sports
  wallet (87% sports); MonsieurDimanche $15M across 9 categories. Three archetypes: political expert, systematic
  sports trader, cross-category generalist. No mechanics.
- My wallet checks (section 9): swisstony 0x204f...5e14: gross 23.53M, fees -7.27M, refunded 2.22M, rebates
  2.59M, economic 21.08M on $1.006B volume (kept 2.10% of volume; 12% of what was kept is rebates/rewards;
  Obsidian taker tier). May-Aug 2026 net 2.08M / 3.70M / 7.94M / 0.83M, and **zero volume in Sep, Oct and Nov
  2026** — the account went quiet (moved wallets, or stopped). kch123: economic 11.37M on $151M volume (7.5%),
  lost 0.28M in May and 0.34M in June 2026, no activity since July.

### 5.2 Casatrick (Substack), "14 of the Top 20 Polymarket Wallets Are Bots" — FULL
- URL: https://casatrick.substack.com/p/polymarket-trading-bot-leaderboard-dominance — 2026-08-10. A bot developer
  for hire. Repeats unverified claims ("One bot reportedly turned $313 into $414,000 in a single month ... 98% win
  rate"; an "OpenClaw" operator "reportedly generated $115,000 in a single week"); cites the $40M arbitrage paper
  and the Stanford/SMU settlement-manipulation paper (821 wallets, ~$8.2M) that are already in r1_papers.md.
- Archive read through `/api/v1/archive` (25 newest posts): 2026-09-21..10-05 is a daily series on bot plumbing
  (state reconciliation, partial fills, WebSocket recovery, monitoring); no strategy content, no results.

### 5.3 Casatrick, "My Polymarket Trading Bot Strategies: 5-Minute Momentum vs 15-Minute Reversal" — FULL
- URL: https://casatrick.substack.com/p/polymarket-trading-bot-strategies-5m-15m — 2026-08-31.
- Idea: after TWAP settlement, on 5m take the direction of a steady, volume-confirmed spot trend going into the
  averaging window, skip when the contract is already near 0.05/0.95; on 15m classify the early move as "impulse,
  fade it" (single volume spike) or "confirmed, follow it" (volume keeps building).
- RED FLAG: the results section is an unfilled template. It prints "[Aug 7-21, 2026] - sample size [380 trades],
  hit rate [54.2%], average edge per trade after fees and slippage [1.8%]" in square brackets and then leaves the
  writing prompts in the published text ("Anything that surprised you: ...", "Be explicit about sample size
  limitations ..."). The numbers are placeholders, not measurements.

### 5.4 Not opened
- Jackson Wang, "Smart Money on Polymarket: A Behavioral Anatomy of 273 Top Prediction-market Traders", SSRN
  6624899 (403). SNIPPET: "the dominant approach is holding through resolution with staggered entries, not
  arbitrage"; "pure bots earn the lowest median PnL of any group".
- Depthy, "We Tracked 38,000 Polymarket Wallets" (depthy.io/blog/wallet-intelligence, unreachable). SNIPPET: "top
  wallets generally allocate 1-3% of their apparent portfolio value per trade"; one top wallet "systematically
  buys 'No' positions". Vendor blog.
- Medium @0xicaruss, "5 Polymarket Strategies That Are Actually Working in 2026 (With Real Wallet Data)" (Medium
  blocked; no snippet content).
- Dune, "Polymarket fast markets" (dune.com/blog/polymarket-fast-markets). SNIPPET: fast markets went "from ~40%
  of crypto volume in September 2025 to over 80% by March 2026"; 5-minute markets' fee revenue peaked "at $2.1M
  in the week of March 30".

## 6. Sports in-play

- dev.to/fatherson, "How Smart Traders Crush Polymarket Live Markets: The 45-Second Information Edge" — FULL —
  https://dev.to/fatherson/how-smart-traders-crush-polymarket-live-markets-the-45-second-information-edge-54f7 —
  2026-06-12, same lead-generation account as 4.1. Claimed timeline of a goal: "T=0s event; T=+3s official data
  feed (Opta, Stats Perform); T=+45-60s your Twitch/YouTube/ESPN stream". Esports: "Game servers update map/round
  winners in 1-2 seconds; Twitch broadcast delay 15-60s+". Says RN1 made "~$2.6M" this way — w1's BlockJuice
  teardown and wallet check show RN1 is a two-sided maker/complete-set operation, not a score sniper, so the
  attribution is wrong. No data.
- Counter-evidence in the window: the 1-second matching delay on Premier League markets (section 3, checked by the
  author on 2026-10-27; NBA showed none). A 1 s taker delay lets makers who hold a fast feed cancel first, which
  removes exactly the "buy at the stale price after a goal" trade for anyone slower than the makers' feed.
- Leo (1.1): soccer favourite-longshot 4-9, inconclusive. Hiberius v5: sports Brier 0.2377.
- swisstony (5.1) is the proof that systematic sports trading at scale paid (2.1% of $1B) through Aug 2026.

## 7. Tweet-count / "social media" markets

- crypto.news, "Prediction markets are now trading on Elon Musk's dopamine" — FULL —
  https://crypto.news/prediction-markets-are-now-trading-on-elon-musks-dopamine/ — 2026-05-11. Weekly "Elon Musk #
  tweets" events with 20-post buckets; counts "main-feed posts, quote posts and reposts" between fixed noon-ET
  timestamps; one bucket (100-119) moved from 29.95% to 11.3% within an hour; a bucket page showed "more than $7
  million in cumulative volume". "Tweet markets resolve on an objective X-post count over a fixed window, letting
  bots and AI agents scrape Musk's feed and trade near real time."
- MEXC news 1083045 (403) — SNIPPET only: a trader "earned $106K in one month with only 25.51% winning
  predictions" by "buying multiple Elon Musk tweet ranges at 1 to 10 cents per share". Not verified, no wallet in
  the snippet.
- Leo (1.1): "social media prediction markets ... actually generate the most profit. Fewer players, worse pricing,
  limited capacity but stable" — no numbers, no wallet.
- VibeTrader (4.1) is described as trading Elon tweet counts next to weather: kept 113K all-time, but negative
  every month Jun-Sep 2026 on $15-72K monthly volume.
- Fee: mentions 0.01; tweet-count events are probably "culture" (0.01) — check `feeSchedule` on a live market.

## 8. LLM / model forecasting

- 1.4 (TDS): price-only LightGBM does not beat the market price out of sample (Brier 0.07784 vs 0.07710).
- levelup.gitconnected.com, "Seven AI models traded prediction markets for a week. Five lost money" (403) —
  SNIPPET: market Brier ~0.469 vs agents ~0.470-0.483; five of seven lost money.
- Hiberius v2/v3/v5 (1.3) and Leo's news pipeline (1.1): LLM latency 2-11 s; the pipeline is too slow for
  headline news and has no measurable forecasting edge on sports.
- r1_papers.md section 6 has the academic benchmarks.

## 9. My wallet checks (2026-11-27, `tools/wallet_check.py --monthly`; "NET" = change in economic_pnl)

| account | wallet | gross (profile P/L) | fees | refunded | rebates+rewards | ECONOMIC | volume $ | kept % of vol | rebate share of kept |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ColdMath | 0x594edb9112f526fa6a80b8f858a6379c8a2c1c11 | 128,441 | -34,972 | 6,604 | 6,846 | 106,919 | 10,019,789 | 1.07% | 6% |
| HondaCivic | 0x15ceffed7bf820cd2d90f90ea24ae9909f5cd5fa | 68,676 | -2,171 | 1,085 | 320 | 67,973 | 7,086,911 | 0.96% | 0% |
| VibeTrader | 0xcbbc5e035504421b084ad9248b660f6e9618b5d0 | 116,794 | -12,224 | 6,866 | 1,518 | 112,955 | 2,054,127 | 5.50% | 1% |
| BeefSlayer | 0x331bf91c132af9d921e1908ca0979363fc47193f | 92,197 | -4,145 | 1,402 | 424 | 90,010 | 561,749 | 16.02% | 0% |
| HenryTheAtmoPhD | 0x57ee70867b4e387de9de34fd62bc685aa02a8112 | 63,805 | -5,031 | 3,867 | 261 | 62,901 | 433,530 | 14.51% | 0% |
| russell110320 | 0x118689b24aead1d6e9507b8068d056b2ec4f051b | 102,728 | -2,100 | 0 | 309 | 100,937 (31,288 unrealized) | 1,198,359 | 8.42% | 0% |
| "Maskache2" | no exact match; closest "Maskache" 0xc981e9d3b977dfc69188889f979f5cd36555a75d | 6,693 | 0 | 0 | 93 | 6,788 | 224,758 | 3.02% | 1% |
| swisstony | 0x204f72f35326db932158cba6adff0b9a1da95e14 | 23,534,499 | -7,272,318 | 2,220,210 | 2,594,437 | 21,076,828 | 1,005,948,824 | 2.10% | 12% |
| kch123 | 0x6a72f61820b26b1fe4d956e17b6dc2a1ea3033ee | 11,382,875 | -328,859 | 297,391 | 19,614 | 11,371,020 | 151,384,978 | 7.51% | 0% |

("Maskache" is probably NOT the account in the article: 6.7K vs the claimed 34K. Treat as unverified.)

Monthly NET kept (USD):

| month | ColdMath | HondaCivic | VibeTrader | BeefSlayer | HenryTheAtmoPhD | russell110320 | swisstony | kch123 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2025-11 | -334 | - | 11,330 | 2,132 | 2,970 | 9,868 | 1,517,918 | 2,910,757 |
| 2025-12 | 9,620 | - | 50,307 | 2,847 | 6,110 | 11,070 | 1,581,767 | -106,762 |
| 2026-01 | 13,062 | 1 | 49,379 | 12,172 | -1,215 | 4,658 | 783,269 | 6,394,413 |
| 2026-02 | 29,315 | 19,355 | 9,850 | 10,822 | 6,914 | 13,795 | 580,898 | 2,047,375 |
| 2026-03 | 41,252 | 28,747 | 6,499 | 20,267 | 10,876 | 13,893 | 1,122,366 | -586,283 |
| 2026-04 | 43,714 | 8,348 | -8,848 | 14,990 | 20,241 | 7,806 | 859,342 | 1,623,457 |
| 2026-05 | -2,625 | 2,325 | -1,047 | 85 | 288 | 6,569 | 2,079,050 | -283,455 |
| 2026-06 | -1,595 | -48 | -3,033 | 2,749 | 1,473 | 1,046 | 3,702,259 | -339,190 |
| 2026-07 | -606 | 79 | -1,983 | -512 | 4 | 8,506 | 7,938,054 | 45 |
| 2026-08 | 67 | 9,018 | -5,408 | 10,272 | -72 | 17,943 | 829,997 | 0 |
| 2026-09 | 7,247 | 810 | -1,530 | 7,687 | -17 (no volume) | -2,129 | 46,433 (no volume) | 0 |
| 2026-10 | -30,372 | -561 | 759 | 6,165 | 0 | 16,872 | -2,501 (no volume) | 0 |
| 2026-11 | -1,826 | -102 | -521 | -432 | 0 | 6,524 | -35 (no volume) | 0 |

Earlier months are in `data/w3_pages/wallets/<name>.txt`. russell110320 also had losing months in 2025 (-15.9K in
May 2025, -7.7K in Sep 2025). kch123's result is two months (Nov 2025 +2.9M, Jan 2026 +6.4M).

Monthly volume in the window: ColdMath $765K / $1,209K / $415K (Sep/Oct/Nov); BeefSlayer $40K / $54K / $25K;
russell110320 $27K / $19K / $6K (31-66 fills a month); HondaCivic < $10K.

### 9.1 What the two still-profitable weather wallets did, 2026-09-01 .. 2026-11-27
(`tools_scratch/w3_profile.py`: Data API v2 `trades?user=&taker_only=false` and `taker_only=true`, notional = size x price)

- BeefSlayer: 9,201 fills, $118,118 notional, **62% taker**. BUY $85.9K / SELL $32.2K. Buys are spread over the
  whole price range (0.50-0.80 $20.3K; >=0.95 $19.9K; 0.80-0.95 $17.1K; 0.20-0.50 $15.3K; 0.05-0.20 $10.3K; <0.05
  $3.1K) — NOT only "extremely cheap" outcomes as the article says. $80.7K daily temperature (Istanbul, Dallas,
  Chicago, New York, Atlanta: highest and lowest), $27.7K storms ("Will Hurricane Polo peak at Category #?",
  "Will Tropical Storm Saudel make landfall in Japan?"), $9.6K other. Kept about 11% of that notional in Sep-Oct.
- russell110320: 135 fills, $52,097, 86% taker, almost only BUY at 0.50-0.80 ($42.7K): "Will 2026 be the hottest
  year on record?" $35.9K and "second-hottest" $5.1K, monthly "global temperature increase by more than X C".
  A slow, concentrated view on annual/monthly global temperature. Much of the all-time result is unrealized.

Not done: PnL by market, entry time relative to station observations, maker/taker split by price bucket.

## 10. Red-flag catalogue (products and promotion; what they claim)

- dev.to accounts fatherson / ABROWNFOX001 / benjamin_cup / benjamin_martin_749c1d57f / pmtraderadam / chumba_24 /
  xniiinx: dozens of near-identical "5-minute BTC bot" posts ("45% weekly ROI", "1-4% profits per 5-minute cycle",
  "~85% of a 5-minute interval's direction is decided in the final 10 seconds", "market making ... ~80% win
  rates") ending in a Telegram handle or a GitHub repo. w2 found a credential-stealing binary in this family.
  "How Traders Are Actually Making Money on Polymarket in 2026" (benjamin_cup, 2026-04-27, edited 07-29, FULL): the
  example "Buy Yes at $0.48, Buy No at $0.48 = $0.96" does not exist on a mirrored book (NOTES.md).
- Casatrick Substack: developer for hire; unfilled-template "results" (5.3).
- leolabs.me: honest post-mortem, but paid course + referral links; survivors are deliberately not described.
- startpolymarket.com, pm.wiki, sailgp.com "prediction-markets" guides, tech-insider.org, polymarkets.co.il
  ("Polymarket bot tutorial, chapter 15 of 32", unreachable): affiliate/SEO sites. Only startpolymarket showed
  dated first-hand checks.
- thedatascientist.com: course vendor, but the article reports negative results with sample sizes.

## 11. What this adds up to (my reading, to be attacked)

1. Every honest small-operator account in this class of source ends the same way: trading is about flat and the
   income was incentives (Tanuj: +$4.75 trading vs +$63.89 incentives; Leo's rebate farm; Hiberius v4) — and the
   incentives for small accounts were removed on Oct 19 (US venue) and Nov 20 (international). A plan that needs
   rebates is dead for a new account; a plan that needs liquidity rewards competes with makers who arrive within
   minutes of a pool appearing (Telonex).
2. The only categories where named small/mid wallets still kept money in Sep-Nov 2026 in this sample are weather
   (BeefSlayer, daily temperature + storms, 62% taker, 0.01 fee) and long-horizon climate (russell110320). The
   famous weather bot (ColdMath) has been losing since May. Weather edge is real but shrinking and operator-specific.
3. "Time gap" evidence in long-form sources: (a) BTC 5m: the gap is sub-second and the stale quotes are bait
   (Leo: 75.9 bp adverse selection); (b) sports: 3 s official feed vs 45-60 s stream is plausible but unmeasured,
   and Premier League markets now carry a 1 s taker delay; (c) news: LLM pipelines (2-11 s) arrive after the
   repricing; (d) resolution lag (hours to months) is the only gap that is long by construction — the "bond" trade —
   and the new fee formula makes its fee almost zero near $1; its problem is tail risk and capital lock-up, plus
   there is a 3.25-4% holding reward on eligible markets that partly pays for the wait.
4. Mechanical arbitrage (complete sets, logical constraints, cross-venue) shows zero executable profit at real asks
   in every careful source (Anton: 0 of ~20,000 pulls).

## Verification pass

Done 2026-11-27 by a second reader. About 25 tool calls. Scripts: `tools_scratch/v3_verify_*.py`.

### What was checked

- Sources re-opened with curl and searched for the quoted numbers: dev.to weather top-7, dev.to in-play post,
  Tanuj-07 README, six startpolymarket pages (reward farming, market making, in-play, bonding, news, copy trading),
  Odaily, Leo, Casatrick 5m/15m, crypto.news, anton41, both Telonex studies, Hiberius README, the benjamin_cup
  post, pm.wiki, and the @billsperos post through xread. Every number the catalog quotes from these pages is there,
  with three exceptions:
  - thedatascientist.com now answers with a "One moment, please..." script page, so its numbers were confirmed only
    from the saved copy `data/w3_pages/tds.txt`, not from the live site.
  - pm.wiki returned 2,855 characters of text and no "$164.50"; that figure stays a search snippet.
  - The bonding page says Warsh shares "settled around $0.95" and dates the story to "early 2025"; I did not find
    the words "a couple of months" next to it.
- `wallet_check.py --monthly` on ColdMath, HondaCivic, VibeTrader, BeefSlayer, HenryTheAtmoPhD, Maskache2,
  russell110320, swisstony, kch123, Theo4, MonsieurDimanche, RN1, and on four accounts found during the pass
  (Flaznorp, sb911, Annica, Prexpect). The table in section 9 reproduces to the dollar.
- BeefSlayer's fill profile for Sep 1 - Nov 27 re-pulled from the Data API: 9,226 fills, $118,190, 62% taker
  (catalog: 9,201 / $118,118 / 62%). Confirmed.
- Live API checks: `secondsDelay`, `holdingRewardsEnabled` and reward pools over the 1,000 most traded active
  markets; fee fields on a tweet-count, a temperature and a hottest-year market; order of the CLOB book.

### What was wrong or missing, and what changed

1. ColdMath is not evidence about weather in the window. Its fills from Aug 25 to Nov 27 (71,051) are soccer:
   $777K / $1,265K / $339K in Sep / Oct / Nov against $1.5K / $2.0K / $0.5K of weather. The -30,372 of October is a
   soccer loss. Sections 4.1, 9 and 11.2 read it as "the famous weather bot has been losing". What the data shows is
   that it left weather. May-July (when it was also slightly negative) was not classified.
2. swisstony did not stop. It shares both 30-day tier volumes with Flaznorp
   (0x821dab0565ebf5b327f51db06223fdcfe01acf16): taker 20,722,259.26, maker 15,273,968.34, the maker figure being
   entirely Flaznorp's own. Flaznorp joined 2026-08-11: gross 5,506,575, fees -3,063,573, rebates and rewards
   1,779,861, economic 4,222,864 on $332.9M (kept 1.27%; 42% of what was kept is rebates). Net by month: Aug 106K,
   Sep 1,260K, Oct 1,018K, Nov 1,839K; without rebates 38K / 739K / 447K / 1,220K. Section 5.1 and candidate
   "Systematic sports pricing" are corrected: the operator is active in the window and keeps money even without
   rebates, but only 0.4-1.0% of volume.
3. The weather fee was not 0.01 during the period the catalog measures. From BeefSlayer's actual charges the rate
   was 0.0500 (Sep), 0.0496 (Oct 1-18), 0.0500 (Nov 1-19) and 0.0100 (Nov 22-27). "BeefSlayer paid about 1% of
   volume in fees" is the 0.05 rate on 62% taker volume, not the 0.01 rate. Its Sep-Oct result was earned under
   five times today's fee: its September and October charges were $860, and the same fills at 0.01 would cost
   about $170.
4. Maker rebates: confirmed at zero for small accounts from Nov 22 in the daily data of ColdMath and BeefSlayer.
5. The 1-second matching delay is confirmed and is much wider than the guide says: 272 of 307 sports game markets
   in the top 1,000 carry `secondsDelay = 1` (football leagues, NFL, college sports, NHL, tennis, esports); the 35
   with 0 are all NBA. Section 6's "Premier League markets now carry a 1 s taker delay" becomes "everything except
   the NBA does".
6. Holding rewards: eligibility is the gamma flag `holdingRewardsEnabled`. True on 171 of the top 1,000 (99
   `zero_fees` markets, 42 elections, 19 long-dated crypto, 4 tech); false on every sports, weather and tweet
   market sampled. Section 11.3(d)'s "3.25-4% holding reward ... partly pays for the wait" holds only for those
   long-dated markets.
7. RN1 (named by the dev.to in-play post with "~$2.6M"): gross 15,090,230, fees -5,343,676, refunded 3,852,784,
   rebates and rewards 2,302,007, economic 15,901,347 on $747M (kept 2.13%, 14% of it rebates). Maker 30-day
   weighted volume 19.1M against 2.4M taker: a maker. Sep / Oct / Nov net 628K / 1,026K / 329K. The article's
   number and its story are both wrong.
8. Odaily's side names do not check out as catalog evidence: no profile is called exactly "Theo4" (the tool picked
   "theo43", an unrelated losing account), and the profile MonsieurDimanche shows 786,575 kept on $7.8M volume,
   not $15M. Neither is a sports account; both are removed from the sports candidate's wallet list.
9. The MEXC snippet in section 7 traces to a Blockonomi article of January 2026 about the account sb911
   (0xca6e9879b0a83eb471f974e159f2483c08b546f2). wallet_check: economic -31,173 on $1.25M; best month Jan 2026
   +53.6K; Dec -29.2K, Feb -31.9K, Mar -19.1K, Apr -12.7K; inactive since August. The "buy cheap ranges" example is
   one good month of a losing account. Two more tweet traders named in the press: Annica
   (0x689ae12e11aa489adb3605afd8f39040ff52779e) kept 701,432 on $21.2M (3.3%), peak +272K in Feb 2026, inactive
   since August; Prexpect (0xa59c570a9eca148da55f6e1f47a538c0c600bb62) kept 136,310 on $7.6M (1.8%), Sep +991,
   Oct -226, Nov -59. I did not check that their volume is in tweet markets; the attribution is the press's.
10. Live facts for the tweet candidate: fee type `culture_fees`, rate 0.01, tick 0.001, 30 buckets of 20 posts,
    reward band 4.5c with a 20-50 share minimum, holding rewards off; the Nov 20-27 weekly event has $1.84M volume
    and several overlapping events run at once (weekly from different start days, two-day, monthly).
11. Reward pools in the top 1,000 by 24-hour volume: 319 markets have one, about $56K a day in total. Median per
    market: `zero_fees` $240, tech $175, weather $89 (9 of 33 weather markets in this sample: Paris, Munich, Busan,
    Hong Kong, London, Madrid, Milan, Miami), elections $62, politics $50, sports $4 (24 of 347), crypto $3.
    The full-catalog count in NOTES.md (weather: 630 rewarded markets, median $10) is the better number for
    weather; this sample is the busiest end.
12. The CLOB book: asks come first-worst (0.99 ... 0.55) and bids first-worst (0.01 ... 0.47); the best price on
    each side is the last element. Confirmed on a live book.

### Credibility changes

- Kalshi-anchored maker: 4 to 3. The source is honest and exact, but no wallet, the US venue, and 93% of the result
  was two incentives that a new international account does not get (maker rebate verified at zero).
- Small-account spread capture: 3 to 2. The only positive first-person claim is an affiliate author with no wallet;
  every source with numbers shows a loss or a capacity limit of about $15 per market.
- Live sports feed versus broadcast: 2 to 1. Promotional source, wrong attribution, and the taker delay covers
  every league except the NBA.
- Complete-set and cross-venue arbitrage: 2 to 1. Zero executable profit in every careful source and in the lab's
  own scan; one of the two numeric claims could not be found on its page.
- All others unchanged. Nothing was dropped: every cited source exists and says what the catalog reports, apart
  from the items listed above.

### Not checked

Truncated Telonex addresses (full ones are in the notebook, not opened); what VibeTrader, Annica and Prexpect
actually traded; ColdMath's category mix in May-July; the Kalshi side of the temperature brackets; the companion
thedatascientist.com study; levelup, MEXC, SSRN, Depthy and Dune pages (still blocked).
