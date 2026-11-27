# Finance category: how the profitable accounts make money (study of 2026-11-27)

Window for fills: 2026-11-06 16:00 .. 2026-11-27 16:00 UTC (21 days) unless a line says otherwise; a second window
(2026-09-25 .. 2026-10-16) is used once as a falsification. Protocol written first: `protocol.md`.
All numbers are after the taker fee (0.05 * p * (1-p) per share; makers pay nothing), rebates and rewards = 0.

## Short answer

1. The "finance" board is three different things. (a) One-off news money: the top of the month board is the NVIDIA
   CEO story (Jensen Huang markets of Nov 12 and Nov 23) and the Anthropic IPO of Nov 19; those accounts have 3-130
   markets and one month of profit. (b) Price ladders on stocks, ETFs, indices and commodities ("close above X",
   "hit HIGH/LOW X this week/month", "Up or Down today"), settled on Pyth 1-minute candles, about $126K of volume a
   day in the part we could measure, median $130-1,075 per market. (c) "Bond" buyers who pay 0.95-0.999 for outcomes
   that are decided or nearly decided.
2. There is no usable time gap in the price ladders. The winners there do NOT buy after the outcome is known:
   grasstoucher69 55 of 8,588 buy fills at/after the deciding time, thanksforplayin 6 of 2,578, superstonksbro 19 of
   2,208. On the tapes of 547 "hit" markets that were touched (the markets of the seven accounts' 21-day activity), takers
   locked in $1,185 by buying after the touch (70% of it more than an hour later, i.e. probably Yahoo/Pyth mismatch, not a gap). After the 16:00 ET close
   168 trades happened in 723 close/up-down markets, net taker gain -$50. These markets resolve on-chain a median 16
   minutes after the deciding candle (p10 16, p90 21), and the whole discount paid by sellers in those 16 minutes was
   $889 in 21 days over 1,323 markets.
3. What the systematic ladder winner (grasstoucher69) does is buy cheap outcomes on both sides of hundreds of ladders
   (average price 0.24-0.33, $26 a fill, maker and taker, any hour of the day), hold to settlement and merge pairs. It
   is long volatility. In both windows we looked at, ALL of its profit is on the bearish side and the bullish side
   loses (Nov: +62.5K / -15.8K; Sep 25-Oct 16: +94.1K / -45.7K), and the same is true of the losing account
   PippiTrader. NVDA fell from 224 to 148 across those months. We could not separate "cheap tails are structurally
   underpriced" from "the market fell and realized volatility was high". Its 8 positive months of 9 since March are
   the only evidence for the first reading.
4. The bond money in finance is not in the automated price ladders (0.1-0.4% for 16 minutes, pennies per market) but in
   event markets with a human-speed resolution (Anthropic IPO / valuation): CoinTrick made $5.7K of its $7.3K finance
   result of the window in five such markets, buying at 0.95-0.99 between 7 and 15 hours before resolution.
5. For a few hundred dollars: nothing here is a ready strategy. The ladder tail-buying fits the ticket size but its
   edge is unproven outside a falling market; the post-decision bond needs speed for cents; the event bond needs rule
   reading and carries reversal risk we did not measure in finance (in mentions it was 1.6-4.2%).

## Public price sources from this sandbox (tested 2026-11-27)

| Source | Result |
|---|---|
| Yahoo chart API `query1/query2.finance.yahoo.com/v8/finance/chart/<SYM>` | works: 1-minute bars with `includePrePost=true` for the last 30 days (7-day chunks via `period1/period2`), 5-minute, daily. Symbols used: stocks/ETFs as is, `^GSPC`, `^DJI`, `^RUT`, `^N225`, `GC=F`, `SI=F`, `CL=F`, `DX-Y.NYB`. This is the proxy used everywhere below |
| Nasdaq API `api.nasdaq.com/api/quote/<SYM>/info|chart|historical?assetclass=stocks` | works (needs an `Accept: application/json` header); `info` returns the last sale flagged `isRealTime: true` with bid/ask; `chart` is the intraday series; `historical` daily OHLC. 2-3 s per request |
| stockanalysis.com `/api/symbol/s/<SYM>/history?type=daily` | works, daily only |
| Google Finance quote page | 200 (HTML, 1.7 MB), not parsed |
| Binance mirror `PAXGUSDT` | works; a gold proxy only |
| stooq.com CSV (`/q/d/l/`, `/q/l/`) | NOT reachable: connection reset by peer on all three URLs |
| Pyth (the settlement source) | Hermes `v2/price_feeds` (feed list and market hours) works; `v2/updates/price/...` returns 401 unauthorized; `benchmarks.pyth.network` TradingView shim returns 404; `pythdata.app` answers 307. We have NO history of the candles the markets settle on |
| finnhub, alpaca, twelvedata | need an API key (401) |
| marketwatch 401 (bot wall), investing.com 403, cdn.cboe.com options 307 | not usable |

Consequence: every "deciding time" below is the Yahoo candle, not the Pyth candle. 24 of 602 hit markets that resolved
Yes have no Yahoo touch at all (4%), so individual timings within a minute or within a few cents of a strike are not
reliable. Option-implied odds could not be built (no option chain source answered), so the yardstick is a plain
lognormal model on realized volatility (see "Model").

## Rules of the price ladders (read from market text)

- Resolution source: Pyth, 1-minute candles (`https://pythdata.app/explore/Equity.US.<TICKER>/USD`). "Close" = the
  Close of the candle of the final minute of regular trading hours, NOT the exchange's official closing-auction price.
  Equal to the strike resolves No (close markets) or 50-50 (up/down).
- "Hit (HIGH/LOW) X week of / in <month>": Yes if any 1-minute candle High/Low in regular hours (stocks) or in the
  trading session (metals, oil: 18:00-17:00 ET) is at or beyond X after market creation. These resolve EARLY: a median
  16 minutes after the touch.
- Anthropic "close below IPO price" markets use Nasdaq's official closing price; Anthropic valuation markets use the
  Nasdaq Private Market price and, after the IPO, public market cap.
- Fee type `finance_prices_fees`, rate 0.05, tick 0.001 or 0.01, minimum 20-50 shares in the rewards band but
  `clobRewards` is null on every sampled market: there is no liquidity-rewards program on these markets now.
- Fee implied by real charges (API daily fees / sum of shares*p*(1-p) over taker fills): grasstoucher69 0.0462 on
  Nov 7-19 and 0.0493 on Nov 22-26 (largest base); the three smaller bases scatter between 0.018 and 0.060 (day
  alignment). Consistent with 0.05 now and something close to it before Nov 20.

## Selection

`tools/leaders.py finance --top 60` -> 139 accounts (`leaders.txt`). Screen of the last 7 days of fills for the 92
accounts with >=100 markets or >=1,000 fills (`screen.py`, `screen.txt`).

Chosen (7):

| Account | Why | All-time kept | Rebate share | Fills / markets all-time | Last months kept (Sep / Oct / Nov) |
|---|---|---|---|---|---|
| grasstoucher69 | 566 finance markets a week, $25 fills | 303,601 | 6% | 144K / 13.8K | +35.9K / +81.0K / +118.5K; 8 of 9 months positive since March |
| thanksforplayin | ladders, two-sided, 10 positive months in a row | 325,487 | 8% | 229K / 23.1K | +23.0K / +58.0K / +37.0K |
| superstonksbro | ladders, buys only | 333,568 | 11% | 98K / 8.9K | +19.1K / -38.6K / +28.6K (June -124K) |
| C03B | 0.99 buyer, 70%+ finance | 345,383 | 3% | 27.9K / 2.5K | +21.2K / +13.6K / +14.0K |
| CoinTrick | 0.999 buyer across categories, 880 finance markets in 14 days | 313,937 | 1% | 75.7K / 19.9K | +36.9K / +182.6K / +24.9K |
| Hauchn | market-cap rank markets, 92 fills per market | 465,953 | 1% | 20.9K / 227 | -9.0K / +104.3K / +131.1K (lumpy: Dec -46.7K, Jul +214K) |
| PippiTrader | CONTROL, breaks the rebate rule on purpose: same ladders, 76% of what it kept is rewards | 114,595 | 76% | 124K / 9.2K | +42.0K / +32.8K / -23.5K |

Skipped and why:

- 0x77958acc (cat month +314K), 0xEC1Fe517, nimble-mellow-comet, ljhggk, 0xB7632365, bbbbbbbbzzz, bmilabs,
  82727skjwojq, Srodt, Mork1e, simkind, jsdk3k21k, TinyRise, JD98, paule334 and the other one-month names: 3-130
  markets, fills of $0.4-19K, profit only in November, almost all of it in the NVIDIA CEO markets. Whales / news bets.
- WarriorPooh, Samael-of-Rome, aenews2, 0x21F701A6, TBill1, urhfrhchj123123: the same NVIDIA CEO markets (86-100% of
  recent "finance" turnover); WarriorPooh is already known to have bought before a release was public.
- BreakTheBank, BrotherObama, paperclip-maxxer, dromedaryy, Kettle, borntoolate.eth, uma003, Bertapotamous: the money is
  in other categories or the account was idle in the screen week.
- xtxpleasecallme (49% rebates), Lolakis (37%), ArmageddonRewardsBilly (80%), cigarettes, Haradwaith, hfv, NotJump,
  a5533, HoshinoAI, Digital-Boy, AntEating, zhaocaimao8888: rebate / reward accounts, mostly non-finance.
- Tokor (+76K / +713K / +454K, 2,706 markets): 80% crypto price markets in the screen week, 17% finance hit markets.
  Belongs to the crypto study; not looked at here.
- 033033033, pvc975, pelik, Malfunction., thegreengem, Shirtybonds: 0.999 buyers with fills of $0.4-9K; the same
  mechanism as CoinTrick with more capital. One representative was enough.
- suohasuo (IPO valuation buckets, 37% rebates, 25 markets a week) and Stonktrader / Jensen4ever (mostly non-finance
  on inspection): left out for budget.

## Tool totals against the "API says" line (14-day wallet tool)

| Account | Tool net | API kept | Explanation |
|---|---|---|---|
| grasstoucher69 | 25,766 | 64,690 | Disagree. 339 markets unresolved and 140 "incomplete" (merges of inventory bought before the window). Own accounting over 21 days: resolved +59.6K, open positions marked at gamma prices +13.7K |
| thanksforplayin | -1,153 | 12,205 | Disagree, not fully explained. 363 redeems in the window, 168 of them in markets with no fill in the window (positions opened earlier). Own 21-day accounting: resolved +8.0K, open -4.1K. Its window result comes largely from positions we do not see being opened |
| superstonksbro | 28,072 | 32,687 | Agree (14%) |
| C03B | 4,604 | 8,037 | 27 unresolved markets; 21-day: resolved +4.4K, open +7.1K |
| CoinTrick | 13,576 | 12,613 | Agree |
| Hauchn | 220 | 15,875 | Everything unresolved (month-end market-cap markets); marked +12.3K |
| PippiTrader | -18,486 | -21,983 | Agree (16%) |

## The accounts

### grasstoucher69 (0x982a77e7...) — buyer of cheap outcomes on both sides, long volatility

What it trades (21 days, `types_trio.txt`): 13,873 fills, 1,945 markets, $443K: hit-month $132K, hit-week $88K,
up/down-day $56K, close-day $28K, close-month $27K, close-week $11K, plus $92K of crypto daily price ladders.
91-100% buys, 34-55% maker, median price 0.13 (close-day), 0.23 (up/down), 0.5 (hit). Trades around the clock:
daily markets 45-47% pre-market, 12-26% night. No fill after a market's end.

Result by type on resolved markets: up/down +19.4K (35% of turnover, t 2.6 by market), hit-week +16.2K (t 2.0),
close-day +11.8K (t 1.2), hit-month +10.0K (t 1.3). Wins 38-49% of markets. By ladder (`ladders.txt`): 429 resolved
ladders, +52% on cost, t 3.3, wins 45%, top 3 ladders give 36% of the profit.

Structure: bought both outcomes in 599 of 1,945 markets; 122.7K paired shares at an average pair cost of 0.837 =
$20.0K locked before fees (1,115 merges). The two legs are bought at different times after the price has swung, not at
once. Across strikes the book is NOT hedged: worst-case payoff is 11% of cost, 76% of cost sits in ladders whose
worst case is under 5% of cost, 0% in ladders locked above cost. So it is not a cross-strike arbitrage.

Model (`model.txt`, 6,960 fills with a reference bar under 15 minutes old): buys 4-5 cents under the lognormal fair
value both as maker (+5.2c) and as taker (+4.3c, fee 0.6c); realized +8.5c a share on taker buys (t 2.4), +1.6c on
maker buys (t 0.7). Measured against the previous regular close its buys look 8-16c cheap, more than against the
price at the fill: it buys the side the underlying has just moved AGAINST (dip buying below fair), the opposite of
sniping a stale quote. Exception: 270 taker fills in the post-market session ($10.4K) where the edge is larger at the
fill (8.8c) than 10 minutes earlier (5.4c) or at the close (3.2c), realized +22c (t 2.4): that small part does look like
taking stale quotes after an after-hours move.
By price: taker buys at 0.15-0.45 earn +20c (t 3.4); buys at 0.70 and above lose 3-9c.

Falsification 1 ("it buys after the outcome is decided"): 55 buy fills ($1,699) at/after the Yahoo deciding time against
8,533 ($261,026) before; model "decided" share 0.2-0.8% of dollars. Rejected.
Falsification 2 ("the edge is direction-free", `g3.txt`): bearish buys +62.5K (65% on cost, t 4.8, 656 markets), bullish
buys -15.8K (-22%, t -2.3, 829 markets). By week: +26.4K, +30.6K, -10.3K. The claim fails in this window.
Falsification 3, earlier window Sep 25-Oct 16 (`altwin_sep22_oct13.txt`, 22,318 resolved buys, 2,391 markets): +48.4K
(6.3% of $766K, t 3.1); bearish +94.1K (t 5.1), bullish -45.7K (t -2.7). Dollars were split 52/48 between the sides,
so it is not betting on direction; it holds both tails and the falling side paid. NVDA went 224.6 -> 214.1 in that
window (SPY -0.5%), so this is not an independent regime either.
Control: PippiTrader shows the same sign pattern (Nov: bearish +14.1K, bullish -27.8K) and the same model edge at the
fill (+3-4c) while losing 10c a share. The model cannot tell the winner from the loser; what differs is price level
(Pippi buys 0.45-0.70, grasstoucher 0.05-0.45) and the bearish share of dollars (36% vs 57% in November).

- Mechanism: systematic maker+taker buying of low-priced outcomes on both sides of every ladder, hold to settlement,
  merge pairs. Model / volatility edge and liquidity provision, not a time gap.
- Time gap: none in the main book; a possible after-hours one in 4% of its dollars.
- To copy: a live reference price per ticker (Nasdaq `info` or Yahoo, REST polling is enough: holding period is hours
  to days), a fair-value model, order management across several hundred markets, merge transactions. Fills are $26 on
  average, median market turnover $31, so the ticket size fits a small account; it runs ~1,500 markets per two weeks,
  which a few hundred dollars cannot diversify (10-20 positions at a 45% win rate).
- Fee: 0.05 on the taker half (0.5-1.2c a share at its prices), 0 on the maker half.
- Capacity: it turns over about $17K a day in finance markets (commodities included) against about $126K a day of
  total volume in the equity ladders we could measure; it is already one of the largest participants.
- Risks: a quiet or rising month (its bullish half loses 12-22%), May 2026 was its only losing month (-1.7K);
  Pyth-vs-quote differences at strikes; the edge may simply be the 2026 autumn sell-off.
- Confidence: 4 that this is what it does, 2 that it is a durable edge.

### thanksforplayin (0x38d812af...) — two-sided discretionary-looking ladder trader, regular hours

4,838 fills, 677 markets, $309K in 21 days: close-day $88K, up/down $83K, hit-month $43K, hit-week $34K, close-month
$25K, market-cap buckets $14K. 51-74% buys, the rest sells (it exits before settlement), 44-84% maker, 72-86% of
dollars in regular hours; 20% of its close-day dollars in the last hour. Pair cost where it holds both sides 0.977.

Result on resolved markets in the window: +8.0K, of which hit-month +8.2K (20 markets, t 2.0), up/down +4.7K (t 1.6),
close-day -1.4K, hit-week -3.4K; open positions -4.1K. By ladder: 246 resolved, +1.6% on cost, t 0.1. Model edge at
the fill about +1c on buys, -5c on taker sells. Nothing in this window identifies an edge.
Earlier window (Sep 25-Oct 16): resolved buys +45.3K on $172K (t 2.3, 753 markets), again all bearish (+47.2K) at
prices under 0.45 (+44.3K, t 2.6); sells not included in that table.
Falsification ("buys after the decision"): 6 of 2,578 buy fills. Rejected. In the last 5 minutes before the close it is
the largest LOSER among takers (22 fills, $3.5K, -$1.1K).

- Mechanism: cheap-side buying like grasstoucher69 with active exits; mostly a person or a semi-manual tool in US hours.
- Time gap: none found. Model edge: not shown by our yardstick.
- To copy: nothing specific to copy. Monthly record (10 positive months, +14K to +58K, 4-10% of volume) says there is
  something; 21 days of fills do not show what.
- Confidence: 2.

### superstonksbro (0x969fae0a...) — directional swings, regular hours only

2,307 fills, 407 markets, $214K: hit-month $110K (51%), close-month $29K, close-day $28K, hit-week $24K. Buys only,
65-84% maker (36% in close-week), 99-100% of dollars in regular hours (a person). Uses a buy of the opposite outcome plus a merge as its
exit: pair cost 1.066, i.e. it pays to get out. Close-day: 30% of dollars in the last 10 minutes.

Result: resolved +28.3K, of which hit-month +21.2K on 35 markets (t 2.1); by ladder +11% on cost, t 0.7 (135 ladders).
Model edge at the fill is negative (-1 to -3c); realized is positive because the bets were right: bearish +23.6K
(t 3.3), bullish +2.4K. Earlier window: -27.6K on $231K (t -2.7), bullish -26.3K. Monthly: +130.9K (Mar), -124.4K
(Jun), -38.6K (Oct).
Falsification ("buys after the decision"): 19 of 2,208 buy fills. Rejected.

- Mechanism: a directional view on large caps expressed through monthly hit markets. Not a time gap, not a model.
- To copy: nothing. Confidence: 2 (that it is direction; the rest is not knowable from fills).

### CoinTrick (0x731a2417...) — buys what is already decided, minutes before resolution

5,636 fills, 1,996 markets, $4.57M in 14 days across all categories (sports $2.40M, finance $0.92M, crypto $0.61M);
71% maker; 95% of dollars at 0.99-1.00. Kept 0.27% of volume; monthly positive since February (+2.7K to +37K, +182.6K
in October). Finance has the best margin: 0.8% of turnover against 0.1-0.5% elsewhere.

Finance, 21 days (`bond.txt`, `extra.txt`): 1,336 markets, resolved net +$7.3K, 4 losing markets worth -$105 in total
(the largest, -$94, is a 0.023 lottery ticket, not a bond). Equity price ladders: hit-week 776 markets, $147K at
0.9962, +$549; close-day 149 markets +$100; up/down 123 markets +$35; close-week 126 markets +$3. Median time from its
fill to the market closing: 0.3 hours.
Order test on equity ladders (`stories.txt`): 918 fills ($181,855) at/after the Yahoo deciding time against 160
($43,675) before; the 160 are a median 20.6 sigma from the strike or on the minute boundary; 0 lost. Delay decision ->
fill: p10 5 s, median 120 s, p90 829 s; fill -> on-chain resolution median 17 minutes. The explanation holds.
But the money is elsewhere: top five markets = $5.7K of the $7.3K, all Anthropic IPO / valuation markets bought at
0.95-0.99 (e.g. "valuation hit (LOW) $1.0T": 72,943 shares at 0.962 on Nov 25 14:44 - Nov 26 04:32 UTC after the
stock opened at 76 and the market jumped from 0.92 to 0.99; resolved Nov 26 05:13; +$2,795).

- Mechanism: pays 0.95-0.999 for outcomes that are decided but not yet paid out; half as resting bids that impatient
  holders sell into, half by lifting asks.
- Time gap: decision -> payout. 16 minutes on Pyth ladders (discount 0.1-0.4%), 7-15 hours on event markets resolved by
  a proposer (discount 1-5%).
- To copy: on Pyth ladders a live price feed and being first at the touch; the whole pool there was $889 of discount in
  21 days over 1,323 markets and three wallets took most of the taker part (0xc4b5a673 $414, CoinTrick $227,
  0x31fed1eb $107). On event markets: reading the rule text and the source correctly, and capital (its tickets are
  $5-130K).
- Fee: 0.01-0.2 cents a share at these prices. Capacity for us: cents per market on ladders. Risk: one wrong reading of
  a rule costs 20-100 winning trades; we did not see a loss in 1,332 resolved finance markets, which says the losses
  are rare, not that they are absent. Confidence: 4.

### C03B (0x40604cb1...) — larger tickets, a mix of decided outcomes and near-certain carry

563 fills, 94 markets, $691K in 21 days; $1,157 a fill; 58% maker. Finance $320K, also tech, culture, crypto. Monthly
+13.6K to +94.7K since May on $0.9-5.3M of volume (kept 0.7-6% of volume, about 1.5% in Sep-Nov); volume fell from $5M to $1M a month.
Buys at 0.90+: market-cap markets $95.6K at 0.983 (2.8 h to close, +$1,563), hit-month $82.1K at 0.979 held a median
182 hours (79% maker; commodities and Anthropic valuation: this part is carry, not a decided outcome), index up/down
$50.5K at 0.9986 after the close, IPO markets $27.0K at 0.976. Resolved net +$4.6K in the window with 10 losing markets
worth -$3.1K (largest -$1,206 and -$646: wrong-side fills minutes before a close), top five +$6.8K. In equity ladders
it only does last-minute lock-ins (5 fills, $321, 1.6-2.1 sigma from the strike, 0 lost; 13 taker fills in the last
5 minutes for +$214).

- Mechanism: bond buyer with judgement: decided-but-unpaid outcomes plus weeks-long holds of 0.95-0.99 favourites.
- Time gap: partly decision -> payout (hours); partly none (tail risk for yield).
- To copy: capital and rule reading; not a small-account business (0.2-2.5% per trade on $5-95K tickets).
- Confidence: 3. Rests on 62 resolved markets.

### Hauchn (0xf0ca28d5...) — concentrated relative-value bets on the mega-cap ranking

387 fills in 25 markets in 21 days, $162K, 84% taker, 56% of dollars pre-market. Almost everything is two positions:
NVIDIA NOT the largest company on Dec 31 (75,798 No at 0.841) and Apple the largest (61,439 Yes at 0.830), plus
smaller rank markets. All unresolved; marked +12.3K. Monthly result swings between -46.7K and +214.2K.

- Mechanism: a view on which mega-cap is first by market cap at a date, traded in 20 markets; possibly computed from
  pre-market quotes, but two positions cannot show that. Not systematic in the sense of the brief. Confidence: 2.

### PippiTrader (0x403f2471...) — control: the liquidity the winners trade against

12,363 fills, 1,882 markets, $296K in 21 days in the same ladders. Two-sided, 37-68% maker. Resolved net -19.5K
(hit-week -12.4K, t -5.1); taker buys at 0.45-0.70 lose 17c a share (t -4.0). All-time kept 114.6K of which 78.6K is
liquidity rewards; rebates and rewards were 16-30K a month in July-October and 1.8K in November, and November is -23.5K.
The reward program on these markets is gone (`clobRewards` null), and with it the reason to quote them naively.
Confidence: 4.

## Market-level tests (independent of any account)

Universe: price markets on equity/ETF tickers touched by at least one of the seven accounts, resolved
(1,212 hit-week, 486 close-day, 237 up/down, 226 close-week, 197 hit-month); whole-market tapes in `cache/tapes/`.

| Test | Result |
|---|---|
| G1 stale takes after a touch (547 hit markets with a Yahoo touch 10 bp beyond the strike) | 74 takes, $1,185 net: 0-10 s $0; 10-60 s $47; 1-5 min $0; 5-60 min $309; over 1 h $828 (mostly one AMZN market 3 days "after" the Yahoo touch: proxy mismatch). Only 109 of 547 markets printed at >= 0.99 after the touch at all; median delay to that print 129 s |
| G2 trades after the session close (723 close / up-down markets) | 168 trades, $9.8K, taker net -$50; median 151 s after the close, all at 0.99-0.999 |
| Last 30 minutes before the close (564 markets, 2,031 taker fills, $91K) | takers net +$2.3K at 5-30 min (t 1.4), -$1.0K at 1-5 min, +$61 at 10-60 s, +$80 in the last 10 s. Fills on the model side when the price is >= 2.5 sigma from the strike: 93 fills, $3.4K, +$254, 2 losers |
| Post-decision discount pool (1,323 markets) | winning outcome traded at >= 0.90 from decision + 60 s to resolution: $76K of volume, $889 of discount ($469 at 0.90-0.97, $330 at 0.99-0.995) |
| Calibration of our model on first fills (2,164 market-outcomes) | fair 0.04 -> won 0.088 (price 0.051); 0.15 -> 0.180 (0.121); 0.25 -> 0.344 (0.227); 0.75 -> 0.628 (0.749); 0.84 -> 0.749 (0.815). Cheap outcomes won more often than both the model and the price said, in this sample of this month |

## Sampled market stories

`stories.txt` has 14 markets per ladder account, taken evenly through each account's PnL ranking (worst to best, not
hand-picked), and 14 + 5 of the largest bond fills. A few:

- grasstoucher69, best: "SPY closes above $725 on Nov 19". Bought No 7,502 shares at 0.028 (16 of 26 fills as maker)
  between 10:59 and 13:28 UTC with SPY at 739 (1.9% above the strike), model fair 0.06. SPY closed below 725. +$7,285.
- grasstoucher69, worst: "SpaceX (SPCX) hit (HIGH) $130 in November". Bought No 5,678 at 0.451 on Nov 25 with the stock
  at 122-127; touched Nov 27 14:31 UTC, resolved 14:47. -$2,626.
- grasstoucher69, typical: "NVDA close above $185 on Nov 9": No 7 shares at 0.82 and Yes 83 shares at 0.122 six hours
  before the close with NVDA at 175-179; lost $9. "TSLA hit (LOW) $352.50 week of Nov 9": No 100 at 0.52, 102 hours
  ahead, model fair 0.52; +$47.
- thanksforplayin, best: "SPY closes above $760 on Nov 11": No 8,146 at 0.093 between 15:27 and 20:53 UTC with SPY at
  756-760, sold 503 at 0.49 on the way; +$7,125. Worst: "AAPL Up or Down on Nov 6": Up 3,891 at 0.222 in the last 75
  minutes with AAPL 0.1-0.3% below the prior close; -$866.
