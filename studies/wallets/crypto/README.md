# Crypto category: how the profitable accounts make money (study of 2026-11-27)

Protocol written before any fills were read: `protocol.md`. Public, read-only data. Wallet windows: 14 days to
2026-11-27 (`<name>.txt`, `<name>.json`); deep work on fills of 2026-11-21 00:00 .. 2026-11-27 00:00 UTC (the six days
with Binance 1-second dumps). One or two weeks of one account is weak evidence; monthly persistence is in
`<name>.monthly.txt`. Every number below says how many markets it rests on.

## Short answer

1. **Nobody on the board earns from a "pair under $1" arbitrage or from a slow gap.** The systematic winners are
   (a) makers who buy with resting bids and hold to settlement, (b) one new speed taker, (c) model-based market
   makers on the strike ladders. Speed (1-3 s after a Binance move) is in every one of them, either as fast
   requoting or as fast taking.
2. **The one mechanism that looks reachable for a small account is the late resting bid**: a bid at 0.99-0.999 for
   the leading outcome in the last 30 s of a 5-minute window and in the ~20 s between the end of the window and the
   on-chain resolution. Account `0x50f7` does this for $250K a day. Checked on the whole market, not on one account
   (`late_pool.py`, 5,388 tapes of 21-26 Nov): resting buyers at >= 0.99 on BTC 5m earned +0.45..0.55 c/share in
   the last 30 s (1 losing market in 1,619) and +0.32..0.43 c/share after the end (0 losing markets in 1,343), in
   both halves of the sample. Pool: about $2.4-3.0K a day (last 30 s) plus $1.1-1.2K a day (after the end) on
   BTC 5m, $150-300 a day on ETH 5m, almost nothing on the 15-minute alts. Capital is tied for under a minute
   (markets resolve 17-21 s after the window ends; `0x50f7` redeems a median 34 s after the end). What is NOT
   known: the share a new bidder at the back of the queue would get, and how much worse its mix of fills is.
3. **A small passive two-sided maker exists at our capital scale** (`tiredofwinning2much`: median fill $3.90,
   $68 per market, 2-3 markets at a time) but its margin before rebates fell from 4.4% of volume in August to 0.4%
   in November, and 30% of what it keeps is maker rebates from a three-wallet fee group. Not a business for a new
   account with 0% rebate.
4. **Threshold markets (above X, hit price) are a market-making business**, not a time-gap one: `0xDB5` (positive
   21 months of 22) and `x6916Cc` quote both sides and earn about 0.5-0.6% of volume; none of the three threshold
   accounts bought a barrier outcome after the barrier was touched. The taker `Eager47259` is not distinguishable
   from noise on 14 days (t = 1.2 by market).
5. The crypto leaderboard is polluted: about 30 anonymous `0x…` wallets show $60-150K of "category PnL" each and
   kept about zero (they only SELL on BTC 5m as makers, 0 buys and 0 splits in their feed: the board counts sale
   proceeds of inventory that arrives from elsewhere as profit).

## Selection

`tools/leaders.py crypto --top 60` -> `leaders.txt`, `leaders.json` (117 accounts). Screen: `screen.py` ->
`screen.txt` (last 3 days of fills, cap 4,000, turnover by sub-family; classifier in `subfam.py`).

Chosen:

| account | why | sub-families (3-day screen) |
|---|---|---|
| 0x50f7 (0xee65685d…) | 168,811 markets, 8 positive months of 8, rebates 3%, median price 0.99: tests "late buying" | BTC 5m 81%, ETH 5m 11%, 15m 8% |
| tiredofwinning2much (0xcd4a4057…) | 29,374 markets, $9 fills, 4 positive months of 4, ETH 15m | ETH 15m 38%, BTC 5m 32%, BTC 15m 30% |
| mo-money (0x32ed2e54…) | 118,275 markets, 6 positive months of 6, rebates 12%, 95% maker: something different on BTC 5m | BTC 5m 74%, BTC 15m 22%, 1h/4h/daily 2% |
| 0x0dbd0e1d (0x0dbd0e1d…) | 25,402 markets in 25 days, rebates 6%, all assets | BTC 15m 26%, ETH 15m 17%, BTC 5m 16%, ETH 5m 10%, XRP/SOL/DOGE/BNB |
| 0xDB5 (0xdb5ad26b…) | 13,883 markets, positive 21 months of 22, rebates 14% | BTC above 42%, BTC hit 37%, BTC range 11% |
| x6916Cc… (0x6916cc00…) | 3,419 markets, 464K fills, positive 20 months of 21, rebates 11% | BTC hit 87%, ETH/SOL/XRP hit |
| Eager47259 (0xab155a20…) | 5,663 markets, $31 fills, rebates 7%, +104K in November | BTC hit 43%, BTC above 19%, ETH above/hit 17%, stocks |
| bubble-bobble (looked at, tables only) | the only board account on alt hourlies, $4 fills | SOL/ETH/DOGE/BNB/XRP 1h |

