# news_latency — independent audit (2026-11-27, fresh context)

Auditor's code: `audit/recompute.py` (own screen, tape timing, confirmation, 2-hour test, rule, clustering, bootstrap;
imports nothing from the study), `audit/attacks.py`, `audit/checks.py`, `audit/rt_trigger.py`. Outputs:
`audit/recomputed.json`, `audit/attacks.json`. Inputs were only the raw caches (`data/gaps_news/markets_all.jsonl.gz`,
`ph/`, `tapes/`), the cached settlement answer `out/resolutions.json` and the frozen hand labels `out/labels.csv`.
Run each with `python3 -I <script>` from `audit/` (about 35 s each). Sources dated: caches 27 Nov 16:43-18:38 UTC, git
history of the study folder (commits 288b9d9 17:01 to 8980a67 18:42).

## Verdict: BROKEN (the positive number); the author's own conclusion "nothing to test live" HOLDS

The headline +$2,436 reproduces exactly, but it comes from two things a trader cannot have at entry. (1) The sample
is chosen with prices from after the entry (the 0.40 move within 10 minutes and the 2-hour hold). (2) The fills are
taken only from prints that other takers made in the next 10 minutes. When nobody else bought a stale offer, the
rule records no trade, and those are the losing cases. Remove either one and the profit is gone:

| test (reporting period 14 Oct - 25 Nov unless noted) | jumps / triggers | clusters | fills | net $ | t (cluster) |
|---|---|---|---|---|---|
| headline as reported, d = 30 s, $200 (reproduced) | 47 | 34 | 25 | **+2,436** | 2.53 |
| same, d = 120 s (reproduced) | 47 | 34 | 25 | +1,042 | 3.40 |
| jumps from the same screen that were not confirmed at +10 min, d = 30 / 120 s | 48 | 42 | 31 / 27 | **+7 / -26** | 0.01 / -0.04 |
| headline sample, one-shot fill (first offer print within 5 s of t0 + 30 s, its size only) | 47 | 34 | 11 | **-16** | -0.07 |
| real order book, one sweep at t0 + 120 s / 600 s (10 jumps, author's L2 sweep x settlement, recomputed) | 10 | - | 6 / 5 | **-82 / -254** | - |
| real-time trigger with no hindsight (auditor's: >= 0.15 move vs the print 60 s - 30 min earlier), $20, d = 30 s | 190 | 157 | 124 | **-16** | -0.07 |
| same trigger, first half, d = 30 s | 98 (away from screened jumps) | 93 | 58 | -162 | -1.41 |
| **the zero-money step results.md proposes** (>= 0.10 vs previous print within 30 min, buy from +3 s for 60 s, $20) | 520 | 425 | 185 | **-267** | -1.31 |
| same, first half | 521 | 460 | 164 | -11 | -0.06 |

**Corrected headline.** In politics and geopolitics markets, a follower with a reaction time of a few seconds to
2 minutes earns about $0 after fees. It loses -$267 on 520 real-time triggers (t -1.31), -$16 on 190 (t -0.07) and
-$16 on the one-shot-fill version of the headline sample. The +$2,436 on 47 jumps (43 markets, 34 clusters, t 2.53)
exists only after hindsight selection and with fills that a real order would not have got.

## Checklist

**1. Look-ahead. Serious; this is the defect that breaks the result.**
- The rule's sample depends on prices after entry. Candidates need a 0.40 mid-price move in prices-history within
  600 s (1,800 s buckets: 3,600 s). "Confirmed" uses the last print at t0 + 600 s, which is inside the buying window
  for every delay below 600 s. "Main" uses the price at t0 + 2 h. The author reports this and does not count it
  as the result. I confirm the numbers: not-confirmed only gives +$7 / -$26 (48 jumps). The two triggers that use no
  hindsight give -$16 and -$267.
- t0 itself is found by looking for the first 10-cent print inside a window that the hindsight screen defines.
  A live program has no such window. On the same tapes the proposed live trigger fires 12 times a day, against 0.8
  confirmed clusters a day.
- The 2-hour price comes from prices-history at the first point >= t0 + 7,200 s; it is not used by the rule except for
  selection. Settlement: from the cached `tokens` answer; 12 of 47 reporting-period main jumps are unresolved and
  marked at today's price, but none of them had a fill at 30 s (resolved-only: +$2,436, 35 jumps, t 2.66), so no effect.
- Labels: `out/labels_draft.csv` (the sheet the labeller read) shows `status` (main/R, i.e. the 2-hour outcome) and p10.
  It does not show settlement or rule P&L. That is a small leak. Counting the doubtful labels as unscheduled leaves
  the result unchanged (author's A4: +$2,464).

**2. Fills. Serious.**
- Every fill is a print that another taker made. The rule assumes that we, not they, took that liquidity. It
  buys only where someone else bought. L2 shows the bias. For "China ballistic missile launch by Dec 31" (16 Oct, main,
  settled NO), offers at 0.81-0.84 stood for the whole 10 minutes. Nobody took them, so the tape rule records $0. A
  real taker sweeping at t0 + 30 s loses -$200. The same happened for "no next Israeli Minister of National Security"
  (marked 0.195): -$75 at 30 s, $0 on the tape. In both cases the tape shows no fill exactly where the book would
  have produced a loss.
- One-shot fill (only the first offer print at or after t0 + d, within 5 s, its size): -$16 at 30 s, +$99 at 120 s
  (6 fills, t 1.43) on the headline sample. Profit needs prints that are picked up across the next 10 minutes.
- Block delay: the rule's window uses differences of block times, so the 3 s constant cancels. If a follower can act
  only after seeing the print on the public tape (+5 s), the result is +$2,443 / +$1,042 (no change). Delay is not
  the problem. Selection is.
- Tape rows are VWAP per taker order (NOTES.md), so a row priced <= 0.90 can contain levels above 0.90. This is minor.
  Within one jump no print is used twice ($ spent per jump <= 200, checked).

**3. Fees. Clean, immaterial.** Rates come from the recorded `feeSchedule` (reporting period main: geopolitics 0 x 17,
other politics 0.01 x 17 and 0 x 3, elections 0.05 x 8 and 0.01 x 2). Hand check: Press Secretary by Oct 31,
0.01 x 0.3498 x 0.6502 x 64.0 = $0.146, as coded. Total fees $5.97 on $5,000 spent at 30 s. Even a 0.05 rate on
everything would cost under about $100. Rebates are zero, as required.

**4. Statistics. Serious.**
- The headline is concentrated. Without the best day (3 Nov, the ceasefire ladder): +$1,556 (t 2.19). Without the
  10 best markets: **+$398 (t 1.29)** at 30 s and +$246 (t 2.25) at 120 s. The top 5 clusters carry 83%
  (author's figure, consistent with my per-jump list: Paris curfew +$338, Press Secretary +$316, four ceasefire legs
  +$807).
- 43 markets, below the 100 that the verdict rule requires. Errors are clustered by event within 30 min (34 clusters)
  and by day; both are reproduced (t 2.53 / 2.32).
- Blind comparison (the same rule without the hindsight signal) is about zero, as the table shows.
- Split: the first half (to 13 Oct) and the second half (from 14 Oct) do not overlap in time. Nothing was tuned, so
  the split is clean, but it is no protection against the selection.
- Variants: the author ran 8 rule variants and 12 re-cuts. I add 2 fill modes x 2 delays, a +5 s timing check, my
  real-time trigger (1 definition x 2 delays, plus halves and subsets) and the proposed trigger (1 definition). None of
  the variants without hindsight is positive with t > 1.

**5. Data. Clean.** My own screen reproduces the same 396 candidates (396 / 396 matched, 0 extra). Funnel
reproduced exactly: 77 no tape jump, 149 not confirmed, 10 artefacts, 136 main, 24 R. All 321 tapes reached their
stop, none hit the 600K cap, and there are 0 exact duplicate rows (33,030 rows in the reporting-period main markets).
Limits not fixable here: `volumeNum` is lifetime volume as of today, and 1,800 s buckets before 27 Sep can miss fast
reversals. The 2028-nominee "jumps" are mid-price artefacts of empty books (no fills, harmless to P&L).

**6. Reproduction. Exact**, on 100% of the sample. All 8 cells of the main table match to the dollar, including
fills, spend and t (my bootstrap CIs differ slightly by seed: +$683..+$4,438 against +$801..+$4,557).

**Protocol timing and deviations.**
- `protocol.md` entered git at 17:01:16 (288b9d9) together with the scripts. The first outputs (12 jumps,
  3 L2 sweeps) were committed at 17:14. That is consistent with "written before results"; nothing earlier can be
  proven.
- Amendment 2 (18:30) says it was written "before any confirmed jump ... was read". Git c7fac67 (17:14) already
  held 4 confirmed jumps and L2 sweeps for 3 jumps, among them the Paris curfew jump of 19 Oct, the largest
  contributor. The amendment only caps the amount of work (L2 cut from 30 to 10, news timing capped) and changes no
  threshold. Minor deviation, not hidden.
- News timing: 34 of the 40 drawn clusters were searched and 10 were timed. L2: 10 of 30. Both are reported. Labels were
  frozen 19 s before the rule ran (labels.csv 18:39:14, rule.json 18:39:33), as the protocol requires.

## What a ~200 EUR account could earn

About **$0 a day**. The proposed live trigger at $20 a trade gives 4.3 fills a day and -$267 over 43 days, i.e.
-$6 a day (t -1.3; 95% range roughly -$15 to +$3 a day). My stricter trigger: -$0.4 a day. The selected sample's
"$7.6 a day" is not available to anyone without hindsight.

**Weekends (the owner's question).** These markets do not depend on exchange hours, and headlines do arrive on
Saturdays and Sundays: 11 of 47 reporting-period main jumps fell on a weekend. But the same no-hindsight trigger on
weekends loses too: -$82 on 20 triggers (t -1.37). Weekends give no edge here either. The "time gap" (Polymarket
moves 7-141 minutes before the Telegram aggregators, per the author's news sample) means a news-feed follower is
always late. A Polymarket-print follower 3-30 s behind the first print earns nothing on average, because it cannot
tell the jumps that stick from those that do not.

## Live micro-test

None. The test proposed in results.md (FOK $10 at the best ask <= 0.90 after the trigger, 30 repetitions) was meant
to follow a positive zero-money backtest. I ran that backtest on the cached tapes and it is negative (-$267,
520 triggers). Even if it had been positive, 30 trades at a spread of about $10 a trade can only detect an edge
above about $3.6 a trade. This is "nothing to test here".

## To trade this live you would need

You would need a signal, available at entry, that separates the jumps that stick from those that revert. The +10 min
confirmation and the 2-hour hold are exactly that signal, and no trader has them at t0 + 30 s. You would also need
to be inside the first 10 s after the first print, against the wallets that make it, with a WebSocket feed on all
~2,500 markets. That is a sub-second-to-seconds race, not a few-seconds follower. Finally, you would need real
book depth at that moment, not prints that other people took. None of this is present for a Mac in Serbia with
200 EUR.
