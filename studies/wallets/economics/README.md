# Economics category: how the profitable accounts make money (study of 2026-11-27)

Window: 2026-08-31 .. 2026-11-27 (88 days) for wallets; 53 scheduled-release events of Sep-Nov 2026 for tapes.
Protocol written before the data: `protocol.md`. Everything below is public, read-only data.

## Short answer

1. **A time gap exists and it is 2-20 seconds long.** After a scheduled release (BLS/BEA 08:30 ET, ISM 10:00 ET,
   FOMC 14:00 ET, ONS, StatCan, central banks) the Polymarket bucket markets still fill at pre-release prices for a
   few seconds. Over 53 events: 263 taker fills on the winning side below 0.95, $69.7K notional, $20.8K profit;
   78% of that profit was taken within 15 s of the release and 98.8% within 60 s. After one minute nothing is left
   ($257 in three months). Block timestamps run 2-3 s late, so real matches are even earlier.
2. **The accounts that take it are small and specialised**, not the leaderboard names: TheElement115 (76 fills in
   88 days, every one a taker buy 2-40 s after a scheduled release, kept $0.7-4.9K a month) and road2million (same
   events, same seconds). The whole pool is about $7K a month across all snipers in the sampled events.
3. **The leaderboard accounts do something else**: they position days or weeks before the release from their own
   view of the outcome (perfectnostalgia), trade the Fed-path markets around data with holds of minutes to days
   (Ahpo, GoldmanSachs), run a two-sided book with a large balance sheet (ATCapital), or deal in sub-cent tails
   (jozeslemsek). None of the seven leaderboard accounts took a single taker fill in the 60 s after the release of a
   market it traded.
4. **"Buy the favourite" is not an edge by itself.** Prices 7 days, 1 day and 1 hour before the release are roughly
   calibrated (0.70-0.90 bucket: -3.2c, -0.1c, -2.7c per share after fee). The pre-positioning winners select.
5. **Carry after the release does not exist here**: the markets resolve about two hours after the number. The one
   exception in the sample (October CPI annual and core YoY, resolved ten days late) paid 2.6% on $25.7K.

## Selection

`tools/leaders.py economics --top 60` -> `leaders.txt`, `leaders.json` (136 accounts). The board is dominated by one
event: in the last 30 days `fed-decision-in-december` is the top economics event for 42 of the 54 screened accounts that traded economics at all (66 screened).
Screen (`screen.py`, `screen.txt`): accounts with >=150 markets or >=1,500 fills, kept_all > 0, two of the last three
months positive, rebates < 40%; last 30 days of fills (cap 4,000), share of turnover in economics-keyword markets.

Chosen (seven from the board, one found from the tapes):

| account | why |
|---|---|
| perfectnostalgia | 890 markets, 27K fills, $76/fill, positive 28 of 32 months, 66% economics, 36 economics markets in 30 days |
| GoldmanSachs (0x71dd2d53…) | 100% economics (Fed path), three positive months, small fills |
| ATCapital | 99.9% economics, 3,342 fills in 30 days, half maker |
| Ahpo | 3,292 markets, 92K fills, positive 16 months of 16, 42% economics |
| 0x831449c4… | 617 markets in six weeks, 56 economics markets (international CPI/GDP) |
| Stonktrader | trades the US CPI bucket markets directly, three positive months |
| jozeslemsek | $3 fills, 1,017 markets, nine positive months of nine: the only one at our capital scale |
| TheElement115 (+ road2million) | not on the board; top of the post-release taker table built from the tapes |

Skipped, with the reason:

- elmcap2 ($2.6M kept), The Spirit of Ukraine, Trump2028, mr.ozi, RememberAmalek, Hashbrown, nonkenny90, arjennnnn:
  economics is 0.2-22% of their recent turnover; the category number comes from one or two Fed tickets.
- hymolu, Votei14Voude22, Kevindoto, sabsabinxz, Tigerofthehood: zero economics-keyword fills in 30 days.
- b2d0 (3 fills, $48.9K each), welcometowinnercircle ($11.4K a fill, one Fed market), thegreengem ($47K a fill),
  0x62D56a93… (48 fills, 7 markets, $94K in one month), 0x6302CDeF…, Bukaj0889, TheyAreTakingTheHobits (4 markets),
  pako, Vilgefortz, TheReturnOfDarthMaul, foodenjoyer, classified: whales, a few large directional Fed bets.
- xtxpleasecallme (53% rebates, 1.5M fills at $11), truthteller (61%), timetowander, cigarettes, Haradwaith,
  ArmageddonRewardsBilly: rebate-driven volume accounts.
