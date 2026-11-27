# r4 — Other venues as arbitrage legs or leading signals for Polymarket

Researcher pass of 2026-11-27 (all live numbers were taken between 15:45 and 16:05 UTC that day).
Code and protocol: `studies/r4_cross_venue/` (`protocol.md` was written before each result was looked at).
Raw data: `data/r4/` (`snapshot_1795794410.json`, `deribit_vs_pm_*.json`, `leadlag_minute.json`,
`poll15m_v2.jsonl`, `poll15m_v1_STALE_KALSHI_QUOTE.jsonl`, `kalshi_open_events.json`, `pages/`).

Short answer
- Two-leg Kalshi x Polymarket arbitrage: on liquid same-day events there is nothing after fees (0 of 10 game
  outcomes). What is left under $1 after both fees is long-dated (2027-2028 lock-up), thin, or sits on a real
  settlement difference. Needs a Kalshi account and capital on both venues. Not for a Polymarket-only trader.
- Kalshi as a leading signal in sports: published work says Kalshi moves first by about 1-7 seconds; on minute bars
  I see no lead in either direction and the venues quote the same cent most of the time. A taker on Polymarket
  cannot use it (0.05 fee rate = 1.25c at 50c, spread 1c, gap median 0c). It is a quoting input for a maker, at best.
- Deribit vs Polymarket crypto thresholds: Polymarket is 1-2c away from the option-implied digital on most strikes
  and systematically rich on cheap upside strikes and on "dip/reach" barriers. The fee there is 0.01 (max 0.25c).
  This is the only family in this file where the gap is hours-to-days wide and the fee is small, so it is the one
  worth a proper test. One snapshot is not evidence of profit.
- BTC 15-minute up/down on both venues are NOT the same contract: different index and different strike. In the one
  window I watched the two venues resolved opposite ways (details in 2.3).

No source in this file names a Polymarket wallet, so `wallet_check` had nothing to run on.

---------------------------------------------------------------------------------------------------------------

## 1. Venue facts and frictions (what I verified, what I could not)

### 1.1 Kalshi public API (checked live)
- Base `https://api.elections.kalshi.com/trade-api/v2`, no auth for market data. Used: `/events?status=open&with_nested_markets=true&limit=200`
  (110 pages, 21,927 open events), `/events/<ticker>?with_nested_markets=true`, `/markets?series_ticker=`,
  `/markets/<ticker>`, `/markets/<ticker>/orderbook?depth=N`, `/series/<ticker>`,
  `/series/<series>/markets/<ticker>/candlesticks?start_ts&end_ts&period_interval=1|60|1440` (works for markets
  settled a day or two ago), `/exchange/status`, `/series/fee_changes` (returned an empty list).
- Prices are strings in dollars (`yes_bid_dollars`), sizes `*_fp`. The order book returns BIDS ONLY for yes and no,
  ascending; best yes ask = 1 - best no bid.
- **Trap found:** `GET /markets/<ticker>` serves a cached quote. On the live 15-minute BTC market it showed
  0.20/0.21 while `/orderbook` showed 0.28/0.29 seconds apart, and `updated_time` did not change over 15 s. Use
  `/orderbook` for any timing work. My first 15-minute poll used `/markets` and is void (file renamed `..._STALE_...`).
- Rate limit: I got HTTP 429 with roughly one request per second from two processes. Back off.
- 24h contracts by category at 15:45 UTC: Sports 45.9M, Crypto 7.2M, Elections 3.5M, Economics 2.5M,
  Entertainment 1.9M, Financials 1.0M, Weather 1.0M, Politics 0.9M. Kalshi is a sports venue first.
- Fee type per series (from `/series/<ticker>`): KXBTCD, KXBTC, KXETHD, KXBTCMAXY, KXBTCMINY = `quadratic`,
  multiplier 1; KXFED, KXCPI, KXNFLGAME, KXNBAGAME = `quadratic_with_maker_fees`, multiplier 1. Settlement source
  for all crypto series: CF Benchmarks (BRTI); NBA: ESPN + league; NFL: league.

### 1.2 Kalshi fees
- WebSearch summary of Kalshi's fee schedule (kalshi.com/docs/kalshi-fee-schedule.pdf; I did not open the PDF):
  taker fee = round up(M x 0.07 x C x P x (1-P)), maker fee = round up(M x 0.0175 x C x P x (1-P)) on series that
  have maker fees; "100 contracts priced at $0.50 ... $1.75 taker fee, compared with just $0.44 in maker fees".
- `https://docs.kalshi.com/getting_started/fee_rounding.md` (opened): trade fee is rounded up to $0.000001 per
  fill, then a "rounding fee" brings the balance to the member's precision ($0.01 for non-direct members) with an
  accumulator per order. Practical meaning: for small orders the effective fee is higher than the formula.
- In all calculations below: Kalshi taker 0.07 x p x (1-p) per contract, rounding ignored (optimistic for arbitrage).

### 1.3 Can a resident of Serbia open the accounts?
- Kalshi help centre, "Can I trade on Kalshi from outside the United States?" (dated March 20, 2026, opened):
  "Yes, you can trade on Kalshi from many countries"; eligibility per the Member Agreement; identity verification at
  signup; international funding by debit card (Visa/Mastercard), wire (minimum $1,000) or crypto; withdrawals by
  debit card or crypto; no ACH/PayPal/Venmo.
- datawallet.com/crypto/kalshi-restricted-countries (page updated 2026-11-16, read through WebFetch): 55 restricted
  jurisdictions in the Member Agreement as of 2026-11-15. Europe: Belarus, Belgium, Bulgaria, France, Hungary,
  Ireland, Italy, Monaco, Poland, Portugal, Russia, Switzerland, Ukraine, United Kingdom. Serbia, Montenegro,
  Bosnia, North Macedonia, Kosovo are NOT in the list. KYC: name, date of birth, residential address, possibly ID +
  selfie. Third-party reading; I did not open the Member Agreement itself. Brazil, Spain and Czechia blocked
  kalshi.com at ISP level in 2026 without being in the agreement.
