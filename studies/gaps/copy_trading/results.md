# Copying selected wallets with a 10 s / 60 s / 5 min delay — results

Study run 2026-11-27. Protocol: `protocol.md` (saved 18:12 UTC by file time, before any outcome number; its header
says "~18:30", which was a wrong estimate of the clock). Code: `select_wallets.py` (pool and selection), `fetch.py`
(entries, sample, tapes), `analyze.py` (simulation), `report.py` (tables). Outputs: `out/report.txt` (all tables),
`out/variants.csv` (every variant and subgroup), `out/selected.json` / `out/selected_typed.json` (the 36 wallets),
`out/select_log.txt`, `out/fetch_log.txt`. Raw data in `data/gaps_copy/` (not in git).

## Verdict: NEGATIVE. Nothing here deserves a live test.

- **Out of sample (late window, 21-25 Nov) every one of the 6 copy variants loses money after fees**: -10.1% of the
  money spent at 10 s, -11.1% at 60 s, -2.2% at 5 min (hold to resolution; closing when the wallet closes gives the
  same within 1 point). None is significant (t -0.1 to -1.2 by market; 92-204 markets), but none comes near the
  decision rule (positive with t >= 2). No subgroup qualifies either: the only |t| >= 3 cells are negative
  (taker-style wallets at 10 s: -25.4%, t -3.1; maker-style wallets at 5 min: -56.7%, t -3.4).
- **The chosen wallets themselves were not reliably profitable out of sample.** At their own prices and with the fee
  they actually paid as takers, the 704 sampled late entries returned +13.4% (95% CI -2.8 to +29.7%, t 1.6 by
  market, 630 markets), and +0.1% after dropping the 5 best markets: their result is a handful of long shots
  (entries under 0.20 returned +40.7%; everything above 0.80 about zero). That is before the survivorship bias of
  the pool, which works in their favour.
- **The delay removes what was left.** The copier pays a median 0.7-1.0 cent per share more than the wallet, fills
  only 31% / 22% / 15% of the entries at 10 s / 60 s / 5 min (nobody else trades the token in the 30 s after the
  delay in most markets), and the fills it does get are tilted to the active, already-moved markets.
- **In the early window (the window the wallets were selected on) copying looks good** (+32% at 10 s, t 2.5; +22%
  at 60 s; +29% at 5 min). That is the selection itself: wallets were picked because they made money in exactly
  those days. It did not carry over to the following five days.

## The question

A small account (about 200 EUR, no rebates, reaction time of a few seconds, trades of 5-20 USD) picks wallets by a
rule fixed in advance on an early window (category leaderboards, the advertised wallets of `catalog/raw/x1_wallets.md`,
the wallets analysed in `studies/wallets/`), then in a later window copies each BUY entry of theirs 10 s, 60 s or
5 min after it is visible, at a price the tape shows as buyable then, about 10 USD, holding to resolution or closing
when the wallet closes. Does it keep money after taker fees, by category and by whether the wallet buys as a taker
or with resting orders? How many copyable entries are there per day?

## Data

- Pool: 341 wallets = top ~22 of the month PNL board in 10 categories (219) + 71 addresses of `x1_wallets.md` +
  19 addresses in `studies/wallets/*/README.md` and the subject wallets of the per-wallet JSON files (165 outside the
  boards). 216 were eligible (trading result without rebates/rewards > 0 over 7-21 Nov, >= 30 trades).
- Chosen: 36 wallets (3 per board category + 6 from x1/studies), list in `out/selected.json`. Wallet type from the
  early window (share of BUY dollars as taker): 16 taker-style, 12 maker-style, 8 mixed/unknown.
- Early window: entries 7-20 Nov (Sat 7 Nov 00:00 - Sat 21 Nov 00:00 UTC); late window: entries 21-25 Nov
  (21 Nov 00:00 - 26 Nov 00:00 UTC, includes the weekend 21-22 Nov). Outcomes and exits read to 27 Nov ~18:30 UTC.