- simpleman, ratehikes, m00n, aijack90, S55, KimJonEn, HDGB, Donkov: passed the screen, not studied (budget). Donkov
  ($12 fills, +$1.5-2.3K each month, 22 economics markets) and HDGB (treasury-yield ladders) are the next to look at.

## Tool totals against the "API says" line

14-day runs (`<name>.txt`) are nearly empty for this category because economics markets resolve in bursts and almost
everything open now is the December Fed event. The 88-day runs (`<name>_88d.txt`) are the ones used.

| account | tool net, resolved complete markets (88 d) | API kept (88 d) | why they differ |
|---|---|---|---|
| perfectnostalgia | 23,879 (123 markets) | 35,010 | 33 markets open, 5 incomplete; FIFO: +3,166 sold early, +12,876 held to resolution in economics |
| GoldmanSachs | 708 (4 markets) | 21,009 | 16 of 23 markets open (Fed Dec/Jan); profit is realised by selling before resolution (FIFO +14,434) |
| ATCapital | -53 (6 markets) | 27,858 | 62 merges, 11 neg-risk conversions, 17 of 23 markets open, about $1.0M of inventory at cost |
| Ahpo | 17,894 (209 markets) | 42,992 | 125 open, 40 incomplete; 86% of economics buys are sold before resolution (FIFO +26,218) |
| 0x831449c4… | 5,722 (180 markets) | 52,316 | 437 of 617 markets open; $21.8K of the API figure is unrealised |
| Stonktrader | 62,774 (104 markets) | 72,058 | within 13% |
| jozeslemsek | -256 (205 markets) | 5,807 | profit is made inside markets that are still open (FIFO round trips +6,422) |

Monthly figures: `<name>.monthly.txt` (from `tools/wallet_check.py --monthly`).

## Release tapes: the time gap measured

Scripts: `list_events.py` (239 closed economics events Sep-Nov), `fetch_tapes.py` (419 market tapes, 163K fills, in
`data/econ_tapes/`), `release_analysis_v2.py` -> `release_analysis_v2.txt`, `release_results_v2.json`.
Method: for each event the release time is the scheduled one (table `SCHED` in the script). A fill counts as "stale"
when the taker ends up long the outcome that finally won at a winner-equivalent price below 0.95 at or after the
release. Profit = (1 - price) x shares minus a 0.01 fee rate.

| lag after release (block time) | fills | notional $ | profit $ |
|---|---|---|---|
| under 6 s | 69 | 22,427 | 4,472 |
| 6-15 s | 107 | 35,231 | 11,816 |
| 15-60 s | 60 | 10,505 | 4,280 |
| 1-5 min | 14 | 875 | 216 |
| 5-30 min | 2 | 35 | 4 |
| 30 min - 6 h | 0 | 0 | 0 |
| over 6 h | 11 | 670 | 37 |

- 42 of the 53 events had at least one market priced below 0.90 for the eventual winner just before the release.
  The other 11 (ECB, BoE, RBA, BoJ-type decisions, Fed October, October CPI annual) were already at 0.9+.
- First print at 0.95+ on a previously uncertain market: ISM 2-3 s, StatCan 3 s, ONS 4-5 s, FOMC 4-6 s, BLS and
  BEA 6-9 s (with a second wave at 15-20 s).
- Largest pots: core CPI m/m September $6.9K notional -> $6.7K (the favourite bucket lost), FOMC September $19.4K ->
  $2.1K, core PCE m/m August $2.2K -> $1.6K, UK CPI October $1.4K -> $1.2K, core CPI m/m October $2.7K -> $1.1K.
  Typical event: $0.3-3K notional, $20-600 profit.
- Who took it (profit in the first 60 s): TheElement115 $4,060 (20 events), 0x67babd… $3,447 (2 events),
  road2million $2,755 (18), makeit99 $1,890 (12), balthazar $1,019 (9), CryptoPuchok $917 (7). Four wallets = 59%.
- Makers who leave quotes through the release pay for it: perfectnostalgia lost $1,587 on 9 resting bids hit in the
  first 60 s.
- The first run (`release_analysis.py`, release time guessed from the busiest minute) was wrong for most events and is
  kept only as a record; its totals must not be used.

