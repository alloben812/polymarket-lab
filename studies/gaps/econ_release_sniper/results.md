# Macro release sniper: could a fast, well-placed small taker get a share of the release race?

Study run 2026-11-27. Protocol: `protocol.md` (frozen before any outcome statistic). Code: `measure.py` (Part 1, the 12
cells), `diag.py` (diagnostics), `probe_sources.py` (Part 2 source probe), `december.py` and `dec_books.py` (Part 3
calendar and books), `paper_probe.py` (forward paper test, read-only). Outputs in `out/` (all small JSON).

## Verdict: PAPER TEST FIRST, then a live micro-test only if the paper test passes

- **On the tape the money is there, if you are matched about 1 second after the scheduled time.** One prepared buy
  of $50 per market at a limit of 0.95, matched at T + 1 s and splitting each stale print with the wallets that really
  took it (the primary cell): +$487 net after fees over 51 releases in 87 days, **about $170 a month** (95% interval
  $83-282). Reporting part (from 2026-10-15, 30 releases): +$306, **$217 a month ($73-424)**; early part +$181,
  $125 a month ($40-230). With $20 orders: $95 a month ($47-152). With $200 orders (account of $2,000): $345 a month
  ($153-622). Net per filled order: $7 at $20, $12 at $50, $25 at $200. About 7 releases and 14 filled orders a month.
- **The frozen rule therefore says "paper test", not "live test":** the numbers pass, but this sandbox could not show
  that an official source is readable within about 1 second of the publication second (BLS pages answer 403 to a
  script, the free BLS API allows 25 requests a day, the Fed feed is held in a Cloudflare cache for a few seconds even
  with a cache-busting query; only BEA is readable fresh by busting its 60 s cache). Everything above is conditional
  on that one fact, and on mapping the number to the bucket without a single mistake.
- **Why being 1 s fast might be enough:** on BLS and BEA releases (CPI, jobs, PPI, PCE, GDP, JOLTS) the current
  winners are not sub-second. Nothing stale trades before block +4 s (match about T + 1 s); the bulk is at block
  +6..+9 s (match about T + 3..6 s) and a second wave at +16..+18 s. On ISM, Michigan and the Fed the first informed
  prints sit at block +2..+4 s (match about T - 1 to + 1 s): a 1-second trader gets nothing there (0 fills on ISM and
  PCE in the primary cell, $13 on the Fed).
- **Pool size, for scale:** all takers together took $30.5K of profit after fees at stale prices in 87 days
  (about $10.7K a month, $350 a day), 112 wallets, top three 46%; the first 2 s (match) hold $7.1K of it, the first
  5 s $18.7K, the first 10 s $25.2K. The primary cell is about 1.6% of that pool.
- **What to do:** run `paper_probe.py` from a small server in AWS eu-west-1 at the December releases (JOLTS + ISM on
  1 Dec, jobs 4 Dec, Fed 9 Dec, CPI 10 Dec) and compare our detection time with the first stale print on the tape.
  Only if our order could have been matched by T + 0.7 s on at least three of the four, start the live micro-test
  below with $10-20 tickets.

## Question

Prices on Polymarket absorb a scheduled US macro number in about 5 s of block time and nothing is left after 30 s
(`studies/gaps/econ_release_lag`, audited). The source is public and timed to the second. Could a trader who reads the
number from the official source within tens to hundreds of milliseconds and sends prepared orders from AWS eu-west-1
(no taker delay on economics markets, fee 0.01 x p x (1 - p), no rebates) take a meaningful share, and how many dollars
is that per release and per month for an account of about 200 EUR and one of 2,000 USD?

## Data

- 268 markets (229 with a mechanical number-to-bucket mapping, used for the strategy) in 51 release seconds,
  2026-09-01 .. 2026-11-25 (87 days): US CPI, employment, PPI, PCE, GDP, JOLTS, FOMC, ISM, Michigan, non-US central
  banks, GDP and inflation. Whole-market tapes from the cache of `econ_release_lag` (`data/gaps_econ/tapes/`, audited
  against a fresh download and against gamma volume). Early part 21 releases (to 2026-10-14), reporting part 30.
- Fresh-data check (gamma, closed events ending 25-27 Nov, same tags): the only new release events are the core PCE
  October events of 25 Nov (already in the set) and the Bank of Korea decision (excluded family, no fixed second).
  Text search for jobless claims, initial claims and retail sales: **no Polymarket market exists**; there is also none
  for PPI in December.
