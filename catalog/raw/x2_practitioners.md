# X/Twitter: practitioners and official announcements, Sep 1 - Nov 27 2026

Collected 2026-11-27. Everything quoted is untrusted web content. Posts were read with `tools/xread.py`
(fxtwitter mirror); wallets were checked with `tools/wallet_check.py --monthly` on the same day.
"gross" = profile Profit/Loss (before fees); "net" = economic PnL (after fees, with rebates and rewards).

How this was collected: WebSearch returned no x.com results at all for Polymarket strategy queries (only dev.to /
Medium / indiehackers SEO posts), so discovery went through timelines: the official accounts and their retweets,
then the handles named there, then the handles those people quote. About 45 timelines were scanned
(Sep 1 onward where the mirror allowed; many returned only the last 20-100 posts).

A general observation first: on 2026-10-23 Polymarket started paying affiliates 20%+ of the fees their referrals
pay (source 0.9). Almost every "this wallet made $X" post since then carries a `?via=` or `poly.market/<code>`
referral link. Treat those posts as advertising for the click, not as strategy disclosure.

---------------------------------------------------------------------------------------------------------------

## 0. Official announcements that change what works

0.1 Taker delay on crypto markets raised from 50 ms to 150 ms, effective 2026-09-04 14:00 UTC.
    https://x.com/PolymarketDevs/status/2095516409790910925 (2026-09-03, @PolymarketDevs)
    "To improve the trading experience across crypto markets, we're increasing the taker delay from 50ms to 150ms"
    Confirmed in the docs changelog (local copy data/pm_docs/changelog_predictions.md, fetched today): "Higher
    taker delay: The taker delay on crypto markets is now 150ms, up from 50ms. The change took effect on
    September 4 at 14:00 UTC".
    NOTES.md still says 50 ms - that is out of date. A third docs page (concepts_order-lifecycle.md) says
    "held for 250 ms" on "selected crypto and finance up/down markets" - the docs disagree with each other;
    the current value needs a direct measurement.

0.2 Fee and rebate change, announced 2026-11-17, effective 2026-11-20 23:59 UTC.
    https://x.com/Polymarket/status/2122745203102474713 (2026-11-17, @Polymarket, 459K views)
    "dropping the taker fee coefficient to 0.01 across politics, culture, weather, economics, mentions, &
    non-5/15m-BTC crypto". Docs changelog Nov 20: taker rebates Gold 10%, Platinum 25%, Diamond 40%,
    Obsidian 50%, Onyx 60%; Bronze and Silver, category multipliers and level-up bonuses removed.
    What it replaced (from traders, not from the docs):
    - @Tenebrus87 https://x.com/Tenebrus87/status/2122990344950157429 (2026-11-18): "Until Friday, every maker
      earns 25% of the taker fees their fills generate (15% in sports, 20% in crypto). No minimum. From Friday
      night it's tiers on 30-day weighted volume: under $200k: 0%; $200k-1M: 3%; $1-4M: 7%; $4-10M: 10%;
      $10M+: 15%. So a small maker loses 100% ... Gold cut from 18% to 10% ... fees actually go up in
      elections, finance and tech (0.04 -> 0.05). I earn $100-200/day in maker rebates, $3-6k/month.
      Depending on the market, 85-97% of that disappears."
    - @holy_moses7 https://x.com/holy_moses7/status/2122751310638309463 (2026-11-17): fees down 75-80% for
      economics, mentions, culture, non-election politics; "Maker rebates are gone (25% -> 0%) for small -
      medium traders"; https://x.com/holy_moses7/status/2122756004831989850: "a trader like me is doing
      around 20-60k wVol a month" (i.e. far below the 200K tier).
    - @GollumGekko1 https://x.com/GollumGekko1/status/2123027800919527533 (2026-11-18): "we only lowered fees
      on stuff where we barely get any volume, and INCREASED on anything where its possible to get size ...
      usually have silver tier taker, which costs around $600 a month to get 8% back. Under the new taker
      tiers, I will need to spend $6000 a month to get 10% back".
    - @KyleDeWriter https://x.com/KyleDeWriter/status/2123078804176265705 (2026-11-18): crypto non-up/down
      0.07 -> 0.01; BTC up/down 0.07 -> 0.05; sports and combos 0.05 unchanged; finance/tech/elections 0.05
      (~25% higher); geopolitics 0.
    Consequence for a small account: taking became ~5x cheaper in weather / economics / mentions / culture /
    non-election politics; making lost its rebate entirely below $200K of 30-day weighted volume.

0.3 Fee holiday: 2026-10-20 to 2026-10-31, zero fees on NBA, Politics, Economics, Weather, Finance, Culture,
    Mentions and Tech. https://x.com/Polymarket/status/2112611919593103689 (quoted in
    https://x.com/GollumGekko1/status/2112651894325743687, 2026-10-20). Any October backtest must use fee 0
    for those days in those categories.

0.4 New exchange "Nex" (Rust rewrite of the CLOB).
    https://x.com/devjoshstevens/status/2121241806469796103 (2026-11-13, Polymarket engineering lead, 159K views)
    Shadow mode on production traffic for 4 weeks, "we will go live mid-December". Internal timings, p99,
    current CLOB -> Nex: place order 1.55 s -> 3.76 ms; cancel 628 ms -> 3.2 ms; cancel-market 810 ms -> 5.1 ms.
    p95: place 342 ms -> 1.6 ms; cancel 78 ms -> 1.6 ms. "Cancel all: the current CLOB responds immediately and
    cancels in the background, so when you get the response, your orders aren't cancelled yet ... usually adds
    another 600ms-2s." WebSocket write latency p99 44-88 ms -> 0.1 ms. No breaking API changes.
    https://x.com/devjoshstevens/status/2125604044055933225 (2026-11-25): 358 market makers and traders in the
    sandbox; end-to-end (PrivateLink vs public internet) p50 place 36.4 ms -> 3.6 ms, cancel 24.0 -> 2.9 ms;
    p99 place 1,392 ms -> 6.8 ms, cancel 716 ms -> 3.9 ms.
    Why it matters: today a maker's cancel can take 0.6-2 s at the tail, which is exactly why resting orders get
    run over in news events (section 1). After mid-December makers can pull in milliseconds; the stale-quote
    window on news and on crypto should shrink, and co-located speed will matter more, not less.
    Timeline post: https://x.com/devjoshstevens/status/2104561259207065957 (2026-09-28).