Skipped, with the reason:

- hqb.prediction (+664K in one month, 246 markets, sells hit-price tails), greater-fools (6 markets), Cyclewin
  (12 markets), haveanedge.xyz, max1ved (29 markets), Lunarcorona (27), 76marsh (61), wahmanmarket (92, $1,097 a
  fill), Berkaja, Rhabarberbarbarbar, borderlocket, ponzisniper, 0x82aad706, floatingraft: whales or one-month
  directional results.
- Tokor (+1.34M, $281 a fill, buy-only hit-price), 0xf705fa04 ($838 a fill), getbipped, justdance, 0x06dc5182
  (+998K all-time, -119K in November), Sharky6999 ($619 a fill, months +43K/-35K/+56K), AllByMyseIf (97% outside
  crypto), 033033033 (88% outside crypto, $5,243 a fill): large directional or big-ticket books; not systematic at
  a size we can learn from in two weeks.
- Bonereaper/wzbbb/Hcrystallash (one fee group, rebates 128%/43%/24%), dangerously-skip-permissions/GoodFallen
  (53-60%), CrouchPredictions (74%), blue.birds (79%), tmsd-test (180%), Polkadot-Frog (198%), 0xb55fa129 (107%,
  the only daily/hourly up/down specialist; same fee group as 0x06dc5182), stepahead (67%), coinfilippe (51%),
  snoopdoge (70%), EZTRADENL2, pnyz, hdueilqhsdn, lkojihfafaf: rebate-driven; a new account gets 0%.
- almach, bosona: same bot as mo-money (NOTES.md); one studied.
- mykr0ph0ne, thesidehustle: same fee group as tiredofwinning2much (found here, see below); one studied.
- About 30 `0x…` wallets with 14-21K markets, $7-10 fills and kept_all between -2K and +10K (0x8edb6bc0…,
  0x9E696317…, 0x20e5e881… and so on): sell-only BTC 5m makers, see point 5 above. Checked one (0x976dcfd8…):
  649 fills in 24 h, all SELL, all maker, activity feed contains only TRADE rows.
- e46m3, LlamaLoco0000, The Spirit of Ukraine: no crypto in the last three days. minusalpha1, penguinx, suntori,
  neutralwave23, 0x9e3ed7b6, adadmadm…, the.prod.dt, 0x765e6a48: losing accounts.
- Passed the screen, not studied (budget): 0x1bc32be1 (15m alts, +200K in November, -31K in October),
  0x502b532F, machinelearned, arcsine-barrister (sell-only BTC 5m, 24% rebates), CleanCoinFlip, ComTruise,
  Lolakis, Egozic86, hoodquant, mia1111, newbeginning2, THG. (the last three trade like 0x50f7: median price 0.99).

Fee groups among board accounts (identical 30-day weighted volume in `gamma /v1/maker-tier/tiers`):
tiredofwinning2much + mykr0ph0ne + thesidehustle (5.62M, 10% maker rebate); Bonereaper + wzbbb + Hcrystallash;
dangerously-skip-permissions + GoodFallen; 0x06dc5182 + 0xb55fa129; hdueilqhsdn + lkojihfafaf.

## Tool totals against the "API says" line (14 days unless truncated)