Second-order gap, data -> Fed market (`fed_reaction.py`, `fed_reaction.txt`, the two largest December markets, six
releases in November): on the jobs report of 11-06 "hike 25 bps" went 0.71 -> 0.74 (+5 s) -> 0.79 (+30 s); takers in
the first 8 s made +$893 on $11.8K marked one hour later, takers at 8-33 s made +$51 on $90K. CPI, PPI, PCE and ISM
days show no usable move. Four informative releases: too few to conclude anything except that the move, when there
is one, is over in about 30 s.

Carry after the release (`checks.py` part 4): taker buys of the determined winner at 0.95-0.999 later than 60 s:
268 fills, $34.8K, profit $718 (2.07%), of which $675 in the two October CPI markets that waited ten days.

Calibration (`checks2.py` part 6, both sides of every market, 53 events): edge per $1 share after fee, price bucket
0.70-0.90: -0.032 (7 d before, 74 bets), -0.001 (1 d, 71), -0.027 (1 h, 71). Bucket 0.30-0.50: +0.049, +0.118, +0.032
(44-56 bets) and 0.50-0.70: -0.037, -0.101, -0.023 (45-54 bets). The last two are a post-hoc pattern in 21 cells
examined; treat as a hypothesis only.

## Accounts

Fee note: actual charges on economics markets imply a rate of 0.036-0.048 before 2026-11-21 and 0.0100-0.0102 after
(`fee_calibration.txt`; five accounts, 5-722 taker fills each). The tool's fee estimates use the market field and are
too low for the older period; "API kept" figures are after real fees.

### perfectnostalgia — positions before the release, holds to settlement
- All time: kept $181,889 on $2.04M volume (8.9%), rebates 3%. Positive in 28 of 32 months; last three
  $10.7K, $12.7K, $11.7K.
- 88 days: 2,960 fills, 158 markets, 134 of them economics (77% of turnover). Economics net on 105 resolved markets
  $17,992 (8.4% of turnover, t by market 1.55). Taker buys +12.4c per share (t 2.34, 69 markets); maker buys +5.1c
  (t 0.72); the taker fills carry the edge.
- Timing (`timing.txt`, 82 release-event markets): 149 taker fills more than a day before the release, $65.5K, edge to
  final +$16,603; zero taker fills after the release; 9 maker fills in the first 60 s after it, -$1,587.
- Entry: first buy a median 15.6 days before the scheduled end. Position cost median $317, p90 $3.2K, max $34.4K;
  13-25 economics markets a week. 76% of bought dollars are held to resolution or still open.
- Stories (`stories_perfectnosta.txt`, 16 markets):
  - ECB "no change" October: bought Yes at 0.83-0.92 from 09-01 to 10-15, $34.4K, resolved 10-29, +$5,187.
  - BoE "+25 bps" November: bought Yes at 0.36-0.61 on 09-11..09-17, sold at 0.983 on 10-29..10-31, a week before
    the meeting, +$2,732.
  - August CPI "3.4%": resting bids at 0.43-0.47 for ten days plus four takes, last fill 18 minutes before the
    release, 8,041 shares, +$4,356.
  - September CPI: 7,511 shares of "3.7%" at about 0.40 (+$4,303) and "3.6%" as well (-$3,240); core m/m "0.2%"
    -$2,442. It buys two adjacent buckets and is wrong on single markets often.
  - Fed October "no change": in at 0.30-0.47 in September, out at 0.82 on 10-02, back in at 0.87 a week before,
    +$2,261.
- Falsification: "it only buys favourites" -> a blind favourite buyer in the same markets earns about zero (calibration
  above). "It reacts to the release" -> no taker fill after any of 82 releases.
- What it is: a model edge (which bucket, which decision) with patient execution. The inputs are not visible in the
  data. Fee: taker 64% of volume.

### GoldmanSachs (0x71dd2d539a793687451d4af8c43169369b47d61c) — discretionary Fed-path swing trader
- All time kept $86,646; months Sep $0.4K, Oct $6.5K, Nov $14.1K; before August under $1.1K a month.
- 88 days: 246 fills, 23 markets, $267.8K; 72% of buys sold before resolution, FIFO +$14,434, median hold 45 h.
- Stories (`stories_GoldmanSachs.txt`, 12 markets): 11-10 09:02 UTC bought 111,222 "hike 50 bps in December" at
  0.009 ($1,000), 4.5 hours before CPI; sold from 13:33 at 0.096: +$9.7K, two thirds of the month. 10-28 18:02, two
  minutes after the FOMC statement, bought "hike 25 bps in December" at 0.81-0.82; cut it at 0.64 on 11-05; rebought
  at 0.65 and 0.83. Fed October "no change": in and out five times between 0.43 and 0.93, exit at 0.971 ten minutes
  before the statement.
