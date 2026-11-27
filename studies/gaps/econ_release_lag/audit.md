# Audit — scheduled economic releases (`studies/gaps/econ_release_lag`)

Auditor's pass, 2026-11-27. Nothing in the analyst's files was edited. My scripts are copied to `audit_scripts/`
(they were run from a scratch directory, so the paths inside point there; the downloads they made are not kept).

## Verdict: WEAKENED

Every number in the headline reproduces to the cent, on three independent data paths. The description of the
market (absorbed in about 5 s, 98% of the stale money gone within 30 s, a handful of wallets) holds. What does
not hold is the small positive remainder: the "+30 s: $7-13 a day, t = 1.84" is not money left lying for a
late taker. It is made of one event whose clock time is not the publication second, one event where the
market itself disagreed about the answer for 100 s, late "carry" fills, and offers that appeared after the
price had already moved. Cleaned of those it is $0 in the US official releases and about $1-6 a day elsewhere,
and the t-statistic means nothing. The analyst's own conclusion (no dependable edge at +30 s) gets stronger;
by the evidence it should read NO EDGE at 30 s and later, not INCONCLUSIVE.

## What I reproduced (step 6)

| check | coverage | result |
|---|---|---|
| Own E1-E4 code on the analyst's cached tapes (raw rows, not `lib.py`) | 268 markets / 51 release seconds (100%) | identical per market, max difference $0.00 |
| Same code on another study's download (`data/econ_tapes/`, fetched earlier by a different script) | 187 markets / 33 release seconds (70%) | identical: +5 s $4,247.5, +30 s $292.0 on both |
| My own fresh download from the data API, with transaction hashes | 75 markets / 34 release seconds (28%), including all 17 markets with +30 s fills | row-for-row identical inside the window; +30 s $640.0, +5 s $2,823.4 on both |
| Winners straight from the `tokens` endpoint | 268 of 268 | 0 mismatches |
| Tape completeness: sum of shares on the tape vs gamma `volumeNum` | 256 complete tapes | ratio 1.000 on all 256 |

Reproduced figures: 268 markets, 51 release seconds, reporting part 140 / 30. E1 median 0.888, 140 uncertain.
E2 median 5 s, 76 / 120 / 128 within 5 s / 30 s / 2 min. E3 $107,046 changed hands, $30,347 gap, 98.0% within
30 s, 110 wallets, top three 46.7%. E4 +30 s $640 on $3,692 (whole) and $570 on $3,327 (reporting), t = 1.84;
+5 s $6,147 and $2,038, t = 2.56; 54% of the +5 s profit in fills stamped +5/+6 s.

Two fills recomputed by hand: Korea GDP 3.0-3.4 (13.79 at 0.87 + 529.37 at 0.9219 = $500.00 cost, 543.16
shares, fee $0.40, net $42.76) and Argentina CPI 1.9-2.1 (45.01 at 0.9477 + 300 at 0.35, fee $0.70, net
$196.65). Both match. The $500 cap binds exactly (maximum cost in one market $500.00; 5 markets at the cap at
+30 s, 29 at +5 s).

## Problems, in the order of the audit

### 1. Look-ahead

- **L1 (high). Argentina CPI October: T is not the publication second, so its "+30 s" fills are the first
  reaction.** Nothing prints for 39 s after 19:00:00; the first informed print is at +39 s (the earlier two
  months: +21 s and +15 s). The tier B gate accepts a first move up to +60 s, which is wider than the 30 s
  delay being tested, so a publisher that posts 15-40 s late turns "the first seconds" into "+30 s". This one
  event is $228 of the $570 reporting total (40%) and the whole of the best day.
- **L2 (high). Germany GDP Q3 was left unflagged, but the tape shows the answer was not mechanical.** The rules
  resolve on "% change on the same quarter a year earlier, price adjusted"; the Destatis release carries more
  than one year-on-year figure. The eventual winner traded at 0.42-0.45 from +3 s to +24 s, 0.56-0.60 at +58 s,
  0.78-0.93 at +94..+117 s, 0.99 only at +240 s, and at +57 s three takers were still buying the eventual loser
  at 0.39. E4 buys the resolved winner all the way through that minute. $208 of the $570 (37%).
- **L3 (medium, admitted). The outcome is used in every fill**, so every fill wins and no wrong-bucket loss can
  appear. Measured size of the wrong-side risk on the tape: takers who went long the eventual loser at 0.50 or
  more within 10 minutes of T lost $329 over 7 releases (US PPI August $182, US PCE August $96). Small, but it
  is the only loss the method can see.