| account | window | fills | markets | turnover | maker share | tool net | API kept | why they differ |
|---|---|---|---|---|---|---|---|---|
| 0x50f7 | 14 d | 28,666 | 5,555 | $4.17M | 91% | 8,332 | 10,926 | API counts 1,060 more fills ($150K); not explained. Tables are internally consistent (all markets resolved, no sells). |
| tiredofwinning2much | 7.9 d (TRUNCATED) | 59,998 | 3,702 | $405K | 100% | 3,769 | 5,540 | rebates 894; API has 1,614 more fills at the cut |
| mo-money | 12.1 d (TRUNCATED) | 59,999 | 5,831 | $1.88M | 95% | about 28,700 | 26,802 | within 7% |
| 0x0dbd0e1d | 13.8 d (TRUNCATED) | 59,999 | 17,952 | $1.31M | 38% | about 50,300 | 46,477 | within 8% |
| 0xDB5 | 14 d | 15,706 | 605 | $1.23M | 56% | -81 | 10,906 | 76 markets still open (cash out so far -26,679), 37 incomplete (+3,000), 729 merges ($121K); the profit sits in open and carried positions |
| x6916Cc | 14 d | 8,257 | 207 | $4.69M | 100% | -1,748 | 14,840 | 141 of 207 markets open, 93 carry inventory from before the window; rebates 4,246; spread is earned inside open markets |
| Eager47259 | 14 d | 54,488 | 2,097 | $1.97M | 25% | 45,811 | 58,500 | 388 open markets marked to market by the API, rebates 5,037 |
| bubble-bobble | 14 d | 1,847 | 655 | $7.2K | 52% | 206 | 195 | agree |

## Account by account

Scripts: `ud.py` (cached fills, Binance fair values), `deep_updown.py` -> `out/deep_updown_<name>.txt`,
`checks_ud.py` -> `out/checks_ud.txt`, `stories_ud.py` -> `out/stories_ud.txt`, `deep_thr.py` ->
`out/deep_thr_<name>.txt`, `markout_thr.py` -> `out/markout_thr_<name>.txt`, `late_pool.py`, `late_pool_split.py`.
Match time = block time - 3 s. "Fair" = `pmlab.fair.fair_up` on Binance 1 s closes with the Binance TWAP as the
price to beat (the proxy agreed with the official outcome on 97.7-99.4% of fills).

### 1. 0x50f7 — resting bids at 0.99+ for the leader, late and after the end; penny bids on the trailing side

Months (kept): Apr 91.6K, May 39.4K, Jun 181.6K, Jul 138.0K, Aug 30.5K, Sep 54.7K, Oct 48.3K, Nov 17.9K
($91.8M volume, kept 0.66%, rebates 3%). The trend is down.

14 days: buy only, never sells, redeems. $3.77M of the $4.17M was maker buys at 0.99-1.00 (avg 0.9976):
+0.219 c/share, se 0.027, 2,284 markets, +$8,269. Another 18,379 maker fills at 0.00-0.15 (cost $19.6K) on the
trailing side in the middle of the window: -$813 under 5 cents, +$971 at 5-15 cents, about zero in total.
Taker buys at 0.99+ ($338K): -0.38 c/share (one loss).

Six days, buys at >= 0.95 (`out/checks_ud.txt` part 4; 3,049 fills, 749 markets, $1.53M, 94% maker):

| when (match time) | fills | markets | usd | median gap to strike, bp | losing markets | net $ | net c/share |
|---|---|---|---|---|---|---|---|
| more than 120 s before the end | 35 | 11 | 17,984 | 37.4 | 0 | +164 | 0.90 |
| 60-120 s | 646 | 216 | 233,653 | 24.3 | 1 (-$3,005) | -2,519 | -1.08 |
| 30-60 s | 980 | 357 | 487,325 | 14.6 | 0 | +995 | 0.20 |
| 10-30 s | 699 | 269 | 406,386 | 10.7 | 1 (-$54) | +987 | 0.24 |
| 0-10 s | 253 | 164 | 107,350 | 10.1 | 0 | +216 | 0.20 |
| after the end, 0-30 s | 306 | 155 | 163,327 | 9.6 | 0 | +856 | 0.52 |
| after the end, over 30 s | 130 | 71 | 114,027 | 10.1 | 0 | +219 | 0.19 |

Falsification of "it buys only after the outcome is determined": false as stated. Only $277K of $1.53M (18%) was
bought after the window had ended; $1.0M (65%) was bought inside the last 60 s while the settlement TWAP was still
running, $252K earlier. The one large loss: `btc-updown-5m-1795299900`, 3,005 shares at 0.999 with 88-91 s left,
Binance 13.2 bp on the right side, model fair 1.000, and the price came back. Average win is 0.262 c per dollar;
observed loss share 0.20% of dollars; 2 losing markets of 749 (Wilson 0.07%..0.96%, break-even about 0.26%). On this
account alone the edge is not proven; the population check below is what makes it credible.

