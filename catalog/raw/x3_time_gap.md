# X3 — Time gap: documented cases where Polymarket lagged an outside source (collected 2026-11-27)

Scope: every category where something is known elsewhere before Polymarket reprices, with the lag, who takes it,
what Polymarket did about it, and whether it is open in late November 2026. This file builds on (and does not
repeat in full) `x2_practitioners.md` (X posts), `r1_papers.md` (papers), `w1_reddit_forums.md`, `w3_longform.md`.
New here: four checks of my own (sections 1.2, 2.8, 2.2, 2.1), the per-market delay and liveness settings read
from the API, and several sources not in the other files (Bitquery, Hackernoon, esports.net, Human Invariant,
1kto1m). Everything from the web is untrusted third-party text; numbers I measured myself are marked MINE.

Access notes: WebSearch + WebFetch worked for hackernoon, substack, bitquery, esports.net, dev.to. Reddit/Medium
not reachable (not retried). I did not use X directly in this pass (x2 already covers Sep-Nov X posts; I cite it).
Variants run by me, all reported below, none dropped: W1 (weather kill events), W1-tape, C1 (crypto post-close),
N1 (NBA post-game). Scripts: `studies/gaps/weather_metar_lag/{protocol.md,run.py,tape.py}`,
`tools_scratch/x3_postclose.py`, `tools_scratch/x3_nba_postgame.py`, `tools_scratch/x3_gamma_fields*.py`.
Outputs: `data/x3/`.

## 0. What the evidence says, in short

1. In every category I could measure, the fast part of the gap is already taken by someone with a better feed
   than the public "source of truth": weather buckets die 3-5 minutes BEFORE the official resolution source
   (aviationweather.gov) shows the observation (MINE); NBA winners are at 0.99+ before or within single seconds
   of the final buzzer (MINE); BTC 5m asks for the winner disappear at the close (MINE); CPI is at 90c in 9 s
   (x2); a headline is half priced in 25 s (x2).
2. What remains for a slow participant is the tail of each move (seconds 10-70 after a headline, the 97c -> 99.9c
   "bond" leg) and markets where the truth needs reading/interpretation rather than a feed (court documents,
   live speeches, long rule texts). The seconds 10-70 tail made "30 times less" than the first 5 s (x2 1.2).
3. Polymarket's countermeasures are per-market and public: `secondsDelay` (1 s on most sports, 0 on NBA), a
   150 ms taker delay on crypto, 15-minute dispute windows on sports/weather, TWAP settlement, and from
   mid-December the Nex engine (cancels in <10 ms instead of ~0.7 s p99), which shrinks the stale-order pool that
   funds news sniping.
4. Promotional numbers are unreliable even from "forensics" vendors: Bitquery's top "oracle race" wallet
   (Mep72, "$6.87M won") shows +$20.3K kept on $55K volume in Polymarket's own Data API (MINE).

## 1. Countermeasures

### 1.1 From the official changelog (local copy `data/pm_docs/changelog_predictions.md`)
- 2026-01: taker fees on 15-minute crypto ("peaking at 1.56% at 50%"); 5-minute markets launched with fees.
  Finance Magnates (Jan 2026, via search summary, not opened) describes it as a "dynamic taker-fee model ... to
  neutralise latency-based arbitrage"; Protos (not opened) says Polymarket "quietly eliminated its 500-millisecond
  taker price delay" at that time.
