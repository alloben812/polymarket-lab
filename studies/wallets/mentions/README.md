# Mentions category - how the profitable accounts make money (study of 2026-11-27)

Read-only study, public data only. Protocol and its three addenda (each written before the variant it governs) are in
`protocol.md`. Fees are in everywhere (taker 0.01*p*(1-p), rebates 0). Unit of analysis is the market or the event.

## Short answer

1. There is no dominant speech-to-text bot. In 131 clean live jumps (8 weeks, 51 events) the median jump has ONE
   wallet trading in the first 10 seconds; the most frequent fast taker (QuantDeLaFugazi) is present in 26 of 131.
2. Speed alone pays almost nothing. In 57% of jumps the very first print after the word is already >= 0.90; the
   median time from the first print >= 0.60 to the first print >= 0.95 is 2 seconds. Everything all takers together
   locked in below 0.95 during those jumps is $5,485 in 8 weeks (about $690 a week for the whole field; $1,885 of it
   at a lag of 30 s or more). The fastest account locked in $295 from its first-10-second fills.
3. Buying the "already decided" side at 0.95-0.99 is not free carry. Following the first >= 0.95 print blindly wins
   96-98% of markets and still returns -0.2% to -4.4% on the test half, because 4.2% of Yes confirmations (29 of 695)
   and 1.6% of No confirmations (11 of 670) resolve the other way. The accounts that do profit there have a lower
   error rate (oidocrop 2 wrong of 265 markets, 0xtrador 0 of 117) - they verify, they do not follow the tape.
4. The money of the consistent accounts comes from three other places:
   - judgment while the outcome is still disputed or being counted (oidocrop: more than 90% of its profit is from
     ~45 markets where it bought the eventual winner below 0.95);
   - picking the No side a day or so before the event on words that are priced as longshots (jkerkela, Faston,
     0xtrador): their No picks returned +26% to +31% against +8% to +14% for buying No on every sibling market;
   - small resting bids before the event that are cancelled or lucky during it (Faston, 0xtrador maker fills).
5. The niche is tiny: 1,382 resolved markets in 95 events had $2.42M of volume in 8 weeks, median market $482, 90th
   percentile $3.0K. The winners studied here run $1K-$5K of capital in mentions and keep $1K-$3K per 45 days. A
   few hundred dollars fits; it does not scale.

## Selection

`python3 tools/leaders.py mentions --top 60` -> `leaders.txt` / `leaders.json` (141 accounts).

Tooling note found on the way: `pmlab.wallet` never prints a "mentions" family, because the gamma tag is
`mention-markets` (the tool looks for `mentions`) and politics/tech/sports tags win first. Mentions markets are
identified here by tag slug containing "mention" or a whole-word say/says/said/mention in the slug (`split.py`).

Rule fixed in `protocol.md` before any wallet table: >= 400 lifetime markets, average fill <= ~$200, rebates < 25%
of kept, positive all-time, 2 of the last 3 months positive, then at least 30 mentions markets in the window. Only
five accounts passed with real mentions activity; the window was widened to 45 days for the deep pass.

| account | wallet | mentions markets 45d | share of its turnover | why chosen |
|---|---|---|---|---|
| oidocrop | 0x23c46463c281deb26a041fdcc24ae9c5d7629c42 | 293 | 81% | the only leaderboard account that is mostly mentions; 13 of 13 months positive |
| QuantDeLaFugazi | 0x66c1a6fe836ff555ca32848646acedbbe93bfa3f | 176 | 32% | #9 on the all-time mentions board ($109.9K), fastest taker on the tape |
| Faston | 0xa7fea388f955a9517067111030eb771c6d911f3e | 256 | 22% | smallest tickets ($34 median per market), 9 positive months in a row |
| -Dominus- | 0x5415c298dde8c84f4ba726d36b411df6e9a72a6e | 134 | 46% | 14 of 14 months positive |
| jkerkela | 0xde18162d38cd41fd8c27872584d9451120427ca8 | 64 | 10% | pure taker, No side, bot-like schedule; only 2 months old |
| 0xtrador (contrast, breaks the rebate rule: 48%) | 0x80ed3442ee13ca855d90cf78cede3ad3f66ece26 | 360 | 51% | small two-sided maker |