- Part 2: 96 requests to 12 agency/exchange URLs from this sandbox (egress in Chicago, Cloudflare colo ORD), not from
  Ireland. Part 3: official December calendars (BLS, BEA, Fed via WebFetch), 189 open gamma events, one snapshot of the
  books of 29 December release events (2026-11-27 20:56 UTC).

## What was run

12 strategy cells, all declared in the protocol: arrival (match time) A1 = T + 1 s or A2 = T + 3 s x order size $20 /
$50 / $200 x fill scenario U (we displace whoever really took the print: upper bound) or S (we get 1/(k+1) of each
print, k = real takers in that market in the same 2 s window). One taker buy per market of the winning outcome, limit
0.95, filled against stale prints matched in [a, a + 2 s], cheapest first. Primary: A1, $50, S. Robustness of the
primary (5 runs, declared): best release removed, best ten markets removed, lag 2 s and 4 s, dearest-first order.
Diagnostics (not strategies): pool by window and by block second, earliest prints, first-wave wallets.

## Part 1 — the tape

### Pool: stale prints after T (winner buyable below 0.95), profit after the 0.01 fee

Windows on match time = block time - 3 s (lab rule). "First block" = the earliest block of each release with a stale print.

| window | all 268 markets: stale $ traded / profit after fee | wallets | top-3 share | releases with any | mechanical, reporting part: $ / profit | wallets | top-3 |
|---|---|---|---|---|---|---|---|
| first block | 27,786 / 10,319 | 40 | 77% | 40 of 51 | 18,660 / 7,349 | 27 | 78% |
| match <= 2 s (block <= 5) | 51,346 / 7,064 | 37 | 44% | 21 | 17,090 / 3,551 | 19 | 66% |
| match <= 5 s (block <= 8) | 91,481 / 18,653 | 69 | 52% | 35 | 36,500 / 10,579 | 31 | 79% |
| match <= 10 s (block <= 13) | 99,704 / 25,196 | 77 | 48% | 37 | 36,626 / 10,633 | 36 | 79% |
| all after T | 116,341 / 30,536 | 112 | 46% | 40 | 38,949 / 11,456 | 47 | 75% |

(The first-2-s window holds many dollars but little profit: large Fed-decision prints at 0.85-0.95.)

Profit after fee by block second, mechanical markets (`out/diag.json`): BLS/BEA releases $0 at blocks 0-3, $614 at 4,
$16 at 5, $625 at 6, $2,053 at 7, $1,944 at 8, $6,034 at 9, then $3,600 at 16-18. FOMC: $59 at 3, $1,495 at 4, $470
at 6. ISM/Michigan: $203 at 2, $863 at 3, nothing after 5. Non-US: spread over 2-10, largest $3,669 at 8 (RBNZ October).

First-wave wallets (blocks 3-5): 0x8cb3ed (8 releases), 0x5a218c (3), 0x2f633e (6), 0x059468 (8) and a handful of
one-off wallets: the same incumbents as in `econ_release_lag`.

### Were the first stale trades too early for a page reader?

Block - match lag is 1.06-3.33 s (1st-99th percentile), so a print at block +0/+1 was matched before T and one at +2
between T - 1.3 and T + 0.9 s. Winner-buyable vs loser-buyable dollars: blocks -60..-1 $10,452 vs $4,115 (2.5 : 1,
the market leans the right way before the number); blocks 0-1 $578 vs $80 (4 prints); block 2 $1,528 vs $26 (8 prints);
blocks 3-5 $49,240 vs $47; blocks 6-13 $48,359 vs $416.
- Blocks 0-1: the FOMC September print at 0.88 equals the price before the release, ISM services August $33: no sign of
  information, consistent with ordinary trading inside the block jitter.
- Block 2: ISM services September ($1,360, 0x2f633e at 0.89), Michigan October ($147, 0x059468), Japan GDP Q3 ($245,
  four wallets). These were matched within about a second of T: possible for a sub-second reader, impossible for a
  human. Nothing on BLS/BEA releases appears before block 4.
- Limits: one-second block stamps, 1-3.3 s lag, order inside a block is not match order. Any statement finer than
  about +-1 s is not supported by this data.

### A single prepared order (the 12 cells), mechanical markets, fee included

Net after fee, $ in 87 days (whole) and per month with 95% bootstrap intervals by release second.

