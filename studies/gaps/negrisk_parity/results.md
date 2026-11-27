# Structural arbitrage (binary parity, neg-risk complete sets, ladders) for a small account — results

Study run 2026-11-27 18:21-19:10 UTC. Protocol: `protocol.md` (saved 18:25, before any outcome number). Code:
`u1_universe.py` (gamma universe), `u2_extract.py` (archive download and filter), `a1_scan.py` (stage 1,
exchange best-price fields), `a2_episodes.py` (stage 2, level replay with sizes), `a3_report.py` (tables),
`d1_replaycheck.py` (post-hoc diagnostic). Outputs: `out/report.txt`, `out/episodes_R5.csv`. Family `negrisk-arb`.

## Verdict: NOTHING TO TEST HERE

- **Binary parity (A1) does not exist.** YES ask + NO ask was never below 1 and the bids never summed above 1:
  0 of 365,039 same-millisecond two-token states in the archive (minimum ask sum 1.001) and 0 of 4,121 REST
  snapshots in `data/rec_rest` (minimum 1.001, maximum bid sum 1.000). The two tokens are one book; the exchange
  crosses them itself.
- **Neg-risk NO basket (B2, "bids sum above 1") is a replay artefact.** 887 / 1,960 positive states (early / late)
  with at least 5 sets, but they last a median 0.10-0.12 s, 76-88% disagree with the exchange's own best-price
  field, and only 1 / 1 episode per period survives 5 s with a clean book (1 event each). Late part: $0.00 at
  the 20 USD size. Fails rules (1)-(3).
- **Neg-risk YES basket (B1, "asks sum below 1") is real but worth cents, and mostly not arbitrage.** Late part:
  55 clean episodes still open 5 s after they appeared (73 a day) in 17 events, mean +$0.089 per trade at the
  20 USD size, 95% CI [+0.059, +0.130] by event, median +0.50 c per set. It meets rules (1)-(3) and fails (4):
  a trade printed on a leg during only 38% of these episodes (rule: at least half). Two further attacks
  remove what is left: the median episode is in an event that resolves in 36 days (the dollars are locked; at
  +0.5% per 36 days that is about 5% a year, not an arbitrage), and for some events the $1 is not certain
  (OpenAI IPO valuation lists only valuation buckets and no "no IPO" outcome; the protocol did not check that
  outcome lists are exhaustive). The same-day part (weather buckets and
  post-count buckets, which are exhaustive) is 11 episodes in 8 events in 18 late hours: about $2.3 a day for
  all of it at 20 USD per trade, before anyone else takes it.
- **Strike ladders (C1) are one-off and tiny, date ladders (C2) are never violated.** C1 late: 13 clean
  takeable episodes in 3 events, +$0.005 per trade (+0.09 c per set: a 0.999 bid over a 0.998 ask in the deep
  wing, resolving in 2-3 days). The early part's +$15/day is 76% one event in its expiry hour
  (`ethereum-above-on-november-23-2026-10am-et`, 3 episodes). C2: one 0.03 s state in 36 hours.
- **Weekends.** 21-22 Nov were Saturday and Sunday. They look like weekdays: B1 16 and 62 clean takeable
  episodes ($2.05 and $1.77 at 20 USD over 6 sampled hours each) against 13-69 ($1.18-6.52) on 23-26 Nov. The
  structural "free money" is no larger on weekends; it is near zero every day.
- **Reaction time.** Of all positive B1 states, half (early) and a quarter (late) last 1 s, 22% / 14% last 5 s.
  The ones that last are the boring ones (long-dated baskets 0.5 c under $1); the large gaps (several cents)
  close in under a second and most of them disagree with the exchange's own quote, i.e. they are message
  ordering, not tradable prices.

## Question

Can a small account (5-20 USD per trade, about 200 EUR, a program on a Mac in Serbia with a reaction time of a few
seconds, no rebates) take price-identity violations on Polymarket after taker fees: (a) binary markets where
best ask YES + best ask NO < 1 or bids > 1; (b) neg-risk events where the best YES asks of all outcomes sum below
1 (buy every outcome) or the YES bids sum above 1 (buy every NO, convert); (c) "above K" strike ladders and
"by date D" ladders that violate monotonicity? How often, how big, how long, and does a gap last 5 s?

## Data

- Order books: PendulumFlow V3.1 archive (HF `chitoyuuri/polymarket-l2-v3-1-archive`, CC BY-NC, research use only;
  WebSocket recording of the whole CLOB with receive times). 36 sample hours: 21-26 Nov 2026 at 02, 06, 10, 14,
  18, 22 UTC (all after the 20 Nov fee change). 439.8 million rows kept (universe markets only, all lean category
  files + `opening_state`), 2.8 GB under `data/gaps_negrisk/hours/`. Early = 21-23 Nov (18 h), late = 24-26 Nov
  (18 h).
