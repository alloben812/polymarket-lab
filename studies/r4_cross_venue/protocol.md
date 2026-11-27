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