- Timing: 33.5% of its Fed-market dollars trade within 6 h after a US release (5.7% expected by chance) but only two
  taker fills within 120 s. Not a speed account.
- One trade is most of the result: weak evidence.

### ATCapital — two-sided book on the December Fed event with a large balance sheet
- Joined 2026-10-03. Kept $28,640, 14% of it rebates and rewards; October $1.3K, November $26.5K; last 14 days -$2.4K.
- 88 days: 3,468 fills in 23 markets, $2.12M, 53% maker; 62 merges, 11 neg-risk conversions, 2 splits. About $1.0M of
  inventory at cost is open: both sides of the same markets, and No at 0.990-0.999 on the cut outcomes ($40K lots).
- 23 taker fills within 120 s of a US release, all small ($11-440): quote maintenance, not sniping.
- Two months, one event, unresolved: no conclusion on persistence. Needs capital three orders above ours.

### Ahpo — fast, news-reactive trading in Fed-path markets, short holds
- All time kept $154,896 on $15.8M (0.98%); 16 positive months of 16; last three $21.5K, $8.6K, $12.9K; rebates 4%
  all time, 11% in November.
- 88 days: 46,851 fills (40K of them one maker ladder at 0.85-0.95 in September), 353 markets, $2.0M, 62% maker;
  economics 79 markets, $898K. Economics FIFO: 86% of buys sold before resolution, +$26,218, dollar-weighted median
  hold 0.9 h.
- Stories (`stories_Ahpo.txt`): 09-04 12:30 (jobs) took 27,343 "hike 25 bps in September" at 0.432, sold over the
  next week at 0.54-0.83. 09-16 18:00 (FOMC) took 12,770 "hike in October" at 0.347, sold 0.386 inside the hour.
  11-06 13:30:19 took $17.0K "hike in December" at 0.778, sold $20.0K at 0.790 twenty seconds later.
- Timing: 30.3% of its Fed-market dollars within 6 h after a US release (5.7% by chance); three taker fills within
  60 s, $37K.
- Positions of $10-57K; the edge is about 1% of volume. Only 16 economics markets resolved in the window, so the
  economics part of the profit rests on round trips, not on outcomes.

### 0x831449c4b94607dd3367023c61525aea99a90b88 — sweeps thin macro markets and buys year-end "No" at 0.93-0.97
- Joined 2026-10-19; kept $52,316 of which $21,821 unrealised; 617 markets; 88% taker. Economics 75 markets, $106K
  (19% of turnover); politics is the main book.
- Stories (`stories_0x831449c4b9.txt`): China November CPI "+0.3%" No bought 2,600 at 0.931 and resold at 0.997-0.998
  within a minute; Mexico Q4 GDP No 0.857 -> 0.99 in hours; Japan core CPI Yes 0.642 -> 0.891 in two days. On 11-20
  two tickets, $25.0K No on "inflation above 5% in 2026" at 0.970 and $20.2K No on "above 4.5%" at 0.926.
- 10 economics markets resolved (+$1,125). Six weeks, 437 of 617 markets open: cannot be judged yet.

### Stonktrader — not an economics account
- Kept $98,410; months $10.1K, $1.8K, $14.8K, -$0.3K, $10.4K, $59.6K, $2.1K (May-Nov).
- 88 days: economics is 16 markets and $35K of $395K. Profit came from crypto (+$49.9K on 6 markets) and tech
  (+$33.2K on 12), politics lost $34.9K.
- Economics fills: $12K No on Fed September "no change" at 0.80 two days before (+$2,976); October CPI "3.7%" Yes at
  0.96 before and after the release and at 0.997 on the day it finally resolved (+$246, +$168 on core YoY).
- Studied and set aside: concentrated discretionary bets, four resolved economics markets.

### jozeslemsek — dealer in sub-cent tails
- All time kept $6,714 on $52.7K volume (12.7%); nine positive months of nine: $25, $188, $20, $143, $161, $370,
  $664, $1,378, $3,765. Rebates and rewards 9%.
- 88 days: 18,529 fills, 575 markets (115 economics, 35% of turnover), $41.6K, 88% maker.
- FIFO round trips, all markets (`checks.txt` part 1): 12,283 lots, cost $15,329, profit $6,422 (42% of cost).
  Median buy price 0.003; 90% of buys and 88% of sells are maker; median hold 105 h, p90 24.5 days. 302 of 373
  markets positive; top ten markets = 54% of profit. By resale multiple: under 1.5x $433, 1.5-3x $3,451, 3-10x
  $1,906, over 10x $632; losing lots -$1,058. Unsold inventory at cost $4,022.
