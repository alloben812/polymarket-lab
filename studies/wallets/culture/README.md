# Culture category: how the consistently profitable accounts make money

Study date 2026-11-27. Read-only, public data. Protocol (hypotheses and rules written before each look):
`protocol.md` (base + 3 addenda). All numbers are after an estimated taker fee unless a line says "API".

## Short answer

1. The culture winners are **specialists with a model of one data source**, not speed traders and not market
   makers. The cleanest case is **cat-dog** (box-office buckets): 38 events in 60 days, 35 profitable, t = 4.0 by
   event, six positive months in a row, about $11K a month on about $23K of capital.
2. There **is** a time gap, but it is not "be first after the number". After each public data point (Thursday
   previews, Friday actual, Sunday studio estimate) the crowd reprices in the right direction and **overshoots**:
   following 10-cent jumps in box-office buckets lost 9.7 c/share (t = -2.3, 50 markets). The winners trade against
   the overshoot with a calibrated bucket model and hold to the Monday actuals.
3. **Copying them by watching their fills does not work** for cat-dog (-1.4 c/share, t = -0.3, 47 markets, worst
   print within 15 minutes) and is unstable for shovelingdigging (+8.4 c, t = 1.6; first half +14 c, second half
   -0.9 c). The price moves about 6 c within 10 minutes of their taker fills.
4. **Post-count markets** (Elon Musk weekly / 2-day buckets): the official counter has a public JSON API with every
   counted post; the counter lags the post by a median of 161 s (p90 296 s). With 12 hours left the pace projection
   is still wrong by about one bucket (RMSE 18.5 posts) and the eventual winner trades at 20 cents or less in 6 of 24
   events. One two-month-old account (**hixlz**) made $40K on $3K of capital by resting 1-15 cent bids on the
   bucket next to the pace bucket in the last 6-13 hours. Lumpy: 8 winning events of 30.
5. **Late buying of near-certain outcomes exists and pays 2-4% per turn**: cat-dog bought 0.90-0.995 tokens in 50
   box-office markets, $70K, +4.4%, no losing market, median 4.5 days to resolution. Fifty markets is about 20
   weekends, so the tail is not measured.
6. Three "leaders" on the culture board are **accounting artefacts or unverifiable**: anothercoin (API says +$37K;
   cash flows over 33 days say +$1.0K and the 3,700 open positions are worth $207), 0xc023bee9 (API +$23K on $1.6K
   volume) and pleaseletmealone (3,337 splits + 3,337 conversions in 14 days). Do not trust a leaderboard number for
   an account that uses neg-risk conversions.

## Selection

`leaders.txt` / `leaders.json`: 140 accounts on the culture month / week / volume boards.
Selection rule (protocol): >= 500 lifetime markets (or >= 250 with three positive months), average fill <= ~$250,
rebates <= 20% of kept, at least 2 of the last 3 months positive, kept_all > 0.

| account | why chosen | depth |
|---|---|---|
| cat-dog | 282 mkts, $224/fill, 1% rebates, 6 positive months | deep (150 markets, 60 d) |
| shovelingdigging | 1,158 mkts, $137/fill, 3% rebates, 3 positive months | deep (150 of 337 markets, 60 d) |
| ayosussybenny | 528 mkts, $65/fill, 1% rebates, 4 positive months, smallest account | deep (150 of 353 markets, 90 d) |
| Elonurmom | 1,834 mkts, post-count specialist, 3 positive months | deep (120 of 190 markets, 60 d) + tracker data |
| hixlz | found on the board with $5/fill; post-count longshot bids; only 2 months old | deep (149 markets, 35 d) + tracker data |
| anothercoin | 9,047 mkts, $14/fill, 3% rebates, 2 positive months | cash-flow reconstruction (33 d) |
| 0x66E7ce01.. / 0xc7D02944.. | 26K / 49K mkts, three positive months, 18% / 14% rebates | table level only (cross-category market makers) |
| Electricy (contrast) | $489/fill, same streamer niche as ayosussybenny | story on 35 markets |