- 2026-03-06 fees on all crypto markets; 2026-03-30 "Fee Structure V2" (all categories except geopolitics).
- 2026-07: sports fee 0.03 -> 0.05, sports maker rebate 25% -> 15%. 2026-07-24 async commit pipeline ("cuts
  matching latency").
- 2026-08-07 crypto up/down resolve on a Chainlink TWAP (30 s); 2026-08-14 60 s TWAP on 5-minute markets.
- 2026-08-17 crypto taker delay 250 ms -> 50 ms; 2026-09-04 14:00 UTC 50 ms -> 150 ms.
- `/v2/resolutions`: "answers are cached for up to 5 seconds while any row is live ... a new proposal, dispute or
  expiry can take up to 5 seconds to appear"; optional `expected_settlement_time` with basis
  `managed_proposal_expiration` / `proposal_expiration` / `liveness` / `dvm_round_estimate`.
- 2026-11-18 hourly/daily crypto up/down on Chainlink TWAP-60s (NOTES); 2026-11-20 new fee table (weather,
  economics, mentions, culture, other politics, non-BTC crypto at 0.01; sports/finance/tech/elections 0.05);
  2026-11-30 Chainlink price subscriptions need a Chainlink API key; mid-December Nex (NOTES).

### 1.2 Per-market settings read from gamma (MINE, 2026-11-27 ~15:45 UTC)
Sample: top 1,000 open events by 24 h volume (`events?closed=false&order=volume24hr`, 17,235 markets carrying a
`secondsDelay` field). Saved to `data/x3/open_events_top1000.json`.

| series / tag | markets | `secondsDelay` | fee rate |
|---|---|---|---|
| NBA games (`nba-2026`) | 5,382 | 0 | 0.05 |
| NFL (`nfl-2026`) | 3,031 | 1 | 0.05 |
| College football (`cfb-2026`) | 2,576 | 1 | 0.05 |
| College basketball (`ncaa-cbb`) | 1,142 | 1 | 0.05 |
| NHL (`nhl-2026`) | 210 | 1 | 0.05 |
| Soccer leagues (EPL, La Liga, Bundesliga, Serie A/B, Ligue 1, MLS, Eredivisie, Turkey, Poland, ...) | 4,285 tagged soccer | 1 | 0.05 (20 at 0.03) |
| Valorant | 110 | 1 (18 without the field) | 0.05 |
| F1 | 52 | 1 | 0.05 |
| Cricket | 7 | 1 | 0.05 |
| Tennis | 172 | 1 on 16, field absent on 156 | 0.05 |
| CS2 | 244 | field absent | 0.05 |
| Golf, UFC | 121, 9 | field absent | 0.05 |
| Weather (daily temperature) | 1,254 | field absent | 0.01 |
| Elon tweet counts | 90 | field absent | 0.01 |
| Mention markets | (2 events seen) | field absent | 0.01 |
| Economy / Fed | 296+86 | field absent | 0.01 (165 "economy"-tagged at 0.05) |
| Crypto level/"hit price" markets | 955 | field absent | 0.01 |

Reading: a 1-second matching delay on taker orders is the default for live sports EXCEPT the NBA (0 on all 5,382
markets). This confirms and widens the third-party observation of 2026-10-27 in NOTES (EPL 1 s, NBA none).
Whether "field absent" means no delay was not tested (the 150 ms crypto delay is not in this field either).
Human Invariant (section 2.2) already wrote in Nov 2025 that everything is FCFS "with the exception of live
sports on Polymarket".

UMA dispute window (`customLiveness`, seconds) and bond (`umaBond`) in the same sample:
- sports: 900 s / $250 on 12,461 markets (3,600 s on 121; 1,800 s on 20); futures-type 0 (= default 2 h) / $500.
- weather: 900 s / $250 on 1,221 of 1,291 (7,200 s / $500 on 14).
- crypto level markets: 600 s / $250 on 530; 0 / $500 on 309. Crypto up/down: no UMA at all (Chainlink, automatic).
- politics: 0 (default) / $500 on 3,528; bonds of $25,000 (256 markets) and $50,000 (128) on the largest.
- mentions, tweet counts: 0 or absent (default 2 h) / $500.
The docs page (`data/pm_docs/concepts_resolution.md`) only says "2-hour challenge period ... bond typically $750";
the per-market values above are what is actually set. A third-party guide and The Block (search summaries, not
opened) say proposals were restricted to whitelisted proposers ("MOOV2"); the docs still say "anyone can propose".
I did not verify which is true today - it decides whether "be the proposer" is even possible.

## 2. Cases by category

### 2.1 Crypto price feeds vs up/down markets (5m / 15m / 1h / daily)
Sources
- Lab's own work (NOTES): the book absorbs a Binance move in roughly 0.5-2 s (REST, rough); BTC 5m takers lose
  1.33% of turnover before fees.
- Young, "OpenMarket", arXiv 2607.26245, 2026-07-28 (r1 2.1): "Polymarket quotes respond to large Binance moves
  after a median 347 ms"; no strategy survived fees. Pre-dates the taker delay changes.
- @saurav_tweets 2026-11-26 (x2 7): "the cheap shares are gone in about 162ms"; Dublin 25 ms from the engine.
- Dai, Jia, Yu (Stanford), arXiv 2606.31675 (r1 2.2): settlement manipulation in the last 10 s; gone after the
  60 s TWAP (Aug 14).
- NEW: Bitquery Research, "Polymarket Arbitrage: Racing the Oracle",
  https://bitquery.io/investigations/polymarket-oracle-race (figures "verified August 24, 2026"; footer says
  written with AI tools; read via WebFetch). Data: Polygon trades and settlements 2025-09-01 .. 2026-08-22,
  551,453 short crypto markets. Mechanism: the market closes at the time in its title, the result comes from the
  off-chain Chainlink feed, "the chain is not told the answer until a separate transaction lands about half a
  minute later", and the order book stays open in between. Delay: median 26 s, nine in ten within 85 s.
  Claims: $23.1M won in the gap, 97% of it in about three weeks (mid-April to second week of May 2026), 30% by
  one wallet; buying the written-off side (<= 3c) in the gap: $2,240,651 spent, $23,083,874 returned; buying the
  near-certain side (>= 99c) in the gap: $898.6M spent, +0.0%. Share of money spent after close by month:
  Sep 3.7%, Oct 1.6%, Nov 2.6%, Dec 4.3%, Jan 10.9%, Feb 18.8%, Mar 18.4%, Apr 36.5%, May 52.4%, Jun 11.8%,
  Jul 10.6%, Aug 9.4%. Penny-bet win rate in the gap: week of 04-19 25.94%, 04-26 67.13% (+$11.7M), 05-03 84.91%
  (+$4.6M), 05-10 3.44%, late May ~0. Example: SOL 5m on 2026-05-03 07:00 ET: $570 traded before close, $517,980
  in the 36 s after, 184 wallets. Named: Mep72 (0xc227...d0c5) 5,465 markets, $93,729 spent, $6,874,804 won;
  95slave (0xd81e...b8737) $1,208,597; 0xd02c...b1d7 $907,168; 0x619e...f583; 0x7fa1...347d; PayoRamon; NotWinr;
  egig. Who pays: in Aug 1-20 the 1,157 wallets buying the near-certain side in the gap netted -$961,239.
- NEW: "1kto1m", "Why My Polymarket Bot Watches Chainlink, Not Binance", dev.to/lkto1m (dated "Jun 27", year
  not shown, read via WebFetch): Binance and Chainlink "can diverge by 0.3% to 0.8% for 10 to 30 seconds during
  high-volatility windows"; hard cutoff for new positions at T-90 s; claims win rate 52% -> 57-58% on 5m; no PnL.
  Links its profile polymarket.com/@1kto1m and a GitHub bot repo (not opened, not run).
