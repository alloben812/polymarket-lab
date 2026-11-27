# Audit of the calibration map (independent, fresh context, 2026-11-27)

## Verdict: WEAKENED

The pooled negative result is correct and reproduces to the digit. What is NOT established is "no edge in the short-dated crypto
up/down families" and "no edge in daily weather": the pre-registered grid never looked at the part of those markets where an effect
would live. Re-run those two before treating them as dead. Nothing found here is a reason to send real orders either.

## What I recomputed (audit/recompute.py, own code, reads only data/gaps_calibration_map/ph.jsonl and sample.jsonl.gz)

Pooled buy-the-favourite, shown price + slippage + taker fee, one market per horizon, cluster = gamma event:

| part | gross c/sh | net c/sh (95% CI) | t | obs | events |
|---|---|---|---|---|---|
| early | +0.278 | -1.079 (-2.05..-0.11) | -2.18 | 16,706 | 5,087 |
| late | +0.216 | -1.174 (-2.52..+0.17) | -1.72 | 9,426 | 2,677 |

All six numbers match results.md. The join is right (a wrong outcome/token join would give a large gross edge, not +0.2 c),
the sign is right, the fee is counted once (rate*e*(1-e) on e = price + slippage).

## What I checked and found sound

- Fee, slippage, payoff, bucket edges, early/late split, event clustering: as in protocol.md; the late CI includes zero, so
  "-1.2 c" is a point estimate, not proof of a loss.
- No look-ahead: price is the last point at or before o minus the bucket; market must be open at o.
- 0 of 828 cells: the decision code in s4_cells.py is the protocol rule. The protocol was written before outcomes.
- Gross favourite edge about 0 pooled: shown prices are calibrated on average, so the cost (slippage + fee) is what is lost.

## Problems that weaken it

1. **Up/down 15m, 1h, 4h horizons are all before the window opens (most important).** Because the price used is the last point
   at or before o minus 300/1800 s, I measured where it sits relative to the window start (audit/probes.py):
   updown-15m, horizons 24 h / 6 h / 1 h: 0% of used prices are inside the window, mean favourite price 0.504-0.507, 99-100% below
   0.60; horizon "10 min": median price time = exactly the window start (0 s), 0% inside the window. updown-4h: only the 1 h and
   10 min horizons are in-window. So for the biggest short-dated family (407 markets/day) the study tested "does the
   pre-open price of a coin flip predict the flip", and the answer is trivially "no". results.md describes the
   candidate as "leader five minutes into the window"; it is the leader AT the window open. The in-window path (price 5-10
   minutes in, favourite at 0.70-0.95 versus the Binance move) was not tested. The study itself calls the 5 m exclusion a
   "no usable horizon" case; the same holds for 15 m at 300 s buckets.
   Exploratory check (audit/inwindow_eval.py, not pre-registered, 200 random late 15m markets, 300 s buckets):
   5 min into the window, buying the favourite loses about 1.9 c net if the 5-min-old price is used (n=200) and the freshest
   point gives -6.5 c; 10 min in: -1.7 c (freshest point) or -6.5 c. Bucket 0.70-0.90: win rate 0.73-0.75 vs price 0.79-0.81.
   n is far too small for any conclusion (standard error of a bucket about 4-5 c); it is a pointer for a re-run, not a result.
2. **Weather anchor inconsistent (the author found it, but it breaks the early/late rule for this family).** Only 132 of
   934 early weather-temp markets carry eventStartTime (anchor = 12:00 UTC of the target day; for a New York market that is
   07:00 local, before the day starts); all 466 late ones have it (anchor = end of local day). Early and late horizons
   measure different things, so a late-day effect cannot be a candidate (no early counterpart) and a day-ahead effect cannot be
   confirmed. Late weather has only 25/27/44 observations at 10 min / 1 h / 6 h (favourites already above 0.995) and no horizon
   near the afternoon peak (about 8-12 h before the local end), where stale prices would matter. Pooled weather-temp favourites
   are positive in both halves (+1.03 c early, +1.16 c late, t 0.9 / 0.7); at 24 h gross +3.1 c early (net +2.25, t 2.0) and +1.8 c late
   (net +0.91, t 0.5). Not significant, but not "calibrated to within 1 c" either, and it is the family with 461 markets/day.
3. **Power, not bias, limits the negative.** Cells have 20-300 events; only 10 cells had >= 200 late events. The study cannot
   exclude 1-3 c edges, which is the size that matters after a 1-2 c cost. "0 of 828" means "none detectable", not "none exist".
4. **Only taker entries.** The 0.98-0.995 bucket shows +0.46..+1.04 c gross at every horizon in both halves; as a maker bid
   (no fee, no spread) that is a different answer. Listed under "Ideas", correctly, but it is the one pattern that was consistent.
5. Minor: the price-time lag (300 / 1800 s) means "24 h" is 24.5 h and "6 h" is 6.5 h for pre-28-Sep markets. 4% of sampled
   markets returned no points (407), not analysed for what they are.

## What would be needed to trade live (nothing is justified today)

Nothing in the map clears the bar. If the owner wants one cheap test, the order is: (a) re-run updown-15m with 60 s buckets
(available for the last 7 days) or tapes at fixed in-window offsets, pre-registered, ETH/SOL/XRP at the 0.01 fee, 1,000+
windows; (b) re-anchor weather-temp to local end of day for all months (city time zones) and add 8-12 h horizons.
Money bound from the data: pooled taker net -1.2 c/share (late CI upper end +0.17 c), i.e. about -1.7 USD per 100 USD of
turnover at price 0.70; the best case is +0.2 USD. At 1-20 USD tickets a 50-100 USD test cannot tell these apart.
