# Audit: mentions_model (independent sceptic, fresh context, 2026-11-27)

## Verdict: WEAKENED

The money conclusion stands: nothing here is worth a live test at the size and speed of the owner's setup, and weekends are
negative for both rules. One part of the "no edge" wording is doubtful. The frozen V1 buys at the FIRST print of a 24-hour
window (median 17 h before the start). The earlier wallet lead that V1 comes from used the LAST price before the start. An
entry timing the protocol did not run (the last 6 hours) is positive in both halves. It is post hoc, so it is a lead and not
a result. I found no wrong sign, wrong join, wrong time zone, double fee or truncated tape.

## What I recomputed (`audit/recompute_v1.py`, own code, reads only the raw gamma events and raw cached tapes)

Key number: V1 pooled, return on stake after the 0.01 fee, error clustered by event.

| | trades | events | stake | pnl | return | 95% |
|---|---|---|---|---|---|---|
| pooled (mine) | 1,173 | 243 | $14,172 | +$507.3 | +3.58% | -0.97 .. +8.13 |
| S1 (mine) | 665 | 144 | $8,019 | +$656.0 | +8.18% | +3.11 .. +13.25 |
| S2 (mine) | 508 | 99 | $6,153 | -$148.7 | -2.42% | -10.22 .. +5.38 |

All three match `results.md` to the cent, trade for trade. I did not import `analyze.py`, `universe.py` or `pmlab.stats`.

## What I checked, no fault found

- Sign and join: No wins when `outcomePrices` is [0,1]. The outcomes are exactly ['Yes','No']. Rows are matched on conditionId.
- Fills: the tape holds taker rows only, so "taker BUY No at x" and "taker SELL Yes at 1-x" are the right mirror. The
  3-second lag is applied. Epoch seconds are used throughout, so there is no time-zone problem.
- Fee counted once, as `0.01*sh*p*(1-p)`. It matches the raw `feeSchedule` (rate 0.01, exponent 1). At 0.04 V1 is +2.7%
  (S1 +7.4%, S2 -3.3%), so the fee does not decide the result.
- Tapes are not truncated: the longest holds 52,523 rows, far past any page limit.
- Start time: the median first close is 2-3 h after the stated start, so the window really is pre-event. The sample keeps
  events whose start time looks like a placeholder only if it passes the closing-time test.
- Priors for V2 use only markets closed before the entry row, from other events. I saw no look-ahead.
- Every protocol item was run: V1, V2, +1 cent, weekend split, three-best-events attack, bootstrap. S3 is empty and the
  study says so.

## What is doubtful

1. **Entry timing (the main point).** Same data, same rule, same fee. All of these are post hoc.

   | entry | pooled return (95%) | S1 | S2 |
   |---|---|---|---|
   | first row in [-24h, -5m] (frozen) | +3.6% (-1.0..+8.1) | +8.2% | -2.4% |
   | first row in [-24h, -6h] | +2.2% (-3.0..+7.5) | +8.1% | -4.2% |
   | **first row in [-6h, -5m]** | **+7.5% (+1.9..+13.1)**, 786 trades, 190 events | +9.8% | +4.0% |
   | last row in [-6h, -5m] | +7.4% (+1.7..+13.1) | +11.4% | +1.5% |
   | last row in [-24h, -5m] | +0.8% (-3.9..+5.5) | +4.4% | -4.6% |

   The [-6h, -5m] variant would pass all four frozen criteria: positive in both parts, pooled lower bound above 0, and
   more than 30 events and 150 trades. It also survives the attacks. Without the 3 best events it gives +6.0% (+0.4..+11.5),
   at +1 cent +6.0% (+0.5..+11.5), and at fee 0.04 +6.7%. By month: Aug +7.2%, Sep +12.9%, Oct +2.4%, Nov +4.7%.
   Caveats: I looked at about 10 timings, so the p-value of roughly 0.007 is nominal. The windows overlap and are not
   independent. It was chosen after seeing results. It needs a new protocol on fresh data.
2. **Weekends.** The same variant is -1.4% (-11.9..+9.0) on weekend starts (109 trades, 23 events) and +9.0% on weekdays.
   The owner's weekend question gets the same answer as in `results.md`: nothing on weekends.
3. **Money.** The [-6h] variant is about 6.6 entries a day, an average stake of $10 and +$590 in 119 days, which is
   about $5 a day, weekdays only. The size problem in `results.md` is real, so even if real the edge is tiny.
4. **Left out of the sample.** About 950 "this week / in <month>" period markets in 67 events were excluded because their
   start time is the end of the counting period. They run through weekends and nobody tested a base-rate rule on them.
   Only 355 live markets in 24 events were dropped for a bad start time, so the "24% dropped" figure is mostly period events.

## What should be re-run

- A new frozen protocol: V1 entry in [start-6h, start-5m] only, on events after 28 Nov. Run it as a forward paper log first,
  since it costs nothing and gives the 0.01-fee sample that S3 lacks. Earnings season starts again in late January.
- If a live micro-test follows, size it at $5-10 a trade on weekday events only. At 2 standard errors, telling +$0.7 a trade from
  zero needs roughly 700-1,000 trades, which is months. It cannot pay for itself, so it should be treated as a measurement.
- Optionally, the same base-rate idea on period markets with a creation-based window.

## Not done

I did not test the V2 key construction against real transcripts, and I did not re-run V2 with my own code.
