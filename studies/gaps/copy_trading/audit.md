# Audit: copy trading with a delay (independent, fresh context, 2026-11-27)

## Verdict: WEAKENED

The numbers reproduce exactly and I found no wrong sign, join, time zone or double-counted fee. What is doubtful is
the headline "every copy variant LOST money". That is a product of the fill rule, not a measured property of copying.
The honest statement is "no demonstrable edge: the best unconditional estimate is about 0 to +6% of turnover with a
CI of about +-12 points". The practical conclusion (nothing deserves a 50-100 USD live test on this evidence) stands,
because no version of the numbers is positive with t >= 1.

## Recomputed (audit/recompute.py, own code from raw cache; does not import analyze.py or pmlab.updown)

Late window, hold to resolution, 10 USD, taker fee from gamma feeSchedule, cluster by market:

| run | author | mine |
|---|---|---|
| d10 | 222 fills, 204 mkts, spent 1,607, net -162, -10.1%, t -1.17 | identical (se 8.6%) |
| d60 | 152 fills, -11.1%, t -1.15 | identical |
| d300 | 107 fills, -2.2%, t -0.17 | identical |
| reference (wallet price) | +13.4%, t 1.62, 630 mkts | +13.4%, t 1.62 (taker fee only on TAKER entries) |

Fee rate source on the 704 late entries: 670 gamma, 34 "fees off", 0 fallbacks. Payoff sign check: on 512 resolved
late entries the last tape price of the entry token disagrees with `final` by > 0.5 in 7 cases, all in-play sports
whose tape ends before the game ends (tape short, final is right). No tape fails to reach tb-60. Weekend split
(Sat+Sun 21-22 Nov vs weekdays) reproduces the author's +7.1% / -20.4% at d10.

## Finding 1 (main, serious for the wording, no effect on the decision): the print rule selects against the wallets

A copy is "filled" only if some other trade printed the token within a 30 s window after the delay. That is evidence
of activity, not of a book: a marketable order would fill against resting asks with no print. Only 32% / 22% / 15% of
entries are evaluated, and they are the entries that happened in active, already-moving markets. The wallets' own
result on the same entries (reference, same sample, same fee):

| subset | wallet's own price, return | markets |
|---|---|---|
| all 704 entries | +13.4% (t 1.6) | 630 |
| entries a d10 copy fills | **-5.1%** (t -0.6) | 204 |
| entries a d10 copy does not fill | **+22.0%** (t 1.9) | 454 |
| d60 filled / unfilled | -1.6% / +17.6% | 139 / 512 |
| d300 filled / unfilled | +8.7% / +14.3% | 92 / 551 |

So of the d10 copy's -10.1%, about 5 points are already in the wallets' own price on that subset, and only about
5 points are attributable to delay, slippage (median +1.0 c/share) and fee. The 68% of entries that never "fill" carry
the wallets' best results and are simply not tested.

An unconditional proxy (not a pre-registered variant, a diagnostic): every late entry, price = wallet price + slippage,
taker fee always, 10 USD, hold, market clusters:

| price assumption | all 704 entries | TAKER entries only (416) | TAKER, resolved only (306) |
|---|---|---|---|
| wallet price | +12.5% (t 1.5) | +6.6% (t 1.25) | +2.7% (t 0.4) |
| wallet + 1 c (measured median) | +5.9% (t 0.9, se 6.4) | +3.1% (t 0.6) | +0.4% (t 0.06) |
| wallet + 2 c | +1.4% (t 0.3) | +0.1% | -1.8% |

This is an optimistic bound (it assumes a fillable ask exists for the unprinted entries, and the pool is chosen with
late-window information), yet even it is not significant and falls to zero on resolved taker entries at +1 c. So the
claim "copying loses 10%" is not supported; "copying is indistinguishable from zero and extremely sensitive to
1-2 cents of slippage" is.

Re-run needed to settle it: the same entries with the copier's price from a real book. The repo has no historical
book for these markets, so the cheapest honest test is forward: record the best ask at tb+10 s for the next days
(public CLOB `book` endpoint, read-only) for the same wallets, no orders. I did not run it (no history, time budget).

## Finding 2 (minor): own-fill and liquidity reuse
24 of 222 d10 fills (11%) are in a block that contains the wallet's own rows (its follow-up buys). Those return
-27.0% (t -2.0); the other 198 return -7.2% (t -0.7). The author already lists this as a limitation; it does not
flatter the copy, so it does not rescue the result.

## Finding 3 (descriptive, relevant to the owner's weekend question)
All of the wallets' own late profit sits on the one weekend in the window: reference +35.6% on 21-22 Nov (297 entries,
t 2.0) vs -2.7% on Mon-Wed (407 entries, t -0.4). Copies at d10: +7.1% weekend (88 fills, t 0.5) vs -20.4% weekdays
(134 fills, t -1.8); on the same filled entries the wallets' own price gives +8.9% / -14.3%. One weekend, post-hoc,
36 sports-heavy wallets: no claim, but "weekend is dead" is not what the data say (entries per day are as high on
Sat/Sun as on weekdays, as the author reports), and a second weekend would be a cheap replication.

## Checked and clean
Time order (copier acts at tb+d, fills use block-3 s, nothing before tb+d is used for the price); windows (UTC,
1794009600 = Sat 7 Nov 00:00, 1795219200 = Sat 21 Nov, 1795651200 = Thu 26 Nov; late window entirely after the
20 Nov 23:59 fee change); fee formula and rate per market; fee not double counted (copy pays once on the buy, reference
only for taker entries); outcome mapping and `final` direction; clustering by market with the linearised ratio SE;
tape completeness (0 of 1,228 entries unreachable); 7 runs counted and reported; unresolved marks (resolved-only d10
-9.4%, d60 -12.1%, d300 -1.2%: same as the headline); survivorship in the pool is disclosed and goes in favour of
copying. Not checked: the 4,000-row cap bias (5 bots), the early window and the selection step (only the late number
was recomputed), wallet-type labels, category cells.

## Corrected headline
"On 21-25 Nov, 36 pre-selected wallets copied at 10 s / 60 s / 5 min and filled only where another trade printed
(15-32% of 704 entries) lost 2-11% after fees (all t < 1.3, CI +-17 to +25 points). That subset is the one on which the
wallets' own price already lost 5% (d10); an unconditional estimate with 1 c slippage is +0.4% to +5.9% (t < 1).
No edge is demonstrated and none can be excluded within about +-12 points; nothing here justifies a live test."

Files: audit/recompute.py (main recompute), audit/diag.py, audit/diag2.py, audit/diag3.py, audit/diag4.py (diagnostics).
No orders, no accounts, no background processes left.