- Deribit, sportsbooks (Pinnacle etc.): eligibility for Serbia NOT checked.
- "Polymarket US" is a separate CFTC venue with its own API and fees (docs.polymarket.us; per the BotCookery post
  below: API taker coefficient 0.0695 with a 70% rebate through 2026-12-31, app tiers 0.11/0.10/0.09/0.0695 since
  2026-11-25). Most English-language "Kalshi vs Polymarket arbitrage" posts are about that US venue, not the
  international CLOB the lab would trade. I did not check whether a Serbian resident can use it.

### 1.4 Settlement differences that break "same event" (read from both rule texts on 2026-11-27)
| Pair | Polymarket | Kalshi | Break |
|---|---|---|---|
| NFL/NBA game winner | tie resolves 50-50; cancelled / not started by a date two days later -> 50-50 | tie -> $0.50 each; postponed > 48 h -> "fair price" | postponement handling |
| EPL 3-way | win/draw markets (negRisk); cancelled -> "No" | 90 min + stoppage; "Tie" market; cancelled -> fair price | cancellation |
| Fed decision December | change in upper bound, "rounded up to the nearest 25" | "Hike 25bps", "Hike >25bps", cancelled meeting -> "maintains" | odd-size moves, cancelled meeting |
| US recession 2026 | two negative quarters (BEA) OR an NBER announcement | two negative quarters (BEA) only | NBER leg exists only on Polymarket |
| BTC low in 2026 | any Binance BTC/USDT 1-minute candle (Low) since market creation, to 23:59 ET Dec 31 | CF BRTI below level between Feb 5 2026 and Jan 1 2027 00:00 ET, trimmed-mean wording | different index; USDT trades at 0.9987 so Binance prints ~$73 above USD indices |
| BTC 15-minute up/down | Chainlink 60 s TWAP at end >= TWAP at start | BRTI 60 s average at close >= "target" | different index AND different strike ($8.23 apart in the window I watched) |
| 2028 nominee / president | "wins and accepts the nomination"; consensus of party sources | same wording | close to identical; 2-year lock-up |
| Taipei mayor 2026-11-28 | consensus of credible reporting, CEC as fallback | winner; accelerated resolution by media calls | timing of payout |

---------------------------------------------------------------------------------------------------------------

## 2. My measurements

