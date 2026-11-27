# Counter-settled markets (post counts): does a simple counter model beat the bucket prices? — results

Study run 2026-11-27. Protocol: `protocol.md` (saved before any outcome number). Code: `fetch.py` (downloads),
`analyze.py` (the protocol run), `supply.py` (events per week), `diag.py` (post-hoc diagnostic, marked as such).
Outputs: `out/report.txt`, `out/variants.csv`, `out/trades.csv` (one row per entry of the selected variant),
`out/supply.txt`, `out/diag.txt`. Raw data: `data/gaps_counter/` (posts, trackings, 1,888 whole-market tapes).

## Verdict: INCONCLUSIVE by the protocol rule, and in practice NOTHING TO TEST with money

- The variant chosen on the early half (pace model, enter when model minus price minus fee >= 10 cents) made
  **+8.5% of dollars spent on the late half, t = +0.33 by event** (145 entries, 39 events, $1,416 spent, +$120 net;
  95% interval for the total -$476 .. +$932). Without its best event it is **-13.9%**. The other three variants
  made +12.7%, -6.4% and -2.7% in the late half; no variant has |t| above 1.6 in either half.
- **The price is a better forecaster than the counter model.** For the first print of every bucket token in the
  decision windows, the Brier score (lower is better) of the price beats the model in 15 of 16 cells
  (2 models x 2 halves x 4 horizons): late half, pace model 0.159 vs price 0.152, profile model 0.174 vs 0.152
  (669 prints, 57 events). The model's "edges" are mostly its own over-confidence: entries with model
  probability 0.8-0.9 won 63% (late) against a paid price of 0.66.
- In the current fee regime (events ending on or after 2026-11-21) the selected rule lost: 24 entries, 6 events,
  -88% of $ (one win in 24). Entries decided on a Saturday or Sunday lost -48% (27 entries, 15 events).
- Repetitions needed to tell an edge from noise are out of reach: the per-event spread of returns is about 160% of
  the dollars spent, so a real +10% edge needs about 1,000 events and +30% about 115 events (25 weeks of the
  Elon events at 4-5 a week). A 50-100 USD live test cannot answer the question, so none is proposed.

**For the owner's question about weekends.** These markets do run through weekends: the counter keeps counting,
Elon Musk has three 2-day events a week (some end on Saturday or Sunday), the 7-day events of eight accounts span
every weekend, and box-office buckets are a weekend product (Friday-Sunday, settled on Monday's final figure). So
"stocks are closed" is not the limit. The limit is that the simple "rate so far" model is not better than the
crowd: hours or days before the end, the bucket prices already contain the pace. The time gap that does exist here
is the counter's own delay (a post shows up in the official counter about 2.7 minutes after it is written, see
the culture study), and that is a minutes-long gap on one post, not a mispricing of the bucket.

## Question

Markets settled by one public counter or table (number of posts of a public figure in a period, weekend box
office, chart positions, review scores, app ranks): does a simple model of the counter (the rate so far, an
hour-of-week pattern) beat the bucket prices after the 0.01 taker fee, with entries hours or days before the end
rather than seconds? How many such markets run per week? The model test is run on the post-count family only,
the one family whose counter has a public, timestamped history (`xtracker.polymarket.com`); the other families are
counted.

## Data

- **Events**: every xtracker tracking with a market link, 2-day or 7-day window, window end 2026-10-01 .. 2026-11-27
  17:00 UTC: 146 events, 1,888 bucket markets. elonmusk 24 two-day + 16 seven-day; realDonaldTrump 16; WhiteHouse,
  ZelenskyyUa, NYCMayor, cz_binance, tedcruz, khamenei_ir 15 each (seven-day). Two events (ending 2026-11-27) were
  not yet resolved and were dropped: 144 usable. The budget rule (stop downloads at 19:40 UTC) did not bite.
- **Counter**: `/api/users/<handle>/posts`, 2026-08-26 .. 2026-11-27, 12,415 posts in all (elonmusk 3,563,
  realDonaldTrump 2,499, WhiteHouse 2,855, tedcruz 1,605, ZelenskyyUa 1,032, cz_binance 437, NYCMayor 403,
  khamenei_ir 21). Import lag (importedAt - createdAt): median 159-238 s, p90 293-365 s by account.
  Information at time t = posts imported by t. The tracker's final count fell in the resolved bucket in 141 of 144
  events; the three misses are Zelenskyy events of 2-16 October (tracker 15-61, resolved 80-119: the counter's
  history for that account is incomplete in early October). All three are in the early half and were kept.
- **Tapes**: whole-market taker tapes for all 1,888 markets, 666,932 rows, $25.8M of taker turnover. Tape share
  totals equal gamma `volumeNum` (checked on 24 markets from the largest to $1.2K): the tapes are complete.
