# Crypto price-level markets vs option-implied probabilities — results

Run 2026-11-27. Protocol: `protocol.md` (written before any gap or rule result). Code: `discover.py`, `fetch.py`,
`common.py`, `panel.py`, `l0.py`, `l12.py`, `l3.py`, `l4.py`, `deribit_c.py`. Raw outputs: `out_*.txt` in this
folder. Data: `data/gaps_levels/`.

## Verdict

**INCONCLUSIVE, leaning to "no tradable edge shown".** The gap exists but is small (typically 2-3 points, not 5-6),
its systematic part is a model error (flat 30-day vol, no skew), and the large gaps that drive the paper profit are
mid-prices of empty books: 77% of the rule's entries had no print at the assumed price within 10 minutes (93% in the
48 h-7 d band where all the paper profit sits). On tape-confirmed entries the tuned variant is still positive in the
reporting period (+$694 on 43 entries, t = 2.08), but that is 34 markets (the bar is 100), 15 overlapping clusters,
all of it from the NO side during a month in which BTC fell 27%, and only 13 of the 43 entries had the full $20 of
size on the tape (+$47). One-touch markets: nothing after tape confirmation.

## What was measured

- European group ("above X at noon ET", plus the hourly ladders): 560 markets with volume >= $5,000 resolving
  27 Oct-26 Nov (BTC 314 daily + 9 hourly, ETH 236 daily + 1 hourly); 62 clusters (asset x date); tune 359 markets /
  40 clusters, report 201 / 22. 1.11M five-minute points, 92,366 market-hours.
- One-touch group ("reach / dip to X"): 825 markets by scheduled end date (602 daily, 152 weekly, 71 monthly).
  Done (time allowed), reported separately.
- Fair value: N(d2), zero drift, Binance 1-minute spot, (a) Deribit DVOL hourly close scaled to the horizon,
  (b) realised 24 h vol; one-touch: reflection-principle barrier formula. (c) Deribit BTC daily options, 10 expiries
  17-26 Nov, 321 instruments, 3,109 traded hourly candles.
- Variants run: **27** = 9 primary (European, DVOL) + 9 secondary with realised vol + 9 on the one-touch group.
  Each was also recomputed on tape-confirmed entries (same rule, fill requirement only). Nothing else was run.

### Sanity (L0, first three tune dates, then full window)

- Official outcomes are reproduced from Binance 1-minute closes in 550/550 daily-ladder markets by the candle that
  OPENS 11:59 ET (closes at 12:00:00) and in 549/550 by the candle opening 12:00 (the one market that separates
  them, BTC > 76k on 6 Nov, resolved with the 11:59 candle). One-touch: 825/825 from 1-minute highs/lows.
  So the price source and the resolution minute in the model are right. Noon ET = 16:00 UTC until 31 Oct,
  17:00 UTC from 1 Nov (handled through `endDate`).
- `prices_history` is a mid-price snapshot: 5-minute changes of the Polymarket price correlate with model changes
  only at lag 0 (0.57; +-1 bucket: 0.02). The market absorbs spot inside one 5-minute bucket.
- Fees match `pmlab.fees` to 1e-16; all 560 markets carry `feeSchedule.rate = 0.01`.
- Market price 0.45-0.55 in the slice: 41% YES on 25 markets / 6 clusters (inside noise for 6 clusters).

## L1 — the gap (Polymarket minus model), European group, vol (a)

Active strikes (model probability 0.05-0.95), hourly observations:

| time to resolution | market-hours | mean gap | sd | mean abs gap | share abs gap >= 0.05 |
|---|---|---|---|---|---|
| < 2 h | 29 | -0.005 | 0.110 | 0.072 | 52% |
| 2-12 h | 701 | +0.003 | 0.054 | 0.041 | 33% |
| 12-48 h | 5,547 | +0.005 | 0.044 | 0.030 | 16% |
| >= 48 h | 34,589 | +0.005 | 0.037 | 0.023 | 7% |
| all | 40,866 | +0.005 | 0.039 | 0.024 | 8.6% |

By moneyness (all horizons pooled per cell, see `out_l12_euro.txt` for the 20 cells with medians, IQR, calibration):

| model probability | mean gap 2-12 h | 12-48 h | >= 48 h |
|---|---|---|---|
| 0-0.1 | +0.007 | +0.006 | +0.005 |
| 0.1-0.3 | +0.004 | -0.012 | -0.010 |
| 0.3-0.7 | +0.014 | +0.014 | +0.014 |
| 0.7-0.9 | -0.010 | +0.020 | +0.016 |
| 0.9-1 | -0.011 | -0.012 | -0.017 |

