# Politics: how the accounts at the top of the board really make money (2026-11-27)

Window: mostly 14 days (13-27 Nov 2026), 30 days for Car, whole account life for the cash reconstructions.
All numbers are from public APIs. Nothing here was traded. Scripts and raw outputs are in this folder; fills and
whole-market tapes are cached under `data/politics_wallets/` (git-ignored).

## Short version

1. **The politics leaderboard is badly polluted by neg-risk conversions.** Six of the "systematic, many small fills,
   positive" accounts on it are NO-basket converters, and the API profit for them is an accounting artefact. Rebuilt
   from cash (buys, sells, conversions, merges, redeems, rewards, rebates) over the whole life of each account:

   | account | API economic PnL | real: net cash + open positions | of which rewards + rebates | trading alone |
   |---|---|---|---|---|
   | Bigggggggg (1st on the month board, "2.13M") | 534,300 | **112,500** (since 2026-05-16) | 47,200 | +65,300 |
   | kaxel78 | 81,381 | 5,500 (since 2026-10-12) | 9,500 | -4,000 |
   | glpgb | 89,821 | -1,100 (since 2026-09-10) | 11,800 | -12,900 |
   | VerilyWinningly | 36,707 | -950 (since 2026-09-11) | 9,000 | -10,000 |
   | BetaShrimp | 8,936 | 1,700 (since 2026-10-17, 6,800 of it is open positions at mark) | 850 | +850 |

   Only the largest one (Bigggggggg) makes money on the trade itself; the smaller copies lose 0.3-2% of what they buy
   and live on liquidity rewards.
2. **Real, persistent money in this category is made by three kinds of account**: an informed two-sided trader of
   fee-free geopolitics and "by date" news markets (Car: positive 27 of the last 30 months), a pure taker bot that
   buys and resells within about an hour across thousands of markets (Cb94C437: positive 6 of 6 months, gross +1.32%
   of $25.6M), and reward-farming makers who lose on every fill and are paid more than that by the rewards program
   (0x9495d622, SPLPB, hfv; over the 14 days they kept 43%, 9% and 12% of the rewards they collected).
3. **Nobody in the sample is a systematic "buy at 0.95+ and wait" account in politics.** On the cached tapes the
   blanket version of that rule shows no edge (T1 below: -0.48 c/share after fee, t -0.2, 24 resolved markets, buyers
   at 0.95+ were on the losing side in 6 of them).