Looked at and dropped: **smellyEllie** (table run; 169 of 222 markets are politics/news, culture slice -$651 on 11
markets). Skipped top names: xtxpleasecallme (53% rebates, 1.5M fills, market maker), Bigggggggg (-$127K in
November), elmcap2 ($3,087/fill, whale), Haradwaith (rebates 201% of kept), laidaodao (66 markets, one month),
e46m3 and donthackme (-$554K / -$534K in November), pleaseletmealone (one month, conversion machinery, tool cannot
reconcile 723 of 775 markets), bernardbulletin and paddaa (meet most of the rule, a negative month each; not
studied for lack of budget), 0xA2cd4C ($8,603/fill, 27 markets), 0xc023bee9 (artefact, above), New.Jeans and
AnonymousUsername (two negative months), 0x62D56 / Mitchieboi / KazLCC / asdkd938 (4-12 markets), soonand
(-$762K all time), auros2 (one month, market-making firm name), JamesBonder007 ($3,764/fill).

Note on categories: `pmlab.gamma.family` files the Elon post-count markets under "politics" (their tags), while
the leaderboard's culture board includes accounts whose money comes from them. I treated them as culture.

## Tool totals against the API (step 2)

| account | window | tool net (resolved, complete) | API gross same days | verdict |
|---|---|---|---|---|
| ayosussybenny | 14 d | 7,134 | 7,943 | agree |
| hixlz | 30 d | 33,638 | 36,812 | agree |
| Electricy | 30 d | 21,331 | 20,983 | agree |
| cat-dog | 14 d | 1,199 | 3,628 | differ: 30 unresolved + 10 carried-in markets. 60-day story: 19,637 resolved + 1,923 open vs API Oct+Nov 21,981: agree |
| shovelingdigging | 14 d | -240 | 4,437 | differ: 57 unresolved long-dated markets. 60-day story: 26,127 + 11,163 open (150 of 337 markets) vs API Oct+Nov 35,224: agree within 6% |
| Elonurmom | 14 d | 4,117 | 1,087 | differ: 48 incomplete (7 conversions), 34 unresolved. 60-day story 2,605 + 5,874 open vs API Oct+Nov 13,257: 64% explained (120 of 190 markets; conversions not modelled) |
| anothercoin | 14 d | -151 | 7,261 | NOT reconciled: see its section |
| 0xc7D02944 | 14 d | 1,775 | 28,548 | NOT reconciled (504 incomplete markets, 1,217 merges); table level only |
| 0x66E7ce01 | 14 d | -13,903 | -9,505 | same sign, both negative in the window |

## Account by account

### cat-dog (0x7056f248c5098cce2fb0a062cdd2ab0f8318c95c) - box-office buckets

Monthly kept (API): Jun 4,805, Jul 8,457, Aug 13,458, Sep 14,165, Oct 10,740, Nov 11,241. Rebates 1%.
60 days, 150 box-office markets (125 resolved), 38 events:

- Resolved PnL 19,637 on 209K turnover (9.4%); 100 of 125 markets and 35 of 38 events profitable; event-level
  t = 4.01; worst event -1,336, best +3,059.
- 57% taker by dollars. Peak net cost tied up $23.4K, 13 markets open at once (max 29), median buy per market
  $624, its turnover is 6% of the market's volume (median market volume $13.6K).
- Exits: sells 58% of what it buys, mostly winners at 0.999 after the outcome is known (frees capital before the
  UMA resolution) and repositioning between buckets.
- Rules: resolves on The Numbers **final** 3-day figure (Monday), not the Sunday studio estimate; a value exactly
  on a boundary goes to the higher bucket.

Where the money is, by information phase (weekend markets, fills priced 0.03-0.97; phase times inferred from when
the tape jumps: Sat 14-16 UTC, Sun 14-17 UTC, Fri 19/23 UTC):

