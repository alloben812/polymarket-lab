# Audit: weather observation gap (independent, fresh context, 2026-11-27)

**Verdict: HOLDS**, with one scope caveat on the headline wording (see "Corrected headline").

## What I recomputed (own code, no import of the study's scripts: `audit/recompute.py`, `audit/dupes.py`, `audit/locked_nocap.py`)

Inputs: raw Iowa Mesonet METAR text, AWC JSON `receiptTime`, whole-market tapes, `markets.json` (bucket titles and resolution).
Own T-group / half-up (Decimal) parser, own zoneinfo local days, own running-maximum kill logic.

| number | study | audit |
|---|---|---|
| validation, rebuilt maximum vs official winner | 615/616 | 615/616 |
| newly dead buckets (kill events) | 3,335 | 3,335 |
| kills with an official receipt time (12-24 Nov) | 714 | 714 (of 776 kills in the window) |
| stale profit taken by takers BEFORE official receipt | $1,762 | $1,761.6 |
| stale profit taken AFTER official receipt (key number) | $39 in 13 days | $39.4 (0-10 s $19.3, 10-30 s $9.5, 30-120 s $10.7, later $0) |
| after obs+300 s: Oct / Nov | $926 / $200 | $926 / $200 |

Sensitivities on the key number: block-time lag 0 s instead of 3 s: $39.4; lag -5 s (prints counted later): $40.1; lowering the
stale-price floor from YES 0.02 to 0.005 (NO bought up to 0.995): $54.0 after receipt (before receipt $2,146). The 62 kills
that have no AWC receipt (AWC files them as SPECI or lacks them): $227 stale before obs+300 s and $0.0 after. Tapes of dead
buckets: 296,866 rows, 0 exact duplicate rows. Tape rows are in ascending time order (first_print logic is valid).

## What I checked and found clean

- Signs: NO pays when a dead bucket loses; 0 of 3,335 dead buckets resolved YES; Rule A pay = 1 - won, Rule B pay = won. Fee `0.01*p*(1-p)` applied once per fill.
- Join and time zone: IEM `valid` is UTC; local day bounds by zoneinfo; DST end (1 Nov) handled; my independent validation gives the same 615/616.
- Dead-bucket definition (running maximum, buckets with upper bound below it, top bucket never dead) is correct.
- Stale-profit direction: taker SELL Yes at p or BUY No at 1-p; profit = shares x YES price; correct for a dead bucket.
- Receipt data cover 714 of 776 kills (92%), all 11 stations; missing ones carry no stale money after obs+300 s.
- The only positive (Rule A d=5, 8 entries, all Denver, old KBKF rule) is correctly flagged non-repeatable; 1 November entry.
- Protocol was followed; 12 variants all reported; s8/s9/s10 labelled descriptive.

## Doubts (not changing the verdict)

1. **Rule A grid was in the wrong window for the question.** Delays were 5/15/60 min after obs+5 min (i.e. 10 min or more after the observation). The effect lives at 30-180 s after the observation; the study covers that only by the descriptive s10 cut (all takers, not a simulated single trader). My recompute confirms s10, so the answer for "react within seconds of the official receipt" stands, but no pre-registered rule tested "seconds after receipt".
2. **Rule B caps (0.80-0.95) are above where the locked bucket trades**, so by construction it barely trades. I ran the missing variant with no cap (same entry rule, `audit/locked_nocap.py`): 21 h: 22 entries, 20 wins, avg price 0.973, net -$57.6 (-8.5% on stake; Chicago 15 Oct and NYC 13 Oct old-rule losses); 23 h: 15 entries, 15 wins, avg price 0.9965, +$1.41 on $402 stake (+0.35%); 19 h: 87 entries, -$18 (-0.7%); 17 h: 425 entries, -$67 (-0.6%). In 594 of 616 city-days (21 h) and 601 of 616 (23 h) there is NO taker print on the locked bucket in 30 minutes: nobody trades it. No edge, and not even liquidity to test.
3. **Faster-feed hypothesis untested.** The takers who win trade 28-65 s after the observation time, before AWC shows the report (my probe: AWC receipt about 3 min after obs; api.weather.gov showed observations only up to 17 minutes old, so it is slower than AWC). Which feed they use is unknown. The study lists this as idea 1 and does not claim it is dead. Pool for all takers: $135/day (12-24 Nov, before receipt) to $171-179/day (all days), median profit per print $1.40, top 6 wallets take most. 
4. Celsius cities (37) were not re-run here; earlier pass says the same picture. Only 13 days of real receipts (AWC keeps about 400 reports).

## Corrected headline

"For a program that reads the official source (aviationweather.gov) there is no stale price left: all takers together got $39 in 13 days after the receipt. The stale money ($135-180/day for ALL takers across 11 cities, median $1.40 per print) is taken 30-180 s after the observation by traders with a faster feed that this study did not identify or test. Locked buckets are not tradable (no prints at 21-23 h)." That is a no-test for the owner's stated setup, but not a proof that no faster public feed exists.