My checks (MINE)
- Mep72 = 0xc227bdcfa753509ba71a271121cab504a029d0c5 (matches the article's prefix/suffix): volume $55,465,
  528,070 shares, trade_pnl ~+20.4K, economic PnL +20,285. Net by month: Apr +16,725, May +3,712, zero volume
  since June. With 528K shares bought in total, a $6.87M payout is impossible. Bitquery's dollar figures are
  wrong by a factor of ~300 for its headline wallet (probably a decoding/units error); its timing facts (26 s,
  the monthly post-close shares, the sudden stop on ~May 10) are plausible but I could not re-derive them.
  The profile name "95slave" resolves to a different address (0xd1af...6111, zero activity): not verifiable.
- 1kto1m = 0xa1d57d329227c75b12b09f927fb3d6d6ef8f1343: joined 2026-05-02, $934,693 volume, gross +49,550, fees
  -19,326, rebates 2,484, kept +32,711 (3.5% of volume; 8% of it rebates). Net by month: May +14.0K, Jun +4.8K,
  Jul +6.0K, Aug +7.6K, Sep +0.3K ($9.9K volume), Oct -8 ($228), Nov 0. A real small 5m bot that worked May-Aug
  and stopped right after the TWAP change (Aug 14) and the delay increase (Sep 4).
- C1, post-close trading today: 144 BTC 5m markets of 2026-11-26 00:00-12:00 UTC (whole tape, block time):
  $3,096,499 traded; $13,580 (0.44%) with block time >= end + 3 s, in 258 fills: 241 taker SELLs of the winner
  ($13,456: holders dumping winning shares into resting bids instead of waiting for redemption) and 17 taker
  BUYs of the loser ($124). Zero taker buys of the winner after the close: the asks are gone. Last fill after
  the end: median 16 s, p90 46 s, max 100 s. So the book still stays open for ~16-46 s after the outcome is
  fixed, but the only flow left is impatient winners selling. (Bitquery's post-close share was 52% in May; 0.44%
  now.) I did not compute the price of those sells; whoever bids there needs the Chainlink TWAP outcome in real
  time (API key needed from Nov 30).
Status late 2026: sub-second race at the engine (London), 150 ms taker delay, 0.05 fee on BTC 5m/15m, TWAP
settlement. Closed for a small VPS. Non-BTC and hourly/daily crypto pay 0.01 and settle on the same TWAP; thin
(ETH 5m ~$4K per market) - see `studies/gaps/crypto_lowfee` (another agent).

### 2.2 Live sports: feed latency, broadcast delay, post-game settlement
Sources
- Georgetown Law Technology Review, Feb 2026 (r1 2.7): official feed "3 to 4 seconds ahead of video"; TV "several
  seconds to tens of seconds" late. No Polymarket measurement.
- Bloomberg 2025-12-08, "Crypto.com Gives Pros 3-Second Head Start Over Retail Traders for Sports Bets" (search
  summary only): retail orders on Crypto.com's event contracts face a three-second delay, market makers none; a
  consultant ties it to courtsiding. Mechanism reference for why venues add delays.
- Human Invariant (@HumanInvariant), "The Case For Alternative Ordering Mechanisms in Prediction Markets",
  https://humaninvariant.substack.com/p/the-case-for-alternative-ordering, 2025-11-12 (old; read via WebFetch):
  all four big order books match off-chain FCFS "with the exception of live sports on Polymarket"; FCFS "creates
  a latency war"; "A taker only has to be right once to pick off a market maker", so the most profitable traders
  run taker strategies; spreads widen in "every single live sports event"; proposes batch auctions (10 s for live
  sports, 1 min for news) with cancels first. No Polymarket numbers.
- esports.net (Jacob Hale), 2025-12-30 (old),
  https://www.esports.net/news/polymarket-bot-makes-over-200k-in-3-months-with-lol-dota-2-esports/ : account
  TeemuTeemuTeemu, "approximately $208,521 in pure profit in a single quarter" on live LoL and Dota 2; "ingesting
  official match data and parsing broadcast information faster than the market can react"; triggers are kills,
  objectives, teamfights; exits "almost immediately once the market updates"; prices "often lag behind by a matter
  of seconds". Kotaku (search summary) says $230,000 in five months incl. Counter-Strike.
- Polymarket x GRID partnership, June 2026 (grid.gg, sportsvideo.org; search summary): official esports data
  "with lower latency" and live streams inside Polymarket. PandaScore blog 2026-05-06 sells a "low-latency esports
  data feed" for prediction bots (vendor, not opened). Genius Sports data deal with Polymarket, Aug 2026 (r1,
  unverified snippet).
- dev.to/fatherson "45-second information edge" (w3 6): T+3 s official feed, T+45-60 s stream. Lead-gen, no data.
- x2 5 / w3: swisstony (largest systematic sports account) has had zero volume since September 2026.
My checks (MINE)
- TeemuTeemuTeemu = 0x5388bc8cb72eb19a3bec0e8f3db6a77f7cd54d5a: volume $2,620,902, kept +8.79% of volume, zero
  fees (pre-fee era). Net by month: Sep 2025 +3.4K, Oct +36.2K, Nov +39.4K, Dec +151.4K, then ZERO volume from
  January 2026 to today. The press number is right (~$230K) and the account stopped the month after the article
  (esports got fees in early 2026 and a 1 s delay on Valorant; CS2 shows no delay field).
- Delay table in 1.2: 1 s on NFL/CFB/CBB/NHL/soccer/F1/Valorant, 0 on NBA.
- N1, NBA post-game: 29 completed games of Nov 22-25 (5 days requested; ESPN scoreboard + play-by-play
  `wallclock` of the "End of Game" play; Polymarket moneyline tape; `/v2/resolutions`).
  - On-chain resolution came a median 17 min after the last play (min 16, max 19) = ~2 min to the proposal +
    the 900 s window. Gamma `closedTime` is within a minute of that.
  - In 26 of 29 games the winner had already traded >= 0.99 minutes before the end (median first >= 0.99 fill
    558 s before the last play). In the three games still open at the end (winner's median price in the last two
    minutes 0.63, 0.81, 0.86) the first fill >= 0.99 came 3 s and 7 s after ESPN's end-of-game time stamp
    (block time, itself 2-3 s late) in two of them.
  - Fills on the winner BELOW 0.99 time-stamped >= 3 s after the last play: $45,015 in total across those three
    games, worth $3,198 at $1 (before fees) - i.e. the post-buzzer money exists only in close finishes and is
    taken within single seconds. ESPN's wallclock accuracy is unknown (+-seconds), so this cannot separate
    "courtside" from "TV".
  - After that the winner sits at ~0.999 for 17 minutes: a "bond" of 0.1c per share at best, before a fee of
    0.005c. Nothing there.
Not measured: score event -> book lag during play. HF `Houroux/polymarket-l2-history` has Polymarket's own
score feed and the L2 book on one clock for NFL/EPL/CFB (r2 2.1) - that is the dataset to do it with.
Status late 2026: official low-latency feeds are sold to (and partnered with) the venue and its makers; takers
wait 1 s everywhere except the NBA; sports fee is the highest (0.05). A TV/stream viewer is 5-60 s late.

### 2.3 Elections and vote counts
- Edwin Munyui (Prediction Frontier), Hackernoon, 2026-11-11,
  https://hackernoon.com/kalshi-and-polymarket-traded-$2-billion-on-the-2026-midterms (read via WebFetch; badge
  "AI-assisted"; 284,000 trades from Aug 1): Kalshi's House contract "hit 99% at 8:10pm", NBC called the House at
  10:08pm; Senate 99% at 9pm, NBC call 11:26pm; Democratic sweep "75% at 6pm Eastern to 89% at 7pm and 98% by
  9pm" on both venues; "prices on results night moved on vote counts". Miss: Polymarket had Annie Andrews (SC)
  at 30.5% an hour before polls closed; she won by 4.4 points.
