# Protocol — predicting tennis walkovers hours ahead (buy the underdog before any news)

Written 2026-11-27 before any outcome-based statistic of this study was computed. Looked at so far: AGENTS.md,
NOTES.md, `studies/gaps/tennis_walkover/` (results.md, protocol.md, common.py, s2_universe.py), the field layout of
`data/gaps_tennis_wo/universe.json`, `data/gaps_tennis_wo/events.jsonl.gz` (keys, counts of market types) and one tape
row. Reachability: raw.githubusercontent JeffSackmann `atp_matches_2026.csv` and `_2025.csv` return 404,
tennis-data.co.uk returns 403 through the proxy. After this file is saved the rules below do not change; later ideas
go to "Ideas, not tested" in results.md.

## 1. Question

A tennis match market settles 50/50 if a player withdraws before the start (walkover). Buying the underdog at p
earns P(walkover) x (0.5 - p) on top of its normal value. (a) Do underdog prices a few hours before the start
already contain the average walkover premium? (b) Can facts that are public at the moment of the trade flag matches
with a higher walkover rate, so that buying the underdog in flagged matches pays after the 0.05 sports taker fee?

## 2. Data (no new downloads planned)

- Universe from the finished walkover study (`data/gaps_tennis_wo/universe.json`): moneyline markets with
  `closedTime` 2026-09-01 .. 2026-11-25 (86 days). Class A = moneyline resolved 0.5/0.5 (830, all of them, weight 1).
  Control = moneylines resolved 1/0 with a non-null volume: 21,849, of which the deterministic sha1 sample k = 8
  (2,734) has cached tapes; each control counts with weight 8. Final prices are the Data-API-confirmed ones.
  Moneylines that resolved anything else are not in either list and are left out (stated as a limitation).
- Tapes: `data/tape/<conditionId>.jsonl.gz` (whole-market tape; match time = block time - 3 s). Class A moneylines
  with no tape file count as having no print (ineligible). The number of class A moneylines with volume > 0 but no
  tape is reported.
- Public facts for features: all 32,760 tennis events in `data/gaps_tennis_wo/events.jsonl.gz` (gamma: titles,
  `seriesSlug`, `createdAt`, moneyline outcomes = player names, `gameStartTime`, `closedTime`, final prices of the
  moneyline and the `tennis_completed_match` market). External match-result files (Sackmann, tennis-data.co.uk) are
  not reachable from here (see header); no other source is tried. Round and medical timeouts are therefore NOT
  available; this is a limitation, not a variant.

## 3. The trade (one per match at most)

- T = moneyline `gameStartTime` (fallback event `startTime`). Decision window W = [T - 6 h, T - 1 h] in match time.
- The trade = the FIRST buyable print in W of either outcome with price p in [0.05, 0.45]: a taker BUY of X at p,
  or a taker SELL of the other outcome at 1 - p (X then buyable at p). X is the underdog (p < 0.5).
- Fill (taker, conservative): at price p, shares q = min(printed shares, S / (p + fee)) for target sizes
  S = 5, 10, 20 USD. Fee per share 0.05 x p x (1 - p) (pmlab.fees sports rate), rebates 0. Only that one print is used.
- Payoff per share = the bought outcome's final price (0.5 for class A, 1 or 0 for controls). Edge per share
  e = payoff - p - fee. Hold to resolution.
- Matches with no such print are not traded (listed as ineligible counts).

## 4. Features (all binary, flag if EITHER player qualifies; computed only from events whose information existed
before the trade's match time t; "player" = exact moneyline outcome name after lower-casing and stripping accents)

- F1 `itf`: series is itf.
- F2 `doubles`: series ends with "-doubles".
- F3 `short_rest`: the player's previous moneyline event (another event with that name as an outcome, start < T)
  has `closedTime` < t and `closedTime` >= T - 16 h.
- F4 `long_prev`: that previous event (closed < t, start >= T - 72 h) lasted >= 150 min (`closedTime` - start).
- F5 `recent_ret`: the player was in an event with start in [T - 14 d, T), closed < t, whose moneyline resolved 1/0
  and whose `tennis_completed_match` market resolved "No" = 1 (a retirement).
- F6 `double_duty`: another event, created (`createdAt`) before t, with start within +-12 h of T and different from
  this one, contains the same full name as an outcome, or (singles player vs a doubles event) the player's surname
  (last token) as one of the "/"-separated doubles names; and the mirror case for doubles players vs singles events.
- F7 `wo_history`: the player was in another event whose moneyline resolved 0.5/0.5 and closed < t (history from
  2026-08-20 on).
- Late-season fatigue cannot be tuned on an early period that ends in October; the month is reported as a
  descriptive cut only, never as a rule.

## 5. Variants (counted)

- V0 blind: buy the underdog in every eligible match (sizes 5/10/20). Diagnostic cuts (not variants): price bands
  0.05-0.15, 0.15-0.30, 0.30-0.45; series; month.
- Screening on the EARLY period only: F1..F7 one by one (7 variants): weighted walkover rate and edge per share among
  flagged trades.
- S1: the single feature with the highest early edge per share among features with >= 100 flagged early trades
  (unweighted count). S2: the OR of all features whose early weighted walkover rate is >= 1.5 x the early base rate
  of eligible trades and that have >= 50 flagged early trades. S1 and S2 are then run once on the LATE period.
  If no feature passes a filter, that rule does not exist and is reported as such.
- Maker scenario (separate, optimistic, fee 0): at the trade's moment a resting bid for X at p - 0.01; filled only if
  a later sellable print of X (a taker SELL of X, or a taker BUY of the other outcome) is priced strictly below
  p - 0.01 before T, for at most that print's size (first such print only). Run for V0, S1, S2. A second, more
  optimistic line counts a print AT p - 0.01 as a fill ("filled at the price with a queue share").
- Total planned: V0, 7 screens, S1, S2 = 10 taker variants, plus 3 x 2 maker scenarios.

## 6. Premium measurement (part a)

On all eligible trades (weights 1/8): gross mean (payoff - p), the weighted walkover rate q, the premium implied if
prices ignored walkovers: mean q x (0.5 - p), and the played-match calibration mean (win - p) over controls only.
If the gross mean is about 0 the premium is priced in; if it is about q x (0.5 - p) it is not.

## 7. Time split, clustering, statistics

- Early = moneyline `closedTime` < 2026-10-26 13:35 UTC (the cut of the finished study: first 67% of class A),
  late = the rest. Everything is reported per part.
- Unit = the match (one trade per match). Weighted means with SE = sqrt(sum w_i^2 (x_i - m)^2) / sum w_i, 95% CI =
  m +- 1.96 SE. Also a sensitivity with clustering by calendar day (match start date).
- Counts per week = weighted trades / (days / 7). Dollar figures per trade at the filled size; capacity per day =
  trades/day x filled dollars x edge.

## 8. Decision rule

A live micro-test is proposed only if S1 or S2 on the LATE period has edge per share > 0 with the 95% CI lower
bound > 0 (match clustering), >= 100 unweighted late trades, >= 15 walkovers among them, and a positive early edge.
Otherwise the result is "nothing to test here". Attacks before reporting a positive: look-ahead in features,
the ineligible set, fills (one print, shown size), concentration in few days/tournaments.