| phase | fills | mkts | usd | pnl | % | usd on winning side |
|---|---|---|---|---|---|---|
| A before Fri 14:00 UTC (no previews yet) | 213 | 64 | 66,999 | 6,987 | 10.4% | 90% |
| B Fri 14:00 - Sat 14:00 (previews known) | 139 | 54 | 25,895 | 872 | 3.4% | 55% |
| C Sat 14:00 - Sun 15:00 (Friday actual known) | 141 | 46 | 23,113 | 9,364 | 40.5% | 71% |
| D Sun 15:00 - Mon 20:00 (studio estimate known) | 27 | 13 | 7,791 | 990 | 12.7% | 40% |
| E after Mon 20:00 | 13 | 2 | 1,804 | 933 | 51.7% | 100% |

Two sampled stories (`cat-dog.wildwood.txt`, `cat-dog.godzilla.txt`):

- *Wildwood*, opening 23-25 Oct. Sat 14:30 UTC the Friday number lands: "10-12M" jumps 0.37 -> 0.59, "12-14M"
  falls 0.55 -> 0.27. cat-dog buys 10-12M at 0.587 at 14:53 (23 minutes later; others print 0.73 ten minutes after),
  then buys the dumped 12-14M bucket: 1,404 shares at 0.30 (16:02), 1,027 at 0.12 (Sun 09:43), 478 at 0.34 (Sun
  23:18) and sells 925 of 10-12M at 0.65. Monday actuals: 12-14M. PnL on that bucket +2,299.
- *Godzilla Minus Zero*, opening 6-8 Nov. Sun 15:30 UTC studio estimate: "31-34M" 0.51 -> 0.85 and "28-31M"
  0.46 -> 0.16 on 42 trades. At 15:53-15:55 cat-dog buys 1,085 shares of 28-31M at 0.09-0.11. Monday actuals:
  28-31M. +1,674 on that bucket and +873 on the short of "less than 28M".
- Losses look the same in reverse: *Ebenezer* 16-19M bought at 0.61 (2,000 shares), actual fell outside, -1,219;
  *Other Mommy* at-least-33M, -1,451.

Falsification attempts:
- "It buys after the outcome is decided": false. 46% of its dollars are before the market's T90 and that part
  earns 18.1%; after T90 it earns 2.6%, after T99 zero. Fills in markets "not yet decided": +33.3K on the winning
  side, -16.4K on the losing side.
- "The drift after its fills is its own prints": false. With its own rows removed, the independent price is
  +3.4 c/share after 10 minutes, positive in 143 of 149 markets; for taker fills in quiet markets (no move in the
  prior 2 h) the independent price ends 6.9 c above its pre-fill level, i.e. 4.5 c beyond what cat-dog paid (it pays
  2.5 c of slippage) (`leadlag.py`).
- "It follows momentum": false. FADE taker fills (price ran 14 c against it in the prior 2 h) earn 34% of
  notional; FOLLOW taker fills 13%.

Mechanism: a calibrated model of the 3-day gross given previews / Friday / Saturday numbers and of the gap between
Sunday estimates and Monday actuals; it buys the mispriced neighbour bucket, mostly as taker, plus a carry leg
(0.90-0.995 tokens, 50 markets, +4.4%, no loser, 4.5 days locked).
Time gap: minutes to hours after each public number; the crowd's adjustment overshoots and is corrected only by
the next number. Not a latency race: its Wildwood entry was 23 minutes after the jump began.
Confidence 4/5 (38 events, six months of monthly data).

### shovelingdigging (0xe904443b4084bbda216e344353a44cd4324a2d9f) - pop-data generalist

Monthly kept: May 2,453, Jun -1,388, Jul 10,483, Aug -3,938, Sep 20,056, Oct 22,870, Nov 12,354.
60 days, 150 of 337 markets (largest by turnover), 110 resolved: PnL 26,127 on 145K (18%), 80 winners; open
positions marked +11,163. Peak capital $47K, 32 markets open at once, about 80-88% taker by dollars.

