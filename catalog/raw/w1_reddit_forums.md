# W1 — Reddit, Hacker News and trading forums (collected 2026-11-27)

Scope: strategy posts and the practitioner discussions that confirm or debunk them, Sep–Nov 2026 first,
older material only where the mechanism still applies (date marked). Everything below was opened by me
unless a line says "search summary only". Downloaded pages and the tape used for the checks are in
`data/w1/` (git-ignored).

## 0. Access: what worked and what did not

- **Reddit: not reached at all.** Direct access is blocked (NOTES). WebSearch refuses `allowed_domains:["reddit.com"]`
  ("domains are not accessible to our user agent") and eight plain queries with subreddit names returned zero
  reddit.com results. An attempt to read Reddit through third-party archive mirrors was refused by the sandbox
  permission layer, so I did not pursue it. The only Reddit thread I can cite is one that a news site summarised
  (section 5). r/Polymarket, r/PolymarketTrading, r/Kalshi, r/algotrading, r/quant, r/CryptoCurrency are NOT covered.
- **Hacker News: reached** (Algolia API). 57 stories with "polymarket" since 2026-09-01, plus comment searches for
  six phrases (42 comments) and six full threads. HN is thin on mechanics; the useful part was the linked articles.
- Bloomberg ("Longshots Losing 98% of Time Dominate Kalshi, Polymarket Trading", 2026-10-07) returned a robot wall (403);
  not read. Medium not tried (blocked per NOTES). `datdiego.github.io/posts/polymarket-arbitrage` is 404.
- dev.to / IndieHackers results for "polymarket bot" are dominated by a handful of accounts that sell bots
  (benjamin_cup / benjamin_martin_749c1d57f, fatherson / ABROWNFOX001, xniiinx / soulcrancerdev). I treated them as
  advertising and only used them to pull wallet names for checking.

## 1. A tool fact verified on the way (affects every wallet check)

`data-api /v2/user-stats` has a field **`fees_refunded`** that `tools/wallet_check.py` does not print. `fees` is the
gross charge; `fees_paid = fees + fees_refunded` is what the account really paid, and
`economic_pnl = trade_pnl + fees + fees_refunded + rebates + rewards`. Checked on four wallets (identity holds to the dollar):

| wallet | trade_pnl | fees (charged) | fees_refunded | fees_paid | rebates+rewards | economic_pnl |
|---|---|---|---|---|---|---|
| RN1 | 15,090,230 | -5,343,676 | 3,852,784 | -1,490,891 | 2,302,007 | 15,901,347 |
| slip-me | 170,543 | -388,252 | 201,295 | -186,957 | 687 | -15,727 |
| b00k13 | 6,293 | -357 | 71 | -285 | 50 | 6,058 |
| Dava1414 | 1,163 | -155 | 0 | -155 | 135 | 1,143 |

