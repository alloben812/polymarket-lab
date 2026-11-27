# R1 — Academic papers and quantitative studies (collected 2026-11-27)

Scope: arXiv (API), plus SSRN / NBER / CEPR working papers found through WebSearch. Window of interest
2026-09-01 .. 2026-11-27; older papers kept when the mechanism still applies (date marked).
How to read: "ABS" = I read the abstract only; "FULL" = I downloaded the arXiv HTML / PDF and read the passages
quoted; "2nd-hand" = I only saw a press or search summary, the paper itself was not opened.
Local copies: `data/papers/full/<arxiv-id>.txt` (text of the HTML), `data/papers/arx_list.txt` (149 hits of the
arXiv queries, date | id | title | authors), `data/papers/nber_f243677.txt`.

arXiv queries run (sorted by submittedDate, 60 per page): `all:polymarket` (3 pages, ~95 hits), `all:kalshi`,
`"prediction market" AND arbitrage`, `"prediction markets" AND microstructure`, `"favorite-longshot"`,
`"prediction market" AND LLM AND forecasting`, `"prediction market" AND "wash trading"` (0), `... AND sportsbook`
(0), `"prediction markets" AND "lead-lag"`, `"event contracts"`.

No paper names a Polymarket profile or a 0x address in its text, so there was nothing to run `wallet_check` on
from the sources. I ran it on three wallets I picked myself from the weather leaderboard (section 9).

---------------------------------------------------------------------------------------------------------------

## 1. Arbitrage (within a market, across related markets, across venues)

### 1.1 Shi & Zhai, "Combinatorial Arbitrage in Prediction Markets" — arXiv 2610.23517v4, 2026-10-16 — FULL
https://arxiv.org/abs/2610.23517
- Data: Polymarket, 23 Jun – 3 Aug 2026 (6 weeks). Own live collector of venue-wide book snapshots + level
  updates (Polymarket has no retrospective depth feed), on-chain fills: 145.16M trades, $5.23B volume, 679K
  addresses. 1.9M logical relations over >255K contracts. Fees included ("the sports fee rate was still 0.03 on
  28 June 2026; Polymarket raised it to 0.05 on 10 July 2026").
- Three relation layers: (1) venue-asserted = NegRisk groups (20,866 groups -> 20,118 partitions + 748 mutual
  exclusivity); (2) venue-derived = rebuilt from typed sports fields (match, line: e.g. over-3.5 implies over-2.5;
  spread implies moneyline) and crypto/finance threshold ladders ("Bitcoin above $65,000 on July 28, 5AM ET"
  implies "above $64,800"); (3) semantic-inferred = LLM reading of resolution text. Sports = 453,190 relations,
  crypto = 89,088, together 94.6%.
- Result: 491,827 arbitrage windows detected, 125,095 executable, 112,376 settled. "an ideal arbitrageur that takes
  the full displayed depth of every opportunity and reuses its capital at resolution accumulates $2.50 million of
  guaranteed profit, a risk-free return of 3.5% a week on the $11.1 million of capital the strategy requires at
  its peak." First execution per window alone: $1.10M on $40.6M committed (2.7%).
  Profit split: venue-asserted 34% ($852K on $22.6M, 3.8%), venue-derived 59% ($1,467K on $79.0M, 1.9%),
  semantic 7% ($179K on $12.1M, 1.5%). "The median window guarantees 0.5% on capital, but half of the accumulated
  take comes from" high-return windows. Capital-weighted holding period 1.6 days; median window ~3 h to resolution
  for venue-derived.
- Speed: among windows lasting >= 0.3 s the median duration is 2.9 s (venue-asserted), 6.3 s (venue-derived),
  ~31 s (semantic-inferred). Order delay robustness: with 100 ms delay 71.6% of orders fill in full (92.4% of
  quantity); "With a 1-second delay, 54% of the orders fill in full and the orders fill 84% of the submitted
  quantity; the settled orders pay 79% of the profit at resolution ... and 22% of them lose money at resolution"
  (legging risk: an unequal fill is no longer an arbitrage). 50% participation keeps 57% of profit.
- Who takes it: "In 44% of the executed windows based on venue-asserted relations, at least one trader is observed
  to trade every leg ... venue-derived and semantic-inferred ... 15% and 9%." Median lag from window open to the
  matched trade ~2.6 s. "854 addresses make these trades, and the 10 most active ones account for 78% of the
  windows with such a trade." Addresses not listed in the text.
- Example in the paper: Argentina–Cape Verde 3 Jul 2026, "Argentina wins" sold 230,629 shares in 234 executions.
- Implication for us: the slowest, least-contested layer is the semantic one (31 s windows, 9% taken), i.e. a
  seconds-scale game, not milliseconds, and it needs brains (relation discovery) more than co-location. But the
  profit in that layer is small ($179K in 6 weeks at FULL depth for everyone), 22% of delayed fills lose, and it
  needs multi-leg taker execution with 0.05 sports fee. Median edge 0.5% of capital. For a few hundred euros the
  binding limit is order minimums and legging risk, not capital. Testable: we cannot replay depth (no WebSocket
  here), but `prices-history` + `trades?condition=` can show whether nested crypto/sports thresholds printed
  inverted prices and for how long (trade prints, not quotes — an upper bound on the opportunity).

### 1.2 Gebele, Mutzel, Matthes, "Executable Arbitrage and Market Efficiency in Prediction Markets" — arXiv 2608.00666, 2026-08-01 — FULL
https://arxiv.org/abs/2608.00666
- Data: historical CLOB panel, 32,702 events, 259M trades, events listed through 31 Dec 2025; NegRisk Adapter
  conversions from Goldsky subgraphs; older FPMM panel (~53K trades).
- NegRisk Adapter converts NO-side baskets into YES + collateral before settlement; the reverse is not available.
- "we estimate $1.12 million in arbitrage profit across the two realization channels: $1.086 million from
  converter-enabled strategies and $32 thousand from settlement-based basket formation." Ten most profitable
  addresses take ~75% (number garbled in the HTML, "75" followed by lost % sign). One anomalous cluster of 75
  conversions by three addresses (381,748 USDC in seven minutes) was excluded.
- CLOB panel: 2,098 positive YES-side violation episodes vs 36 NO-side. Exact-duration episodes: median 16.15 s
  (YES side, n=253) and 7.99 s (NO side, n=5); 366 of 624 episodes span more than 50 minutes (YES side, where no
  conversion exists, so the only exit is holding the full YES basket to settlement).
- Decay: "Through July 2024, median profit is approximately one USDC per conversion ... During late 2024 and 2025,
  the median declines to approximately 0.20 USDC ... By early 2026, median profit falls further to approximately
  0.08 USDC." ~80% of conversions are maker-acquired (the arbitrageur rests bids on NO legs), all-taker ones are
  rarer but larger.
- Compares itself with Saguillo et al. (below): their "$10.6 million from same-condition rebalancing and $29
  million from rebalancing mutually exclusive NegRisk outcomes"; Gebele's stricter reconstruction of the same
  window yields $291,424 — i.e. the famous "$40M of arbitrage" is mostly an accounting artefact of grouping fills
  in a 950-block window.
- Implication: NegRisk "sum of NO" arbitrage is a crowded, pennies-per-conversion business by 2026. The long-lived
  violations are YES-side (sum of YES asks < 1), which lock capital until settlement.

### 1.3 Saguillo, Ghafouri, Kiffer, Suarez-Tangil, "Unravelling the Probabilistic Forest: Arbitrage in Prediction Markets" — arXiv 2508.03474, 2025-08-05 — ABS (old, mechanism reference)
https://arxiv.org/abs/2508.03474 — "We find a realized estimate of 40 million USD of profit extracted" (market
rebalancing + combinatorial). See the correction in 1.2. This is the paper behind most "arbitrage bot made $X"
posts.

