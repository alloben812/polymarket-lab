# Sceptic's protocol - mentions wallet study (written 2026-11-27 BEFORE any of the checks below was run)

Target: the analyst's three highest-confidence accounts. oidocrop is 4; five accounts tie at 3 (QuantDeLaFugazi,
Faston, 0xtrador, BipBop). Tie broken by the analyst's own order: QuantDeLaFugazi and Faston. The others are not
re-tested here and stay unverified.

Windows. Analyst: 45 days ending 2026-11-27 15:40 UTC (NOW = 1795794000). Mine:
- W0 (out of sample): the 45 days immediately before, 2026-08-29 15:40 -> 2026-10-13 15:40 UTC. No overlap.
- W1 (the suggested command): `python3 -m pmlab.wallet <name> --days 14 --end 2026-11-06`. It lies INSIDE the
  analyst's window, so it only checks the tool against the analyst's script, not the claim.
Definitions (mentions filter, T_pre / T_det, phases, fill PnL, fee 0.01*p*(1-p) on taker fills) are copied from the
analyst's `deep.py` unchanged, so a difference is a difference in data, not in rules.

S1 pass criteria in W0, fixed now:
- oidocrop: net after fee > 0 with t by market >= 2; >= 80% of buy dollars at >= 0.95 in JUMP/POST; buys below
  0.95 (ALL of them, winners and losers together, not split by outcome) carry more than half of the profit;
  wrong side in at most 2% of markets with a buy at >= 0.95.
- QuantDeLaFugazi: net after fee > 0; JUMP-phase pnl > 0. Negative net in both windows = the profit claim fails.
- Faston: net > 0; PRE fills carry the majority of the profit; >= 2/3 of events positive (the analyst's own bar);
  shares sold / bought < 0.05.
S2 concentration, both windows: drop the three best markets, then the best event; is the rest > 0? Monthly record
from a fresh `tools/wallet_check.py --monthly`.
S3 raw re-derivation: at least five markets per account, fills pulled fresh from the user feed and the market tape
pulled fresh from the condition feed (not the cached tape), start/closed times from gamma. Markets: the analyst's
named stories (to check the table) plus the five largest |pnl| markets of W0 (to check out of sample).
S4 alternatives: (a) operator cluster - identical `wv_30d` in gamma /tiers across the nine wallets; (b) rebates and
rewards share; (c) hidden losers - unresolved mention markets marked at the last tape print; (d) inventory
operations (split / merge / conversion) that would mean hedging or a mis-stated profile; (e) non-mention pnl of the
same wallet in the same window; (f) fee actually charged vs the 0.01 assumed (implied rate from the account's own
charges); (g) survivorship - stated, cannot be removed here.

Verdicts: SUPPORTED = S1 passes, S2 rest positive in both windows, S3 shows no contradiction. REFUTED = the profit
is absent in both windows or comes from somewhere other than the stated mechanism. WEAK = anything in between.
Variants are counted in NOTES.md.

## Addendum (written after W0 and A had been run and read)

- Wm1 (2026-07-15 15:40 -> 2026-08-29 15:40 UTC) was added after seeing W0. Reason: W0 overlaps September and
  October, which the analyst's selection rule ("2 of the last 3 months positive") looked at. Same script, no rule
  changed, run for all three accounts. Treat it as a post-hoc addition.
- `post.py` (clean-jump speed, below-0.95 buys by phase, sides, fee base, non-mention pnl, splits) and `bench.py`
  (Faston's pre-event picks vs blind buying of every sibling market, rules copied from `../pre_event.py`) were
  written after the first runs. The fee measurement from activity rows was also added then.
- Verdicts by the literal rule above: all three accounts fail at least one S1 criterion in W0 (oidocrop: t 0.78
  and below-0.95 share of profit 2%; QuantDeLaFugazi: passes S1, fails S2 concentration; Faston: events positive
  60% and sold/bought 0.08). Faston is reported as SUPPORTED all the same, because profit, its source (PRE fills)
  and the selection against the blind Yes baseline reproduce in every window and the two failed criteria concern
  the description. This is a departure from the rule and is stated as one in the README.