- **Split**: events sorted by end; EARLY 72 events ending 2026-10-02 .. 10-27, LATE 72 ending 10-27 .. 11-25.
  Unit = event.
- **Fee**: 0.01 x p x (1-p) per share on every entry (fee type `culture_fees`, rate 0.01 today). Prices before
  2026-11-20 were set by traders who paid a different fee (zero on 20-31 October in several categories).

## What was run (every variant)

- Models: **M1 pace** (remaining = count so far x time left / time elapsed); **M2 profile** (28-day hour-of-week
  profile of the account, scaled by the count so far). Remaining count ~ negative binomial; dispersion fitted on
  EARLY counts only (k = 3 at 72 h, 1 at 24/12/6 h for both models: the remaining count is very dispersed).
- Entry: decision times 72, 24, 12, 6 h before the end (only if at least 24 h of the window had passed). Within
  30 minutes after each, the first taker print per bucket token that shows a price c with
  model - c - fee >= theta, 0.02 <= c <= 0.97 (a taker sell of one token counts as an available buy of the other at
  1 - c). Size = min(print size, $20 / c). Hold to resolution.
- **Four strategy variants**: {M1, M2} x theta {0.05, 0.10}. One sizing re-run ($5 cap) of the selected variant.
  Descriptive cuts written in the protocol (fee regime, weekend, handle group, side, horizon). One post-hoc
  diagnostic (`diag.py`, Brier score of model vs price), one post-hoc cut (Elon 2-day vs 7-day, below, under
  "Ideas"). Nothing else was run.

## Headline numbers (after fees, $20 cap)

| variant | half | entries | events | $ spent | net $ | c/share (se) | net % of $ | t (event) | 95% CI total $ | % w/o best event |
|---|---|---|---|---|---|---|---|---|---|---|
| M1 theta 0.05 | EARLY | 209 | 39 | 1,840 | +324 | +3.3 (3.2) | +17.6 | +1.06 | -240 .. +975 | +9.5 |
| M1 theta 0.05 | LATE | 226 | 44 | 2,170 | +276 | +3.1 (4.2) | +12.7 | +0.75 | -352 .. +1,093 | -0.6 |
| **M1 theta 0.10 (selected)** | EARLY | 146 | 35 | 1,313 | +413 | +6.2 (4.2) | +31.5 | +1.55 | -95 .. +1,018 | +19.9 |
| **M1 theta 0.10 (selected)** | **LATE** | **145** | **39** | **1,416** | **+120** | **+2.1 (6.4)** | **+8.5** | **+0.33** | **-476 .. +932** | **-13.9** |
| M2 theta 0.05 | EARLY | 202 | 39 | 1,820 | +236 | +2.6 (3.4) | +12.9 | +0.81 | -320 .. +854 | +3.9 |
| M2 theta 0.05 | LATE | 246 | 46 | 2,427 | -156 | -1.6 (3.8) | -6.4 | -0.42 | -791 .. +644 | -19.3 |
| M2 theta 0.10 | EARLY | 152 | 37 | 1,420 | +112 | +1.8 (4.2) | +7.9 | +0.43 | -361 .. +660 | -4.2 |
| M2 theta 0.10 | LATE | 184 | 43 | 1,811 | -49 | -0.7 (5.0) | -2.7 | -0.13 | -642 .. +735 | -20.6 |

Selected variant at the $5 cap: EARLY +32.5% (t 1.16), LATE +17.7% (t 0.56, 145 entries, $581 spent, +$103).

LATE cuts of the selected variant (descriptive, protocol-listed):

| cut | entries | events | net % of $ | t |
|---|---|---|---|---|
| events ending >= 2026-11-21 (current fees) | 24 | 6 | -87.9 | -8.4 |
| decision on Sat/Sun UTC | 27 | 15 | -48.0 | -3.3 |
| decision Mon-Fri UTC | 118 | 35 | +18.5 | +0.64 |
| elonmusk | 113 | 20 | +14.9 | +0.49 |
| other seven accounts | 32 | 19 | -23.7 | -0.99 |
| buy YES / buy NO | 53 / 92 | 36 / 32 | +24.9 / +1.7 | +0.37 / +0.11 |
| 72 h / 24 h / 12 h / 6 h before the end | 19 / 67 / 34 / 25 | 15 / 28 / 21 / 16 | -33.5 / +1.3 / +19.1 / +39.9 | -1.5 / +0.06 / +0.37 / +1.27 |

The seven smaller accounts barely trade: the selected rule entered only 35 of their 106 events (32 entries in 19
events in the late half).

## Opportunities, size and capacity

- LATE half, selected rule: 145 entries in 28.5 days = **5.1 entries a day**, $50 a day spent at the $20 cap, mean
  spend $9.77 per entry (only 28% of entries could fill the full $20 at the printed size).
