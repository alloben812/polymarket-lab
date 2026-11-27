# Results — scheduled economic releases: how fast does Polymarket absorb the number?

Run 2026-11-27. Protocol: `protocol.md` (written before any tape was read). Code: `discover.py`, `release_calendar.py`,
`build_markets.py`, `fetch_tapes.py`, `sanity.py`, `confirm_times.py`, `measure.py`, `report.py`. Data: `data/gaps_econ/`.

## Short answer

- The number is absorbed in seconds. In the 140 markets that were still uncertain before the release (winner last traded
  below 0.90), the winner first printed at >= 0.95 after a median of 5 s; 120 of 140 within 30 s, 128 within 2 minutes.
  Per release the median is 4 s (43 releases), three quarters within 10 s.
- Money that traded at stale prices after the release (winner bought below 0.95 / loser sold above 0.05): $107K changed
  hands in 87 days, worth $30.3K of "gap" to the takers, about $350 a day over ALL takers and all 51 releases.
  81% of it was taken in the first 7 seconds, 98% in the first 30 seconds. 110 wallets took any of it, the top three took
  47%, the top ten 77%; three wallets (0x8cb3ed, 0x059468, 0x2f633e) show up in 14-19 releases each.
- What a late taker could have had (winner at <= 0.97, $500 per market, fee 0.01, perfect knowledge of the outcome,
  every remaining print taken away from the taker who really got it):

| start | whole period, 51 releases / 268 markets | reporting part (from 2026-10-15), 30 releases / 140 markets | t (mean per release, reporting part) |
|---|---|---|---|
| +5 s | $6,147 on $22,913 cost, $70.65/day | $2,038 on $9,049, $47.40/day | 2.56 |
| +30 s (primary, declared in advance) | $640 on $3,692, $7.36/day | $570 on $3,327, $13.25/day | 1.84 |
| +2 min | $183 on $2,432, $2.11/day | $121 on $2,198, $2.81/day | 1.40 |
| +10 min | $76 on $1,640, $0.88/day | $74 on $1,632, $1.72/day | 1.00 |

- Verdict by the pre-set rule (primary variant, reporting part: positive, t = 1.84 < 2, fills in 11 of 140 markets and
  5 of 30 releases): **INCONCLUSIVE**, and small. A trader who needs 30 seconds finds nothing in any US release
  (Employment, PPI, GDP, FOMC, JOLTS, ISM, Michigan: zero fills at +30 s; CPI and PCE: only flagged or trivial fills). What
  is left at +30 s is three thin non-US releases (Germany GDP, Korea GDP, Argentina CPI) worth about $500 in total.
- The +5 s row clears t > 2, but it is not an edge that can be banked: (1) it is an upper bound that assumes we displace
  the incumbent bots on every print; (2) 54% of it sits in fills stamped +5 s and +6 s, inside the 1-2 s timestamp
  jitter, so it is really "be exactly as fast as the fastest wallets"; (3) every E4 fill is profitable by construction
  (the outcome is used), so the t-statistic measures how regularly stale offers exist, not whether we would get them.
- For the lab's time-gap hypothesis: the gap here exists but is 0-15 seconds wide and is contested by a handful of
  specialised wallets; it is a "parse the release and fire" race at the scale of seconds (not milliseconds), with a
  total pool of roughly $350/day shared among everyone, heavily concentrated in CPI, FOMC, PCE and a few surprises.

## What entered and what was dropped

- Calendar: 61 release rows fixed in `release_calendar.py` before the tapes; 84 Polymarket events matched them.
  Tier A (BLS, BEA, Fed calendars fetched today): Employment 09-04, 10-02, 11-06; CPI 09-11, 10-14, 11-10; PPI 09-10,
  10-15, 11-13; Personal Income and Outlays 09-30, 10-29, 11-25; GDP advance Q3 10-29; FOMC 09-16, 10-28 (18:00 UTC);
  JOLTS 09-01, 09-29, 11-03. No postponement in the period. Retail sales and weekly jobless claims: no Polymarket
  market exists, nothing measured.
- Markets after the filters: 295 (volume >= 5,000, Yes/No, resolved 1/0, closed after T). Dropped: 302 markets under
  $5,000 volume; 16 closed before the scheduled time (5 duplicate "Fed decision in September" markets closed in May, 6
  "Fed decisions" combination buckets already dead in July, 5 China GDP markets that closed on 10-19 while the rules
  said 10-20 — the date in the rules was wrong, the event is not re-timed and is lost).
- Time confirmation (protocol section 4): 42 releases confirmed by a >= 0.10 move inside [-5 s, +60 s]; 6 confirmed by
  the activity burst (no market moved by 0.10: BANXICO-sep, RBA-sep, RBA-nov, BOE-nov, BCCH-oct, BOI-nov); 5
  investigated and kept — in each the "early move" was one 5-10 share print 14-44 s before T and the burst of trading
  starts at 0 to +6 s (US-EMP-august, US-CPI-august, US-PCE-august, US-ISMM-october) or at +39 s with a 0.44 -> 0.02
  move (AR-CPI-oct; INDEC evidently publishes some tens of seconds after 16:00); 7 tier B releases dropped as
  unconfirmed (RBNZ-sep, BOC-sep, ECB-sep, BOE-sep, SNB-sep, BOI-oct, ECB-oct: 27 markets, $2.1M volume; all were fully
  priced, the largest pre-release gap to the outcome among them was 0.09, so nothing material is lost with them).