| arrival | size | fill | orders filled (whole) | net per filled order | whole: net / per month (CI) | early part: net / month | reporting part: net / month (CI) | t (reporting) | US releases only, per month |
|---|---|---|---|---|---|---|---|---|---|
| T+1 s | $20 | U | 40 | 9.44 | 377 / 132 (62-214) | 202 / 140 | 175 / 124 (49-218) | 2.77 | 86 |
| T+1 s | $20 | S | 40 | 6.79 | 272 / 95 (47-152) | 134 / 93 | 138 / 97 (35-182) | 2.52 | 57 |
| T+1 s | $50 | U | 40 | 18.43 | 737 / 258 (120-427) | 381 / 263 | 356 / 252 (93-464) | 2.57 | 159 |
| **T+1 s** | **$50** | **S** | **40** | **12.17** | **487 / 170 (83-282)** | **181 / 125** | **306 / 217 (73-424)** | **2.33** | **84** |
| T+1 s | $200 | U | 40 | 43.97 | 1,759 / 615 (274-1,071) | 623 / 430 | 1,136 / 803 (248-1,628) | 2.20 | 303 |
| T+1 s | $200 | S | 40 | 24.65 | 986 / 345 (153-622) | 274 / 189 | 712 / 503 (146-1,039) | 2.14 | 153 |
| T+3 s | $20 | U | 51 | 18.09 | 923 / 322 (79-740) | 223 / 154 | 700 / 495 (58-1,270) | 1.39 | 113 |
| T+3 s | $20 | S | 51 | 16.38 | 836 / 292 (63-696) | 160 / 111 | 676 / 478 (52-1,245) | 1.34 | 89 |
| T+3 s | $50 | U | 51 | 41.76 | 2,130 / 744 (162-1,769) | 404 / 279 | 1,726 / 1,220 (133-3,157) | 1.37 | 225 |
| T+3 s | $50 | S | 51 | 27.03 | 1,379 / 482 (132-1,069) | 304 / 210 | 1,075 / 760 (121-1,867) | 1.53 | 187 |
| T+3 s | $200 | U | 51 | 101.29 | 5,166 / 1,805 (452-4,130) | 1,112 / 768 | 4,053 / 2,866 (411-7,208) | 1.45 | 695 |
| T+3 s | $200 | S | 51 | 44.05 | 2,247 / 785 (285-1,507) | 560 / 387 | 1,687 / 1,192 (278-2,597) | 1.98 | 436 |

How to read: "S" is the cell to believe more; "U" assumes we beat every real taker in the window. The T+3 s rows are
not "better because slower": their window (blocks 6-8) is where the main incumbent wave sits, so S there means
splitting with that wave, and half of the reporting-part money is one release (RBNZ October, $700 of $1,075 at $50 S;
t 1.3-1.5). The T+1 s rows are spread out (t 2.1-2.8) but they sit just before the wave.

Where the primary comes from (by type, whole period, $50 S): CPI $127 (13 orders), non-US inflation $130 (3; UK CPI
October $122), non-US GDP $98 (8), JOLTS $58 (5), employment $34 (2), central banks $17, FOMC $13, Michigan $6, PPI $3,
ISM, PCE and US GDP $0. Best markets: UK CPI October 3.4-3.6% $63 and 3.7-3.9% $59, JOLTS July $27, payrolls October
$26, JOLTS September $24, Japan GDP $24, CPI August $24.

### Attacks on the primary (T+1 s, $50, S)

| check | result |
|---|---|
| reporting part as defined | $306, $217/month (73-424), t 2.33, 11 of 30 releases with fills |
| without the best release (UK CPI October, $122) | $184, $130/month (52-220), t 2.93 |
| whole period without the best ten markets | $185, $65/month (31-104), t 3.51 |
| lag 2 s / 4 s instead of 3 s (reporting) | $317 / $454, $224 / $321 per month |
| dearest print first instead of cheapest (reporting) | $229, $162/month (60-298) |
| stale dollars in the primary window priced >= 5 c below an earlier post-T print of the same winner (new orders, audit F1) | $606 of $5,561 of gap (11%) |
| Germany GDP Q3 (audit: answer not mechanical for 100 s) | $9 of the primary: immaterial |
| capital: $50 orders with a 200 EUR (~$215) account | filled cost per release median $53, max $244, up to 7 orders; capping at $200 per release costs $5 of $487 |

