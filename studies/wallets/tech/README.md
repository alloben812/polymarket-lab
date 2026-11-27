# Tech category: how the consistently profitable accounts make money (study of 2026-11-27)

Window for the deep work: 88 days, 2026-08-31 16:00 .. 2026-11-27 16:00 UTC. The 14-day `pmlab.wallet` runs asked for in
the assignment are in `<name>.txt/.json`; they cover too few resolved markets to be useful here (these markets have
end dates months away and resolve early, so the tool's "time to end" table reads "over 7 d" for almost every fill and
its totals miss the API by 70-95%; see "Tool vs API" below). Everything was fetched from the public Data API / gamma.
Fees: 0.05*p*(1-p) applied to every taker fill (the real rate was 0.04 before Nov 20 and zero on Oct 20-31, so fees here
are slightly overstated). Protocol and the rule tested: `protocol.md` (written before the fills were opened; the
follower rule was added before `follower.py` was run).

## 1. What "tech" is on Polymarket right now

By the turnover of the seven accounts (`rules.txt`, `overview.txt`):

| family | what decides it | example |
|---|---|---|
| debut score / rank | score or rank on arena.ai Text Arena "at 12:00 PM ET on the calendar date FOLLOWING the date on which the model first appears on the leaderboard" | "Will Kimi K3.1 Pro debut at a score of at least 1480?" |
| HLE-Diamond debut | same rule, source agi.safe.ai | "Will Gemini Carbon debut with an HLE-Diamond score of 65% or higher?" |
| month-end rank | arena.ai lab/model rank at 12:00 ET on the last day (Text, Text style-control-on, Math, Code WebDev, Agent, Chinese labs; #1/#2/#3 of each) - about 1,000 negRisk legs alive at once | "Will Google be the #3 AI Lab at the end of October 2026 (Style Control On)?" |
| release dates | official announcement + consensus of reporting | "Next Astra Model (6.1+) released by October 31?" |
| company news | Jensen Huang / Nvidia succession, Anthropic IPO and valuations, GPU rental prices, OpenRouter shares | whale territory |

The debut rule is the structural point: the deciding number is public on the leaderboard for 12-36 hours before the
check, and it can still drift a few points in that time. Thresholds far from the debut score are decided the moment
the model appears; thresholds within a few points stay uncertain until noon ET the next day.

## 2. Selection

`leaders.txt` (133 accounts) -> rule in `protocol.md` -> 71 candidates -> `screen.txt` (30-day tech share by gamma tags).

Studied (7): **iutwpfal, lamyk, KimchiCapital, NoTeacher, 0xAee8611B (profile name "0xAee8611B76c7e8114"), fountaim, melonmanm**.

Skipped, with the reason:
- xtxpleasecallme (category month +293K): 1.54M fills, 53% of what it kept is rebates; a volume-tier bot, tech is a by-product.
- pleaseletmealone (+188K): 5% tech in the screen, one month old.
- 0x9112edc7 ($430/fill), dromedaryy ($1,387/fill), Dragontree ($602), AllByMyseIf ($305), WarriorPooh ($372), aviato
  ($565), noreasapa ($1,789), 0xAD96914D ($4,259), 0xe639e410 ($847), BigMackyG ($1,114), seal7, GollumGekko: whales;
  their tech turnover is Jensen Huang succession / Anthropic IPO / GTA 6 news in fills of hundreds to thousands of dollars.
- glpgb, anoin123, The-Joker, Contentious-Dinnerdate, BigMackyG: fail "two of the last three months positive".
- TableDataFormat, 1nvoker1: GPU-rental-price market makers (rebate share 15-37%, 146K fills), a different niche.
- 71.btc, 0x62D56a93, 0xc023bee9, plimzo814, uldon33, badonde1: under 150 markets and under 1,500 fills.
- Two wallets that the race table (section 4) shows to be the fastest snipers were NOT on my list and deserve a
  follow-up: 0x09e27c2cbcd98c7e821ef66b309506701dcf29de (kept 47.0K on 1,811 fills) and
  0xa7d2ec6680f4e5f6ab0da244d8006eec3e20f954 (kept 30.8K, 11,375 fills); also 0xA2770432... (kept 17.2K, 100% tech).

## 3. Numbers (88 days; API bottom line; tech sub-families from `overview.txt`)

| account | kept 88 d (API) | volume | fills | markets | tech share of turnover | taker share (tech) | months positive (kept) | rebate share all-time |
|---|---|---|---|---|---|---|---|---|
| iutwpfal | 63,442 | 407,740 | 2,203 | 330 | 95% | 90-95% | 10 of 11 | 3% |
| lamyk | 22,216 | 202,299 | 839 | 283 | 80% | 70-89% | 8 of the last 8 | 3% |
| KimchiCapital | 36,487 | 316,790 | 2,199 | 897 | 59% | 85-97% | 11 of 11 since Jan | 2% |
| NoTeacher | 6,338 | 159,006 | 3,717 | 498 | 98% | 63-87% | 7 of 8 (two of them only through rewards) | 24% |
| 0xAee8611B | 35,575 | 455,033 | 28,855 | 1,374 | 98% | 82% | 10 in a row since Feb | 12% |
| fountaim | 12,336 | 37,837 | 236 | 175 | 83% | 98-100% | 7 of 7 | 0% |
| melonmanm | 81,528 | 1,008,369 | 7,662 | 892 | 34% | 22-93% | 7 of 8 | 3% |

Tool vs API: over 88 days the tool's resolved-and-complete markets explain 53.7K of iutwpfal's 65.4K gross, 11.0K of
fountaim's 12.7K, 31.0K of KimchiCapital's 38.0K, 71.3K of melonmanm's 82.0K, 10.5K of lamyk's 22.7K (it has 8.7K
unrealized) and only 3.5K of 0xAee8611B's 36.6K (148 resolved markets are "incomplete" because it carried inventory
in and it merges constantly: 3,480 merges; with those markets included its resolved arena net is 8.4K). The 14-day
tool totals were 8-80% of the API's for the same days for the same reasons (positions carried in, merges, 80-550
markets still open). So tables below use the 88-day window and say how many markets they rest on.