Found on the tape, not on the board selection, checked briefly: BipBop (0x9ba43501360dcacaca09caa523401c7447d8f8c2),
0xCc97... (0xcc97bbe4aec6a9797100211eb206f62f443e79b7), alsdkfjasd (0xc6cb9289841eace1219abc274c4c6c6d07167926).

Skipped, with the reason:
- 033033033 (top of the board, $21.3K month): whale, $5,243 average fill, 0 mentions markets in the last 14 days.
- 0x9112edc7...: $457 average fill, 0 mentions markets in 14 days, -$185K in the same 14 days elsewhere.
- DrSlips: lifetime -$34.7K. KawaiAngel: 11 markets in total. telesns, 71.btc: 34 markets in total.
  elon-forever: new and -$10.9K. PeruvianPuffPepper: 3 mentions markets in 14 days.
- SmallFishInWhaleStomach ($1,939 fills), welcometowinnercircle ($2,801), yen4u ($563, 6 mentions markets): whales.
- Dragontree (all-time mentions $85.5K): 0 mentions markets in 14 days, -$15.8K in that window.
- ENORMOUZ: 4 mentions markets in 14 days (but shows up within 10 s in 10 jumps - an occasional listener).
- AiBird (64% rebates; 13 mentions markets = 2% of turnover), spxtest (84% rebates; 6%), Haradwaith,
  tradetosurvive1, pootytherewardfarmer, chessplayer: rebate/reward farms, mentions is incidental.
- Mandalorec (4 mentions markets), CosmicCedar (8), 0xF1635E (1), QuantDe-like names lower on the board: too few.

## Tool totals against "API says" (14-day run of pmlab.wallet)

| account | tool net | API kept | gap explained by |
|---|---|---|---|
| oidocrop | 603 | 633 | agrees |
| QuantDeLaFugazi | 631 | 1,481 | 14 unresolved + 3 incomplete markets (tool leaves them out; API marks them to market) |
| Faston | 912 | 2,145 | 45 unresolved + 8 incomplete |
| -Dominus- | 743 | 1,506 | 15 unresolved/incomplete of 40 |
| jkerkela | 1,397 | 4,567 | 78 unresolved of 175; account shows $2,172 unrealized |
| 0xtrador | -7 | 157 | rewards/rebates and unresolved |

The cause is stated from the counts, not reconciled dollar for dollar. The deep pass avoids the problem: each fill is
valued against the final outcome of its market (resolved markets only), so carried inventory does not distort it.
Cross-check against the leaderboard's 30-day mentions PnL: oidocrop 1,755 vs my weeks 45-48 = 1,238 plus part of
week 44 (673) - consistent; -Dominus- 1,514 vs 1,099 plus part of 316 - consistent; jkerkela 1,633 vs 670 plus part
of 1,083 - consistent; QuantDeLaFugazi 1,504 vs at most ~600 - NOT reconciled (it also trades mention-like markets
without the tag, e.g. "will a turkey audibly gobble", "will Trump publicly insult someone").

## Per-account results (45 days to 2026-11-27, mentions markets only, after fee)

Phases: PRE = before the scheduled start; LIVE = after the start, before the jump; JUMP = from the last print below
0.60 to 60 s after the first print >= 0.90 that held; POST = later. For No-resolved markets the "determination" is
the first print <= 0.10 that held (soft). Files: `deep_<name>.txt`, `stories_<name>.txt` (14 markets each),
`extras.txt`, `monthly_<name>.txt`.