- Stories (`stories_jozeslemsek.txt`): "Fed cuts 25 bps in January" bought 4,487 at 0.012, sold at 0.014-0.016 a week
  later, another 24,599 sold at 0.024; "no change in December" Yes bought at 0.017-0.022 and sold at 0.031-0.037 the
  next day, three times in four days; "cut 50 bps in December" bought at 0.006, 45,000 sold at 0.003 (a loss).
- Position per market median $4, p90 $205, max $1,157; 35-50 economics markets a week.
- Falsification: "a few lucky jumps" -> 81% of markets positive and 54% of profit from the 1.5-3x band, but the top
  ten markets are still half. Holds, with concentration noted.

### TheElement115 (and road2million) — the release snipers
- TheElement115: joined 2026-07-21, 151 fills all time, kept $8,491 on $77K (11%), no rebates; months $0.9K, $0.9K,
  $0.7K, $4.9K, $1.1K. road2million: kept $5,291; $4.4K of it in October.
- 88 days, TheElement115: 76 fills, all taker buys. 51 are in the sampled events (33 events, 25 of 37 release times):
  lag 2-18 s, median 7 s, p90 17 s; median price paid 0.94; median $401 a fill, max $5,000; $47.7K, edge to final
  +$4,618. The other 25 are the same pattern on releases outside the sample: Bank of Russia 10:30:05, Copom
  21:31:40, China CPI 01:30:16, JOLTS 15:00:04, RBNZ 01:00:08, Michigan sentiment 15:00:02.
- road2million fills land in the same events at the same block times (09-11 10:30:06, 11-04 21:31:40, 09-09
  01:30:16): the same operator or the same software.
- Falsification: is the fill after the number? In 51 of 51 and 45 of 45 fills the block time is 2-19 s after the
  scheduled second; none before.
- Three months, 33 events, and October is 58% of TheElement115's profit: the mechanism is certain, the income is
  lumpy and depends on surprises.

## What the winners have in common

- Three separate games: seconds after the number (small bots), days before the number (model), and the Fed-path
  markets (capital and judgement). The leaderboard only shows the last two.
- Rebates do not matter here (0-14%); nobody is in a volume tier.
- Every directional winner buys between 0.30 and 0.97; almost nothing above 0.97 except ATCapital's balance-sheet use.
- Everybody pulls or loses resting quotes at the release. Nobody on the list makes money as a passive maker through it.
- Profits are lumpy: one surprise (core CPI September) or one ticket (GoldmanSachs on 11-10) is a large part of a
  quarter.

## What it would take to copy

| mechanism | data | speed | capital | fee | room | main risks |
|---|---|---|---|---|---|---|
| release sniping | the number itself within 1-3 s (agency page or a paid calendar feed), bucket map prepared | order in the book 2-8 s after the release | $300-5,000, recycled in 2 h | 0.01 now (0.036+ before 11-21) | about $7K a month for everyone, sampled events | parsing the wrong figure (rounding, revisions, unadjusted vs adjusted), 5-10 bots ahead, lower fee invites more |
| pre-release model | nowcasts, futures-implied odds, consensus | none | $5-35K per position to earn what they earn; works at $50 | same | CPI bucket markets trade $35-275K per event | being wrong: single markets lose 100% of the stake |
| penny tails | none | none, resting orders | $200-4,000 inventory | maker, zero | $1.4-3.8K a month for one account | inventory expiring worthless, queue position, top ten markets are half the result |
| Fed-path trading | everything | seconds to minutes | $10-50K per position | same | $100M+ per meeting | discretionary |

## Checked and not checked

Checked: release timing on 53 events from the tapes; every account's fills against release times (`timing.py`);
FIFO round trips (`checks.py`, `checks2.py`); calibration; fee rate from real charges.

Not checked:
- How TheElement115 gets the number, and how fast the agencies' pages serve it. The 6-9 s on BLS days may be the
  agency's own latency.
- Depth at stale prices beyond what actually traded. The tape shows fills, not the book; a faster bot may find more
  or may find the same $0.3-3K.
- The inputs behind perfectnostalgia's choices (no historical OIS or nowcast data pulled). Its edge is inferred from
  outcomes on 105 markets.
- Release times come from the standard calendar; each was accepted only where the tape shows the burst (see the
  `n10before/n10after` columns). BoJ and three other events without a fixed time were left out.