With realised vol (b) the gap is twice as wide (active: mean abs 0.046, 34% of market-hours at >= 0.05): the market
is closer to DVOL than to trailing realised vol.

Calibration. In this window both the model and the market were far from outcomes at long horizons because BTC fell
from 82.8K (20 Oct) to 60.5K (26 Nov) and ETH from 2,452 to 1,692: e.g. cell 0.3-0.7 / >= 48 h: outcome 0.17, model
0.50, market 0.52. Brier (active): model 0.1807, market 0.1849, difference -0.0042 (clustered t = -4.2), encompassing
beta 1.9 (se 0.35); in the 2-48 h bands the two are indistinguishable (t between -0.5 and +0.1). The long-horizon
"model beats market" is the same trend seen through 7-day ladders that overlap in time; the clusters are not
independent there and the t-values are overstated. I do not read it as evidence that the market was wrong.

## L2 — persistence (European, vol a)

- Autocorrelation of the gap (active): 0.65 at 1 h, 0.58 at 4 h, 0.47 at 12 h; after removing each market's mean:
  0.52 / 0.40 / 0.26.
- Gaps of 5 points or more: 59% of the gap is gone after 1 h (slope 0.41), then it decays slowly (0.32 at 4 h, 0.24
  at 12 h, 0.16 at 24 h). Half-life 0.8 h from the 1 h slope, 2.4 h from the 4 h slope: a fast transient part plus a
  persistent level.
- Who moves: over the next 4 h the market price moves by -0.68 x gap, the model by -0.005 x gap. The transient part
  is the Polymarket mid coming back, not spot moving. Together with L4 this says the transient part is mostly a
  wide or empty book whose mid is off, not a tradable mispricing.

## (c) Deribit listed options vs the DVOL model (BTC, 10 daily expiries 17-26 Nov)

- Near-the-money implied vol from traded candles, 2-24 h to expiry (n = 1,002): median IV 54.0% vs DVOL 50.5%;
  ratio IV/DVOL quartiles 0.96 / 1.10 / 1.27. "30-day DVOL scaled to the horizon" understated one-day vol by about
  10% in this period, with a wide spread from day to day.
- Call/put-spread digitals (n = 2,425, noisy because they come from last trades inside an hour): model minus option
  digital mean +0.002, mean absolute 0.077. By moneyness the option digital is ABOVE the lognormal model at
  0-0.1 (+0.016), 0.1-0.3 (+0.016), 0.3-0.7 (+0.026) and BELOW it at 0.7-0.9 (-0.036) and 0.9-1 (-0.035).
- That is the same sign pattern as Polymarket minus model in L1 (+0.5 / mixed / +1.4 / mixed / -1.2 to -1.7).

**Plain answer on model error vs market error.** The price source and the time of day are not the problem (550/550
outcomes reproduced). The systematic gap of 0.5-1.7 points is a model error: flat DVOL has no skew and was about
10% too low for one-day horizons; Deribit's own digitals deviate from the model in the same direction as
Polymarket, and by more. The remaining large gaps are short-lived and mostly not executable (L4). A 5-6 point gap
with a four-hour half-life is not what late 2026 looks like in these ladders.

## L3 — rule, primary (European, vol a). Entry = next bucket mid + 1 cent, $20, hold, fee 0.01 p(1-p)

All entries (paper):