| | oidocrop | QuantDeLaFugazi | Faston | -Dominus- | jkerkela | 0xtrador |
|---|---|---|---|---|---|---|
| resolved markets / events | 292 / 64 | 175 / 42 | 245 / 68 | 123 / 38 | 59 / 18 | 347 / 45 |
| turnover | $47.2K | $31.4K | $13.5K | $49.3K | $9.8K | $35.2K |
| net after fee | +$2,708 | -$975 | +$1,218 | +$11,680 | +$1,885 | +$1,502 |
| markets won | 289/292 | 148/175 | 165/245 | 87/123 | 41/59 | 248/347 |
| t by market | 3.1 | -0.6 | 2.3 | 1.2 | 2.7 | 3.0 |
| positive events | 62/64 | 32/42 | 43/68 | 25/38 | 14/18 | 34/45 |
| positive weeks | 7/7 | 4/7 | 5/6 | 5/7 | 4/5 | 6/7 |
| PRE pnl (usd) | +7 (0.1K) | -220 (4.9K) | +835 (5.0K) | -34 (6.8K) | +1,525 (6.7K) | +493 (4.7K) |
| LIVE pnl | +1,081 (4.2K) | -1,669 (5.6K) | -183 (0.5K) | +10,878 (11.8K) | +13 | +351 (5.5K) |
| JUMP pnl | +877 (17.7K) | +823 (13.4K) | +235 (1.3K) | +689 (3.4K) | -26 | -274 (2.4K) |
| POST pnl | +244 (24.2K) | +156 (7.1K) | +404 (5.5K) | +135 (23.1K) | +272 (2.2K) | +691 (21.2K) |
| maker share of fills | 32% | 27% | 32% | 43% | 0% | 59% |
| shares sold / bought | 0.14 | 0.16 | 0.01 | 0.66 | 0.04 | 0.37 |
| median / max $ per market | 98 / 4,268 | 123 / 2,124 | 34 / 519 | 70 / 28,190 | 36 / 1,783 | 42 / 1,057 |
| most markets in one day | 26 | 27 | 34 | 21 | 8 | 37 |
| $-weighted hours buy -> resolution | 7 | 9 | 30 | 13 | 42 | 13 |
| peak capital tied up | $2.7K | $2.3K | $1.9K | $9.5K | $5.2K | $1.1K |
| markets with a buy >= 0.95: wrong side | 2/265 | 4/119 | 1/53 | 0/18 | 0/0 | 0/117 |
| pnl of those buys | +0.6% | -2.0% | -1.5% | +2.2% | - | +2.1% |
| clean jumps traded; first long-Yes fill <= 10 s | 48; 18 | 49; 26 | 35; 1 | 34; 6 | 12; 0 | 59; 3 |
| lifetime kept / volume | $17.8K / $591K | $154.9K / $1.28M | $13.9K / $356K | $44.4K / $1.13M | $7.1K / $96K | $4.3K / $572K |
| months positive | 13/13 | 18/23 | 9 in a row | 14/14 | 2/2 | 9/13 |

### oidocrop - verifies, then buys the decided side; profit is from the disputed and counted ones
- What it does: listens to the event (active 17:00-02:00 UTC, the US speech and earnings hours), buys the side that
  has just been decided, mostly as taker (316 taker buys, $33.7K), holds to resolution (7 h weighted), sells some
  winners at 0.999 as maker to free capital. Up to 26 markets a day, $98 median per market, $2.7K peak capital,
  capital turned 15 times in 45 days.
- Where the money is: buys at >= 0.95 are 71% of its dollars and produced +$214 (0.6%). Buys of the eventual winner
  between 0.05 and 0.95 were ~$7.6K in about 45 markets and produced about +$2,760; losers at those prices cost
  about -$190. That is more than 90% of the $2,708. Two wrong confirmations cost -$300.
- Falsification: (a) "it buys after the outcome is determined" - 94% of its >= 0.95 buy dollars are in JUMP/POST:
  holds. (b) "its profit is that carry" - fails: 0.6% on $33.6K. (c) "it is fast at cheap prices" - fails: a taker
  fill below 0.90 inside the jump window in 6 of 208 Yes markets; in 48 clean jumps its first fill came <= 2 s after
  the first print in 11, 3-10 s in 7, 11-60 s in 5, 1-10 min in 10, later in 8; median price paid 0.987.