- superstonksbro, worst: "NVDA hit (LOW) $168 in November": No 3,572 at 0.612 on Nov 6 with NVDA at 188; touched Nov 10.
  -$2,160. Best: "NVDA hit (LOW) $128 in November": Yes 13,827 at 0.394 between Nov 16 and Nov 20 while NVDA went
  159 -> 130; touched Nov 20 19:53 UTC. +$8,254. A directional call that was right.
- CoinTrick: "PLTR hit (LOW) $159 week of Nov 16": Yes 7,143 at 0.993 as maker 3 minutes after the touch, resolved 13
  minutes later (+$50). "AMZN close above $255 on Nov 17": Yes 4,995 at 0.999 at 21:16 UTC, resolved 21:16 (+$5).
  "NVDA hit (HIGH) $168 in November": Yes 4,129 at 0.947 about half an hour before the Yahoo touch with NVDA at 167.04
  (a near-touch bet, +$218).
- C03B: "NVDA close above $165 on Nov 12": Yes 140 at 0.9495 one minute before the close with NVDA at 165.84.

## What was run (every variant, including the broken ones)

1. `screen.py` once (regex classifier is crude: "fin-other" swallowed sports titles with tickers in brackets; used only
   to shortlist).
2. `python3 -m pmlab.wallet` x 7 (14 days, none truncated) and `wallet_check.py --monthly` x 7.
3. `types_table.py`: two runs. The first iterated fills newest-first and flagged 146 of 186 thanksforplayin close-day
   markets as "incomplete" (wrong); fixed by sorting by time and using net shares; rerun for the two-sided accounts.