What these checks cannot fix: (1) the outcome is known to the simulation, so a wrong bucket never appears (the audit
measured $329 lost by takers who went long a loser within 10 minutes of T in 7 releases; one wrong $50 order at 0.80
erases four average fills); (2) whether the stale offers printed at T + 1..3 s were already resting at T + 1 s; (3)
whether we would be matched at T + 1 s at all. The reporting part is also not unseen by the lab (the earlier study
published its aggregates), though nothing here was tuned on it.

## Part 2 — the design

### Where the number appears and how fast it can be read (measured from this sandbox, Chicago, 2026-11-27, 8 requests each)

| source | status | time to first byte | cache behaviour |
|---|---|---|---|
| BLS release pages (`bls.gov/news.release/cpi.nr0.htm`, `empsit.nr0.htm`) | 403 (AkamaiGHost) | 0.06-0.27 s | `no-cache, no-store`: no edge cache, but scripted clients are refused from this IP |
| BLS API v1 (`api.bls.gov/publicAPI/v1/timeseries/data/CUSR0000SA0`) | 200 | 0.17-0.39 s | `no-cache, no-store`: fresh; but 25 queries a day without a key, 500 with a free v2 key (BLS rules, not re-checked here) |
| BEA pages (current releases, PCE) | 200 | 0.09-0.38 s | Varnish `max-age=60`, Age 0-59 s; a cache-busting query string gives Age 0: fresh reads possible |
| Fed press releases page | 200 | 0.07-0.13 s | Cloudflare HIT; a busting query got REVALIDATED once |
| Fed monetary RSS | 200 | 0.07-0.09 s | Cloudflare HIT with Age 1-4 s even with a busting query: up to ~4 s stale |
| DOL weekly claims PDF | 200 | 0.07-0.23 s | Apache, `max-age=19`; Last-Modified Wed 25 Nov 13:29:59 UTC (file replaced 1 s before 8:30 ET). No market exists. |
| ISM PMI page | 302 (Cloudflare, dynamic) | 0.29-0.59 s | redirect / bot check for scripts |
| UMich SCA home | 200 | 0.21-0.46 s | CloudFront "RefreshHit": revalidated against origin |
| ONS CPI page | 200 | 0.21-1.8 s | Cloudflare `s-maxage=900`; busting query gives MISS |
| Polymarket CLOB `/time` (reference) | 200 | 0.16-0.33 s | dynamic |

No release fell inside the study window, so the update behaviour AT a release second (is the page live at T + 0.0 s,
does Akamai hold the old page, how long the BLS API lags its pages) is not measured. That is the first thing the paper
test measures.

### Fastest detection, by agency

- BLS (CPI, jobs, JOLTS, PPI): the release page or its known-in-advance text URL, polled every 100-250 ms with
  keep-alive and a browser-like client from a non-blocked IP; the API only as a confirmation (query budget). Rounding
  matters: markets resolve on the one-decimal figure printed in the release (Table A-15 U-3, CPI-U SA m/m, CPI-U NSA
  y/y, core SA m/m, core NSA y/y; payrolls "exactly between two brackets -> higher bracket").
- BEA (PCE, GDP): the release page with a cache-busting query (measured: Age 0). Markets resolve on the BEA Personal
  Income and Outlays release; the figure is the one-decimal percent in the release.
- Fed: the statement URL is predictable (`/newsevents/pressreleases/monetary<YYYYMMDD>a.htm`); poll it with a busting
  query until it stops returning 404, read the target-range sentence. The RSS feed can lag about 4 s. The dissent market
  needs the vote paragraph (flagged in the earlier study).
- ISM and Michigan: the incumbents are matched at about T + 0..1 s; a page reader starts behind them. Skip.
- Embargo: BLS/BEA/Fed news-agency lock-ups and paid low-latency feeds deliver the number at T + 0 to subscribers; a
  page reader competes with whoever uses them. The tape says nobody does so on BLS/BEA markets today (first stale
  print at block +4 s), which is the whole opportunity.

### Mapping and prepared orders

- Every December US event read today has a one-number rule (bracket containing the published figure, first release,
  revisions ignored). The program needs, per event, a table "published value -> winning market and token" built the day
  before, and must refuse to trade on any parse it cannot match exactly (no "closest bucket").