- October CPI annual was priced 0.95 before 13:30 on 11-10 and resolved on 11-20. Why is unknown.
- Whether jozeslemsek's bids would have been filled for a second account in the same queue.
- Profit figures in the release table use a 0.01 fee; at the old rate they are a few percent lower.

## Variants run

Screen: 1. Release analysis: 2 (first with auto-detected times, discarded; second with the schedule). Stale threshold:
one value (0.95). Calibration: 3 horizons x 7 price buckets, all reported. FIFO, timing, Fed reaction, carry, fee: one
run each. Nothing was tuned on one period and reported on another: this is a description of the past, not a backtest.

## Files

`protocol.md`, `leaders.txt/json`, `screen.py/txt/json`, `<name>.txt/json` (14 d), `<name>_88d.txt/json`,
`<name>.monthly.txt`, `econ_markets.py`, `stories.py`, `stories_<name>.txt`, `list_events.py`,
`events_sep_nov.json`, `fetch_tapes.py`, `release_events.json`, `release_analysis.py/.txt` (discarded run),
`release_analysis_v2.py/.txt`, `release_results_v2.json`, `release_snipers_v2.json`, `timing.py/txt/json`,
`fed_reaction.py/txt`, `checks.py/txt`, `checks2.py/txt`, `fee_calibration.txt`. Tapes and cached fills:
`data/econ_tapes/`.

## Sceptic's check

Done 2026-11-27 by a second reader whose job was to break the account explanations above. Scripts and outputs are in
`sceptic/`. No protocol file was written before these runs (the checks were fixed by the review brief: another window,
concentration, raw re-derivation, alternatives); every run is listed and nothing was tuned. Accounts checked: the two
with confidence 4 (perfectnostalgia, TheElement115) and both accounts tied at 3 (jozeslemsek in full, Ahpo lighter).

| account | verdict | one line |
|---|---|---|
| TheElement115 | SUPPORTED | Reproduces in Jul-Aug and on raw tapes outside the 53 events; 111 markets, none lost |
| perfectnostalgia | WEAK | The account is a real long-run winner; the stated source of the edge does not reproduce |
| jozeslemsek | WEAK | Real cash, but half of it is three events and the finished markets earned almost nothing |
| Ahpo | SUPPORTED (lighter check) | Reproduces in Jun-Aug; faster than described; the 11-06 showcase lost money after fees |

### TheElement115: SUPPORTED