Ten markets, evenly spaced (`out/stories_ud.txt`): 3,008 Down at 0.999 at 248-278 s of a 300 s window with Binance
21 bp below the strike; 12,356 Down at 0.999 from 275 s to 40 s AFTER the end; 6,118 Up at 0.990 19 s after the
end; 1,953 Up at 0.990 at 871-904 s of a 900 s window with a gap of only 1.7 bp (won). Sizes $200 to $12K per
market; median one market a minute, at most 5. Capital tied up (2 days): median $11, p90 $3.0K, peak $32K on
$494K of turnover.

Time gap: (a) window end -> on-chain resolution, 17-21 s (two markets checked), paid by holders who sell the
winner at 0.99x instead of waiting; (b) the last 30-60 s, when two thirds or more of the 60 s settlement average is
already fixed. Fee: none (maker). To copy: Binance (better Chainlink) price stream, the TWAP so far, a rule on the
gap in sigmas, post-only bids, auto-redeem. Risks: reversal in the last 60-90 s (one such event costs 400 wins);
proxy/Chainlink disagreement for gaps under 1 bp; queue priority; from 2026-11-30 the Chainlink feed needs a key;
the "Nex" matching engine in mid-December changes queue dynamics. Confidence 4.

### 2. tiredofwinning2much (+ mykr0ph0ne, thesidehustle) — small passive bids on both outcomes

Months (kept / kept without rebates / volume): Aug 12.5K / 10.9K / $248K; Sep 27.4K / 22.7K / $706K; Oct 12.2K /
6.5K / $1.41M; Nov 17.7K / 8.9K / $2.25M. Margin before rebates: 4.4% -> 3.2% -> 0.46% -> 0.40% of volume. The
fee group holds 5.62M of 30-day maker weighted volume (this wallet 0.80M) -> 10% maker rebate tier; siblings on the
board kept 14.0K (mykr0ph0ne) and 23.5K (thesidehustle) in November.

7.9 days: 59,998 fills, 100% maker, 100% buys, both outcomes in 3,592 of 3,702 markets, +0.452 c/share (se 0.121,
t 3.7, 3,698 markets). Six days by family (`out/deep_updown_tiredofwinning2much.txt`):

| family | markets | pairs (shares) | pair cost | pair PnL | residual shares | residual win % | residual PnL |
|---|---|---|---|---|---|---|---|
| BTC 15m | 575 | 76,060 | 0.9822 | +1,352 | 28,492 | 46.4 | -1,151 |
| BTC 5m | 1,722 | 73,962 | 0.9786 | +1,580 | 40,362 | 53.2 | -307 |
| ETH 15m | 576 | 101,377 | 0.9591 | +4,143 | 27,294 | 26.0 | -3,059 |

Fills of 5-30 shares (median $3.90, max $30), median 12 fills and $68 per market, first fill 20 s after the start,
last 83 s before the end, 2-3 markets at once; positive on each of the six days ($56 to $697). Its bids sit
around fair value (+0.9 c/share below the Binance fair at the match, flat from -10 s to +30 s: neither picked off
nor fast).

Falsification of "pair arbitrage with no risk": false. Pairs made $7,075 and the unmatched residual lost $4,517;
median share imbalance per market 18%, p90 54%. Ten stories: `out/stories_ud.txt` (4 of 10 sampled markets lost).

Mechanism: market making with tiny clips; no time gap. To copy: a quoting loop on 3 series, inventory cap,
about $500-1,000 of capital. Fee 0; what a new account keeps is the 0.4% before rebates, which is 4 cents on a $10
fill and shrinking as volume grows. Confidence 4 on the mechanism, 2 that it still pays for a newcomer.

### 3. mo-money (+ almach, bosona) — BTC 5m/15m maker that requotes fast and ends up long the winner

Months (kept): Jun 37.8K, Jul 157.3K, Aug 148.7K, Sep 109.7K, Oct 87.7K, Nov 102.1K; rebates 12%; $17.5M volume,
kept 3.7%. almach and bosona show the same curve (98.3K and 69.5K in November).