### 2.1 Snapshot: 20 events live on both venues, 85 matched outcomes (2026-11-27 ~15:46 UTC)
Script `studies/r4_cross_venue/snapshot.py`. Top of book from Polymarket `POST /books` and Kalshi `/orderbook`.
A = buy YES on Polymarket + NO on Kalshi; B = buy YES on Kalshi + NO on Polymarket; cost includes Polymarket fee
(market's `feeSchedule.rate`) and Kalshi 0.07 taker. "thr" = what a Polymarket-only taker pays to act on a signal
(half the Polymarket spread + Polymarket taker fee at mid). One pass, no variants.

Events: NFL DEN@PIT 11-27, SEA@SF 11-29, TEN@JAX 11-29; NBA LAL@SAS, MIA@NYK, PHI@IND 11-27; CFB TEX@TXAM 11-27; EPL
NFO-CHE 11-27 (3 outcomes); Super Bowl 2027; NBA champion 2027; NFL MVP; Fed decision December (5 outcomes); US
recession 2026; Democratic nominee 2028; Republican nominee 2028; President 2028; Taipei mayor; TIME Person of the
Year 2026; Game Awards GOTY; BTC low in 2026 (4 strikes). For multi-outcome events only outcomes priced >= 3c.

| Category | outcomes | median abs(mid PM - mid K) | max | n with abs diff > thr | n with net cost < 1 | median spread PM / K |
|---|---|---|---|---|---|---|
| sports, game lines | 10 | 0.000 | 0.010 | 0 | 0 | 0.010 / 0.010 |
| sports futures | 27 | 0.0045 | 0.0165 | 15 | 2 | 0.001 / 0.010 |
| economics | 6 | 0.0033 | 0.016 | 5 | 1 | 0.0015 / 0.010 |
| politics | 22 | 0.0065 | 0.0355 | 15 | 7 | 0.001 / 0.0015 |
| culture | 16 | 0.0085 | 0.020 | 10 | 3 | 0.010 / 0.010 |
| crypto (BTC low in 2026) | 4 | 0.0272 | 0.0325 | 4 | 3 | 0.001 / 0.010 |

Game lines (the liquid, same-day part): 7 of 10 outcomes had the identical bid and ask on both venues; raw cost of
either two-leg combination 1.00-1.01, net 1.021-1.039.

All 16 outcomes with net cost under $1 (size = smaller top-of-book size of the two legs):
| Event | Outcome | Side | raw | net | usable shares | Why it is not free money |
|---|---|---|---|---|---|---|
| BTC low 2026 | dip to 45,000 | A | 0.9730 | 0.9836 | 3,530 | different index (Binance wick vs BRTI); 34 days |
| BTC low 2026 | dip to 40,000 | A | 0.9810 | 0.9880 | 115 | same |
| BTC low 2026 | dip to 55,000 | A | 0.9800 | 0.9994 | 48 | same |
| Rep nominee 2028 | Marco Rubio (PM 0.240/0.241, K 0.200/0.210) | B | 0.9700 | 0.9907 | 35,226 | 0.9% for ~21 months of lock-up |
| Fed decision Dec | 50+ bps increase (PM 0.018/0.020, K 0.030/0.040) | A | 0.9900 | 0.9922 | 5,469 | 0.78% in 12 days, about $42 at top of book; odd-size-move rule differs |
| Rep nominee 2028 | Tucker Carlson | B | 0.9890 | 0.9934 | 11,179 | 2-year lock-up |
| President 2028 | Ron DeSantis | A | 0.9880 | 0.9935 | 966 | same |
| Dem nominee 2028 | Josh Shapiro | B | 0.9880 | 0.9940 | 115,503 | same |
| Dem nominee 2028 | Gavin Newsom | A | 0.9840 | 0.9951 | 11,001 | same |
| NBA champion 2027 | Portland | B | 0.9920 | 0.9959 | 1,821 | 7 months |
| TIME POY 2026 | Netanyahu | A | 0.9910 | 0.9968 | 308 | thin |
| NBA champion 2027 | Minnesota | B | 0.9890 | 0.9973 | 20,827 | 7 months |
| TIME POY 2026 | Dario Amodei | A | 0.9940 | 0.9977 | 10 | thin |
| President 2028 | Marco Rubio | A | 0.9880 | 0.9978 | 310 | 2 years |
| President 2028 | Josh Shapiro | B | 0.9950 | 0.9985 | 526 | 2 years |
| Game Awards | Zelda | A | 0.9960 | 0.9998 | 60 | thin |

Reading: the only short-dated one is the Fed "50+ bps increase" leg (0.78% in 12 days on about $5.4K notional).
Everything else is a carry trade on a 1-2 year lock-up paying under 1%, or a basis bet. Kalshi fee rounding and the
cost of moving money to Kalshi are not included, so the real numbers are worse.

Signal reading for a Polymarket-only trader: the mid differs by more than the Polymarket cost threshold in 49 of 75
non-game outcomes, but a level difference at one instant says nothing about which venue is right. The largest
persistent-looking ones: Rubio nominee (PM +3.6c), Newsom nominee (PM -2.2c), Taipei mayor Chiang (PM +2.5c, the
day before the vote), Fed 50+ hike (PM -1.6c), BTC dips (PM -1.5 to -3.3c).

### 2.2 Minute-bar lead-lag, Kalshi vs Polymarket, 11 settled games (NFL 11-26: PHI@DAL, CHI@DET; NBA 11-25: nine games)
Script `leadlag_minute.py`. Kalshi 1-minute candles (mid of yes bid/ask close) vs Polymarket `prices-history`
60-second buckets for the same team; window from 30 minutes before start while both prices are in 0.03-0.97;
143-238 minutes per game. One pass. (KC@BUF 11-26 and GB@LAR 11-25: I did not find the Polymarket slug.)
- Correlation of one-minute changes, mean over games (se across games): lag 0: +0.977 (0.004); Kalshi one minute
  earlier: +0.082 (0.028); Polymarket one minute earlier: +0.061 (0.027); lags of 2-3 minutes: 0.00 +- 0.03.
- abs(Kalshi mid - Polymarket price) per minute: median 0.000-0.002, 90th percentile 0.007-0.010 in every game.
- Gap-closure regression is too noisy to read (gap is 0 or one tick): next-minute closure by Polymarket 0.47
  (se 0.19), by Kalshi 0.16 (se 0.16).
- Conclusion: at one-minute resolution the two venues are one price. Whatever lead exists is inside the minute.

### 2.3 BTC 15-minute up/down on both venues (window 15:45-16:00 UTC)
Scripts `poll15m_v2.py`, protocol Q3. Run 1 is void (stale Kalshi quote, see 1.1). Run 2: 79 valid REST polls,
2.3 s apart, covering 191 s that ended 30 s before the close; BTC (Coinbase) moved between 60,004 and 60,133,
i.e. across both strikes; Polymarket Up mid ranged 0.15-0.92.
- Strikes: Kalshi target 60,113.12 (BRTI); Polymarket `priceToBeat` 60,104.89 (Chainlink). $8.23 apart.
- Polymarket Up mid minus Kalshi Yes mid: mean +0.026, median +0.020, sd 0.029, range -0.03..+0.13 (Polymarket's
  strike is lower, so its Up should be worth more).
- Two-leg cost under $1: 56 of 79 polls raw, 21 of 79 after both taker fees (Polymarket 0.05, Kalshi 0.07), 12
  below 0.99, best 0.907; runs of 1-5 consecutive polls (2-12 s). I did not split the count by side; with
  Polymarket above Kalshi the cheap pair is Kalshi Yes + Polymarket Down, which LOSES BOTH legs when the final
  price lands between the strikes.
- That is what happened: Kalshi finalized "no" (expiration value 60,110.79 < 60,113.12) while Polymarket's Up token
  went to 0.995 (60,110.79 would be above 60,104.89; Polymarket's `finalPrice` was not yet published when I looked,
  so the Polymarket result is inferred from the 0.995 price). Same 15 minutes, opposite results on the two venues.
- Correlation of 2.3-second mid changes: lag 0: +0.90; Kalshi one poll earlier: +0.32; Polymarket one poll
  earlier: +0.23 (n = 77). No usable lead at REST resolution; a hint, not a result.
- The between-strikes payoff is the whole "edge" of the repo thesis recorded in w2 (CarlosIbCu, BTC 1-hour: buy the
  two sides that both pay if the price lands between the strikes). With different indices even that pair is not
  guaranteed $1.

### 2.4 Deribit option-implied digitals vs Polymarket "Bitcoin/Ethereum above K on <date>" (15:47 UTC)
Script `deribit_vs_pm.py`, protocol Q2. Deribit `get_book_summary_by_currency` marks; total variance interpolated
in time between the two Deribit expiries (08:00 UTC) around the Polymarket expiry (17:00 UTC, Binance 1-minute
close at noon ET); smile interpolated in strike; digital = call-spread finite difference (so skew is in);
forward shifted by the Binance-minus-Deribit-index basis. One pass; one sensitivity check on the basis.
- Basis is real: Binance BTCUSDT minus Deribit btc_usd index = +73 (8 paired samples, range 63-76); Binance minus
  Coinbase BTC-USD = +72; Coinbase USDT-USD = 0.99873. For a one-day ATM digital $88 of forward is about 2.7 points
  of probability, so ATM comparisons are only as good as the basis.
- 99 strikes (BTC Nov 27, 28, 29, 30, Dec 1, Dec 2; ETH Nov 28, 29, 30). Core set (option digital between 5% and
  95%): n = 27, mean(Polymarket mid - option) = -0.013, median abs = 0.018, median Polymarket spread 0.04; 13 of 27
  outside Polymarket bid/ask plus fee, by 0.1-2.6c in all but one case (BTC Nov 30 K=58,000: Polymarket 0.79/0.81
  vs 0.850, 3.9c).
- Pattern, same on every date: at and below spot Polymarket YES is BELOW the option digital (BTC 60,000: 0.51/0.54
  vs 0.543 for Nov 28; 0.48/0.52 vs 0.546 for Nov 29; 0.49/0.52 vs 0.542 for Nov 30; 0.48/0.51 vs 0.538 for
  Dec 1); above spot Polymarket YES is ABOVE it (BTC Nov 28: 62,000 0.07/0.08 vs 0.060; 64,000 0.011/0.015 vs
  0.006; 66,000 0.007/0.010 vs 0.002; ETH 1,800 Nov 29 0.042/0.070 vs 0.025). Cheap upside is overpriced by
  0.5-2c in absolute terms and by 2-5x in relative terms.
- Liquidity: the Nov 27 event had $871K of 24h volume, Nov 28 $151K, Nov 29 $55K, Dec 2 $2.6K; per strike
  $1K-$20K a day except on the expiry day. ETH: $40K for the next day, $6-8K beyond.
- What this is not: a test. Deribit marks are not tradable prices; risk-neutral is not real-world; one snapshot;
  the interpolation between 08:00 expiries is my own model. Fee on these markets is 0.01 (0.25c at 50c).

### 2.5 "BTC dips to X in 2026": Polymarket vs Kalshi vs option-implied one-touch
- Now (15:46 UTC): Polymarket YES mid 0.565 / 0.2905 / 0.1325 / 0.0805 for 55K / 50K / 45K / 40K; Kalshi 0.595 /
  0.305 / 0.165 / 0.105; Deribit one-touch by reflection (2 x P(S_T < K) at 2027-01-01 05:00 UTC, smile included,
  no drift, rough to +-3c): 0.50 / 0.22 / 0.10 / 0.058.
- 30 days of hourly history (`dip_gap.py`, Kalshi 60-minute candle mids vs Polymarket 30-minute buckets, ~700
  hours per strike): Kalshi minus Polymarket mean +0.013 / +0.007 / +0.016 / +0.015; Kalshi above Polymarket in
  79% / 68% / 91% / 93% of hours; above by more than 2c in 40% / 25% / 39% / 31%. Weekly means between -0.007 and
  +0.024. So the sign is persistent, the size averages about the two fees (Kalshi 0.07 x 0.83 x 0.17 = 1.0c plus
  Polymarket 0.1c), and today's 3.3c is in the upper part of the range. (The last hourly bar of that script shows
  a much larger difference; the two series' bucket timestamps are not aligned to better than an hour while BTC
  was moving, so I do not use it.)
