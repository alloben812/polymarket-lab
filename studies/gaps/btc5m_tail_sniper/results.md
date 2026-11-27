# BTC 5m tail sniper: results

**Verdict: NO EDGE. Nothing here deserves a live micro-test, and a server next to the exchange would not help.**
The Vega7-style rule fixed in advance (tail at or under 1.5 c or 5 c, seconds 225-285, model distance under 2.61 sd,
Binance moving toward the tail over the last 30 s) loses money out of sample on real recorded order books at every
reaction delay from 0 to 5 seconds; at 1.5 c it also loses in its own formation period (Sep-Nov), and on a second
out-of-sample period (Aug 22-31, tape only) it wins no more often than break-even. Speed is not what is missing:
about 90% of the cheap offers visible at the trigger are still there at the same price cap 5 s later (97-98%
counting the next signal seconds). The price is simply not cheap. On 2,304 BTC 5m markets of 2026-08-14..21 (8 days,
books), at a 2-second reaction: at <= 1.5 c, 397 tickets, 3 won (0.8% against 1.03% needed), net -$392 on $1,774 of
stake (-22%, 95% interval of net per $5 ticket -$5.17 to +$3.19); at <= 5 c, 779 tickets, 14 won (1.8% against 3.10%
needed), net -$1,972 (-53%, -$3.87 to -$1.19 per ticket). On 2,880 markets of Aug 22-31 (tape) the 1.5 c rows show
+$305 to +$1,863 from 8-9 wins (0.8-1.1% against 1.05% needed, p 0.47-0.78): a size artefact of the tape, negative
without the best 3 tickets at 2 and 5 s. Opportunities: about 50 (1.5 c) or 97 (5 c) tickets a day; capacity for a
200 EUR account: $0 a day.

Study run 2026-11-27, 18:29-20:20 UTC, one agent. Protocol: `protocol.md` (written 18:35, before any outcome
statistic, not changed). Code: `common.py` (the rule), `book_build.py` (book replay), `tape_run.py` (tape fill
rule), `fetch_tape.py` (download), `report.py` (all tables). Raw tables: `out/tables.md`, `out/summary.csv`,
`out/pie_oos_book.txt`. Ticket files: `data/gaps_btc5m_tail_sniper/tickets_*.parquet`.

## Question

`btc5m_tails` showed that buying every 1-5 c tail of a BTC 5-minute up/down market in seconds 225-285 loses 27-46%
of stake, while the wallet Vega7 kept +$34K on $31K of stake in Sep-Nov 2026 by choosing moments: its picks
followed a Binance move toward the tail and sat closer to the strike in model terms (3.8% hit rate against 0.34%
for all <= 1.5 c tails in the 75-45 s cell). Can that selection be written as a rule fixed in advance that a small
account on a Mac in Serbia (reaction of a few seconds, 1-20 USD tickets, no rebates, taker fee 0.05) can run, does it
hold on months not used to form it, and how much of it survives a reaction delay of 0.15, 0.5, 1, 2 and 5 seconds
against the real order book? Same rule on BTC 15m and ETH/SOL/XRP 5m and 15m.

## The rule (protocol section 2, thresholds = the published T3 tercile cuts)

