# Audit: cross_venue_signal (fresh-context sceptic, 2026-11-27)

## Verdict: WEAKENED

The numbers are right and the specific rule that was tested loses. Two parts of the headline say more than the data supports. Neither changes the sign of the tested rule.

## Recomputed (own code: `audit/recompute.py`, `audit/checks.py`, `audit/leads.py`)

The code uses the football-data CSVs, the cached tapes and only the cid/outcome mapping from `matches.json`. It has its own de-margining, its own Tuesday/Friday 18:00 UTC time, its own kick-off from the CSV `Date`/`Time` converted from Europe/London, and its own fill and fee code.

- **Protocol trades match exactly.**
  - S1 X=3: 8 trades; early 5 at -38.0%, late 3 at -34.8%.
  - S1 X=5: 1 trade at -102.8%. S1 X=8: 0.
  - S2 X=3: 6 trades; early 2 at -17.2%, late 4 at +79.4%. S2 X=5 and X=8: 0.
  - The CSV-derived kick-offs equal the study's `k` for all 724 matches. All 724 tapes are sorted in time, so the `break` in `candidates()` is safe. None of the 2,172 tapes is empty. The largest tape has 9,486 rows.
- **Time zone, sign, join.** Home/draw/away order, the Yes/No fair values and the win logic are consistent. The study's check that gamma `outcomePrices` equals FTR on all 724 matches also validates the home/away mapping. The fee is 0.05*p*(1-p) per share, with rate 0.05 on all 724 markets. Fees are counted once.
- **Who-leads claim.** "62 of 81 outcomes with a gap of 2+ points, the bookmaker moved toward Polymarket" reproduces: 81 outcomes, bookmaker 62, Polymarket moved toward the bookmaker in 45.

## Variants the protocol did not run (my re-runs)

1. **Taker SELL prints as buyable complement.** A taker SELL of Yes at p shows a resting bid, which is a No ask at 1-p. This is not an impossibly strict fill rule. It adds 1 trade to S1 X=3 (9 trades: early +3.2%, late -34.8%) and 0 to S2. It is immaterial.
2. **S1 window widened from E1..E1+30min to E1..kick-off-30min.** The 30-minute window is in the protocol, but it decides the "very rare" claim.
   - X=3: **220 trades, -6.3% per dollar (se 7.3, day-clustered se 6.5)**; early -10.1%, late -3.0%.
   - X=5: 59 trades, -22.4% (se 13); early -25.8%, late -19.5%.
   - X=8: 7 trades, -21.8%.
   - Trades come a median 3.3 h before kick-off. So against the Friday/Tuesday line the gap is not rare. It is common, and buying it loses, which supports the "bookmaker is stale" reading.
3. **S2 closing line over a wider window (look-ahead, upper bound only).**
   - Last 30 min: 6 trades, +47% (se 32).
   - 3 h before kick-off to kick-off: X=3 gives 87 trades, **+9.5% (se 13)**; X=5 gives 13 trades, +8.1% (se 35).
   - The closing line contains later news, so this is biased upward. It cannot be a backtest, but it does not rule out a live-feed edge either.

## What is weakened

- **"Gaps of 3 points or more that could actually be bought are very rare" is an artifact of the window.**
  - The study used 30 minutes after Friday/Tuesday 18:00 UTC. In that window 372 of 724 matches have any taker buy.
  - Over E1..kick-off, 718 matches have prints and 220 (30%) reach a 3-point gap. The correct statement is "rare in the 30 minutes after 18:00, common later, and losing against the stale line".
  - The 8-trades-in-103-days figure and the "0.06-0.08 trades a day" capacity line should not be quoted as the opportunity rate.
- **"Clean negative / nothing to test" overreaches for a live signal.**
  - The only signals tested are a twice-a-week snapshot (S1) and the closing line (S2). Both are weak proxies for what the owner would run: a live Smarkets or other exchange price compared with Polymarket every few seconds. The archive cannot test that.
  - The study's own "Ideas" section proposes a Smarkets paper-log. That is the right next step, but it is a paper-only test costing no stake, not a live-money micro-test.
  - The protocol's rule "S2 alone positive means a live feed test on paper only" was not reached, because S2 had only 6 trades. The verdict should read: "S1 (archive snapshot) is dead; live-feed signal unmeasured".
- **Narrow scope, as the study admits.** Soccer only, six leagues, no tennis (403), no Pinnacle. The raw folder has N1 (Eredivisie) and P1 (Primeira) CSVs that were not used. 28 matches were dropped for name matching.

## Checked and clean

- No look-ahead in S1. E1 is 18:00 UTC against a Friday-afternoon collection, and median E1 is 22.5 h before kick-off with a 96 h cap. S2 is flagged as look-ahead by design.
- Per-match unit with one trade per match, so there is no double use of liquidity.
- Block time is used as trade time without the AGENTS rule's -3 s. This is irrelevant for 30-minute windows and median 9-minute and 15-second lags.
- The outcome is used only for P&L.
- Cheap-side (>=3 points under fair) taker buys in the S1 window number 169. Rich-side buys number 566, so the median print sits 0.4 points on the expensive side, which is the spread. That is not a sign error.
- Early/late split is by kick-off time. X is chosen on early only, and the 20-trade bar was never met, so nothing was selected.
- All 8 trading variants are counted.

## What should be re-run

- S1 with E1..kick-off-30min as a protocol-style variant, reported early/late, with the day-clustered error. I have done the pooled version above.
- A live paper-log (Smarkets vs Polymarket books, 2 weekends) before the idea is declared dead.