4. Time gaps that the data did show: (a) sibling legs of one event reprice with a lag (median 12 s, p90 133 s over 52
   follower legs in 12 events); (b) after a disqualifying event the "dead" leg of a geopolitics ladder still traded
   at 0.917 one second later and at 0.989-0.99 for two more hours with zero fee (one event, Car's fills). Both are
   small samples and are listed as things to test, not as findings.

## Selection (step 1)

`python3 tools/leaders.py politics --top 60` -> `leaders.txt` (136 accounts). Then `pmlab.wallet --days 14` and
`wallet_check.py --monthly` on 18 candidates (`candidates.txt` + 033033033), `summ.py` for a one-screen comparison.

Studied in depth (7): **Car, Cb94C437, Bigggggggg, 0x9495d622, Lolakis, kaxel78, BetaShrimp**.
Checked by cash only: glpgb, VerilyWinningly, SPLPB, 0x9b129ad0. Screened and dropped: see below.

Skipped, with the reason:

- Directional whales, few markets and huge fills (November was the US midterms): 0xA2cd4Ccd (27 markets, $8.6K a
  fill, +1.22M in November alone), plimzo814 (19 markets), 8m1 (1 market), tnmh (2 markets, 2,179 fills per market),
  dubdubdub2 (7 markets, $21.7K a fill), 0xc4d1a863, lastminwin, Railcool, Contestable-Parfait, dromedaryy,
  SlavaUkraini, UnderperformingForALivin, NoCryInCasino, midterms, soared, TeamA, hedgie1, 0x62D56a93.
- Big but not systematic in the window: aenews2 (43 markets, $2,000 a fill, -106.9K in the 14 days, one Alaska Senate
  market is 43% of its turnover), JJo (70 markets, -59.0K, mostly a tech loss), arjennnnn (56% of turnover is sports).
- Crypto / sports bots that only appear on the politics board: xtxpleasecallme (28,302 markets in the truncated
  window, 5,861 conversions and 27,576 merges, so its API profit needs a cash rebuild that was not done; the wallet
  tool took over 10 minutes on it), cigarettes, balthazar, wokerjoesleeper (rebate share 49-287%, hundreds of
  thousands of markets).
- 033033033 (0xd1c7...): the one true "near-certain" account seen (84% maker, $9,453 a fill, never sells, 29 of 29
  resolved markets won, +0.10% of turnover, 10-34K kept every month on $9-22M of volume) but only 1 of its 44 markets
  in the window was politics (finance closes and sports). It needs millions for 0.1%; not for us.
- anothercoin, 0x66E7ce01, 0xc023bee9: already covered by the culture study (conversion artefacts, Elon counts).
- The four-wallet cluster 0x9b129aD0 / 0x005ED998 / 0x16c73371 / 0xeB68675C (64,069 / 64,075 / 64,070 / 63,961
  markets, $9 a fill): 56% of its turnover is weather; also a converter (1,942 conversions in 30 days). In the
  30-day window conversions of NO bought earlier dominate (Taipei: bought $3.4K, converted $32.9K), so a 30-day cash
  figure (+27.4K) cannot be read as profit. Not resolved.

## Tool totals against the "API says" line (step 2)

| account | tool net (14 d) | API kept (14 d) | why they differ |
|---|---|---|---|
| Car | 6,536 | 8,006 | agree within rewards (1,439) + rebates (628) |
| Cb94C437 | 8,126 | 12,246 | tool fee estimate 2,229 vs 11,150 charged (old rates before Nov 21), rebates 3,341, 705 open markets |
| Lolakis | -3,033 | 19,626 | rewards 8,539 + rebates 1,566; 107 of 173 markets unresolved, 43 with carried-in inventory |
| 0x9495d622 | -2,300 | 9,236 | rewards 21,240; 1,015 markets with carried-in inventory or conversions |
| Bigggggggg | 1,285 | 123,714 | 852 conversions: 1,038 of 1,329 markets are "incomplete" for the tool, and the API books conversions wrongly |
| kaxel78 | 23 | 18,361 | same (520 conversions) |
| BetaShrimp | 242 | 6,341 | same (93 conversions) |

For the last three the wallet tables are close to useless (they leave out every converted market), so `cash.py`
(all activity rows of the account, signed) and `evstats.py` (the same per event) replace them. One TRADE row was
checked by hand: 25 shares at 0.42 has `usdc_size` 10.8045 = 10.50 + fee 0.3045 (rate 0.05), so the activity cash
already contains the taker fee.

## The accounts

### 1. Bigggggggg (0x511f...acbe1) - NO baskets on huge multi-outcome events, converted, tail sold

- 14 days: 9,668 fills, 100% in neg-risk markets, only two kinds of fill: BUY No ($883K; 75% taker) and SELL Yes
  ($96K; 74% maker). 124 events with conversions; conversions returned $780K. 64% of the NO dollars are bought at
  0.90 or higher, 23% at 0.99 or higher.
- Cycle (`Bigggggggg.negrisk.txt`): buy the same number of NO shares (8-9K) on the 10-15 leading outcomes of an event
  with 22-128 outcomes, convert the m NO legs into (m - 1) USDC plus one YES share of every other outcome, then sell
  those tail YES shares as a maker. Six largest events of the window, "sum of average NO prices" against the
  conversion payout m - 1:

  | event (outcomes) | legs m | basket vs payout | tail YES sold |
  |---|---|---|---|
  | next French presidential election (128) | 12 | +4.7 c per set | $3,504 |
  | next CEO of Nvidia (107) | 15 | +5.1 c | $779 |
  | PGL Major Singapore winner (38) | 13 | +15.9 c | $566 |
  | NBA 2027 champion (36) | 10 | -10.3 c | $1,209 |
  | next leader out of power (22) | 14 | -4.3 c | $2,103 |
  | Fed decision in December (5) | 5 | +2.0 c | $0 |

  The baskets are VWAPs over days, not simultaneous quotes, and are before fees (about 0.1 c per leg at 0.98 with the
  0.05 rate).
- Falsification: if the explanation is right the trade must be positive at the event level over the whole life.
  `evstats.py`: 1,400 conversion events, $17.44M bought, net cash +$71,206 = **+0.41% of buys, t 4.3 by event**, 64%
  of events positive. Its 192 non-conversion events lose 5.1% (-$11.0K, t -1.2). The explanation survives; the
  board figure (534K) does not.
- It is a structural edge, not a time gap: the YES prices of an event with dozens of longshots add up to more than 1,
  and the conversion lets the buyer of the leaders' NO own the whole tail for free or better. Outcome risk is small
  (the worst case of a set is the basket shortfall), capital comes back in the conversion transaction.
- To copy: books of every leg of every large neg-risk event, a conversion call (neg-risk adapter), resting sells on
  100+ tail legs. Its sets are about $100K each; turnover $90K a day; trading result about $330 a day plus $240 a
  day of rewards and rebates. Fee: taker rate of the category on the NO legs (0.05 for elections, 0.01 other
  politics; small at 0.95+).
- Risks: the small copies lose. kaxel78 518 conversion events -0.31% of buys (t -3.0), glpgb 766 events -0.84%
  (t -9.6), VerilyWinningly 223 events -2.07% (t -7.4), BetaShrimp 57 events -0.28% (t -0.5). The niche is crowded
  (at least 9 accounts on this board do it) and November is negative for Bigggggggg on the API (not rebuilt by month).
- Confidence in the mechanism 4; that we could earn on it with a few hundred dollars 1-2.

### 2. Car (0x7c3d...5c6b) - informed two-sided trader of geopolitics and "by date" news markets

- All time: kept $1.69M on $119M (+1.42% of volume), rebates and rewards 6% of that, Tier 0, positive in 27 of the
  last 30 months (negative: Jul 2025, Aug 2025, Aug 2026). Sep / Oct / Nov 2026: +32.3K / +35.8K / +45.2K.
- 30 days, politics only: 2,687 fills, $511K, 106 markets in 54 events; 49% of dollars as taker; median fill $17,
  p90 $450, p99 $2,369. Top events: US announces end of Iranian blockade ($135K), US x Iran effective ceasefire
  ladder ($110K), Israel x Iran ceasefire continues ($43K), Hegseth out ($28K), FAA nationwide ground stop lifted
  ladder ($24K). The Iran markets have fee type None on gamma (zero fee).
- It both exits and holds: 36% of what it bought was round-tripped inside the window (+1.42 c a share; exits as a
  maker earn +3.7 c, exits as a taker lose 1.0-3.5 c); median holding of round trips about 2 days.
- Mark-outs on 40 markets (`Car.markout.txt`, cents a share, clustered by market): taker buys pay 1.9 c above the
  last print and are +1.34 c after 1 minute (t 4.3), +1.76 c after 10 minutes (t 3.2); maker buys are filled 1.4 c
  below the last print and are still +1.0 c after 10 minutes (t 3.2), +1.5 c after a day (t 5.2). Its resting orders
  are not adversely selected, which is the opposite of the reward farmers below.
- Sampled stories (`Car.stories.txt`, 12 markets; jump time = first print of a move of 8 c or more within 120 s):

  | market | jump (UTC) | Car's first fill | what it did | outcome |
  |---|---|---|---|---|
  | US x Iran effective ceasefire by Nov 15 | 11-17 19:19:46, YES 0.31 -> 0.03 | +1 s | took 24,320 NO at 0.917, 2,033 more as maker at 0.931, 202 at 0.989 later; held | NO, resolved 21:31 (2 h 12 min later) |
  | same, by Nov 8 | 11-17 19:19:41, 0.31 -> 0.02 | +5 s | took 3,929 NO at 0.910, 4,522 at 0.990 later; held | NO |
  | same, by Nov 22 | 11-08 17:20:15, 0.48 -> 0.57 | 0 s (first print) | took 11,388 YES at 0.516, sold part at 0.52-0.59 | open |
  | Hegseth out by Dec 31 | 11-04 18:22:36, 0.62 -> 0.42 | 0 s | took 3,665 NO at 0.455 and sold 3,676 NO at 0.590 as maker within 5 min | open |
  | Hegseth out by Oct 31 (ends Dec 1) | 11-04 18:22:21, 0.60 -> 0.34 | +3 s | maker bought 1,847 YES at 0.270, sold at 0.39-0.42 | open |
  | Trump meets Putin by Nov 30 | 10-29 17:17:11, 0.84 -> 0.47 | 0 s | sold 3,052 YES at 0.602 | **YES: a loss of about $1.2K** |
  | FAA ground stop lifted by Nov 14 12pm | 11-14 01:14:32, 0.85 -> 0.98 | +41 s | took 2,662 YES at 0.858; held | YES |
  | FAA ... by Nov 13 10pm | 11-14 01:14:56, 0.14 -> 0.93 | +20 s | resting sells hit: sold 1,702 YES at 0.89; rebought 555 at 0.96 | YES |
  | Trump calls for Huang's return | 11-23 02:54:58, 0.24 -> 0.72 | +31 s | took 1,096 YES at 0.929, maker 1,044 at 0.784, later both sides | YES |
  | Andersson next PM of Sweden | 11-15 18:49:13, 0.34 -> 0.78 | +226 s | took 2,055 YES at 0.691, sold 666 at 0.695 | open |
  | next press secretary by Nov 30 | 11-06 23:34:36, 0.56 -> 0.47 | 0 s | took 815 NO at 0.438, sold at 0.56 as maker | open |
  | Trump meets Kim in 2026 | 11-16 14:28:26, 0.09 -> 0.17 | 0 s | had bought 4,503 YES at 0.071 in the 30 min before; resting NO bid filled at 0.816 | open |

  Rules read from gamma for each (text in the file). The deciding source is an official announcement or "a consensus
  of credible reporting"; the public timestamp of each headline was NOT obtained, so "lag" is measured from the
  first print of the move, not from the news.
- Falsification: "Car is a first-second news bot." `Car.jumps.txt`: 394 jumps on 41 of its markets in 30 days; it has
  a fill within 10 s in 14, within 60 s in 20, within 300 s in 33; net with the jump in 17, run over as a maker in
  17. The 5-minute value of everything it did in those windows is $4,165, a small part of a month that kept $45K.
  The claim fails as the main mechanism: it is sometimes first (lag 0-5 s in 9 of the 12 stories) but most of its
  result comes from being on the right side with resting and taking orders outside jumps.
- Time gap: partly (seconds after a headline in fee-free markets); mostly an information/model edge of a specialist.
- To copy: a news feed faster than the crowd for US/Iran/Russia items and cabinet news, reaction within 1-5 s, deep
  knowledge of the rule text, $10-30K per event. Fee 0 on geopolitics, 0.01 on other politics.
- Capacity: its taker entries are 2-25K shares in markets with $0.1-3.3M of volume. Confidence in the description 4;
  in our ability to copy the informed part 1.

### 3. Cb94C437 (0x122c...8efbed) - pure taker, buys and resells within about an hour, 2,500 markets in 14 days

- Joined 2026-06-22. All time: gross +$338.0K (+1.32% of $25.56M), taker fees -$148.6K, taker rebates +$30.7K,
  maker rebate $21, kept **$220.1K**; kept in Jun-Nov: 30.2K / 91.1K / 19.5K / 29.2K / 19.2K / 30.9K. No
  conversions, splits or merges, so the API can be trusted here.
- 14 days: 35,346 fills, every one a taker fill and every transaction a single fill; $1.51M; buys $761K and sells
  $751K; median fill $7, p90 $89, p99 $722; 2,493 markets (1,544 of them weather, 350 politics with 47% of the
  dollars); active around the clock. 92% of what it buys is sold again inside the window at +0.97 c a share before
  fees (politics: +0.87 c); holding time weighted by dollars: p10 1.2 min, median 54 min, p90 15.7 h. It rarely
  holds to settlement (454 redeems).
- Mark-outs, politics, 40 markets: its buys are at the last print (pre +0.01 c), +0.32 c after 1 minute (t 2.4),
  +0.98 c after 10 minutes (t 2.4), +1.05 c after an hour; its sells are followed by nothing (-0.13 / -0.17 c). Only
  31% of its buys follow a same-direction print in the previous 30 s: it is usually the first to move.
- What triggers the buys is only partly identified. T2 (pre-registered): a sibling market of the same event moved
  2 c or more in the 120 s before 22.2% of 1,638 buys against 9.0% at placebo times one hour earlier (ratio 2.48;
  own market: 20.8% against 4.5%). So about a fifth of the buys follow a move in a related market; for the rest no
  price move precedes them in its own or a sibling market. It reacts to news jumps in only a minority of cases: a
  fill within 10 s in 28 of 380 jumps, $833 of 5-minute value in 14 days. Example of the sibling pattern (Israel
  PM event, 26 Nov 05:25:07 UTC): sold Eizenkot YES, bought 2,000 Netanyahu NO at 0.833 in the same second, sold
  them at 0.854-0.855 between 35 and 45 s later, much of it in 20-share clips into a bid that kept refilling.
- Falsification: "it is a maker in disguise." Roles come from the multiset difference of the full and taker-only
  feeds (0 maker fills of 35,346), and the API shows $21 of maker rebate against $30.7K of taker rebate in five
  months. It is a taker. "The profit is the rebate": no, rebates are 14% of what it kept.
- Fee: it paid 0.58% of volume when election/politics rates were 0.04-0.05; fees ate 62% of the November gross
  (36.1K of 58.4K). Since Nov 21 non-election politics, weather and culture are 0.01, which helps this style most.
- To copy: live books for thousands of markets (WebSocket; not possible from this sandbox), a signal we have not
  identified for four fifths of its entries, $20-50K of working capital at its size (rough: half a day of buys).
  Capacity: its typical clip is $7-90.
- Confidence that it is real and persistent 4; in the stated trigger 2.

### 4. 0x9495d622 (0x9495...468f) - reward-farming maker (SPLPB and hfv are the same business)

- 14 days: 12,006 fills in 2,963 markets, 97% maker, median market turnover $12. Politics: 876 markets, 4,385 fills.
- Its fills lose: maker buys are filled 1.47 c below the last print and the price is 0.80 c below the fill a minute
  later (t -4.5) and still -0.74 c after an hour; round trips inside the window realise -2.76 c a share (136K shares,
  -$3.8K in politics alone). Jumps hit its resting orders in 41 of 717 cases (5-minute cost only $758), so the loss
  is ordinary adverse selection, not headline risk.
- Monthly (API): gross -12.4K / -26.6K / -11.5K / -3.2K / -28.7K / -33.0K (Jun-Nov), rewards and rebates +17.3K /
  +34.8K / +16.2K / +11.8K / +47.3K / +47.5K, kept +4.6K / +7.6K / +4.7K / +8.4K / +18.4K / +14.2K. Cash over 60
  days: rewards $91.5K, maker rebates $4.2K, net cash +$9.2K, open positions $8.3K now (value at the start unknown).
  It uses merges (5,098) and conversions (1,303) to turn two-sided inventory back into cash.
- Same pattern elsewhere in the 14 days: SPLPB gross -14.0K, rewards 14.5K, kept 1.3K; hfv gross -35.3K, rewards
  44.1K, kept 5.4K.
- Falsification: "it earns the spread and the rewards are a bonus." Fails: the trade PnL is negative in all six
  months and in all three accounts; without rewards the business does not exist.
- Not a time gap. Market making paid by the rewards program; the account kept 22-39% of its rewards and rebates in
  five of the six months (72% in September).
- To copy: quotes inside the rewards band on hundreds of markets at the minimum size (20-200 shares, 1,000 on the
  biggest), merge/conversion plumbing, cancel-on-move. Capital was not measurable (open orders are not public).
  Maker fee 0; maker rebate 0 for a new account.
- Confidence in the description 4; that it pays at small scale 2.

### 5. Lolakis (0x401e...6fc9) - market maker that does earn the spread (mostly tech/finance; politics 16%)

- Kept +21.9K / +7.4K / +7.5K / +21.8K / +48.7K / +52.0K (Jun-Nov); in Oct-Nov rebates and rewards are 61.1K of
  the 100.8K kept, trade PnL is positive in all six months. No conversions.
- Politics, 14 days: 890 fills, $226K, 55 markets, 89% maker, median fill $42, p90 $697; same events as Car (Iran
  ceasefire ladders, FAA ground stop). Maker-to-maker round trips +0.68 c a share (0x9495d622: -2.79 c); mark-outs
  -0.5 c at 1 minute, about zero after a day; hit by a jump as a maker in 4 of 307 jumps.
- Difference from the farmers: 55 markets instead of 876, sizes 5-80 times larger, quotes that are rarely there
  when the jump comes. That is a judgement about its quoting that the public data cannot show directly.
- Confidence 3 (politics sample is 30 markets; most of its business is elsewhere).

### 6. kaxel78 (0xc1b5...5d85) - conversion farmer, the small copy of Bigggggggg

- Since 2026-10-12: bought $1.19M, conversions $1.08M, merges $62K, sells $42K: net of the trade about -$4.0K
  (fees included), rewards $8.6K, rebates $0.9K, open positions $0.5K: **+$5.5K real against +$81.4K on the API**.
  78% taker, $61 a fill, 2,281 markets in 14 days. 518 conversion events: -0.31% of buys (t -3.0), 25% positive.
- Why it runs at a loss before rewards was not established (rewards on resting NO bids, volume for a tier, or
  simply a worse version of the same idea).
- Confidence in the numbers 4.

### 7. BetaShrimp (0xe5aa...44db) - small all-category taker, no evidence of an edge yet

- Since 2026-10-17: 5,805 trades, bought $51.6K, sold $25.5K, conversions $15.8K, redeems $4.3K, rewards $0.8K: net
  cash -$5.2K, 1,022 open positions marked at $6.8K: +$1.7K if the marks hold, against +$8.9K on the API.
- 14 days: 950 markets, $15 a fill, 84% taker, spread over politics / finance / sports / crypto / economics; no
  family has a t above 1.3. Its 192 non-conversion events are -21% of buys in cash with the open positions
  outstanding.
- This is the only account at our scale on the board, and its result is noise so far. Confidence 3.

## Tests

- **T1 (pre-registered, one variant; `protocol.md`, `t1_nearcertain.txt`)**: all taker buys at 0.95-0.999 on the 24
  resolved politics tapes (3,404 fills, 1,047 wallets, $1.98M): gross -0.41 c, after fee **-0.48 c a share (se 2.15,
  t -0.2)**, total -$9.7K. Earlier half of the markets -3.73 c (t -0.7), later half +1.89 c (t 14.1): the halves
  disagree because the losses sit in 6 of 24 markets (5 in the earlier half). By price: 0.95-0.97 +2.40 c (t 2.1),
  0.97-0.99 +0.20 c, 0.99-0.999 -2.48 c. No wallet bought at 0.95+ in 10 or more of these markets. Verdict: no
  demonstrated edge. The sample is selected (markets the studied accounts trade) and small.
- **T2 (pre-registered, one variant; `t2_sibling.txt`)**: see Cb94C437. Prediction met (ratio 2.48), coverage 22%.
- Exploratory, one setting each, not pre-registered: mark-outs (`markout.py`), jump detection at 8 c / 120 s
  (`jumps.py`), sibling lag (`ladder_lag.py`): 12 events, 52 follower legs, lag median 12 s, p90 133 s, 18 legs at
  30 s or more; prints at the old level after the leader had moved in 16 legs, 10,963 shares, worth $3,751 against
  the level five minutes later, of which $3,091 is one leg (FAA "by 9pm ET": three prints at about 0.07, 119 s after
  the "by 11:59pm" leg had gone 0.37 -> 0.83, then 0.86).

## What the winners here have in common

- None of the real winners is a speed-only reactor and none buys certainty. The profit is in structure (neg-risk
  conversion, rewards) or in knowing the subject (Car), plus one taker with a signal we could not fully read.
- Zero or low fees matter: Car's home is fee-free geopolitics; Cb94C437 gave 44% of its gross to fees under the old
  rates.
- Everything that looks like a small-fill money machine on this board must be rebuilt from cash before it is
  believed. Any account with conversions is suspect.
- Reward farming is a real income but a thin one: three accounts kept 9%, 12% and 43% of 14 days of rewards.

## What was run

`leaders.py` 1; `pmlab.wallet` 18 accounts (xtxpleasecallme truncated at 60,000 fills); `wallet_check --monthly` 18;
`cash.py` 10 accounts (5 whole-life, 5 windows of 30-60 days; 5 rerun to add per-event output); `evstats.py` 5;
`dive.py` 5 accounts (7 runs); `markout.py` 4; `jumps.py` 4; `cb_seq.py` 1; `negrisk_story.py` 1;
`car_stories.py` 1; `t1_nearcertain.py` 1; `t2_sibling.py` 1; `ladder_lag.py` 1. No parameter was changed after
seeing a result.

## What could not be checked

- When each headline became public. All lags are from the first print of the move.
- Books: no historical depth was used, so nothing here shows what size was available at a price, only what traded.
- Capital in use by the makers (open orders are not public) and by Cb94C437.
- Why the small converters accept a trading loss; whether Bigggggggg's November is really negative (the API says
  -127K; the cash rebuild was done for the whole life only).
- The 0x9b129aD0 cluster and xtxpleasecallme (cash rebuild over their whole life is 240K-1.5M fills each).
- Tapes are capped at the latest 40,000 prints per market; mark-outs use last prints, not mid-quotes, so maker
  mark-outs contain bid-ask bounce.
- 14 days for most accounts; persistence rests on the monthly API figures, which are only reliable for accounts
  without conversions (Car, Cb94C437, Lolakis).