- Both prediction venues price the crash barriers above the option-implied touch probability, Polymarket less so
  than Kalshi. Consistent with the FC26 talk below ("Reach and Dip ... persistent overpricing").

Variants run in total: Q1 one pass; Q2 one pass plus one basis re-measurement (no re-run of the table); Q3 two
runs (first void); Q4 one pass; Q5 one pass (re-run once after an API 400 on the date span, rule unchanged); one
one-touch calculation.

---------------------------------------------------------------------------------------------------------------

## 3. Sources

### 3.1 BotCookery, "Our Polymarket-Kalshi arbitrage monitor found one 2c gap. After real fees it lost 1.4c"
https://dev.to/botcookery/our-polymarket-kalshi-arbitrage-monitor-found-one-2c-gap-after-real-fees-it-lost-14c-41b7
(canonical https://botcookery.com/recipes/polymarket-kalshi-arbitrage-alert-monitor/) — 2026-11-05, updated
Nov 18, 23, 27 — author "botcookery", "written with AI assistance" — full text read through the dev.to API.
- Read-only runs on Oct 25, 2026 against Kalshi and **Polymarket US** on three hand-mapped pairs (Magic@Knicks,
  Chiefs@Seahawks, Miami high 83-84F).
- "On these books the real fees were 1.4-1.8c per contract on each leg." Magic@Knicks: cost 0.29 + 0.72 = 1.01,
  "edge -0.0390/contract" after fees at 10 contracts.
- The only gross gap of the afternoon: "Kalshi NO at $0.38 plus Polymarket US YES at $0.60 = $0.98"; with real fees
  for 12 contracts "Total per contract: 0.38 + 0.6008 + 0.40 / 12 = 1.0142. So the edge is -1.4c a contract."
  It lasted 73 s and got worse ("CLOSED ... after 73s").
- "Kalshi's Miami high-temperature market settled 'according to The Weather Company'. Polymarket US's settled on
  the National Weather Service's daily climate report. Same city, same day, same bucket, two different sources."
- NFL: "Both venues paid $0.50 on a tie, but on a postponement Kalshi went to a fair price after 48 hours while
  Polymarket US waited up to two weeks."
- Kalshi quirks: recommended host `external-api.kalshi.com` answered 403, `api.elections.kalshi.com` worked; order
  book is bids only, ascending. Polymarket US fee details as in 1.3.
- Use: honest negative result with mechanics; matches my snapshot. Polymarket US, not the international venue.

### 3.2 ZenHodl, "Polymarket vs Kalshi Price Discovery" (who moves first)
https://zenhodl.net/blog/who-moves-first-polymarket-kalshi-price-discovery — pilot 2026-06-24, "Correction and
update" 2026-10-19 — no named author; the page sells a matched-book data archive — read through WebFetch (summary
by a small model; numbers below are as it reported them, treat wording as paraphrase).
- Pilot (MLB, 26-29 games, June 21-23, ~31 s cadence): Polymarket led 63.6% of follow-events. WITHDRAWN: "We are
  withdrawing this pilot post's directional conclusion."
- Update: 581 matched games over 12 UTC days between 2026-08-29 and 2026-10-16 (CFB 220, MLB 112, NBA 62, NFL 84,
  NHL 103), 194,408 32-second intervals. Kalshi leads in every sport: asymmetry -0.304 (95% CI -0.342..-0.269);
  CFB -0.355, NFL -0.366, MLB -0.267, NBA -0.209, NHL -0.192.