- Other window (`element_jul_aug.txt`, 2026-07-17..08-31, before the analyst's sample): 37 resolved markets, net
  +$1,818 on $12.1K (15%), t by market 3.23; API kept $1,769 after $55 of fees. Same behaviour, smaller size.
- Concentration (`element_life.txt`, whole life from raw fills): 111 resolved markets, +$8,483 on $78.4K at a 0.04
  fee (API kept $8,491); 99 positive, no market lost more than $5; t 5.81, and 7.06 without the three best markets
  ($6,429 left). By release day: 46 of 48 days positive; without the three best days t 5.17.
- Timing re-derived without the analyst's schedule table: seconds past the nearest quarter hour for each fill. Of
  96 fills of $20 or more, 86 land 0-40 s after :00/:15/:30/:45 (84 of them within 20 s). The other 10 follow
  announcements with no quarter-hour second (South African Reserve Bank 13:05:30, Japan GDP 23:50:02, Copom
  21:31:40, RBI 04:32:20, Bank of Korea 00:50:06).
- Raw tapes fetched fresh for 9 markets outside the 53 events (`element_tapes.txt`): its fill is 5-8 s after the
  quarter hour (RBNZ +8, July jobs +6 and +7, July CPI +6, Bank of Russia +5 and +7, FOMC July +6); the last print
  before was 0.003-0.87 for the outcome that won. No buying of the winner in the ten minutes before, except normal
  two-way flow in the Fed market: nothing that looks like a leak. federalreserve.gov confirms the 2026 meeting dates
  (July 28-29, Sep 15-16, Oct 27-28); bls.gov is blocked from the sandbox.
- Corrections to the write-up:
  - "Every fill is 2-40 s after a release" holds for the real fills. The account also has 57 fills under $20
    ($175 in total, including $1 buy/sell probes in an unrelated market) and 17 sells.
  - It is never alone. In 7 of the 9 tapes 3-8 other takers are in the same block (road2million, makeit99,
    ClickKlackClick, balthazar, mildwindow27, 0x67babdb5, vivonzulull). Prices inside one block differ widely
    (0.118 and 0.99 for the same token), so block order is not match order and the lag cannot rank the bots.
  - Half the profit is a few deep-stale fills: bought under 0.80, $8.1K earned $4,478; bought at 0.95 or more,
    $39.5K earned $761. In the one large market checked (FOMC July) 17 fills worth $107K were ahead of it and it paid
    0.840 against 0.811 before the statement.
  - October is 47% of the profit by fill date (58% by the API's booking date).
- Alternatives: rebates $10 in total. Not luck (no losing market in 111). No fee group with road2million or makeit99
  (different `wv_30d`). road2million existed since 2025-10 and lost $779 on $1 fills until June 2026, then began
  sniping in July 2026, the month TheElement115 was created: 38 of its 107 fills in shared markets are in the same
  block. One operator is possible and unproven; if so the "four wallets" are three operators.
- Still open: depth beyond what traded, how the number is obtained, and what happens at the 0.01 fee.

### perfectnostalgia: WEAK (the account wins; the explanation is thin)

- Behaviour reproduces in two more quarters (`perfectnosta_mar_may.txt`, `perfectnosta_jun_aug.txt`): buys days to
  weeks ahead, sells 10-23% of dollars, no post-release takes. In 7 markets re-derived from raw fills and tapes
  (`perfect_checks.txt` part c) the first buy is 14-76 days before the release, the last 15 hours to 22 days before,
  and there are zero fills at or after the release.
- Profit reproduces at the account level: API kept $28.1K (Mar-May), $11.2K (Jun-Aug), $35.0K (Sep-Nov). Monthly
  record: 28 of 32 positive, t of monthly kept 4.56, and 4.53 without the three best months.
- What does not hold:
  - "The taker fills carry the edge" (+12.4c, t 2.34 in Sep-Nov): taker buys earned -0.7c a share in Mar-May
    (t -0.11, 89 markets) and -3.4c in Jun-Aug (t -0.38, 61 markets). In Mar-May the money came from maker buys and
    maker sells.
  - Concentration. Sep-Nov economics: three markets are $13.8K of $18.0K; the rest is +$4.1K, t 0.48. Jun-Aug:
    +$5.0K in total, three markets +$28.2K, the rest -$23.2K. By event (adjacent buckets netted): t 2.64 / 0.60 /
    2.51 in the three quarters; without the three best events t 1.78 / -0.20 / 1.82.
  - The falsification used the wrong price range. It tested blind buying at 0.70-0.90; the account's bucket bets are
    at 0.30-0.55, where the analyst's own table shows blind buyers earning +3 to +12c. Against a blind buyer of every
    same-priced token (within 0.10) in the same event at the same moment (`perfect_checks.txt` part d, 29 events,
    $84K): its edge $13.0K, blind $5.5K, difference $7.5K, t by event 1.53; without its three best events the
    difference is $503 (t 0.18). Selection is not shown in this quarter.
  - Execution is not an edge: its VWAP equals everyone else's over the same span (0.448 vs 0.436, 0.401 vs 0.397,
    0.426 vs 0.444, 0.473 vs 0.467).
  - Story error: the last fill in August CPI "3.4%" is 09-10 12:12:33, 18 minutes before the PPI release and
    24 hours before CPI. The ECB October position started 08-14, not 09-01 ($37.9K in all).
- Corrected mechanism (`perfect_bands.txt`): two books. (1) Favourites bought at an average of 0.70 or more and
  held: 62 markets in three quarters, 57 positive, +$28.9K on $324K (8.9%), positive in every quarter. This is
  carry that pays while nothing surprising happens; 5 of the 62 lost, and one miss can cost a stake of up to $34K
  (which losing event belongs to this book was not traced). It sits uneasily with "buying the favourite is not an
  edge": that calibration cell has 71-74 bets from one quarter and cannot exclude a few cents. (2) Bucket bets at 0.30-0.70: 74 markets, 42 positive, +$25.7K
  on $210K, t 0.4 / 0.4 / 1.2 by quarter: positive but indistinguishable from variance inside any one quarter.
  Buys under 0.30 lost $2.9K on 112 markets.
- Alternatives: rebates and rewards 3%; no fee group (`own_wv_30d` equals `wv_30d`); nothing suggests inside
  information (it loses single markets outright); hedges on other venues are not visible. Survivorship: picked from a
  leaderboard, but 32 months of record make a pure-luck reading unlikely.
- Confidence should be 3, not 4: a skilled account whose skill cannot be located in the fills.

### jozeslemsek: WEAK

- Other window (`jozes_jun_aug.txt`): same behaviour (maker buys at an average 0.0086, maker sells at 0.0135), API
  kept $675 on $7.3K. Tool net on 249 resolved markets +$136 (t 0.71), -$34 without the three best.
- Whole-life cash rebuilt from all 26,345 fills and the activity feed (`jozes_life.txt`): buys $24,772, sells
  $28,580, redeems $230, rewards $405, maker rebates $228, fees $193: net cash +$4,478; 206 open positions cost
  $2,600 and are marked $2,260. Cash plus marks $6,738 against the API's $6,714: the profit is real and mostly cash.
- Concentration: 554 events; the three best are $3,066 of $6,298 (49%), the ten best 71%. "Fed decision in January"
  and "Fed decision in December" alone are $2,612. The 656 markets that have resolved earned +$740 in eight months
  (t 1.52; +$191 and t 0.55 without the three best). Nearly all the profit is in markets still open, and November is
  56% of the lifetime figure.
- Spread or price move (`jozes_tapes.txt`, `jozes_sample.txt`; reference = everyone else's VWAP within 2 hours of
  each fill): on the seven best markets $715 of $3,179 realised is spread and $2,463 is the price being higher when
  it sold; on a random 30 markets (seed fixed first) $436 of $1,597. The split overstates the move in thin markets
  (prints around its buys are bid-side), so read it as an upper bound. In the Fed tails the move is real: January
  "cut 25 bps" bought at 0.0060 and sold at 0.0174 while the weekly VWAP went 0.0070 -> 0.0217; December
  "hike 50 bps" bought at 0.0077, sold at 0.0233, $505 of it as taker sells in the week the tail traded at 0.076.
- Corrected mechanism: a buyer of cheap tails that sells when a tail reprices, more than a dealer earning a spread.
  It was long Fed tails in October-November when they moved 3-4x. Half of its buy dollars are not sub-3c tails
  (19% at 0.10-0.30, 15% above 0.30); the median buy price of 0.003 is by count.
- Alternatives: rewards and rebates $633 (9% of kept, 14% of net cash); no fee group. Luck is not excluded: one
  quarter of tail volatility explains most of the money.
- For us: it stays the only mechanism at our scale, but the evidence is a few hundred dollars outside two Fed events.

### Ahpo: SUPPORTED (lighter check: no per-market tape re-derivation)

- Other window (`ahpo_check.txt`, Jun-Aug fetched fresh): economics round trips +$7,021 on $312K of cost, 25 of 28
  events positive, t by event 2.50, and 2.41 without the three best. Sep-Nov: +$26,218, 18 of 23 positive, t 2.14,
  but three events are $20.5K and the rest has t 1.31. Positive 16 months of 16.
- Faster than described. Taker fills in the first 60 s after 12:30/13:30/18:00/19:00 UTC: 19 for $124K in Sep-Nov
  and 12 for $43K in Jun-Aug. The write-up counted three for $37K because fills in Fed-decision markets were timed
  only against the FOMC, not against CPI and jobs: 09-11 12:30:10 $25.9K, 09-04 12:30:10 $11.2K, 10-02 12:30:11
  $14.0K, 10-14 12:30:14 $11.1K. So "no leaderboard account took in the 60 s after a release" is true only for a
  market's own release.
- Where the money is (`ahpo_roles.txt`): lots opened as taker and closed by resting offers, +$5.3K (4.3% of cost) in
  Jun-Aug and +$15.7K (7.3%) in Sep-Nov after an estimated fee. Maker-opened lots +$0.6K and +$2.5K. Taker in and
  taker out: -$1.3K and +$2.4K. Lots opened within ten minutes after a release time earn 4.0% and 8.1% of cost
  against 1.0% and 3.8% otherwise.
- The 11-06 showcase (bought $17.0K at 0.778, sold at 0.790 twenty seconds later) grossed $262 on the matched shares
  and paid about $295 in taker fees at the 0.04 rate then measured: slightly negative. Only 4 of the 19 fast fills
  could be marked to a tape (`ahpo_fast.txt`); the cached tapes of the September and October Fed markets are cut.

### Runs

`pmlab.wallet` on four other windows; `conc.py`; `fetch_life.py` (3 wallets); `jozes_life.py`; `jozes_tapes.py`;
`jozes_sample.py` (one seed, one draw); `element_life.py`; `element_tapes.py`; `perfect_checks.py` (one comparator
band, 0.10); `perfect_bands.py`; `ahpo_check.py`; `ahpo_fast.py`; `ahpo_roles.py`. One variant each, all reported.