12 days: 95% maker, buys only; BTC 5m +$27.9K on $1.36M (t 3.0, 3,320 markets); BTC 15m -$4.9K on $386K; 1h/4h
small. Six days: maker buys on BTC 5m +1.36 c/share (se 0.59, 1,669 markets). It is NOT pair accumulation: pair
cost on BTC 5m was 1.074 (-$25.8K) and the residual one-sided inventory (429K shares at 0.659) won 75.5% of the
time (+$41.1K). The profit is in maker buys at 0.70-0.95 (+2.07 c/share, se 1.03, 1,703 markets).

Speed check (`out/checks_ud.txt` part 2, maker buys at 0.30-0.95, 18,672 fills): the Binance fair value of what it
bought minus its price was -12.1 c thirty seconds before the fill, -4.1 c five seconds before, -1.8 c at the match
and -1.5 c after: its bid is filled right after Binance moved towards that side, i.e. it lifts its bid on the new
leader faster than sellers reprice. Its few taker fills (552) show the same shape, steeper.

Falsification of "it earns the spread like a neutral market maker": false, it carries direction on purpose.
Mechanism: speed as a maker (cancel/replace within about a second of the Binance move) plus a momentum tilt.
To copy: co-location class latency in London and a tuned signal; not for one small VPS. Fee: 0 as maker, 0.05 on
the few taker fills. Confidence 3 (the tilt could also be a better price model than ours; see the calibration note).

### 4. 0x0dbd0e1d — taker that buys within seconds of a move, all assets, holds to settlement

Joined 2026-11-02: one month only. +66.9K kept on $2.11M (3.2%), rebates 6%, taker fees paid 15.0K.
13.8 days: 59,999 fills in 17,952 markets (12 series including DOGE and BNB), 62% taker, 96% buys, one outcome in
93% of markets. Taker buys +2.98 c/share after fees (se 0.70, t 4.25, 10,607 markets); maker buys +0.88 (t 1.0).
Best family BTC 15m: +$22.3K on $387K (fee rate 0.05 there), t 3.05 on 1,170 markets.

Speed check (taker buys at 0.30-0.95, 3,559 fills): fair minus price was -13.5 c at -30 s, -8.4 c at -10 s,
-6.1 c at -5 s, -3.7 c at -3 s, -2.1 c at -2 s, 0.0 at the match, +0.3 c one second later and flat after that.
Binance moved 4-7 bp towards the bought side in the 5 s before the match and 4-5.5 bp in the 25 s before that, in
every asset; BTC moved the same amount before the alt fills, so "BTC leads the alts" cannot be separated here.
It trades with 120+ s left (no fills in the last 60 s), sizes $3 median, $40 at p90, up to $3.7K per market,
2-4 markets a minute. Days: +1.7K, +3.0K, +4.4K, +5.0K, -8.4K, +8.1K.

Falsification of "it buys cheap against the Binance model": false. At the match its price equals the model fair
value; the realised +3 c comes from the model understating the leader that week (calibration below) and from being
first after the move. Lag exploited: about 1-3 s between a Binance move and the Polymarket book (block-time
resolution; cannot be measured tighter here). To copy: websocket feeds, sub-second reaction, 150 ms taker delay,
capital of a few thousand. Risks: one month of history, daily swings of +-$8K, fee 0.05 on BTC. Confidence 3.

### 5. 0xDB5 — model-based two-sided maker on the BTC/ETH strike ladders (above, hit, range)

Positive 21 months of 22 since Feb 2025 (June 2026: -6.7K); 2026: 16.1K, 14.6K, 14.2K, 26.4K, 24.9K, -6.7K,
23.6K, 9.9K, 9.9K, 9.2K, 30.9K. $34.6M volume, kept 0.60%, rebates 14%.

14 days: 605 markets (BTC hit 246, BTC above 103, BTC range 93, ETH above 62, ETH range 62), both outcomes in 385,
729 merges. Maker buys +1.61 c/share (460 markets), maker sells +1.80 (287); taker buys -1.92, taker sells -1.65.
Six days (`out/deep_thr_0xDB5.txt`): its taker fills come after spot moved 10-18 bp in 30 s and 25-70 bp in 5 min
in the trade's direction (it takes stale quotes and resets inventory after a move); its maker fills come after no
move (-0.4..+1 bp). Tape markouts on 12 markets (`out/markout_thr_0xDB5.txt`): maker +0.68 c at 10 s (se 0.33),
+2.15 c at 10 min, +2.70 c at 1 h (se 1.30); taker +0.86 c at 10 s (se 0.85).