### 1.4 Cheng, Yang, Zou, "Arbitrage Analysis in Polymarket NBA Markets" — arXiv 2605.00864, 2026-04-22 — FULL
https://arxiv.org/abs/2605.00864
- Data: 75,088,497 book snapshots, 173 NBA games, 4 Feb – 4 Mar 2026, polling cycle 3.6–5.5 s.
- Single-market (YES+NO): 37 raw episodes, 30 post-game (hollow book, not real); 7 valid in-game, median duration
  3.6 s; capped at $100 per episode total profit $210.19.
- Combinatorial moneyline vs spread: 290 executable episodes in 8.59M states, "overwhelmingly concentrated in the
  final minutes of live play", median return 101 bp, "76.9% of combinatorial opportunities constrained to an
  average executable size of just 14.8 shares". "confining risk-free extraction strictly to the retail scale."
- Implication: consistent with 1.1; in sports the mispricings appear in the last minutes of a game when books thin
  out; size is tiny (which is fine for us) but fee was lower then (0.03, now 0.05 for sports).

### 1.5 Gebele & Matthes, "Semantic Non-Fungibility and Violations of the Law of One Price in Prediction Markets" — arXiv 2601.01706, 2026-01-05 — ABS
https://arxiv.org/abs/2601.01706 — >100,000 events on ten venues 2018–2025; ~6% of events are listed on more than
one venue; "semantically equivalent markets exhibit persistent execution-aware price deviations of 2-4% on
average". Cross-venue arbitrage is "capital-intensive or unenforceable" (capital on both venues, different
resolution rules).

### 1.6 Gebele & Matthes, "When Certainty Is Not Worth It: Capital Lock-Up and Settlement Discounting in Prediction Markets" — arXiv 2605.31431, 2026-05-29 — FULL (partly)
https://arxiv.org/abs/2605.31431
- Near-certain contracts trade below $1 because the dollar is locked until oracle settlement. Example: "Will Jesus
  Christ return in 2025" NO at ~$0.96 for months = ~4.2% for most of a year.
- Sample: Polymarket inception – 31 Dec 2025; contracts >= 0.90 for seven daily snapshots, duration >= 14 days.
  Annualized settlement wedge (ASW) is positive and maturity dependent; minimum-ASW frontier mean 3.06% p.a.;
  adjusting for it removes 48–88% of the apparent long-horizon miscalibration of near-certain prices. NegRisk
  conversion and the 4% "Holding Rewards" program compress the discount.
- Implication: "buy 97–99c and wait" (resolution bond) is priced like a money-market rate, not free money.

### 1.7 Portnaya, "Do Prediction Markets Match Option Prices? Bitcoin Threshold Evidence from Binance and Polymarket" — arXiv 2606.19517, 2026-06-17 — ABS + passages
https://arxiv.org/abs/2606.19517
- Polymarket BTC threshold YES price vs risk-neutral digital from Binance options, same strike/maturity, hourly.
  Main Sept 2023 contract: mean gap 5.6 pp over 214 hourly obs (t = 6.46); pooled three markets 6.3 pp (287 obs);
  vs Deribit 11 pp. Gap persistent, "AR(1) half-life of roughly four hours". "largest at low option-implied
  probabilities and long maturities" (speculative demand for cheap YES). "A delta-hedged arbitrage proxy remains
  profitable after conservative transaction costs, though with marginal statistical precision." ETH: mixed.
- Red flags: sample is 2023 (thin, pre-CLOB-era liquidity), 3 markets.

---------------------------------------------------------------------------------------------------------------

## 2. Lead-lag, latency and the "time gap"

### 2.1 Young, "OpenMarket: A Synchronized Polymarket-Binance Dataset" — arXiv 2607.26245, 2026-07-28 — FULL (passages)
https://arxiv.org/abs/2607.26245 ; dataset `gregyoung14/openmarket-btc-polymarket` on HuggingFace (exists, checked)
- 727M rows, 54 Polymarket days between 2026-02-12 and 2026-05-15, BTC 15-minute markets vs Binance BTC/USDT,
  2,936,031 lead-lag pairs.
- "an apparent 16 ms median lag on venue source clocks ... remaining single-vantage constant-offset ambiguity of
  approximately plus or minus 99 ms. A synchronization-free event study, measured only on the collector clock,
  independently shows that Polymarket quotes respond to large Binance moves after a median 347 ms."
- Trading attempt: 43 microstructure features, walk-forward logistic: "does not beat, and slightly underperforms,
  the probability already implied by Polymarket's own order book"; simulated trading with 1% fee + 0.5% slippage
  "nets -0.116 normalized payoff units per attempted trade". "No strategy iteration survived fees".
- Implication: independent confirmation of the lab's own conclusion (book absorbs a Binance move in 0.3–2 s; no
  edge for a non-co-located taker). Pre-dates the 50 ms taker delay (Aug 17).

### 2.2 Dai, Jia, Yu (Stanford), "Settlement Manipulation in Prediction Markets" — arXiv 2606.31675v2, 2026-06-30 — FULL (passages)
https://arxiv.org/abs/2606.31675
- Sample 1 Jul 2025 – 8 Apr 2026; BTC 5-minute contract live 12 Feb – 8 Apr 2026. Median cycle: ~105K shares on
  Polymarket vs $3.15M Binance volume.
