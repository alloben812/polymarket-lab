# r4 cross-venue snapshot study — protocol (written 2026-11-27 before any result was looked at)

Question 1 (Kalshi vs Polymarket): for ~20 liquid events live on both venues, is there a gap at top of book net of both fees?
- Matching is manual: a pair counts only if I read both rule texts and note every difference (source, time, tie rule).
- For each matched binary outcome take top-of-book: PM best bid/ask for YES and NO token (CLOB /book), Kalshi best
  yes bid / no bid from /markets/<ticker>/orderbook (yes ask = 1 - best no bid).
- Arb cost A = PM_yes_ask + K_no_ask + fee_PM(PM_yes_ask) + fee_K(K_no_ask); B = K_yes_ask + PM_no_ask + fees.
  fee_PM = rate*p*(1-p) with the market's feeSchedule rate (NOTES), fee_K = 0.07*p*(1-p) taker (series fee_type
  quadratic; maker 0.0175 where quadratic_with_maker_fees), rounding ignored. Arbitrage iff min(A,B) < 1.
- Also report mid_PM - mid_K (signal gap) and each venue's spread. A "signal gap" matters only if |mid diff| exceeds
  PM half-spread + PM taker fee (what a PM-only trader would pay to act on it).
- One snapshot, both books fetched within a few seconds. No variants: one rule, one pass. A snapshot cannot show
  lead-lag; it only shows the level gap.

Question 2 (Deribit vs Polymarket crypto thresholds): PM "Bitcoin/Ethereum above K on <date>" (Binance 1m close at
12:00 ET) and "what price will BTC hit" (barrier) markets.
- Terminal digitals: risk-neutral P(S_T > K) from Deribit marks: interpolate total implied variance linearly in time
  between the two Deribit expiries bracketing the PM expiry (or scale the nearest if PM expiry is before the first),
  take IV at strike K by linear interpolation in strike, digital = call-spread finite difference
  (C(K-h) - C(K+h)) / 2h with Black-76 on the Deribit forward interpolated to the PM time (captures skew). r = 0.
- Compare with PM mid and with PM bid/ask. Flag |PM mid - Deribit| > PM half-spread + fee (crypto rate 0.01).
- Barrier ("hit") markets: reflection approximation P(hit) ~ 2*P(S_T > K) for up-barriers with ATM-ish vol, reported
  as rough only; not counted as a test.
- Known basis sources that are NOT edge: Binance spot vs Deribit index, 08:00 UTC vs 17:00 UTC expiry, risk-neutral
  vs real-world, Deribit mark vs tradable bid/ask.
Variants run are counted in results.md.

Question 3 (added 2026-11-27 before running): BTC 15-minute "up/down" on both venues (Kalshi KXBTC15M: CF BRTI 60 s
average at close >= target; Polymarket btc-updown-15m: Chainlink 60 s TWAP end >= start). Poll both top-of-books
by REST every ~3 s for ~25 minutes (covers at least one full window). Report: distribution of PM Up mid - Kalshi yes
mid; share of polls where buying Up on one venue and Down on the other costs < 1 after taker fees (PM rate 0.05,
Kalshi 0.07); correlation of mid changes at lags of -3..+3 polls. REST polling cannot resolve sub-second lead-lag;
the two targets (Chainlink TWAP vs BRTI average) differ by a few dollars, so near the strike the contracts are not
the same event. One run, no variants.

Question 4 (added 2026-11-27 before running): minute-bar lead-lag, Kalshi vs Polymarket, NFL games of 2026-11-26
(Thanksgiving; settled) plus any NFL/NBA game of 11-25/11-26 that matches by slug. Kalshi 1-minute candlesticks
(mid of yes bid/ask close), Polymarket data-api prices-history 1-minute buckets for the same team's token.
Window: 30 min before the scheduled start to the last bar where both venues are between 0.03 and 0.97.
Statistics, pooled over games with errors by game: (a) corr(dPM(t), dK(t+L)) for L = -3..+3 minutes (L>0: PM
moves first); (b) gap closure: regress dPM(t+1) and dK(t+1) on gap(t) = K(t) - PM(t). One pass, no tuning.
Limits known in advance: minute bars cannot see second-scale leads; PM history is a price series of unknown
construction (mid or last), Kalshi is a quote mid.

Question 5 (added 2026-11-27 after the snapshot showed PM "BTC dips to X in 2026" YES 1.5-3.3c below Kalshi's
KXBTCMINY at all four strikes; written before pulling history): is the level gap persistent? Hourly series for the
last 30 days: Kalshi 60-minute candles (mid of yes bid/ask close) vs PM prices-history (30-minute buckets, last
value in the hour) for strikes 55K/50K/45K/40K. Report mean and median of K - PM per strike per week and the share
of hours with K - PM > 0.02. Also a third opinion: Deribit-implied one-touch ~ 2 * P(S_T < K) at T = 2027-01-01
05:00 UTC (reflection principle, no drift, skew via the smile) — rough, for sign only.

Q3 correction (2026-11-27): run 1 of the 15-minute poll read Kalshi's quote from GET /markets/<ticker>, which turned
out to be cached for several seconds (checked: /markets showed 0.20/0.21 while /orderbook showed 0.28/0.29). Run 1
is void for the arbitrage count. Run 2 (variant 2 of Q3) reads GET /markets/<ticker>/orderbook; same statistics.