- Sample: 524 early and 704 late entries (first BUY per wallet and token, at most 15 / 25 random entries per wallet),
  1,080 markets, all 1,228 evaluable (no tape hit the 25-page cap). Per entry: the wallet's fills in that market
  and the whole-market tape (Data API v2 `trades`), resolutions from `tokens`, fee rate from gamma `feeSchedule`
  (mean rate on filled late copies 0.039-0.044: mostly sports and esports at 0.05). 27% of the late reference
  entries and 6-19% of the filled copies were unresolved at the data cut and are marked at the last tape price;
  resolved-only numbers are in `out/report.txt` and change nothing.

## What was run

7 runs in total, as fixed in the protocol: 3 delays (10 s, 60 s, 300 s) x 2 exits (HOLD to resolution, MIRROR =
sell when the wallet has sold half of what it bought) at 10 USD, plus the reference at the wallet's own price.
Breakdowns by entry type, wallet type, category, resolved-only, wallet clustering and drop-5-best are reports of
the same runs. The code was also run once on the first ~40% of the downloaded entries while the download was still
running, to debug it (same code, same rules; nothing was changed after it except the two deviations below).

Fill rule: the copier acts at block time + d; it gets the first block whose match time (block - 3 s) lies in
[t + d, t + d + 30 s] and shows the token buyable (taker BUY of it, or taker SELL of the other outcome at 1 - p),
at that block's VWAP, for no more than the shown size; under 1 USD = not filled. Taker fee always; rebates 0.

## Headline numbers (net after fees, return on money spent, 95% CI by market)

| run | window | entries | filled (rate) | markets | spent $ | net $ | return | 95% CI | t (market) | t (wallet) | net $/trade | drop 5 best |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| reference: wallet price | early | 524 | 524 | 491 | 5,286 | +2,510 | +47.5% | +17.5..+77.5 | +3.10 | +2.89 | +4.79 | +20.3% |
| d10 hold | early | 524 | 158 (30%) | 147 | 1,149 | +367 | +32.0% | +6.4..+57.5 | +2.45 | +2.10 | +2.33 | +11.4% |
| d10 mirror | early | 524 | 158 (30%) | 147 | 1,149 | +369 | +32.1% | +6.7..+57.6 | +2.48 | +2.08 | +2.34 | +11.5% |
| d60 hold | early | 524 | 111 (21%) | 105 | 918 | +202 | +22.1% | -3.5..+47.6 | +1.69 | +2.12 | +1.82 | +2.3% |
| d60 mirror | early | 524 | 111 (21%) | 105 | 918 | +204 | +22.2% | -3.3..+47.8 | +1.70 | +2.12 | +1.84 | +2.5% |
| d300 hold | early | 524 | 87 (17%) | 80 | 720 | +209 | +28.9% | -0.3..+58.2 | +1.94 | +1.80 | +2.40 | +5.6% |
| d300 mirror | early | 524 | 87 (17%) | 80 | 720 | +203 | +28.1% | -1.0..+57.2 | +1.89 | +1.74 | +2.33 | +5.4% |
| reference: wallet price | **late** | 704 | 704 | 630 | 7,107 | +954 | +13.4% | -2.8..+29.7 | +1.62 | +1.76 | +1.36 | +0.1% |
| d10 hold | **late** | 704 | 222 (32%) | 204 | 1,607 | -162 | **-10.1%** | -27.0..+6.8 | -1.17 | -1.23 | -0.73 | -23.7% |
| d10 mirror | **late** | 704 | 222 (32%) | 204 | 1,607 | -159 | -9.9% | -26.7..+6.9 | -1.15 | -1.21 | -0.72 | -23.5% |
| d60 hold | **late** | 704 | 152 (22%) | 139 | 1,067 | -118 | **-11.1%** | -30.0..+7.9 | -1.15 | -1.18 | -0.78 | -23.3% |
| d60 mirror | **late** | 704 | 152 (22%) | 139 | 1,067 | -117 | -10.9% | -29.9..+8.0 | -1.13 | -1.17 | -0.77 | -23.2% |
| d300 hold | **late** | 704 | 107 (15%) | 92 | 866 | -19 | **-2.2%** | -27.1..+22.8 | -0.17 | -0.13 | -0.18 | -25.2% |
| d300 mirror | **late** | 704 | 107 (15%) | 92 | 866 | -8 | -0.9% | -25.7..+23.8 | -0.07 | -0.06 | -0.08 | -23.8% |

The average filled copy is about $7, not $10: the first block after the delay often shows less than $10.

### Late window by entry type and wallet type (hold)