- Mids correlate 0.996. "Over the next 32-second sample, Polymarket closes 32% of an instantaneous cross-venue gap
  and Kalshi closes 4%."
- On 1-second dual-websocket NBA data (18 series, 28.5 hours) "both venues reprice within about 1 second of each
  other". Polymarket sports markets reportedly hold taker orders 1-3 seconds (`secondsDelay`), unverified by them.
- "taker strategies chasing cross-venue lags lose after spread and fees in both directions"; they cite a historical
  directional bot snapshot of -6.7c CLV, -5.7% ROI.
- Use: the best practitioner evidence in the window; the vendor reports against its own product's sales pitch.

### 3.3 Pantera Research Lab, "The Super Bowl of Prediction Markets: Kalshi and Polymarket's Battle for Price vs Liquidity"
https://panteraresearchlab.xyz/research/the-super-bowl-of-prediction-markets-kalshi-and-polymarkets-battle-for-price-vs-liquidity/
— 2026-02-05 (older than the window; kept for the mechanism) — Ally Zach, Danning Sui — read through WebFetch.
- 282 NFL games, 2025-09-04 to 2026-01-18, trades from 30 minutes before kickoff to the end. Polymarket $359M
  notional, 2,718 trades per game; Kalshi $1.3B, 19,024 trades per game.
- "Kalshi leads the initial repricing in roughly 80% of large moves", "median lead time of approximately 7
  seconds"; by swing size: 5-10pp 1,236 events 78.6%; 10-20pp 459 events 86.7%; 20pp+ 126 events 85.7%.
- "Polymarket requires roughly 3-4x more notional volume to generate a comparable price move over a 60-second
  horizon."
- Caveats: trade prints not quotes; Polymarket trade timestamps are block times (2-3 s after the match, see NOTES),
  which alone explains part of a 7 s "lead"; no fees, no gap sizes.

### 3.4 Adamczewski, "Integration Without Leadership: Cross-Venue Price Discovery in UFC Prediction Markets" — SSRN 7194218
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7194218 — 2026, SSRN returned 403; from the search summary only:
281 matched UFC fights over fourteen months; "venue returns co-move within the same bar, while no lead-lag
correlation is distinguishable from zero at any horizon". Not opened.

### 3.5 Ng, Peng, Tao, Zhou, SSRN 5331995 (already in r1 2.5)
Search summary again: "leadership on Kalshi pronounced in sports markets and when the platform exhibits higher
relative volume and large-trade activity". Not opened (SSRN blocked).

### 3.6 karlewaczko/TennisSharpBot, pull request #15 "Report: who moves first - Polymarket, Kalshi or Pinnacle"
https://github.com/karlewaczko/TennisSharpBot/pull/15 — October 2026 — NOT opened (GitHub pages are blocked here).
Search summary: 39 tennis matches; "Polymarket closes 70 % of the gap, while Pinnacle/Betfair moves 19 % towards
it"; "Kalshi only follows"; Pinnacle snapshots about five hours apart. Unverified, small sample.

### 3.7 OddsPapi, "Polymarket Arbitrage: A 0.44% Median Edge on $4,023 of Depth"
https://oddspapi.io/blog/polymarket-arbitrage-local-bookmakers/ — page dated 2026-03-25 but reports a snapshot of
2026-10-01 13:10 UTC (date mismatch unexplained) — no author; sells an odds API — read through WebFetch.
- 28 boards from 75 upcoming fixtures in seven sports; 2,938 raw "under 100%" pairs -> 42 distinct arbs across 16
  fixtures after screens (fresh within 24 h, >= $500 on the Polymarket rung, prices within 10% of the board median).
  "Median 0.44%, best 1.53%"; median Polymarket rung $4,023.
- "The scanner ignores trading fees, deposit costs and the time it takes to move money onto each venue."
- Worked example: Hapoel Tel-Aviv v Real Madrid, Polymarket 2.439 vs FanDuel 1.74, $15.52 on $1,000 before fees;
  the FanDuel price was last changed the night before. Filtered junk: a 29% "arb" against a $1.15 order, an 8%
  one from a stale Duelbits price.
- Other snippet from the same vendor (search summary, page not opened): on 2026-10-13, 88 winner-market fixtures,
  median margin 1.00% on Polymarket vs 4.02% on Pinnacle.
- Use: a median 0.44% gross edge is far below the Polymarket sports taker fee alone (0.05 x p x (1-p) = 1.25c per
  share at 50c, i.e. 2.5% of the money staked). Sportsbook legs also carry account limits; not addressed by the page.

### 3.8 Fabi, Marfe, Ruffo, Schonleber, "Are Decentralized Prediction Markets Efficient? Evidence from Bitcoin Options" (talk abstract, FC 2026 DeFi workshop)
https://fc26.ifca.ai/defi/papers/market-efficiency-prediction-markets.pdf — 3 pages, read in full (older data;
mechanism still applies).
- Deribit hourly IV surfaces (Amberdata), Breeden-Litzenberger densities; "the standard reflection principle for
  Brownian motion for knock-in barrier events (Reach and Dip)". "Our sample spans 255 bets from March 2024 to
  May 2025."
- "Simple directional bets (Above, Range) are highly aligned (mean correlations 0.97 and 0.83), whereas complex
  path-dependent bets (Reach, Dip) show weaker alignment (0.79 and 0.73)".
- "For highly improbable scenarios — such as BTC reaching $200,000 or dipping below $40,000 — CLOB prices
  persistently exceed the near-zero OIPs". "mispricing is most pronounced at contract inception and near
  expiration, and is systematically amplified during weekends and periods of high macroeconomic uncertainty."
  Above/Range mispricing declines monotonically to expiry; Reach/Dip is U-shaped.
- No trading test, no fees.

### 3.9 Portnaya, arXiv 2606.19517 (already in r1 1.7)
Search summary adds nothing new: pooled gap 6.3 pp vs Binance options, 11 pp vs Deribit, on 2023 contracts;
"largest when the option-implied probability is low and when time to expiry is long".