- A burst of one-sided Binance spot flow in the final 10 s before settlement, concentrated in undecided cycles;
  25% reversal after. "Just 821 wallets fit, about one in three hundred of the roughly 243,000 that traded the
  contract. They take $8.2 million in the manipulated cycles and break even in the rest ... Retail traders ...
  lose $7.6 million in these cycles, whereas market makers, who earn $3.1 million in normal cycles, lose only
  $0.6 million." In cycles priced >= 90% for one side a push still overturned the outcome "one time in three".
  Manipulated cycles: 56% in Asia/overnight hours, 44% on weekends.
- "it disappeared from the five-minute contract once Polymarket began settling on a 60-second average price"
  (TWAP from 7 Aug 2026, 60 s from 14 Aug). Bloomberg covered the paper on 15 Jul 2026; Polymarket announced the
  change 30 Jul.
- Implication: (a) dead since mid-August; (b) explains why pre-August "buy the 95c side in the last seconds" was a
  loser; (c) not something a small trader could or should do (needs to move Binance; it is market manipulation).

### 2.3 Fan, Sun, Zhao, "Whether Is Not When: Separating Occurrence from Timing in Polymarket Prices" — arXiv 2610.36639, 2026-10-27 — FULL (passages)
https://arxiv.org/abs/2610.36639
- All 1.24B on-chain trades, 2.37M markets through Sept 2026. 3,686 geopolitical-conflict markets -> 208
  unscheduled events that happened, each dated by the first Web report meeting the resolution rule (tau); 51
  central-bank decisions as scheduled controls.
- Share of events whose contract was priced >= 0.5: 43% seven days before tau, 56% one day before (109/193), 64%
  six hours before, "78% one minute before" the first report. All 51 central-bank decisions were priced correctly
  a day ahead (98% a week ahead) -> no gap on scheduled rate decisions.
- "we take the event of a ladder to become known at the price-implied time, when the price of a contract that
  resolved Yes first reaches 0.95 and never falls below 0.9 afterwards ... For the dated events, this time differs
  from tau by a median of two minutes."  => median reaction of the price to the first public report is ~2 min.
- One day before tau the median price was 0.97 for talks/meetings/calls, 0.76 for sanctions, 0.32 for military
  strikes and ceasefires; 0.10 for contracts whose deadline was within a day after tau.
- Timing profits: of 13,241 accounts with timing profit in >= 5 ladders, 7.8% significant, "1.4% to 3.8% have true
  skill"; the 337 significant ones have median volume $120K and post (maker) 62% of their volume vs 36% for
  others; top 1% take 80% of timing profit. Their order flow adds nothing to price-based prediction.
- Deadline ladders: "only about one eighth of the information in prices concerns timing"; the date read from
  prices fell a median 18 days after the event.
- Implication for the time-gap hypothesis: in unscheduled geopolitical events ~22% of YES outcomes are still below
  0.5 one minute before the first web report, and prices lock in within a median of ~2 minutes after it. That is a
  minutes-scale window, and the geopolitics fee rate is 0 (NOTES). But: tau is the FIRST web report (often a wire
  flash / X post), the fastest humans/bots get the first seconds, and these markets carry the insider-trading and
  resolution-dispute risk described in 5.x. Released data ("dated events, the deadline ladders") can be used to
  measure how much of the move is still available 30 s / 2 min / 10 min after tau with real fills.

### 2.4 Bazyari, Liu, Moran, "Same Pipeline, Opposite Conclusions: Sample-Surface Effects in Breaking-News Latency" — arXiv 2605.21521, 2026-05-18 — ABS
https://arxiv.org/abs/2605.21521 — 109 Polymarket events, "news moment pinned to the largest 1-hour trade-volume
spike"; X vs news tied at -0.02 min (n=16 paired, X earliest in 38%); Bluesky/Facebook/YouTube 24–32% of earliest
channel wins. Implication: there is no single fastest public channel; the Polymarket volume spike itself is about
as early as X.

### 2.5 Ng, Peng, Tao, Zhou, "Price Discovery and Trading in Modern Prediction Markets" — SSRN 5331995, posted 2025-07-01, revised 2026-04-28 — 2nd-hand (SSRN not opened)
https://papers.ssrn.com/abstract=5331995 — search summary: Polymarket leads Kalshi in price discovery around the
2024 election, more so when liquidity is high; net order imbalance of large trades predicts subsequent returns.
Dubach (arXiv 2610.06412) summarises the 2026 revision as: "Polymarket leads around the 2024 presidential
election and in politics and entertainment, while Kalshi leads in sports and when its relative trading activity
is higher". No lag in minutes/seconds found in what I could read.

### 2.6 Aktug & Torul, "Price Discovery Across Political Prediction Markets" (April 2026) — 2nd-hand
https://web.bogazici.edu.tr/torul/pridis.pdf (not opened) — search summary: Polymarket and Betfair jointly ~85% of
information shares in the 2024 election; "no sportsbook contributes a meaningful share".

### 2.7 Georgetown Law Technology Review, "Already Scored: Information Asymmetry in Real-Time Sports Betting", Feb 2026 — read via WebFetch
https://georgetownlawtechreview.org/already-scored-information-asymmetry-in-real-time-sports-betting/GLTR-02-2026/
- Genius Sports official feed: "median round-trip latency of under 37 milliseconds", arrives "3 to 4 seconds ahead
  of video"; TV/streaming "delayed by several seconds to tens of seconds relative to the actual game action".
  DRW, Jump, Susquehanna named as firms in prediction markets. No measurement on Polymarket/Kalshi.
- A search snippet (not verified) says Genius Sports announced data partnerships with Polymarket and Kalshi in
  August 2026.
- Implication: in-play sports is a latency race where the reference is a paid official feed; a TV viewer is
  3–30 s behind. I found NO academic measurement of Polymarket's in-play lag versus a sportsbook or an official
  feed (gap in the literature; worth measuring ourselves with ESPN API vs trade tape, knowing ESPN is also slow).

### 2.8 Moshrefi, "Prices, Probabilities, and Parlays: Systematic Bias in Sports Prediction Markets" — arXiv 2607.14430, 2026-07-15 — FULL (passages)
https://arxiv.org/abs/2607.14430
- Kalshi, ~23M moneyline trades, early March – mid May 2026 (NBA 11 weeks, NHL 10, MLB 7).
- Calibration is perfect mid-life; "In the 0–10 minute bucket ... The empirical outcome rate sits at essentially
  zero across prices below 0.4 — contracts trading at 10–40 cents in the final ten minutes resolve favorably
  almost never — transitions sharply around p≈0.5, and saturates near one across the upper half." (i.e. in the
  last ten minutes the trailing side is overpriced; author reads it as insurance demand.)
- Parlays (29 Apr – 13 May 2026): median price / product of legs = 0.991, 0.995, 0.999 for 2–4 legs; 1.01 at 5
  legs, 1.07 at 8, 1.22 at 10, 1.31 at 11; a parlay priced 0.30 wins ~24%, one priced 0.40 ~30%.