4. `ladder.py` once (pairs inside a market, worst/best payoff per ladder).
5. `model.py` once: sigma = 60 daily returns (includes days inside the window: a mild look-ahead in sigma only),
   regular hours carry 70% of a day's variance, reflection formula for hit markets. No parameter was tuned.
6. `gap.py` G1 and G2: one variant each (first launch crashed on titles without a strike; no result was seen).
7. `closewin.py` one variant (thresholds 3c and 2.5 sigma fixed in the script before the run).
8. `g3.py` once; `altwin.py` once on one earlier window (chosen before looking: three weeks ending six weeks back).
9. `bond.py`, `stories.py`, `niche.py`, plus two ad-hoc listings (`extra.txt`, `anthropic_bond.txt`).

## What could not be checked

- Pyth candles: no history, so deciding times are Yahoo's. Anything inside one minute or a few cents of a strike is
  unverified, including whether the last-minute candle close differs from what quote screens show.
- Commodities, DXY, Nikkei, natural gas and SPCX-like tickers are in the fills but not in the model or gap tests
  (session hours and spot-vs-futures basis). That is 35-40% of grasstoucher69's hit-month dollars and most of C03B's.
- What was AVAILABLE on the book: tapes show what was taken. A stale ask nobody lifted is invisible here.
- Whether the tail edge exists in a rising or quiet month: both windows fell. Fills older than about two months for
  these accounts were not pulled.
- Reversal rate of "decided" event markets in finance (the real risk of the event bond).
- thanksforplayin's window profit is not reconciled with its fills.
- Option-implied odds: no free option chain answered from the sandbox.