### 3.10 Thin or unopened items (recorded so nobody repeats the search)
- dev.to/xniiinx "Probability arbitrage: how to beat Polymarket using Deribit options" — the dev.to API returned
  nothing for this slug; search snippet: "if the Deribit model shows a 60% probability ... but Polymarket trades
  at 50 cents, you have found a Positive EV trade". No fees, no results. Not opened.
- cryptodaily.co.uk/2026/07/prediction-markets-vs-options-pricing-gaps — not opened.
- Dune blog "pricing the fed kalshi polymarket cme fedwatch" — 404 at the URL the search returned. Search summary:
  "in November 2025, Polymarket and Kalshi priced 'no change at the April 29 Fed meeting' 20c richer than CME
  FedWatch did. By April 28 ... all three sources had converged to within 1c." Unverified.
- Search summary, source page not identified: "A November 11, 2026 test of NBA games reported ... 133 of 1,080
  Kalshi cross-venue checks priced under $1 but none profitable after fees." Unverified.
- Search summary: "on 8 February 2026 Kalshi settled its Cardi B halftime market at 26 cents while Polymarket paid
  $1" (dev.to/polytrage or tech-insider.org; not opened). Unverified.
- Search summary of GitHub rao/pm-kalshi-arbitrage-bot: the author "ran a version that made money, 100% profit
  over some hours" but "it just is not sustainable long-term due to oracle resolution differences". Not opened.
- Public trackers and tools named in search results (none verified by me): oddpool.com (Fed market watch,
  "Actionable" flag after fees), predictmarketcap.com/arbitrage, predictreport.io/arbitrage, marketmaster.live,
  totalis.trade, launchpoly.com, clawarbs.com, oddspush.com, Apify actors (jpmarketdata/prediction-market-arbitrage,
  congism/polymarket-kalshi-arb-finder, bigdavidson/polymarket-sports-odds-divergence,
  datamole/pinnacle-sports-odds-scraper), OddsPapi, pmxt (unified API library, see w2), dev.to/polytrage series.
  Most are vendor pages with affiliate links.
- X: timelines of `Domahhhh` and `zenhodl` since 2026-09-01 returned no post matching kalshi/deribit/arb/
  sportsbook/pinnacle (11 and 5 posts scanned); `oddpool` and `pmxt_dev` returned 404 (wrong handles or case).
  A `site:x.com` web search returned no X posts. X is effectively not covered for this topic.

---------------------------------------------------------------------------------------------------------------

## 4. Which venue moves first, by category (what the evidence supports)

| Category | Evidence | Who is first | Lag scale | Usable from Polymarket only? |
|---|---|---|---|---|
| Sports in play | Pantera (80% of large moves, ~7 s, trade prints); ZenHodl update (Kalshi in all 5 sports at 32 s; ~1 s on 1-second data); UFC paper (no lead); my minute bars (no lead, gap median 0) | Kalshi, slightly | about 1-7 s | No as taker (fee 1.25c + spread 1c vs gap ~0-1c; Polymarket also delays sports takers). As a quote-pulling signal for a maker: plausible, untested |
| Sports pre-game | OddsPapi (median arb 0.44% gross vs books); my snapshot (identical quotes) | none visible | - | No |
| Politics / long-dated | Ng et al. (Polymarket leads in politics); my snapshot (gaps 1-3.5c that persist) | Polymarket per the paper | hours-days | Kalshi is the follower there; no signal value |
| Economics (Fed) | Fan et al. in r1 (51 of 51 decisions priced a day ahead); my snapshot (within 1.6c) | no gap found | - | No |
| Crypto thresholds (daily/weekly "above") | my Deribit comparison (1-2c, tails rich); Portnaya (half-life ~4 h on 2023 data); FC26 talk | options market | hours | Possibly: fee is 0.01; needs the test in section 5 |
| Crypto barriers (dip/reach) | FC26 talk; my three-way comparison | options market; both prediction venues rich | days-weeks | Possibly, as a seller of overpriced tails; crash risk |
| Crypto 15-minute | my poll (strikes differ, opposite results) | not comparable | - | No |

## 5. Data needed to test the lead-lag properly
1. Sports, second scale: both WebSockets on one clock (Kalshi `orderbook_delta`/`trade`, Polymarket market channel)
   for 50+ games. Not recordable in this sandbox (no WebSockets); needs the VPS. Historical substitute: Kalshi trade
   tape with exchange timestamps (HF `TimeSeventeen/Kalshi`) against Polymarket L2 with a receive clock (HF
   `Houroux/polymarket-l2-history`, NFL/EPL/CFB, 2026-07-22 -> 2026-10-11): for every Kalshi move of >= 5pp within
   10 s, measure when the Polymarket best bid/ask moved and what a taker could still get after 1, 3, 10 s, net of
   the 0.05 fee. This tests the Pantera number with quotes instead of block-time prints.
2. Crypto thresholds: no free history of Deribit surfaces. Start recording now: `get_book_summary_by_currency`
   (BTC, ETH) every 1-5 minutes by REST (works here) plus Polymarket `/books` for the "above" and "hit" events and
   the Binance-minus-index basis. After 3-4 weeks: about 20 expiry days x 11 strikes x 2 assets. Rule to
   pre-register: buy YES (or NO) when Polymarket ask + fee is more than X cents inside the option digital, hold to
   resolution; compare with realised outcomes, clustered by expiry day. A cheaper backfill: Deribit DVOL history
   plus an ATM-only model for the 60-day window where Polymarket keeps 5-minute prices.
3. Fed/CPI: Kalshi 1-minute candles and Polymarket 1-minute history around the release minute for the last 7 days
   only (Polymarket keeps 1-minute buckets for a week), so this has to be collected at each release.

---------------------------------------------------------------------------------------------------------------

## Verification pass

Sceptic pass of 2026-11-27, 16:10-16:40 UTC. No candidate names a wallet, so `wallet_check.py` was not run.
Scratch copies of the pages are outside the repo; the two new snapshots are in `data/r4/`
(`snapshot_1795796767.json`, `deribit_vs_pm_1795796693.json`). No new scripts: I re-ran the researcher's
`snapshot.py` and `deribit_vs_pm.py` once each, unchanged, and recounted `poll15m_v2.jsonl` by side (two time cuts).