| period | g | band | entries | markets | clusters | PnL $ | return on stake | t | win | mean entry | $/day |
|---|---|---|---|---|---|---|---|---|---|---|---|
| tune | 0.05 | 2-12h | 78 | 78 | 37 | -351 | -22.5% | -2.81 | 0.63 | 0.69 | -17.6 |
| tune | 0.05 | 12-48h | 171 | 108 | 38 | +767 | +22.4% | +0.96 | 0.46 | 0.43 | +38.4 |
| tune | 0.05 | 48h-7d | 729 | 313 | 40 | +4,654 | +31.9% | +2.51 | 0.53 | 0.45 | +232.7 |
| tune | 0.08 | 2-12h | 43 | 43 | 28 | -79 | -9.2% | -0.60 | 0.60 | 0.61 | -3.9 |
| tune | 0.08 | 12-48h | 83 | 55 | 23 | +74 | +4.4% | +0.21 | 0.45 | 0.36 | +3.7 |
| tune | 0.08 | 48h-7d | 450 | 295 | 40 | +806 | +9.0% | +1.38 | 0.63 | 0.59 | +40.3 |
| tune | 0.12 | 2-12h | 16 | 16 | 15 | -88 | -27.4% | -1.22 | 0.50 | 0.50 | -4.4 |
| tune | 0.12 | 12-48h | 43 | 30 | 13 | -168 | -19.5% | -0.61 | 0.26 | 0.25 | -8.4 |
| tune | 0.12 | 48h-7d | 373 | 284 | 40 | +1,114 | +14.9% | +2.01 | 0.71 | 0.65 | +55.7 |
| report | 0.05 | 2-12h | 49 | 49 | 20 | +162 | +16.6% | +1.00 | 0.80 | 0.78 | +14.8 |
| report | 0.05 | 12-48h | 97 | 65 | 21 | +310 | +16.0% | +1.36 | 0.84 | 0.81 | +28.2 |
| report | 0.05 | 48h-7d | 507 | 194 | 22 | +2,664 | +26.3% | +3.96 | 0.76 | 0.67 | +242.2 |
| report | 0.08 | 2-12h | 35 | 35 | 16 | -137 | -19.6% | -2.78 | 0.69 | 0.83 | -12.5 |
| report | 0.08 | 12-48h | 21 | 19 | 10 | -38 | -9.1% | -0.96 | 0.76 | 0.80 | -3.5 |
| report | 0.08 | 48h-7d | 346 | 193 | 22 | +1,195 | +17.3% | +3.79 | 0.75 | 0.66 | +108.7 |
| report | 0.12 | 2-12h | 18 | 18 | 12 | -14 | -3.8% | -0.33 | 0.78 | 0.82 | -1.3 |
| report | 0.12 | 12-48h | 4 | 4 | 3 | -55 | -69.2% | -2.96 | 0.25 | 0.73 | -5.0 |
| report | 0.12 | 48h-7d | 289 | 190 | 22 | +934 | +16.2% | +3.14 | 0.76 | 0.67 | +85.0 |

Tuned variant (highest tune t with >= 30 entries): g = 0.05, 48 h-7 d. On paper it passes the bar in the reporting
period (t = 3.96, 194 markets). It does not survive the fill check below. Pooled over variants the NO side made
+$13.2K (tune) and +$6.9K (report) and the YES side lost -$6.5K and -$1.9K: the paper profit is a short position on
a falling market, bought at prices nobody was offering.

## L4 — fill realism

Protocol sample, 150 entries drawn at random from the 2,078 distinct primary entries: **46 confirmed = 30.7%**
(Wilson 23.8-38.5%); 20.0% with tape size >= the entry's shares; in 62% of cases there was no print at all in the
10 minutes. By band: 2-12 h 81% (n 16), 12-48 h 71% (n 34), 48 h-7 d 9% (n 100). On the 46 confirmed entries of the
sample every variant has 0-12 entries; nothing can be said from the sample alone (table in
`out_l4_euro_pa_sample.txt`).

Same check on all 2,078 entries (514 market tapes): **473 confirmed = 22.8%** (21.0-24.6%); 13.8% with full size;
2-12 h 79%, 12-48 h 54%, 48 h-7 d 7.0%. By gap size: 29% / 38% / 17% / 1.4% for abs gap 0.05-0.08 / 0.08-0.12 /
0.12-0.20 / >= 0.20. Entries in the first 24 h of a market's life: 3% confirmed (median mid 0.50-0.56: empty book).

L3 on tape-confirmed entries only (all entries checked):