- Excluded before the tapes (no scheduled second or not a single release): BoJ, Copom, Colombia, SARB, RBI, Bank of
  Korea, PBoC, China CPI (rules give only the month), deadline/ladder/price-level markets.
- Final set: **53 release ids on 51 distinct seconds (the clusters), 75 Polymarket events, 268 markets, $318M volume**
  ($310M of it in the ten Fed-decision markets). By type: CPI 74 markets, non-US central banks 48, non-US GDP 35, FOMC
  26, PCE 19, Employment 18, ISM 15, non-US inflation 11, PPI 7, JOLTS 6, Michigan 6, US GDP 3.
- Flagged in advance as needing judgement or arriving later: 39 markets (eggs 9, dissent count 8, Fed-decisions
  combinations 8, closed more than 6 h after the release 14 — the October CPI annual and core y/y events, which stayed
  open for ten days with the winner trading at 0.94-0.96).
- Sanity slice: fee formula reproduces (100 shares at 0.50 -> $0.25); all tapes present, none hit the cap; over 15,701
  pre-release prints in 167 markets, positions opened at 0.40-0.60 won 49.1% (dollar-weighted 53.9%).

## Tables

Times are match times (block time minus 3 s) relative to the scheduled second; jitter 1-2 s. Dollar cells in E3 are
"dollars that changed hands / gap dollars".

## Entry

markets measured: 268; Polymarket-release ids: 53; release seconds (clusters): 51; early part 21 clusters / 128 markets, reporting part 30 clusters / 140 markets
flagged (judgement / late) markets: 39; markets with no print after T: 33; with no print before T: 0

## E1 — winner's last traded price before the release

| type | releases | markets | median E1 | E1 < 0.50 | 0.50-0.90 | >= 0.90 | median age of that print, s |
|---|---|---|---|---|---|---|---|
| Employment | 3 | 18 | 0.549 | 6 | 11 | 1 | 198 |
| CPI | 3 | 74 | 0.926 | 15 | 15 | 44 | 597 |
| PPI | 3 | 7 | 0.700 | 2 | 5 | 0 | 9,729 |
| PCE | 3 | 19 | 0.750 | 5 | 10 | 4 | 589 |
| GDP | 1 | 3 | 0.760 | 0 | 2 | 1 | 6,296 |
| FOMC | 2 | 26 | 0.950 | 2 | 8 | 16 | 344 |
| JOLTS | 3 | 6 | 0.825 | 2 | 3 | 1 | 6,066 |
| ISM | 6 | 15 | 0.710 | 6 | 7 | 2 | 836 |
| UMich | 3 | 6 | 0.980 | 0 | 2 | 4 | 24 |
| Central bank (non-US) | 12 | 48 | 0.996 | 6 | 4 | 38 | 2,462 |
| Inflation (non-US) | 5 | 11 | 0.570 | 4 | 7 | 0 | 951 |
| GDP (non-US) | 9 | 35 | 0.862 | 6 | 12 | 17 | 20,229 |
| ALL | 51 | 268 | 0.888 | 54 | 86 | 128 | 1,099 |

## E2 — seconds from the release to the first print of the winner at >= 0.90 / 0.95 / 0.99

Markets that were still uncertain (E1 < 0.90). 'never' = no such print before the tape ended.

| group | releases | markets | med to 0.90 | med to 0.95 | med to 0.99 | p75 to 0.95 | reached 0.95 within 5 s / 30 s / 2 min | never 0.95 | never 0.99 |
|---|---|---|---|---|---|---|---|---|---|
| Employment | 3 | 17 | 12 | 11 | 11 | 14 | 3 / 14 / 16 | 1 | 1 |
| CPI | 3 | 30 | 6 | 6 | 10 | 12 | 15 / 26 / 27 | 0 | 0 |
| PPI | 3 | 7 | 4 | 7 | 7 | 10 | 3 / 6 / 6 | 0 | 0 |
| PCE | 3 | 15 | 6 | 6 | 10 | 9 | 6 / 13 / 14 | 1 | 1 |
| GDP | 1 | 2 | 4 | 4 | 4 | 4 | 2 / 2 / 2 | 0 | 0 |
| FOMC | 2 | 10 | 10 | 15 | 17 | 15 | 4 / 9 / 9 | 0 | 0 |
| JOLTS | 3 | 5 | 2 | 2 | 2 | 3 | 5 / 5 / 5 | 0 | 0 |
| ISM | 6 | 13 | 0 | 0 | 0 | 1 | 11 / 12 / 12 | 0 | 0 |
| UMich | 2 | 2 | 1 | 1 | 1 | 0 | 2 / 2 / 2 | 0 | 0 |
| Central bank (non-US) | 5 | 10 | 4 | 4 | 4 | 4 | 8 / 10 / 10 | 0 | 0 |
| Inflation (non-US) | 5 | 11 | 21 | 21 | 192 | 39 | 4 / 7 / 9 | 0 | 0 |
| GDP (non-US) | 9 | 18 | 1 | 1 | 6 | 3 | 13 / 14 / 16 | 0 | 0 |
| size 5K-20K | 38 | 102 | 5 | 5 | 10 | 14 | 52 / 87 / 93 | 2 | 2 |
| size 20K-100K | 20 | 29 | 5 | 5 | 6 | 8 | 16 / 25 / 27 | 0 | 0 |
| size 100K-1M | 4 | 7 | 1 | 4 | 4 | 4 | 6 / 6 / 6 | 0 | 0 |
| size >1M | 1 | 2 | 1 | 2 | 2 | 1 | 2 / 2 / 2 | 0 | 0 |
| ALL | 43 | 140 | 4 | 5 | 8 | 13 | 76 / 120 / 128 | 2 | 2 |

