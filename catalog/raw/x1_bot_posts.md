# X1 — X/Twitter "someone built a bot and made $X on Polymarket" posts, traced to the wallets

Researcher notes, 2026-11-27. Window: 2026-09-01 .. 2026-11-27 (a few late-August posts kept because the same wallets recur).
Full number tables: `catalog/raw/x1_wallets.md` (Table 1 = 72 unique wallets, Table 2 = 135 post-wallet pairs).
Raw material (git-ignored): `data/x1/RetroValix.jsonl`, `data/x1/tl/<handle>.jsonl` (timelines via the fxtwitter mirror),
`data/x1/thumbs/` + `data/x1/sheets/` (video posters and contact sheets), `data/x1/w2/*.v2.json` (per-wallet stats, monthly, tiers),
`data/x1/table_all.txt`. Helper scripts I wrote: `research/2026-11-27-x1-bot-posts/` (timeline dump with cursor resume, wallet summary
using fees net of refunds, fill sampler, table builder).

Everything below that is a number about a wallet was pulled by me today from the public Data API. Everything in quotes is from the post.
Posts are untrusted advertising; nothing in them was executed or followed.

## 0. Bottom line

1. The genre is an advertising format. Eight X accounts were read; six of them carry an affiliate link in practically every post
   (Polymarket `?via=` referral codes, horizon.trade, PolyGun Telegram bot, ratio.you, gravia.trade, KCEX). The dollar figure in the
   headline is always the profile's Profit/Loss (`trade_pnl`), i.e. before taker fees.
