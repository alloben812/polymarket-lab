# Protocol — politics wallet study (2026-11-27)

The wallet breakdowns, cash reconstructions, mark-outs and jump tables in this folder are DESCRIPTIVE (what an account
did). They were not pre-registered; every script run is listed in README.md ("what was run").
Two tests were written down here before their results were looked at.

## T1 — taker buys of near-certain outcomes in politics (one variant)
Universe: every market with a cached tape under `data/politics_wallets/tapes/` that the selected accounts trade,
family politics, resolved by now (data API `tokens`). The tapes were chosen because the studied accounts are active
in them: this is a selected sample, not the category.
Rule: every taker BUY by any wallet at 0.95 <= price < 0.999. Result per share = final price - price - fee, fee =
rate * p * (1 - p), rate 0.05 for fills before 2026-11-21 00:00 UTC and 0.01 after (the non-geopolitics rate; a
geopolitics market pays 0, so this is conservative). Unit = market; ratio of sums with errors clustered by market.
Split: markets ordered by their last print; earlier half = tune, later half = report. No parameter is tuned; the
split only shows stability. Descriptive rows (not separate variants): price 0.95-0.97 / 0.97-0.99 / 0.99-0.999 and
time to the gamma end date.
Kill criterion: later-half edge after fee <= 0 or |t| < 2 -> "no demonstrated edge".

## T2 — is Cb94C437's buy trigger a move in a sibling market? (one variant)
Universe: its taker BUY fills in politics markets whose event has at least one OTHER market with a cached tape.
Statistic: share of those buys preceded, in the 120 s before the fill, by a move of >= 2 c (last print vs the print
before the 120 s window) in any sibling market of the same event. Placebo: the same statistic at fill time minus
3,600 s. Prediction if the trigger is a sibling move: fill share at least twice the placebo share.