Per release (median over its uncertain markets that reached 0.95): 43 releases, median 4 s, quartiles 1 / 10 s, max 177 s; releases with median <= 5 s: 27, <= 30 s: 38

## E3 — dollars traded after the release at prices more than 5 cents short of the outcome

(a) taker bought the winner below 0.95 or sold the loser above 0.05. Cells: dollars that changed hands / gap dollars (shares x (1 - winner price)).

| group | releases | markets | 0-5s | 5-30s | 30s-2m | 2-10m | later | total (a) | (b) wrong-side takers, total |
|---|---|---|---|---|---|---|---|---|---|
| Employment | 3 | 18 | 837 / 320 | 3,237 / 555 | 0 / 0 | 0 / 0 | 0 / 0 | 4,074 / 875 | 3 / 3 |
| CPI | 3 | 74 | 5,796 / 1,874 | 17,567 / 9,152 | 23 / 3 | 228 / 62 | 517 / 38 | 24,131 / 11,129 | 4,253 / 462 |
| PPI | 3 | 7 | 2,915 / 578 | 449 / 217 | 0 / 0 | 0 / 0 | 0 / 0 | 3,364 / 795 | 182 / 182 |
| PCE | 3 | 19 | 33 / 3 | 4,727 / 2,259 | 0 / 0 | 0 / 0 | 2 / 2 | 4,762 / 2,264 | 112 / 112 |
| GDP | 1 | 3 | 556 / 109 | 4,028 / 413 | 0 / 0 | 0 / 0 | 0 / 0 | 4,584 / 522 | 0 / 0 |
| FOMC | 2 | 26 | 34,228 / 5,313 | 659 / 174 | 0 / 0 | 0 / 0 | 0 / 0 | 34,888 / 5,488 | 224 / 224 |
| JOLTS | 3 | 6 | 951 / 446 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 951 / 446 | 0 / 0 |
| ISM | 6 | 15 | 3,962 / 870 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 3,962 / 870 | 18 / 2 |
| UMich | 3 | 6 | 244 / 31 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 244 / 31 | 0 / 0 |
| Central bank (non-US) | 12 | 48 | 14,208 / 1,155 | 5,024 / 3,964 | 128 / 11 | 0 / 0 | 0 / 0 | 19,360 / 5,131 | 19 / 15 |
| Inflation (non-US) | 5 | 11 | 1,525 / 1,246 | 495 / 96 | 166 / 229 | 0 / 0 | 0 / 0 | 2,186 / 1,570 | 47 / 45 |
| GDP (non-US) | 9 | 35 | 2,947 / 822 | 97 / 133 | 885 / 220 | 612 / 52 | 0 / 0 | 4,541 / 1,227 | 51 / 47 |
| size 5K-20K | 46 | 180 | 18,878 / 5,739 | 17,462 / 5,006 | 682 / 193 | 273 / 64 | 2 / 2 | 37,298 / 11,005 | 670 / 643 |
| size 20K-100K | 30 | 59 | 7,431 / 2,814 | 18,820 / 11,957 | 520 / 270 | 567 / 49 | 517 / 38 | 27,856 / 15,127 | 4,230 / 440 |
| size 100K-1M | 7 | 19 | 29,536 / 2,172 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 29,536 / 2,172 | 0 / 0 |
| size >1M | 2 | 10 | 12,357 / 2,043 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 12,357 / 2,043 | 8 / 8 |
| ALL | 51 | 268 | 68,202 / 12,768 | 36,282 / 16,964 | 1,202 / 462 | 840 / 113 | 520 / 40 | 107,046 / 30,347 | 4,908 / 1,091 |
| early part | 21 | 128 | 42,988 / 6,780 | 23,769 / 11,954 | 32 / 3 | 226 / 61 | 2 / 2 | 67,018 / 18,800 | 519 / 503 |
| reporting part | 30 | 140 | 25,214 / 5,988 | 12,514 / 5,010 | 1,170 / 459 | 614 / 53 | 517 / 38 | 40,028 / 11,547 | 4,389 / 589 |

(b) by time bucket, all markets: 0-5s: 311 / 291; 5-30s: 345 / 345; 30s-2m: 93 / 42; 2-10m: 57 / 7; later: 4,103 / 405