- **L4 (low). The volume filter uses final volume**, which includes the post-release trading. I measured the
  290 dropped markets (0 < volumeNum < 5,000, closed after T, same releases) with the same rules: +30 s and
  +2 min **zero fills**; +5 s $476 whole period ($176 reporting); stale gap $844, all inside 30 s. The filter
  hid nothing.
- **L5 (low). Fixed 3 s lag.** 16 prints stamped T..T+2 at a winner price below 0.90 are filed as
  "before the release" (Bank of Canada October, ISM services September, Michigan September and October, Japan
  GDP). They set E1 in 7-8 markets (so those count as already priced) and keep about $370 of gap out of E3.
  With a 2 s lag the uncertain set is 145 markets instead of 140 and the medians do not move.
- Not found: no price at or after the fill second is used for a decision other than the fill itself; the time
  confirmation uses Yes prices only; no volatility estimate exists in the study.

### 2. Fills

- **F1 (high). Half of the +30 s profit is not a stale quote that survived 30 s.** $318 of the $640 comes from
  fills priced at least 5 cents BELOW an earlier post-release print of the same winner: Argentina (winner
  bought at 0.948-0.99 at +39 s, then at 0.35 at +55 s and 0.374 at +75 s), Korea GDP (0.98 at +2 s, then 0.87
  at +104 s and 0.92 at +269 s), eggs (0.97 at +16 s, 0.78 at +334 s). These are new mistaken or profit-taking
  orders, and the tape shows them taken in the same block by one to three wallets (Argentina +55 s: three
  separate transactions, 200 + 50 + 50 shares; I confirmed in each wallet's own feed that they are taker
  fills). A taker "arriving at +30 s" gets them only by being the fastest at that later instant.
- **F2 (medium). The +5 s row is not a stable number.** One second changes it by half: reporting part $2,038
  as defined, $1,042 if the start is +6 s or the lag is 4 s, $3,277 if the lag is 2 s. The order of prints
  inside one second is arbitrary on the tape (the code takes them in reversed API order): taking the cheapest
  first gives $4,664, the dearest first $1,488 (whole period $9,437 / $4,970). Quote it as "$1,000-4,700 in the
  reporting part", not as $2,038 with t = 2.56. At +30 s neither the lag nor the order matters (difference
  under $3).
- **F3 (medium). No time cap.** US CPI October "fills" run to +889,612 s (ten days) in the two events whose
  resolution was delayed: $74 of the $570 for $1,632 of capital held ten days under dispute risk. Fills within
  2 h of T only: $540 reporting.
- Checked and fine: each print is used once; the same liquidity is not used twice inside a variant; rows that
  look identical are separate fills (433 such rows in my sample, all with different transaction hashes; one
  row per transaction); the converted prices (taker BUY of winner at p, taker SELL of loser at 1 - p) are
  right; taking the first $500 of a large taker order at its VWAP is on the conservative side.
- Cannot be checked from prints (admitted by the analyst): whether any offer was resting at T + 30 s, and
  whether a second taker would have been filled at all.

### 3. Fees and accounting

- **A1 (low on the numbers, but a wrong statement). The fee was not 0.01 in the study period.** NOTES.md
  already records the economics rate measured from real charges: 0.036-0.048 before 2026-11-21, 0.0100 after
  (and nothing on some Fed markets in October). Only 2 of the 51 release seconds fall after the change. The
  results say the history is "unverified". With 0.04 before 2026-11-21: +30 s fees $16 instead of $4 (net $628
  / $559 reporting), +5 s fees $144 instead of $37 (net $6,039 / $2,004). At 0.01 the figures describe today's
  fee, which is the relevant one going forward.
- **A2 (low, labelling). `volumeNum` is shares, not dollars.** Shares on the tape equal `volumeNum` exactly on
  all 256 complete tapes; dollar turnover is about half (median 0.50, as low as 0.05 in cheap buckets). So
  "$318M volume", "under $5,000", "above $100K" are share counts. The filter is as the protocol wrote it; only
  the dollar signs are wrong.
- Settlement direction: 268 of 268 winners agree with the live `tokens` endpoint, all 1/0, no ties. The fee
  formula and the net (shares - cost - fee) are right.

### 4. Statistics

- **S1 (high). t = 1.84 is not a test.** 25 of the 30 reporting releases are exactly zero and the other five
  are positive by construction. Bootstrap by release for the reporting total: $70 to $1,228.