0.5 Protocol V2 (new contracts). Announced 2026-10-05 https://x.com/PolymarketDevs/status/2107123604643086570
    (article by @0xrajath https://x.com/0xrajath/status/2107122541219205344 - not read in full). Canary markets
    Oct 5-30 (weather canaries Oct 15, slugs `polyv2-central-park-...`,
    https://x.com/PolymarketDevs/status/2110844441191731267). Rollout moved twice; final: Nov 23, Nov 24, Dec 1
    (https://x.com/PolymarketDevs/status/2120154839724200385). 2026-11-23: "Our first alt-crypto & weather
    markets are now live on Polymarket Protocol V2" (https://x.com/Polymarket/status/2124951396776829228).
    Integrations must support V1 and V2 at once.

0.6 Crypto reference prices. 1-hour and daily crypto Up/Down moved from Binance to Chainlink USD TWAP-60s on
    2026-11-18 00:00 UTC (https://x.com/PolymarketDevs/status/2121003114245620053, 2026-11-12, and
    https://x.com/PolymarketDevs/status/2122397718186283356). RTDS price topics shut down 2026-11-30, replaced
    by PolyBolt (https://x.com/PolymarketDevs/status/2118728223504597137); Chainlink feeds need a Chainlink API
    key from 2026-11-30 (https://x.com/PolymarketDevs/status/2122398311315279935).

0.7 Data and infrastructure. Data API v2 released 2026-09-04, v1 retired 2026-11-02; in-house indexer
    (2026-09-15, https://x.com/devjoshstevens/status/2099930887538319824): "We now see onchain data events up
    to 14 blocks (28 seconds) faster". `GET /v2/resolutions` carries `expected_settlement_time` since 2026-09-28
    (changelog) - useful for any resolution-timing study. CLOB `/prices-history` shut down 2026-10-30
    (https://x.com/PolymarketDevs/status/2114499849634918748). Rewards API rate limits from 2026-11-05
    (https://x.com/PolymarketDevs/status/2115611320259141747). `GET /market-clarifications` since 2026-11-25
    (changelog). Esports markets "5.5x faster" 2026-10-06 (https://x.com/devjoshstevens/status/2107509685712535725).

0.8 Outages and the October incident. CLOB downtime early Sep and again 2026-09-11 (30 min), goodwill credits to
    ~3,000 wallets (@SuhailKakar, retweeted by @PolymarketDevs). 2026-10-29: a third-party script on
    polymarket.com was compromised, sessions were used "to sell positions and move funds"; trading and the
    relayer were paused; 726 wallets affected, $3.9M returned
    (https://x.com/devjoshstevens/status/2116254421369655514, 2026-10-30). A trader lost ~$17K to slippage in
    it (https://x.com/Tenebrus87/status/2115951708035793246). Operational risk is real: a bot must survive
    multi-hour pauses.

0.9 Affiliate revenue share. https://x.com/supermegadaniel/status/2113637607494058173 (2026-10-23): "Polymarket
    affiliates now earn Revenue share on Predictions. 20%+ of the fees your referrals pay on Predictions and
    Perps. No cap per referral." One affiliate reports $26,892 in 30 days
    (https://x.com/Caneleo55/status/2124377338129375388, 2026-11-22).

0.10 New products. Polymarket Perps live 2026-09-03, open to all 2026-09-19, builder codes 2026-10-21, perps fee
    change 2026-11-25, H100 compute perp with "0.01% taker fee" 2026-11-26
    (https://x.com/Poly_Perps/status/2125959269967417442). Commodities up/down (gold, silver, oil, natgas;
    15-minute, hourly, daily) 2026-11-18 (https://x.com/PolymarketMoney/status/2123133542431613006). Compute
    markets 2026-11-25. Combos via builders (Jupiter, 2026-11-06). Builder weekly rewards +$10K for December,
    boosted 4x finance up/down, 2x crypto up/down, 2x tech (https://x.com/PolymarketDevs/status/2125290112376287661,
    quoted 2026-11-24). Polymarket US: 70% API taker fee rebates through end of year
    (https://x.com/Polymarket/status/2125333977493914007, 2026-11-24) - US accounts only, not usable from Serbia.
    LP rewards scale: "$100K in LP rewards up for grabs today" (@PolymarketTrade, 2026-11-24,
    https://x.com/PolymarketTrade/status/2125237678967022053); "$109,852 paid out" on 2026-09-16 (@PolyBuys,
    quoted in https://x.com/Tenebrus87/status/2100515983324578201).

---------------------------------------------------------------------------------------------------------------

## 1. News-headline sniping on deadline ladders (the clearest time-gap evidence found)

1.1 https://x.com/rb_tweets/status/2125192375039595005 (2026-11-24, @rb_tweets, X article; the author promotes
    the Gravia analytics tool and every wallet link is a `gravia.trade/...?via=learn` referral link)
    "How 10 Polymarket wallets made $429k on Jensen Huang's return ($216k came within 40 seconds)".
    Market: Huang rejoins Nvidia by Nov 30 / Dec 31 / Dec 31 2027. Yes was 3c, "traders were bonding No at 97c".
    - First post-news trade 2026-11-23 13:55:50 UTC (Thanks4TheMoney, 1,030 shares at 3.3c, $34).
    - +3 s nimble-mellow-comet buys Dec 31 at 12.4c (50,980 shares); +5 s WarriorPooh buys 46,459 Nov 30 at 4.2c.
    - Price: 50c after 24 s, 80c after 56 s, 95c after 72 s.
    - "In the 72 seconds that followed, 91 wallets bought Yes and made about $239k, and five of them took $216k."
      WarriorPooh +$91.6k (plus a $4k buy 25 minutes BEFORE the news, total ~$120k); nimble-mellow-comet
      +$77.1k on $22.2k; brohop (+11 s, 20c) +$17.7k on $4.5k; Samael-of-Rome (+17 s) +$19.3k on $18.7k;
      tinman2 (+35 s, 50c) +$10.7k on $10.6k.
    - Late bonder: "One wallet bought $133k of 30 Nov at around 97c and sold it at 99.9c a few minutes later,
      for about $4.5k."
    - Other side: "162 wallets had orders filled at the old prices, most of them bids to buy No ... Between them
      they lost about $238k." Flipadelphia 46 fills ~$80k; dromedaryy $25k and DonaldinhoTrumpito $17k in one fill.
    - Before the news: "78 wallets less than two weeks old put $17.8k into Yes and made about $270k" in the
      prior 48 hours; 0x7795...9a17 put in $27k from Nov 14 and made $275.5k (likely informed, not copyable).

1.2 https://x.com/rb_tweets/status/2121613610879512672 (2026-11-14, @rb_tweets, X article)
    "How 3 traders made $71K in 33 seconds on Jensen Huang's Resignation". 2026-11-12 13:48 UTC, the Nov 12
    bracket went 35c -> 97c in 33 seconds; "121 wallets bought $346K of Yes across the six brackets, and made
    about $91K".
    - 13:48:19 Michael-The-Taxiarch buys 69,942 at 37c ($26K) in two fills against 42 wallets, sells all at 99c
      by 13:50:12: +$42.4K "after fees".
    - 13:48:22 wallet "237492103894712349" buys 33,916 at 63c AND 19,003 of the Nov 13 deadline at 50c
      ("which hadn't caught up yet ... cheaper than the market that resolves a day earlier"): +$21.5K.
    - 13:48:42 nimble-mellow-comet, 24,189 shares at avg 94c, $66K across six deadlines: +$7.1K.
    - Bonders at 97-99c: tsekinming01 $45.6K, JJo $42.2K, tinman2 $22.6K, sbimbg $21.7K - "$132K between four
      wallets, for a few hundred dollars each".
    - "The same trade, 30 seconds later, made 30 times less."
    - Losers: resting asks and No bids (Raskell had 32,961 Yes on the ask at 38c).
    Corroboration: https://x.com/KyleDeWriter/status/2121958202497446163 (2026-11-15) and
    https://x.com/datadashxyz/status/2124961655201419474 (2026-11-23).

1.3 Related single cases. https://x.com/dunik_7/status/2120274684952371632 (2026-11-10): Tesla Roadster launch
    stream, 2026-10-15: "yes" fell to 13c at the start of the stream, "at 9:04 pm ET a wallet called dromedaryy
    bought 192,680 yes shares at 10c in a single order; by 9:11 the price was 74c, by 9:30 it was 97c" (a live
    stream watched faster than the market: minutes). https://x.com/KyleDeWriter/status/2122716202329862161
    (2026-11-17): three accounts registered the same day bought ~$14,350 of No at ~4c on "Predict Fun TGE by
    Nov 30" 15 minutes before the postponement announcement (insider pattern, not a strategy).
    https://x.com/primo_data/status/2117840878232649801 (2026-11-04, Polymarket data lead): election calls on
    Polymarket "an hour" before CNN.

My wallet checks (2026-11-27):
| account | joined | gross | fees | rebates+rewards | net | notes |
|---|---|---|---|---|---|---|
| WarriorPooh 0x853c37a9...bd03 | 2025-12 | 350,358 | -8,933 | 5,454 | 347,389 | 808 markets, $3.53M volume, kept 9.8% of volume, 2% of net is rebates. Net by month Jul-Nov: 11.7K, 3.2K, 3.0K, 7.0K, 170.3K. Profitable every month since Dec 2025 but half of all-time is the two Huang events. |
| nimble-mellow-comet 0x3e03eaee...b571 | 2026-10-13 | 196,211 | -2,061 | 703 | 194,892 | 69 markets, 511 fills. Oct -516, Nov +195.4K. A six-week-old account whose whole PnL is November news events. |
| 0x3cc37974...fb0b (shown as Michael-The-Taxiarch on Nov 14 and Samael-of-Rome on Nov 24 - same address, renamed) | 2026-09-23 | 129,012 | -4,165 | 1,216 | 126,063 | 173 markets. Sep +0.9K, Oct +34.6K, Nov +90.5K. |
| Thanks4TheMoney 0x1e0f2a7a...9556 | 2025-11 | -31,765 | -2,046 | 60 | -33,752 | First to trade after the Huang news but with $34; loses money overall (9 of 13 months negative). Being first is not enough. |
| dromedaryy 0x65757591...b198 | 2026-08-14 | 808,816 | -30,614 | 20,062 | 798,857 | 194 markets, $6.0M volume. Sep +27.8K, Oct +416.0K, Nov +359.7K. Both a sniper (Roadster) and a victim (lost $25K on a stale No bid on Nov 23). |
| "Flipadelphia" | - | - | - | - | - | not found by name (closest match is an unrelated dead account) |
Tier 0 on both taker and maker for WarriorPooh, nimble and 0x3cc3: these accounts do not live on rebates.

Reading: the lag between a headline and the Polymarket book is real and long: 3-5 s to the first serious buyer,
~25 s to the midpoint, ~70 s to 95c, on markets with tens of thousands of dollars resting at stale prices.
Sister deadlines lag the front one by further seconds. The money comes from resting "bond" orders (No bids at
97c) and wide asks that cannot be pulled in time (see 0.4 for why). Limits: (a) both documented events are
the same story in the same fortnight, written up by a tool vendor; (b) the three sniping wallets are new and
their PnL is concentrated in 2-3 events; (c) fees: tech markets pay 0.05 (at 5c entry the fee is 0.24c per
share, irrelevant against a 90c move), (d) the edge needs a machine-readable headline feed and a pre-built map
from headline to market; a human reading X is in the 30 s+ bucket where "the same trade made 30 times less";
(e) Nex in mid-December lets makers cancel in milliseconds.

---------------------------------------------------------------------------------------------------------------

## 2. Scheduled economic releases (CPI, jobs, Fed)

2.1 https://x.com/PavelPavlyuh/status/2118315492876132694 (2026-11-05, @PavelPavlyuh, builds smartposition.trade;
    endorsed by Polymarket's data lead @primo_data https://x.com/primo_data/status/2118373796147327078: "The
    markets on Polymarket react within seconds of CPI reports being published.")
    "I took 33 of these releases in 2026 and looked at every single trade, second by second, around 8:30.
    The second before: the correct answer is priced at 48c on average. 7 seconds later: the first trades hit.
    9 seconds later: the correct answer is above 90c. 27 seconds later: it's at 99c."
    "Only 217 wallets traded in the first 10 seconds after a release. 26 of them did it again and again, on 5
    or more releases." Favourite won: inflation 13 of 17, jobs 3 of 9, Fed 7 of 7 (market ~99.6% sure hours
    before). Example: July jobs "US will lose jobs" at 0.3c -> ~$1.
    Not reproduced by me. Caveats: trade timestamps in the Data API are block times 2-3 s after the match
    (NOTES.md), so "first trades at +7 s" is roughly +4-5 s at the matching engine; the post does not say how
    much size was available at the pre-release prices nor who the 26 wallets are.
    Fee: economics is 0.01 since Nov 20 (was ~0.04-0.05; zero during Oct 20-31).

---------------------------------------------------------------------------------------------------------------

## 3. Liquidity-reward farming and maker rebates (discretionary trader scale)

3.1 @Tenebrus87 (named by @PolymarketTrade among "big Polymarket traders").
    https://x.com/Tenebrus87/status/2105566697818136995 (2026-10-01): "September on Polymarket: +$26.3K. $16K
    trading, $10K rewards farming + maker rebates."
    https://x.com/Tenebrus87/status/2100515983324578201 (2026-09-17): 4th on the daily LP-farmer list with $787
    for one day, "mainly due to the 200k clarity yes shares doing its work" (i.e. large resting size inside the
    reward spread on a hot market). Leaderboard that day (PolyBuys): Dr_PNL $7,085, Eltonma $1,717,
    jonathas1158157 $1,069, Tenebrus87 $787, AnjunPoly $763; "$109,852 paid out".
    https://x.com/Tenebrus87/status/2122990344950157429 (2026-11-18): see 0.2 - "I earn $100-200/day in maker
    rebates, $3-6k/month ... 85-97% of that disappears".
    Wallet check: name search matched "Tenebrus7" 0xa8c63f77...44e8 (closest match, not exact - probable, not
    certain): joined 2024-06, 5,322 markets, $43.0M volume. gross 73,707; fees -7,300; rebates+rewards 95,090
    (taker 347 / maker 13,171 / liquidity rewards 81,572); net 163,231; 58% of net is rebates/rewards.
    Rebates+rewards by month Jul-Nov: 11.6K, 12.2K, 10.4K, 11.7K, 9.0K (matches the "$10K" claim for
    September; September gross 11.8K vs the claimed 16K). Net without rebates: +3.7K, -6.3K, +11.2K, -0.6K,
    -84.5K (November: a large directional loss).
    Reading: the reward income is real and steady (~$10K/month on resting size of hundreds of thousands of
    shares), the trading around it is roughly zero-sum for him, and one bad month wipes out eight months of
    rewards. Capital need is far above a few hundred euros.

3.2 @tsybka reply 2026-11-12 "Farm rewards here: <Huang resignation market>" - reward farming on hot news
    markets is exactly where resting orders were run over on Nov 12 and Nov 23 (section 1).
    @XenyPM https://x.com/XenyPM/status/2114333656789442640 (2026-10-25): "LoL Worlds rewards go crazy" (+$200).

3.3 Small maker bot on crypto markets. @XenyPM https://x.com/XenyPM/status/2107102254960447503 (2026-10-05):
    "My Polymarket crypto bot has ultimately generated me roughly $700 in maker fees in September - and roughly
    $300 in trading PNL ... Passively earning ~$1.5k a month" (the $1.5K includes other platforms). Earlier:
    https://x.com/XenyPM/status/2097304869778653546 (2026-09-08) "my small maker bot ... over $1,000 in a
    month". No parameters disclosed; profile "XenyPM" not found by the tool (the wallet in a third-party post is
    a referral short link). 70% of the stated income was the flat maker rebate, which went to 0% for an
    account of this size on Nov 20.

3.4 Context on what "fees" did to non-sports markets before the cut: @GollumGekko1
    https://x.com/GollumGekko1/status/2099804502199033994 (2026-09-15): "when the game is -7% EV based on fees
    ... Swing trading is dead ... leaving a bid on something fast moving is likely to get adversed".

---------------------------------------------------------------------------------------------------------------

## 4. "Bonding": buying near-certain outcomes at 94-99c

4.1 @tsybka (profile tsybka; every market link carries `?via=bond`).
    https://x.com/tsybka/status/2120980677214814615 (2026-11-12): "I bought 50k shares of Jesus return NO at 94c
    thanks to a recent degen who very kindly fills the limit orders of those providing him with liquidity."
    https://x.com/tsybka/status/2116909971073896724 (2026-11-01): Democrats win the House, "over 50,000% APY for
    these 3 days"; 2026-11-03: "In total, I've bet about $45k".
    Wallet check tsybka 0xd5ccdf77...dea4: joined 2024-06, 890 markets, $40.6M volume, gross 303,688, fees -837
    (maker orders and fee-free categories), net 305,579 = 0.75% of volume, of which unrealized -57,543.
    Net by month Jul-Nov: 13.6K, 11.5K, 3.8K, 9.5K, -29.1K.
4.2 The tail: section 1.1 - No bids at 97c on the Huang market lost ~$238K in 72 seconds; section 1.2 - the
    post-news bonders made "a few hundred dollars each" on $20-45K. @KyleDeWriter 2026-11-23 calls bonding No on
    "Jensen Huang divorce by EOY" "free $" (affiliate link); @gavelsvtw 2026-11-23 "52.62% APY" on Huang out
    again (affiliate link).
    Reading: ~0.75% on turnover with tens of thousands per position, punctuated by losses of whole positions.
    Two distinct variants: pre-event bonds (carry jump risk; this is where the snipers' profit comes from) and
    post-event bonds between the fact and the resolution (the time gap is hours to days, the yield is 0.1-3%).

---------------------------------------------------------------------------------------------------------------

## 5. Sports and esports volume bots (large, real, mechanism undisclosed)

Sources are affiliate posts that point at wallets; none explains the rule.
- https://x.com/gusik4ever/status/2125261008478626111 (2026-11-24): homerunhazard "+$5.4M all-time. 57,000+
  markets. no crazy jackpots, just small edges, over and over ... buying every ~8 seconds before tip-off".
- https://x.com/gusik4ever/status/2124155053691080964 (2026-11-21): "one account made $582K in 24 hours, another
  lost $541K in the exact same period ... a market maker doing $28.39M in monthly volume while sitting at
  -$950K PnL; keeptheblueflagflyinghigh quietly made $1.59M this month on $102M volume ... 8 bots traded Suns
  vs Jazz, with 424 trades worth $1.47M".
- https://x.com/gusik4ever/status/2125757975273029861 (2026-11-26): 0xf0318c... "up $5.4M in sports, usual size
  ~$17K ... trades like a bot, ~1,000 trades a day", $717K on one NFL game. Same wallet as BreakTheBank in
  https://x.com/dunik_7/status/2114781070545584378 (2026-10-26: "+$8.38M this month").
- https://x.com/0xTengen_/status/2125976734776676440 and .../2125564057856197005 (2026-11-25/26): thehighlife,
  "$2.4M+ on esports ... 12 of 13 months green".
My wallet checks:
| account | joined | markets / fills | volume | gross | fees (refunded) | rebates+rewards | net | rebate share | net by month |
|---|---|---|---|---|---|---|---|---|---|
| HomeRunHazard 0x52685279...135d | 2026-04-23 | 58,505 / 877,212 | $283.5M | 5,474,967 | -1,734,686 (131,354) | 1,209,755 (taker 732,754, maker 419,482) | 5,081,390 = 1.79% of volume | 24% | Jul 401K, Aug 1,189K, Sep 85K (-127K without rebates), Oct 1,521K, Nov 957K. Diamond taker tier, top maker tier. |
| keeptheblueflagflyinghigh 0x0d6a1ada...aa98 | 2026-08-25 | 16,095 / 203,558 | $62.1M | 3,531,929 | -356,424 | 252,186 | 3,427,691 = 5.5% of volume | 7% | Oct 588K, Nov 2,840K (volume $52.7M, not the $102M in the post). |
| BreakTheBank 0xf0318c32...c80c | 2026-01-22 | 1,864 / 327,337 | $198.2M | 5,717,083 | -404,826 | 731,683 | 6,047,440 (unrealized 336K) | 12% | Jun +5.17M, Jul +2.67M, Aug -4.92M, Sep +2.27M, Oct +7.07M, Nov -5.34M. A whale with multi-million swings, not a steady bot. |
| THEHIGHLIFE 0x8c0b024c...7aa5 | 2025-11-01 | 5,686 / 165,888 | $35.3M | 2,448,036 | -348,366 (204,766) | 83,452 | 2,389,087 = 6.8% of volume | 3% | Jul 128K, Aug 173K, Sep 328K, Oct 521K, Nov 263K. Tier 0: no rebate dependence. |
| 0xe5672675...4fcb ("NBA-only wallet") | 2026-10-31 | 180 / 657 | $1.59M | 224,485 | -3,270 | 4,502 (maker 4,290) | 225,716 = 14% of volume | 2% | one month old; gusik's own count: 15 of 31 tracked positions hit. |
The "market maker at -$950K" is not named in the post (the link under it goes to keeptheblueflagflyinghigh).
Reading: sports is where the largest verified, non-rebate-dependent bot profits are (HomeRunHazard,
keeptheblueflagflyinghigh, THEHIGHLIFE). How they price (sharp sportsbook lines? in-play feeds?) is not in any
post; it has to be reverse-engineered from their tape. Sports fee is 0.05 and was not cut.

---------------------------------------------------------------------------------------------------------------

## 6. Copy-trading "fresh sharp wallets" (the dominant genre on X since October)

- @gusik4ever, https://x.com/gusik4ever/status/2120169616437821788 (2026-11-10): "how I find wallets to copytrade
  on polymarket at 0% fees" (video, not readable here). Daily posts of the form "a 3-day-old account just put
  $82K on Imperial ... 7 for 8 since we started tracking it" (2026-11-27), all with `?via=gusik4ever`.
  His own counter-example: https://x.com/gusik4ever/status/2125260104744448448 (2026-11-24) "one massive win
  doesn't make you smart money".
- @0xTengen_: ~56 posts of this kind since early November (football, tennis, esports wallets).
- @rb_tweets: "Copytrading is the only PMF for building on top of polymarket rn" (2026-11-02);
  https://x.com/rb_tweets/status/2104937277361459695 (2026-09-29): "a trader made $2500 copytrading a BTC
  up/down bot, while the leader made $18k" (backtest hosted by Gravia); 2026-10-03 "finally made $1.1k
  copytrading a BTC up/down bot".
- @datadashxyz (analytics vendor): "top 1,000 traders" positioning vs market price, e.g. 2026-11-23 Jets at 39%
  with "88% of their money on the Jets"; 2026-11-26 Eizenkot 86% vs market 72%.
Reading: nothing here can be tested from the posts; the copier in the only quantified case kept 14% of the
leader's profit; survivorship is built into "N-day-old account, 7 for 8".

---------------------------------------------------------------------------------------------------------------

## 7. BTC 5/15-minute latency bots

- @saurav_tweets https://x.com/saurav_tweets/status/2125592594982076760 (2026-11-25): last 24 h of BTC 5/15m:
  "501k trades, $7.78m traded, $106k paid in fees"; bot 0xc53375ff... "16,558 trades in a day ... about $3.9k
  in estimated fees". https://x.com/saurav_tweets/status/2126030545251647578 (2026-11-26): order book in AWS
  London; latency Dublin 25 ms, Dubai 143, Mumbai 146, Tokyo 243; "when btc jumps on binance, polymarket's odds
  lag for a split second and the cheap shares are gone in about 162ms"; same bot from Dublin 14.8% of orders
  filled vs Mexico 11.4%; "the closest city, london, can't even open trades" (source "research team" not named;
  referral links `?via=freebot`).
- @KyleDeWriter https://x.com/KyleDeWriter/status/2121282599029002698 (2026-11-13) on Nex: "more advantageous
  for high-frequency ... bots".
My wallet checks:
| account | gross | fees | rebates | net | notes |
|---|---|---|---|---|---|
| 0xc53375ff...69a9 | 505,137 | -369,255 | 200,849 (taker 176,434) | 336,731 | $16.9M volume, 1.6M fills, Diamond tier; 60% of net is rebates. Net without rebates by month Jul-Nov: 3.1K, 35.0K, 38.2K, 46.6K, 13.0K. Without the Diamond rebate this is a ~0.8%-of-volume business. |
| 0x8dxd 0x63ce3421...ba9a (the "famous" BTC bot still used in ads) | 2,372,850 | -4,494,762 (4,172,347 refunded) | 72,050 | 2,171,921 | Zero volume in Sep, Oct, Nov 2026 (last activity Aug: $567K volume, -1.4K). It stopped. |
Agrees with NOTES.md: a speed-and-rebate-tier business.

---------------------------------------------------------------------------------------------------------------

## 8. Weather markets

- @atteonthephone (active weather trader, no affiliate links).
  https://x.com/atteonthephone/status/2099759215891878023 (2026-09-15): "Here's a weather trader who made +$17k
  profit and paid $20k in fees, resulting in a net loss of -$3k" (0xf8dc8cd0...).
  https://x.com/atteonthephone/status/2108284371270832349 (2026-10-08): Helsinki - forecasts predicted an
  evening rise, temperature rose from 11.1C at 19:00 to 12.4C at 22:10 and then 0.1C more, "flipping the 13C
  bracket from 0.1c to 100c"; "Most weather traders have been struggling all summer as liquidity has evaporated".
  https://x.com/atteonthephone/status/2111933698647920942 (2026-10-18): Cape Town 13C -> 19C spike was a SPECI
  from another airport (FABL) mislabelled FACT on weather.gov, never corrected; resolution ambiguous between
  the 16C and 19C brackets.
  https://x.com/atteonthephone/status/2122708318460297448 (2026-11-17): "Polymarket is dying. Weather is dying."
  Timeline line (undated in my capture): the market "resolves according to a specific source (Wunderground in
  the past, now weather gov), not METAR".
- @jfm_20wx https://x.com/jfm_20wx/status/2094572953950363844 (late Aug 2026): "my PnL has crossed $125.000
  trading just Weather markets ... Earlier this year, I had just 30$ left"; runs a Discord (weatherolympus). The
  promised how-to thread was not found. Name search matched "jfm-20" (gross 24,225, inactive since July) - not
  an exact match, so the $125K claim is unverified.
My wallet check: 0xf8dc8cd0...f31f: 18,111 markets, 255,885 fills, $879K volume; gross +3,030; fees -29,046
(5,384 refunded); rebates 1,346; net -19,286. Net by month Jul-Nov: -12.0K, +5.8K, -12.2K, -7.1K, -0.8K.
A high-frequency small-ticket weather taker with ~zero gross edge that fees turned into a steady loss. At the new
0.01 rate its fees would have been roughly a fifth, still not profitable.
Reading: the weather gap (station observation vs book) exists in single cases (Helsinki), the practitioners say
liquidity is thin, and the fee was the binding constraint until Nov 20. Weather is now a 0.01 category and V2
markets started there on Nov 23 - conditions changed a week ago, so older results are not a verdict.

---------------------------------------------------------------------------------------------------------------

## 9. Structural / rule edges

9.1 Cancelled-event 50/50 resolution (dead). https://x.com/KyleDeWriter/status/2124514489483542559 (2026-11-22):
    "Until recent changes in resolution system, markets on matches/fights/etc. that were cancelled by any reason
    were resolved 50/50 ... Guys like Stavenson were aping into cheapest outcomes ... Stavenson made ~$324,000
    in just a few months ... recent changes eliminated the way".
    Wallet check Stavenson 0xf5fe759c...e23d: joined 2025-10, 1,036 markets, 44,236 fills, $3.34M volume, gross
    326,102, fees -62,307 (46,908 refunded), net 317,769 = 9.5% of volume. Net by month Jul-Nov: 18.4K, 47.0K,
    15.9K, 11.5K, 11.6K - still positive at a lower level after the rule change. Worth a tape study: what does
    it buy now?
9.2 Complete sets below $1 during fast repricing. https://x.com/PavelPavlyuh/status/2118431176075694140
    (2026-11-05) on @CarOnPolymarket: on May 15, as a ceasefire market ran 52c -> 80c, "he bought Yes on the
    rally and picked up the leftover No side at 11-16c - $3,008 for a complete Yes+No pair. Merged it into cash
    two minutes later for $3,958". Wallet check Car 0x7c3db723...5c6b: 9,357 markets, 268,824 fills, $119.4M
    volume (the post says $193M), gross 1,589,153, liquidity rewards 101,723, net 1,693,275; net by month
    Jul-Nov: 48.4K, -4.3K, 32.3K, 35.8K, 45.0K (the post's "last 30 days: $304k" does not match). Mostly
    discretionary geopolitics (fee 0); the pair trade is a side line of unknown size.
9.3 Combos pricing. https://x.com/KyleDeWriter/status/2122374514432409893 (2026-11-16): "Someone found a huge
    vulnerability in Polymarket Combos pricing ... $149,494 profit in 4 months ... ~26.7k trades with the
    biggest win of just $3.9k" (profile behind a referral short link `poly.market/ComboGOD`). Name search found
    only an unrelated dead account - unverified.
9.4 Resolution-event feed. https://x.com/bravadotrade/status/2108185755734458488 (2026-10-08, vendor): "Bravado
    now streams every Polymarket UMA proposal, dispute and settlement, live. Proposals hit our socket a median
    1.4 seconds before they land on-chain." Vendor claim, not checked.
9.5 Sportsbook vs Polymarket surebets. https://x.com/arbilest_app/status/2115178367989502044 (2026-10-27,
    vendor): "watches Polymarket order books and sportsbook odds live, finds prices that disagree and shows the
    surebet". No numbers.
9.6 Weather data errors as resolution risk: 8, Cape Town.

---------------------------------------------------------------------------------------------------------------

## 10. Mechanism references (not Polymarket-specific, but explain the microstructure)

- @Boywus https://x.com/Boywus/status/2113197626757665185 (2026-10-22, Chinese, X article, 45K views, 498
  bookmarks): tape study of the largest market maker on a perps venue ("Arcus"). "88% of gross profit came from
  taking": it quotes to keep volume and fee tier, and takes other makers' quotes that were not pulled after
  Binance moved; median 95 ms from the Binance move to its fill (venue has a 50 ms taker delay); +0.99 bp per
  taker fill vs fair; at base fees the same trades lose $1,655, at VIP tier they make $662. Same structure as
  the Polymarket BTC bots: taker edge that only exists at the top fee tier.
- @Boywus https://x.com/Boywus/status/2100897533237280923 (2026-09-18): retail-only (RPI) orders - exchanges
  shield makers from API takers. Not a Polymarket feature as far as the docs show.
- @yenwod_ https://x.com/yenwod_/status/2119896129794126320 (2026-11-09, "How to HFT", 263K views, 4,935
  bookmarks): build a deterministic, replayable event-log -> state-machine stack; inventory skew formula
  (widen by `spread * x / (1 - x)` on the aggressed side, tighten by `spread * x` on the other, x = share of
  max inventory); maker on venue A hedged by taker on venue B; simulator reconciled against live fills. Useful
  as an engineering checklist for any bot here.
- @KyleDeWriter https://x.com/KyleDeWriter/status/2122016831217045648 (2026-11-15): reading list with the links
  above plus zostaff "Build an HFT bot for Polymarket" (status 2060691218045206621, mid-2026, not read) and
  supermomonga (2120462603768209850, not read).

---------------------------------------------------------------------------------------------------------------

## 11. Discretionary traders (context only)

- @GollumGekko1 2026-10-07 https://x.com/GollumGekko1/status/2107963253435326551: "if you move something far
  off the FV, liquidity will" come back (thin books are not mispriced books). 2026-10-23/24: rule clarifications
  changing a market's meaning mid-life ("Fire the markets team") - clarification risk is a live issue; see the
  new `/market-clarifications` endpoint.
- @Tenebrus87 2026-10-01 lists his September mistakes: all are rule/clarification reads (LMArena score, "SI"
  executive order, UN meeting).
- @XenyPM 2026-11-21 https://x.com/XenyPM/status/2124276404267466923: bought "over 10k shares at 0.5c" on the
  Anthropic IPO opening-price bracket while watching the indicated open rise (a live-feed gap of minutes).
- @CarOnPolymarket 2026-11-05: "$70,000 from the midterms ... and my oil short".

## 12. What was not found

No practitioner post in the window with rules for: mention markets, tweet-count markets, negative-risk
conversion arbitrage, options replication, or LLM forecasting agents with a checkable wallet. Formerly prolific
"Polymarket bot" accounts (the_smart_ape, RohOnChain, hanakoxbt, carverfomo, noisyb0y1, LunarResearcher) had
zero Polymarket posts in their latest 40-60 posts (all November): the genre moved to AI-agent content, and what
remains is affiliate copy-trading. Handles that failed on the mirror: defiance_cr, 0xMovez, r_gopfan,
Parz1valPM, ChaoticAna9, Boywus (timeline only; single posts worked).

---------------------------------------------------------------------------------------------------------------

## Verification pass

Done 2026-11-27 by a second reader. Method: re-opened 42 of the cited posts with `tools/xread.py status` (every
source URL of candidates 1-12 except the four KyleDeWriter/gavelsvtw side mentions), re-ran
`tools/wallet_check.py --monthly` 46 times on 40 distinct wallets (all wallets named in the candidates plus the addresses
behind the gravia links in the two rb_tweets articles), searched gamma profiles for the names the first pass could
not match, compared against the lab's other files (`w1_reddit_forums.md`, `x1_wallets.md`, `x1_bot_posts.md`,
`studies/wallets/economics/README.md`), and ran three small tape checks (`pmlab.wallet` on Stavenson and THEHIGHLIFE,
MERGE activity of Car, rules + tape of four tennis markets). No candidate was dropped: every cited post exists and
says what is quoted. What changed:

V1. Section 9.1 is wrong that the 50/50 edge is dead. Stavenson (0xf5fe759c...e23d, matched by exact name; gross
    326,102 fits the post's "~$324,000") in the last 30 days: 2,933 fills in 155 sports markets, 154 resolved, and
    2,922 of the 2,933 fills are in markets whose final price is 0.5 / 0.5 ($145K bought, gross +$12.2K). All are
    tennis (ATP/Challenger/ITF match winner, set handicap, totals, set-1 winner). The market rules still say:
    "If the match ends in a walkover (player withdraws before the start and the other advances automatically), this
    market will resolve to 50-50" (retirement after the start resolves to the player who advances).
    Observed sequence, Paris Masters Davidovich Fokina vs Kouame, 2026-11-03: favourite printing 0.74 until 09:33 UTC;
    09:38 Stavenson takes the underdog at 0.28 (20,371 shares printed at 0.28, 2,959 at 0.37), then bids 0.49-0.50 on
    both sides; scheduled start 11:30; market closed 12:30 at 0.5/0.5. Metz Martinez vs Donald, 2026-11-18: favourite
    0.71, 11:15:58 underdog taken at 0.32 (9,478 shares), closed 11:56. Split of his month: 46 taker buys below 0.46
    ($14.6K) earn most of the money (0.15-0.30 bucket +20.8c per share after a 1.0c fee, 0.30-0.45 +13.6c); 2,783
    maker buys at 0.49 earn +0.97c per share (t = 10 over 131 markets), i.e. a 2% post-event bond held about an hour.
    Net by month Jul-Nov: 18.4K, 47.0K, 15.9K, 11.5K, 11.6K; positive in 13 of 14 months; Tier 0.
    Not measured: how many seconds or minutes pass between the public withdrawal notice and his first fill, and
    who else takes in the same window. This is a time-gap edge at small-capital scale and it is live.
V2. Candidate 1 (headline sniping). Both rb_tweets articles confirmed line by line. The lab's own tape
    (`w1_reddit_forums.md`, section 8 and its verification) independently reproduces Nov 23: nimble-mellow-comet
    50,980 at 0.124 at 13:55:53, brohop 18,517 at 0.20 at 13:56:01, first print to 0.90 in 66-74 s. Corrections:
    (a) WarriorPooh bought about 47K Yes at 0.115-0.123 at 13:30:59-13:31:11, 24 minutes before the release was
    public (the article mentions "$4k ... 25 minutes before the news"); it is not a clean public-news reactor.
    (b) Flipadelphia is findable by the address in the article link, 0x448861...e319: gross 866,654, net 842,853,
    November -182.5K; Raskell (the "retail trader" whose 38c ask was lifted on Nov 12) is net +98,471 and positive in
    5 of the last 6 months: the people run over are profitable regulars, not novices.
    (c) New checks: 0xe176...f65 (the "237492103894712349" account) gross 57,129 / net 55,929, Oct -11.7K, Nov +39.2K;
    brohop gross 29,914 / net 29,331, Nov +21.6K on $9K volume; tinman2 gross 16,287 / net 14,868 of which unrealized
    -14,254 (months Jul-Nov -5.6K, -0.5K, -2.1K, -6.2K, +12.6K).
    (d) What a reader 20-70 s late could get on Nov 23 was about 26K shares at 0.50-0.85 for the whole crowd.
    (e) The inference in 0.4 and in NOTES.md that the slow cancel tail is "exactly why" resting orders are run over
    is not supported: the same posts give cancel p50 24 ms and p95 78 ms on the current CLOB; only p99 is 0.6-0.7 s.
    Orders that were still resting 5-70 s after the headline belonged to people who had not reacted at all. Nex
    shortens the takers' order placement too (p99 1.4 s -> 7 ms), so do not assume the window shrinks.
    (f) The datadashxyz post cited as corroboration describes the pre-news holder 0x7795, not the sniping.
V3. Candidate 2 (economic releases). Post and endorsement confirmed. It is no longer "not reproduced": the lab's
    economics study finds stale fills 2-20 s after the release on 53 events, but the whole pool was $20.8K of profit
    in three months. The two specialists named there: TheElement115 gross 8,716 / net 8,491 (Jul-Nov 0.9K, 0.9K,
    0.7K, 4.9K, 1.1K; 151 fills ever) and road2million gross 5,437 / net 5,291 (0.4K, 0.2K, 0.2K, 4.4K, 0.9K).
    October was the zero-fee month.
V4. Candidate 3 (reward farming). Wallet identity strengthened: @Tenebrus87 wrote on 2026-11-25 "Lost $130K on the
    Jensen Huang return markets"; the Tenebrus7 wallet shows November gross -82,149, NET -75,498. His loss came
    from a directional No position ("Close to 100K shares now", 2026-11-23 10:17), not only from resting quotes.
    "Eltonma" and "Dr_PNL" are NOT matched: the closest names (eltonmarisa9771, Dr.PNL2) are unrelated small
    accounts. The same Nov 25 post proposes fading reward-farmer quotes in newly launched high-reward markets
    ("reward farmers set the price, not fundamentals") - not followed up here.
V5. Candidate 4 (small maker bot). Posts confirmed, but "Earned about ~$550 across accounts after rebates"
    (2026-10-25) shows several accounts. The profile "Xeny" (0x7b75...3fd1, net 117,484) had 3 fills and zero maker
    rebate in September, so it is not the bot account. Still unverified; credibility lowered to 1.
V6. Candidate 5 (bonding). The four post-news "bonders" named in the Nov 14 article: tsekinming01 gross -139,991,
    net -140,489 on $58.4M volume (Nov -59.6K); JJo net 335,755 = 0.80% of volume (Nov +34.3K); sbimbg net 269,967 of
    which 48% rebates/rewards (without them Oct -82.2K, Nov +16.4K); tinman2 above. Bonding at size is not a
    reliably positive business even for its regulars.
V7. Candidate 6 (sports bots). The mechanism of HomeRunHazard is described in a post the first pass did not have
    (`x1_bot_posts.md`: resting bids below de-vigged sportsbook lines 1-3 h before games and in play; last 1,000
    fills 81% maker). THEHIGHLIFE is not a high-volume bot: last 30 days 3,103 fills in 165 markets, $1.61M turnover,
    74% maker, about $10K per market, t by market 1.8, kept 262.8K; maker tier 1 (3%), taker Tier 0.
V8. Candidate 7 (copy-trading). The other three "fresh sharp" wallets: 0x7d267c...fdea joined 2026-11-24, 13 markets,
    net 309,052; 0x95581a...fd3f joined 2026-11-03, 22 markets, net 126,854; 0x06081d...3120 joined 2026-11-05,
    57 markets, net 75,293. Real profits, records of 3 to 24 days.
V9. Candidate 8 (BTC latency). 0xc53375ff...69a9 is the profile "dangerously-skip-permissions": same fee group as
    x-MoneyForWhiskas (identical wv_30d 4,471,870, see `x1_wallets.md`), i.e. the operator the lab already took
    apart. It is not independent evidence, and its Diamond rebate comes from the group's pooled volume.
V10. Candidate 9 (weather). "jfm-20" (0xcd9d...06b0): gross 24,225, zero volume June-November, while the post claims
    a "productive summer": not his wallet; the $125K stays unverified. The post is dated 2026-08-31.
V11. Candidate 10 (fresh wallets). 0x7795...9a17 is not fresh: active since at least June, -54.1K in July, +306.1K in
    November, net 260,359. 0x208cd...a396 is the Taipei wallet (joined 2026-11-05, 5 fills, $97K, unrealized +10.0K,
    election on Nov 28: unresolved). 0x127f: net 46,894 on $2,593. 0x41ad: net 28,672, 5 fills.
V12. Candidate 11 (pair merge). Car's activity has 555 MERGE rows in 90 days for $4.80M of complete sets ($2.42M in
    October, $2.14M in November); the largest ($166K-278K each) are 2028 presidential markets. That is inventory
    recycling by a two-sided quoter on rewarded long-dated markets, not taker arbitrage on stale asks. The post's
    "$193M lifetime volume" and "$304k last 30 days" do not match the API ($119.4M; November +45.2K).
V13. General: `wallet_check.py <name>` falls back to the closest profile name. Four of the first pass's fallback
    matches are wrong or unusable (jfm-20, eltonmarisa9771, Dr.PNL2, combogod with one $21 fill); only Tenebrus7
    holds up. Use the 0x address from the link whenever a post has one.