Wallets on side (a): 110 distinct takers over the study; gap dollars 30,347; top three take 46.7%, top ten 76.7%.
Top ten (gap dollars, number of releases they appear in): 0x8cb3ed 5,530 (18); 0x059468 5,149 (19); 0x67babd 3,489 (4); 0x2f633e 3,214 (14); 0x5a218c 1,259 (7); 0x97276d 1,228 (6); 0x64ff98 922 (5); 0x731a24 859 (3); 0xd61b43 850 (2); 0x2ef771 762 (1)
Per release with any (a) trade (38 releases): median number of taker wallets 4, median top-three share 100%.

## E4 — taker starting at release + d, winner bought at every later print <= 0.97, max $500 per market, fee 0.01

| set | d | releases (with fills) | markets (with fills) | cost $ | shares | avg price | fees $ | net $ | net / cost | t (by release) | mean net per release $ (se) | t | t if clustered by market |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | 5 s | 51 (18) | 268 (68) | 22,913 | 29,097 | 0.787 | 36.77 | 6,147 | 26.8% | 6.11 | 120.5 (41.9) | 2.88 | 5.16 |
| ALL | 30 s | 51 (9) | 268 (17) | 3,692 | 4,336 | 0.851 | 4.04 | 640 | 17.3% | 2.11 | 12.5 (6.2) | 2.02 | 2.90 |
| ALL | 120 s | 51 (4) | 268 (9) | 2,432 | 2,616 | 0.929 | 1.64 | 183 | 7.5% | 2.79 | 3.6 (2.0) | 1.76 | 4.47 |
| ALL | 600 s | 51 (2) | 268 (5) | 1,640 | 1,717 | 0.955 | 0.73 | 76 | 4.6% | 26.30 | 1.5 (1.4) | 1.03 | 13.19 |
| early part (before 2026-10-15) | 5 s | 21 (9) | 128 (41) | 13,864 | 17,997 | 0.770 | 24.50 | 4,109 | 29.6% | 7.03 | 195.7 (93.4) | 2.09 | 3.91 |
| early part (before 2026-10-15) | 30 s | 21 (4) | 128 (6) | 365 | 436 | 0.838 | 0.57 | 70 | 19.2% | 2.96 | 3.3 (2.9) | 1.17 | 4.17 |
| early part (before 2026-10-15) | 120 s | 21 (2) | 128 (3) | 234 | 297 | 0.788 | 0.49 | 62 | 26.7% | 121.92 | 3.0 (2.9) | 1.04 | 26.52 |
| early part (before 2026-10-15) | 600 s | 21 (1) | 128 (1) | 8 | 10 | 0.760 | 0.02 | 2 | 31.3% | - | 0.1 (0.1) | 1.00 | - |
| REPORTING part (from 2026-10-15) | 5 s | 30 (9) | 140 (27) | 9,049 | 11,100 | 0.815 | 12.27 | 2,038 | 22.5% | 2.86 | 67.9 (26.5) | 2.56 | 3.69 |
| REPORTING part (from 2026-10-15) | 30 s | 30 (5) | 140 (11) | 3,327 | 3,900 | 0.853 | 3.47 | 570 | 17.1% | 1.88 | 19.0 (10.3) | 1.84 | 2.59 |
| REPORTING part (from 2026-10-15) | 120 s | 30 (2) | 140 (6) | 2,198 | 2,320 | 0.947 | 1.15 | 121 | 5.5% | 5.44 | 4.0 (2.9) | 1.40 | 6.90 |
| REPORTING part (from 2026-10-15) | 600 s | 30 (1) | 140 (4) | 1,632 | 1,707 | 0.956 | 0.71 | 74 | 4.5% | - | 2.5 (2.5) | 1.00 | 13.88 |
| mechanical mapping only (unflagged) | 5 s | 51 (15) | 229 (52) | 18,646 | 24,162 | 0.772 | 31.66 | 5,483 | 29.4% | 5.91 | 107.5 (40.6) | 2.65 | 4.72 |
| mechanical mapping only (unflagged) | 30 s | 51 (7) | 229 (11) | 1,834 | 2,342 | 0.783 | 2.85 | 506 | 27.6% | 2.31 | 9.9 (6.0) | 1.64 | 2.66 |
| mechanical mapping only (unflagged) | 120 s | 51 (2) | 229 (3) | 573 | 622 | 0.921 | 0.45 | 49 | 8.5% | 19.73 | 1.0 (0.9) | 1.05 | 22.70 |
| mechanical mapping only (unflagged) | 600 s | 51 (1) | 229 (1) | 8 | 10 | 0.760 | 0.02 | 2 | 31.3% | - | 0.0 (0.0) | 1.00 | - |
| flagged (judgement / late) | 5 s | 5 (5) | 39 (16) | 4,267 | 4,935 | 0.865 | 5.11 | 663 | 15.5% | 2.08 | 132.7 (47.3) | 2.81 | 3.29 |
| flagged (judgement / late) | 30 s | 5 (2) | 39 (6) | 1,859 | 1,994 | 0.932 | 1.19 | 134 | 7.2% | 1.94 | 26.9 (16.6) | 1.62 | 3.37 |
| flagged (judgement / late) | 120 s | 5 (2) | 39 (6) | 1,859 | 1,994 | 0.932 | 1.19 | 134 | 7.2% | 1.94 | 26.9 (16.6) | 1.62 | 3.37 |
| flagged (judgement / late) | 600 s | 5 (1) | 39 (4) | 1,632 | 1,707 | 0.956 | 0.71 | 74 | 4.5% | - | 14.8 (14.8) | 1.00 | 13.75 |