| sub-family | mkts | resolved | win | usd | pnl resolved | t by market |
|---|---|---|---|---|---|---|
| Billboard / US song rank | 36 | 25 | 14 | 58,442 | -1,378 | -0.62 |
| box office | 28 | 20 | 14 | 43,072 | 1,254 | 0.72 |
| Spotify (weekly #, monthly listeners) | 15 | 12 | 9 | 30,900 | 2,639 | 0.96 |
| album first-week sales / releases | 22 | 10 | 9 | 27,007 | 1,224 | 3.24 |
| market-cap rank (not culture) | 9 | 4 | 3 | 24,384 | 8,913 | 1.81 |
| "next James Bond" (sold favourites) | 7 | 7 | 7 | 12,911 | 4,082 | 2.03 |
| YouTube views (MrBeast, trailers) | 17 | 17 | 11 | 11,749 | 2,719 | 1.00 |

Taker fills in quiet markets: independent price +6.3 c in 10 minutes, PnL 33% of notional (240 fills, 111
markets). Holds: sells only 29% of what it buys. Trades 2-7 days and more than 7 days before the end; the 6-24 h
bucket loses (-3,246). No single sub-family is significant in 60 days and Billboard is negative; a third of the
resolved profit is two non-culture bets (Apple largest company +4,995, Lula +3,710).
Mechanism: counts public running data (YouTube view counter, Spotify daily charts via trackers such as kworb,
HITS Daily Double, The Numbers) and buys buckets 2-10 days out when the running number already makes them likely.
Model / data edge, days of lag, discretionary breadth. Confidence 3/5.

### hixlz (0xcfa9f86fa970296835711d9513c346343a2ba5d3) - longshot bids on Elon post-count buckets

Joined 2026-10-22. API: Oct +31,628, Nov +8,103 (the split is mark-to-market; totals agree with the story).
35 days, 149 markets, 30 events: PnL +40,530 on $21.4K of buys; 9 winning markets of 127, 8 winning events of 30,
event-level t = 1.86, best event +14,256. 91% maker, buys only, never sells, median fill **$1**, median cost per
market $26, peak capital $3.0K, up to 39 markets open.

Against the official counter (`elon.py`, tracker count matched the resolved bucket in 21 of 21 events):

| where the bucket sits vs pace projection | fills | events | usd | pnl |
|---|---|---|---|---|
| +1 bucket, 6-24 h to end | 952 | 13 | 8,148 | +28,604 |
| +1 bucket, 24-72 h | 159 | 10 | 857 | +1,672 |
| on pace, 6-24 h | 171 | 4 | 3,193 | +1,721 |
| >= +2 buckets (all times) | 1,696 | 15 | 5,507 | -2,351 |
| before the window opens | 364 | 12 | 684 | +4,124 |

Winning tickets: 380-399 bought at 0.060 (13,795 shares, 5-9 h before the end, 42 posts still needed at T-6h and
the market at 0.02); 90-114 at 0.133 (17,008 shares, 7-9 h before); 140-164 at 0.031 (32-35 h before).
118 losing markets cost $15.2K in total at an average price of 1.9 cents.
Falsification: "it buys buckets already decided": false, zero fills in a bucket that was arithmetically dead or
after the window. "It leads the price": no, +0.2 c after 10 minutes; the payoff is at the end.
Mechanism: long variance. It bids under the market on the bucket above the pace bucket in the last 6-13 hours
(window ends 17:00 UTC; over the last 28 days the hours 14, 15 and 16 UTC carry 58, 52 and 72 posts against a
median hour-of-day of 50, so the final hours run somewhat above the pace so far) and lets sellers come to it. Model edge on the spread of the final count, not a time gap.
Confidence 2/5: two months, 8 winning events, one account.

### Elonurmom (0x0f7f9903f46c24ba66900ceb4a427873129c6450) - Elon post-count, bigger tickets

Monthly kept, last 12: +403, +2,004, -3,557, +10,687, +3,257, +8,312, -10,939, +403, -2,537, +2,168, +8,383,
+4,874 (8 of 12 positive, all-time +15.5K; about $1.2M volume in those 12 months).
60 days, 120 of 190 markets, 17 events: resolved PnL +2,605 on 133K (2.0%), 10 winning events, t = 0.27; worst
event -7,617. 96% taker, sells 8% of what it buys, median market buy $400, up to $3,000.
By pace offset: buckets two or more below pace +7,350 on 51.6K (13 events); on pace -3,652; +1 bucket -3,016.
Last 6 hours: -7,495 on 9.6K. Independent price after its fills: -0.5 c at 10 minutes.
Mechanism: early (2-7 days out) bets that the final count comes in below the current pace, taker, held to the
end; no evidence of a time gap or of an information lead. Small positive expectancy with large event variance.
Confidence 2/5 that there is an edge at all.

### ayosussybenny (0xad7fe966ec683f63666069950848b6075ca9c31f) - streamer events, small account

Monthly kept: Aug 2,313, Sep 1,139, Oct 2,663, Nov 7,191. Volume $13-33K a month. Taker 98%.
90 days, 150 of 353 markets: streamers (Kai Cenat / xQc / IShowSpeed "finish GTA VI by date") 43 markets,
+9,041 on 25.2K, 28 events, 18 winners, t = 1.59, best event +5,074. Sports 87 markets, +508 on 21.5K (t = 0.24):
no edge there. Peak capital $2.8K, median market buy $210.
Stories (`ayosussybenny.kaicenat.txt`): bursts across several date markets inside 15 minutes while the stream is
live (Tue 10 Nov 02:20-02:37 UTC: by-Nov-11 variants bought at 0.27-0.52, 0.96-0.98 a day later; Wed 18 Nov
03:44: 3,715 shares at 0.09 and 1,227 at 0.31 on later dates, final Yes). Independent price +0.3 c at 10 minutes,
+6.8 c at 24 hours: not a speed edge; a judgement about remaining playtime against the deadline.
Mechanism: watches the live stream (the resolution source) and prices progress better than the crowd; half of the
profit is one event. Confidence 2/5 (lumpy, the GTA VI release was a one-off supply of such markets).
Electricy does the same with 30 times the size: 35 markets, +15,736 on 173K, 27 of 32 winners, peak capital $91K.

### anothercoin (0xc22b72b0fec23b797589ef6778bb6589e325deab) - neg-risk conversion bot, API profit not real

API: +37,204 since 2026-10-27 on $215K volume; culture board month PnL 35,743.
Cash reconstruction, 33 days (`anothercoin_hist.py`): buys of No $212,895 (15,623 fills, about $14 each), 2,465
conversions returning $207,875, merges $3,180, redeems $748, sells $2,449 -> **net cash +$1,038**. Open positions:
3,700, current value **$207**, booked entry cost $14,796. Rebates and rewards $986. Daily API PnL: +7K, +6K,
+5K, +14K, +10K, +8K, +5K in the first week, then -26K on 5 Nov: marks, not cash.
What it does: in a neg-risk event it buys No on two or more outcomes when the asks sum to about (n-1) dollars
(Spain PM: 5,104 No shares at 0.498 for $2,542, converted for $2,552) and keeps the Yes tokens of the remaining
outcomes for free. Real edge is about 0.5% of turnover plus a pile of free tail tickets.
Structural arbitrage, bot required (3,400 markets in 14 days), real profit about $1-2K a month. Confidence 4/5 in
the mechanism, 4/5 that the API figure overstates it.

### 0x66E7ce01.. and 0xc7D02944.. - cross-category market makers (table level only)

0xc7D0: 100% maker, $982K volume in 14 days, 1,217 merges; kept +34.1K (API), 16% of it rebates; culture is 101 of
1,028 markets and -$216 in the window. 0x66E7: 55% maker, 4,020 merges, API -9.6K in the window after +41K in
November overall; November rebates 19.9K against fees 14.2K. Culture slice +$457 on $111K.
Neither earns its money in culture; both need rebate tiers and inventory across thousands of markets.
Not copyable with a few hundred dollars. Confidence 3/5 (not studied market by market).

## Category-wide checks

**H1 "buy after the deciding number is public"**: rejected for every specialist as the main source. Share of
resolved PnL from fills before the market's T90: cat-dog 89%, shovelingdigging 94%, ayosussybenny 100%, hixlz
all of it.

**H3 near-certain carry** (buys at 0.90-0.995, resolved markets):

| account | mkts | usd | pnl | losers | median days locked |
|---|---|---|---|---|---|
| cat-dog | 50 | 70,256 | +3,115 (4.4%) | 0 | 4.5 |
| shovelingdigging | 25 | 27,298 | +704 (2.6%) | 2 (-876) | 4.2 |
| Electricy | 20 | 59,793 | +625 (1.0%) | 1 (-3,222) | 0.9 |
| ayosussybenny | 14 | 3,799 | +143 (3.8%) | 0 | 0.9 |
| Elonurmom | 17 | 40,623 | +122 (0.3%) | 1 (-2,279) | 3.0 |

**Copy rule C** (`copy.py`, 2 variants, worst independent print in the window, fee in, unit = market):

| account | variant | markets | pnl/share | t | first half | second half | no print |
|---|---|---|---|---|---|---|---|
| cat-dog | 60 s - 15 min | 47 | -1.43 c | -0.31 | -0.46 c | -2.45 c | 39 clusters |
| cat-dog | 5 - 30 min | 39 | +0.64 c | 0.12 | +5.85 c | -6.11 c | 49 |
| shovelingdigging | 60 s - 15 min | 55 | +8.36 c | 1.59 | +14.05 c | -0.85 c | 59 |
| shovelingdigging | 5 - 30 min | 55 | +6.89 c | 1.33 | +11.19 c | +1.35 c | 57 |

About 40% of the signals had no independent print at all in the window: thin markets.

**Jump-follow rule J** (`jumps.py`, 1 variant, 125 resolved box-office markets cat-dog traded): 395 jumps, 202 with
no print in the next bar; following loses -9.72 c/share (t = -2.28, 50 markets; first half -12.99, second half
-7.15). Outcome minus the price right after the jump: -9.18 c before any cost. Universe is selected (markets one
winner chose to trade), so the size of the reversal is an upper bound.

**Elon post-count events, unconditional** (`elon_all.py`, 24 events ended 21 Oct - 25 Nov):
- Counter lag (importedAt - createdAt), last 30 days, 1,294 posts: median 161 s, p10 35 s, p90 296 s, p99 5,807 s.
- Projection error, final minus projection: pace bias +1.1, RMSE 18.7 posts at T-12h (bucket width 20-25);
  RMSE 9.9 at T-6h. A 28-day hour-of-week model was no better (18.5 and 12.7).
- Eventual winner's price: median 0.40 at T-24h, 0.50 at T-12h, 0.74 at T-6h, 0.89 at T-2h; at or below 0.20 in
  7, 6, 6 and 1 of 24 events.
- 12 exploratory variants (price + 1 c, fee in, prices-history is not an ask, so not a fill test): buying the
  pace bucket at T-12h -31.4 c (t = -3.5, 5 hits in 23, average cost 0.53); pace+1 at T-12h +13.0 c (t = 1.4);
  pace-1 at T-12h +13.5 c (t = 1.3); the other nine between -22 and +8 c (two of them negative with |t| near 2.4: the diurnal bucket at T-6h, pace-1 at T-24h). One t of -3.5 out of 12 variants on 23
  events is a lead, not a result.

## What it would take to copy

| niche | data | speed | capital | tooling | fee | room |
|---|---|---|---|---|---|---|
| box-office buckets | previews / Friday / estimate / actual history (Box Office Mojo reachable here; The Numbers returns 403, Deadline 404 through this proxy) | minutes to hours | $300 works: 6-12 markets a weekend at $20-50 | bucket-probability model, REST polling | 0.01 (0.25 c at 0.50) | median market volume $13.6K; cat-dog alone is 6% of it; a few hundred dollars per bucket without moving it |
| Elon post-count tails | xtracker JSON API (free; count matched the resolved bucket in 21 of 21 events) | none (resting bids) | $300-3,000; tickets of $1-25 | count model with a proper tail, bid ladder | maker: 0 | median market volume $86K-180K; hixlz filled 17,000 shares at 13 c |
| streamer deadlines | the live stream itself | hours | $200 a market | a person watching | 0.01 | $30-100K a market, but supply is event-driven |
| near-certain carry | same as the niche it sits in | hours | any | knowing which "certain" is really certain | 0.01 x p(1-p): 0.05 c at 0.95 | $1-3K per bucket near 0.95 |
| conversion arbitrage | gamma + CLOB books for all neg-risk events | seconds | $3-5K recycled | bot, on-chain conversions | mostly taker at 0.01-0.05 | about $1-2K a month for the one account seen |

Main risks: bucket boundaries (one unit of the source decides everything), resolution on a different figure than
the one the crowd watches (estimate vs actual, tracker vs X), rule changes on the counter, thin books (40% of copy
signals had no print in 15 minutes), event-supply risk (GTA VI streams), and plain variance in the tail strategies
(hixlz: 22 of 30 events lost).

## What I checked and what I could not

Checked: 60-90 days of fills for six accounts (1,266 / 1,244 / 831 / 1,053 / 4,002 / 526 matching fills), whole
tapes of about 760 markets, monthly API figures, rules text of 11 market types, the tracker's post log (2,881
posts) against the resolved bucket of 21 events (15 overlapping ones for the second account), 33 days of anothercoin's cash flows.
Script variants run and counted: story.py 6 accounts; drift.py 5; leadlag.py 4; subfam.py 5; copy.py 2 variants
x 2 accounts; jumps.py 1; elon.py 2 accounts; elon_all.py 12 exploratory variants (9 written in the protocol
first, 3 "diurnal" rows added while coding and disclosed); capital / phase / carry tables are descriptive.