- Sampled stories (`stories_oidocrop.txt`): Trump Lubbock rally "Two Percent" ($308K market): bought 2,000 Yes at
  0.712 at start+3h27m while the market argued whether it had been said; first print >= 0.90 that held came 7 h
  later, resolution 4 days later: +$600. Caedrel "Dive 7+ times": resting bids filled at 0.07-0.09 and 0.39-0.71 a
  day before the count was accepted: +$473. Trump "60 Minutes" extended interview "Biden/Kamala/Obama 7+": bought
  100-lots at 0.12, 0.16, 0.37, 0.45 within 34 seconds, then 0.98 ten minutes later (a published interview, counted
  from text): +$293. Bank of America "Inflation 3+": its two fills at 0.839 and 0.961 ARE the first prints after the
  third mention: +$117. Trump Cape Canaveral "Drone": first print >= 0.60 at 23:25:36, its fill at 23:25:39 at
  0.979: +$4. Robinhood "Weekend": bought 300 Yes at 0.985, two minutes later the market fell to 0.25 and it bought
  No at 0.51: -$183 (a wrong confirmation).
- Time gap: none that can be measured in seconds; it is a verification edge (rules reading, counting, hearing it
  right) with a hold of 2-7 hours to resolution.
- To copy: watch the live stream or call yourself, a word list per event, the rules PDF, fast manual or scripted
  order entry; $1K-$3K. Fee 0.01 (0.02-0.05 cents per share at 0.95-0.98). Absorbs a few thousand dollars.
- Risks: one wrong confirmation costs 30-60 right ones at 0.98; disputes can lock capital for days; thin books.
- Confidence 4 (292 markets, 64 events, 13 positive months).

### QuantDeLaFugazi - fastest taker on the tape, profit depends on directional calls
- First long-Yes printer in 11 of 131 clean jumps, within 10 s in 26, median price 0.972. JUMP phase +$823 on
  $13.4K (100 of 100 markets won). But LIVE and PRE directional bets lost $1,889 in this window (e.g. Yes 1,000
  shares at 0.82 on "Russia/Ukraine" at a Georgia rally a day ahead: -$1,227), and 4 of 119 confirmations were wrong.
- Net -$975 in 45 days, 4 of 7 weeks positive. Lifetime +$154.9K, 18 of 23 months positive, all-time mentions
  +$109.9K on $1.34M: the long record is real, the last 45 days in mentions are not.
- Falsification: "speed makes the money" fails - its first-10-second fills locked in $295 in 8 weeks.
- Time gap: seconds after the word for the jump part (a human or light tooling with pre-staged orders); the rest
  is a model/judgment edge that did not show in this window.
- Confidence 3 (175 markets; mechanism clear, profitability in the window negative).

### Faston - many $30 bets before the event, holds everything
- 220 of 392 fills are PRE (median 30 hours before the start), $34 median per market, never sells (0.01).
  PRE +$835 on $5.0K; maker buys +24% on $3.1K, taker buys +4.3% on $9.6K. Wins 165 of 245 markets.
- Falsification: "base-rate edge, positive in 2/3 of events" - 43 of 68 events (63%), just under the bar I set.
  Its Yes picks returned +12.6% where buying Yes on all 550 sibling markets returned -17.9%; No picks +30.8% vs
  +13.6% blind. So it selects, but the sample is 52 events.
- Other business is of the same kind (weekly tweet counts, handshake length).
- To copy: a word-by-speaker history table and patience; $1K-$2K; 30-hour holds. Confidence 3.

### -Dominus- - discretionary live trader; one market is 85% of the result
- +$11,680, of which +$9,883 is one market (Trump "Star", Georgia rally, $293K volume): bought Yes at 0.23-0.76
  for 50 minutes while the price swung, 2,500 more at 0.37 four minutes before the word, sold 19,012 at 0.999.
  Without it: about +$1,800 on 122 markets. PRE bets lost slightly. Sells 66% of what it buys (trades in and out).
- Falsification: "systematic" fails - t by market 1.2, and a single market decides the window.
- 14 of 14 months positive in all categories, so the person is good; the method is not a rule one can copy.
- Confidence 2.