By release type:

| set | d | releases (with fills) | markets (with fills) | cost $ | shares | avg price | fees $ | net $ | net / cost | t (by release) | mean net per release $ (se) | t | t if clustered by market |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Employment | 5 s | 3 (2) | 18 (10) | 3,123 | 3,610 | 0.865 | 4.01 | 482 | 15.4% | 6.96 | 160.8 (80.8) | 1.99 | 5.03 |
| Employment | 30 s | 3 (0) | 18 (0) | 0 | 0 | - | 0.00 | 0 | -% | - | 0.0 (0.0) | - | - |
| CPI | 5 s | 3 (3) | 74 (26) | 9,932 | 12,498 | 0.795 | 15.09 | 2,551 | 25.7% | 3.70 | 850.4 (517.5) | 1.64 | 2.58 |
| CPI | 30 s | 3 (3) | 74 (8) | 1,981 | 2,124 | 0.933 | 1.26 | 142 | 7.1% | 1.89 | 47.2 (20.4) | 2.32 | 3.60 |
| PPI | 5 s | 3 (1) | 7 (2) | 505 | 724 | 0.697 | 1.49 | 218 | 43.1% | - | 72.6 (72.6) | 1.00 | 6.67 |
| PPI | 30 s | 3 (0) | 7 (0) | 0 | 0 | - | 0.00 | 0 | -% | - | 0.0 (0.0) | - | - |
| PCE | 5 s | 3 (3) | 19 (9) | 3,570 | 4,548 | 0.785 | 5.73 | 972 | 27.2% | 1.54 | 324.1 (192.7) | 1.68 | 2.32 |
| PCE | 30 s | 3 (1) | 19 (1) | 8 | 10 | 0.760 | 0.02 | 2 | 31.3% | - | 0.8 (0.8) | 1.00 | - |
| GDP | 5 s | 1 (1) | 3 (2) | 1,000 | 1,101 | 0.908 | 0.92 | 101 | 10.1% | - | 100.5 (-) | - | 11.96 |
| GDP | 30 s | 1 (0) | 3 (0) | 0 | 0 | - | 0.00 | 0 | -% | - | 0.0 (-) | - | - |
| FOMC | 5 s | 2 (2) | 26 (6) | 740 | 919 | 0.806 | 1.39 | 177 | 23.9% | 7.65 | 88.5 (46.9) | 1.89 | 5.21 |
| FOMC | 30 s | 2 (0) | 26 (0) | 0 | 0 | - | 0.00 | 0 | -% | - | 0.0 (0.0) | - | - |
| JOLTS | 5 s | 3 (0) | 6 (0) | 0 | 0 | - | 0.00 | 0 | -% | - | 0.0 (0.0) | - | - |
| JOLTS | 30 s | 3 (0) | 6 (0) | 0 | 0 | - | 0.00 | 0 | -% | - | 0.0 (0.0) | - | - |
| ISM | 5 s | 6 (0) | 15 (0) | 0 | 0 | - | 0.00 | 0 | -% | - | 0.0 (0.0) | - | - |
| ISM | 30 s | 6 (0) | 15 (0) | 0 | 0 | - | 0.00 | 0 | -% | - | 0.0 (0.0) | - | - |
| UMich | 5 s | 3 (0) | 6 (0) | 0 | 0 | - | 0.00 | 0 | -% | - | 0.0 (0.0) | - | - |
| UMich | 30 s | 3 (0) | 6 (0) | 0 | 0 | - | 0.00 | 0 | -% | - | 0.0 (0.0) | - | - |
| Central bank (non-US) | 5 s | 12 (3) | 48 (5) | 1,943 | 2,885 | 0.673 | 4.17 | 938 | 48.3% | 3.10 | 78.2 (57.1) | 1.37 | 2.30 |
| Central bank (non-US) | 30 s | 12 (2) | 48 (2) | 128 | 139 | 0.921 | 0.10 | 11 | 8.6% | 35.32 | 0.9 (0.9) | 1.06 | 36.51 |
| Inflation (non-US) | 5 s | 5 (2) | 11 (4) | 661 | 985 | 0.671 | 1.62 | 323 | 48.8% | 1.39 | 64.5 (44.8) | 1.44 | 1.88 |
| Inflation (non-US) | 30 s | 5 (1) | 11 (2) | 166 | 395 | 0.421 | 0.82 | 228 | 137.0% | - | 45.6 (45.6) | 1.00 | 27.57 |
| GDP (non-US) | 5 s | 9 (2) | 35 (4) | 1,439 | 1,826 | 0.788 | 2.35 | 385 | 26.7% | 2.44 | 42.7 (37.0) | 1.16 | 2.75 |
| GDP (non-US) | 30 s | 9 (2) | 35 (4) | 1,409 | 1,668 | 0.845 | 1.84 | 257 | 18.2% | 3.05 | 28.6 (23.1) | 1.24 | 3.44 |

