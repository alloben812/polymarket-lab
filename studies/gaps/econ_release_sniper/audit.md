# Audit — macro release sniper

Auditor: independent agent, fresh context, 2026-11-27 (~21:10-22:00 UTC). Checklist: `docs/audit-checklist.md`.
Own code in `audit/` (`recompute.py`, `by_release.py`, `extra.py`, `cpi_aug.py`); none of them imports the author's
`measure.py` or `diag.py`. Data: `data/gaps_econ/` (markets.json, release_status.json, confirm.json, tapes/), read
directly. Run: `python3 -I audit/recompute.py` (5 s), `python3 -I audit/by_release.py`, `python3 -I audit/extra.py`.
No network requests were made by the audit; no orders, wallets or keys.

## Verdict: WEAKENED

The arithmetic is right: every number of the 12 cells, the pool table and the early-print test reproduces to the
dollar from the raw tapes with independent code. The protocol was frozen before the analysis and the decision rule
was applied as written. But the headline ($170 a month for a 200 EUR account) is the optimistic end of what the tape
supports, for three reasons the headline does not carry:

1. **Queue position is assumed, not shown.** The primary "S" fill gives us 1/(k+1) of every stale print, including
   the cheapest ones in the first block. If the incumbents are matched before us (they are matched about T + 1-2 s on
   BLS/BEA releases, the same second we are supposed to be), we only get what is left after each market's first stale
   block: **$36 a month instead of $170** (whole period; reporting part $61, 95% CI 6-139).
2. **Half the money is in releases the proposed tests do not trade.** Tier-B non-US releases carry $279 of the $487
   (UK CPI October alone $122, 25%); the top three releases carry 46%. The paper test and the live micro-test trade
   only BLS/BEA + FOMC, where the same primary order makes **$82 a month whole period, $53 in the reporting part**;
   at the $10-20 tickets of the micro-test, **$40-56 a month whole, $15-25 in the reporting part**.
3. **The T + 1 s match is unproven and the latency budget omits order-entry latency.** No official source was shown
   readable within 1 s (the author says so). The latency table puts "order to matching" at 15-40 ms, but NOTES.md
   records practitioner reports of place-order p99 about 1.4 s on the current exchange, and a new matching engine
   ("Nex", sub-10 ms) going live mid-December, which will speed up the incumbents too. Taking only prints that were
   certainly matched after T + 1 s at any block lag (blocks 5-6) the primary drops to $117 a month (reporting part
   t 1.62).

## Corrected headline

Sample: 51 release seconds (36 days, 2026-09-01..11-25, 87 days), 268 markets, 229 mechanical; 20 release seconds
and 40 orders with fills in the primary. One prepared $50 buy per mechanical market at limit 0.95, matched at T + 1 s:

| fill assumption | whole period, $/month (95% CI) | reporting part (30 releases), $/month | BLS/BEA+FOMC only (micro-test scope), $/month whole / late |
|---|---|---|---|
| U: we displace every real taker (upper bound) | 258 (120-426) | 252 (93-464) | — |
| S: share 1/(k+1) of each print (author's primary) | **170 (83-282)**, reproduced | 217 (73-424), t 2.33 | 82 / 53 |
| strict timing: only blocks that certainly matched after T + 1 s | 117 (43-223) | 142 (25-335), t 1.62 | — |
| behind the incumbent: first stale block of each market lost | **36 (8-75)** | 61 (6-139), t 1.78 | 12 / — |

For an account of about 200 EUR with $20 tickets: $95 a month (S, all releases) down to $17 (behind the incumbent);
on the BLS/BEA+FOMC scope of the micro-test $56 down to $6 a month whole period, $25 in the reporting part.
**Realistically $0.2-2 a day**, before $10-80 a month of server cost, and only if a T + 1 s match is achieved.
For $2,000 with $200 orders: $345 a month (S), only 2x the $50 figure for 4x the size, because the prints, not the
order, limit the fill; behind the incumbent it would be a fraction of that.

## Checklist

### 1. Look-ahead — minor, acknowledged

- The winner is taken from resolution. For the 229 unflagged markets that is equivalent to reading the published
  number (one-number bucket rules); acceptable, but parse/mapping errors are therefore absent from every number.
  Break-even: net per filled order $12.17 on a cost of $36.84, so up to 25% of orders could be wrong before the
  primary is zero (`recompute.py`, last block). One wrong $50 order erases about four average fills.
- Release times: tier-A from official calendars; tier-B from the market's rules text, kept only if the tape moves
  within -5..+60 s (`confirm.json`). Seven tier-B releases were dropped on that test. This selects releases with a
  visible reaction, but dropped releases would add zeros to the total (per-month = total / days), so the total is
  not inflated. For the tier-B releases that contribute to the primary the tape move offsets are -1..+4 s (`by_release.py`), so the T + 1 s
  window is not pre-information on any release that contributes to the primary.
- US-CPI-august and US-EMP-august are "kept after investigation (noise print before T)", move offsets -20 and -26 s.
  Looked at the CPI tape (`cpi_aug.py US-CPI-august`): the prints at -15..-17 s are small loser-side prints; the
  winner-side stale prints start at block +4. No look-ahead found; CPI August ($57 of the primary) stands.

### 2. Execution (fills that could not have happened) — the main weakness

- Window: an order matched at T + 1 s takes prints with block time 4..6 (lab rule match = block - 3). With the
  measured lag 1.06-3.33 s, block 4 prints were matched T + 0.67 .. T + 2.94 s: part of them before our arrival.
  Strict version (blocks 5-6 only): whole $335 → $117/month, reporting $201, t 1.62.
- Queue: the S share is an assumption, not an observation. Behind-the-incumbent version (lose each market's first
  stale block): whole $104 ($36/month), reporting $87 ($61/month). The truth for a T + 1 s trader lies between these
  rows; nothing in the tape can tell which.
- Resting depth at T + 1 s is not observable from prints. The author's F1 check (11% of window gap dollars printed
  >= 5 c below an earlier post-T print, i.e. new offers) is reproduced in spirit: primary-window gap $5,561, 39
  wallets, top three 42% (author: $5,561). Median stale price in the window 0.88; 34% of prints at >= 0.90.
- Tape rows are VWAPs per taker order (NOTES.md); a 0.88 print may contain levels above 0.95 that our limit would not
  take. Not quantifiable; small.
- No liquidity used twice (one order per market, each print consumed once within the order). Capital: $50 orders
  need up to $244 in one release (author's capital.json; capping at $200 costs $5): consistent.
- Exact duplicate rows: 1,194 in the kept tapes, 56 within ±60 s of T, none at stale prices in the strategy window
  (de-duplicated rerun: primary unchanged, $487.0 / $306.4). They look like repeated bot orders, not page overlaps.

### 3. Fees — clean

Fee `0.01 × p × (1 - p)` per share, taker only, no rebates, matches NOTES.md for economics since 2026-11-21. At the
historical 0.04 the primary is $478 instead of $487 (`recompute.py`, "fee rate 0.04"). Direction (BUY winner / SELL
loser → winner offered at p / 1 - p) checked by hand on the UK CPI October and CPI August tapes.

### 4. Statistics — adequate, but thin and concentrated

- Clusters: release second (51). By calendar day (36): whole $170/month (82-283), t 3.29; reporting $217 (78-417),
  t 2.41 (`extra.py`). Clustering does not change the conclusion.
- Concentration: top three releases 46% of the primary; without UK CPI October $128/month; without the best ten
  markets $65/month (author: same numbers). Fills in 20 of 51 releases.
- Split: early part (to 2026-10-14) $125/month, reporting $217/month. Nothing tuned on either; the reporting part's
  excess over the early part is non-US ($225 of $306 late is non-US; US-only late $81, $57/month, CI 4-123).
- Variants: 12 cells + 5 declared robustness runs, all reported. My own sensitivity runs (arrival +2..+6 s, strict
  window, behind-incumbent, scopes) are labelled as auditor runs and are not new strategies.
- "Blind" comparison of the same rule without the signal is not meaningful here (the signal is the number itself);
  the early-print test plays that role: winner/loser-buyable $ at blocks -60..-1 10,452/4,115, 0..1 578/80,
  2: 1,528/26, 3..5 49,240/47, 6..13 48,359/416 — reproduced exactly.

### 5. Data — clean

268 kept markets, 229 mechanical, 51 release seconds, 21 early / 30 late, reproduced. 39 tapes are "stopped after
crossing T-2h" (newest-first fetch), all of them cover T. Pool table reproduced to the dollar: first block
$27,786 / $10,319, 40 wallets, 77%; all after T $116,341 / $30,536, 112 wallets, 46%. Fresh Sep-Nov tapes were not
re-downloaded by the author beyond a gamma check (protocol says so); the cache was audited by `econ_release_lag`.

### 6. Independent reproduction — done, full sample

All 12 cells match the author's `out/part1.json` to the cent (e.g. primary $487.0 whole, $180.6 early, $306.4 late;
A3 $200 S $2,246.6). Bootstrap intervals match (seed-dependent at ±$1).