- Red flags: time-to-expiry is measured to settlement, so the "last ten minutes" bucket mixes live end-game with
  stale prints after the result is known; trade prices, not quotes. Kalshi, not Polymarket.

### 2.9 Kim et al., "LLM as a Risk Manager: LLM Semantic Filtering for Lead-Lag Trading in Prediction Markets" — arXiv 2602.07048, 2026-02-04 — ABS
https://arxiv.org/abs/2602.07048 — Kalshi Economics markets; Granger-causal leader/follower pairs re-ranked by an
LLM; win rate 51.4% -> 54.5%, average losing trade $649 -> $347. No fees/fill model in the abstract.

### 2.10 Crosier, "Prediction Markets Beat the Weather Forecast on Tomorrow's High Temperature" — arXiv 2609.23969, 2026-09-21 — FULL (passages)
https://arxiv.org/abs/2609.23969
- Kalshi daily-high markets, seven US cities, five years. "at the end of the market's first hour of trading it
  beats the best single public product [NBM] by about 10 percent in root-mean-square error, and holds its lead"
  (11% at the NBM's final bulletin). "the National Blend travels four times further toward the market between
  its postings than the market travels toward the NBM. The market does not react to new weather forecast updates;
  instead, the forecast slowly publishes information that the market had already shared".
- Implication: on liquid US-city weather markets "public model says X, market has not moved yet" is NOT a gap;
  the market already has it (someone runs better blends / reads raw model runs and observations). An edge would
  have to come from intraday station observations (settlement-station METAR/ASOS running max vs the bucket) or
  from thin non-US cities on Polymarket, which this paper does not cover.

### 2.11 Tsang & Yang, "Political Shocks and Price Discovery ..." — arXiv 2603.03152, 2026-03-03 — ABS
https://arxiv.org/abs/2603.03152 — three 2024 shocks: debate repricing largely reversed, assassination-attempt
repricing persisted, Biden withdrawal: heavy volume, little price change. Trading after shocks is done by
incumbents with larger prior activity. (Overreaction after some news = fade candidate, n=3 only.)

### 2.12 Nechepurenko, Kalshi "decidability" series — arXiv 2609.16642 (2026-09-15), 2610.00173 (2026-09-16), 2610.00165, 2609.15368/15373 (Polymarket resolution vs settlement) — ABS
Directly about the owner's hypothesis ("public evidence can become sufficient to settle a contract before the venue
records its first determination") but the papers are protocols: "zero historically eligible events", "No ...
price ... result is reported here". Nothing usable yet; watch for results.

---------------------------------------------------------------------------------------------------------------

## 3. Systematic biases

### 3.1 Qiu & Qiu, "Time-Varying Favorite-Longshot Bias in Polymarket Weather Markets" — arXiv 2610.13593, 2026-10-09 — FULL
https://arxiv.org/abs/2610.13593 ; code https://github.com/ShouchenQiu/PolyWeatherData (README reachable, HTTP 200; not read)
- Data: daily maximum-temperature events, ten cities, 5 Dec 2025 – 31 Jul 2026: 2,189 events, 21,697 bucket
  contracts, 8,544,732 taker trades. Train Dec–May (1,585 events), validate June (294), test July (310).
- "Longshot overpricing is concentrated at 30–48 hours ... Overpricing between 0.75 and 0.95 is strongest during
  the final 1–12 hours and is nearly one order of magnitude larger ... the event-weighted favorite bias is
  approximately -0.10 at 6 hours, compared with approximately -0.009 for longshots at 48 hours." Heatmap: the
  70–90% bin is -11.2 pp at 6 hours.
- Buy-NO test on July (rule fixed on training data): YES price 0.75–0.95, 1–12 h before the daily peak, $10 per
  trade: 184 trades, $1,840 notional, NO win rate 20.7%, pre-fee +$1,011 (+54.96%), post-fee +$933 (+50.71%) at
  an assumed fee rate f = 0.05; 95% CI [1.76, 102.98] cents per $1. Longshot rule (YES <= 0.10, 30–48 h, buy NO):
  11,924 trades, -0.13% pre-fee, -0.23% post-fee.
- Authors' own caveat: "The tests diagnose the economic direction of mispricing using mean taker prices. The
  Buy-NO calculations exclude order-book depth, bid–ask spreads, and slippage, so the reported returns do not
  establish executable trading profits." B-spline recalibration gives no significant score gain.
- My reading: a bucket trading at 0.85 six hours before the peak wins ~75% of the time. Sample is tiny (184
  trades, one month, CI almost touches zero) and uses mean trade price, but the fee assumed (0.05) is five times
  the current weather rate (0.01), and the horizon is hours — exactly the lab's target zone. Mechanism is
  plausible: by late morning traders anchor on the forecast bucket while the true max is still +-1 bucket
  uncertain (station rounding, late-afternoon spikes).
- Test: `prices-history` (1-min for last 7 days, 5-min for 60 days) + `trades?condition=` for all temperature
  buckets; rule = when a bucket's YES ask implies NO ask <= 0.25 within 1–12 h of local peak, buy NO at the ask
  actually shown by the next taker print; compare with Iowa Mesonet ASOS running max. Aug–Nov 2026 is fully
  out-of-sample relative to the paper.

### 3.2 Cardozo & Rivero-Wildemauwe, "The Favorite-Longshot Bias in Prediction Markets: Evidence from Polymarket" — arXiv 2609.12878, 2026-09-11 — FULL (passages)
https://arxiv.org/abs/2609.12878
- Data: Polymarket Users dataset v1.3 (Akey et al. / Grégoire; HF `vgregoire/polymarket-users`), ~588M trades,
  2.48M wallets, Nov 2022 – Mar 2026. Returns exclude fees and rewards.
- Pooled purchases: below 10 cents lose 19.3 cents per dollar; at or above 90 cents earn 0.83 cents per dollar.
  Equal-weight per contract: longshots -6.3; grouped by parent event: +4.1 (i.e. depends on aggregation).
- By category: Crypto longshots -14.84% (equal weight) / -12.63% (pooled); Politics -16.34% / -46.15%; favorites
  positive in both. Finance pooled: longshots -72.40%, favorites +1.826%. Weather: equal-weight longshots -25.15%,
  favorites +0.502%, but pooled longshots +24.74% (sign flips). "Sports is the clearest counterexample: its
  longshot returns are positive under both methods".
- Longshot losses "appear at every experience level and under all purchase methods, including when buyers post
  their own offers" and in markets without fees. Crypto = 67.2% of purchases but 25.2% of dollars.
- Implication: buying >= 0.90 earns +0.83% gross per dollar on average; taker fee at p = 0.95 is rate*0.05 per
  share = 0.26% of notional at rate 0.05 and 0.05% at rate 0.01. So the favorite side survives fees on paper in
  0.01-fee categories, but the return is per trade, not annualised, and is exposed to rare full losses (and to
  the settlement manipulation in 2.2 for crypto pre-August). Selling longshots (buying NO at 0.90+) in crypto and
  politics is the same trade.

### 3.3 Bürgi, Deng, Whelan, "Makers and Takers: The Economics of the Kalshi Prediction Market" — CEPR DP 20631 / CESifo WP 12122 / UCD WP2025_19 (2025, revised 2026) — 2nd-hand (abstract via search)
https://www.ucd.ie/economics/t4media/WP2025_19.pdf (not opened) — >300,000 Kalshi contracts; clear
favorite-longshot bias; "Makers earn higher returns than Takers, but returns for both exhibit a favorite–longshot
pattern", more pronounced for takers.

### 3.4 Bartlett & O'Hara, "Adverse Selection in Prediction Markets: Evidence from Kalshi" — NBER conference paper, version 2 Jul 2026 — FULL (first pages + key passages)
https://conference.nber.org/conf_papers/f243677.pdf
- 41.6M Kalshi trades. "traders systematically overbet YES in markets that predominantly settle NO, generating a
  behavioral surplus that cross-subsidizes adverse selection."
- Makers on single-name markets: lose 23.13 cents per contract when they lose, earn 16.34 when they win; frequency
  edge +5.31, magnitude deficit -3.40, "net profit of 1.91 cents per contract". Broad-based markets: makers earn
  0.82 cents per contract (+2.01 frequency, -1.19 magnitude). Effective half-spreads average ~3 cents.
- Case: "Will Jeff Bezos attend the Super Bowl" (Feb 2026): informed NO takers, yet makers earned $29,274 (3.3
  cents per contract) because uninformed YES takers bought 518,000 contracts at an average of 19 cents. Another
  market: lifetime maker P&L -$75,754 after an informed burst (71,000 contracts, YES 90c -> below 40c).
  One-sided flow (VPIN) predicts maker losses in single-name markets.
- Implication: the structural payer is the retail YES-longshot buyer in "will X happen / will X say / will X
  attend" markets (on Polymarket: mentions, culture — both at the 0.01 fee). Passive NO-side quoting earns ~1–2
  cents per contract on average but with insider tail risk; pull quotes on one-sided bursts.

### 3.5 Le, "Decomposing Crowd Wisdom: Domain-Specific Calibration Dynamics in Prediction Markets" — arXiv 2602.19520v2, 2026-02-23 (v2 Aug 2026) — ABS
https://arxiv.org/abs/2602.19520 — 353M trades, 429K contracts, Kalshi + Polymarket. "persistent underconfidence
in political markets, where prices compress toward 50%; it replicates on Polymarket." Roughly half of the raw
calibration-slope variation is estimation noise.

### 3.6 Dubach, "The Anatomy of a Decentralized Prediction Market" — arXiv 2604.24366v2, 2026-04-27 — ABS + passages
https://arxiv.org/abs/2604.24366 — 30 billion book events, 52 days, panel of 600 markets (58% crypto, 24% sports).
"Median spread is ~400 bps in the central [0.4,0.6] range and climbs to 1,300–1,800 bps for" the lowest-probability
decile; effective half-spread ~200 bps at central prices; self-counterparty wash share median 1%, max 22%;
"broad maker-wallet diversity with a concentrated tail". Trade direction from the public feed agrees with
on-chain truth only ~59% -> use on-chain taker side (the Data API `trades` feed is taker-side, fine).

### 3.7 Dubach, "Measuring Trade Direction in a Prediction Market ..." — arXiv 2610.06412, 2026-10-05 — passages
https://arxiv.org/abs/2610.06412 — 12 days Apr–Aug 2026, 24.5M matched prints. Equal-fill weights: taker effective
spread 2.328 cents per share. Useful dated fee history (from the venue changelog, matches NOTES): 6 Mar 2026
taker fees + maker rebates extended to all crypto markets; 30 Mar "Fee Structure V2"; 28 Apr exchange V2
migration; 28 May taker rebate programme live; 2 Jul World Cup markets to 0.0025 tick; 10 Jul sports taker rate
0.03 -> 0.05 and sports maker rebate 25% -> 15%; 24 Jul matching latency cut, no tx hashes for FAK/FOK; 7 Aug
up/down resolution change.

### 3.8 Mahrous & Di Pietro, "What Prediction-Market Contracts Reveal at Launch" — arXiv 2610.29578, 2026-10-21 — ABS
https://arxiv.org/abs/2610.29578 — 802,863 resolved markets Jan 2023 – May 2026. Disputes: 0.31% base rate;
launch-time features rank dispute risk with AUC 0.78 but precision 0.012. (Size of the resolution-dispute tail
risk for any "near-certain" strategy: ~3 in 1000 markets.)

### 3.9 Sultan & Morstatter, "The Conversation Turns First" — arXiv 2609.28965, 2026-09-24 — ABS
https://arxiv.org/abs/2609.28965 — 79 non-political markets; comment stance shifts against the leader before
reversals in 23 of 27 markets, but "adds no clear improvement in individual-block forecasting" (ROC-AUC 0.780 ->
0.788). Not tradable as described.

---------------------------------------------------------------------------------------------------------------

## 4. Who profits (bots vs humans, makers vs takers), wash trading

### 4.1 Akey, Grégoire, Harvie, Martineau, "Who Wins and Who Loses in Prediction Markets? Evidence from Polymarket" — CEPR DP 21615 / SSRN, 2026 — abstract read on RePEc; rest 2nd-hand
https://ideas.repec.org/p/cpr/ceprdp/21615.html
- Abstract: "Using 588 million trades ($67 billion in volume), we show that the gains are highly concentrated: the
  top 1% of users with positive PnL capture 76.5% of profits. Successful traders provide liquidity using limit
  orders that resolve favorably relative to realized outcomes while unsuccessful traders take liquidity using
  market orders. Monthly performance is modestly persistent, however this may represent sample selection rather
  than skill. ... 'insider' trading is unlikely to explain the performance of the largest winners."
- Press (Gigazine 2026-05-25, not verified against the paper): 2,469,589 accounts, ~69% lose, total losses
  $650.3M; 1,200 accounts (0.05%) take more than half of the profits; users "weaker in sports betting, but more
  successful in weather and technology". Bloomberg 2026-04-28 headline: "Most Prediction Market Traders Are Losing
  Money While Bots Rack Up Gains" (not opened). Qiu & Qiu cite this paper for "especially large bias in weather
  markets".

### 4.2 Gómez-Cram, Guo, Jensen, Kung, "Prediction Market Accuracy: Crowd Wisdom or Informed Minority?" — SSRN, revised 2026-04-25 — 2nd-hand (Yale Insights article read)
https://insights.som.yale.edu/insights/wisdom-of-the-few-prediction-markets-are-driven-by-small-number-of-skilled-traders
- 1.72M accounts, 210,322 markets, $13.76B. ~3% (3.14% per The Block) are "skilled" (PnL beats 10,000 random
  buy/sell relabelings); 44% of those found skilled in one random half of events are skilled in the other half;
  skilled + market makers < 3.5% of accounts, > 30% of gains; "lucky winners" (~29% of accounts) hold 69% of
  gains. Skilled accounts trade faster around FOMC and earnings. Insider activity moves prices 7–12x more but is
  sporadic.

### 4.3 Jia & Sun, "Beyond Profit Rankings: Identifying, Understanding, and Evaluating Smart Money in Prediction Markets" — arXiv 2610.34754, 2026-10-26 — FULL (passages)
https://arxiv.org/abs/2610.34754
- 1,541,104 wallets in 2026 through 17 Oct: 68.66% negative PnL, top 1% take 89.2% of profit.
- 1,101 candidate "smart" wallets; next-week profitability prediction from past profit: Brier 0.2306–0.2278 vs
  base rate 0.2493, AUC 0.681 (0.577 excluding zero-PnL weeks) -> weak persistence at weekly horizon.
- Behaviour: position additions 55.3% of observations, openings 11.5%, reductions 3.9%, exits 0.4% (they hold to
  resolution); buys spread over all prices (23.63% in 0.40–0.60, 11.55% below 0.10, 11.19% in 0.90–1.00).
- Live copy-trading system, 13–24 Oct 2026, FOK orders, $1 per trade: paper +44.18 pUSD on 283 buys, but one ETH
  trade is +56.07 ("excluding this trade reduces aggregate paper PnL to -11.89"); 20 live buys: -3.04 USDC; 18
  matched paper/live trades both lose ~3.2. "confirm the feasibility of real-time on-chain copy trading but do not
  establish consistent profitability."

### 4.4 Sirolly, Kanoria et al. (Columbia), "Network-Based Detection of Wash-Trading" — SSRN, Nov 2025 — 2nd-hand (press)
https://fortune.com/2025/11/07/polymarket-wash-trading-inflated-prediction-markets-columbia-research/ (not opened;
search summary): ~25% of Polymarket volume over three years looks like wash trading; 14% of 1.26M wallets flagged;
45% of sports volume, 17% election, 12% politics, 3% crypto; peak ~60% of weekly volume. Motive probably airdrop
farming. (Dubach's self-counterparty measure: median 1%, max 22% — different definition.)
- Implication: volume leaderboards and "volume" fields overstate real liquidity, most of all in sports.

### 4.5 Lab's own tape result (NOTES.md) agrees with 4.1/3.3/3.4: BTC 5m takers lose 1.33% of turnover before fees, 2.67% after; makers +0.66 cents per share.

---------------------------------------------------------------------------------------------------------------

## 5. Insider / information leakage (risk for any news strategy)
- Mitts & Ofir, "From Iran to Taylor Swift: Informed Trading in Prediction Markets" (2026) — 2nd-hand; cited by Fan
  et al.: "in the hours before the strike on Iran [28 Feb 2026], six new accounts earned about USD 1.2 million".
- Nechepurenko, arXiv 2605.02286 (2026-05-04), ABS: "US forces enter Iran by April 30" ($269M volume): pre-event
  drift mild, "short-window variants (30-min, 2-hour) are exactly zero"; 332 wallets active in both Iran markets.
- Bartlett & O'Hara (3.4): Bezos Super Bowl case; Kalshi sanctioned traders twice.
- Implication: on unscheduled single-actor events the counterparty in the last hours can be an insider; a maker
  there must cancel on one-sided bursts; a news taker competes with people who knew before the news existed.

## 6. Forecasting models / LLM agents
- Gu, Kagan, Sun, Wu, Xu, "When do prophets profit in prediction markets?" — arXiv 2607.06166v3, 2026-07-07 — ABS.
  "Proper betting" (a sizing rule from forecast p and market q) is the only rule that turns a Brier-score edge into
  profit; "monthlong live pilot test on Kalshi; the encouraging preliminary results" (no number in the abstract).
- Jia et al., "AlphaOpsBench" — arXiv 2609.31390, 2026-09-25 — ABS. 581 strategy records from public sources turned
  into executable programs over 1.28M Polymarket markets / 183.6M executions: "no confirmed pass on the real
  cohort"; "execution costs alter subsequent trading paths rather than acting only as ex-post deductions".
  (Possible source of a ready-made strategy catalogue + dataset; not opened in full.)
- Zhang, "Hard to Fool ..." — arXiv 2611.06607, 2026-11-04 — passages. Pre-registered campaigns incl. Kalshi BTC
  hourly (138 conditional hypotheses), Kalshi BTC 15-minute binaries, Kalshi maker side: "The single formal pass
  among 138 Kalshi hypotheses conditioned on volume in the same window it predicted" (look-ahead, rejected). 46
  days of Kalshi data. An LLM-found survivor with Sharpe ~3 in validation fell to 0.26 on holdout.
- Benchmarks (ABS only): ForecastGym 2611.23045, Forecast-Dojo 2609.28876, Hindcast 2607.14051, PolyBench
  2604.14199, Prediction Arena 2604.07355, "One Fabrication Is Enough" 2611.15102 (a single fake article changes
  LLM forecasts — attack surface for news bots).
- Barot & Borkhatariya, "PolySwarm ... Latency Arbitrage" — arXiv 2604.03888, 2026-04-04 — title only, not read.

## 7. Market making theory (no data)
Feil & Nendel 2607.17991 (optimal quotes under settlement risk); Lejmi 2610.26789 (MARL market making); Dalen
2510.15205; Xi, Moallemi, Pai 2607.08199 (volatility). Not read beyond abstracts.

## 8. Data sources surfaced (HuggingFace, existence checked through the HF API, 2026-11-27)
`vgregoire/polymarket-users` (Akey et al. wallet-level data), `TimeSeventeen/Polymarket-v1` and `-v2` (Qin & Yang,
arXiv 2606.04217: 1.20B trades 2022-11-21..2026-04-28 with true aggressor side), `Houroux/polymarket-l2-history`,
`chitoyuuri/polymarket-l2-v3-1-archive`, `ithiria894/polymarket-l2-orderbook`, `Joseph3222/polymarket-orderbook`
(L2 books — these could replace the WebSocket recording we cannot do here), `trentmkelly/polymarket_historical_data`,
`gregyoung14/openmarket-btc-polymarket`, `polydata5/polymarket-updown-5m-ws`, `SII-WANGZJ/Polymarket_data`.
Contents not inspected.

---------------------------------------------------------------------------------------------------------------

## 9. My own checks (2026-11-27)

1. Fee facts quoted by the papers match NOTES.md (sports 0.03 -> 0.05 on 10 Jul 2026; TWAP settlement 7/14 Aug).
2. HF datasets and the PolyWeatherData repo exist (API / HTTP 200).
3. Weather leaderboard, month, by PnL (`data-api .../v2/leaderboard?category=weather&time_period=month`): top
   month PnL is only $53K, then $31K, $17K, $16K, $15K, $12K, $12K, $8K. Weather is a small pond.
   `wallet_check --monthly` on the top three (numbers are whole-account, all categories, all time):
   - xtxpleasecallme 0xad5353afe30c2da57709e2704ef3ccdcf67eef24 (joined 2025-10-08, 132,553 markets, 1.54M fills,
     volume $17.1M): profile P/L 231,871; taker fees -65,941; rebates+rewards 190,337 (taker 9,620 / maker 20,515 /
     liquidity rewards 160,202); kept 361,894 (unrealized -224,583 on top); 53% of net is rebates/rewards. Net
     without rebates by month Apr..Nov 2026: 17,130 / -9,276 / -12,811 / 2,092 / 8,733 / -2,500 / 115,388 /
     -17,615. => a wide market maker / rewards farmer; apart from October its trading P&L is about zero and the
     income is the rewards program (49K, 79K, 34K in Sep, Oct, Nov).
   - WrongBy1Degree 0x0a0c42f6b1da5a633ec1a4d45ba76eb486c1a853 (joined 2026-05-11, 14,112 markets, 42,742 fills,
     volume $396K): profile P/L 36,165; fees -7,691; rebates 1,598; kept 30,071 = +7.59% of volume; 5% of net is
     rebates. Net by month May..Nov: 1,312 / 225 / -108 / 1,205 / 3,164 / -2,881 / 27,154. => a directional taker
     with a real but lumpy edge (90% of the profit is November); small size — the profile of a solo trader.
     Worth deconstructing (which buckets, how many hours before the peak, NO or YES).
   - 1DVSBSTD 0xeb1d1cd1b31070fb34b1d1de20d700f59c9959b0 (joined 2026-01-08, 80,455 markets, volume $7.57M on
     7.62M shares, i.e. average price ~0.99): profile P/L 3,315; fees -1,110; kept 2,368 = +0.03% of volume;
     negative in Aug, Sep, Nov. => a near-$1 sweeper ("resolution bond") earns 3 basis points on turnover: it
     ranks #3 on the monthly weather board by PnL with $1.07M monthly volume and almost nothing kept all-time.
     Confirms 1.6: buying near-certain outcomes is not a free lunch.

## 10. What I could not open / did not do
- SSRN pages (Akey et al., Ng et al., Gómez-Cram et al., Sirolly et al., Mitts & Ofir): not opened; I relied on
  RePEc abstract, Yale Insights, and search summaries. Bloomberg, Fortune, The Block: not opened.
- Bürgi-Deng-Whelan PDF and Aktug-Torul PDF: URLs found, not downloaded.
- No replication of any paper's numbers on raw data (that is a study with a protocol, not a reading task).
- Not searched: NBER working-paper series proper, Google Scholar, journal sites; non-English literature.

---------------------------------------------------------------------------------------------------------------

## Verification pass (2026-11-27, second reader)

Scripts: `catalog/raw/r1_verify_scripts/` (`grepnum.py`, `ctx.py`, `ctx2.py` search the papers for each claimed
number; `w1.py` splits wallet fills; `fav.py` is the weather check below). Nothing here is a replication of a paper.

### What was checked

1. Existence: all 27 arXiv ids cited in the candidates were fetched from the arXiv API again; every id exists with
   the title, authors and date given above. I downloaded the HTML of 13 papers a second time; the files are
   byte-identical to the local copies.
2. Numbers: every figure quoted in candidates 1-9, 11 and 12 was searched in the paper text and found, with these
   exceptions and nuances:
   - Fan et al. (2.3): the sentence is "this time differs from tau by a median of two minutes". It gives no
     direction. "The price locks in a median two minutes AFTER the first report" is the researcher's reading, not
     the paper's statement. The 0.43 -> 0.78 series, 337 accounts, 62% posted volume, 1.4-3.8% are there.
   - Gebele et al. (1.2): "ten most profitable addresses account for 75[%]" and "approximately 80[%]" maker-built
     conversions are in the text with the percent sign lost, as the researcher said. The same passage says the
     all-taker share is "at or below 40[%]" from late 2024, so 80% is an average, not a constant.
   - Moshrefi (2.8): the parlay overpricing by leg count rests on few contracts: 140 parlays with 8 legs, 67 with
     9, 57 with 10 and 12 with 11, out of 12,639; the median price/product ratio over all parlays is 0.996. The
     broader statement (win rate 2-10 points below price, 0.30 wins about 24%) is in the text.
   - Cardozo (3.2): finance longshots -72.40% is the pooled figure only; the equal-weight figure is -2.62% with an
     interval that includes zero. Sports favorites are -0.230% equal-weight and +0.137% pooled.
   - AlphaOpsBench (section 6): "no confirmed pass on the real cohort" is about whether LLM-written programs pass
     the benchmark's end-to-end validity checks. It is not a finding that the 24 public strategies lose money. The
     candidate text read it as the second.
3. Non-arXiv sources opened directly (all HTTP 200): RePEc abstract of CEPR DP 21615 (76.5%, limit orders,
   "modestly persistent": confirmed), Yale Insights (3%, 44%, 29% lucky winners with 69% of gains, 1.72M accounts:
   confirmed), the NBER PDF of Bartlett & O'Hara (1.91, 0.82, -$75,754, 41.6M trades: confirmed in the local text),
   Georgetown Law Technology Review (37 ms, 3 to 4 seconds, DRW/Jump/Susquehanna: confirmed; the article never
   mentions Polymarket and mentions Kalshi once in passing).
   Two PDFs the researcher had not opened are reachable and were read on the first pages:
   - Buergi, Deng, Whelan (UCD WP25/19, version September 2025): abstract as summarised; over 300,000 contracts.
   - Aktug & Torul (version June 2026, not April): 5-minute data, nine venues, Polymarket and Betfair "nearly 85%"
     of information shares, "no dealer sportsbook exceeds 11%" (not "none"). They describe Ng et al. as a
     30-minute return VAR, so the Polymarket/Kalshi lead in that paper is measured on 30-minute bars.
   SSRN returns 403 here as well, so Ng et al. stays second-hand. The PolyWeatherData README is reachable on
   raw.githubusercontent.com; it calls the paper an "ICDM (student paper)" and lists the ten cities (Atlanta,
   Chicago, London, Miami, Toronto, New York, Seattle, Seoul, Shanghai, Tokyo).
4. Wallets (`wallet_check.py --monthly`, then `pmlab.wallet` and `w1.py` to see what they trade):
   - WrongBy1Degree 0x0a0c...a853: gross 36,176, fees -7,692, rebates 1,598, kept 30,081 (+7.59% of $396K), 5% of
     the net is rebates, Tier 0. Net by month May-Nov: 1,312 / 225 / -108 / 1,205 / 3,164 / -2,881 / 27,154.
     The researcher's figures stand. What it trades (last 30 days, 2,700 fills, $150K): 100% weather, 100% taker,
     buys only (YES $78.7K, NO $69.3K), average price 0.39, 11 fills in the 0.85-0.95 band. 2,500 of the 2,700
     fills are more than 12 hours before 12:00 UTC of the target date. The lab's weather study found 0 of its
     1,252 resolved fills inside the station's local day. It is a day-ahead forecast-update taker. It does not
     trade the late-favorite fade and is not evidence for it.
   - xtxpleasecallme 0xad53...ef24: gross 256,799, fees -65,958 (5,571 refunded), rebates and rewards 190,337, kept
     386,805 (+2.26% of $17.1M), 49% of the net is rebates/rewards (the notes above say 361,894 and 53%). Net
     without rebates Apr-Nov: 22,675 / -9,275 / -12,808 / 2,094 / 8,736 / -2,494 / 115,400 / -12,413 (April and
     November differ from section 9). Its last six hours: 1,471 fills, of which 95 in temperature markets; the
     rest is Dutch second-division football, crypto price thresholds, politics and economics. It is a
     cross-category rewards farmer that happens to top the weather board, not a weather trader.
   - 1DVSBSTD 0xeb1d...59b0: gross 3,303, fees -1,110 (154 refunded), kept 2,356 (+0.03% of $7.57M), no rebates.
     Net by month Mar-Nov: 373 / 1,093 / 577 / 966 / 185 / -113 / -437 / 231 / -373. Last 10 days: 89% of
     turnover is weather, 29% maker, average buy price 0.995-0.999, net -$239 on $322K. Taker buys at 0.99-1.00
     lose 0.17 cents a share; taker buys at 0.95-0.99 earn 1.14 cents a share (t 4.8) but on $4.2K only.
     The story stands. One caution on the figure: 0.03% is per dollar of turnover, and the positions last hours,
     so it is not an annual yield on capital; the account's capital is unknown.

### A check that contradicts candidate 1 (weather late-favorite fade)

The lab already holds prices for 3,198 temperature markets of 13-26 Nov 2026 (48 stations, `studies/wallets/weather/
out/px.json`, 30-minute points). I applied the paper's rule to them: YES price between 0.75 and 0.95 at a fixed
local hour, buy NO at 1 - p, fee 0.01, hold. The rule was written in `fav.py` before the run, but I had already
seen the neighbouring bands in the lab's `out/calib.txt`, so this is not a blind test. One script, ten cells, all
shown:

| local hour | n (events) | mean YES | NO wins | implied | return at 1-p | t | return with 2 c slippage | t |
|---|---|---|---|---|---|---|---|---|
| 07 | 51 | 0.863 | 13.7% | 13.7% | -0.9% | -0.03 | -13.5% | -0.45 |
| 09 | 41 | 0.867 | 9.8% | 13.3% | -27.5% | -0.80 | -37.0% | -1.23 |
| 11 | 61 | 0.845 | 13.1% | 15.5% | -16.5% | -0.58 | -26.0% | -1.02 |
| 13 | 174 | 0.858 | 9.8% | 14.2% | -31.8% | -2.03 | -40.3% | -2.94 |
| 15 | 188 | 0.891 | 10.6% | 10.9% | -3.0% | -0.15 | -18.1% | -1.09 |

The paper's ten cities alone (11-47 events per cell): -100% at 09 h and 11 h (no NO win in 27 events), -24% at
13 h, +4% at 07 h, +70% at 15 h (t 1.2). In November the favorite band won as often as priced or more often; the
paper's July result (NO wins 20.7%) does not show up. Limits: 14 days, another season, the market set is the union
of what seven accounts traded, 30-minute API prices are not quotes, the same events appear in several rows. It is
enough to say the effect is not stable; it is not enough to say the paper is wrong about July.

### What I changed in the candidate list

- Candidate 1 (weather late-favorite fade): credibility 3 -> 2. Out-of-sample lab data has the opposite sign, and
  neither wallet trades the rule. Wallet evidence rewritten. The paper's fee of 0.05 was the real weather rate at
  the time (NOTES: weather was 0.05 until 20 Nov), not a conservative assumption.
- Candidate 4 (news latency): credibility kept at 3, verification PARTIAL because of the "two minutes" reading.
  Added the lab's own timings (headline to 0.95 in about 70 s; economic releases 98% taken within 30 s).
- Candidate 5 (longshot fade): figures confirmed; added the finance and sports nuance and the lab's mentions result
  (blind buying at >= 0.95 is negative after fee there).
- Candidate 7 (crypto latency): the taker delay is 150 ms since 4 Sep 2026 (NOTES), not 50 ms.
- Candidate 10 (cross-venue): Aktug-Torul details corrected; the only lag scale in the cited work is 30-minute bars.
- Candidate 11 (end-of-game sports): added that 272 of 307 sports game markets carry a 1-second taker delay
  (all but NBA), which the candidate did not mention.
- Candidate 12 (parlays): sample sizes added.
- Candidate 13 (model forecasting): AlphaOpsBench claim corrected.
- Nothing dropped: every cited source exists and contains the quoted figures.

### Systematic problems

- Wallets taken from a category leaderboard were used as evidence about that category without looking at what
  they trade. Two of three do not fit the story they were attached to.
- Several "testability" lines propose work the lab has already done (`studies/wallets/weather`,
  `studies/gaps/econ_release_lag`, `studies/wallets/mentions`). Those results bear directly on candidates 1, 4, 5
  and 6 and were not used.
- The summary's finding (4) puts weather favorites next to geopolitical news as one of two places with a
  minutes-to-hours gap. After this pass only the geopolitical one remains, and it has no fill evidence.