By market size:

| set | d | releases (with fills) | markets (with fills) | cost $ | shares | avg price | fees $ | net $ | net / cost | t (by release) | mean net per release $ (se) | t | t if clustered by market |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| size 5K-20K | 5 s | 46 (15) | 180 (43) | 13,430 | 16,491 | 0.814 | 20.96 | 3,040 | 22.6% | 4.75 | 66.1 (21.1) | 3.14 | 5.95 |
| size 5K-20K | 30 s | 46 (7) | 180 (9) | 1,084 | 1,345 | 0.806 | 1.75 | 259 | 23.9% | 4.89 | 5.6 (3.4) | 1.63 | 5.17 |
| size 20K-100K | 5 s | 30 (13) | 59 (24) | 8,983 | 12,089 | 0.743 | 15.65 | 3,091 | 34.4% | 4.13 | 103.0 (51.8) | 1.99 | 2.91 |
| size 20K-100K | 30 s | 30 (6) | 59 (8) | 2,608 | 2,991 | 0.872 | 2.29 | 381 | 14.6% | 1.60 | 12.7 (7.1) | 1.78 | 1.90 |
| size 100K-1M | 5 s | 7 (1) | 19 (1) | 500 | 516 | 0.969 | 0.16 | 16 | 3.2% | - | 2.3 (2.3) | 1.00 | - |
| size 100K-1M | 30 s | 7 (0) | 19 (0) | 0 | 0 | - | 0.00 | 0 | -% | - | 0.0 (0.0) | - | - |
| size >1M | 5 s | 2 (0) | 10 (0) | 0 | 0 | - | 0.00 | 0 | -% | - | 0.0 (0.0) | - | - |
| size >1M | 30 s | 2 (0) | 10 (0) | 0 | 0 | - | 0.00 | 0 | -% | - | 0.0 (0.0) | - | - |

US official calendar (tier A) vs the rest:

| set | d | releases (with fills) | markets (with fills) | cost $ | shares | avg price | fees $ | net $ | net / cost | t (by release) | mean net per release $ (se) | t | t if clustered by market |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tier A (BLS, BEA, Fed) | 5 s | 17 (11) | 153 (55) | 18,870 | 23,400 | 0.806 | 28.63 | 4,501 | 23.9% | 4.98 | 264.8 (111.0) | 2.39 | 4.15 |
| tier B (others) | 5 s | 35 (7) | 115 (13) | 4,043 | 5,697 | 0.710 | 8.14 | 1,646 | 40.7% | 3.85 | 47.0 (22.5) | 2.09 | 3.49 |
| tier A (BLS, BEA, Fed) | 30 s | 17 (4) | 153 (9) | 1,988 | 2,134 | 0.932 | 1.28 | 144 | 7.2% | 2.25 | 8.5 (5.4) | 1.57 | 3.63 |
| tier B (others) | 30 s | 35 (5) | 115 (8) | 1,704 | 2,203 | 0.774 | 2.76 | 496 | 29.1% | 2.23 | 14.2 (8.7) | 1.62 | 2.57 |

Dollars per calendar day (ALL: 87 days; reporting part: 43 days):
- d = 5 s: 70.65 $/day over the whole period, 47.40 $/day in the reporting part
- d = 30 s: 7.36 $/day over the whole period, 13.25 $/day in the reporting part
- d = 120 s: 2.11 $/day over the whole period, 2.81 $/day in the reporting part
- d = 600 s: 0.88 $/day over the whole period, 1.72 $/day in the reporting part

Where the d = 5 s and d = 30 s profit sits (per release, top ten by net):

d = 5 s, total 6,147; top three releases = 52% of it
- 2026-10-14 12:30 US-CPI-september: net 1,858 on cost 5,817, fills from +5 s to +17 s
- 2026-09-30 12:30 US-PCE-august: net 707 on cost 1,062, fills from +6 s to +968 s
- 2026-10-28 01:00 RBNZ-oct: net 658 on cost 1,000, fills from +5 s to +5 s
- 2026-09-11 12:30 US-CPI-august: net 550 on cost 1,907, fills from +13 s to +334 s
- 2026-10-30 09:00 DE-GDP-q3: net 335 on cost 862, fills from +6 s to +99 s
- 2026-10-29 12:30 US-GDP-q3adv+US-PCE-september: net 268 on cost 2,508, fills from +5 s to +5 s
- 2026-09-01 13:00 BOI-sep: net 264 on cost 443, fills from +6 s to +30 s
- 2026-09-04 12:30 US-EMP-august: net 255 on cost 1,912, fills from +13 s to +16 s
- 2026-11-12 19:00 AR-CPI-oct: net 228 on cost 166, fills from +39 s to +75 s
- 2026-10-02 12:30 US-EMP-september: net 227 on cost 1,211, fills from +5 s to +14 s