Consequence: the tool's line "= after fees, before rebates" and its monthly NET column are too pessimistic for
any wallet with refunds (RN1's April 2026 row shows -3.6M fees, most of which came back). The headline
"ECONOMIC PnL" line is right. Monthly rows below are the tool's and carry this caveat.

## 2. BlockJuice teardown of RN1 (best source found; via HN)

- HN: "Reverse Engineering a Polymarket Bot", submitted 2026-11-19 by iankguimaraes, 1 point, 0 comments
  (https://news.ycombinator.com/item?id=50566070).
- Article 1: "RN1 Doesn't Need to Know Who Wins", Ian Guimarães, 2026-11-12,
  https://blockjuice.asof.sh/articles/rn1-strategy-teardown/
- Article 2: "How RN1's Bot Works, Read From 911,860 Fills", Ian Guimarães, 2026-11-18,
  https://blockjuice.asof.sh/articles/rn1-reverse-engineering/
- Data: every OrderFilled log where RN1 is maker or taker, 10 Aug – 10 Nov 2026 (92 days), plus the wallet's pUSD
  transfers and signed orders decoded from calldata (two samples). Author is selling nothing but a data framework.

What RN1 does (author's numbers):
- 911,860 fills in 87,642 markets, **all sports**, 110 series; 89.75% of fills as maker; 97.1% of fills after kickoff;
  **0 sells**; 98.65% of money back via auto-redeem at resolution, 1.35% via merges, done only when cash ran short.
- Rests bids on BOTH outcomes at once; the two bids sum to exactly 0.99 in 72–79% of observed pairs (one-tick-wide
  quote, the tightest possible), 2–3 levels on consecutive cents, fixed share size per league (~1,500 / 3,000 / 5,000 /
  7,500), re-quotes within seconds (filled orders median 11.8 s old), holdings do not move price or size.
- Average pair cost 0.985 incl. fees; pairs locked +2.1M pUSD; unpaired leftovers lost -486K (cheap-side extras lost
  10.2M, dear-side extras won 9.6M: "the cheap side is usually the team that is losing").
- Spent 222.5M; fills kept +1.6M = **0.71% of spend**; daily payments from four addresses added 935K (37% of the 2.53M
  total): one pays 15% of the taker fee on RN1's maker fills, one returns half of RN1's own taker fees.
- By job: quoting in-game +1.13M (+0.66%); **quoting pre-game -283K** (227K of it from fills >= 1 h before start; "a bid
  left on the book before kickoff is mostly a gift to whoever reads the team sheet first"); taking in-game +497K
  (+1.36% after fees); **taking pre-game +243K (+7.36%)**, all of it inside the last hour, 4,374 fills over 1,984 markets.
- **Who beats it:** 42,885 wallets hit its bids; it made +1.4M from everyone except its 50 busiest takers, who took
  504K back (the busiest: 37,654 fills, +169K). "A copy of this strategy has to spot them and widen or pull."
- Weakest series: ITF tennis -331K; best: college football +242K. Lost money on 39 of 92 days; worst drawdown 323K.
- Capital: cash plus open positions 1.19M–2.66M (median 1.92M). Client fits Polymarket's own Python client.
- Open questions listed by the author: no order book (cancels unseen), two payers unexplained, two tennis matches
  where RN1 paid 0.50–0.51 for both sides (1.0M spend, resolved 50/50, -36K) look like volume or a fault.

My check (`python3 -I tools/wallet_check.py RN1 --monthly`, 2026-11-27): wallet 0x2005d16a84ceefa912d4e380cd32e7ff827875ea,
joined 2024-12-12, 5.32M fills, volume $747M. All time: shown P/L 15.09M, fees charged 5.34M, refunded 3.85M (paid 1.49M),
rebates+rewards 2.30M (taker 620K / maker 1.31M / rewards 375K), kept 15.90M = 2.13% of volume; rebates/rewards = 14% of kept.
Maker tier 4 (15% rebate), 30-day maker weighted volume 19.1M. Monthly (gross / fees charged / rebates / volume):
2026-07 1.72M / -314K / 415K / 102.7M; 08 1.31M / -247K / 288K / 67.9M; 09 561K / -294K / 361K / 85.9M;
10 918K / -160K / 267K / 66.7M; 11 (to the 27th) 217K / -99K / 212K / 51.0M. Gross as % of volume: Jul 1.68, Aug 1.93,
Sep 0.65, Oct 1.38, Nov 0.42 -> the margin is shrinking; in Sep and Nov rebates are 58% and 64% of the month's net.
The article's 92-day figures (1.6M from fills + 0.94M payments) are the same order as the tool's Aug–Nov rows.

## 3. Kacho (kacho.io) — a small solo bot with a public wallet, honest post-mortems (found via WebSearch)

- "I ran an arbitrage bot on Polymarket. Here are the real numbers." 2026-06-06,
  https://kacho.io/polymarket-arbitrage-real-numbers
- "Adverse selection eating away my Polymarket bot arbitrage profits." 2026-06-30,
  https://kacho.io/why-my-polymarket-arbitrage-bot-lost-money
- "I'm open-sourcing my Polymarket market making bot." 2026-07-21, https://kacho.io/open-sourcing-my-polymarket-bot
  (repo github.com/kachence/polymm, MIT; scrapers and the live Rust rewrite are NOT in it)
- "I recorded Polymarket's 5-minute crypto markets for two months. Here's the dataset." 2026-06-16,
  https://kacho.io/polymarket-5min-crypto-dataset
- "Every awesome list rots. I built one that won't." 2026-08-13, https://kacho.io/prediction-almanac
  (github.com/kachence/prediction-almanac — list of datasets and tools, section 9)
- Older than the window, kept because the mechanism is exactly the time-gap one and the wallet is still trading.

Mechanism: scrape sportsbook odds (Spinbetter, GGBet…), de-vig to a fair probability, post a limit bid one cent above
the best bid wherever fair − bid >= 7 points, in **pre-match esports** markets with 20–30 cent spreads and real volume
(example 2026-06-05: MPL Indonesia, bid 46 / ask 73, $237 volume). When one side fills, bid the other side so both
cost <= 0.93. If the hedge does not fill, he is left with a directional bet. Started with about $1,000.

His numbers: Jan–late Mar 2026, 3,858 bets, $95,830 volume, +$4,973; locked arbs +$8.3K, forced directional -$3.2K.
Why it died:
- **Stale reference price = being picked off.** His odds were up to 30 min old (later 10 min, now 5 min at ~$3/day).
  Odds sampled every 7–8 min, 6–20 Mar 2026, 2,555 matches: the line jumped >= 5 points before the match went live in
  about a third of matches — CoD 60% (median move 10.9 pp), LoL 49% (4.9), Dota 2 37% (3.1), CS2 31% (1.9), MLBB 28%,
  SC2 17%, Valorant 12%, R6 0%. "My 60¢ bid is now a gift… whoever has the up-to-date odds lifts it."
- **Competition:** fill rate on outcomes he bid: Jan 37.4% (760/2,034), Feb 15.0%, Mar 5.0%, Apr 1.0% (222/22,467);
  locked arb profit $2,865 / $4,158 / $1,254 / $17. "Faster bots would outbid me by a cent."
- Expansion to basketball, football, hockey, rugby: all net negative (-$509 total); arb covered directional loss 3.3x in
  esports, under a third in football/basketball.
- Bugs (AI-written code): swapped team probabilities, odds from an older match, odds from a different game.
- Shin de-vig made him overpay favourites (Jan favourites ROI 1.5% vs 11.7% in Feb with proportional de-vig).
- 5-minute crypto: his BTC bot backtested at 3–5% ROI after fees on his own 1-second book dataset and lost about $600 live.
- Dataset: ~89,000 five-minute markets, 7 coins, 26.8M one-second top-of-book rows, 24 Mar – 18 May 2026 (pre-TWAP rules).

My check (`wallet_check b00k13`): 0x1c5575dc20e4ea54d1bb09ccda72ccf8a3b684ce, joined 2026-01-06, 12,238 fills, volume
$144,398. Shown P/L 6,293; fees paid 285; rebates+rewards 50 (1% of kept); kept 6,058 (4.2% of volume). Monthly net:
Jan 2,295; Feb 2,086; Mar 405; Apr 105; May 0; Jun 17; Jul 617; Aug -106; **Sep 285; Oct 192; Nov 86** on $2.7–4.7K
monthly volume. Jan–Apr gross sums to 4,961 vs his claimed 4,973: the blog is truthful. The edge now pays lunch money.

## 4. Other first-person bot posts with numbers (all outside the window; mechanism notes only)

- manja316, "176 Trades on Polymarket: What My Bot Actually Made", dev.to, 2026-03-14,
  https://dev.to/manja316/176-trades-on-polymarket-what-my-bot-actually-made-its-not-what-you-think-1nab
  15-minute crypto. Total about **$2 on 176 trades**. Both-sides "arb" (UP+DOWN asks < $1): 98 true arbs, 97% wins,
  $0.10–0.30 each; half-fills (one FOK leg rejected) turned arbs into naked bets with -$8 to -$20 losses on ETH/SOL/XRP.
  Late momentum (minute 8–12, Binance move > 0.20%): backtest 95.7% win, live ~80% -> net loss because entries are at
  0.85+. Late snipe (minute 13, buy 0.93–0.97): net loss. "BTC +0.517% but price $0.99: the market ate the edge."
  No wallet given.
- Chudi Nnorukam, "Polymarket BTC Up/Down Bot: What 7 Live Trades Showed", 2026-11-10 (trades from 26–27 Apr 2026),
  https://chudi.dev/blog/polymarket-btc-up-down-bot — Binance sharp move -> limit buy; right on 6 of 7, lost $1.36
  (five entries at 0.92–0.96, one loss at 0.23 wiped everything). Page sells a $49 bot kit and VPS affiliate links.
- 1kto1m, "February 2026 Changed Polymarket Forever", dev.to, 2026-06-25,
  https://dev.to/lkto1m/february-2026-changed-polymarket-forever-heres-what-happened-to-my-bots-numbers-2fi5
  Claims: removal of the old 500 ms taker delay plus dynamic taker fees killed pure Binance->Polymarket taker latency
  bots the same week ("wallets… simply stopped trading"); his own maker-side "crowd momentum" bot (enter the side
  priced >= 0.70–0.72 with resting orders, 78 trades/day) kept $0.031 EV per trade. No wallet, not checkable.
- Emil Nielsen, "Polymarket's New Fee Structure…", dev.to, 2026-06-24 — fee explainer; maker rebate share cut from
  100% to 20% of taker fees. Superseded by the 2026-11-20 tier system in NOTES.
- Benjamin-Cup, "Inside a Polymarket Bot: How 'Slip-Me' Generated $111K in 23 Days", dev.to, 2026-05-06 (edited 07-29),
  https://dev.to/benjamin_cup/inside-a-polymarket-bot-how-slip-me-generated-111k-in-23-days-trading-5-minute-bitcoin-markets-5an1
  Claims +$111K on $4.3M, 22 of 23 days profitable, pair cost $1.02 (-$97K) and late directional scaling (+$204K).
  **My check (`wallet_check slip-me`, 0x476639d9845d7a0261cb005dae6473f089ff5a03): shown P/L +170,543; fees charged
  388,252, refunded 201,295, paid 186,957; rebates 687; kept -15,727 on $7.44M volume. Stopped trading after July 2026.**
  The "profitable bot" lost money once fees are counted.
- xniiinx, "Automated Polymarket Trading Bot Hits $5,182 Profit in One Day… (Dava1414)", dev.to (date not captured).
  My check: Dava1414 0x994f892c9dd2e75edc319e3282354cd3f38af39d all-time shown P/L 1,163, kept 1,143, May +1,554,
  June -413, inactive since. The headline number does not exist in the account's history.
- ABROWNFOX001 / "fatherson", "How Smart Traders Crush Polymarket Live Markets: The 45-Second Information Edge",
  dev.to, 2026-06-12, https://dev.to/fatherson/how-smart-traders-crush-polymarket-live-markets-the-45-second-information-edge-54f7
  Claim (no data): official feeds update ~3 s after a goal, streams 45–60 s later; esports game servers 1–2 s vs Twitch
  15–60 s. Sells bots over Telegram. My check of the author's own account abrownfox001
  (0x12b712029efeee7efc4066e98e4e1b6beb8b1b0b): shown P/L 19,353; fees charged 78,291; rebates 5,784; kept 7,617 on
  $1.56M volume (0.49%), 76% of what was kept is rebates; Jan–Apr 2026 about -58K before refunds; Sep +479, Oct -9, Nov +218.

## 5. The one Reddit thread reachable second-hand

- Reddit: u/marvmarv2693, r/PredictionMarkets, "I spent a few weeks trying to beat Polymarket. Ten…" (posted "a couple of
  months" before September 2026), https://www.reddit.com/r/PredictionMarkets/comments/1ubletl/i_spent_a_few_weeks_trying_to_beat_polymarket_ten/
  — NOT opened; read through Action Network, Luke Garrison, 2026-09-03/04,
  https://www.actionnetwork.com/news/is-it-possible-to-beat-polymarket-reddit-user-attempts-10-different-trading-strategies
- 10 months of data, 600 liquid markets, ten backtested ideas, **all failed**: 8-agent LLM swarm (Brier 0.38 vs market
  0.30); copying top-15 wallets (**-13.6% out of sample** after post-trade price movement); favourite–longshot (longshots
  under 0.20 won 1.15% vs 0.73% implied — i.e. not overpriced in his sample); momentum; multi-leg books; calendar arb;
  **settlement-lag discounts**; crypto round-number bias; illiquid-market limit orders; re-slicing.
- Base rate: only 16.8% of markets with > $10K volume resolved YES.
- Comments (about 40, as summarised): 3% of accounts drive nearly all price discovery, so track calibration not ROI
  (OP: by the time a fill is visible the price has adjusted); a bot developer reported "233 screens a day with zero
  executions" for cross-venue arb under strict thresholds; OP: different settlement rules and fees wipe cross-venue edges.
- Caveat: the article says "standard 2% fees", which is not Polymarket's fee formula; the backtest's fee model is unknown.

## 6. Hacker News comments worth keeping (practitioner voices)

- qoez, 2026-10-16, https://news.ycombinator.com/item?id=50121910 : "Sports are mostly very well priced (live sports not
  so much). Many new markets that are just invented by polymarket/kalshi though SIG are basically on an even playing
  field with you… if it's a niche low liquidity market they probably don't pay much attention to it anyway so you can
  easily come in and price it with a large edge… I mostly take liquidity that are placed at poor prices where I've
  spent many weeks on trying to figure a more informed way to price it." No wallet.
- PaulRobinson, 2026-11-24, https://news.ycombinator.com/item?id=50627477 : in-play latency arbitrage with a data feed 2 s
  faster than the bookmaker's "has been a widely used strategy… on betting exchanges for decades… and is now leaking
  into prediction markets."
- kart23, 2026-10-16, https://news.ycombinator.com/item?id=50120538 : "the overwhelming majority of trading volume is HFT
  firms with faster access to data… these firms pay the prediction markets for that access."
- m00dy (Blockrotate job ad), 2026-11-03, https://news.ycombinator.com/item?id=50349000 : "Polymarket orderbooks are bounded,
  often thin, and subject to severe adverse selection. When a high-volume leader buys, the book moves immediately. If
  followers lag by a few hundred milliseconds, or if a platform taxes every order with a 50bps fee, follower alpha
  drops to zero." (A copy-trading vendor saying copy trading needs co-location.)
- peikail ("Who wants to be hired"), 2026-11-03, https://news.ycombinator.com/item?id=50347191 : claims a live book on Kalshi
  and **Polymarket US** — "short-dated event contracts, cross-venue hedged market making, and late-window pricing
  models… $3-4k/day net… no losing day" over two weeks. Unverifiable (track record "under NDA"); US venues.
- kibwen, 2026-11-24, https://news.ycombinator.com/item?id=50628436 : once bots follow insider-looking flow, insiders who know
  X is false are paid to fake the signal.
- none_to_remain, 2026-09-03 (id 49555228): the only pure arbitrage he ever had was IEM vs Kalshi at Kalshi's launch.
- adamewozniak (TurbineFi), 2026-10-28, https://news.ycombinator.com/item?id=50279152 : "Most of our users focus on crypto
  and weather"; launched a sports arb finder for Kalshi / Polymarket US / Novig. Vendor.

## 7. PredictPnL articles (via HN, user lorande; the site is a product, the method is stated)

- "Who are the best Polymarket traders? The leaderboard and the skill ranking disagree", 2026-11-05,
  https://predictpnl.com/articles/best-polymarket-traders-profit-vs-skill — of the top 40 by all-time profit ($284.2M
  together) only 2 are in the top 100 by their per-price-band skill score; 24 of the 40 have < 50 closed trades or are
  outside the top 1,000 by volume; the #1 wallet has 22 closed trades. Top-20 by skill: 1,962–17,960 closed trades,
  median all-time profit $469K, result = 0.7% of volume ("small edge, many trades").
- "How many trades does it take to tell skill from luck", 2026-11-24,
  https://predictpnl.com/articles/how-many-trades-to-tell-skill-from-luck — zero-edge simulated wallets reach their +0.05
  threshold 1 in 18 times at 100 trades, 3 in 100 at 1,000, 1 in 500 at 3,000. Practical rule: a wallet needs
  thousands of closed trades before its record means anything.
- Teaser (not opened): "Where do the most skilled traders find their edge? Mostly below 25" (2026-11-10): 55 of the top
  100 by skill get most of their score from shares bought under 0.25.

## 8. News-latency case measured by me: "Will Jensen Huang rejoin NVIDIA by December 31, 2026?"

- Source: "Polymarket : Autopsie d'un délit d'initié…", deucalionn, 2026-11-23,
  https://deucalionn.vercel.app/polymarket-delit-initie-jensen-huang-nvidia/ ; HN thread 481 points / 278 comments,
  https://news.ycombinator.com/item?id=50626578 (2026-11-24); WSJ card on two "suspicious clusters" making $340K (not opened).
- Article's claims: account `ljhggk` (wallet created 81 h earlier) bought 71,518 YES at 0.065 for $4,648 between 01:19 and
  02:28 UTC on 23 Nov; Trump's Truth Social post at 03:57 UTC; NVIDIA press release "14:30 CET" (13:30 UTC); resolved YES.
- My check, market tape `data-api /v2/trades?condition=0x27748e74503ff93d998d1e857980c43eca77c38efd61f642dd43d41a18525250`
  (10,036 fills; fee schedule on the market: rate 0.05, tech) and CLOB `prices-history`:
  - After the Trump post the YES price drifted 0.078 -> 0.11 over about an hour and then sat at 0.10–0.12 for nine hours
    (30-minute VWAPs 04:00 0.080, 05:00 0.109, 09:00 0.100, 13:00 0.112). The sister market "by November 30" stayed at
    0.02–0.03 the whole time.
  - 13:30:59 UTC: `WarriorPooh` buys 17,432 YES at 0.115. Then 25 minutes of nothing.
  - **13:55:55 UTC** WarriorPooh buys 23,453 at 0.149 and 28,236 at 0.185; first print >= 0.50 at 13:56:07; 0.886 at
    13:56:58; 0.938 at 13:57:07; 0.99 at 13:57:16. So the repricing from first aggressive print to > 0.90 took about
    **60–75 seconds** (block timestamps, ±3 s). In the 120 s after the first >= 0.50 print: 2,484 shares traded below 0.50,
    29,160 at 0.50–0.90, 14,241 at 0.90–0.97.
  - I could not confirm the exact release time. If the article's 13:30 UTC is right, the market ignored the release for
    25 minutes; if the release was at ~13:55, the gap was about one minute. Either way a buyer who reacted within
    10–30 s of the headline could still buy tens of thousands of shares below 0.90 with a taker fee of at most 1.25 c.
  - `WarriorPooh` (0x853c37a959a5791b849e3f3225c7f5963746bd03): 86,278 YES bought in this market at an average 0.151
    ($13,005). `wallet_check`: joined 2025-12-11, 808 markets, 8,947 fills, volume $3.53M, shown P/L 350,358, fees 8,933,
    rebates+rewards 5,454 (2%), kept 347,389 (9.8% of volume), **positive in each of 12 months** (Sep 2,983; Oct 6,970;
    Nov 170,304). Low-frequency, fee-light, not a rebate farmer: a news/judgement trader worth deconstructing.
- One event is one sample. It shows the scale of the gap on a $5.7M headline market, not an edge.

## 9. Structural context from other sources

- Wired, Kate Knibbs, "Over $600 Million in Polymarket Election Trades Took Place After Races Ended", 2026-10-15,
  https://www.wired.com/story/over-dollar600-million-traded-on-polymarket-election-contracts-after-races-ended/ (via HN).
  The Ethiopia market stayed open **123 days** after the result was clear because the rules waited for the swearing-in;
  ~$284M of its $285M volume was pairs of accounts trading with each other (38,000 loops, 98% zero P&L, median holding
  9 s) — "activity farming" for a hoped-for token; Romania market: 99.6% wash volume in some weeks. Two lessons:
  volume in dead markets is fake, and "event known, market unresolved for months" exists — the price there is a
  capital-lock-up discount, not a mistake.
- arXiv 2605.31431, Gebele & Matthes, "When Certainty Is Not Worth It: Capital Lock-Up and Settlement Discounting in
  Prediction Markets", 2026-05-29 (abstract only): near-certain contracts trade at a maturity-dependent discount that is
  a priced settlement wedge; adjusting for it removes 48–88% of the apparent mispricing; negRisk conversion and
  yield-bearing collateral shrink it.
- arXiv 2605.00864, Cheng, Yang, Zou, "Arbitrage Analysis in Polymarket NBA Markets", 2026-04-22 (abstract only): 75M book
  snapshots, 173 games: 7 executable single-market arbs, median life 3.6 s; 290 combinatorial episodes, mostly in the
  last minutes, median 101 bp, 76.9% capped at ~14.8 shares.
- Search summaries only (pages not opened): > 1,150 Polymarket markets went to UMA dispute in 2026; a UFO market bought
  at 0.99 was overturned by a token vote; weather-bot claims ($1K -> $24K London; "$88K weather bot"; airport-station
  vs city-centre error of 3–8 degrees; ECMWF/GFS update every 6 h) all come from promotional dev.to / Medium posts.
- Prediction Almanac README (github.com/kachence/prediction-almanac, fetched raw, updated daily) — datasets worth knowing:
  pmxt archive (archive.pmxt.dev, hourly Polymarket book snapshots from Feb 2026), HuggingFace TimeSeventeen/Polymarket-v1
  (+v2; trades with resolution and fees, 2022-11 onward), HuggingFace vpcapitano/polymarket-genesis-liquidity (10-level
  depth, 2025-10–2026-03), jon-becker/prediction-market-analysis (~36 GB trades through 2025), Marketlens (tick book
  history from Mar 2026, paid above free tier), outcometick (crypto up/down ticks since Jun 2026, paid), Probalytics
  (ms book history, paid). Odds feeds: The Odds API, Pinnacle API, Betfair, Live Tennis API. Papers: arXiv 2604.24366
  (trade direction inferred from the public book is only ~59% accurate), 2602.19520, 2607.14430 (Kalshi sports
  calibration breaks in the final ten minutes). Skill leaderboards: OVERROUND, PMWallets.

## 10. What this adds up to (my reading, to be attacked)

1. Every checkable "bot made $X" claim from the promotional cluster failed the wallet check (slip-me -15.7K,
   Dava1414 +1.1K total, abrownfox001 +7.6K of which 76% rebates).
2. The two honest, verified operators (RN1 at $2M capital, b00k13 at $1K) run the same idea — rest bids on both sides
   of a sports match and collect the pair — and both are documented as being **picked off by someone with a fresher
   outside price**: RN1 loses 504K per quarter to 50 takers and 283K on pre-game quotes; b00k13's 7-point "edge" was
   negative after line moves. The published evidence therefore points at the taker side of the time gap in sports:
   sportsbook line moves and team news pre-game (minutes), score events in-game (seconds).
3. Crypto up/down taker ideas (momentum, snipe, both-sides) are consistently reported dead by the people who tried.
4. Copy trading is contradicted three ways (Reddit backtest, PredictPnL leaderboard study, a copy-trading vendor's own
   job ad).
5. On a headline news market the measured repricing took about a minute — slow enough for a watcher with a news feed,
   but it is one case.