- **S2 (high). A handful of markets carry everything at +30 s.** Reporting part: best day (2026-11-12,
  Argentina) $228; without it $342, $7.95/day, t = 1.55. The best ten markets carry $564 of $570; without them
  $6 ($0.14/day). Whole period without the best ten markets: $33. Profit on 5 of 21 release days.
- **S3 (medium). +5 s.** Without the best day $1,338 (t = 2.63); without the best ten markets $371 (t = 2.11);
  without both $329 (t = 1.91). Less concentrated than +30 s, but see F2.
- **S4 (medium, process). The reporting part was not unseen by the lab.** `data/econ_tapes/` was downloaded at
  15:42-15:46 and NOTES.md already stated "98.8% of the $20.8K taken within 60 s" for the same 53 events before
  this protocol was written (15:51; this study's first tape 15:51:51, so the protocol did precede its own
  tapes). The 30 s primary was chosen knowing the answer. Nothing was tuned, and the bias is toward confirming a
  known null, but the split is cosmetic.
- **S5 (low). "Mostly by three wallets"**: the top three take 46.7% over the study (top ten 76.7%). Per release
  the top three take about everything (median 99.8%, 3.5 wallets), but they are not the same three each time.
  The pool is also lumpy: three releases hold 59% of the $30.3K gap, ten hold 83%, 13 of 51 have none; "$350 a
  day" is a mean, the median release with any stale trade has $228.
- Variants: four declared, four run; I found no fifth in the code. Clustering by release second is done as
  stated; the market-clustered t is printed for reference only.

### 5. Data

- Tapes: 295 files, none capped, all 39 truncated ones cross T - 2 h, timestamps monotonic, no page
  duplicates, complete against gamma volume. Time zones and daylight-saving switches in `release_calendar.py`
  are right for every row I checked (US, UK/EU, Israel, Australia, New Zealand, Korea, Japan).
- All 17 US official release times are supported by the tape (first move of 0.10 at +1 to +12 s, or a burst
  starting at +1 to +6 s).
- **D1 (low). The step from `events_raw.json.gz` (10,178 events) to `events_core.json.gz` (281) has no script
  in the folder.** I checked the result: every core event is either matched or excluded by a written rule, and
  the only release-like slugs left behind in raw are three earnings markets.
- **D2 (low). One description is inaccurate.** For US CPI August the "early move" is not "one 5-10 share
  print": five prints worth about $315 hit in the 20 s before T, all buying eventual losers. T is still right
  (163 prints in the first minute, starting at +1 s).
- The seven dropped tier B releases have zero E4 at their nominal times at +5 s and +30 s, as the analyst said.
- Not checked by me: the BLS, BEA and Fed calendar pages (my fetch was refused in this session), and whether
  markets exist outside the tags the discovery used.

## Corrected numbers

Reporting part, +30 s start, $500 per market, 43 days:

| definition | net | per day |
|---|---|---|
| as published | $570 | $13.25 |
| fee 0.04 before 2026-11-21 (measured) | $559 | $13.01 |
| without the flagged markets (ten-day carry) | $495 | $11.52 |
| also without Argentina CPI October (T is not the publication second) | $268 | $6.22 |
| also without Germany GDP (answer disputed for 100 s) | $60 | $1.38 |
| US official releases, unflagged | $0 | $0.00 |

Whole period, +30 s: $640 as published; $628 with the measured fee; of it $318 in offers that appeared after
the market had moved and $322 that could have been resting (Germany $208, CPI October carry $74, eggs $26). US
official releases, unflagged, whole period: $10 ($0.11/day). The 290 markets below the volume filter add $0.

+5 s, reporting part: $2,038 as published; honest range $1,000-4,700 (one second of timing, order inside a
second); US official unflagged whole period $3,838 at +5 s, $2,477 at +7 s, $21 at +20 s. All of it still an
upper bound that assumes every print is won from the wallets that took it.

E3: $30,347 gap stands; add about $370 for prints stamped T..T+2 and $844 from the sub-threshold markets.
The 98.0% within 30 s is unchanged for any lag from 0 to 3 s.

## What this means for the lab

- Acting 30 s or more after a scheduled release: nothing in the US releases, and the non-US remainder is two
  events. Do not fund it.
- The only place money exists is the first 5-15 s, about $350 a day on average for all takers together and
  concentrated in a few surprise releases, against wallets that are already there. This study cannot say what
  share a newcomer would win; the analyst's "$10-20 a day" is a guess, as stated.
- If the non-US thin markets are studied again, time each release from the publisher's own page, and use a
  gate tighter than the delay being tested.