| group | ref (wallet price) | d10 | d60 | d300 |
|---|---|---|---|---|
| TAKER entries (wallet took liquidity) | +6.5% (t 1.2, 393 mkts) | -15.0% (t -2.1, 133) | -5.8% (t -0.7, 95) | -0.8% (t -0.1, 64) |
| MAKER entries (resting order filled) | +23.5% (t 1.2, 273) | -0.8% (t -0.0, 77) | -22.3% (t -0.9, 51) | -6.0% (t -0.2, 35) |
| taker-style wallets (16) | +4.3% (t 0.7, 289) | -25.4% (t -3.1, 79) | -17.3% (t -1.5, 53) | +13.4% (t 0.8, 42) |
| maker-style wallets (12) | +26.9% (t 1.3, 251) | +3.9% (t 0.2, 74) | -14.8% (t -0.5, 47) | -56.7% (t -3.4, 24) |
| mixed (8) | +8.2% (t 0.6, 125) | -2.0% (t -0.2, 60) | +0.3% (t 0.0, 46) | +2.9% (t 0.1, 33) |

The maker/taker distinction behaves as expected in one way: a maker entry's own price is better (+23.5% vs +6.5% for
the wallets themselves), and that advantage is exactly what a copier cannot get; copies of maker entries fill less
often (28% / 18% / 12%). Copies of taker entries are no better: taker-style wallets are the worst group to copy at 10 s.

### Late window by category (d10 hold; other delays in `out/report.txt`)

sports 91 fills / 88 markets -1.7% (t -0.2); esports 39 / 27 -12.2% (t -0.9); crypto (non up/down) 24 / 24 -38.4%
(t -3.3); finance 11 / 11 -61.8% (t -3.3); politics 13 / 11 -5.5%; tech 14 / 13 -12.7%; culture 7 / 7 -59%;
weather 6 / 6 -76%; economics 3 / 3 -1.7%; crypto up/down 14 / 14 +84% (2 wallets, t 0.7). No category has 30
filled markets except sports, so the category cells are descriptive only. The wallets' own late prices were positive
in economics (+44%, t 2.2, 27 markets) and tech (+21%, t 1.7), but copies there almost never fill (10% and 28% at
10 s, 3% and 16% at 60 s): those wallets trade thin markets where nobody else prints in the next 30 s.

### Price paid vs the wallet (late, filled copies)

Median +0.7 c/share at 10 s for taker entries (+1.0 c for maker entries), +0.9 / +1.0 c at 60 s, +0.9 / 0.0 c at
5 min; the mean is +0.3 to +2.2 c. At a 0.05 fee rate the fee is another 1.25 c/share at p = 0.5.

## Opportunities per day and net per trade

- First-buy entries of the 36 chosen wallets: about 9,100 a day (coverage-adjusted), most of them from 5 bots whose
  feed hit the 4,000-row cap (Flaznorp and similar). The 31 uncapped wallets alone: 887 / 483 / 504 / 499 / 487 entries
  on Sat 21 / Sun 22 / Mon 23 / Tue 24 / Wed 25 Nov: there is as much to copy at the weekend as on weekdays.
- Copyable after the delay: about 2,900 a day at 10 s, 2,000 at 60 s, 1,400 at 5 min (fill rates 31.5% / 21.6% /
  15.2% applied to all entries).
- Net per filled trade at about $7 (sized to 10 USD, capped by the shown size): -$0.73 at 10 s, -$0.78 at 60 s,
  -$0.18 at 5 min (late). At 5-20 USD scale it is the same return per dollar: -10% / -11% / -2%.
- Weekend vs weekdays (post-hoc breakdown, not a variant): d10 hold +7.1% on the weekend (88 fills, t 0.5) and
  -20.4% on weekdays (134 fills, t -1.8); d300 +24.6% (39, t 0.9) vs -16.0% (68, t -1.4). Noise of the same size as
  the effect; no claim.
- Markets of filled copies close a median 2.5 h after the entry (p25 1.1 h, p75 5.9 h), so capital turns over a few
  times a day; with a negative return that only loses faster.

## Capacity for an account of about 200 EUR