## 4. The time gap in debut markets, measured on the tape

`race.py` (279 whole-market tapes of the resolved arena/HLE markets these accounts traded; 115 are debut markets in 32
event groups; total volume of those 115 markets $2.9M, median market $15K). "First sweep" t0 of an event = the earliest
moment, on the ET calendar day before the check, at which two sibling markets settle above 0.90 on the eventual winner
within 15 minutes (or one market jumps by more than 10 cents). Found in 20 of 32 groups (`race.txt`).

Gap money = taker buys of the eventual winner below 0.97 between t0 and the check, edge = 1 - price (`check3.txt` (2)):

| seconds after the first sweep | edge taken | share | wallets | cents per share |
|---|---|---|---|---|
| <= 3 s | $12,002 | 85% | 68 | 20.7 |
| 3-10 s | $95 | 1% | 12 | 6.4 |
| 10-60 s | $410 | 3% | 14 | 6.8 |
| 1-10 min | $409 | 3% | 40 | 5.4 |
| 10 min - 6 h | $979 | 7% | 76 | 5.8 |
| > 6 h | $217 | 2% | 18 | 6.5 |

- $14.1K in 12 weeks over 20 events is the whole pot in these tapes, and 85% of it goes in the first block or two.
  In all 21 sweeps of fountaim and lamyk another wallet bought the same winner within the same 0-2 s
  (`check4.txt` (a)); nobody enjoys minutes alone, on arena.ai or on the HLE page.
- The @arena X account is not the trigger: its "now in the Arena, scores coming soon" posts come about two days
  before the score row, and its debut posts come hours after the sweep (Opus 5.5: sweep Sep 26 01:32 UTC, post
  17:02 UTC, after the check) - `arena_tweets_vs_tape.txt`. The snipers read the leaderboard itself.
- Reversal after the jump: of 83 sibling markets, 10 minutes after the sweep 54 were at >= 0.97 on the eventual
  winner, 23 at 0.90-0.97, 6 undecided, 0 confidently wrong (`check3.txt` (3)). Zero reversals in 77 is an upper
  bound of about 5% (Wilson), which is the same size as the price discount, so "safe" is not established.
- What I could not measure: the time from the leaderboard update to the first trade (no archive of the page; t0 comes
  from the tape). Only the spread between traders (<= 2 s) is measured.

## 5. Accounts

Phase tables and 14 market stories per account: `phases_<account>.txt`. Sub-family table: `overview.txt`.
Concentration and drift: `deep2.txt`. First-mover test: `check3.txt` (1). Calibration by price: `check4.txt` (c).

### fountaim - leaderboard sniper (confidence 4)
- 236 fills in 88 days, all taker, 99% buys, one fill per market ($300-1,100), holds to settlement, 0% rebates, kept
  32% of its volume, positive in every month since it started (May).
- Debut markets inside the 40 h before the check: 32 fills in 32 markets, 32 right; the bought side was at 0.668 on
  the tape 10 s earlier, it paid 0.785, the tape was at 0.973 ten minutes later; 81% of the fills are within 5 s of
  the first trade of the burst; net $5.0K after fees.