d = 30 s, total 640; top three releases = 80% of it
- 2026-11-12 19:00 AR-CPI-oct: net 228 on cost 166, fills from +39 s to +75 s
- 2026-10-30 09:00 DE-GDP-q3: net 208 on cost 832, fills from +57 s to +117 s
- 2026-11-10 13:30 US-CPI-october: net 74 on cost 1,632, fills from +180 s to +889612 s
- 2026-09-11 12:30 US-CPI-august: net 60 on cost 226, fills from +165 s to +334 s
- 2026-10-26 23:00 KR-GDP-q3: net 49 on cost 577, fills from +104 s to +380 s
- 2026-10-28 01:00 RBNZ-oct: net 10 on cost 119, fills from +41 s to +96 s
- 2026-10-14 12:30 US-CPI-september: net 7 on cost 122, fills from +30 s to +83 s
- 2026-09-30 12:30 US-PCE-august: net 2 on cost 8, fills from +968 s to +968 s
- 2026-09-01 13:00 BOI-sep: net 1 on cost 9, fills from +30 s to +30 s

E4 fills by the offset of the fill (all markets), share of net profit:
- d = 5 s: <10s: net 3,662 on cost 10,743; 10-30s: net 1,868 on cost 8,786; 30s-2m: net 435 on cost 965; 2-10m: net 133 on cost 1,307; 10m-1h: net 20 on cost 480; >1h: net 29 on cost 632
- d = 30 s: <10s: net 0 on cost 0; 10-30s: net 0 on cost 0; 30s-2m: net 458 on cost 1,273; 2-10m: net 133 on cost 1,307; 10m-1h: net 20 on cost 480; >1h: net 29 on cost 632

## Reading the tables

- E1. Half of the kept markets were already at >= 0.90 for the eventual winner (most buckets of a multi-bucket event are
  dead before the number). The uncertain ones are where the money is: 140 markets.
