# Sceptic's protocol for the culture wallet study (written 2026-11-27 BEFORE any re-run)

Accounts: the three highest analyst confidences: cat-dog (4), anothercoin (4), shovelingdigging (3; tied at 3 with
the market-maker pair, which is table-level only and not something the lab plans to build on, so the specialist is
taken). Read-only, public data, fee in, unit = market or event.

Windows (none overlaps the analyst's 28 Sep - 27 Nov story window):
- W1 = 2026-07-30 00:00 .. 2026-09-28 00:00 UTC (60 days) for cat-dog and shovelingdigging, ALL matching markets
  (no 150-market cap).  W0 = the analyst's window, re-computed with my code as a control.
- pmlab.wallet --days 14 --end 2026-11-06 for the two (tool table, as the task suggests).
- anothercoin has existed 31 days: its life is split at 2026-11-11 00:00 UTC, cash flows per half.

Fee: the culture rate before 2026-11-20 is NOT known to the lab (mentions was 0.04, weather 0.05). First measure it
from real charges (activity TRADE rows: usdc_size - shares*price over taker fills / sum shares*p*(1-p)), per period,
and use the measured rate per period in every table. Stated in advance: if the old rate is 0.04-0.05, the analyst's
"fee does not matter" line is wrong for anything before 20 Nov and all his PnL figures are overstated.

Tests, fixed now:
T1 reproduce. Per-market PnL to final after fee = sum over fills sign*shares*(final - price_yes) - fee (same
   convention as story.py); resolved markets only; events = gamma event slug (fallback: slug stem). Report PnL,
   turnover, winners, t by event. "Reproduces" = W1 PnL > 0 and t by event > 2. Compare with the API's change in
   economic_pnl over the same days.
T2 concentration. Drop the 3 most profitable markets, and separately the 3 most profitable events: still > 0?
   Monthly record via tools/wallet_check.py --monthly.
T3 raw re-derivation (>= 5 markets per account):
   cat-dog: (a) fade/follow table on taker BUY fills priced 0.03-0.97: the independent (other wallets) last price of
   the same token 2 h before the fill vs the last independent price before the fill; FOLLOW = moved >= +10 c its way,
   FADE = moved <= -10 c, QUIET otherwise; PnL per class, W1 and W0. Analyst's claim: FADE earns most (34%).
   (b) price paid x token (Yes/No) table: is the profit from cheap Yes picks (a model of the gross) or from buying No /
   favourites at 0.6-0.97 (selling tails)?  (c) for >= 5 weekend events: tape jump times on Sat/Sun, cat-dog's fills
   relative to them, resolved bucket, and the weekend actual from Box Office Mojo if it can be read.
   (d) universe test of the "overshoot" claim: rule J of the analyst's protocol, unchanged, on box-office bucket
   markets cat-dog did NOT trade (if they can be enumerated from gamma). One variant. If the reversal is absent there,
   the "crowd overshoots" pattern is selection.
   shovelingdigging: sub-family table in W1 with the analyst's families; price paid vs hit rate (does it buy what is
   "already likely"?); hours-to-end table; >= 5 markets listed with entry time, price, T90, outcome.
   anothercoin: >= 5 largest CONVERSION rows: cost of the No bought in that event before the conversion vs USDC
   returned; cash per half-life; current value of positions from the positions endpoint.
T4 alternatives: fee group (gamma /tiers and /v1/maker-tier/tiers same wv_30d among the study's wallets), rebates and
   rewards share, luck (T2), survivorship (how the account was picked), hedges (cannot be seen; say so).

Verdict rule: SUPPORTED = W1 positive with t > 2, survives T2, T3 agrees with the stated mechanism. WEAK = profit
reproduces but the mechanism is thin or partly contradicted, or profit does not reproduce clearly. REFUTED = W1 not
positive or the mechanism is contradicted by raw data.
Variants are counted in the write-up.

## Addendum S1 (written after the cat-dog W1 table, BEFORE running uni.py)

Seen: the culture fee was 0.05 before 20 Oct (implied 0.0500 on 219 taker fills); cat-dog W1 is +28.3K, and most of
it sits in fills made BEFORE Friday 14:00 UTC and in QUIET markets, not after jumps. Two universe checks, fixed now,
on every closed box-office event (gamma tag `box-office`) that ended 2026-08-01 .. 2026-11-23, all bucket markets:
U1. Rule J of the analyst's protocol, code copied from jumps.py unchanged (10-minute bars, >= 10 c, >= 3 trades,
    worst print of the next bar, fee 0.01 as he used), reported for (i) markets cat-dog traded, (ii) markets it did
    not trade, (iii) events it never touched. One variant. Also the no-cost "outcome minus price right after the jump".
U2. Blind benchmark for its pre-release leg: at end - 70 h (Thursday 14:00 UTC, last tape print in the 48 h before
    that), every bucket priced 0.10-0.90: return of blind Yes and of blind No per dollar, unit = event, no fee.
    Compared with cat-dog's own phase-A return. One variant. If blind No (or blind Yes) earns what cat-dog earns,
    its phase-A profit is a category bias, not its model.