### Protocol

`protocol.md` mtime 20:51:33 UTC, before `measure.py` (20:52) and every output (first 20:53); committed unchanged in
185d740 (20:55). Its header says "written ~20:58", which is wrong but harmless. Deviations: none found in Part 1.
The decision rule was applied correctly: the late-part primary passes the numeric test, Part 2 failed the source
test → "paper test only". That outcome is right.

## Part 2 and Part 3 — not re-measured

No HTTP probes were repeated (the author's 96 requests are in `out/sources.json`; not re-run to spare the shared
APIs). Points the design misses:
- order-entry latency (p99 ~1.4 s by practitioner reports in NOTES.md) is not in the budget; the paper test does not
  measure it either (it posts nothing);
- `paper_probe.py` polls bls.gov at 4 requests/s with a non-browser User-Agent; BLS answered 403 to scripts from the
  sandbox. If it also refuses the AWS box, the probe records no change and the BLS legs of the test fail silently —
  check the HTTP status before T;
- the paper test compares our detection time with a tape whose time resolution is ±1-3 s; its useful output is our
  own detection latency and the 1 s book snapshots (resting depth at T + 1 s), which is exactly the missing fact;
- Protocol V2 rollout on 1 Dec and the "Nex" engine mid-December change the race during the test window.

## Would the proposed live micro-test measure the claimed effect?

Partly. It measures whether a prepared order from our server is filled at stale prices on US releases, which
decides between the S row and the behind-incumbent row. It cannot confirm the headline: the headline's money is half
non-US, which the test does not trade; on its own scope the tape expectation at $10-20 tickets is $40-56 a month over
the whole period and $15-25 in the reporting part (17 US releases in 87 days, fills in 10; 23 filled orders).
Over 10 releases that is $20-90 expected in total, a factor-of-several noise band, so the test can show "ahead or
behind" from fill prices, not the dollar edge — as the author says.

## Owner's actual set-up (Mac in Serbia, a few seconds)

Auditor sensitivity, $20, S share: matched at T + 3 s $292/month all releases but t 1.34 and $504 of $836 from one
release (RBNZ October); BLS/BEA+FOMC only $89/month whole, $70 reporting part; behind the incumbent $21/month. At
T + 6 s it is $10/month in the reporting part. A home machine that reacts in "a few seconds" is in the middle of the
incumbents' main wave; what it gets depends entirely on queue luck, and BLS pages refuse scripted clients.

## To trade this live you would need

A detector that reads the official number (BLS, BEA, Fed; ONS for UK CPI, which carried a quarter of the money)
within about 0.5 s of the publication second from a machine the agency does not block; a pre-built table
"number → winning token" per market with zero tolerance for an ambiguous parse; pre-signed fill-and-kill buys at
0.95 that are matched within about 1 s of T — which needs order-entry latency far below the reported 1.4 s p99; and
proof, from 1-second book snapshots at real releases, that stale offers are still resting at T + 1 s and that our
fills are not just the leftovers after the incumbents. If all of that holds, an account of about 200 EUR makes
roughly $0.5-6 a day on all releases ($0.2-2 on US releases only), minus the server. If any one fails, it is about zero.