Zero: the expected value is negative or indistinguishable from zero at every delay. For scale only: at 10 s,
200 entries a day at $7-10 would put $1,400-2,000 a day through the market and, at the measured -10%, lose
$140-200 a day; at the upper end of the CI (+7%) it would make about $100-140 a day, which is why the sample cannot
exclude a small positive edge, but nothing in it points that way.

## Reaction time needed

Not the bottleneck. 10 s, 60 s and 5 min give the same answer within the noise; the 10 s copy is not better than
the 5-minute one (-10% vs -2%). A faster copier would pay closer to the wallet's price, but the wallet's own late
result (+13%, t 1.6, +0.1% without the 5 best markets) is the ceiling, and that ceiling is not distinguishable from
zero either. Sub-second copying would turn this into a race with the wallet's own follow-up orders and other bots.

## Live micro-test

Nothing here deserves one. No variant or subgroup met the pre-registered rule (late return > 0 with t >= 2 overall or
>= 3 in a subgroup, >= 50 markets, the same sign early, positive without the 5 best markets, t >= 1.5 by wallet).
Spending the 50-100 USD test account on copy trading would test noise with a negative expected value.

## Limitations

- **Survivorship in the pool (in favour of copying):** the leaderboards were read on 27 Nov and cover the late window;
  wallets that lost in 21-25 Nov are less likely to be on them. The negative late result is therefore conservative.
- **Selection by account-wide PnL**, not by category PnL (the API gives no per-category time series): a wallet chosen
  from the weather board may have made its early-window money in soccer (cf. ColdMath in NOTES.md).
- **Short late window:** five days, 704 sampled entries, 92-204 filled markets per delay; CIs are +-17 to +-25 points.
  A small positive edge (a few % of turnover) cannot be excluded; a large one can.
- **Sampling caps:** at most 4,000 BUY rows per wallet and window (5 wallets capped: their entries come only from the
  last part of a window) and at most 25 / 15 sampled entries per wallet: heavy bots weigh as much as occasional traders.
  One entry per (wallet, token): repeated adds into the same token were not copied.
- **Fill evidence is the next printed block within 30 s of the delay.** A copier who sends a marketable order may get
  a fill where no print shows one (raising the fill rate) and may pay more when the book is thin; the VWAP of a block
  is at or above its best ask, so filled prices are conservative. The wallet's own follow-up fills count as liquidity.
- **Exit:** MIRROR sees only SELL fills; merges, redeems and conversions are not seen as closes (treated as hold).
  Unresolved positions are marked at the last tape price.
- **Fees:** current category rates (since 20 Nov) for both windows; the early window charged most wallets more at the
  time, but that window is only used for selection.
- **Wallet type** comes from the early window's capped feeds compared on their common time span (deviation 2).

## Deviations from the protocol

1. Source 3 of the pool: the protocol said "every 0x address in `studies/wallets/*/*.json`"; those files hold 2,648
   addresses (counterparties inside tape extracts), not analysed wallets. Narrowed, before any outcome number, to the
   addresses in the READMEs plus each JSON file's own subject wallet (`wallet` / `account.wallet`). An earlier run of
   the selection script also matched 40-hex prefixes of transaction hashes; it was killed before it produced anything.
2. Wallet type: the full feed and the taker-only feed are each capped at the newest 4,000 rows, so for 5 busy wallets
   they covered different time spans and the first computation gave taker shares above 100%. Fixed by comparing the
   two feeds only on their common span (capped at 100%). Only the wallet-type breakdown changed (among the 35 wallets with
   late entries: 20 / 9 / 6 taker / maker / mixed before the fix, 16 / 11 / 8 after); headline variants did not.
3. The weekend / weekday split and the price-bucket split of the reference were added after the results (descriptive).

## Ideas, not tested

- Copy only the wallets' long-shot entries (wallet price under 0.20): the reference made +40.7% there in the late
  window (146 entries), but copies at 10 s lost 16.8% (40 fills). A test would need a new protocol and a wider window.
- Select by category-specific PnL rebuilt from fills (per-wallet `pmlab.wallet` over the early window) instead of the
  account-wide series, and require the wallet's early-window edge to be in the category it is copied in.
- A longer late window (4+ weeks) with all entries of fewer wallets, to tighten the CI to a few points.
- Copy with a resting limit order at the wallet's price instead of a taker order (fill only if a later print goes
  strictly through it), especially for maker entries.