At each Binance second T in seconds 225..284 of a 5m window (825..884 of a 15m window): the tail is the side the
Binance model (`pmlab.fair.gap_in_sigmas`, K = Binance 60 s average at the start) puts behind; signal when its
distance is under **2.61 model sd** and Binance moved **toward the tail** over the last 30 s (>= 0.00122 bp), and
the tail is offered at or under **Z1 = 1.5 c** or **Z2 = 5 c**. Decision at tau = T + 1 s. Order: fill-and-kill
limit buy at Z, $5 of stake, matched against the book at tau + d; at most one ticket per market; held to
settlement. Fee 0.05 x p x (1 - p) per share (today's BTC rate; 0.01 for ETH/SOL/XRP), rebates 0.

## Data

| set | role | period | markets | source |
|---|---|---|---|---|
| OOS-BOOK | primary, out of sample | BTC 5m, 2026-08-14..21 (8 days, all 2,304 windows) | 2,304 (all with an outcome: 2,265 from the dataset, 39 from gamma) | HF `mileswangs/polymarket-btc-updown-5m-orderbook-tick-data` (PMData, CC BY 4.0; `l2` books and deltas recorded in AWS London, ms timestamps), Binance BTCUSDT 1 s dumps |
| OOS-TAPE | second out-of-sample period | BTC 5m, 2026-08-22..31 (10 days, all 2,880 windows) | 2,880 (62 empty tapes) | Data API tapes (`pmlab.updown.tape`, read 2026-11-27 18:35-19:04), gamma outcomes, Binance 1 s dumps |
| FORMATION | in-sample, context only | BTC 5m grid (every 4th window) 2026-09-01..11-26 | 6,244 | cached prints of `btc5m_tails` |
| OTHER FAMILIES | out of sample by asset / duration | 2026-11-21..26 | BTC 15m 576, ETH 5m 1,728, ETH 15m 576, SOL 5m 432, SOL 15m 576, XRP 5m 432, XRP 15m 576 | cached tapes, Binance 1 s |

Checks on the book data: the recorded book is the Up token (Up buys print at its best ask, Down buys at 1 - its best
bid, median deviation 0.00 on one market's 1,641 trades); each of the 410 (1.5 c) and 798 (5 c) d = 0 tickets has
a real trade of the tail at or under the cap within 30 s in the dataset's own trade feed; the replayed best tail ask
equals the dataset's own `best_ask` (or 1 - `best_bid`) in 1,484 of 1,484 queries of 25 random markets; 96 of 124,215
book queries had no snapshot in the window (0.08%). August is out of sample for the hypothesis (formed on Sep-Nov); its
settlement rule (60 s average) is today's. The crypto taker delay then was 0 (to Aug 17) and 50 ms (from Aug 17);
it is 150 ms today, so d = 0 and d = 0.15 s are only reachable today by a co-located machine.

## What was run (all counted)

- Book variants: 2 caps x 6 delays (0, 0.15, 0.5, 1, 2, 5 s) = 12, each with early/late halves; the same 12 at the
  historical fee 0.07; 2 caps x 2 delays with tau shifted +0.5 s (clock-offset attack) = 4. **28 book rows.**
- Tape variants: 2 caps x 3 delays (1, 2, 5 s) on OOS-TAPE, FORMATION (and again at the historical fee) and each of
  the 7 other families = 2 x 3 x 10 = **60 tape rows**, plus halves.
- Descriptive, not rules: the whole pie of cheap tail trades in OOS-BOOK (`out/pie_oos_book.txt`), pooled other
  families, shown size at the fill moment.
- Nothing was tuned. No threshold, window, size or delay was added after the first result.

## Headline: OOS-BOOK, BTC 5m, 2026-08-14..21, fee 0.05

| cap | delay | tickets (per day) | kept vs d = 0 | avg price | won (rate) [Wilson 95%] | break-even | exact p (hits >= k) | net $ | net per $5 ticket [95%] | return on stake | day-bootstrap 95% of net |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1.5 c | 0 | 410 (51.2) | 100% | 0.0097 | 4 (1.0%) [0.4, 2.5] | 1.05% | 0.62 | -403 | -0.98 [-4.77, +2.80] | -23% | -1,606 .. +797 |
| 1.5 c | 0.15 s | 409 (51.1) | 100% | 0.0096 | 4 (1.0%) [0.4, 2.5] | 1.04% | 0.62 | -296 | -0.72 [-4.88, +3.43] | -17% | -1,620 .. +1,083 |
| 1.5 c | 0.5 s | 405 (50.6) | 99% | 0.0096 | 4 (1.0%) [0.4, 2.5] | 1.04% | 0.61 | -302 | -0.75 [-4.94, +3.45] | -17% | -1,619 .. +1,085 |
| 1.5 c | 1 s | 403 (50.4) | 98% | 0.0092 | 4 (1.0%) [0.4, 2.5] | 1.04% | 0.60 | -411 | -1.02 [-4.92, +2.88] | -23% | -1,619 .. +814 |
| 1.5 c | **2 s** | **397 (49.6)** | 97% | 0.0090 | **3 (0.8%)** [0.3, 2.2] | 1.03% | 0.78 | **-392** | **-0.99 [-5.17, +3.19]** | **-22%** | -1,684 .. +964 |
| 1.5 c | 5 s | 396 (49.5) | 97% | 0.0090 | 1 (0.3%) [0.0, 1.4] | 1.03% | 0.98 | -1,409 | -3.56 [-6.03, -1.08] | -77% | -2,033 .. -740 |
| 5 c | 0 | 798 (99.8) | 100% | 0.0231 | 18 (2.3%) [1.4, 3.5] | 3.53% | 0.985 | -1,712 | -2.15 [-3.51, -0.79] | -46% | -2,628 .. -907 |
| 5 c | 0.15 s | 789 (98.6) | 99% | 0.0231 | 18 (2.3%) [1.4, 3.6] | 3.47% | 0.98 | -1,853 | -2.35 [-3.67, -1.03] | -50% | -2,679 .. -1,118 |
| 5 c | 0.5 s | 786 (98.2) | 98% | 0.0228 | 17 (2.2%) [1.4, 3.4] | 3.37% | 0.98 | -1,686 | -2.15 [-3.60, -0.69] | -45% | -2,576 .. -896 |
| 5 c | 1 s | 781 (97.6) | 98% | 0.0217 | 15 (1.9%) [1.2, 3.1] | 3.27% | 0.99 | -1,695 | -2.17 [-3.71, -0.63] | -45% | -2,424 .. -1,097 |
| 5 c | **2 s** | **779 (97.4)** | 98% | 0.0203 | **14 (1.8%)** [1.1, 3.0] | 3.10% | 0.99 | **-1,972** | **-2.53 [-3.87, -1.19]** | **-53%** | -2,629 .. -1,370 |
| 5 c | 5 s | 781 (97.6) | 98% | 0.0179 | 12 (1.5%) [0.9, 2.7] | 2.66% | 0.99 | -1,918 | -2.46 [-4.23, -0.69] | -50% | -2,919 .. -783 |

How to read: one ticket per market, so the 95% interval of the net per ticket is by market; "kept vs d = 0" is the
number of markets with a ticket at that delay as a share of those at d = 0 (the rule retries at the next signal
second; the same-moment share is in the next section); break-even is the average
of (price + fee) per share; "exact p" is the probability of at least that many wins if the break-even were the true
win rate (small = evidence of an edge; every value here is 0.60 or more). Average stake per ticket $4.30-4.88 (shown
size limits some tickets). Of the 2,304 markets, 1,169 had a Binance signal second, 410 also had the tail offered at
or under 1.5 c at the signal, 798 at or under 5 c.

**Early and late halves** (2 s delay): 1.5 c Aug 14-17 141 tickets, 2 won, +$311; Aug 18-21 256 tickets, 1 won,
-$702. 5 c Aug 14-17 356 tickets, 7 won, -$751 (-45%); Aug 18-21 423 tickets, 7 won, -$1,221 (-59%). The only
positive half is the 1.5 c early half, which is two winning tickets ($495 each) and turns to -$649 without its 3 best
tickets. All halves and delays: `out/tables.md`.

**Decision rule (protocol 5).** EDGE needs net > 0, >= 5 wins and p < 0.025 at d = 2 s on OOS-BOOK: 1.5 c has net
-$392 and 3 wins (p 0.78), 5 c has net -$1,972 (p 0.99). FAST-ONLY needs the same at d = 0.15 or 0.5 s: 1.5 c -$296
and -$302 (4 wins, p 0.62), 5 c -$1,853 and -$1,686. **-> NO EDGE.**

### How much each delay keeps

The question "is the cheap offer still there after the Binance move?" has a clear answer: mostly yes. Of the first
trigger moments of each market, at 1.5 c 97.6% still find an offer at or under the cap after 0.15 s, 95.6% after
0.5 s, 94.6% after 1 s, 92.4% after 2 s and 89.0% after 5 s (5 c: 96.0 / 92.5 / 90.6 / 90.2 / 90.4%); counting the
next signal seconds of the same market (the rule retries), 97-100% of markets get a ticket at every delay. The offer is a standing maker quote, not a stale quote that fast traders race to lift.
What the delay changes is the price and the outcome mix: waiting makes the tail cheaper (5 c average price 2.31 c
at d = 0, 2.03 c at 2 s, 1.79 c at 5 s) and less likely to win (18, 14, 12 wins), i.e. later prices carry later
information. There is no fraction of a positive result to keep: the result is negative already at d = 0.

### Attacks

- **Clock offset** (tau shifted +0.5 s): 1.5 c d = 0 -$354, d = 2 -$533; 5 c -$1,471 and -$1,950. Same sign.
- **Historical fee 0.07** (what August traders paid): every row slightly worse (1.5 c d = 2 -$427, 5 c -$2,044).
- **Concentration:** without the best 3 tickets every row is -$1,733 or worse (1.5 c) and -$2,315 or worse (5 c).
- **Look-ahead:** the signal uses the Binance kline of second T only from T + 1; the book state is taken from events
  with Polymarket timestamps at or before the query time; outcomes come from Polymarket's own resolution message.
- **Fills:** levels at or under the cap only, no more than the shown size, minimum 5 shares; a $20 ticket would have
  been filled in full in 49% (1.5 c) and 66% (5 c) of the 2 s tickets (median shown $19 and $32).
- **Sample:** 3-18 winning tickets per row; the result is lumpy (a 1.5 c win pays about $495 on $5). The 1.5 c
  intervals include zero; the conclusion rests on (a) no row showing more wins than break-even, (b) the 5 c rows being
  significantly negative, (c) the formation period also failing (below).
- **The pie** (descriptive): all takers together bought $5,900 a day of tails at <= 1.5 c and $15,100 a day at <= 5 c
  in seconds 225-285 in these 8 days and lost 64% and 34% of it after a 0.05 fee (13 and 44 winning markets of 2,008 and
  2,177). The August tails were as overpriced as the Sep-Nov ones in `btc5m_tails`.

## OOS-TAPE, BTC 5m, 2026-08-22..31 (tape fill rule)

All 2,880 windows downloaded (all four sub-grids complete; 62 tapes empty, 2.2%, they give no ticket). The tape
fill rule takes real prints at or under the cap 1-3 s after the trigger, at the print's price and size (up to $5).

| cap | delay | tickets (per day) | won (rate) | break-even | exact p | net $ | net per ticket [95%] | return on stake | day-bootstrap 95% | net w/o best 3 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.5 c | 1 s | 808 (80.8) | 9 (1.1%) | 1.05% | 0.47 | +1,863 | +2.31 [-0.60, +5.21] | +146% | -185 .. +4,161 | +379 |
| 1.5 c | **2 s** | **853 (85.3)** | **8 (0.9%)** | 1.05% | 0.67 | **+1,291** | +1.51 [-1.00, +4.02] | +96% | -768 .. +3,636 | **-193** |
| 1.5 c | 5 s | 960 (96.0) | 8 (0.8%) | 1.04% | 0.78 | +305 | +0.32 [-1.41, +2.05] | +21% | -1,159 .. +2,211 | -1,065 |
| 5 c | 1 s | 1,154 (115.4) | 30 (2.6%) | 3.36% | 0.94 | +438 | +0.38 [-1.33, +2.09] | +14% | -1,754 .. +3,271 | -965 |
| 5 c | **2 s** | **1,175 (117.5)** | **29 (2.5%)** | 3.29% | 0.96 | **-758** | -0.65 [-1.83, +0.54] | -24% | -2,080 .. +857 | -1,722 |
| 5 c | 5 s | 1,205 (120.5) | 25 (2.1%) | 3.18% | 0.99 | -1,657 | -1.38 [-2.13, -0.62] | -50% | -2,341 .. -933 | -2,204 |

Halves (2 s): 1.5 c Aug 22-26 +$503 (5 of 454 won), Aug 27-31 +$788 (3 of 399); 5 c -$355 (15 of 588) and -$403 (14 of 587).

**Attack on the positive 1.5 c rows.** They are a size effect of the tape, not more wins: the equal-weight hit rate
is at or below break-even in every 1.5 c row (1.1% against 1.05% at 1 s, 0.9% and 0.8% against 1.05% and 1.04% at 2
and 5 s; p 0.47-0.78). On the tape the ticket size is the
printed size, and the four winners that took a full $5 (500 shares) carry the result, while losing tickets average
$1.56 (winners $3.37). At an equal $5 stake per ticket the same hit rate would return about -12% (0.9% / 1.05% - 1).
Without the best 3 tickets the 2 s and 5 s rows are negative. Under the protocol the tape cannot rescue a failed book
test, and here it does not even agree with itself across delays and caps (5 c is negative at 2 and 5 s).

## FORMATION (in-sample, 6,244 grid markets, Sep 1 - Nov 26, tape fill rule, fee 0.05)

The rule fails even where the hypothesis came from. At 1.5 c: 1,671 / 1,734 / 1,904 tickets at 1 / 2 / 5 s, 9 / 10 /
11 won (0.5-0.6% against 1.03% needed, p 0.99), -55% / -38% / -21% of stake. At 5 c: 2,297 / 2,325 / 2,367 tickets,
78 / 80 / 77 won (3.4% against 3.1-3.2%), +5% / +4% / +4% of stake (p 0.27-0.35, not significant; day-bootstrap of
the net -$1,370 to +$2,037 at 2 s; negative without the best 3 tickets). By part (2 s): Sep-Oct +22% (61 won of
1,545, p 0.09), Nov 1-26 -32% (19 of 780). The Sep-Oct sign at 5 c does not survive into November or into August.
So the published terciles do not reproduce Vega7's 3.8% hit rate when they are used as a rule: its picks must use
something the terciles do not capture (see Ideas).

## OTHER FAMILIES, 2026-11-21..26 (tape fill rule, today's fees)

| family | fee | markets | with a signal | 1.5 c, 2 s: tickets, won, net $ | 5 c, 2 s: tickets, won, net $ |
|---|---|---|---|---|---|
| BTC 15m | 0.05 | 576 | 235 | 117, 2, +197 | 152, 3, -146 |
| ETH 5m | 0.01 | 1,728 | 1,122 | 423, 4, -146 | 562, 15, -103 |
| ETH 15m | 0.01 | 576 | 270 | 74, 1, +1 | 113, 3, -5 |
| SOL 5m | 0.01 | 432 | 289 | 40, 1, +0 | 65, 2, +2 |
| SOL 15m | 0.01 | 576 | 299 | 28, 1, +84 | 43, 1, +73 |
| XRP 5m | 0.01 | 432 | 263 | 31, 1, +87 | 42, 2, +78 |
| XRP 15m | 0.01 | 576 | 264 | 11, 0, -6 | 20, 1, -3 |
| pooled | | 4,896 | 2,742 | 724, 10 (1.38% vs 0.95%), +217, p 0.16 | 997, 27 (2.71% vs 2.45%), -104, p 0.32 |

Signs are mixed and every result hangs on 0-4 wins: no family is significant (smallest p 0.075, XRP 5m 5 c at 1 s,
one of 42 family rows), and without the best 3 tickets every pooled row is negative (-$254 to -$491). Tape tickets
here are small (average $0.65 at 1.5 c) because the printed sizes are small; ETH/SOL/XRP up/down markets have a
fraction of BTC's volume. 1, 2 and 5 s rows and halves: `out/tables.md`.

## Opportunities, net per trade, capacity

- Opportunities: about 50 tickets a day at 1.5 c and 97 a day at 5 c on BTC 5m (OOS-BOOK, 2 s); 85 and 118 a day on
  OOS-TAPE (the tape rule has no "offer visible" check, so it fires more often); 77-109 a day in the
  formation period (scaled from the 1-in-4 grid); BTC 15m about 18-26, ETH 5m 69-94, ETH 15m 12-20, SOL and XRP 2-12 a day.
- Net per ticket after the 0.05 fee, OOS-BOOK at 2 s, scaled from the return on stake: 1.5 c -22% of stake = -$0.22
  per $1, -$1.10 per $5, -$4.40 per $20 ticket (95% interval of the return -116% to +71%); 5 c -53% = -$0.53,
  -$2.65, -$10.60 (interval about -81% to -25%).
- **Capacity for a 200 EUR account: $0 a day.** The edge is negative; size is not the constraint (a $20 ticket would
  fill in full about half the time, and the pie of cheap tails is $6-15K a day).

## Reaction time needed

None, because nothing is gained at any delay, including the impossible zero. The offers persist (about 90% still
there 5 s after the trigger moment), so this is not a speed race: a server next to the exchange (AWS eu-west-2 / eu-west-1) would buy
the same overpriced tails faster. **Not worth renting for this strategy.**

## Live micro-test

Nothing here deserves one. The rule is negative out of sample at every delay on real books, negative in its own
formation period at 1.5 c, and not significant at 5 c. A live test with 50-100 USD would measure only the connection,
not an edge. (For scale: telling a 3.8% hit rate from a 1.05% break-even at 1 c would need about 150 tickets with 80%
power; this rule shows 0.8-1.0% on 397 book tickets and 0.9% on 853 tape tickets, so there is nothing to confirm.)

## Limitations

- The book test covers 8 days (Aug 14-21) and one series. Its 1.5 c rows have only 1-4 winning tickets; the
  negative verdict there rests on the absence of any excess of wins, not on a precise loss.
- August had a different taker delay (0 / 50 ms vs 150 ms now) and fee (0.07 vs 0.05); both are reported, and the
  conclusion does not depend on them.
- The Binance signal uses 1-second klines; a trader with the raw trade stream could react within a second, but the
  result is negative already at d = 0.
- Tape fill rule (OOS-TAPE, FORMATION, other families): block time jitters 1-2 s, the "offer visible at the
  trigger" condition cannot be checked, and the hypothetical trader replaces the taker who really got that print.
  It flatters the rule if anything.
- Other families: only 6 days (the cached tapes and Binance files), fee 0.01 instead of 0.05 for ETH/SOL/XRP.
- OOS-TAPE: 62 of 2,880 tapes came back empty from the Data API (2.2%, against 13 of 6,264 in Sep-Nov); they produce no
  ticket, which removes wins and losses alike.
- On the tape the ticket size is the printed size, which can correlate with the outcome (see the OOS-TAPE attack);
  the book test with a fixed $5 order is the clean one.
- No queue or maker variant was in scope.
- `audit.md` (independent check) does not exist yet; per AGENTS.md the result is not accepted until it does.

## Ideas, not tested

1. Vega7's own August fills (`pmlab.wallet.fetch_fills` for Aug 14-21) replayed against these books: did the wallet
   still win 3-4% in August, and what did its moments look like on the book? This is the direct test of whether the
   wallet had a model the published terciles miss (official price to beat instead of the Binance proxy, the 5 s
   Chainlink lag, Chainlink Data Streams in the dataset).
2. A rule on the Chainlink stream (in the PMData set) instead of Binance: the settlement average is Chainlink's.
3. The maker side: if tails at 1-5 c are overpriced and the offers stand for seconds, the profitable side may be the
   one selling them (resting tail asks), which the earlier lock-in and favourite studies touch from the other end.
4. Repeat the book replay on the post-fee-change set (HF `ithiria894`, Nov 16-22), price changes only, once a
   streaming reader for its 5-13 GB days exists.
