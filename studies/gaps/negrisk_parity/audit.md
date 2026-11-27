# Audit of negrisk_parity (independent, fresh context, 2026-11-27)

## Verdict: WEAKENED (mildly). The money conclusion stands, two parts are less certain than written.

"Nothing to trade with 200 EUR" holds for A1, B2, C2 and for B1 as a whole-sample strategy. I found no mistake
that flips the sign or turns a negative into a positive. Two statements in results.md are stronger than the data
allow (below), and one protocol item was not delivered.

## What I recomputed (audit/recompute_b1.py, own replay, not a2_episodes.py)

Key number: B1 (neg-risk YES basket, asks + fees < 1, min top size >= 5 sets), late part, episodes still open 5 s
after they appeared. Own replay from the raw parquet of 4 late hours (24-26 Nov, 4 of 18 late hours = 22%):
2026-11-24T10, 25T14, 25T22, 26T06. My own event filter (non-augmented negRisk, every market live and unresolved at
the hour start), same fee formula (rate p(1-p), exponent 1 checked in gamma feeSchedule for all markets).

| hour | author R5 episodes | author clean (replay = exchange field) | mine, continuous 5 s | mine, continuous and field-confirmed |
|---|---|---|---|---|
| 24T10 | 0 | 0 | 1 | 0 |
| 25T14 | 7 | 5 | 14 | 6 |
| 25T22 | 18 | 0 | 18 | 0 |
| 26T06 | 7 | 1 | 12 | 1 |

Clean total 6 (author) vs 7 (mine), the one extra is in an event outside the author's stage-1 candidates. 25T22
reproduces exactly (18 vs 18, all stale-flagged: San Francisco temperature). 26T06 clean PnL at 20 USD: 0.035
vs 0.035. 25T14 clean PnL: 0.998 (author) vs 1.41 with my looser definition. The headline mechanics (episode
definition, fee, mirroring, field check) reproduce. The author's stage-1 screen from the exchange's own
best-price field is not hiding anything: the extra replay-only episodes I found (Helsinki 4, Lucknow 1 in 26T06)
are replay artefacts. Lucknow checked by hand: at the episode start the exchange field says sum of asks 1.085, the
replayed book says below 1. So the "clean book" filter is right and protective, not too strict.

## What I checked for a hidden effect

1. Continuity rule. The protocol says "takeable = the state at start + R still has net > 0". The code requires the
   episode to stay positive without interruption until start + R (stricter than the protocol text). I relaxed it
   (state positive at start + 5 s even if it flickered off in between): replay-only episodes go 45 -> 196, but
   after the exchange-field check only 7 -> 8. Not a hidden effect, the flicker is replay noise.
2. Fees: exponent 1 everywhere, rates per market (0.01 / 0.05 / 0), 590 markets with no feeSchedule fall back to
   category rates. No double counting in state(). Sign of B1 and B2 formulas correct. Time zone: all epoch ms UTC,
   consistent. Join NO-token mirroring correct (BUY on NO = ask in YES space at 1 - p). A1 formulas correct.
   `mirror_dropped` is true on the retained rows, not a sign of missing rows.
3. A1 (binary parity): 0 of 365,039 states and 0 of 4,121 REST snapshots, minimum ask sum 1.001. This is
   structural (the matching engine crosses complementary orders). Stands.
4. Time-of-week: weekends 21-22 Nov = 12 sampled hours only. Per-day figures are x4 extrapolations of 6 hours a day.

## Issues

1. Medium. The print check (rule 4, 38% vs 50%) is a weak test for B1. A resting ask on a quiet long-dated
   basket seldom prints in a few minutes, so absence of a print does not show that the quote is fake. Also the
   code counts any `last_trade_price` on any leg during the episode, with no price comparison (looser than the
   protocol text), so the 38% is, if anything, optimistic. Impact: the "fails rule 4" label should not be read as
   "the gap is not real". The real reasons to drop B1 are economic: +0.5 c per set, +0.09 USD per 20 USD trade,
   capital locked a median 36 days (about 5% a year), and some baskets without a certain payout. Those I did not
   find wrong. The conclusion is unchanged, the argument should be reworded.
2. Medium. The same-day exhaustive subset of B1 (weather buckets, post-count buckets) is the only part with fast
   capital turnover. It rests on 8 events and 11 episodes in 18 late hours (about 2.3 USD a day for everyone, post
   hoc, not pre-registered). That is under-powered, not a negative. "Nothing here deserves a micro-test" is fair on
   money (1-2 USD a day cannot pay for the work), but it is "too small to measure", not "does not exist".
3. Low. C1 early (+0.144 per trade, CI [0.011, 0.53], 11 events, 107 a day) is dismissed as one event in its expiry
   hour. 6 of 24 hours are sampled, so only about 23% of the 351 ladders that ended in the window have their last
   hour sampled (80 of 351; the 36 noon-ET ladders at 17 UTC never). If any real expiry effect exists in hourly
   crypto ladders, it is sampled at 25% density. Edge is 0.1 c per set, so even a real effect is worth cents.
4. Low. Protocol said depth beyond the best level would be reported as a descriptive extra. It was not reported
   (results.md Limitations says "not used"). B1 at larger size could look different, but only for the worse
   (fees and one level).
5. Low. Universe is the top 500 open and top 500 closed events by volume (+ all weather, all multi-strikes). Thin
   neg-risk events outside it are not scanned, and thin books are exactly where stale asks live. Stated by the
   author as a limitation. Not tested, so "never" cannot be claimed for them.

## Corrected headline

No tradable structural edge for a 5-20 USD account that reacts in seconds in the 36 sampled hours of the top
events: A1 0, B2 0, C2 0, C1 tiny (+0.005 USD per trade late). B1 gives real but tiny standing quotes (+0.09 USD per
20 USD, locked for weeks), and the print check is a weak argument against them; the same-day exhaustive part is
about 2 USD a day and under-powered. Re-run before closing the idea for good: B1 on same-day buckets and C1 on
final-hour-before-expiry ladders with denser hours, and a scan of events outside the top 500.

## Files
- audit/recompute_b1.py (own replay), audit/chk_lucknow.py (field vs replay check), audit/b1_<hour>.json (outputs).
- Not edited: results.md, protocol.md. No background process left running.