### Sources opened by me
| Source | Result | What matches, what does not |
|---|---|---|
| BotCookery (dev.to API, full text) | CONFIRMED | Published 2026-11-05, edited 2026-11-27; Polymarket US; 0.38 + 0.6008 + 0.40/12 = 1.0142; "CLOSED ... after 73s"; fees 1.4-1.8c per leg; Weather Company vs NWS; postponement rule. Not said in the notes: the single 0.98 gap was on the Miami temperature pair, 12 contracts deep, which the monitor itself flagged as a stale-rules pair, and the two venues settle it on different sources. So even the one gross gap was not the same event. |
| ZenHodl (page fetched with curl, text read) | CONFIRMED | 581 games, 194,408 intervals, asymmetry -0.304 (CI -0.342..-0.269), per-sport figures, 0.996, 32% vs 4%, pilot withdrawn on 2026-10-19, "within about 1 second ... neither leads in a tradeable way", "taker strategies chasing cross-venue lags lose after spread and fees in both directions", -6.7c CLV / -5.7% ROI. The page carries an affiliate programme (30%). |
| Pantera (page fetched, text read) | CONFIRMED | 282 games, $359M vs $1.3B, 2,718 vs 19,024 trades per game, "roughly 80%", "approximately 7 seconds", the three swing-size rows, "roughly 3-4x more notional". The page's own table says Polymarket trades settle on chain "after delay window" on a ~2 s chain: its timestamps are prints, as the researcher warned. Dated 2026-02-05, outside the three-month window. |
| OddsPapi (page fetched, text read) | PARTIAL | 2,938 -> 42 arbs on 16 fixtures, 0.44% median, 1.53% best, $4,023, "ignores trading fees", the 29% / $1.15 and Duelbits examples: all there. NOT there: "Pinnacle 4.02%" (this page says Pinnacle 3.86% and bet365 7.12% on one fixture, Polymarket 1.0% median). The page is about two-leg arbs against soft books (FanDuel, Duelbits); it does not use a de-vigged Pinnacle line as fair value, which is what the candidate's name says. Extra fact on the page: it lists `polymarket.us` and `polymarket` as two separate books with different prices (2.50/1.639 with zero limit vs 2.439/1.667 with $4,325). |
| FC26 talk abstract (PDF, 3 pages, text extracted) | CONFIRMED | 255 bets Mar 2024 - May 2025, correlations 0.97 / 0.83 / 0.79 / 0.73, $200,000 / $40,000 tails, inception / expiry / weekends, U-shape, reflection principle, Amberdata. BTC only (no ETH). No words "profit", "fee", "transaction cost" or "strategy" anywhere: it is a pricing comparison, not a trading test. |
| arXiv 2601.01706, 2606.19517, 2610.36639 (arXiv API) | CONFIRMED | Gebele & Matthes: "execution-aware price deviations of 2-4%", "capital-intensive or unenforceable". Portnaya: 6.3 pp over 287 hourly observations, AR(1) half-life "roughly four hours", Deribit extension 11 pp, hedged proxy "profitable ... marginal statistical precision"; three 2023 contracts. Fan, Sun, Zhao: "all 51 scheduled central-bank decisions". |
| CarlosIbCu repo (README.md, thesis.md from raw.githubusercontent) | PARTIAL | The thesis says exactly "minimum payout is $1.00 ... middle ... $2.00". It is about the Bitcoin 1-HOUR market, not the 15-minute one, calls the trade "risk-free", and never mentions fees or that the two venues use different price indices. No results. Commit date not checked. |
| Dune "Pricing the Fed" | PARTIAL | dune.com answers 403 to curl here (the researcher got 404). WebSearch finds the post: Filippo Armani, 2026-05-21 (outside the window). Its summary confirms the 20c gap in November 2025 and the 1c convergence, and adds two things the notes lack: the Kalshi-Polymarket spread averaged about 1c, and the gap to FedWatch is an instrument difference (meeting move vs level after the whole path). Not a lag. |
| SSRN 7194218 (Adamczewski, UFC) | NOT FOUND | SSRN is blocked and a title + author web search returned nothing. Treat it as unverified; I removed it from the supporting evidence of the sports candidate. |
| TennisSharpBot PR #15, dev.to xniiinx Deribit post | NOT FOUND | GitHub 403, dev.to API 404. Removed from supporting evidence (the tennis 70% / 19% figures and the "60% vs 50c" snippet are search summaries only). |
| Cardi B settlement split (Feb 2026) | CONFIRMED by search | CBS, Fortune, AP reprints: Kalshi settled at the last traded price, 26c Yes / 74c No, citing ambiguity; Polymarket paid Yes in full per later reports (one early report says a dispute was pending). A real case of one event, two payouts. |
| Kalshi eligibility for Serbia | NOT CONFIRMED | Search finds only the same third-party lists (55 jurisdictions, India added June 2026); none reproduces the Member Agreement and none names Serbia either way. Still an open question. |

### Measurements I repeated or extended
1. BTC 15-minute window 15:45-16:00 UTC, official results now published. Polymarket `eventMetadata`: priceToBeat
   60,104.89, finalPrice 60,108.58 -> Up, market `resolved`. Kalshi KXBTC15M-26NOV271100-00: `result` no,
   expiration value 60,110.79 against 60,113.12. The opposite resolutions are now a fact, not an inference.
2. Same window, counted by side (80 polls up to 30 s before the close; the researcher has 79). Pair A, Polymarket Up
   + Kalshi No, which is the pair the repo thesis says to buy when Polymarket's strike is the lower one: under $1 after
   fees in 0 of 80 polls, cheapest 1.0048. Pair B, Kalshi Yes + Polymarket Down: under $1 in 22 of 80, cheapest
   0.9069. So ALL the sub-$1 polls were the pair that loses both legs between the strikes (the notes said "mostly"),
   and that is the pair that lost both legs. The thesis pair was never an arbitrage; it cost a premium of 0.5c or more
   for the chance of a double payout. (With a 900 s cut the counts are 0 of 85 and 27 of 85; the extra polls sit in the
   last 30 s.)
