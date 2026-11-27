"""Assemble results.md from the narrative below and the table fragments in out/frag_*.md."""
from common import HERE, OUT

F = {p.stem[5:]: p.read_text().rstrip() for p in OUT.glob("frag_*.md")}
TEXT = r"""# Results: do thin, low-fee crypto up/down series lag exchange prices enough to trade?

Study run 2026-11-27 under `protocol.md` (written before any tape or outcome was loaded). Code: `fetch.py` (download),
`build.py` (flat tables), `sanity.py` (slice checks), `analyze.py` (M1-M5, proxy check), `extra.py` (re-aggregations),
`report_tables.py`. Raw tables: `out/*.csv`, `out/tables.md`.

## Answer

**No tradable edge.** The thin series do not lag Binance by more than BTC 5m does. In every one of the six series
the tape follows the Binance-based fair value with a peak lag of 2 seconds over the six days, which is no more than the
on-chain block delay, and trade prices fit the model best at a lag of 1 second in the thin series against 2 seconds in
the BTC 5m reference. What looks like slowness in SOL and XRP is sparse trading (a fill in 4-6% of seconds), not
stale quotes that can be hit.

None of the 90 taker variants (60 M4, 30 M5) is positive after fees with t above 2 across 100 markets in the
reporting period. The M4 variants picked on 21-24 Nov returned, on 25-26 Nov at the protocol's size (up to 50 shares
per print, 300 per side per market): eth 5m -$987 per day (t -1.3), eth 15m +$266 (t +0.6), sol 15m +$666 (t +1.3),
xrp 15m -$979 (t -3.1), btc 15m -$813 (t -1.6). The two positive ones were negative in tuning; pooled over all six
days every selected M4 variant is within one standard error of zero (-0.87 to +0.60 cents per share). The late
lock-in rule (M5) hardly ever fires in the 15m series (at most 18 markets in six days) and loses in eth 5m out of sample
(-20 to -38 cents per share, 6-20 markets).

The one place where a delay matters is the zero-delay variant in the two most liquid series during tuning (btc 15m
+1.2 cents per share at D=0 against -0.0 to -0.4 at D >= 1 s; eth 5m +0.2 against -0.0 to -0.2). That is the same
sub-second race as BTC 5m, not a gap a trader without co-location can use, and it is within the timestamp jitter of
the data.

Lower fees do help takers, but not enough: all takers together lose 1.0-1.4% of turnover after fees in the four
0.01-fee series, against 1.8% in btc 15m and 2.4% in btc 5m. Before fees they lose 0.36-0.61 cents per share to
makers in the low-fee series.

## What was measured

Universe: every window starting 2026-11-21 00:00 to 2026-11-26 23:45 UTC: 1,726 eth 5m, 576 each of eth 15m, sol 15m,
xrp 15m, btc 15m, plus 300 btc 5m windows spread evenly as the reference. All 4,330 markets were found, resolved and
traded; none was dropped. Tuning = 21-24 Nov (1,152 / 384 markets), reporting = 25-26 Nov (574 / 192).
1,512,241 tape rows in total. Fee rates in the metadata were 0.01 for eth, sol, xrp and 0.05 for btc in every
market; `twap_lookback` was 60 everywhere; the official outcome agreed with `final_price >= price_to_beat` in every
market; no tape row had to be dropped; no second of Binance data was missing.

Slice checks before the full run (first day of eth 5m and btc 15m, then repeated on everything): equivalent buys
priced 0.45-0.55 (mean price 0.50-0.51) won 48-51% of the time (table below), tape prices are calibrated by decile,
hand-computed fees equal `fees.taker_fee`, 92-96% of taker dollars trade inside the window.

{m2s}

### M1 Size of the pond

{m1}

btc 5m is a 300-window sample; its per-day and total dollars are scaled up by 1726/300. "Taker $" is price times
size of every tape row. eth 5m is a real market ($0.58M of taker flow per day, 3,255 taker wallets in six days).
sol 15m and xrp 15m are ponds of $41-59K per day in which five wallets do 44-46% of the taker volume; a median
market trades $325-517. A fifth of all fills are below the 5-share minimum order size (partial fills).

### M2 Who pays whom (all taker fills, clustered by market)

{m2_period}

Takers lose in every series; makers collect the "gross" column with the opposite sign. The loss after fees is
significant in eth 5m, eth 15m, btc 15m and btc 5m; in sol and xrp the sign is the same but two to six days are not
enough to pin it (sol was -1.3 cents in tuning and +1.2 in reporting). The btc 5m sample reproduces the lab's
earlier whole-tape number (-2.4% of turnover after fees here, -2.67% on 278 markets before).

Net cents per share (t) by time of the window, by match time:

{m2_time}

Net cents per share (t) by price of the equivalent buy (a SELL of X at p is a buy of the other side at 1 - p):

{m2_price}

By taker side:

{m2_side}

No time or price bucket is profitable for takers with t above 2 in any series. The best-looking cells (pre-window
fills in eth, +1.1 to +1.3 cents; favourites at 0.70-1.00 in eth 5m and xrp) are all inside one and a half standard
errors.

### M3 Reaction lag

Second-by-second changes of the last trade-implied Up price (block time) against changes of the model fair value,
lags -5..+30 s, pooled Pearson correlation; peak interval from 300 bootstrap resamples of markets.

{m3}

Correlation by lag, all six days:

{m3_curve}

Reading: the peak is at 2 s in every series and in the reference, so the difference between each series and btc 5m
is 0 s (1 s earlier than btc 5m in tuning for eth, xrp, btc 15m; equal in reporting). The absolute 2 s is the block
delay. sol and xrp have a lower peak (0.11-0.12 against 0.25-0.33) and a long positive tail out to about 25 s, which
gives them a mean lag of 6-7 s. That tail is what sparse trading produces mechanically: the price can only update
when somebody trades, and in these two series a fill happens in 4-6% of seconds (the caveat written into the
protocol before the run).

M3b, the level fit that separates "stale" from "sparse": RMS distance between the price of each traded second (Up
price 0.05-0.95) and the fair value L seconds earlier.

{m3b}

If resting quotes were stale by x seconds, trades would fit the fair value of block delay + x seconds ago. They fit
best at 1 s in all thin series and at 2 s in btc 5m, and the fit gets steadily worse with every extra second. The
prices at which people actually trade in sol and xrp are as current as in BTC; they are just further from the model
(RMS 0.076-0.087 against 0.052-0.073 in the other four), which is spread and noise, not delay.

Side finding, by UTC day (peak lag in seconds, peak correlation in brackets):

{m3_day}

The lag fell from 2-3 s on 21-24 Nov to 1 s on 25-26 Nov in all six series at once. A change that hits BTC and XRP
alike is infrastructure (block timestamps, the settlement pipeline, or what the API reports as the timestamp), not
makers getting faster. Consequence: the toolkit's `BLOCK_LAG = 3` is about right for 21-22 Nov and probably 1-2 s
too long for 25-26 Nov, so in the reporting period every rule saw
exchange data 1-2 s older than the protocol intended. That errs on the conservative side (no look-ahead).

### Proxy check (Binance 60 s TWAP against the official Chainlink values)

d = [(Binance twap(t1) - final_price) - (Binance twap(t0) - price_to_beat)] / price_to_beat, in basis points:

{proxy}

The Binance proxy drifts against the official values by about 1 bp (sd) per window in every series and calls the
outcome wrongly in 0.9-1.9% of windows; all misses are windows that officially moved by 3.1 bp or less (medians 0.25-1.1 bp). 6-13% of
windows end within 2 bp of the strike, the zone where the proxy cannot be trusted. Binance trades about 13.5 bp
above the official price in all four assets (median basis), which cancels in the difference.

### Model diagnostic (descriptive)

{diag}

Official Up frequency by model bucket (number of observations), pooled over the four sample times:

{cal}

The last trade price predicts the outcome better than the model in 16 of 24 cells (differences of 0.000-0.012); the model has
nothing the tape lacks. With the default volatility multiplier 1.3 the model is under-confident on these days in every
series (it says 0.20 where Up happens 10-18% of the time, 0.80 where it happens 80-90%), so "cheap against the
model" mostly means "underdog": M4 bought at an average price of 0.23-0.47.

### M4 Taker rule: all 60 variants

f from Binance data up to m - D; buy when f - q - fee(q) >= thr; min(print, 50) shares; 300 per side per market;
held to settlement; fees in. D = delay in seconds, thr = threshold. Net cents per share and t are clustered by
market; $/day is the period total divided by 4 (tuning) or 2 (reporting) days.

{m4}

Prints considered and prints skipped because the delayed fair value would need data from before the window start:

{m4info}

Share-weighted net cents per share by delay (the three thresholds pooled):

{dgrad}

If there were a lag to exploit, results would decay as the delay grows. They do not in eth 15m, sol or xrp in either
period, and not in any series in the reporting period. Only btc 15m and eth 5m in tuning show an advantage for D=0
that is gone at D=1. Between tuning and reporting eth 15m and sol flip from minus to plus, xrp from
plus to minus, and eth 5m and btc 15m go from about zero to minus; that is what noise around zero looks like for a
rule that buys underdogs.

### M5 Late lock-in rule: all 30 variants

Last 45 s, f from data up to m - 1, buy the favoured side when f >= 0.97 and q <= f - margin; "_2bp" adds the
condition that the expected settlement average is at least 2 bp from the strike. Win rate is per (market, side)
position with a Wilson 95% interval.

{m5}

{m5info}

In the 15m series the favoured side almost never trades 3 cents below the model in the last 45 seconds (eth 15m:
9 markets in six days, all won, $690 of turnover in total, about $8 per day; sol, xrp, btc 15m: 6-18 markets, of
which the favoured side mostly won only 40-75%). In eth 5m it happens in about 12 markets a day, and there the tape is right and the model is
wrong: positions bought at a 3-8 cent "discount" to a model value of 0.97+ won 70-80% of the time in tuning and
36-68% in reporting. Adding the 2 bp condition lifted tuning to 86-92% and reporting only to 50-77%, at prices
of 0.71-0.82. A discount to the Binance-based model in the last seconds is information (the official feed is not
Binance), not a gift.

### Selected variants (tuned on 21-24 Nov, reported on 25-26 Nov)

Selection rule from the protocol: highest clustered t in tuning among variants with at least 30 tuning markets
("eligible"); if none, the variant with the most markets.

{selected}

Net dollars per UTC day for the same variants, and all six days pooled (a re-aggregation of the trades above, not a
new variant):

{sel_day}

{sel_pool}

No selected variant meets the lab's bar (positive in reporting, t above 2, at least 100 markets). eth 15m M5 has a
t of 4.5 pooled, but on 9 markets and 737 shares in six days; nine wins out of nine (Wilson lower bound 70%) at about $8 a day is a curiosity, not a
strategy.

## Variants run

90 rule variants, each evaluated on both periods: M4 4 delays x 3 thresholds x 5 series = 60; M5 3 margins x 2 x 5
series = 30. All are in the tables above. The analysis script was run twice: once on the first-day slice of eth 5m
and btc 15m to check the code (its M4/M5 output for that day was on screen; no rule, filter or parameter was changed
afterwards, only two crashes were fixed), and once on the full period. Measurements that are not rules: M1, M2, M3,
M3b, proxy check, model diagnostic, and the per-day re-aggregations in `extra.py` (written after the full run, to
date the block-delay drift and to show the selected variants by day).

## What would have to be true for an edge here to be real

1. Resting quotes in a thin series would have to stay unchanged for seconds after Binance moves. The trade prices
   say they do not (M3b), and a rule that pays up whenever the tape is cheap against a 0-5 s old fair value earns
   nothing (M4). An edge of under one second may exist in btc 15m and eth 5m; it belongs to whoever is fastest.
2. The Binance model would have to know more than the tape. It does not (Brier scores), and where the two disagree
   most confidently, in the last 45 s, the tape wins (M5).
3. For sol 15m and eth 15m the reporting-period plus would have to be the truth and the tuning-period minus the
   noise. Nothing in the data favours that reading; the same variants are at -0.09 and +0.03 cents per share over
   six days.

## What could not be checked

- **Quotes.** Only trades are visible. A stale quote that nobody hit leaves no trace, and in sol/xrp 94-96% of
  seconds have no trade. M3b and M4 argue against stale quotes at the moments when trades happen; they cannot rule
  out stale quotes at other moments. That needs the L2 archive.
- **Whether we would get the fill.** Every simulated fill takes liquidity that a real taker took in that same print;
  we would have been racing that taker, with a 50 ms taker delay and no co-location. Real fills would be worse.
  About a fifth of prints are below the 5-share minimum order.
- **Timing to the second.** Block time is 1-3 s after the match with jitter, and the delay drifted from 3 to 1 s
  during the sample. D=0 and D=1 cannot be told apart from timestamp error; in tuning D=0 may contain up to a second
  of look-ahead.
- **Power.** Two reporting days give a standard error of 0.5-0.8 cents per share in eth 5m, 0.6-1.4 in eth 15m and
  btc 15m, and 1.5-2.0 in sol and xrp. An edge of a cent or two per share in sol or xrp cannot be excluded by this sample; it also
  cannot be shown, and the pond is $41-59K of taker flow per day.
- **Dependence between series.** Markets are treated as independent clusters. Windows of different assets at the same
  time move together, so adding up series would overstate significance; nothing here relies on that.
- **Other series and regimes.** doge, hype and the 5m sol/xrp series were not in the protocol. All six days come
  after the fee change of 20 Nov, in one volatility regime.
- **The official feed.** Chainlink prices were not used; the Binance proxy misses 1-2% of outcomes and is unreliable
  within about 2-3 bp of the strike.
- **Makers.** The other side of M2 (0.36-0.61 cents per share before any adverse-selection accounting per maker) was
  not tested as a strategy.

## Toolkit notes (nothing under pmlab/ was edited)

- `updown.BLOCK_LAG = 3` is not a constant: measured the same way in six series, the tape-vs-Binance peak lag was 2-3 s
  on 21-24 Nov and 1 s on 25-26 Nov. Timing-sensitive studies should estimate it per day.
- `Px.price(t)` is the close of the 1 s kline that opens at t, i.e. the price at t + 1, so `fair_up(px, t, ...)` uses
  information up to t + 1. This study used `fair_up(px, x - 1)` for "data up to x". Worth a line in the docstring.
- `fair_up` with the default `sigma_mult = 1.3` is under-confident in all six series on these days (calibration
  table above).
- `Px.load` falls back to downloading a whole day from the mirror, uncached, when a daily dump is missing; the study
  fetched the 180 seconds it needed from 27 Nov itself (`common.load_px`).
- `updown.tape` writes its temporary file as `<condition>.jsonl.tmp`; two studies fetching the same market at the
  same moment would write the same file. Not observed, but the btc 5m cache is shared with another study.

## Ideas (not run)

1. Measure quote staleness directly in sol 15m and xrp 15m from the L2 archive (HF `chitoyuuri/polymarket-l2-v3-1-archive`,
   crypto about 75 MB per hour): seconds until best bid/ask moves after a Binance move of a given size, and the depth
   that sits there meanwhile. The tape cannot see this.
2. Maker study on eth 5m and eth 15m at the 0.01 fee: takers give up 0.4 cents per share before fees. Test a passive
   quote with `updown.sellable`, 1-2 s of staleness and realistic queue position (needs L2), per-maker adverse
   selection included.
3. Rerun this exact protocol on the next two weeks of data for power, with the block lag estimated per day.
4. Recalibrate the fair value per series (volatility multiplier, official price to beat rescaled by the basis)
   under a new protocol on fresh days; with the current model the taker rule is mostly an underdog-buying rule.
5. Explain the M5 failures in eth 5m: when the Binance model says 0.97+ and the tape is 3+ cents cheaper, who is
   selling and what do they see? Needs the Chainlink stream next to Binance (the official feed needs a key from
   30 Nov).
6. Pre-window fills in eth 5m/15m (takers +1.1 to +1.3 cents per share after fees, t 0.8-1.4): too weak to act on,
   cheap to re-measure on a longer sample.
"""
out = TEXT
for k, v in F.items():
    out = out.replace("{" + k + "}", v)
import re
left = re.findall(r"\{[a-z0-9_]+\}", out)
assert not left, left
(HERE / "results.md").write_text(out)
print("ok", len(out))