| period | g | band | entries | markets | clusters | PnL $ | return on stake | t | win | mean entry | $/day |
|---|---|---|---|---|---|---|---|---|---|---|---|
| tune | 0.05 | 2-12h | 54 | 54 | 28 | -208 | -19.3% | -2.50 | 0.67 | 0.77 | -10.4 |
| tune | 0.05 | 12-48h | 87 | 69 | 31 | +648 | +37.3% | +1.06 | 0.54 | 0.49 | +32.4 |
| tune | 0.05 | 48h-7d | 32 | 27 | 16 | +472 | +73.7% | +1.49 | 0.44 | 0.28 | +23.6 |
| tune | 0.08 | 2-12h | 35 | 35 | 23 | -16 | -2.2% | -0.13 | 0.66 | 0.68 | -0.8 |
| tune | 0.08 | 12-48h | 39 | 33 | 20 | -110 | -14.1% | -0.68 | 0.54 | 0.47 | -5.5 |
| tune | 0.08 | 48h-7d | 19 | 17 | 11 | -38 | -9.9% | -0.22 | 0.26 | 0.26 | -1.9 |
| tune | 0.12 | 2-12h | 9 | 9 | 8 | -59 | -32.9% | -1.40 | 0.56 | 0.65 | -3.0 |
| tune | 0.12 | 12-48h | 12 | 11 | 7 | +222 | +92.4% | +1.09 | 0.42 | 0.25 | +11.1 |
| tune | 0.12 | 48h-7d | 3 | 3 | 3 | -33 | -55.5% | -1.23 | 0.33 | 0.45 | -1.7 |
| report | 0.05 | 2-12h | 40 | 40 | 20 | +140 | +17.5% | +0.86 | 0.75 | 0.76 | +12.7 |
| report | 0.05 | 12-48h | 63 | 49 | 20 | +151 | +12.0% | +1.38 | 0.83 | 0.79 | +13.7 |
| report | 0.05 | 48h-7d | 43 | 34 | 15 | +695 | +80.8% | +2.08 | 0.81 | 0.65 | +63.1 |
| report | 0.08 | 2-12h | 30 | 30 | 16 | -81 | -13.5% | -1.58 | 0.73 | 0.84 | -7.4 |
| report | 0.08 | 12-48h | 12 | 11 | 9 | +7 | +2.8% | +0.20 | 0.83 | 0.81 | +0.6 |
| report | 0.08 | 48h-7d | 16 | 16 | 12 | +102 | +31.8% | +2.59 | 0.88 | 0.73 | +9.3 |
| report | 0.12 | 2-12h | 16 | 16 | 11 | -19 | -5.8% | -0.45 | 0.75 | 0.81 | -1.7 |
| report | 0.12 | 12-48h | 3 | 3 | 2 | -35 | -58.8% | -2.13 | 0.33 | 0.82 | -3.2 |
| report | 0.12 | 48h-7d | 7 | 7 | 6 | +31 | +22.3% | +0.91 | 0.86 | 0.77 | +2.8 |

Tuned variant on confirmed entries (g = 0.05, 48 h-7 d; it is also the top tune t among confirmed, +1.49):
reporting period 43 entries, 34 markets, 15 clusters, **+$694.5, t = 2.08, +$63 per day** at $20 per entry
(about 4 entries a day); tune period +$23.6 per day (t = 1.49). Attack on that number (`out_l4_diag.txt`):
- by side, report: NO 31 entries +$704, YES 12 entries -$10; tune: NO 20 entries +$689, YES 12 entries -$217
  (1 win in 12). All of the result is short exposure while BTC fell 27% and ETH 31%.
- two clusters, BTC 16 Nov and 17 Nov (the ladders that lived through the 73K -> 65K drop), are $497 of the $694.
- 7-day ladders of consecutive dates overlap; 15 clusters are far fewer than 15 independent bets.
- entries where the tape showed at least the full 20 dollars of size at the price: 13, +$47 in total ($4 per day).
- 34 markets against a bar of 100.
All distinct confirmed entries pooled (descriptive): tune 264 entries +$1,249 (t 1.25), report 209 entries +$967
(t 2.01) with the same NO/YES split (confirmed NO +$2,015 and +$915; YES -$1,137 and +$76).
Short horizons are negative in tune after confirmation (2-12 h, g 0.05: -19%, t = -2.5): close to resolution the
book is ahead of a DVOL model.

### Secondary, declared in advance, not used for the verdict

Realised-vol model (R-b), 4,660 distinct entries: 13.5% confirmed (6% in 48 h-7 d). Paper: tuned g = 0.08, 48 h-7 d,
report +$3,951, t = 2.86. Confirmed only: tuned g = 0.05, 48 h-7 d, report 70 entries / 55 markets, +$877,
t = 1.78; no confirmed variant reaches t = 2 with 30 or more entries in both periods. Same NO-side pattern (paper:
NO +$38.7K / +$21.5K, YES -$14.5K / -$10.1K). Tables: `out_l3_euro_pb.txt`, `out_l4_euro_pb_all.txt`.

## One-touch group (done; barrier formula, vol a)

- L1, active: mean gap -0.027 (market BELOW the barrier model), mean abs 0.045, 30% of market-hours at >= 0.05;
  2-12 h mean abs 0.088, 12-48 h 0.087, >= 48 h 0.035. In the middle cells the outcomes sat between the two
  (0.3-0.7: outcome minus model -0.00 to -0.02, outcome minus market +0.04 to +0.07, about 1 se each). Brier model
  0.1845 vs market 0.1865 (t = -0.9): no difference. With realised vol the market is clearly better (t = +4.1).
- L2: much more persistent: slope 0.75 at 1 h, 0.66 at 4 h, 0.54 at 12 h, 0.55 at 24 h; half-life 2.4 h (1 h slope),
  6.7 h (4 h slope). Market moves -0.21 x gap in 4 h, model +0.13 x gap. A standing level difference between a
  continuous-monitoring lognormal barrier model and the market, not a lag.