Not checked:
- The publication times of box-office numbers from the sources themselves (Deadline and The Numbers are blocked
  here). Phase boundaries come from when the tape jumps.
- Stream state for the GTA markets: no data.
- Order books: no history, so no copy or jump test proves a fill of any size. Prints only.
- Fees before 2026-11-20: the market fee field is unreliable there (several older culture markets show rate 0);
  I used `fees.market_rate` with a 0.01 fallback. At 0.25 c a share at most it does not change any conclusion.
- Why the API books +$37K for anothercoin. Cash and positions say about +$1-2K.
- The two market makers market by market; shovelingdigging's other 187 markets; Elonurmom's other 70.
- Persistence beyond the monthly figures: hixlz has two months, ayosussybenny four.

## Files

`protocol.md`, `leaders.txt`, `<account>.txt` / `.json` / `.monthly.txt` (pmlab.wallet and wallet_check outputs),
`<account>.story.json` / `.story.txt` / `.story.log` (per-market stories), `cat-dog.wildwood.txt`,
`cat-dog.godzilla.txt`, `ayosussybenny.kaicenat.txt`, `Electricy.kaicenat.txt` (event timelines), `extra/`
(table-level runs of 0xc023bee9, hixlz, pleaseletmealone, Electricy), scripts `groups.py`, `story.py`, `drift.py`,
`leadlag.py`, `subfam.py`, `copy.py`, `jumps.py`, `event_view.py`, `capital.py`, `elon.py`, `elon_all.py`,
`anothercoin_conv.py`, `anothercoin_hist.py`. Tracker posts cache: `data/xtracker/elon_posts.json` (git-ignored).