- **Net per trade: +$0.83 at the $20 cap, +$0.71 at the $5 cap**, both with a confidence interval that includes
  large losses (the late total's 95% interval is -$17 .. +$33 per day).
- **Capacity for a ~200 EUR account**: about $50 a day of entries, held to the end (mean 24 h); capital tied at any
  time about $50 on average. The ceiling is the printed size, not the account. Expected net at the point estimate $4 a day,
  indistinguishable from zero.
- **Reaction time needed**: minutes. Entries are 6-72 hours before the end, the window is 30 minutes, and only 3% of
  late entries followed a 5-cent move of the same token in the previous 60 seconds. This is not a speed game; it
  is a model game, and the simple model loses it.

## Supply: how many counter-settled markets run per week (`out/supply.txt`)

Closed events with an end date in ISO weeks 40-48 (2026-10-01 .. 11-27), gamma tag listings. "Volume" is gamma's
event volume, which counts shares, not dollars (dollar turnover on the post-count tapes is about a third of it).

| family | events / week | gamma volume / week |
|---|---|---|
| Elon Musk post counts (2-day and 7-day) | 4.4 | 7.4M |
| other post counts (Trump, White House, Zelenskyy, NYC Mayor, CZ, Cruz, Khamenei) | 11.8 (7-8 from week 47) | 0.34M |
| box office (opening weekend, domestic gross) | 5.9 | 0.43M |
| YouTube views (MrBeast etc.) | 5.6 | 0.46M |
| Spotify chart positions | 3.8 | 0.07M |
| App Store ranks | 3.2 | 0.03M |
| Rotten Tomatoes scores | 2.6 | 0.06M |
| Billboard chart positions | 1.8 | 0.03M |

About 40 counter-settled events a week, each with 10-30 buckets. Post-count events of the six smaller accounts
stop after the tracking windows ending 2026-11-24 (none listed for later windows on 2026-11-27).

## Attacks on the result

- Look-ahead: the count uses `importedAt` (what the counter showed), the profile uses only posts before the window,
  the dispersion was fitted on EARLY counts only (so EARLY is in-sample for it and for the variant choice; LATE is
  not). Outcomes are the resolved bucket prices, not the tracker count.
- Fills: each entry is a printed taker trade at that moment, capped at the printed size; the counter-side mirror
  (sell of one token = buy of the other at 1 - p) uses the order's average price. Realistic depth is unknown (no
  order-book history for these markets here); the print rule is, if anything, generous, because the printed
  liquidity was taken by someone else.
- Concentration: removing the best late event turns every late variant negative.
- Sample: 39-46 late events with entries per variant; the post-Nov-21 regime has 6.

## Live micro-test

Nothing here deserves a live test with money. The selected rule's late result is +8.5% with t = 0.33 and turns
negative without one event; the market's prices forecast better than the model; the current-fee slice lost; and a
50-100 USD test would need hundreds of events to separate a plausible edge from noise. If the owner wants a zero-cost
check, the rule can be logged on paper (M1, theta 0.10, the four horizons, Elon events only) for 20 weeks; stop and
drop it if the paper log is below zero after 40 events.

## Limitations

- Only the post-count family was tested. Box office, charts, scores, ranks and YouTube views were counted, not
  modelled (no timestamped history of their intermediate values here; The Numbers is blocked). The culture study's
  box-office results stand: following 10-cent jumps lost 9.7 c/share (t -2.3, 50 markets) and one specialist
  (cat-dog) profits with a richer model.
- Two simple models only, one dispersion per horizon pooled over eight very different accounts.
- Fills from prints, not from order books; no maker orders tested.
- Fee 0.01 applied to all dates, while the prices before 2026-11-20 were formed under other fees; only six late
  events fall in the current regime.
- The counter's history may be revised after the fact (deleted posts, the incomplete early-October Zelenskyy
  history); a live trader would have seen slightly different counts.

## Ideas, not tested

- **Elon 7-day events only** (post-hoc cut seen after the results, not a protocol variant): selected rule +43% of $
  on 8 EARLY events (t 1.5) and +63% on 7 LATE events (t 1.05, $304 of the $339 from one event), while the 2-day
  events made +26% then -25%. A forking-path lead at best; it would need its own protocol and a forward sample.
- Blend model and price (shrink the model toward the market) and trade only where both agree with the counter's
  latest hours; per-account dispersion.
- Resting maker bids on the bucket next to the pace bucket in the last 6-24 hours (the hixlz pattern in the
  culture study): no fee, but needs queue modelling or an order-book replay.
- Box office: Friday actual x weekend multiplier, with Box Office Mojo daily figures, against the Saturday prices.
- Near-certain carry in counter markets (buckets above 0.95 once the count makes them almost certain).