Falsification of "it buys the hit outcome after Binance already touched the level": false, 1 of 3,576 hit-market fills came
after the first 1 s close through the barrier. Mechanism: a volatility model per strike, quotes around it, pairs
merged to recycle capital, positions held to resolution (hours to days). No time gap. To copy: an option-style
pricer fed by Binance and Deribit, quote management on about 100 markets, fast cancels; capital in the tens of
thousands at its size, a few hundred would cover two or three strikes. Fee 0.01 on its taker half. Confidence 3.

### 6. x6916Cc — passive size on hit-price markets (weekly and monthly)

Positive 20 months of 21 (July 2026: -13.8K); Sep 35.4K, Oct 18.8K, Nov 27.5K; $104M volume, kept 0.53%,
rebates and rewards 11%.

14 days: 8,257 fills, 100% maker, $568 a fill, 207 markets (BTC hit 102, ETH 47, SOL 37, XRP 17), buys 51% / sells
49%. Six days: bought "No" for $1.12M at 0.899 and sold "No" for $1.20M at 0.908; spot moved less than 1 bp
against it in the 30 s before its fills. Stories (`out/markout_thr_x6916Cc.txt`): blocks of 1,000-6,000 shares both
ways in far strikes (buys 5,978 Yes of "reach 68k" at 0.019, sells 5,980 at 0.016; buys 4,024 Yes of "dip to 50k"
at 0.055 during a sell-off, sells at 0.042 and 0.031 as it recovers).

Mechanism: spread plus liquidity rewards (markets carry rewardsMinSize 50, rewardsMaxSpread 4.5 c) on a large
balance sheet; no fills after a barrier touch. Not a time gap, not copyable with a few hundred dollars. Confidence 3.

### 7. Eager47259 — ladder trader on crypto strikes and stock closes, mostly taker

Months: Jun -0.4K, Jul +2.3K, Aug +0.1K, Sep -0.6K, Oct +19.3K, Nov +104.4K (volume $9K -> $409K -> $2.74M).
Two profitable months, both after it scaled up.

14 days: 2,097 markets (BTC hit 268, BTC above 144, ETH above 136, ETH hit 185, stock markets 522, hourly and
4-hour up/down 288 with about $15 a market), 72% taker, sells 25% of volume. Net by market t = 1.17: not significant.
Taker fills at 0.15-0.30 +7.4 c/share (t 2.5, 523 markets); taker fills 1-7 days before the end +3.6 c (t 3.05, 480
markets); taker fills 6-24 h before the end -0.9 c (641 markets). Stocks: +$17.2K on $184K, 100% taker (outside this category).

Six days (`out/deep_thr_Eager47259.txt`, 24,485 fills): its taker fills, buys and sells alike, follow a spot move
of 2.6-4.1 bp in 5 s and 3-6 bp in 30 s in the trade's direction; its maker fills are preceded by -1..-5 bp.
Tape markouts on 12 markets: taker +0.11 c at 10 s (se 0.18), +0.37 c at 60 s (se 0.29), +0.24 c at 10 min; maker
about 0. The fee at these prices is 0.1-0.3 c, so the short-term edge per fill is about fee-sized.

Falsification of "it buys hit outcomes after the touch": false, 29 of 12,807 hit-market fills came within 10 s
after the touch and 28 of them were buys of "No" under 1 cent that lost (stale bids being hit). Mechanism: reprices the whole ladder off
spot and takes stale quotes; the month's profit is mostly inventory direction. Confidence 2.

### bubble-bobble (tables only)

Alt hourlies (SOL, ETH, DOGE, BNB, XRP 1h), $3.90 fills, splits and sells. Kept $1.5-5.9K a month from April to
August, then -0.6K, +0.5K, +0.2K; volume fell from $332K to $7K a month. The niche existed and has dried up.

## Population check: resting buyer at >= 0.99 late in up/down markets