2. @RetroValix published 71 Polymarket "bot" posts between 2026-08-29 and 2026-11-26. They cover only **27 wallets**, recycled every
   2-4 weeks under a new invented system name ("Quant Kalman Repricing", "Quant Tree Turnover", ...). The formulas in the Nov posts
   (HAR volatility, gradient trees, Theil-Sen, copulas) are decoration: the same wallet gets a different "model" each time
   (pspspsps5 was "directional + dynamic hedge" on Aug 30, "Quant Tree Turnover" on Nov 25; bosona was "limit maker", "Quant Signature
   Map", "Quant Probit Inventory"). The author's own article (2026-10-24) says: "This is a reconstruction ... The exact indicators remain unknown."
3. Of the 27 RetroValix wallets, after fees and **without rebates**:
   - clearly positive and still positive in Nov 2026: **almach, bosona, mo-money** (one operator, ~97% maker fills, +57K..+91K each in Nov
     without rebates), **0x50f7** (96% maker, bids at 0.97-0.99, +17K in Nov, fading from +177K in June), **0xDB5** (crypto daily
     strike/range markets, +27K in Nov), **BoneOhio** (+16K), **pspspsps5** (+9K, fading), **x-MoneyForWhiskas** (+10K, fading), wzbbb (+9K);
   - positive lifetime but dead or near zero by Oct-Nov: PBot-6, aswfadq1555, nagi777, antsaslyku, NIULAI4 (Nov -4K), 98euf98a,
     flippingsharks, hot-garbage, norm1e69 (stopped trading in Nov), trinity42, std0, Jarvisen;
   - negative without rebates (live on volume-tier rebates): **Bonereaper** (-150K lifetime, rebates are 128% of what it kept),
     **Polkadot-Frog** (-119K, 198%), **0xAAAAA** (-83K, 229%; stopped trading at the end of August and was still advertised on
     Sep 4 and Sep 24), **0xb55fa129** (-40K, 107%; -63K in Nov), **0xcE25E214** (-17K; advertised on Nov 9 as "made $3,634 a day"
     while its Sep/Oct/Nov net was -0K/-3K/-5K), nj23adsknml3 (-3K).
4. The wallets that make money without rebates are overwhelmingly **makers** (resting buy limits, zero fee), not latency takers.
   The "speed / latency edge" wallets the posts celebrate (nj23adsknml3, 0xAAAAA, Bonereaper, trinity42, norm1e69) are the ones that
   are negative or flat after fees. This agrees with the lab's own tape study (takers lose, makers earn).
5. Things worth taking apart next (real, checkable, positive without rebates, and not a pure speed race):
   - **0x5268527977f700f9bf9b6d5cd843859e4e70135d** — sports spreads/totals, 81% maker, buy-only limits at 0.2-0.8; NET 5.08M, 3.87M without
     rebates; Aug-Nov net +1,189K / +85K / +1,521K / +957K. The post describes "sportsbook fair price, bid slightly below".
   - **Tokor** (0xa19cba…) — crypto daily/weekly strike markets ("bitcoin above X on Nov N", "will bitcoin dip to X"), 95% maker,
     NET 1.34M, rebates 2%, Oct +713K, Nov +454K (low-fee category: rate 0.01).
   - **0xDB5** — same category, two-way (buys and sells), 60% taker, +27K in Nov.
   - **almach / bosona / mo-money** — BTC 5m passive maker, 3.2-3.7% of volume kept; the question is how they avoid being picked off.
   - **0x50f7 / pspspsps5 / BoneOhio** — resting bids at 0.97-0.99 on the nearly decided side of 5m markets ("resolution bond" in miniature),
     plus 1-3c tail tickets.
   - **Vega7** (0x6ba25c…) — 100% taker, only buys at <=3c..20c in BTC 5m, ~17 fills a day, $0.1M lifetime volume, NET 44K,
     +14K/+10K/+11K in Sep/Oct/Nov. Tiny capital, no rebates, negligible fee at 1c. The cheapest thing in this file to test.
   - **0x0dbd0e1d5999a401263dc26cbf1597f2be0cfcd5** — new wallet (joined 2026-11-02), alt-coin up/down (DOGE, ETH, BNB, SOL, XRP), 66% maker,
     +63K without rebates in its first 25 days.
   - **Bilberry** (weather, forecast-update repricing, 50 cities) and **hello.67 = 0x2e3ecede…** (weather taker): real but fading
     (Bilberry Sep +34K, Oct +11K, Nov +3K; hello.67 Oct +61K, Nov +1K).

## 1. How the wallets were identified

`python3 -I tools/xread.py timeline RetroValix --since 2026-09-01 --pages 40 --grep polymarket` stopped with a 404 at the Oct 19 cursor,
so I dumped the timeline with my own retrying copy (`research/2026-11-27-x1-bot-posts/tl.py`) back to 2026-08-28: about 108 posts, 71 about
Polymarket bots (the rest: Solana token scanner "QuantumOrb", "AI office with Grok Bot", a KCEX exchange ad).
Only ~8 of the 71 posts name the account in a link; the others say "His Polymarket nickname: X" (all of them do name it in text) and the
video poster shows `WALLET 0xAAAA…BBBB · name`. I downloaded all 71 posters, cropped the header, built six contact sheets
(`data/x1/sheets/s_00..05.png`) and read the names; every name resolved via gamma `public-search` to an address whose first/last
hex digits match the poster. Then per wallet: `user-stats`, `user-pnl?interval=all&fidelity=1d` (monthly deltas), `/tiers`, maker tier.
For 19 wallets I also pulled the last 1,000 fills twice (`taker_only=false` and default) to get maker share, price buckets and market
families (`research/2026-11-27-x1-bot-posts/tr.py`).

Caveat found while doing this (already recorded in NOTES.md by someone else the same day): the API has `fees_refunded`; fees charged
in Jan-Apr 2026 were partly refunded (zero refunds from May 2026 on in all 72 wallets). I use `fees_paid` and `economic_pnl` deltas everywhere. "Net without rebates" = `economic_pnl` minus
(taker_rebate + maker_rebate + reward_income + referral_income).

Operator clusters: gamma `/tiers` returns the same `wv_30d` for wallets in one group, which exposes common ownership:
- Diamond 4,471,870: x-MoneyForWhiskas, dangerously-skip-permissions, GoodFallen, FairValueMachine (combined NET 1,102K; without rebates 487K).
- Diamond 4,583,181: Bonereaper, wzbbb. Platinum 3,244,556: 0xb55fa129, 0xcE25E214. Platinum 2,609,805: BoneOhio, PBot-6, antsaslyku.
  Gold 348,873: ply-pm0, ply-pm2.
- almach, bosona, mo-money: not tier-linked, but same monthly curve, same volume ($17.0M / $17.0M / $17.5M), same maker rebates
  (62K / 62K / 64K), same rewards (4.7K each); almach and bosona joined the same day (2026-05-21).
So "hundreds of trading bots like this" is mostly a handful of operators running several wallets each.

## 2. Sources, one by one

### 2.1 @RetroValix (the account that brought us here)

- Format: daily post, video dashboard, "This guy used Grok Bot / Claude Fable 5.1 to build a Quant <Name> system and it made $N a day".
  Views 2K-1.5M (2026-11-25 post on pspspsps5: 1,500,509 views, 7,411 bookmarks).
- Articles:
  - 2026-08-24 "The Most Profitable Trading Bots on Polymarket Right Now", https://x.com/RetroValix/status/2091951419989573990
    (2.65M views). Describes Bonereaper ("Directional Rotation with Dynamic Hedge"; both sides in ~55% of 5m markets, median 26 s between
    first entries, combined average price of Up and Down ~$1.08: "This means it is not complete-set arbitrage. The bot pays for the hedge"),
    0xb55... ("Asynchronous Complete-Set Accumulator"; both sides in ~75% of markets; median gap 52 s on 5m, ~3 min on 15m; median
    combined price ~$0.93 on 1h and ~$0.91 on 4h markets), mo-money ("Multi-Timeframe Hybrid"; 5m: both sides in 32%, set cost ~$1.07;
    1h: balanced, median VWAP sum ~$0.91), almach ("Buy-Side Inventory Builder"; passive BUY orders at several levels; 1h markets: smaller
    side ~96% of larger, combined ~$0.97; 4h ~$0.99). Useful as a description of what the tape looks like; the "edge" paragraphs are guesses.
    My check: Bonereaper and 0xb55 lose money after fees without rebates; mo-money and almach do not. The article does not distinguish them.
  - 2026-10-24 "HOW TO BUILD A TRADING BOT ON POLYMARKET", https://x.com/RetroValix/status/2114066681098355051 (2.1M views). An
    advertisement for horizon.trade ("tested over 250 strategies in Horizon", link join.horizon.trade/build appears five times). Says
    x-MoneyForWhiskas "posted +$624,300 PnL in four months ... approximately +$156,075 a month", average gap to $1 "2.07c per pair before
    costs". My check: the wallet kept 427K in total, 58% of it rebates; its best month kept 129K (Sep), of which 29K without rebates;
    Nov so far 20K (10K without rebates). The article admits "The exact indicators remain unknown" and that the Horizon backtest is of a
    made-up ROC/ATR momentum signal on BTC, not of the Polymarket strategy.
- Mechanisms as described per wallet (first description; later posts only rename it) and what the fills say:
  - almach (Aug 29, Sep 29, Oct 20, Nov 12): "passive market making, complete-set accumulation, directional residual ... average cost of
    its complete sets is 96.73c ... 81% of inventory paired", 150 trades per active hour, avg trade $33.50. Fills today: 97% maker,
    buy-only, BTC 5m (92%) plus hourly/daily, 45% of dollars at 0.2-0.8 and 47% at 0.8-0.97. NET 550K, 14% rebates, Nov +98K (+87K without).
  - mo-money (Oct 4, Nov 15; also Dan1ro0 Oct 30, igor_mikerin Nov 5): "directional + dynamic hedge + complete sets". Fills: 97% maker,
    buy-only, BTC 5m. NET 643K, 12% rebates, Nov +102K (+91K). The post's claim "+$470,883" was below the poster's own number (445K): sloppy.
  - bosona (Sep 4, Sep 30, Oct 23, Nov 13; Dan1ro0 Oct 31, Nov 15, Nov 26): "limit maker, async set builder", "$20K deposit" on the
    poster. NET 541K, 14% rebates, Nov +70K (+57K).
  - 0x50f7 (Nov 18; Dan1ro0 Nov 12; igor_mikerin Oct 26 and Nov 18): RetroValix: "Required Speed = Gap / Seconds Left ... Favorite Limit =
    $1 x (1 - Tail Probability) - Costs - Buffer; Tail Limit = $1 x Tail Probability - Costs - Buffer ... A tail may be valued at 4c ... the buy
    limit is 3c", avg trade $216, "98.48% of volume at >=90c" on the poster. igor_mikerin: "buys the side nobody believes in and hopes for
    30x, or buys the side that's basically done and takes 1% ... 1c and 99c buys back to back"; best trade "$156 -> $13,450". Fills: 1,000
    fills in 20.6 h, all BUY, 100% of dollars at >=0.97, 96% maker, BTC 5m 80% / ETH 5m 20%. NET 602K on $91.8M volume (0.66%), rebates 3%,
    fees paid 66K. Monthly net Apr-Nov: 80 / 39 / 182 / 138 / 31 / 55 / 48 / 18 (K): fading. No volume tier (Tier 0).
  - BoneOhio (Sep 5, Oct 1, Oct 21): "late-resolution strategy ... records the reference price and tracks Chainlink TWAP along with external
    spot/perp feeds ... increases the position as the outcome gets closer to certainty ... in 88.2% of markets it trades only one outcome".
    Poster: "buys at 0.98-0.99", "single-sided 88.2%". Fills: 81% of dollars at >=0.97, 26% taker, BTC/ETH/XRP/SOL/DOGE/HYPE. NET 388K;
    without rebates 285K lifetime (of which 305K is the Mar-Apr fee refund), Aug-Nov without rebates +78K / +26K / +31K / +16K.
  - pspspsps5 (Aug 30, Sep 26, Oct 18, Nov 2, Nov 25): described as "directional entry then hedge 52.5 s later, never sells, VWAP U+D 0.946".
    Fills: 100% maker, avg fill $5.9, 63% of dollars at >=0.97, BTC 61% / ETH 39%. NET 315K, 9% rebates; Jul-Nov +63 / +56 / +32 / +30 / +10.
  - PBot-6 (Sep 8): "places BUY orders below its fair value in advance and gets most of its fills at 50c or less". Fills: 100% maker, all
    at 0.2-0.8, ETH/BTC/SOL/XRP/XAU 5m. Without rebates: +56K Jun ... +15K Oct, +2K Nov. Same operator as BoneOhio and antsaslyku.
  - NIULAI4 (Oct 3, Oct 19, Nov 14; igor_mikerin Nov 7): "98.2% of its purchases occur in the final minute; median first entry 56 seconds
    before the end; 89.8% of fills at 50c+; more than half at 80c+ (65.9% of volume); both sides in 29.55% of markets; win rate 81.42%".
    Fills today: avg $2.1, 18% taker (so mostly resting bids in the last minute), BTC 5m only. NET 114K, Aug-Oct +47 / +30 / +38, **Nov -1K
    (-4K without rebates)** on higher volume: the edge went away in November (fee/rebate change on Nov 20 and/or competition).
  - 0xDB5 (Oct 15): "BTC and ETH markets ... buys Up or Down in small amounts ... can sell part of its inventory ... bought both sides in 71.6% of
    markets". Poster says "BTC / ETH daily". Fills: NOT up/down 5m at all: "will the price of bitcoin be between", "bitcoin above Nk on
    november N", "ethereum above", "will bitcoin reach / dip to"; 60% taker, 38% sells. Trading since Jan 2025. NET 209K, 14% rebates,
    Jul-Nov +24 / +10 / +10 / +9 / +31.
  - nj23adsknml3 (Sep 6, Sep 27, Oct 31): "The main edge ... comes from speed. It tries to detect changes in fair value on external crypto
    markets before they are reflected in Polymarket prices", 516 trades per active hour, avg $8.13, poster "ROI 5,450% on a $4.6K deposit".
    Wallet: gross 251K, fees paid 254K, rebates 53K, NET 50K, **without rebates -3K**; volume fell to ~0 in Oct. The post on Oct 31
    still said "+$250,750".
  - 0xAAAAA (Sep 4, Sep 24): "directional trading, latency edge, dynamic hedging ... Chainlink reference". Gross 300K, fees 383K, NET 64K
    all from taker rebates (148K); zero volume since September.
  - Bonereaper (Sep 10, Oct 6; Dan1ro0 Oct 29): "+$1,365,350 ... directional repricing, dynamic hedging, near-resolution". Gross 1,467K,
    fees paid 1,617K, rebates 680K, NET 531K; without rebates -150K. $170M volume. Diamond tier.
  - x-MoneyForWhiskas (Aug 31, Sep 25, Oct 17, Nov 6; Dan1ro0 Oct 26): see NOTES.md; NET 427K, 58% rebates, fading.
  - the rest (hot-garbage, trinity42, antsaslyku, std0, Polkadot-Frog, aswfadq1555, norm1e69, 98euf98a, nagi777, Jarvisen,
    flippingsharks, wzbbb, 0xb55fa129, 0xcE25E214): numbers in `x1_wallets.md`. Pattern: best months were Jun-Aug 2026, steep decline
    from September (after the Aug 7/14 TWAP settlement change and the Aug 17 taker delay), near zero by November.
- What RetroValix sells (affiliate links seen in the posts): `polymarket.com/@<name>?via=670` (Polymarket referral), `join.horizon.trade/retrovalix`
  and `/build` (strategy-builder SaaS, "Builder" plan), `t.me/PolyGunSniperBot?start=ref_Valix` (Telegram copy-trading bot),
  `ratio.you/r/SFWM9FFJ`, `kcex.com/register?inviteCode=...` (exchange), `gravia.trade/...?via=valix` (copy-trading), and his own
  `github.com/QuantumOrb/QuantOrb` Solana token scanner ("I made +$4,287.30 in 5 days": not checked, not Polymarket).

### 2.2 @Dan1ro0

- Same template as RetroValix, almost word for word, same wallets, posting since at least 2026-06-27 ("I Analyzed 10M Polymarket Bot
  Trades with Claude", found via WebSearch on youmind.com; not opened). Timeline read back to 2026-10-19 only (33 posts; 26 name a wallet).
- 2026-10-19 article "I Studied 4,700+ Quant Strategies. Here's How to Build Your Own Trading Bot With ..." (1.06M views; title only, not read).
- New wallets vs RetroValix: ply-pm0, ply-pm2 (one operator; NET 86K and 29K, 44-58% rebates), dangerously-skip-permissions, GoodFallen,
  FairValueMachine (the x-MoneyForWhiskas operator), CrouchPredictions (NET 286K, 74% rebates), asdcaxz (NET 31K, 65% rebates),
  blue.birds = 0xb9587c373c773d023f47c2f85a30b3d5bddcf513 (posted twice, Nov 8 as "+$75,469" and Nov 20 as "+$101,923.74 in 46 days ...
  hedge fund track record ... 73.4% of all exposure sits in 90-100c contracts ... P(Up) = Phi[(ln(S/K) - 0.5 sigma^2 T) / (sigma sqrt T)]").
  My check on blue.birds: gross 114K, fees paid 104K, rebates 36K, NET 46K; **without rebates 9K** on $6.8M volume; Nov without rebates +2K.
- Sells: `polymarket.com/@<name>?via=dan-kwpx`, `join.horizon.trade/Quant` ("the first agent that will create a trading bot strategy for you").

### 2.3 @igor_mikerin

- 70 Polymarket posts since Sep 1; one trader profile a day, every one with `?via=igor-mikerin`, plus a long-running "$POLY airdrop"
  campaign ("I'll give you 90% of the airdrop if you sign up through my referral link", `polymarket.com/?r=iic`). On 2026-10-29 he posted
  about the CSV export of his Polymarket affiliate programme (the post mentions "$17M" and "$155,700"; not read in full). The trader descriptions are short but contain the most concrete rules of
  the whole set, and several are about a time gap:
  - 2026-10-10, https://x.com/igor_mikerin/status/2108878693477101880, **Bilberry**: "The market prices the forecast itself pretty well.
    The money is in the gap between a new forecast dropping and the price catching up to it. When a fresh forecast for tomorrow comes out and
    the temperature shifts by 0.5C or more, you buy the option one degree closer to the new number ... The edge holds between 5c and 60c ...
    Open-Meteo ... GFS and ECMWF. Use airport coordinates ... Keep each trade under $25 ... His bot runs this across 50 cities every hour.
    September average was $1,500/day."
    Check: Bilberry 0xbf1393…, 12,071 markets, $1.5M volume, NET 55K, rebates 6%; Aug-Nov net +4K / +36K / +13K / +3K (so September was
    ~$1,200/day, then it decayed 10x). Last 1,000 fills: 70% taker, 33% sells, 55% of dollars at >=0.97 (i.e. more than half of the money
    goes into near-certain buckets: late-day "already measured" trades, not the forecast-update rule), 40% at 0.2-0.8.
  - 2026-10-14, https://x.com/igor_mikerin/status/2110308831515279578, **dgdgt345dfgdf23**: "$700/day on the 5m BTC market ... Polymarket
    prices follow Binance, just a beat late ... if the fair price jumps 20c+ within 5 seconds and goes over 60c, while Polymarket is still
    selling it 10c+ cheaper, it buys that same second." Could not resolve the profile (gamma search returns nothing for that name), so
    unverified. The lab's own measurement (book absorbs a Binance move in 0.5-2 s; naive fair-value taker loses 1-8%) contradicts a
    persistent 10c+ gap.
  - 2026-10-18 and 10-20, https://x.com/igor_mikerin/status/2111821354827686310, **0x5268527977f700f9bf9b6d5cd843859e4e70135d**: "Right
    before a game, the books already know everything: lineups, injuries, where the sharp money went ... you can buy at 52c while the book
    fairly values it at 55c ... Choose a game that starts in 1-3 hours ... convert [odds] with 1/odds ... divide each price by [the overround] ...
    Place a limit order on Polymarket slightly below the fair price and let someone sell into it ... About half of his profit comes before the
    game, the other half he makes live."
    Check: profile name HomeRunHazard, joined 2026-04-23, 58,505 markets, $283.5M volume, gross 5,475K, fees paid 1,603K, rebates 1,210K,
    NET 5,081K, without rebates 3,872K (rebates 24%), Diamond tier. Aug-Nov net +1,189K / +85K / +1,521K / +957K; without rebates
    +887K / -127K / +1,330K / +815K. Last 1,000 fills (17 h): all BUY, 81% maker, avg $190, 99% of dollars at 0.2-0.8; NBA/CBB/NFL/NHL
    spreads and totals. The description (resting bids below a de-vigged sportsbook price) fits the fills. This is the single largest
    verified money-maker in the file.
  - 2026-10-31 and 11-16, https://x.com/igor_mikerin/status/2116595300764639566, **Vega7**: "only plays BTC Up/Down 5-minute markets, and
    only the side everyone already gave up on. The price is 1c or less, the stake is $10-25 ... 1.1c -> $23.74 became $2,239 ... One hit at 1c
    pays for about 90 misses. 10,249 markets later he's up $36.6K"; update: "Since Nov 1 he's added +$6,294. Same 5-min markets, same $16 tickets."
    Check: 0x6ba25c…, joined 2026-04-19, 10,603 markets, volume only $0.1M, gross 47K, fees 4K, rebates 0, NET 44K; Aug-Nov -1K / +14K /
    +10K / +11K. Last 1,000 fills span 58 days (~17 a day), 100% taker, 65% of dollars at <=3c and the rest under 20c.
  - 2026-11-01 **StayFocusLuia** ("buying dead BTC outcomes for pennies, 6,000 markets, up $90K"): NET 83K but Aug-Nov -5K / +6K / -4K / 0;
    inactive since Oct 26. Its money was made earlier.
  - 2026-10-26 and 11-18 **0x50f7**: see 2.1.
  - 2026-10-04 **Happening9014** ("GPT Astra 6 bot ... gap between your probability estimate and the market price ... weather models ECMWF, GFS
    ... $5,000/week"): NET 29K lifetime since 2024, Aug-Nov +3K / -1K / +3K / +2K. The "$5,000/week" is false by an order of magnitude.
  - Weather profiles: windy-weather (NET 27K, ~5K a month Aug-Oct, 2K in Nov), macao.weather (12K lifetime, ~0 now; post said "$500 a day"),
    HellorHeaven (10K; 1-3K a month), BeefSlayer (90K lifetime; +10K / +8K / +6K / 0 Aug-Nov), jjavi (62K, nothing since August although the
    posts of Nov 2 and Nov 4 show single lottery hits), sdllds (3K), terrordogchampion (19K, decaying), emberthespirit (his own "bot":
    headline "$4,000/month" on Sep 21, text "$3,882 in total profit"; wallet shows NET 3K, all in September, ~0 after), **hello.67 = 0x2e3ecedec4b004c61670f0dcda382ec0da1f0f92** (address taken from the profile link in that post)
    ("made $83K in 5 weeks. Now he's giving it back"): joined 2026-10-01, 6,939 markets, 100% taker, NET 65K: Oct +64K, Nov +1K.
  - 2026-09-19 / 09-27 **kneelbeforetheking**, "$500K in trading volume for $0": "buy a YES+NO pair for $1, convert the NO into YES across the
    other outcomes, sell all the YES back ... Fees run about 0.9% per loop, partly offset by rebates" (neg-risk conversion used for airdrop
    volume farming, i.e. wash volume). Wallet: +341K in Sep, -309K in Oct, NET 29K. Not a strategy; shows that part of Polymarket volume in
    multi-outcome markets is airdrop farming.
  - 2026-10-24 "spot insiders before the news drops": points at github.com/pselamy/polymarket-insider... (repo not opened) and wallet
    0xdde15ebd95330ce69136dc0ccd810d22382e02c5 (3 markets, +137K): new-wallet/large-first-bet detection. Lead only.
  - Other profiles checked: Tokor ("smartest trader of October ... +$70,000 yesterday, almost $200,000 in October"; real: Oct +713K, Nov
    +454K, NET 1,342K, 95% maker, crypto strike markets and "will Nvidia be the largest company"), balthazar (multi-category incl. BTC daily,
    weather, Musk tweet counts, Truth Social post counts; NET 1,197K; Sep +418K, Oct -54K, Nov +16K), e46m3 (Sep +831K, Oct -188K, Nov -553K),
    GetsOnBase (29 markets, +777K in Nov: a football bettor, not a system), dmoralez (NET 122K, 48% rebates), Bossgirl (BTC 5m, NET 47K,
    +30K Oct, +3K Nov), 0x0dbd0e1d… ("9-day-old wallet ... already up $16K", now +67K), 0xdb976ec8… ("G.Hchen", streamer markets, +44K Nov).
- Sells: Polymarket referral (`?via=igor-mikerin`, `?r=iic`), Polymarket Perps sign-up challenge.

### 2.4 @DextersSolab

- 56 Polymarket posts since Sep 22; pure copy-trading promotion ("THOSE WHO STARTED COPY TRADING THIS GUY AFTER MY POST MADE $40K ALREADY"),
  links `polymarket.com/...?via=dexter-molu` and `t.me/PolyGunSniperBot?start=ref_dexterssolab`. No mechanics at all; wallets are discretionary
  sports/crypto punters with few markets.
- Check of ten of his picks: luckycat888888 (+205K), 0x76eca410… (+629K, of which +664K in Nov from "will bitcoin/ethereum dip to X in
  November" markets, 77% of its dollars at 3-20c; 246 markets; a directional bet on a crash, not a system), DelidelaDele (+411K, 133 markets), Dreamlawn (+96K; Sep +176K, Oct -110K),
  big8betz (Oct +101K, Nov -59K), woshikd99 (Oct +26K, Nov -29K), mrcoolside (-16K, 16 markets, promoted repeatedly), tin54321
  (-23K, promoted repeatedly from Oct 17), ch27er (-55K). Four of ten are negative; the winners are a few large directional bets. Nothing to deconstruct.

### 2.5 @rb_tweets

- "Can copytrading be profitable on Polymarket?" series (Sep 2026), each with a gravia.trade affiliate link (`?via=rb`, `?via=tr3`); own
  referral `poly.market/burratatata` in every post (his profile burratatata: 167 markets, NET 14K, inactive since spring).
- 2026-09-03 "Trader 3: Bitcoin Up/Down wallet with $35k PnL (only one trade daily) ... avg position $1.1K at 50c ... 22% ROI", wallet
  0xbf5fe8bfc9ec6e7ff7a311ea85cfc0d2901ac035. Check: 748 markets, gross 21K, fees paid 10K, NET 11K; Jun-Nov +7 / +5 / +5 / **-3 / -10 / -8**:
  it has lost money every month since the post. RetroValix re-posted the same wallet on Sep 4 with his own gravia code.
- 2026-09-10 "Trader 5: sports trader with $36k" (gravia campaign link, wallet not visible in text; not checked). Two X articles on
  Nov 14 and Nov 24 not read.

### 2.6 @RohOnChain

- 2026-10-28, https://x.com/RohOnChain/status/2115480282577117588 (56K views): "i reverse engineered the MOST profitable trading bots ... minute
  0: bid on BOTH sides, Up at 47c & Down at 48c, both fill = 95c in, $1 back ... the instant Bitcoin moves, they cancel & re-bid ... minute 1 to
  3: Binance moves first, Polymarket catches up seconds later ... minute 3 to 4: BUY THE PANIC, Bitcoin still within $15 of the start price ...
  scared traders already dumped one side down to 25-35c ... minute 4 to 5: zero trades in the final 60 seconds ... they only buy from the book
  when the gap beats the fee by 3c+ ... people buying from the book are right 53% of the time & still lose". Ends with "paste the prompt below
  into Grok Bot". No wallet named, no affiliate link visible, nothing checkable. Parts contradict verified wallets (0x50f7, NIULAI4,
  BoneOhio trade mostly in the last minute). The "minute 3-4 panic" rule (price within $15 of the reference but one side at 25-35c) is at
  least a testable statement on the lab's BTC 5m tape.

### 2.7 @w1nklerr

- "MY GROK BOT MADE +$9,012 ON TODAY'S CRASH" (Nov 10), "+$8,425 IN ONE DAY ... it caught the news first and bet on Polymarket" (Nov 12),
  "MY AGENT COPIED THE TOP 3 POLYMARKET WALLETS WHILE I SLEPT" (Nov 3). First-person claims, no wallet, a prompt that lists public repos
  (github.com/Polymarket/agents, py-clob-client), Telegram channel t.me/w1nklerr and a Polymarket referral (`?via=w1nklerr-p0ve`).
  Nothing checkable. Credibility 1.

### 2.8 @carverfomo

- 2026-10-26 "This guy made $165,434 in one day ... put $48K on the side nobody wanted", `polymarket.com/@bigggggggg?via=carverfomoo`.
  Check: Bigggggggg 0x511f9c…, 13,565 markets, $18.6M volume, NET 534K, rebates 9%; Aug-Nov +103K / +222K / +104K / -127K. Last 1,000 fills:
  67% sells, football (Europa League), Taiwan local elections, politics, "will AI solve N more Millennium Prize problems"; a large
  discretionary/semi-systematic multi-category trader who sells overpriced outcomes. Not a bot story.

### 2.9 Accounts probed that had no bot-wallet posts in the window

0xMovez, hanakoxbt, noisyb0y1, zodchiii, AleiahLock, the_smart_ape, kirillk_web3, 0xPhilanthrop, 0x_Discover, seelffff, lookonchain,
LunarResearcher, k1rallik, 0xwhrrari, Shelpid_WI3M, antpalkin, MrRyanChi, defiwimar, AIexey_Stark (7 Polymarket posts, none about bots).
Only the last ~4 pages (roughly 3-8 weeks) of each were read. mikita_crypto: handle not found.

### 2.10 Found by WebSearch, not opened (leads)

- https://www.walidriachy.com/lab/polymarket-5m-bots "Inside the five-minute Bitcoin bots" (snippet: BoneOhio ~$45K the month before the
  article and ~$127K in the 49 days after).
- https://www.polyresearchrobotics.com/reports and /reports/bonereaper (snippet: "fair-value market maker on 5- and 15-minute crypto
  up-or-down markets, based on 1.34M observed trades").
- A GitHub project (name in the WebSearch result list: giuseppemineo685-beep/polycool-strategy) that "rebuilds BoneOhio as a bot that buys
  the side already priced at 94-99 cents in the last two minutes of each BTC 5-minute window", and says x-MoneyForWhiskas was formerly
  "@justoneofmystrategies".
- dev.to write-ups: "Reverse engineering gabigol: high-frequency crypto up/down farmer", "Inside a Polymarket bot: how Slip-Me generated
  $111K in 23 days trading 5-minute Bitcoin markets".
- A vendor claim seen in a search snippet: "all 10.9 million fills in 2,654 Bitcoin Up or Down windows, November 1-7, 2026, every wallet's result".

## 3. What the verified wallets say about the lab's question (time gap)

| observed in wallets that keep money without rebates | where the outside information is | lag | who does it |
|---|---|---|---|
| Resting buy limits on both sides of BTC 5m, 97% maker, 3%+ of volume kept | Binance/Chainlink price vs stale takers | ms-s (needs fast cancel) | almach, bosona, mo-money |
| Resting bids at 0.97-0.99 on the decided side in the last minute; sellers pay 1-3c to exit before settlement | outcome is already ~known from the feed; settlement comes minutes later | s-min | 0x50f7, pspspsps5, BoneOhio |
| Buying 1-3c tails of BTC 5m as a taker | reversal probability near the reference is higher than 1-3% | none (mispriced tail) | Vega7, 0x50f7 (part) |
| Limit bids below de-vigged sportsbook lines 1-3 h before games and in play | sportsbook lines | s-min | 0x5268… (HomeRunHazard) |
| Maker quotes in crypto daily/weekly strike and range markets (fee rate 0.01) | spot + implied volatility (option pricing) | s-min | Tokor, 0xDB5, balthazar (part) |
| Weather buckets after a forecast update / after the reading is in | model runs (GFS/ECMWF), station observations | min-h | Bilberry, hello.67, BeefSlayer, windy-weather |

What does NOT hold up: "see Binance move, lift the stale Polymarket ask" as a taker. Every wallet advertised for that
(nj23adsknml3, 0xAAAAA, Bonereaper, trinity42, norm1e69, blue.birds) is negative or about zero after fees without rebates.

## 4. Coverage and gaps

- RetroValix: complete for 2026-08-28 .. 2026-11-26 (71 bot posts, all wallets identified and checked).
- Dan1ro0: only 2026-10-19 .. 2026-11-26 read (older pages not fetched). DextersSolab from Sep 22, igor_mikerin from Sep 2 (complete).
- X search is not available through the mirror, so other accounts were found by guessing handles and by WebSearch; the genre certainly
  has more publishers (RetroValix and Dan1ro0 look like one network: same template, same wallets, same Horizon sponsor).
- Not resolved to a wallet: dgdgt345dfgdf23, fossildiamond, edzachary. Reddit and Medium not reachable (RetroValix has a Medium mirror:
  medium.com/@RetroValix/5-most-profitable-trading-bots-on-polymarket-in-august-bd6b1d81e9db, seen in search results only).
- Fill samples are the last 1,000 fills per wallet (hours to weeks, depending on the wallet), not full histories; maker share is the
  count of fills absent from the taker-only feed over the overlapping time span.
- I did not test any strategy; "edge" statements in section 3 are descriptions of what profitable wallets do, not proofs that the
  rule is profitable for a new, slower, smaller account.
