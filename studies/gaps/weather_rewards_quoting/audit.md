# Audit: liquidity rewards on daily temperature buckets (200-dollar account)

Auditor: independent agent, fresh context, 2026-11-27. Checklist `docs/audit-checklist.md`. The author's files were
not edited. Audit code and outputs: `audit/` (`a1_replay.py`, `a4_replay_queue.py` own book replay from the raw
PendulumFlow files; `a2_quoter.py`, `a6_queue.py` own quoter and fill models; `a3_account.py`,
`a3b_account_floor_per_account.py` own implementation of the 200-dollar account; `a5_settle.py` settlement check;
results in `audit/out/*.json|*.log`). None of them imports the author's code.

## Verdict: HOLDS (no edge for a 200-dollar account; the O-model positive rows are an artefact)

The study's conclusion (INCONCLUSIVE in October, no usable edge at today's rates) is reproduced. The account numbers
are reproduced to the cent by independent code; the per-minute build behind them is reproduced from the raw L2 files
on a sample within about 3% on reward and 1-2% on fills. Nothing I found hides a real effect. The one positive
per-market claim with t above 2 (k0O, +$2.44 per market-day, t 3.99) comes from fills a back-of-queue order would not
get: two queue-position models built from the raw prints give results the same as fill model P, not O.

### Corrected headline

Pre-registered 200-dollar account, k = 0, rules fixed on 2-6 Oct, judged on 7-11 Oct (166/160 markets, 125
events, 5 days): **+$13.44/day under P (CI by event -21.6..+48.5, t 0.75) and -$25.50/day under O (CI -61.5..+10.5,
t -1.39)**, reproduced exactly. Realistic fills (queue position) behave like P, so the best single estimate for
October is the P row: about +$13/day, not different from zero. If the $1 payout floor applies per account rather
than per market (unknown): +$24.6/day (P, t 1.37) and -$13.8/day (O). At today's rates (factor 0.206): +$0.20/day
(P) and -$32.16/day (O), or +$5.2/day (P, t 0.29) with the floor per account. Per market with no capital limit, late
period: P +$0.62/market-day (t 1.07 by event, t 0.98 by day; 0.00 without the 10 best markets); O +$2.44 (t 3.99
by event but **t 1.78 by day**), and on my 21% replay sample the queue models give -$1.53 (Q1) and -$1.37 (Q2)
against -$1.30 for P and +$3.15 for O.

## Checklist

### 1. Look-ahead — clean

- Reward universe, rate, minimum size and band are read as of t_m (latest Houroux discovery snapshot received at or
  before t_m, at most 45 min old). I rebuilt this as-of table myself from the raw `marketsfull_*.parquet`
  (`a1_replay.py`) and got the same reward totals within 3% (below).
- Quote prices use the book at t_m (events with timestamp <= t_m); fills use prints strictly after t_m; the reward
  sample uses the book at t_m + 30 s. The account ranks markets by R x share computed on the t_m book. The class
  filter uses eventStartTime (known in advance) and mids at t_m. Settlement enters only PnL, never a decision.
- The list of markets downloaded (union of 10 days of universe snapshots) is wider than the as-of universe, but it
  only decides which rows are kept; quoting is gated by the as-of rule.
- Pre-registration: `protocol.md` is in commit 288b9d9 (2026-11-27 17:01:16 UTC) and unchanged since (empty
  `git diff 288b9d9 HEAD`). `s4_sim.py` (variants and account) was first committed at 17:14 and changed at 17:48
  only in output paths; full outputs are timestamped 18:06. The one-day slice run before the full run was 10-02,
  inside the choice period.

### 2. Execution (fills) — main issue, already flagged by the author; now quantified