### jkerkela - scheduled taker that buys No a day ahead
- 67 of 110 fills are PRE buys of No, taker only, median 14.6 hours before the start, at 0.44-0.88; fills repeat at
  ~3h10m intervals (05:36:58, 08:46:40, 11:55:49 on 17 Nov), which looks like a scheduled job. 30 of 39 No markets
  won, +$1,620 on $5.9K (+27%). Its Yes buys lost (-11%).
- Falsification: PRE carries 81% of the profit and 14 of 18 events are positive: holds. Against luck of the event:
  blind No on all 234 sibling markets of the same events made +7.8% (+-4.4); its picks made +27%.
- Weak points: 59 markets, 18 events, one event (Trump-Xi-Putin meeting) gave $654; the account is two months old
  and holds $2.2K unrealized; mentions is 10% of its turnover (the rest: Truth Social post counts, diesel, macro).
- To copy: word/speaker base rates and a cron job; $2K-$5K tied for 1-2 days. Confidence 2-3.

### 0xtrador (contrast) - small maker, pays for it during jumps
- 59% maker. Earns on PRE maker No (+$481 on $1.6K), PRE taker No (+$290), POST taker No at ~0.97-0.99 (+$308 on
  $10.4K, 108 of 113 won), and loses when the word is said: 92 maker fills left it long No inside jump windows,
  -$333; plus -$109 as taker. Net +$1,502, t 3.0, 6 of 7 weeks positive, peak capital only $1.1K.
- Lifetime only +$4.3K on $572K (0.76%), 48% of it rebates/rewards, and $7,952 of $8,636 fees were refunded: the
  account depends on programs a new account does not get. Confidence 3.

### Fast listeners found on the tape (brief)
- BipBop: 100% mentions, 41 markets, first print in the jump (median lag 0 s, median price 0.938), sells the same
  shares at ~0.99 instead of waiting (sold/bought 0.98), 39 of 41 won, +$419 in 45 days. Lifetime +$57.4K on $705K,
  but shrinking every month since July ($4.1K, $0.7K, $1.4K, $0.4K, $0.2K) with volume down from $49K to $1.5K.
- 0xCc97...: $5 median stake, first printer in 10 of 10 jumps it traded, 3 of 29 confirmations wrong (10%), LIVE
  fills 11 of 19 right - the profile of an automatic trigger with false positives; +$144; idle in November.
- alsdkfjasd: median lag 3 s, price 0.98, 0 of 31 wrong, +$79; idle in November.

## Category-wide tests (`category.txt`, `fast.txt`, `pre_event.txt`)

Universe: every sibling market of the 95 events the studied accounts touched, resolved 0/1: 1,382 markets
(806 live, 351 earnings calls, 225 weekly/monthly), 29 Sep - 23 Nov 2026, 49.3% resolved Yes, $2.42M volume.
Events split by date at 27 Oct: TUNE / TEST.

- R1 pre-event calibration by price bucket: no stable blind edge; the sign of "buy No" at 0.40-0.60 flips between
  halves (+10% then -12%).
- Variant 4 (exploratory): single-mention markets priced 0.05-0.50 before the start are overpriced on Yes in both
  halves and in both event types: live 0.28 price vs 23% / 21% Yes; earnings 0.27 vs 19% / 23%. Buying that Yes
  returns -30% / -47% (live) and -44% / -38% (earnings); buying No with 2 cents of slippage returns +5.0% +-7.1 /
  +5.1% +-5.9 (live). "N+ times" markets do not show it. A lead, not a result.
- R3 follow the confirmation: test half, Yes: -1.8% at the print itself, -0.2% 5 s later, -0.9% 30 s later;
  No: -1.4%, -2.8%, -3.6%. Tune half looked positive (+1.2%) - it does not survive.
- R4 false confirmations: 29 of 695 Yes, 11 of 670 No. Typical: earnings calls (Airbnb "Code", AMD "China",
  Netflix "Tiktok/Youtube", Robinhood "Weekend"), weekly "post" markets, the 60 Minutes interview.