3. Second Kalshi-Polymarket snapshot at 16:25 UTC, 39 minutes after the first, same 85 outcomes. Under $1 after fees:
   15 (first: 16); 15 are the same outcomes at the same or nearly the same cost (Rubio nominee 0.9907 both times, Fed
   "50+" 0.9922 -> 0.9912, BTC 45K 0.9836 -> 0.9826); "BTC dips to 55K" went from 0.9994 to 1.0197 because Kalshi's
   quote fell 3c. Correlation of the mid difference between the two snapshots on the 78 non-game outcomes: 0.97.
   Game lines: 0 of 10 under $1 again, minimum 1.0212, identical quotes on 6 of 10 (I count 8 of 10 in the first file,
   the notes say 7; a one-row difference I did not chase). Reading: these are level gaps that sit there, i.e. the price
   of capital, lock-up and rule differences. They are not time gaps and nobody is racing to close them.
4. Second Deribit-Polymarket snapshot at 16:25 UTC. Core set n = 24, mean (Polymarket mid - option digital) -0.013,
   median absolute 0.0175, 14 outside bid/ask plus fee, median Polymarket spread 3c: the same numbers as the first
   snapshot. The sign pattern repeats on every date: 60K below the digital by 1.6-3.3c, 58K below by 1.6-4.9c for
   Nov 30 and Dec 1-2, 62K and above over it by 1-2.6c. Largest: BTC Nov 30 58K 0.80/0.83 vs 0.864 and Dec 1 58K
   0.77/0.78 vs 0.814 (3.2-3.3c beyond the ask plus fee; $3.9-7.4K of daily volume). The Binance-minus-index basis the
   script measured was +88.6 this time against +73 at 15:47: it is not a constant, and the two prices are not fetched
   at the same instant.
5. What the pattern is (my reading of the script and the numbers, not a new test). At-the-money the Polymarket mid
   (0.50-0.53) equals a plain lognormal digital at the at-the-money volatility (about 0.507 three days out); the
   option digital of 0.54-0.55 comes from the skew term in the call-spread difference (Deribit marks: 38% at 60K, 45%
   at 58K, 56% at 56K for Nov 30). In the wings Polymarket is fatter on BOTH sides (P(below 58K) on Nov 30: 18.5% on
   Polymarket vs 13.6% from options; P(above 64K): 5.5% vs 2.9%). So the "Deribit fair value" candidate and the
   "sell barriers" candidate are one trade: Polymarket prices more volatility than the options market, and every
   "edge" in both is short volatility, unhedged, paid in binary outcomes. Buying YES at 0.80-0.93 on the in-the-money
   strikes is the same as selling the crash tail. That is a risk premium to be measured on outcomes, not a pricing
   error to be collected.

### What I changed in the candidates
- Two-leg Kalshi x Polymarket arbitrage: credibility 3 -> 2. The evidence is good and it says the trade does not pay
  on liquid markets (fees about 3c a pair at 50c); the only opened primary source is about Polymarket US, another
  venue. Added the second snapshot, the Cardi B confirmation and the BotCookery detail above.
- Kalshi as a leading quote for sports: credibility 3 -> 2. Time gap rewritten: about 1 s or less on quotes
  (ZenHodl), 7 s only on trade prints. The "1-3 s delay, reportedly" flag replaced by the lab's own reading of gamma
  `secondsDelay` (1 on NFL, CFB, NHL, soccer; 0 on NBA). Under the 0.05 sports rate a taker cannot use it; the
  unverified SSRN and GitHub items no longer count as support.
- Deribit digital as fair value: credibility stays 3 (academic sources confirmed, fee 0.01, pattern reproduced), with
  the short-volatility reading and the unstable basis added to red flags. Portnaya's data is three 2023 contracts.
- Barrier outcomes: credibility stays 2. "3-7c claimed mispricing" was the researcher's own rough estimate, not a
  source's claim; at 45K and 40K the gap (3c, 2c) is inside the stated model error of 3c.
- BTC 15-minute / 1-hour strike-gap pair: credibility 2 -> 1. Evidence corrected as in items 1-2.
- Sportsbook fair value: credibility 2 -> 1; the source does not describe the mechanism in the name, the Pinnacle
  4.02% figure is not on the page, the tennis report could not be opened.
- Fed / rates lead: credibility stays 1; source dated and attributed, and its own explanation (instrument difference)
  added.
- Nothing dropped: every candidate has at least one source that exists and says roughly what is claimed.

### Systematic problems
- Four of the seven candidates need a Kalshi (or bookmaker) account and capital on a second venue. The lab's trader
  is Polymarket-only with a couple hundred euros; whether a Serbian resident can open Kalshi rests on one third-party
  page. These are background, not candidates.
- Every measurement is from one Friday afternoon. The second snapshots show the level gaps are stable over 39
  minutes, which is evidence that they are structural, and no evidence about profit.
- The assignment was "leading signals". Nothing here measures a lead at the scale where one could exist (seconds):
  the sandbox has no WebSockets and the minute-bar test cannot see it. The honest state is "published: about 1 s or
  less on quotes; own data: no test".
- Carry arithmetic on the long-dated pairs ignores what both venues pay on positions (Polymarket holding rewards of
  about 4% a year on eligible election markets per NOTES; Kalshi's interest on balances, not checked). The trade is
  then roughly a Treasury bill with rule risk, not "0.9% in 21 months". Conclusion unchanged.
- Missed or not covered: X (nothing found, same as the researcher); Betfair Exchange and bookmaker in-play feeds as
  the leading venue for soccer and tennis; Polymarket US vs international Polymarket as two books of the same brand;
  CME futures themselves (not FedWatch) for the Fed markets; Kalshi's own daily BTC ladders (KXBTCD) as a second
  reference for the Polymarket "above K" strikes, which would give a tradable-price comparison instead of Deribit marks.