`late_pool.py` -> `out/late_pool.txt`; time split `late_pool_split.py` -> `out/late_pool_split.txt` (the split was
written after the first table; rule fixed in its docstring before running; tune 21-24 Nov, report 25-26 Nov).
Every cached tape with official outcome: BTC 5m 1,728 markets, ETH 5m 1,726, ETH/SOL/XRP 15m 576 each, BTC 15m 206.
A taker sell of X at p (or a taker buy of the other side at 1-p) is a fill of somebody's resting bid for X at p.

| series | when | period | markets with fills | usd | c/share (se) | losing markets | pool $/day |
|---|---|---|---|---|---|---|---|
| BTC 5m | last 30 s | tune | 1,098 | 2,247,742 | +0.525 (0.036) | 0 | 2,967 |
| BTC 5m | last 30 s | report | 521 | 1,063,628 | +0.450 (0.080) | 1 | 2,407 |
| BTC 5m | after the end | tune | 910 | 1,357,675 | +0.324 (0.066) | 0 | 1,103 |
| BTC 5m | after the end | report | 433 | 562,957 | +0.432 (0.196) | 0 | 1,222 |
| ETH 5m | last 30 s | tune | 491 | 195,212 | +0.637 (0.102) | 2 | 313 |
| ETH 5m | last 30 s | report | 219 | 40,000 | +0.782 (0.095) | 0 | 158 |
| ETH 5m | after the end | tune / report | 152 / 118 | 254,969 / 9,917 | +0.195 / +0.508 | 0 / 0 | 125 / 25 |
| BTC 15m, ETH/SOL/XRP 15m | both | both | 4-148 | under 92K each | +0.11..+0.89 | 0-1 | under 50 |

Earlier in the window the same bid loses: BTC 5m at 0.99+ with 60-120 s left: -0.81 c/share, 7 losing markets,
-$20.4K in six days; BTC 15m 60-120 s: -6.6 c. The taker sells that hit these bids are small (median $9.5-19 on
BTC 5m), but 97-99% of the dollars come in fills above $50.

Limits: this is the average over everyone who was filled, with their queue position. A late joiner is filled
less when right and in full when wrong. The tape cannot show queue position; an L2 replay is needed.

## Other things verified on the way

- `pmlab.fair` (sigma_mult 1.3) understated the leader on BTC/ETH 5m and 15m in 21-26 Nov: fair 0.649 -> won
  0.673; 0.748 -> 0.782; 0.851 -> 0.893; 0.936 -> 0.954; 0.987 -> 0.985 (14,758 market-minutes at one passive
  account's fill times, about 2,870 markets). Do not read "price above fair" as "overpaid" in the 0.6-0.95 range.
- Up/down 5m and 15m markets close on chain 17-21 s after the window ends (closedTime - endDate, two markets).
- Threshold families and their rules (seven markets read): "above X on date" and ranges settle on the Binance 1 m
  close at 12:00 ET; hit-price (daily, weekly, monthly) on any Binance 1 m High/Low from market creation; daily
  up/down on two noon closes; fee rate 0.01, tick 0.001, rewards min size 50 / max spread 4.5 c.
- None of the three threshold accounts trades the seconds after a barrier touch.

## What was run (count of variants)

Screen 1; `pmlab.wallet` 8 accounts, once each; `deep_updown.py` 4 accounts, one version; `checks_ud.py` 5
checks, one version; `stories_ud.py` 1; `deep_thr.py` 3 accounts, one version; `markout_thr.py` 3 accounts, one
version; `late_pool.py` 1 and its time split 1; two side checks (sell-only wallet, fee groups). No parameter was
tuned and nothing was rerun with different settings.

## What could not be checked

- Queue position and cancels: no order data per wallet, only fills. Reaction times are bounded by block time
  (2-3 s lag, 1-2 s jitter), so "1-3 s" is the best statement possible here.
- The strike models use a flat lognormal with trailing 24 h realised volatility or Deribit DVOL (30-day), not the
  option smile for the matching expiry; the model columns in `deep_thr` are rough and no conclusion rests on them.
- Hit detection uses 1 s closes, not 1 m highs/lows: a wick inside one second is missed.
- SOL/XRP/DOGE/BNB 5m, hourly, 4-hour and daily up/down: only as rows in the wallet tables; no board account with
  low rebates specialises there.
- The 0x50f7 gap between tool and API (24%) is not explained.
- Whether 0x0dbd0e1d's edge survives a second month.