- E2 by type. ISM, Michigan, JOLTS, non-US GDP and central banks: 0-4 s. CPI, PCE, PPI, US GDP: 4-7 s. Employment
  11 s and FOMC 15 s to the first 0.95 print (the first informed prints are earlier; these are multi-bucket events
  where the last buckets take longer). Non-US inflation 21 s, driven by Argentina (first print at +15 to +39 s, which
  looks like the publisher's own delay rather than a slow market).
- E3 by second (diagnostic, all releases): gap dollars taken at +0..+6 s: 24.5K of 30.3K; a second cluster at +13..+17 s
  (4.6K, of which 3.0K is the September CPI released on 10-14); after +30 s: 0.6K in 87 days. First informed taker print per release: 0 s in
  11 releases, 1-4 s in 21, 5-6 s in 3, 13-39 s in 3 (38 releases had any).
- Who takes it. First 5 seconds: 0x2f633e, 0x8cb3ed, 0x5a218c, 0x059468, 0x97276d (together 57% of that bucket).
  From 5 s on: 0x8cb3ed, 0x059468, 0x67babd (66% of that bucket). Per release the median number of taker wallets on
  the informed side is 4 and the top three take everything.
- Wrong-side takers (b) are negligible ($1.1K of gap in total): almost nobody sells the winner cheap after the number.
- E4 at +30 s, market by market (17 markets): Germany GDP Q3 $208 (fills +57..+117 s), Argentina CPI October $228
  (+39..+75 s, i.e. the first reaction), Korea GDP Q3 $49 (+104..+380 s), RBNZ October $10, US CPI September $7
  (+30..+83 s, at 0.94-0.95), eggs in September $60 (flagged, +165..+334 s, the FRED-dependent market), US CPI October
  $74 (flagged: fills at 0.95-0.96 from +180 s to ten days later in the two events whose resolution was delayed — this
  is carrying resolution risk, not a time gap). Unflagged markets only, reporting part: $495 on $1,694 cost, t = 1.63.
- Market size. Nothing is left after 5 s in markets above $100K volume (one fill, $16). The stale offers live in
  $5K-$100K markets, which also caps what can be done: among the 112 such markets with any stale trade the median
  is $308 changing hands after the release, and it goes to the first taker.

## Is there a tradable edge, and how large

- At +30 s and later: no dependable edge. $7/day over the whole period and $13/day in the reporting part at $500 per
  market, as an upper bound, from 5-9 releases, t below 2; without the flagged markets $11.5/day (t = 1.63). In the US
  official releases it is zero.
- At +5 s: an upper bound of $47-71/day at $500 per market, t = 2.56 in the reporting part, but more than half of it
  needs fills at +5/+6 s where the incumbents already are, and all of it assumes we win every print. After +7 s the
  whole-period total from +7 s on is about $2,800 ($32/day), of which $1,800 is the +13..+17 s cluster (mostly the
  CPI release of 10-14). A realistic share for a newcomer who is as fast as the incumbents, splitting with 3-4 of them, would be of
  the order of $10-20/day (a guess, not a measurement), and close to the +30 s row if a few seconds slower.
- Stake: the binding limit is the stale liquidity, not capital. Cost deployed at +5 s averaged $340 per market with
  fills and $1,270 per release with fills (18 releases); at +30 s, $410 per release with fills (9 releases).

## What would have to be true for it to be real

1. We get the number, map it to the buckets and have orders matched within about 3-6 s of the publication second on
   BLS/BEA releases, and within 1-2 s on ISM, Michigan, FOMC and central banks. That means machine-readable parsing of
   the publisher's page with pre-computed bucket maps, from a host in an unrestricted country, with no manual step.
2. The incumbents (0x8cb3ed, 0x059468, 0x2f633e, 0x67babd, 0x5a218c, 0x97276d) do not get faster once a new taker
   appears, and resting stale offers keep being posted by the same kind of slow participants.
3. The outcome mapping is right every time: one wrong bucket at 0.80 costs four good fills. Rounding rules ("to one
   decimal", "falls exactly between two brackets -> higher bracket"), seasonally adjusted vs unadjusted, core vs
   headline and first-release-only clauses all matter; in October the CPI annual and core y/y events stayed unresolved
   for ten days with the "obvious" winner at 0.95.
4. The economics fee stays at 0.01 (at these prices the fee is about 0.1-0.2 cents per share; it is not what decides).

## What could not be checked

- Depth of book. Only prints are visible here: offers that nobody took do not appear, and the size behind a print is
  the size that traded, not the size that was offered. E4 is therefore neither a full count of what was available nor
  something a second taker could add to.
- True publication second. T is the scheduled second; BLS/BEA/Fed post at that second, but for INDEC and other tier B
  publishers the actual moment may be seconds later, so part of their "lag" is the publisher's.
- Timestamps are block times with 1-2 s jitter and an assumed 3 s lag; everything in the first 7 seconds is uncertain
  by that much, including the +5 s variant.
- Whether the incumbents are takers reading the release or makers pulling quotes: only the taker side is on the tape.
  Maker behaviour (how fast stale offers are cancelled) cannot be seen without recorded books; the public L2 archive
  (`chitoyuuri/polymarket-l2-v3-1-archive`, category `economy`) would show it and was not used here.
- The fee history for economics markets before 2026-11-20 was not verified (0.01 assumed throughout; the gamma field
  says 0 for the US GDP event).
- Seven tier B releases dropped as unconfirmed and the pre-excluded central banks (BoJ, Copom and others) were not
  measured; BoJ September alone had $1.5M volume.
- Sample: 51 release seconds over 87 days, one FOMC cycle pair, three prints of each monthly US release. Tails
  (a surprise 50 bp move, a postponed release, a shutdown) are not in the sample.

## Variants run

Four, all declared in the protocol: E4 with d = 5 s, 30 s (primary), 120 s, 600 s. No rule was added after the results.
Pre-declared splits (early/reporting, flagged/unflagged, type, size, tier) and two diagnostics that are not strategies
(gap dollars by second; E4 profit by fill second) are reported above.

## Toolkit notes (nothing under pmlab/ was edited)

- `gamma.iter_events` with its default `limit=100` gets HTTP 406 (gzip_required); pass `limit=50`.
- Tag `finance` returns the commodity/stock up-down series (10,000 events before the page cap) and no macro releases;
  it was fetched once by mistake and discarded.
- `updown.buyable/sellable` assume Up/Down outcome names; Yes/No markets need their own conversion (`lib.py` here).
- `stats.ratio_cluster` gives meaningless t-values (26, 122) when only one or two clusters have a non-zero
  denominator; the mean-per-release t from `stats.mean_se` over all clusters, zeros included, is the one used.
- `dataapi.iter_trades(condition=...)` cannot be windowed, but Fed-decision markets with $56M volume needed only 2,000
  rows to get from the close back to two hours before the statement, so early stopping is enough.

## Ideas (not run)

- Record the economy books live around the next releases (Employment 2026-12-04, FOMC 2026-12-09, CPI 2026-12-10) by REST
  polling of `/books` at 1 s from T - 60 s to T + 120 s, to see the resting stale offers and how fast makers pull them.
- Measure our own achievable latency: time from the scheduled second to the number being readable on bls.gov / bea.gov
  / federalreserve.gov from a VPS, against the +3..+6 s at which the incumbents' fills are stamped.
- Take the incumbent wallets apart with `pmlab.wallet` (0x8cb3ed, 0x059468, 0x2f633e, 0x67babd): are they profitable
  after wrong-bucket losses, do they also quote before the release, what else do they snipe.
- Maker side of the same event: resting bids for the outcome-consistent side placed just before T in thin non-US
  markets (Germany/Korea GDP, Argentina CPI), where absorption took 1-6 minutes.
- Thin non-US releases at off-hours as a separate study with an independently sourced calendar (Eurostat, Destatis,
  INDEC, BoK, NBS, BoJ), since that is the only place where anything survived 30 seconds.
- Delayed-resolution carry: the October CPI events traded at 0.95 for ten days after the number; study what the
  dispute was and whether such cases are systematically safe.
- Pre-release side: 49.1% win rate at 0.40-0.60 says takers have no edge before the number; check whether nowcasts
  (Cleveland Fed, GDPNow) beat the bucket prices in the last day.