- A second analysis (polymarkets.co.il mirror, search summary only, low quality): Polymarket priced a Democratic
  House at 99% at 8 p.m. ET, "more than five hours before AP called"; all three venues passed 99% for the Senate
  between 9:01 and 9:05 p.m. vs AP's 11:36 p.m. call; in all eight races AP called overnight both venues were at
  99% before the call.
- @primo_data 2026-11-04 (x2 1.3): election calls on Polymarket "an hour" before CNN.
- Fan, Sun, Zhao (r1 2.3): all 51 central-bank decisions priced a day ahead - scheduled, forecastable events
  leave no post-event gap.
Reading: against network/AP calls the market is 1-5 hours AHEAD, so "wait for the call" is the bond leg only
(99c -> $1 over days: elections pay 0.05, other politics 0.01; settlement can take days and disputes happen).
The real race on election night is county-level result feeds vs the book (minutes, model-driven); nobody has
published a tick-level measurement and I did not make one. Next US-scale event is far away; other countries'
elections recur (French election markets were among the top-volume events today).

### 2.4 Scheduled economic releases (CPI, jobs, Fed)
- @PavelPavlyuh 2026-11-05 (x2 2.1; endorsed by Polymarket's data lead): 33 releases in 2026, correct answer at
  48c a second before; first trades +7 s (block time, so ~+4-5 s at the engine); >90c at +9 s; 99c at +27 s;
  "only 217 wallets traded in the first 10 seconds ... 26 of them did it again and again, on 5 or more releases".
  Favourite won 13 of 17 inflation prints, 3 of 9 jobs prints, 7 of 7 Fed decisions.
- Source of truth: bls.gov / federalreserve.gov at 08:30:00 / 14:00:00 ET; professional feeds parse it in
  milliseconds. Fee: economics 0.01 since Nov 20. No taker delay field on these markets (1.2).
- Not reproduced by me (another agent: `studies/gaps/econ_release_lag`, tapes in `data/econ_tapes`).
Reading: 4-9 s is long by market standards and short for a human; the open question is size at stale prices and
whether a bot polling the BLS site from a VPS sees the number inside ~1 s (BLS throttles and has blocked bots on
release minutes before; unverified).

### 2.5 News headlines, court rulings, official announcements
- Huang/Nvidia events, 2026-11-12 and 2026-11-23 (@rb_tweets, x2 1.1-1.2; reproduced on the tape in w1 8):
  first serious buy +3-5 s, midpoint ~25 s, 95c ~70 s; five wallets took $216K of $239K in the first 72 s; sister
  deadlines lagged the front contract by further seconds; 162 wallets with stale orders lost ~$238K;
  "the same trade, 30 seconds later, made 30 times less". Wallet checks there: nimble-mellow-comet +194.9K (all
  November), 0x3cc3...fb0b +126K, WarriorPooh +347K (half of it these two events).
- Fan, Sun, Zhao, arXiv 2610.36639 (r1 2.3): 208 dated unscheduled geopolitical events; 78% already priced >= 0.5
  one minute before the first web report; price reaches its final level a median two minutes after the first
  report. Geopolitics fee is 0.
- Bazyari, Liu, Moran, arXiv 2605.21521 (r1 2.4): no single fastest public channel; X is first in 38% of events.
- Court rulings: Benzinga (search summary, not opened, undated in the summary): after a federal court struck down
  the "Liberation Day" tariffs, "one new entrant" made a 2,280% return. No timing, no wallet. I found no
  documented seconds/minutes measurement for a court decision; the mechanism is the same as headlines, with one
  difference: rulings are PDFs posted on a court site at known hours (SCOTUS opinion days 10:00 ET), so the gap
  is "read and interpret the PDF", which favours prepared humans/LLM pipelines over raw speed.
- Tesla Roadster stream, 2026-10-15 (@dunik_7, x2 1.3): dromedaryy bought 192,680 Yes at 10c at 21:04 ET; 74c by
  21:11, 97c by 21:30 - a live-stream event priced over 7-26 minutes.
- Countermeasure coming: Nex (mid-December) cuts cancel latency from ~0.7 s p99 to <10 ms, so resting orders can
  be pulled on a headline; the stale-order pool that paid $238K on Nov 23 should shrink.

### 2.6 Mention markets (settled by a live speech)
- Rules (MINE, gamma, e.g. `what-will-jensen-huang-say-during-his-gtc-washington-dc-keynote`, 12 markets,
  $20.9K 24h volume): "The resolution source will be audio/video of the event"; fee 0.01; bond $500; liveness
  default (2 h); no `secondsDelay`. NYT-headline mention series (`nyt-headlines`): resolves on the printed front
  page - the truth is the next day's front-page image, public the evening before.
- Search found only generic guides (defirate, bonus.com, covers.com 2026-08-14 on regulators reviewing mention
  markets after a "teleprompter" incident; a Dec 2025 incident of someone shouting market words at a rally). No
  latency measurement anywhere.
- Mechanism of the gap: official streams (YouTube/X/C-SPAN) run 5-40 s behind the room; low-latency stream modes
  and being in the room are faster; speech-to-text adds 1-3 s. Who wins is unknown - tapes of resolved mention
  markets are in `data/mentions_tapes` (another agent's study).

### 2.7 Tweet-count markets
- Rules (MINE, gamma `elon-musk-of-tweets-november-20-november-27-2026`, 30 buckets, $468K 24 h volume, fee
  0.01, bond $500): counts "main feed posts, quote posts and reposts" between noon ET timestamps; "Deleted posts
  will count as long as they remain available long enough to be captured by the tracker (~5 minutes)"; resolution
  source is "the 'Post Counter' figure ... at https://xtracker.polymarket.com ... If the tracker does not update
  correctly ... X itself may be used as a secondary resolution source".
- xtracker.polymarket.com answers HTTP 200 from here (11 KB shell page; I did not find its data endpoint).
- crypto.news 2026-05-11 (w3 7): "letting bots and AI agents scrape Musk's feed and trade near real time".
- The gap, as designed: the tracker captures on a cycle of minutes; anyone counting posts on X directly knows the
  count first, and the decisive information is the count near bucket boundaries in the final hours. No published
  measurement of tracker lag or of who trades the last hours. Not measured by me.

### 2.8 Weather: station readings vs the book (the category I measured in depth)
Rules (MINE, gamma, `highest-temperature-in-seoul-on-november-28-2026`): the event's `resolutionSource` is a
literal API URL, e.g. `https://aviationweather.gov/api/data/metar?ids=RKSI&format=raw&date=2026-11-28T18:00:00Z&hours=30`.
"The qualifying value is the highest temperature reported in the hourly temperature remark of any routine (METAR)
observation ... in tenths of a degree Celsius as reported. A report whose line begins with SPECI ... does not
count." T-group (`T01390133` = 13.9 C) if present, else the whole-degree body group; rounded half-up to whole
degrees; observation counts by station-local date; "will resolve at the issuance of the first METAR observation
for the station on the day following". Fee 0.01, bond $250, dispute window 900 s. (Earlier in 2026 the source was
Wunderground, then weather.gov pages - x2 8.)
How the truth source behaves (MINE, 2026-11-27): aviationweather JSON carries `obsTime` and `receiptTime`.
Receipt minus observation stamp: RKSI 4 m 26 s - 4 m 36 s; ZBAA 5 m 12 s - 5 m 27 s; EGLC 5 m 11 s - 5 m 27 s;
KLGA (14:51Z report) 3 m 13 s. Non-US stations report every 30 minutes (:00/:30), EGLC at :20/:50, US stations
hourly at ~:51. NOAA's other public channel, `tgftp.nws.noaa.gov/data/observations/metar/stations/<ID>.TXT`,
is no faster: its Last-Modified was within 1-7 s of the aviationweather receipt for RKSI, ZBAA, EGLC and 28 s
earlier for KLGA.
Study W1 (protocol written first: `studies/gaps/weather_metar_lag/protocol.md`)
- 293 closed "highest temperature" events for Nov 21-26 were found; the first 150 (cap in the protocol) were
  processed: 35 dropped (buckets not in whole degrees C, i.e. Fahrenheit cities), 3 dropped (no aviationweather
  source), 112 used. In all 112 my computed daily maximum landed in the resolved winning bucket (0 mismatches),
  so the parsing and the "day = [date-27 h, date-3 h)" window rule hold. US (Fahrenheit) cities are NOT covered.
- Kill event = a routine report that raises the running daily maximum into a higher bucket; the bucket holding
  the previous maximum is now impossible. 70 kill events (in 59 city-days) where that dead bucket was still
  priced >= 5c just before the observation stamp (median 14.5c).
- Dead bucket's price (60 s price history; a point is close to the midpoint; +-60 s bucket uncertainty):

  | offset | relative to the observation stamp | relative to the aviationweather receipt |
  |---|---|---|
  | -5 min | median 0.195, 100% >= 2c | median 0.068, 66% >= 2c |
  | -1 min | median 0.145, 100% >= 2c | median 0.002, 27% >= 2c |
  | 0 | median 0.148, 93% >= 2c | median 0.002, 21% >= 2c |
  | +1 min | median 0.020, 50% >= 2c | median 0.001, 0% >= 2c |
  | +2 min | median 0.005, 27% >= 2c | 0% |
  | +5 min | median 0.001, 1% >= 2c | 0% |

  Receipt lag over the 70 events: median 355 s (min 43 s, max 7,510 s).
- Tape of the dead bucket (W1-tape): first taker SELL of the dead bucket at >= 2c came a median 25 s after the
  observation stamp (quartiles -26 s / 25 s / 68 s; block time is 2-3 s late) in 53 events, and in 53 of 53 it
  was BEFORE the official source had the report. After the receipt there was not a single fill at >= 2c.
  Money: taker sells of dead buckets between the stamp and the receipt = $1,331 in total over 70 events and six
  days (61 wallets), plus $267 of taker buys of dead buckets (someone's resting asks got lifted by the unaware).
  In the ten minutes BEFORE the stamp these same markets traded $32K of taker sells and $39K of taker buys - the
  price is already drifting on continuous temperature data before the report exists.
- End of day: at the receipt of the day's last routine report the winner was already >= 0.99 in 96% of 112
  city-days (median price 1.000); the remaining 4% reached it within the hour. No resolution-stage gap.
- Who takes it: 0x6011655c4afb76f36dd1b08a137a1ba73466b31e sold dead buckets in 14 of the 70 events ($394);
  0xf76253274dbd0dfbbdae21a51c4e60f67114e14f in 4 ($251); then a long tail of $25-90.
  Wallet checks: 0x6011...b31e joined 2026-03-03, 5,118 markets, $2.58M volume, gross +106,145, fees -5,317,
  kept +101,206 (3.9% of volume, 0% from rebates, tier 0). Net by month: May +4.5K, Jun +21.9K, Jul +27.0K,
  Aug +20.7K, Sep +14.5K, Oct +9.1K, Nov +3.6K (on $96K volume) - a real, systematic weather account whose income
  has fallen every month since July. 0xf762...e14f: kept +4,345 all-time on $256K; Oct +3.2K, Nov +2.5K after
  seven losing months.
Reading: the official source is the SLOWEST copy of the observation. The market reprices within ~1-2 minutes of
the observation's time stamp, i.e. 3-4 minutes before aviationweather.gov or tgftp show it. The fast traders
must be reading (a) national met-service or airport feeds that publish the METAR at issue time, and/or
(b) continuous sensor data (US ASOS 1-minute/5-minute, national AWOS pages) that predicts the report. A bot
polling the resolution source arrives after 100% of the move. And the prize is small: about $19 per kill event
at stale prices, ~$220/day across ~19 city-days/day in this sample. Sources promising otherwise are promotion:
youmind.com "Polymarket Weather Trading Bot Build with Claude ($6k/Month Blueprint)" (search summary; a paid
course claiming "Weather Underground pulls from official METAR observations, which updates every 5 minutes");
dev.to/fatherson "$88K weather bot" (lead-gen; a follow-up says it loses in many cities). Crosier (r1 2.10):
on liquid US-city markets the market already leads the public forecast blends.
Open sub-questions (not done): which channel is first per station (e.g. KMA's AMOS for RKSI, UK Met Office for
EGLC, ogimet, FAA/ASOS 1-minute for US stations); whether the last-observation-of-the-day boundary cases
(x.5 rounding, T-group vs body, SPECI exclusion, station-local midnight) are mispriced - x2 8 has two such cases
(Helsinki late-evening rise 0.1c -> 100c; Cape Town mislabelled SPECI).

### 2.9 On-chain events and the match/settlement gap
- Off-chain match vs on-chain settlement ("ghost fills"): arXiv 2606.16852 (June 2026) and defirate (search
  summaries only, not opened): a fill shown by the API is provisional until the on-chain transaction succeeds;
  attackers made their own orders fail on-chain after a bot had hedged; a figure of $1.49M is attached to the
  reported attacks; CLOB V2 (2026-04-28) changed contracts, the authors say the gap persists in some form.
  This is an attack on other bots, not a strategy for us; it IS a risk for any hedged strategy we run.
- Resolution-event feed: Bravado (vendor, x2 9.4, 2026-10-08): UMA proposals "a median 1.4 seconds before they
  land on-chain". Official `/v2/resolutions` is cached up to 5 s.
- Markets on on-chain facts (airdrops, treasury purchases, token launches): I found no documented latency case.
  The Strategy-bitcoin-sale market (Decrypt/The Block, July 2026: two traders sued over a "No" resolution) is a
  rules dispute, not a speed case.

### 2.10 Resolution stage (outcome public, market not settled)
- Docs: proposal + 2 h challenge (default), disputes 4-6 days. Actual settings in 1.2: 15 min on sports and
  weather, 10 min on crypto level markets, default elsewhere.
- NBA (MINE, 2.2): settled 16-19 min after the final play; winner already at 0.999.
- Weather (MINE, 2.8): winner >= 0.99 at the last observation of the day in 96% of city-days.
- Crypto up/down (MINE, 2.1): ~16-46 s of open book after the outcome is fixed; only winner-dumping left.
- Huang events (x2 1.2): four wallets put $132K into 97-99c "for a few hundred dollars each"; one bought $133K at
  ~97c and sold at 99.9c minutes later for ~$4.5K - the bond leg pays when the news is seconds old and the
  wording risk is nil, and it needs size.
- Gebele & Matthes, arXiv 2605.31431 (r1 1.6): the last cents are a price for capital lock-up and settlement risk.
- Dispute risk is rising: "more than 1,150 disputed markets in the first five months of 2026" (search summary of
  a mexc/Bloomberg-derived piece); Oxford Business Law Blog, Nov 2026, "The Illusion of Justice: Dispute
  Resolution on Polymarket" (not opened) cites ~2,000 disputed contracts in a year.
- The lab's resolution-window study R1/R2 is in `catalog/raw/r3_structure.md` (protocol; results pending when I
  read it).

## 3. Wallet checks run in this pass (`tools/wallet_check.py --monthly`, 2026-11-27)

| account | role in the source | volume | gross | fees | rebates | kept | trend |
|---|---|---|---|---|---|---|---|
| 0x6011655c...b31e | top seller of dead weather buckets in my W1 tape | $2.58M | +106,145 | -5,317 | 373 | +101,206 (3.9%) | Jun 21.9K, Jul 27.0K, Aug 20.7K, Sep 14.5K, Oct 9.1K, Nov 3.6K: falling |
| 0xf7625327...e14f | second in W1 tape | $256K | +4,875 | -1,000 (455 refunded) | 16 | +4,345 | negative Mar-Aug, Oct +3.2K, Nov +2.5K |
| TeemuTeemuTeemu 0x5388bc8c...4d5a | esports in-play bot (esports.net) | $2.62M | ~+230K | 0 | 0 | +8.79% of volume | Oct-Dec 2025 only; zero volume since Jan 2026 |
| Mep72 0xc227bdcf...d0c5 | Bitquery's "$6.87M" oracle-race wallet | $55K | ~+20.4K | small (mostly refunded) | 58 | +20,285 | Apr +16.7K, May +3.7K, nothing since; contradicts the article by ~300x |
| 95slave | Bitquery | - | - | - | - | - | name resolves to 0xd1af...6111 (no activity), not the article's 0xd81e...b8737: unverified |
| 1kto1m 0xa1d57d32...1343 | "watch Chainlink not Binance" 5m bot | $935K | +49,550 | -19,326 | 2,484 | +32,711 (3.5%) | May 14.0K, Jun 4.8K, Jul 6.0K, Aug 7.6K, Sep 0.3K, Oct ~0, Nov 0: stopped |
(News snipers WarriorPooh, nimble-mellow-comet, 0x3cc3...fb0b, dromedaryy: see x2 1.)

## 4. Summary table

| category | source of truth | typical lag Polymarket vs truth | who wins it today | what a solo trader with a small VPS could still do |
|---|---|---|---|---|
| Crypto 5m/15m up/down | Chainlink 60 s TWAP (Binance-led spot) | 0.16-0.35 s to reprice; 150 ms taker delay; ~16-46 s open book after close | co-located firms with Diamond/Obsidian rebates | nothing on speed; at most a passive bid for winners dumped after the close (tiny, needs the TWAP feed/key) |
| Crypto 1h/daily, non-BTC | same TWAP, fee 0.01 | not measured here | unknown; thin books | measure (`studies/gaps/crypto_lowfee`); the low fee is the only thing in its favour |
| Live sports in play | official league feed (Genius/Sportradar/GRID) | feed 3-4 s ahead of video; takers wait 1 s (0 on NBA); fee 0.05 | makers with paid feeds; formerly feed-driven takers (TeemuTeemuTeemu, stopped Jan 2026) | nothing on TV/stream timing; possibly NBA (no delay) with a paid fast feed - not at this budget |
| Sports post-game | final score | winner >= 0.99 before or within ~3-7 s of the buzzer; settles 16-19 min later | whoever is fastest in close finishes ($45K below 0.99 over 3 of 29 games) | no; the 17-minute "bond" at 0.999 pays nothing |
| Elections / vote counts | county result feeds; AP/network calls are late | market 1-5 h AHEAD of calls | modellers reading raw counts | only the slow bond leg; rare events |
| Economic releases | BLS / Fed site at the scheduled second | first trades ~4-7 s, >90c at 9 s, 99c at 27 s | ~26 repeat wallets | testable: fee 0.01, known timestamps, 12+ events/month; needs a sub-second fetch of the release and resting stale size to hit - unproven |
| Headlines / announcements / rulings | wire or X post; court PDF | first big buy 3-5 s, midpoint ~25 s, 95c ~70 s; sister deadlines seconds later; live-stream events 7-26 min | 3-5 news-bot wallets per event; victims are resting "bond" bids | the 10-70 s tail and sister contracts, with a prepared headline-to-market map; shrinks when Nex arrives; document-reading events (rulings, long streams) are the human-speed niche |
| Mention markets | live audio/video of the event | not measured; stream delay 5-40 s vs the room | unknown | measurable from tapes vs transcript timestamps; fee 0.01; small markets ($20K/day) |
| Tweet counts | xtracker.polymarket.com counter (captures in ~5 min); X itself | not measured | unknown | count on X directly and trade bucket boundaries near the deadline; fee 0.01; $468K/day event - worth a measurement |
| Weather daily temperature | aviationweather.gov METAR API (receipt 3-5 min after the observation stamp) | market reprices 3-4 min BEFORE the official source shows the report | 0x6011...b31e and a few others with faster station data; income falling monthly | polling the official source is useless; a faster per-station feed could win ~$20 per event; the unexplored part is rule edge cases (rounding, SPECI, local-midnight) |
| On-chain / settlement mechanics | Polygon | 2-3 s match-to-chain; resolutions API cached 5 s | attackers ("ghost fills"), vendors with mempool feeds | nothing to pursue; treat as a risk |
| Resolution stage (UMA) | the rules + public outcome | 15 min (sports, weather), 10 min (crypto levels), 2 h default, days if disputed | large "bonders" at 97-99.9c right after news | small size at 97-99c only when the outcome is unambiguous; return is cents and the tail risk is a dispute |

## 5. Not done / could not verify
- No in-play score-to-book measurement (dataset identified: Houroux). No election-night tick study. No mention or
  tweet-count lag measurement. Econ-release numbers are second-hand.
- Whether UMA proposals are whitelist-only today. Whether "secondsDelay absent" means zero.
- Bitquery's totals; the "95slave", PayoRamon, NotWinr, egig wallets (not checked); arXiv 2606.16852, Protos,
  Finance Magnates, Benzinga, Oxford blog, Kotaku, PandaScore, GRID pages (search summaries only, not opened).
- prices-history point semantics (mid vs last) and its +-60 s bucket alignment limit the weather table's
  precision; the tape result (53 of 53 first sells before the official receipt) does not depend on it.
- ESPN `wallclock` accuracy is unknown, so the NBA post-buzzer seconds are approximate.

## Verification pass (2026-11-27, second reader; scripts `tools_scratch/x3v_*.py`)

What was checked: all 11 candidates. Sources opened by me: both @rb_tweets articles, @dunik_7, @PavelPavlyuh,
both @primo_data posts, @atteonthephone (tools/xread.py); Bitquery, dev.to/lkto1m, esports.net, Hackernoon, Human
Invariant, defirate, covers.com, crypto.news, dev.to/fatherson, docs resolution page (curl); arXiv metadata for
2610.36639, 2605.21521, 2609.23969, 2605.31431, 2606.16852 (all five exist with the stated authors); gamma rules of
the Seoul temperature, Elon post-count and Huang keynote events. Not opened: Georgetown Law Technology Review
(HTTP 429). Wallets run through `wallet_check.py --monthly`: 23 (the 17 named in the candidates plus 6 further
addresses printed in the Bitquery page). Own checks, 3 variants, all reported: V1 Mep72 fills Apr 19 - May 10;
V2 the Bitquery showcase market; V3 price of post-close winner sells on 40 fresh BTC 5m markets.

Confirmed as written
- Every wallet figure in section 3 reproduces to the dollar (0x6011…b31e, 0xf762…e14f, Mep72, 1kto1m,
  TeemuTeemuTeemu). WarriorPooh, nimble-mellow-comet, dromedaryy and 0x3cc3…fb0b (now named Samael-of-Rome) match
  the x2 table.
- Both Huang articles say what the notes say (91 wallets / $239K / 72 s, five took $216K; three traders $71K in
  33 s; "30 seconds later, made 30 times less"; four bonders $132K "for a few hundred dollars each"; $133K at 97c
  sold at 99.9c for ~$4.5K). The CPI post has all the quoted numbers. esports.net, Hackernoon, Human Invariant and
  the 1kto1m post contain the quoted sentences. The docs page says "Anyone can propose", "$750", "2-hour".
- Temperature rules, fee 0.01, liveness 900 s, bond $250, no `secondsDelay`: confirmed on the Seoul event. Receipt
  lag re-measured on 14 reports today: RKSI 266-285 s, EGLC 306-327 s, KLGA 186-193 s.
- Post-close BTC 5m, independent sample (40 markets, Nov 26 12:00-15:20 UTC, the half-day NOT used in C1): 0.58%
  of dollars after end+3 s; zero taker buys of the winner; 50 taker sells of the winner.

Corrected
1. Bitquery is wrong on more than Mep72. (a) Its showcase market ("Solana Up or Down - May 3, 7:00AM-7:05AM ET",
   article: $570 before the close, $517,980 in the 36 s after, 184 wallets): gamma `volumeNum` is $1,415 and the
   public tape has $724 before the end and $2.36 after it (2 fills); Mep72 has no fill in it. (b) All addresses
   printed in the page, kept all-time per the Data API: Mep72 +20,285; 0xd81e…8737 (the article's "95slave",
   "+$1,208,597") -921 on $26K volume; 0xd02c…b1d7 ("+$907,168") +8,011; 0x619e…f583 ("+$744,814") -514;
   0x7fa1…347d ("+$730,194") +1,547; egig 0x69c7…b03c ("$0.5M") +38,811; 0x31a4…e927 -965; 0xe267…c61c +2,626.
   The six the article names with a figure (Mep72, 95slave, 0xd02c, 0x619e, 0x7fa1, egig) kept +$67K together
   against ~$11.0M claimed; the other two addresses are printed without a figure I could match. (c) Mep72, Apr 19 - May 10: 8,230 fills, $16,227 of buys for
   429,329 shares, of which 347,678 shares at <= 3c: the most those weeks could have paid is $348K, the account's
   real result for April+May is +$20.4K. The mechanism itself is real (Mep72 buys Up at 2c 6-16 s after the 11:05
   close on hype and btc markets), the scale was 2-3 orders of magnitude smaller than published.
   Spend and market counts in the article are close to the API's, so the wallets are the right ones and the "won"
   column is what is broken. Three of its wallets "opened 2026-04-28", the CLOB V2 date; a decoding error for the
   new contract is a guess, not checked.
2. "95slave: name mismatch, unverified" -> resolved. The profile names 95slave, PayoRamon and NotWinr resolve via
   gamma search to wallets created 2026-04-28 with zero fills, while the article's own address for 95slave has
   4,548 fills. A profile name can resolve to an empty shell: use the address when a source prints one.
3. egig did not stop on May 10: May +10.4K on $12K volume, June +28.1K on $13K, July +6.8K, August -7.7K, then
   nothing. Penny bets after the close paid one small account into July; "dead since ~May 10" holds for the
   aggregate only by the source's own (unreliable) series.
4. Candidate "passive bid for winners": price now measured. 50 sells, 6,284 shares, VWAP 0.9966; 27 fills at
   0.99-0.995, 23 at >= 0.995, none below 0.99. Total discount $21.29 in 3.3 hours of BTC 5m, i.e. about $150 a day
   for ALL bidders together, not the ~$270/day at 0.99 assumed in the candidate.
5. Tesla Roadster (2.5, 2.6, summary table): the @dunik_7 post does not describe a 7-26 minute lag. The wallet bought
   at 10c while the price was collapsing at the start of the stream, BEFORE the stunt; the price rose when the
   stunt happened. It is a contrarian bet, not a case of the book lagging a public fact. Removed from both
   candidates. The post carries a referral link (`?via=999`).
6. Huang Nov 23, omitted context from the same article: 78 wallets under two weeks old bought $17.8K of Yes in the
   48 h BEFORE the news and made ~$270K, "more than all 91 wallets that bought in the 72 seconds after"; the top
   winner (0x7795…9a17, $275.5K) had been buying for nine days. The reaction trade was the smaller pool. The only
   named trader in the slow tail (tinman2, +35 s at 50c, +$10.7K) is otherwise flat: all-time +14,868 with -14,254
   unrealized, Jul-Oct -14.4K, Nov +12.6K. Both articles are by a tool vendor with referral links (gravia.trade
   `?via=`) and a Telegram funnel.
7. Bonders named in the Nov 14 article, all-time kept: tsekinming01 -140,489 on $58.4M (Jul -35.5K, Nov -59.6K);
   JJo +335,755 = 0.80% of $41.9M (Nov +34.3K); tinman2 +14,868; sbimbg +269,373 of which 48% is rebates and
   rewards (without them Jun -31.2K, Aug -126.3K, Oct -82.2K, Nov +16.4K). One of four makes money from the
   trading itself.
8. Things already measured elsewhere in the lab and reported here as "not measured":
   - Economic releases: `studies/gaps/econ_release_lag/results.md` (51 releases, 87 days): winner >= 0.95 a median
     5 s after the release; $30.3K of gap taken in total (~$350/day for everyone), 81% in the first 7 s, 98% in
     30 s; a taker arriving at +30 s gets $570 on $3.3K in the reporting part (t = 1.84), nothing in any US release;
     pre-set verdict INCONCLUSIVE.
   - Tweet counts: the tracker HAS a public API (NOTES, culture study); counter lag median 161 s, p10 35 s,
     p90 296 s over 1,294 posts. The "$106K in a month" trader (sb911) is at -31.2K all-time.
   - Mentions: 131 clean live jumps, first print after the word already >= 0.90 in 57%; all takers together locked
     in $5,485 below 0.95 in 8 weeks; buying the first print >= 0.95 is negative after fee.
   - Weather: the weather wallet study found the same thing on 268 kill reports ($3,037, all before the receipt) and
     names 0x6011…b31e as HighTempTation. Two independent measurements agree.
9. Weather details. (a) "Before Nov 20 the fee ... sank high-frequency weather takers" is not supported: at 15c the
   old 0.05 rate cost 0.64c a share against a 15c move, and 0x6011…b31e paid fees of 5% of its gross. (b) The
   protocol's own variant (tradable AFTER the official receipt) is a null; the $1,331 figure comes from the window
   stamp -> receipt, added after seeing that. `protocol.md` and `run.py` carry the same modification time, so
   "protocol first" cannot be shown from the files. (c) 0x6011…b31e took $394 in these 70 events while keeping
   +3.6K in November: dead-bucket selling in Celsius cities is a small part of what it does, its PnL is not clean
   evidence for this one mechanism. (d) NOTES: a faster feed's running maximum is not the settlement value (KLGA:
   different bucket on 45 of 87 days), so "get a faster channel" also means reproducing the routine report exactly.