- Story (Kimi K3.1 Pro, model appeared Nov 9): at 19:54:33 UTC it bought No on the >=1470, >=1480, >=1490 score
  markets and on the top-20 rank market in the same second at 0.754 / 0.865 / 0.914 / 0.864 (Yes had been 0.31 /
  0.16 / 0.08 / 0.13); all four went to 0.00 Yes; +$527. Gemini Carbon HLE >= 65% (Nov 12 00:35 UTC): bought No at
  0.234 while Yes stood at 0.88-0.96, 24 minutes before the rest of the market moved; +$1,984. Haiku 4.6 (Oct 22
  23:29:20): No at 0.766 and 0.942 on two thresholds, Yes had been 0.82 and 0.17.
- Same reflex elsewhere: "will any model reach 1520 Arena score" (bought Yes at 0.13 on Sep 2 23:24, sold at 0.83
  twenty-six minutes later), month-end rank legs after a rank change (11 buys, all right), private-company
  "valuation hit" markets after funding news.
- Falsification: "it buys after the outcome is visible" predicts right side ~100% and a price that jumps after its
  fill. Held in 32 of 32 fills (right side) and 26 of 32 (first within 5 s). Its 0.00-0.80 buys in all resolved tech
  markets win 87-92% (60 markets).
- Gap: leaderboard row -> market, a second or two wide. Fee paid 0.76 c/share against 20 c of edge.

### lamyk - sniper plus month-end rank positions (confidence 3)
- Debut sweeps: 11 fills in 11 markets in the first 60 s, all right, average price 0.669, +33 c/share, net $1,935.
  It does not hold: Astra (Sep 11 21:18:10) bought No at 0.537 one second after the first print and sold it as a
  maker at 0.95 sixteen minutes later.
- Month-end rank markets: 15 taker buys more than a day before the check at 0.25-0.46, 76-100% right, net about
  $6.4K (7 + 6 markets) - one event, "best AI model end of October", is $4.4K of it.
- Loses on what it sells before the appearance (-$3.7K on 14 markets). Top 3 events are 6.4K of its 7.2K arena net.
- Falsification of "sniper": 73% of its 15 late debut buys are the first trade of the burst; 93% right. Holds.

### KimchiCapital - slower follower / favourite buyer across categories (confidence 3)
- 59% tech. Buys the favoured side at 0.80-0.95 as a taker after the information is out and before the price has
  finished moving: Mistral Large 4 >= 1490, No at 0.930 for $4,901 55 s after the first sweep; Fable 5.2 HLE >= 70%,
  Yes at 0.943 for $5,377 sixteen hours before the check; Gemini Hydrogen HLE >= 35%, Yes at 0.949 71 minutes after
  the sweep.
- Calibration of its taker buys in resolved tech markets: price 0.86 -> wins 97% (73 markets); 0.93 -> 100% (58);
  0.96 -> 100% (53). Late debut buys: 18 fills, 18 right, pre-price 0.851, fill 0.861, +10 min 0.877 (it is not the
  one moving the price; only 50% of the fills lead a burst).
- Arena+HLE resolved net is only $1.6K of its 36.5K; the same favourite-buying in IPO/valuation, release-date,
  OpenRouter-share and non-tech (finance, culture) markets makes the rest (non-tech net 14.3K on 325 markets).
- Falsification: if it were a sniper its pre-price would be far below its fill price; it is not (0.851 vs 0.861).
  So: no speed, edge is choosing favourites that are underpriced by 5-10 cents. A model/judgment edge.

### iutwpfal - large pre-positioned forecasts of debut scores (confidence 2)
- $88K of taker buys placed a median 8 days before the model appears, at 0.42-0.47, 66-78% right, +30 c/share:
  $53.1K of its $56.5K arena+HLE net. In the last 40 h before the check it is right 48% of the time: not a sniper.
- Concentration: 50 events, 28 positive, top 3 = $42.5K (Fable 5.2 score $24.0K, Fable 5.2 rank $9.9K, Kimi K3.1
  $8.6K); November alone is $42.9K. Story: Fable 5.2 >= 1510, bought No at 0.16-0.22 on Oct 13-17 when Yes was
  0.74; Yes drifted to 0.56 an hour before the appearance (Nov 20 02:13 UTC) and to 0.01 after. Gemini Carbon HLE >=
  65%: bought Yes at 0.64-0.87, lost $4.7K.
- Its buys move the price: the tape is 4.6 c above its fill 10 minutes later and 3.8 c above after 24 h; settlement
  is 11.0 c above (304 fills, 49 markets). A copier keeps roughly half before the fee.
- What the information is I could not establish (models are testable on Arena for about two days before the score
  row appears, and earlier under code names; it may be forecasting from that). Effectively four bets decide the
  quarter, so this is a model/informed edge with a small sample, not a system I can verify.

### NoTeacher - small active trader of the same forecasts (confidence 2)
- $50-70 fills, buys 52% / sells 48%, 87% taker. Pre-appearance taker buys are right 70-74% and earn $7.2K; its
  taker sells are wrong 72-78% of the time and give back $5.1K (it sells winners early). Net arena+HLE $3.6K on 59
  events (39 positive, top 3 = $2.0K); 24% of everything it ever kept is liquidity rewards.