- Model O fills whenever our price trades, as if first in the queue. I rebuilt fills with queue position from the
  raw prints (`a4_replay_queue.py`, `a6_queue.py`, sample of 175 markets / 149 events / 256 market-days of 7-11 Oct):
  Q1 = fresh order every minute behind the whole level shown at t_m, fills on a print through the price or when
  prints at our price add up to queue + our size; Q2 = same, but an unchanged unfilled order keeps its place and the
  queue ahead shrinks with the level (cancellations ahead allowed). Result, k = 0, no capital limit:

  | model | fills | net $/market-day | t (event) | settle c/share | net without 10 best markets |
  |---|---|---|---|---|---|
  | P | 1,124 | -1.30 | -0.96 | -2.04 | -3.73 (t -3.19) |
  | Q1 queue | 1,135 | -1.53 | -1.14 | -2.12 | -3.98 (t -3.46) |
  | Q2 queue, kept place | 1,212 | -1.37 | -1.02 | -1.97 | -3.83 (t -3.35) |
  | O | 3,653 | +3.15 | +2.79 | +0.05 | +1.16 (t 1.11) |

  The volume printed at our level almost never reaches the queue in front of a new 20- or 100-share order; the
  realistic answer is P, and O's extra ~2,500 fills are the benign ones. Severity: high for the O rows (they are an
  artefact), none for the verdict (the author already treats O as an upper bound and does not call it an edge).
- Latency: shifting the quote's life to (t_m + L, t_m + 60 + L] changes little: P -1.30 / -1.30 / -1.56 and
  O +3.15 / +3.00 / +2.85 per market-day for L = 0 / 2 / 5 s (`audit/out/a2_0.json`). The feed timestamp is the match
  time (Data API block time is 2.3 s later, author's `tapecheck.json`), so the "block minus 3 s" rule is not needed.
- Full-size fills on small prints overstate fills under O; under P a print through our price means the level was
  cleared, so the full fill is plausible.
- Mint/merge matches print on both tokens with BUY/BUY or SELL/SELL; mapped to YES terms the duplicate lands on the
  opposite side of the spread at the maker's price, so it cannot trigger a fill on our side. Checked on 10-08 12:00.

### 3. Fees and accounting — clean

- Maker only, fee 0, rebates 0; no taker trade exists in the strategy, so `pmlab.fees` is never exercised. No fee is
  counted twice because none is counted.
- Signs: my own ledger (YES fill PnL = (final - bid) x size, NO fill = (1 - final - NO price) x size) gives P
  settlement -$1,100 vs the author's -$1,015 and O +$84 vs +$244 on the same 256 market-days; per-market-day
  correlation 0.97 (P) and 0.93 (O). A completed pair nets 1 - YES bid - NO bid, as it should.
- Settlement values: 40 of 40 random markets agree with gamma `outcomePrices` (`a5_settle.py`); every one of the 565
  events has at most one YES winner (532 with one, 33 whose winning bucket was never in the reward universe).
- $1 floor: applied per market per day (conservative). With the floor per account, my run gives +$24.61/day (P,
  CI -10.5..+59.7, t 1.37) and -$13.84/day (O); the author's numbers (+$24.6 / -$13.8) match.

### 4. Statistics — the per-market O row is weaker than its t suggests

- Clustering by event treats 125-320 city-days as independent, but the 5 reporting days carry common moves. By
  calendar day (5 clusters): k0O late t 1.78 (daily totals +1,067, +222, +656, +1,611, -439), k0O early t 9.65,
  k0P late t 0.98, k0P early t -2.35. Without its best day k0O late is +$1.45 (t 1.76); k0P late is +$0.11 (t 0.18).
  Without the 10 best markets k0P late is $0.00/market-day.
- The account's t is computed over events and over days (author reports both; reproduced: 0.75 / 0.73 P,
  -1.39 / -2.12 O).
- Choice and reporting periods do not overlap (10-02..10-06 vs 10-07..10-11, UTC days); the class filter and the
  variant were taken from the first period only (recomputed: keep hours-to-end >24, 24-12, 6-3, 3-0, after end;
  drop 12-6 h and "alone"; best of six k0O at +$3.42).
