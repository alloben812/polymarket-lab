# BTC 5m tail sniper: independent audit

Auditor: fresh-context agent, 2026-11-27. Read: AGENTS.md "Правила исследования", NOTES.md, `protocol.md`, `results.md`,
all five scripts, and the parent study `btc5m_tails` (results, audit, T3 tables). Not edited: `results.md`, `protocol.md`.
No orders, wallets, keys or accounts; only local cached data. Code: `studies/gaps/btc5m_tail_sniper/audit/a1..a4*.py`
(own code, run with `python3 -I`, imports nothing from `pmlab` or the study).

## Verdict: HOLDS

The negative result for the rule as written reproduces from the raw cache and I found no mistake that could hide a
positive effect in the book test. The scope should be stated narrowly (see "Corrected headline").

## What I recomputed (OOS-BOOK, BTC 5m, 2026-08-14..21, fee 0.05, $5 ticket, one ticket per market)

From raw `l2_*.parquet` (events) and Binance 1 s zips, with my own signal code and my own book replay (levels at or
under the cap only, shown size only, 5-share minimum, per-level fee):

- Signals: my rule code gives 17,780 signal seconds, identical to the author's `book_signals.parquet` (17,780 of 17,780
  common), in 1,173 markets.
- Tickets at 2 s delay: 1.5 c: 391 tickets, 3 won (0.77% vs 1.03% break-even), net -$364 (-21%); author 397, 3, -$392.
  5 c: 766 tickets, 14 won (1.83% vs 3.09%), net -$1,904 (-52%); author 779, 14, -$1,972.
  The 6 and 13 tickets I lack are exactly the 39 markets whose outcome the author took from gamma (my outcome source is
  the dataset only); all 19 of them lost. Shares match the author's to the share on every common ticket.
- All six delays, my numbers (hits / tickets, net): 1.5 c: d 0 4/404 -$379; 0.15 4/403 -$272; 0.5 4/399 -$278; 1 s 4/397
  -$387; 2 s 3/391 -$364; 5 s 1/390 -$1,377. 5 c: 17/783 -$1,668; 17/774 -$1,835; 16/771 -$1,674; 15/767 -$1,626;
  14/766 -$1,904; 12/768 -$1,850. Same pattern as `results.md` (hit rate below break-even at every delay, including 0).

## What I checked and found clean

- **Outcome mapping** (yes = Up): the dataset's yes/no agrees with the Binance 60 s TWAP outcome in 2,149 of 2,265
  markets (94.9%, in line with the 96.5% the lab quotes for the proxy). A flipped sign would give about 5%.
- **Token mapping**: the recorded book's mid at 299 s predicts the "yes" winner in 1,124 of 1,126 clear cases, so
  the book is the Up/yes token; tail ask for Down = 1 - bid is the right mirror.
- **Book replay**: tail ask at or under 5 c in my replay against the dataset's own `best_ask` column at 354 random
  (market, second) queries: 0 mismatches. Snapshot reset plus price_change deltas (size 0 = remove) is the right model.
- **Time**: Polymarket `timestamp[us]` in UTC against t0 from the slug; Binance dumps are microseconds (handled);
  kline T used from T + 1 only; no look-ahead in the rule. The +0.5 s shift attack was run by the author, same sign.
- **Units**: the cut `mv30 >= 0.00122` is in bp, as published in T3 (`mv30 toward tail (bp)`, cuts -1.35 / 0.00122), so
  there is no unit slip. But note what it means: the "top tercile" cut is about zero, so the rule only asks that Binance
  moved toward the tail at all (about half of all markets have a signal second). That is faithful to the protocol, not a
  bug, and it is the loosest reading of "Binance moved toward the tail".
- **Fees**: counted once, at today's rate; the 0.07 rerun is worse. No double count.
- **Fill rule not impossibly strict**: the offer must be visible at tau and at least 5 shares fill within the cap at
  tau + d; about 90% of cheap offers persist 5 s. Dropping the "visible at tau" test would not add tickets that win.

## Post hoc diagnostics (descriptive only, not rules, not counted as variants of the study)

To look for a corner where the effect could live, I took every signal second (not only the first per market) with a
real fill at 2 s delay (`a4_diag.py`). 5 c: 7,572 seconds in 828 markets, 20 of them won, return -57%. By Binance move
toward the tail the hit count falls rather than rises (mv30 0-1 bp 17 markets won of 661; 1-2 bp 7 of 285; 2-4 bp 4 of
241; 4 bp and more 1 of 163). By distance, no bucket is clearly positive: dist 1-1.5 is -6% on 9 wins. A few small
cells are positive (1.5 c, dist 1-1.5: +243% on 2 wins; 5 c, dist < 1.5 and mv >= 1 bp: +3% on 5 wins) and rest on
two to five winners each, in a search over several cuts. None is evidence. The "one ticket per market, first fill"
rule does not hide a better moment later in the market.

## Concerns (none changes the verdict)

1. **Power at 1.5 c.** 3 to 4 wins in about 400 tickets. The data exclude a Vega7-like 3.8% hit rate (about 15 wins
   expected, 3 seen, p about 1e-5) and a hit rate of 2% or more at about the 5% level, but they cannot show that a
   0.5-1% edge over break-even is absent. The conclusion for 5 c is stronger (14 of 766 against 24 expected).
2. **What the formation numbers say.** In the parent study's unit table (`t3_units_base_full.parquet`), units with
   dist < 2.61 and mv30 >= cut and a price of 3-5 c "won" 47% (60 of 128), and those under 1.5 c won 0 of 93. The honest
   rule (decision at T + 1) gets 3.4% at 5 c in the same months. A tail priced at 3-5 c does not win 47% of the time
   unless the features were measured after the print: T3 evaluates dist and mv30 at the tape's match time (block time - 3 s)
   from the kline that closes up to 1 s later, and block time jitters 1-2 s. I did not prove this, but it makes the T3 "what
   separates Vega7's picks" numbers an unreliable source for the rule, and a likely reason the rule does not reproduce them.
   Worth one sentence in `results.md`; it supports the negative result.
3. **Scope.** Binance 1 s closes with the lab's own sigma model are a proxy. Vega7 may use Chainlink, the official price to
   beat, or a faster feed. The study lists that as an untested idea; it is not a flaw, but "NO EDGE" holds for the rule
   tested, not for Vega7's method.
4. **Other families** (15 m, ETH, SOL, XRP) are tape-only, 6 days, with 0 to 4 wins per row; they say nothing in either
   direction. OOS-TAPE tickets have a size artefact the author already identified. Neither is used to decide.
5. Tickets are 4.3-4.9 USD on average because of shown size; the study scales to 20 USD and reports the share cut by size.

## Corrected headline

On 2,304 BTC 5m markets with recorded order books (Aug 14-21, out of sample), the pre-registered Binance-move plus
small-distance tail rule, bought at 1.5 c or 5 c with a USD 5 fill-and-kill order, loses after the 0.05 fee at every
reaction delay from 0 to 5 s (1.5 c: -15% to -22%, 3-4 wins in about 400 tickets; 5 c: -44% to -52%, 14-17 wins in about
770). I reproduced this independently (5 c, 2 s: 14 wins in 766 tickets, net -$1,904). The offers do not vanish, so
speed is not the constraint; a nearby server is not justified for this rule. The result does not test Vega7's own
model, only the published-tercile rule on a Binance proxy.

## Needed to trade live

Nothing from this study. No live micro-test is justified.