- Orders can be prepared: Polymarket orders are signed messages with price, size and expiry, so one buy per candidate
  bucket can be signed in advance and only the matching ones posted at T (fill-and-kill / FOK at limit 0.95). Markets
  checked: fee type `economics_fees`, rate 0.01, tick 0.001-0.01, minimum 5 shares, no `secondsDelay`.
- Pre-release books (snapshot 27 Nov): resting asks between 0.20 and 0.95 are $350-9,000 per bucket on CPI, jobs and
  JOLTS, far more than the ~$300 per market that trades stale after a release: most quotes are pulled before T, and what
  is left is what the incumbents take.

### Latency budget (estimates; only the sandbox column is measured)

| step | AWS eu-west-1 (Ireland) | detector us-east-1 + executor Ireland | Mac in Serbia (home line) |
|---|---|---|---|
| poll interval (half of 200 ms) | 100 ms | 100 ms | 100 ms |
| fetch from a no-cache US origin | 80-150 ms | 5-20 ms | 120-200 ms |
| parse + choose pre-signed order | < 5 ms | < 5 ms + 70 ms relay | < 5 ms |
| order to matching (London) | 15-40 ms | 15-40 ms | 40-80 ms + home jitter |
| matched at, if the page is live at T + 0 | T + 0.2-0.3 s | T + 0.2-0.25 s | T + 0.3-0.4 s (worse tail) |

Orders cannot be sent from the US (geoblocked); Ireland is restricted on the website only, not on the API; Serbia is not
listed. Location matters less than the source: a page that is cached for even 1-2 s erases the whole budget. Monthly cost:
a small eu-west-1 instance about $10-20 (the lab's own estimate in `docs/speed-infrastructure.md` is about $80 for a
larger box); the BLS v2 API key is free.

## Part 3 — December 2026 and the forward test

Release calendar (official pages read today: BLS schedule, BEA schedule, Fed calendar) and the Polymarket events open now
(volume is gamma `volumeNum`, which counts shares):

| date (UTC) | release | Polymarket events open now |
|---|---|---|
| Mon 30 Nov 13:30 | Canada GDP September (StatCan, time from rules) | `canada-gdp-september-2026-mom` (6 buckets, 22K) |
| Tue 1 Dec 15:00 | JOLTS October (BLS 10:00 ET); ISM manufacturing November (10:00 ET) | `jolts-job-openings-october-2026` (8, 36K); `ism-manufacturing-pmi-november-2026` (9, 20K) |
| Fri 4 Dec 13:30 | Employment Situation November | `november-unemployment-rate-2026` (9, 24K); `how-many-jobs-added-in-november-2026` (7, 10K); also Canada LFS `november-2026-unemployment-rate-canada` (7, 40K) |
| Wed 9 Dec 19:00 | FOMC statement (meeting 8-9 Dec, with projections) | `fed-decision-in-december` (5, 66.8M); dissents (5, 82K, flagged) |
| Thu 10 Dec 13:30 | CPI November | `november-inflation-us-annual` (12, 70K), `-monthly` (10, 15K), `core-cpi-yoy` (10, 22K), `core-cpi-mom` (7, 9K); eggs (flagged) |
| Tue 15 Dec 13:30 | PPI November | none found |
| 18 Dec (rules) | Michigan sentiment final December | `university-of-michigan-consumer-sentiment-december-2026` (7, 6K) |
| Wed 23 Dec 13:30 | Personal Income and Outlays November (PCE); GDP Q3 third estimate | `core-pce-mom/yoy`, `pce-mom/yoy-november-2026` (7 each, 0-3K: thin) |
| Dec, non-US | RBA (8 Dec), BoC (9 Dec), SNB (10 Dec), BCCh, Canada CPI (15 Dec), ECB and BoE (17 Dec), Banxico, Bank of Russia (18 Dec), RBNZ | one event each (35K-400K); times not fetched from the publishers |

Forward test, step 1 (paper, no money): run `paper_probe.py` from an eu-west-1 instance (or, second best, the Mac) at
1 Dec 15:00 (JOLTS page), 4 Dec 13:30 (empsit page), 9 Dec 19:00 (Fed statement URL), 10 Dec 13:30 (CPI page). It
records our first sight of the new page and the books once a second; afterwards compare with the tape. Pass: our
detection + 0.1 s is at or before T + 0.7 s and before the first stale print on at least 3 of the 4, and the parsed
number maps to the bucket that later resolves Yes on all 4. Step 2 only if step 1 passes: the live micro-test below.

## Opportunities, size, capacity, reaction time