- Variants: 7 pre-registered variants + 4 account runs (P/O x two periods) + the today's-rates rescale and the
  one-maker sensitivity; matches the count in results.md. One non-selected cell, k1P late +$1.70 (t 2.96), is
  -$0.77 in the choice period; with 14 variant-period cells this is not evidence, and the author does not claim it.
- Blind comparison: the strategy has no signal; the "blind" version is the strategy itself.

### 5. Data — clean, minor gaps stated by the author

- 243 hourly flat files and 243 hourly book files present (10-02T00..10-12T02); my replay of 7-11 Oct read 25.2 M rows and 65,644 book
  snapshots for the sample. In-universe minutes with a valid book 99.4-99.7% per day (author's qc files).
- Time zones: reward epoch = UTC day (as in the docs); local day from gamma eventStartTime (e.g. San Francisco
  07:00 UTC = local midnight PDT). Checked in `meta.json`.
- I did not implement the author's feed-vs-rebuild quality gate (it rejects 0.00-0.02% of instants); my book order is
  (timestamp, hour, row_ordinal) rather than (timestamp, book-before-change, hour, row_ordinal). These explain the
  small differences below.

### 6. Independent reproduction

- Raw replay, own code, sample = markets with int(condition_id) mod 4 = 0, 7-11 Oct (175 markets, 149 events, 256
  market-days = 20% of the reporting market-days and 47% of its events; a second quarter, 414 markets, was started
  twice and stopped, once by the memory limit and once for the time budget): raw reward $809 vs author $782 (P) and $762 vs $750 (O); fills 1,124 vs 1,107 (P) and 3,653 vs
  3,626 (O); per-market-day reward correlation 0.98 (P) / 0.99 (O); net per market-day -1.30 vs -1.08 (P) and +3.15
  vs +3.74 (O). Differences come from inventory carried in from 10-02..10-06 in the author's run (mine starts flat
  on 10-07) and the two details above.
- The 200-dollar account, own implementation on the author's per-minute build (validated above), own class filter:
  identical to the author's in every reported field (e.g. last5 P +13.438/day, 231 fills, 166 markets, t 0.752;
  last5 O -25.495/day, 652 fills, t -1.387; today's rates +0.204 and -32.16), `audit/out/a3_s1.0_b200.json`,
  `a3_s0.206_b200.json`.

## Other remarks

- The today's-rates factor (0.206 = median live rate / October median) is crude: an account that picks the top
  markets today would see higher rates (53 of 406 rewarded temperature markets pay $50/day or more, top $311), but
  also thicker books (the author's live check: $0.5-8.5/day per market at the six highest rates, median $1.58/day).
  It does not change the verdict; a rate-matched, sticky account is listed by the author as an untested idea.
- The account's greedy re-ranking every minute (37-39 markets a day) is what pushes 78-89% of its market-days under
  the $1 floor. That is the pre-registered rule, not a bug, but it is the main reason the account trails the
  per-market rows; a sticky rule would need a new protocol and new out-of-sample days.

## What a 200-EUR account could earn, and what trading it live would take

Expected value about $0/day. October, realistic (P-like) fills: about +$13/day (CI -$22..+$48) with the floor per
market, at best +$25/day (CI -$10..+$60) if the floor is per account; at today's rates about $0 to +$5/day before
any change in competition, with daily swings of +-$30-70 from fills. To trade it live you would need: the CLOB
WebSocket book and trades for every rewarded temperature market (not possible in this sandbox; a VPS or the Mac),
gamma reward fields polled at least every 15 minutes, re-quoting within a second and cancelling around routine
METAR times, a funded wallet with API keys and $20-100 of reserve per market, and, before any money, a recorded
queue-position test on live books for a few days, because the result depends entirely on how many fills a
back-of-queue order gets and on whether the $1 floor is per market or per account.