- R5 jump anatomy: numbers in the short answer. Resolution comes a median 2.1-2.4 hours after the confirming print.

## What was checked and what could not be

Checked: 9 accounts, 45 days, 1,700+ account-markets; 1,382 market tapes; monthly history of all nine.
Variants run: split (1), deep (2, eleven accounts), stories (2b), extras (2c), category (3), fast (3b), pre_event
(4, exploratory), plus three inline look-ups (mid-price buys by lag, wrong-confirmation count, mention-filter
check). No rule was changed and rerun.

Could not check:
- When the word was actually spoken. There is no transcript or audio with timestamps here, so every lag is measured
  from the first print on the tape, i.e. from the fastest trader, not from the utterance.
- Who sold at 0.90+ right after the word: the tape names only the taker.
- Book depth at the time: "available" means prints that happened.
- The whole category: the universe is the 95 events these accounts touched.
- The mentions fee before 2026-11-20 (0.01 is used throughout).
- QuantDeLaFugazi's leaderboard month figure against my fill-based figure.
- The post-timestamp gap on "Will Elon/Trump post X" markets (55 such markets are in the universe).

## Sceptic's check

Added 2026-11-27 by a second reader whose job was to break the three highest-confidence write-ups: oidocrop (4),
QuantDeLaFugazi and Faston (3; five accounts tie at 3, taken in table order, so 0xtrador and BipBop are NOT
re-tested). Rules were written first in `sceptic/protocol.md`. Code and outputs are in `sceptic/`
(`sceptic.py`, `post.py`, `bench.py`, `out_<account>_<window>.txt`, `w1_*.txt`, `monthly_*.txt`). Read-only.

Windows: A = the analyst's 45 days (13 Oct - 27 Nov); W0 = the 45 days before it (29 Aug - 13 Oct); Wm1 = the
45 days before that (15 Jul - 29 Aug). Wm1 was NOT in my protocol: I added it after seeing W0, because W0
overlaps the months the selection rule looked at (September, October). Same definitions as `deep.py`, fee 0.01.
Run on window A, my script returns the analyst's figures exactly (2,708 / -975 / 1,218; 2 of 265, 4 of 119, 1 of
53 wrong confirmations; blind Yes -17.9% on 550 siblings), so every difference below is data, not rules.

| mentions only, after 0.01 fee | Wm1 | W0 | A (analyst) | 135 days pooled |
|---|---|---|---|---|
| oidocrop net / t by event | +1,103 / 2.4 | +333 / 0.9 | +2,708 / 2.9 | +4,144 / 3.7 (169 events) |
| - buys at >= 0.95 | +447 on $26.6K, 1 wrong of 164 | +304 on $23.7K, 1 of 234 | +214 on $33.6K, 2 of 265 | +965 on $83.9K (1.15%), 4 of 663 |
| - buys below 0.95, winners and losers together | +543 on $4.5K | +5 on $4.6K | +2,694 on $7.6K | +3,242 on $16.7K |
| - without its 3 best markets | +413 | +94 | +1,342 | +2,726 |
| QuantDeLaFugazi net / t by event | +5,254 / 1.3 | +4,569 / 1.6 | -975 / -0.6 | +8,674 / 1.6 (152 events) |
| - without its 3 best markets | +110 | +789 | -2,140 | +718 without the 5 best events (t 0.2) |
| - clean-jump taker fills within 10 s | +159 | +293 | +295 | |
| Faston net / t by event | +1,451 / 2.7 | +1,997 / 2.1 | +1,218 / 2.2 | +4,719 / 3.8 (248 events) |
| - PRE fills | +962 | +1,551 | +835 | |
| - without its 3 best markets | +1,117 | +1,631 | +821 | +3,226 without the 5 best events (t 3.1) |
| - events positive | 45 of 73 | 71 of 118 | 43 of 68 | 62% |

The suggested command (`pmlab.wallet --days 14 --end 2026-11-06`) lies inside window A and only checks the tool:
oidocrop +757 (API 733), QuantDeLaFugazi +6,281 (API 5,997), Faston +1,366 (API 1,309), all categories.