- Opportunities: primary cell had fills in 20 of 51 release seconds (11 of 30 in the reporting part) and 40 orders in
  87 days: about 7 releases and 14 filled orders a month, 0.46 a day.
- Net per trade after fee at 5-20 USD size: about $6.8 per filled $20 order in the S scenario ($9.4 in U); a $10 order
  would make roughly half (fills are mostly limited by the order, not the print). Per release with fills: $14 at $20.
- Capacity for an account of about 200 EUR: about $3 a day ($95 a month) at $20 orders, about $5.6 a day ($170 a month;
  reporting part $217) at $50 orders with up to four orders per release; for $2,000 at $200 orders about $11 a day
  ($345 a month). Minus $10-80 a month for the server. All conditional on being matched at about T + 1 s.
- Reaction time needed: matched within about 1 s of the scheduled second on BLS/BEA releases (detection within
  ~0.5 s); on ISM, Michigan and the Fed even that is too slow. At T + 3 s the share is splitting the main wave (see table).

## Live micro-test (only after the paper test passes)

- Rule: for each mechanical bucket market of a BLS or BEA release (CPI, jobs, JOLTS, PCE) and the FOMC decision market,
  when the number is parsed from the official page, post the pre-signed buy of the winning token as fill-and-kill at a
  limit of 0.95, once. No order if the parse is not an exact match to the prepared table, or if detection is later than
  T + 1.5 s.
- Size: $10 per order in the first five releases, $20 after; at most 10 orders and $150 per release; account $50-100.
- Repetitions: 10 US releases (December and January: about 2 months). Tape expectation at $20: fills in about 40% of
  releases, about $7 per filled order. Ten releases are enough to tell "we are faster than the incumbents" (several
  fills, most at 0.6-0.9) from "we are behind" (zero or one fill, or fills only at 0.94-0.95); they are not enough to
  measure the dollar edge precisely (the per-month interval above is a factor of three wide).
- Stop at once on any fill in a bucket that does not resolve Yes for us (a mapping or parse error), or if losses reach
  $30. Stop after 6 releases with no fill below 0.92. Scale to $50 only if, after 10 releases, there are at least 5
  fills and the net is positive.

## Limitations

- The fill model is the weak point: no depth at T is observable from prints; the S share (1/(k+1)) is an assumption;
  U is a pure upper bound; 11% of the primary window's gap dollars were new offers that appeared after the price moved.
- Block-time resolution: one-second stamps, 1.06-3.33 s block lag, order inside a block not match order. "Matched at
  T + 1 s" in the tables means "printed at block +4..+6 s"; it cannot be distinguished from T + 0 or T + 2 s.
- The outcome is used by the simulation; mapping and parsing errors are not in the numbers.
- Sample: 51 release seconds, 20 with fills, 11 in the reporting part; three monthly prints of each US release, one Fed
  pair. The reporting part was not unseen by the lab (aggregates published by the earlier study).
- Part 2 is measured from Chicago through the lab's proxy, at a quiet time, not at a release, not from Ireland; BLS
  refuses this IP. The latency budget for Ireland and the Mac is an estimate.
- The economics fee was 0.036-0.048 before 2026-11-21 (NOTES.md); the simulation uses today's 0.01 for all releases
  (at these prices the difference is a few cents per order).
- With 200 EUR, $50 orders allow only about four orders per release if all are sent at once; the cap analysis assumes
  you pick the right four.

## Ideas, not tested

- A resting buy at 0.95 left after the fill-and-kill misses: it would catch late sellers but at 0.95, not at their price.
- Second wave on BLS releases (blocks +16..+18 s, $3.6K of profit in 87 days): who sells stale there and whether a
  re-sent order at T + 10 s captures it.
- Non-US releases at off-hours (UK CPI, Japan and UK GDP, RBNZ) carried a large part of the primary; their publishers'
  pages (ONS 900 s Cloudflare cache, busting works) deserve their own source probe.
- Record the economy books at 1 s around the December releases (part of `paper_probe.py`) to see how fast resting quotes
  are pulled and how much was actually resting at T + 1 s.
- Take the incumbents (0x8cb3ed, 0x059468, 0x2f633e, 0x5a218c) apart with `pmlab.wallet`: wrong-bucket losses, sources.
- Canada LFS / CPI markets (40K and 19K) on StatCan's fixed 8:30 ET release: not in the earlier sample at all.