- L3 paper: tuned g = 0.12, 48 h-7 d (tune t = +5.5 on 6 clusters) -> report -$179, t = -5.5 on 4 clusters.
- L4 on all 1,647 entries: 36.7% confirmed (24.9% with size). Confirmed only, reporting period: all nine variants
  between -17% and +2% of stake, none with abs t above 1.4; tuned (g = 0.08, 48 h-7 d): 21 entries, -$17.
  Tune period 2-12 h confirmed: -34% (t = -3.5) and -42% (t = -4.4): taking the model's side close to expiry loses.
- No edge in the one-touch group at this level of modelling.

## Is there a tradable edge, and how large

Not shown. At the stated size the only number that survives the tape is +$63 per day in the reporting period
(+$24 per day in the tune period, t = 1.5) from about 4 fills a day, and it is a directional result on 34 markets;
on fills where the tape showed the whole 20 dollars it is $4 per day. The +$242 per day paper figure is not real:
91.5% of those entries had no print at or below the assumed price.

For it to be real the following would have to hold: (1) the NO-side result repeats in a month without a 27% fall
(the YES side must stop losing); (2) it holds on 100+ markets and on clusters that do not overlap in time;
(3) the ask actually stood at mid + 1 cent with 20 dollars of size (needs book data, not trade prints);
(4) the gap is measured against a smile-aware, short-dated vol, otherwise 1-2 points of every signal are model
error; (5) the 0.01 fee applied before 20 Nov as well.

## What I could not check

- Books. A print within 10 minutes proves the price existed at some moment, not at the entry moment, and not the
  depth beyond the print. Entries without prints are not proven impossible, only unproven; by the lab rule they do
  not count.
- Fee history before 2026-11-20 for these markets (0.01 assumed for the whole window; fees are 0.4% of stake here,
  so even 0.07 would not change the sign, but it is unverified).
- Deribit quotes. Only trade candles are public for expired options, so (c) is noisy (mean absolute 7.7 points per
  spread) and restricted to 10 BTC expiries at 08:00 UTC; no interpolation to the 17:00 UTC Polymarket time.
- Independence. One month, one strong down-trend, 62 clusters that overlap up to 7 days. All t-values at horizons
  above 24 h are too high by an unknown factor.
- ETH options and the hourly ladders (10 markets passed the volume filter; they only enter the < 2 h cells).

## Toolkit problems met (worked around in study code, `pmlab/` not edited)

- `gamma.iter_events` default `limit=100` gets HTTP 406 `gzip_required`; pass `limit=50`.
- `dataapi.prices_history` fails with HTTP 400 when the span exceeds 15 days ("'start' to 'end' must span at most
  15 days"); `fetch.py` walks in 14-day chunks.
- `updown.buyable/sellable/other` assume Up/Down outcome names; for Yes/No markets I wrote the mirror logic in `l4.py`.
- Walking `tag_slug=crypto-prices` is impractical (tens of thousands of up/down events); use `multi-strikes` and
  `hit-price`.

## Ideas (not run)

1. Maker instead of taker in the 48 h-7 d ladders: the "gap" there is an empty or wide book (93% of signals had
   no print). Quote both sides around a smile-aware fair value, collect the spread and the liquidity rewards
   (`rewardsMinSize` 50, `rewardsMaxSpread` 4.5 on these markets). Needs the L2 archive (HF chitoyuuri, crypto) to
   measure spreads, fill rates and adverse selection.
2. Replace flat DVOL by Deribit's short-dated smile (poll `get_book_summary_by_currency` live, interpolate total
   variance between the 08:00 UTC expiries around noon ET); this removes the 1-2 point skew error and the 10% vol
   level error before any signal is counted.
3. Re-measure entry prices from recorded books (ask, depth) for the 2-48 h bands, where 54-79% of signals did have
   prints; and test whether the tune-period loss at 2-12 h is the book being ahead of DVOL.
4. Model-free checks on the same ladders: monotonicity across strikes, and "above" ladder vs the neg-risk range
   buckets of the same date (sum of ranges above K against the above-K price); "reach K today" against "above K at
   noon" bounds.
5. Hedge the direction (perp short/long sized by model delta) or re-run on a flat month, to see whether anything is
   left of the NO-side result once the trend is taken out.
6. Run the L4 check on a 30-60 minute window to see how long a displayed gap waits for a trade; if it takes hours,
   a resting bid at the model price is the natural test (idea 1).