### Problems that affect the whole study
1. The fee was not 0.01. Measured on oidocrop's own activity rows (`usdc_size` minus shares x price, mention
   markets only): 0.0400 from September to 19 October and 1-20 November, zero on 20-31 October, 0.0100 from
   21 November. The three accounts' blended charges agree (implied 0.033-0.042 in W0). Every "after fee" figure
   of the study before 21 November is slightly too high (W0: oidocrop -$30, Faston -$198, QuantDeLaFugazi -$348),
   and the zero-fee fortnight sits inside window A. For us today's 0.01 is the right number.
2. The JUMP phase is defined only in markets that resolved Yes, so "jump-phase taker buys won 100 of 100" is true
   by construction. A buy at 0.92 after a spike that later collapsed is booked under LIVE (oidocrop "Job 20+
   times" -$280 and "Ukraine" -$93 in W0, QuantDeLaFugazi "Rural" -$416 in A). Read the price-band tables, which
   do not condition on the outcome, not the phase table, when judging the confirm-and-buy leg.
3. For weekly and monthly "period" events the gamma start is the END of the period, so "PRE" fills there were
   placed while the count was running. That is 22%, 54% and 21% of Faston's PRE profit in the three windows
   (W0: +$833 of +$1,551).
4. Selection: the accounts come from a winners' board (141 screened, 5 passed) and the rule required positive
   recent months. W0 overlaps those months; Wm1 does not, but "positive all-time" still does. The only clean test
   is forward.
5. Leaderboard category figures are not usable: QuantDeLaFugazi's "all-time mentions" volume ($1.34M) is larger
   than the account's lifetime volume ($1.28M).

### oidocrop - WEAK (profit is real, the explanation of where it comes from is not)
- Reproduces: buys the decided side and holds (94-98% of its >= 0.95 buy dollars are after the determination in
  all three windows), 76-83% of turnover in mentions, 4 wrong confirmations in 663 markets, positive in every
  window, 13 of 13 months, 0% rebates, no splits, no fee group shared with the other eight wallets.
- Does not reproduce: "more than 90% of the profit is from buys below 0.95" and "'profit is that carry' fails".
  Below-0.95 buys made +$543, +$5 and +$2,694. In W0 the account lost on them outside the jump (LIVE and PRE
  taker buys -$672) and the whole window was +$333 (t 0.8 by market, bootstrap interval -426..+978), which fails the bar I
  set in advance. The 0.97-0.99 buys are the leg that is positive in all three windows: +1.7%, +1.3%, +0.6% of
  dollars, $965 in 135 days on about $2.7K of capital.
- Raw re-derivation (ten markets, fresh tapes; fresh and cached row counts equal, its taker fills are on the tape
  at the same second): the analyst's stories are accurate. Two Percent 2,000 Yes at 0.712 at start+3h27m, price
  0.46 just before, so its own order walked the book; one bet is 22% of the window. BoA "Inflation 3+" 666 at
  0.839 and 284 at 0.961 are the first prints. "60 Minutes" 100-lots at 0.121, 0.157, 0.368, 0.447 in 34 s from a
  0.03-0.10 market: it was first to act on a published text. Robinhood 300 Yes at 0.985, -$183 after a hedge.
  W0: "Million/Billion/Trillion 25+" 900 at 0.889-0.890, also the first prints.
- On speed: in W0 and A it is the first print in 6 of 29 and 10 of 29 clean jumps it traded, and within 10 s in
  about half, but its fills inside 10 s earned +$64, +$169, +$66 in the three windows. The analyst's "speed pays little" holds; "no gap measurable in
  seconds" is too strong for a trader who is often first.
- Corrected mechanism: a verifying carry trade (about 1.2% per turn, error rate 0.6% against roughly 1.5-2% at
  break-even and 4.2% for blind followers) plus an irregular discretionary leg on disputed and counted markets
  that made nothing in one window of three and two thirds of everything in another.

### QuantDeLaFugazi - WEAK (behaviour reproduces, profit is a few large bets)
- Net in mentions +5,254, +4,569, -975; t by event never above 1.6; bootstrap intervals include zero in every
  window. Without the three best markets of each window: +110, +789, -2,140. The winners are large pre-event Yes
  buys at 0.12-0.45 ("Transgender" +2,073, "Ammunition" +1,749, "Supreme Court" +1,622, "Drone" +1,449, "Epic
  Fury" +1,163, "Ass" +867). The analyst's reading (fast taker plus directional bets, not a rule) stands.
- Speed: clean-jump fills within 10 s earned +159, +293, +295. The analyst's $295 reproduces out of sample.
- Confirm-and-buy is about zero: buys at >= 0.80 made +977, +1,340, -1,573; 7 wrong of 410 at >= 0.95 (1.7%).
- The lifetime record is not a mentions record. Mentions were 76%, 42%, 32% of turnover in the three windows and
  non-mention markets made +11.8K, +3.4K, +8.3K before fees (Iran ceasefire +4.9K, "Trump renames AI", "White
  House full lid"); November's +$17.9K is outside mentions. It also splits and merges $61-76K per window (the ten largest in W0 and in A are all
  2028-election markets), so "capital in use about $2.3K" describes mentions only.
- Monthly: 19 of 25 active months positive (the write-up says 18 of 23), losing months of -8.1K, -6.9K, -5.6K.

### Faston - SUPPORTED, with corrections (and a declared departure from my protocol)
- Profit reproduces in all three windows (t by event 2.7, 2.1, 2.2; every bootstrap interval above zero), is not
  concentrated (best event of 248 is under 10%), PRE fills carry 66-78% of it each time, positive every month
  since March, rebates 2%, 11 unresolved markets in A are marked +$337.
- Selection against a blind baseline reproduces out of sample for Yes: in W0 its pre-event Yes picks (live and
  earnings events) returned +6.4% on $8.0K where buying Yes on all 840 sibling markets returned -17.0% +-4.1.
  For No it does not: +6.5% on $3.0K against -0.3% +-7.0 blind (window A: +23.7% against +13.6% +-9.0).
- Two of my four advance criteria fail and I report them rather than hide them: events positive 60-63% in every
  window (the analyst's own 2/3 bar), and shares sold/bought 0.21, 0.08, 0.01. I read both as errors of
  description, not of mechanism, and keep SUPPORTED.
- Corrections: it is mainly a Yes picker (69-85% of pre-event dollars), not one of the "No a day ahead"
  accounts of the summary. Median lead was 100 hours in W0 and 30 in A. It does not "never sell": it bought both
  outcomes in 83 of 545 markets in W0 and merged $4.1K, $6.1K, $5.3K. The maker edge is not stable (pre-event
  maker buys +2.9% in W0 against +24% in A). Part of "PRE" is in-period trading (point 3 above); pre-event fills in live
  and earnings events alone made +$746, +$719, +$659.
- Limits for copying: its taker orders walk the book at about 50 shares per cent (NVIDIA "AI 40+" 50 shares each
  at 0.82, 0.83, 0.84, 0.85), many of its markets have $200-$900 of total volume, and what produces the picks is
  still unknown. It also earns outside mentions (+$0.6K, +$1.8K, +$4.0K before fees in the three windows).

### Alternatives considered
Luck on a few bets: decisive for QuantDeLaFugazi, partial for oidocrop's below-0.95 leg, not for Faston.
One operator, several wallets: the nine wallets have nine different `wv_30d` values, taker and maker. Rebates and
rewards: 0%, 1%, 2% of what was kept. Hedges elsewhere: none visible on Polymarket; other venues cannot be seen.
Inside information: cannot be tested; oidocrop's "60 Minutes" sweep is the only case that looks like being first
to a source. Survivorship: not removable here (point 4).

Count of variants: `sceptic.py` 9 runs (3 accounts x 3 windows, one window added after the fact), `post.py` 1,
`bench.py` 1, `pmlab.wallet` 3, `wallet_check.py --monthly` 3, one tier query, one fee measurement. No rule was
changed and rerun.