10. Kalshi shown as Polymarket: the Hackernoon "99% at 8:10pm" House figure is Kalshi's contract; Crosier
    (arXiv 2609.23969) studies Kalshi, seven US cities, against forecasts; the covers.com item is about Kalshi's
    mention markets and an insider (teleprompter operator), not latency.
11. "$1.49M" for ghost fills is in neither the arXiv abstract nor the defirate article (the abstract gives
    2,037,304 reverted matchOrders() transactions). Figure removed.
12. dev.to/fatherson is posted by the account ABROWNFOX001, the same name as the repo NOTES warns about (closed
    .exe asking for wallet credentials). Removed as evidence. The 1kto1m post is about using Chainlink instead of
    Binance BEFORE the close (it stops trading at T-90 s); it does not document post-close buying.
13. Source age: esports.net (Dec 2025), Human Invariant (Nov 2025), 1kto1m (Jun 2026) and Bitquery (Aug 24) fall
    outside or on the edge of the three-month window.

Credibility changes: headline sniping 4 -> 3 (vendor source, two events of one story, pre-news buyers earned more,
slow tail unproven); oracle race 2 -> 1 (source figures refuted on its own showcase market and on every named
wallet; dead); passive bid 2 -> 1 (~$150/day for the whole market); sports/esports feed 3 -> 2 (one wallet, pre-fee,
stopped 11 months ago, two thirds of its profit in one month; today's 0.05 fee plus the 1 s delay); bond 3 -> 2
(three of four named bonders lose or live on rebates). Weather stays 4 as a measured gap (capacity tiny, see 9).
Economic releases stay 3. Nothing dropped: every cited source exists.

Missed by this file (already in NOTES or one search away): tennis walkover notices vs the book (Stavenson, lag not
measured); box-office markets settling on Monday finals after Sunday estimates; non-US economic releases, where
the only +30 s residue sits (Germany GDP, Korea GDP, Argentina CPI); pre-news informed flow as the larger pool in
the Huang case; resting 1-15c bids next to the pace bucket in post-count events (hixlz).