- Universe (gamma, read 2026-11-27): 1,889 events = top 500 open by 24 h volume + top 500 closed 21-27 Nov by volume
  + all weather events closed 21-27 Nov (504) + all `multi-strikes` events (400). Families: B (negRisk) 827 events /
  11,293 markets (67 augmented); C1 391 ladders / 6,560 markets; C2 29 date ladders / 224 markets. Per sample hour
  on average 397 B events, 49 C1 ladders and 24.6 C2 ladders had live markets.
- `data/rec_rest` (BTC 5m Up and Down books fetched separately by REST): 4,121 snapshots with both asks.
- `prices-history` was not used (protocol: mid snapshots are not tradable).
- Fee: gamma `feeSchedule.rate` per market (B markets: 7,109 at 0.01, 3,918 at 0.05, 266 at 0). Rebates 0.

## What was run (every variant)

Six protocol entries, all run once with the thresholds fixed in advance: A1 on the archive, A1 on `rec_rest`, B1, B2,
C1, C2. For each, reaction times R = 1, 2, 5, 10 s are reported side by side (protocol: not separate variants);
the headline is R = 5 s. Trade sizes 5 and 20 USD. Episode = consecutive book states with net > 0 and at least 5
sets at the top level; takeable = still net > 0 with at least 5 sets in the book state in force 5 s after it
appeared, filled at that state's prices and sizes. Book = level replay (opening state + `book` + `price_change`,
NO rows mirrored into YES space), time = receive time.

Post-hoc diagnostics (after the protocol run, not variants, not used for the verdict except as attacks):
- `d1_replaycheck.py`: on 80 B events of 21 Nov 02 h the replay equals the exchange's best-price field on 96.3% of
  `price_change` rows (989,129 of 1,027,280); the separate `best_bid_ask` messages lead or lag the level updates
  by one message (38% agree). On the hourly BTC ladder of 22 Nov 10 h (the source of most stale-flagged C1
  episodes) the field and the replay leapfrog each other message by message: those "gaps" are ordering artefacts.
- Exchange-field confirmation: whether the stage-1 state (exchange fields, prices only) is still positive 5 s after
  the episode start. It confirms almost exactly the clean-book set and rejects nearly all flagged ones (below).
- Breakdown by days to event end and by event (`out/episodes_R5.csv`).

## Headline numbers after fees (R = 5 s, clean book; 95% CI by bootstrap over events)

| variant | part | positive episodes (events) | share lasting >= 5 s | takeable at 5 s, per day (events) | net per set, median | mean $ per trade at 20 USD [CI] | at 5 USD | $ per day, all takeable at 20 USD [CI] |
|---|---|---|---|---|---|---|---|---|
| A1 | both | 0 of 365,039 states + 0 of 4,121 snapshots | - | 0 | - | - | - | 0 |
| B1 | early | 998 (86) | 0.22 | 196 (17) | +0.51 c | +0.070 [0.032, 0.105] | +0.025 | 13.78 [3.37, 30.89] |
| B1 | late | 1,167 (79) | 0.14 | 73 (17) | +0.50 c | +0.089 [0.059, 0.130] | +0.038 | 6.55 [3.01, 10.97] |
| B2 | early | 887 (128) | 0.09 | 1.3 (1) | +0.85 c | +0.169 (one episode) | +0.042 | 0.23 |
| B2 | late | 1,960 (122) | 0.06 | 1.3 (1) | 0 | 0.000 | 0.000 | 0.00 |
| C1 | early | 527 (18) | 0.55 | 107 (11) | +0.10 c | +0.144 [0.011, 0.530] | +0.125 | 15.34 [1.20, 38.84] |
| C1 | late | 40 (9) | 0.45 | 17 (3) | +0.09 c | +0.005 [0.004, 0.005] | +0.005 | 0.09 [0.03, 0.13] |
| C2 | early | 0 | - | 0 | - | - | - | 0 |
| C2 | late | 1 (1), 0.03 s | 0 | 0 | - | - | - | 0 |

Per-day figures = count in sampled hours x 24 / 18. "Takeable per day" counts each episode once; it is not a
count of independent trades a single account could make (the same resting basket reappears).

Sensitivity (stale-flagged episodes included, not the headline): B1 late 163 takeable in 39 events, +$0.190 per
trade [0.110, 0.288]; the exchange-field check confirms 87 of them (55 are the clean ones) at +$0.085. B2 late 109
takeable, the exchange fields confirm 5. C1 early 292 takeable at +$0.38 per trade, the exchange fields confirm 86 (80
clean) at +$0.136. The flagged gaps are mostly not there in the exchange's own quote.

## Attacks on B1, the only variant that met rules (1)-(3)

1. Stale book: the headline already uses only episodes whose replayed top equals the exchange field on every
   leg (55 of 163 late). Stands.
2. Was the price real: a trade printed on any leg during the episode in 38% of the late clean episodes (13%
   early). Rule (4) asks for at least half: FAILS.
3. Who made the gap: in 36% (late) / 82% (early) of the episodes the leg that opened the gap also closed it, i.e.
   one quote that appeared under the others and was taken or pulled.