- Its buys do not move the price (+1.7 c after 10 min) and settle +10.4 c above the fill (410 fills, 55 markets).
- Mechanism: judgment about where a model will land, no speed. Closest in size to us, thin margin (3.7% of volume).

### 0xAee8611B - relative-value book across ~1,000 month-end rank legs (confidence 3)
- 28,855 fills ($15 average), 1,374 markets, 82% taker, active every day, 3,480 merges. Not a debut sniper: 2 debut
  fills in 88 days; its bursts (213 touching >= 8 markets within 10 s, a median 5 h apart, no clock pattern) coincide
  with debut sweeps 12 times out of 18 against a base rate of 54%.
- In 444 of 1,230 markets it bought both Yes and No, days apart (median 155 h); the pair cost averages 0.924 and 88%
  of the pairs cost under 1.00: it buys whichever side its numbers call cheap, later buys the other side and merges
  instead of selling. Also rests thousands of 1-2 cent bids on long shots.
- Month-end legs, more than 7 days before the check: taker buys $61K at 0.42, +5.2 c/share before a 0.9 c fee, 84
  markets; maker buys +3.0 c. Resolved arena net $8.4K on $127K turnover (incl. incomplete markets); September and
  October closes +$8.4K; 33 of 83 events positive, top 3 = $2.7K, so the result is spread out.
- Mechanism: a pricing model of leaderboard ranks (score gaps, vote counts, upcoming releases) applied to every
  overlapping family at once, plus consistency between them. Not a time gap; a model edge with market-making exits.

### melonmanm - news follower and bond buyer, tech is a third of it (confidence 2)
- Tech turnover is Jensen Huang / release-date / IPO markets. Buys at >= 0.95 a median 2.8 h before the close:
  $163K of cost in tech for +$232 gross (53 markets) - the bonds pay nothing after fees. Its money is Anthropic-IPO
  bucket markets (net $16.6K, 35 markets, bought at 0.44-0.80) and non-tech (net $43.1K, 481 markets).
- Not studied market by market; no leaderboard activity (2 arena markets).

## 6. The one rule I tested (Rule F, `follower.py`, 2 variants, both reported)

Buy the favoured side at 0.80-0.97 at the first print available D minutes after the first sweep, hold to resolution,
100 shares per market, fee included.

| D | entries | events | wins | net per 100 shares | per event (se) | earlier half / later half |
|---|---|---|---|---|---|---|
| 10 min | 17 | 9 | 17 | $6.02 | $11.4 (2.0) | $46 on 7 / $56 on 10 |
| 60 min | 12 | 7 | 12 | $5.40 | $9.3 (3.4) | $12 on 4 / $52 on 8 |

Attack on it: 17 markets in 9 events with no loss says nothing about a loss rate below ~16%; one loss costs 15 wins.
The trigger t0 is defined with the eventual winner (look-ahead in timing). The prints used as entries are small
(median 50 shares), so the capacity is tens to a few hundred dollars per market. Sample is the markets the seven
accounts traded. It is a candidate, not a result.

## 7. Variants run (all counted)

Screen 1; overview 1; appearance definitions 4 (trade burst in the last 60 h; burst on the rule-implied day; jump with
a 10-cent floor; cluster-or-jump, the one kept - the first three were dropped because sibling events of one batch got
different times or fountaim's own fills landed "before" the appearance); phase tables 3 (one per definition kept);
race 2; follower 2. No parameter was tuned on profit.

## 8. Not checked / open

- The leaderboard's own update times (needs a recorder polling arena.ai and agi.safe.ai; none exists in the lab).
- Whether the several wallets printed in the same second are independent pollers or followers of the first print.
- The whole debut universe (only markets these accounts traded were taped); debut events before September.
- Gemini Carbon text markets closed six days after the model's debut (dispute or late resolution); not examined.
- iutwpfal's source of conviction; 0xAee8611B's model; melonmanm market by market.
- Fees charged in reality (0.04 before Nov 20, zero Oct 20-31) were not reconstructed per fill.

## Files

`protocol.md`, `leaders.txt/json`, `screen.py/txt`, `<name>.txt/.json/.monthly.txt` (14-day tool runs, monthly),
`common.py` (88-day loader), `overview.py/txt`, `rules.py/txt`, `tapes.py`, `race.py/txt`, `phases.py` +
`phases_<name>.txt`, `deep2.py/txt`, `check3.py/txt`, `check4.py/txt`, `follower.py/txt`, `arena_x_timeline.txt`,
`arena_tweets_vs_tape.txt`, `appearance_proxy.txt` (superseded first proxy). Caches: `data/tech_wallets/`.
