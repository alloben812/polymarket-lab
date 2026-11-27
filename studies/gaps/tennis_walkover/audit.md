# Audit: tennis walkovers (studies/gaps/tennis_walkover)

Auditor: independent agent, fresh context, 2026-11-27. Read: `docs/audit-checklist.md`, AGENTS.md «Правила
исследования», NOTES.md, `protocol.md`, `results.md`, all `s*.py` and `common.py`. Did not edit results.md or protocol.md.
Audit code is in `audit/` (a1..a6). It is written from scratch: it does not import `common.py` or any `s*.py`, and
reads only the raw gamma dump (`data/gaps_tennis_wo/events.jsonl.gz`), the raw cached tapes (`data/tape/*.jsonl.gz`)
and, for W3, the author's list of notice times (`out/public_times.json`, the times are taken as given).
Run with `python3 -I studies/gaps/tennis_walkover/audit/aN_*.py` (a1 first: it writes the universe file to the
scratchpad). Run time is under 15 s each.

## Verdict: HOLDS (negative result)

The author's numbers come out the same to the dollar from independent code. I found no bug that hides an effect. Three
signal variants I added for the audit only (not protocol) are also flat. The only positive lines are the hindsight
ceiling and the notice line, and the author already marks both as not tradable or not significant.

**Corrected headline (same as the author's, with sample sizes):** A tape follower makes nothing after the 0.05 fee. The
causal rule ran on 830 walkover moneylines plus 2,734 control moneylines scaled by 8 (22,702 represented, 2,794
triggered). Net over 86 days: -$6,422 / -$6,471 / -$17,103 / -$25,494 at 10 s / 60 s / 5 min / 15 min (t -0.26 /
-0.27 / -0.70 / -1.10). In the reporting period (274 walkovers + 956 x 8 controls) it nets +$629 / +$716 / +$1,868 /
-$15,433 (t 0.05 / 0.05 / 0.13 / -1.25). The hindsight ceiling (you know it is a walkover from the first print)
in the reporting period at 10 s: +$534 ($17.6/day). That rests on 25 filled events of 274. The 95% CI per event is
$0.88-3.02, and the 95% interval by day-bootstrap is $275-836. It falls to +$121 without the 10 best events, to
$14.9/day if the follower is 3 s later, and to $12.8/day at a 200 EUR ($215) cap plus 3 s later. Starting from the
notice: +$288 over 86 days on 28 events, 7 fills, t 1.22. Without its single best event it is +$54.

## Reproduction (checklist item 6)

| quantity | author | audit (own code) | script |
|---|---|---|---|
| class A events / control population / sample (k) | 830 / 21,849 / 2,734 (8) | 830 / 21,849 / 2,734 (8), identical slug and cid sets | a1 |
| t_first found | 350 | 350, 0 disagreements to the second; Stavenson sanity 09:37:58 / 09:38:00 (03 Nov), 11:15:55 (18 Nov) | a4 |
| causal, all 86 d, 10/60/300/900 s | -6,422 / -6,471 / -17,103 / -25,494; t -0.26..-1.10 | -6,422 / -6,471 / -17,103 / -25,494; t -0.26 / -0.27 / -0.70 / -1.10 | a3 |
| causal, reporting period | +629 / +716 / +1,868 / -15,433 | +629 / +716 / +1,868 / -15,433; t 0.05 / 0.05 / 0.13 / -1.25 | a3 |
| hindsight A, reporting, 10 s | +534, 25 fills, CI [0.88, 3.02], t 3.6, $17.6/day | identical; without the top 3 +324 | a4 |
| hindsight A, all 86 d, 10 s | +3,025, 90 fills, t 5.2 | identical | a4 |
| W4 cheap side below 0.45 after t_first | $479,681 on 209 events, 75% in 2 s, 229 takers, top 3 55%, 97 first wallets | $479,681, 0.748, 229, 0.55, 97 | a5 |
| W3 lag (25 events) | median -36 s, 17 of 25 book first | -36 s, 17 | a5 |
| rule from t_public, 10/60/300/900 s | +288 / +192 / -10 / -29 | +288 / +192 / -10 / -29; 7 / 4 / 2 / 1 fills | a5 |

The full sample was reproduced, not a quarter of it.

## Checklist

1. **Look-ahead.** The causal rule uses a reference made of prints at least 120 s old, triggers on the current print,
   and fills only prints from trigger + d onward, at match time = block time - 3 s. Both sides use the same shift, so
   the shift cannot leak. One input is not causal by construction: the scheduled start (gamma `gameStartTime`, read
   after the fact). If it was revised to the real start, that revision helps the follower, so the negative result is
   if anything optimistic. The class A "t_first" uses hindsight (the move "sticks"). The author says so, and that line
   is presented only as a ceiling. Clean.
2. **Fills.** Every follower fill copies a print that a real taker already took (an upper bound; the same liquidity is
   counted once for the follower and once for the real taker). The follower uses no price that did not print. Tennis
   moneylines carry `secondsDelay = 1` (830 of 830, a5), so the follower's own order matches at least 1 s after it is
   sent. Haircuts on the only positive line (hindsight, reporting, 10 s): start 3 s later gives +$454; cap the price
   at 0.45 gives +$484; cap $215 plus 3 s gives +$390 ($12.8/day), +$93 without the top 10. 75% of the cheap dollars
   print within 2 s of the first move (a5). A follower who reacts to a public signal is not in that window.
3. **Fees and accounting.** Fee 0.05·p·(1-p) per share, no rebate. Checked by hand on 3 filled events
   (konsta2-wang19: implied fee 0.447 vs formula 0.447; barrbue-diassil 8.412 vs 8.415 at the average price;
   rybakin-fernand 4.826 vs 4.826). The fee is charged once. Payoff = each market's own final price, joined by outcome
   name. The completed-match market's No = 1.0 is handled. Sign: control losses are underdog buys where the favourite
   won, as expected. Sensitivity at rate 0.04: causal -5,373 / -5,513 (10 / 60 s), reporting +965 / +1,005 (t 0.07 /
   0.08). The conclusion does not change.
4. **Statistics.** The unit is the match. Per-event nets include zeros. The combined t uses a stratified variance
   (A + k² · control), which covers the sampling error of the x8 control. Day-bootstrap of the hindsight reporting
   line: [$275, $836], 18 days positive, 1 negative. No threshold was tuned, so there is nothing to overlap between the
   tuning and reporting parts; the split is by moneyline closedTime at the 67% point (2026-10-26 13:35 UTC).
   Variants: the author ran 24, all reported. The audit added 8 diagnostics (below) plus haircuts. Blind comparison
   (same rule, no signal, window from 60 min before the scheduled start): -$33,713 on $273K spent (-12.3%). From 10 min
   before the start: -$177,905 (-14.0%, t -2.34). The move signal halves the loss rate (-3.8% for the causal rule) but
   does not make it positive.
5. **Data.** Tape dollars / gamma volumeNum: median 0.55, p1 0.10 (tiny ITF markets with 1-5 prints). Largest tape
   3,418 rows with ratio 0.52, so there is no sign of truncation by pagination; 1 tape has exactly 1,000 rows. No tape
   rows after closedTime + 60 s. Identical rows: 9,714 of 485,203 (2.0%). The rate is the same in tapes of 1,000 rows
   or fewer (2.1%) and in larger ones (1.8%), so these are repeated small orders, not pagination overlap.
   **Minor bug found:** outcome names with an apostrophe (O'Connell, O'Hayon) appear without it on the tape. 804 rows
   in 13 markets (2 class A, 11 control) are dropped, a whole side of each market. Fixed in the audit: causal 10 s
   -6,442 (was -6,422), reporting +609 (was +629); 900 s unchanged. Negligible. The audit finds 563 class A moneylines
   with a cached, non-empty tape; results.md says 561. I did not trace the difference of 2. It does not affect any
   number above, because t_first and every rule number match exactly. Time zones: all epoch
   UTC; the two known Stavenson matches land on the expected minutes.
6. **Independent reproduction.** See the table above.

**A hidden effect?** I tried three things a better-tuned follower might do (audit only, not protocol, so they are
hypothesis-generating at most). (a) Trigger only when the print sweeps to 0.47 or more: 10 s all -$11,815 (t -1.80),
reporting +$1,268 (t 0.41). (b) The same, with the reference underdog at 0.40 or less: all -$663 (t -0.21), reporting
+$1,992 to +$2,376 (t 0.96 to 1.07). (c) The blind rule above. None is significant. The walkover share of triggers stays
low (461 triggered, of which most are scaled control). No wrong sign, wrong join or double fee was found.

**Protocol deviations.** W3 reached 28 notices against a target of 40. ATP, ITF and order-of-play sources were not
tried. All 28 notices have second precision (16 WTA API `LastUpdated`, 12 X). The author reported this. Reporting-only
additions to `s5_rule.py` (CI column, per-day figures) do not affect fills. Nothing else deviates.

## What 200 EUR could earn

About $0/day from the tape follower (negative overall, zero in the reporting period). The notice follower makes about
$0-3/day; that is not significant, and it is +$54 without one event. The ceiling with a perfect walkover feed is about
$13/day at a $215 cap, if the follower trades within about 13 s of the first move. That ceiling sits on about 25 events
a month and falls to about $3/day without the 10 best events.

## To trade this live you would need

A withdrawal feed that is faster than the book. The book moves a median 36 s before the public notices found, and 75%
of the cheap dollars are gone within 2 s. Candidates: the WTA live-scoring API polled every second, which coincided
with the first move within 5 s in 3 events; the ATP/ITF equivalents, untested. You would also need an automatic
mapping from player names to every market of the match, and order entry that matches within 1-2 s despite the 1 s
taker delay. Even then the measured ceiling is about $13/day on 200 EUR, carried by a few events, against more than
100 competing wallets. The edge is speed, which this setup does not have. The public data shows no tradable result.