4. Concentration: late top event 28% (NVIDIA market cap end of 2026), top 3 58%; early top event 59% (Bank of
   England December decision, 60 episodes, 0 prints), top 3 81%.
5. Payout not guaranteed (outcome lists of the top events read from gamma after the run): "next leader out of power
   before 2027" and "which Millennium Prize problem will AI solve next" do carry a "None" outcome and are
   exhaustive; OpenAI IPO valuation ($1.08 of the early and $0.04 of the late clean B1 dollars) has eight valuation buckets and
   no "no IPO" outcome, so if there is no IPO the basket may pay nothing (rule text not read); "Section 232 rate on
   Canadian aluminum" has an "Other" leg and "Jensen Huang affairs" starts at 3 (lower buckets presumably resolved).
   Where the list is not exhaustive a sum of asks under $1 is the price of "none of these", not a free dollar.
6. Capital lock: median 24.7 days (early) and 36.1 days (late) from the episode to the event end; only 6% / 20% of
   the episodes resolve within a day. Same-day subset (weather and post-count buckets, exhaustive by design):
   early 9 episodes in 5 events ($0.80 a day at 20 USD), late 11 episodes in 8 events ($2.34 a day, mean $0.16 per
   trade, 6 of 11 printed). Fewer than 10 events: below rule (2) even if it had been a pre-registered variant.

## Opportunities per day, net per trade, capacity, reaction time

- Opportunities a day (late, takeable at 5 s, clean): B1 73, B2 1, C1 17, C2 0, A1 0.
- Net per trade: B1 +$0.04 (5 USD) / +$0.09 (20 USD); C1 +$0.005; B2 and C2 nothing.
- Capacity for about 200 EUR: B1's $6.55 a day needs one $11.6 basket (median 11.7 sets at 0.995) per episode, about
  $850 a day of new capital locked for a median 36 days. 200 EUR can be placed once, earning about 0.5%, i.e. about
  $1 a month. The same-day weather/post-count part turns capital daily but is at most about $2 a day for all
  participants together in the sampled hours. Realistic capacity: $0-2 a day.
- Reaction time: the gaps worth more than 1 c per set close in under 1 s (median positive-state life 0.14 s late);
  what survives 5-10 s is 0.1-0.5 c per set. A few-seconds program gets only the leftovers.

## Live micro-test

Nothing here deserves one. No variant passed the pre-registered rule in the late part; the only candidate (B1)
fails the print check and its money is either locked for weeks or not guaranteed, and the same-day remainder is
about $2 a day across 8 events.

## Limitations

- Sample: 36 hours of 144 (6 per day), so per-day figures are x4 extrapolations; episodes within an hour are not
  independent. Clustering is by event; with 17 events the CIs are rough.
- Universe is volume-ranked and read on 27 Nov: thin events outside the top 500 open / top 500 closed (except
  weather and multi-strikes, taken whole) are missing. Events that closed before 21 Nov 00:00 or after 27 Nov 12:00
  but traded in the window are only included if open-top-500.
- B1 "complete set" was defined as non-augmented negRisk; the protocol did not check that outcomes are exhaustive
  (see attack 5). This makes B1 look better, not worse.
- Top-of-book size only; depth beyond the best level not used. Sequential legs (11 legs for weather) carry leg risk
  that is not modelled; a partial fill leaves a directional position.
- Minimum order size: 5 shares per leg assumed; if the minimum is 1 USDC per order (the docs disagree), legs priced
  at 0.001-0.05 need 20-1,000 shares and most B1 baskets at 5-20 USD are impossible as sized here.
- Gas and conversion costs ignored (they only reduce B2, which is already zero).
- Receive time of the archive collector (London-area latency unknown) is not the receive time on a Mac in Serbia;
  a slower listener sees each episode later, which only shortens it.
- `protocol.md` was edited once after saving: its header time was mistyped as 18:45 and corrected to the file time
  18:25. Nothing else in it changed.
- The process was interrupted twice by out-of-memory kills (one download worker, several scan runs); every hour
  was re-run to completion, all 36 hours are in the result.

## Ideas, not tested

- Pre-register B1 on same-day exhaustive bucket events only (daily weather highs/lows, post-count windows on their
  last day, 3-way soccer lines at kick-off): measured here post hoc at about $2 a day across 8 events in 18 hours;
  would need a few weeks of tape to reach 10+ events per period, and the print check would need the trade tape.
- Maker version of B1: rest a bid on the most expensive leg so that the basket closes under $1 when it fills
  (the "conversion" accounts in the politics study do a version of this and mostly lose).
- Logical relations not covered here: hit-price ladders, "between" ranges vs "above" ladders of the same expiry,
  game lines vs moneylines in one sports event.
- Nested-date ladders on geopolitics markets with fee 0: C2 found no violation in 29 ladders; widening to all open
  "by date" events may still find thin stale ones.
