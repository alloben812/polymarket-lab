# Independent safety review of `pilot/exp_fav.py` (2026-11-27)

Reviewer: Claude, fresh context. I did not write the runner. Scope: `exp_fav.py` (sha256 `be5f29d4…489d7e`,
2,211 lines), the `smoke.py` helpers it imports (sha256 `30198080…ddeca`), `EXP-FAV.md`,
`verification-fav-2026-11-27.txt`, the rule in `docs/forward-tests.md` v1.0 ("Зацепка 3"), `AGENTS.md`, `NOTES.md`
(update of 2026-11-27 evening), and the SDK `polymarket-client==0.20.1` in `pilot/.venv` wherever the runner relies on it.
Nothing authenticated was sent. Only the pinned SDK and official endpoints were used. No commit, no push.

## Коротко для владельца (простым языком)

- **Вердикт: можно, после правок (GO WITH FIXES).** Деньги ограничены правильно: на одном пути код отправляет только
  покупку FAK на сумму не больше билета и по цене не выше 0,98. Повторов нет. Вторую копию программы запустить нельзя.
  Худший случай по конструкции около 30 USD плюс центы комиссии.
- **Что исправить до первого живого запуска.** Нашлись три небольшие ошибки в учёте ответа биржи (M1–M3). Из-за двух из
  них настоящая покупка в редком случае может не попасть в счёт проигрышей. Тогда стоп «2 проигрыша / 30 USD»
  перестаёт держать. Третья портит главный замер, проскальзывание. Каждая правка занимает несколько строк.
- **Что решить вам до запуска (M4).** На живом стакане правило сработало на дневном рынке HYPE «вверх или вниз», где
  «фаворит» на деле не фаворит: лучшая цена покупки 0,27, продажи 0,97. Правило купило бы его по 0,97 при шансах
  около половины. Добавить фильтр без новой версии правила нельзя. Нужно ваше решение: принять как есть или записать
  версию 1.1 с условием на спред.
- **Порядок.** По `docs/forward-tests.md` живая стадия идёт после бумажной. Живой запуск сейчас — ваше отдельное
  решение. Запишите его строкой в `HANDOFF.md`.
- **Где запускать.** Только на вашем Mac в Сербии, без VPN. Из облачной песочницы нельзя: там американский адрес,
  а для США Polymarket закрыт. Программа там и сама откажется.
- **Сколько класть на первую сессию.** Хватит 50–60 USD, как в таблице `forward-tests.md`, а не 200 EUR. Под риском
  по правилам всего 30 USD. Остальное на счёте защищено только ключом. Лучше торговать Session Key: он не может
  выводить деньги (`NOTES.md`).

## Verdict: GO WITH FIXES

The money path is narrow and well guarded. Exactly one line posts (`env.post` in `Session.send`, line 1107). It is
reached only through `Session.decide`, line 1050, and only after these steps, in order:
1. the technical checks (clock, book age, geoblock age; lines 1001-1015);
2. `check_caps` (halt file, STOP file, one decision per market, stop conditions, daily cap, worst-case exposure;
   lines 519-537), plus the market-minimum check;
3. signing hard-wired to `create_market_order(side="BUY", order_type="FAK", max_price=ask)` (line 669);
4. `guard_signed` on the signed object (BUY, FAK, not post-only, no expiration, the favourite's token,
   spend <= ticket, limit in [0.95, 0.98), implied price <= limit + 0.0001; lines 373-392);
5. a `decision` record written and fsynced **before** the post (line 1036).

The SDK does not retry `post_order`: only GETs go through `run_with_rate_limit_retry` (SDK `_internal/dispatch.py`).
Every exception after the post leaves the decision without an order record. `build_ledger` then books it as
`unknown` at the full ticket (line 484), so a crash, Ctrl+C or a timeout fails toward over-counting.

The worst-case arithmetic holds on the intended paths. Before each order, realised losses + open worst cost + the
new ticket must be <= 30.05 USD (line 535), and realised losses count gross losses, not net. So the sum of all losses
between two manual clears is at most about 30 USD plus fees. The case is 3 simultaneous positions that all lose, or
1 realised loss plus 2 open that lose; a third loss can still happen when positions overlap, but the total stays
under 30 USD. I could not construct a path to a price above 0.98, a SELL, a resting order type, a wrong token
(versus the chosen favourite), a second order on the same market, an hourly or 5m/15m Up/Down market, or a leaked key
or address.

Two classification gaps in `send` can book a real fill as unfilled or under-sized (M1, M2). That breaks the
property above, because the 2-loss / 30 USD stop and the exposure gate only see what the ledger holds. One reporting
bug corrupts the main measurement (M3). M4 is a rule question the owner must answer. Apply M1–M3, re-run the
selftest, record M4 and the live-before-paper decision, then the first live session is a GO.

## What I ran

| check | result |
|---|---|
| `cd pilot && .venv/bin/python -I exp_fav.py selftest` on the repository file (sha256 `be5f29d4…489d7e`) | **105 checks, ALL PASS, exit 0** (matches the author's report). Side effect: `FavOut` logs to `smoke.OUT`, so this run appended selftest lines to the existing `pilot/out/exp-fav-20261127.log` (see S9). |
| dry-run, byte-identical copy in a scratch folder, `run --hours 0.05`, public data, 35 polls | geoblock correctly says `blocked=True country=US` ("a live run would be refused here"); clock offset +0.53 s; universe: 145 markets ending in the next 26 h (dip 25, reach 25 ending 2026-11-28 05:00 UTC; above 44, between 36, between-tail 8, updown-daily 7 ending 17:00 UTC); assets BTC, ETH, SOL, XRP plus daily Up/Down on BNB, DOGE, HYPE; 0 rejected. No window was open (the first opens 2026-11-28 04:00 UTC), so no trigger, as expected. |
| same copy with only `WINDOW_S` widened to 30 h (scratch only), to exercise real books, signing and twins | 12 triggers across all six types, on real token ids, with tick 0.001 and 0.01. Offline signing with the throwaway key passed the guard (e.g. `10000000/10309270` at 0.97). From the 4th trigger on, the exposure gate refused with "open 30.00 + ticket 10 > 30". The paper twins were recorded 2.0-2.1 s later. One trigger exposed M4 (HYPE). |
| offline probes against `FakeEnv` (scratch copy) | M1 reproduced: an order answered `matched` with zero amounts is recorded `unfilled` although the trades list shows the fill; after a loss, `losses() == (0, 0)`, exposure 0, daily count 0. M2 reproduced: a `live` FAK whose cancel fails is booked as filled at 5 shares / 4.853 USD, the remainder is not counted, and the session does not stop. M3 reproduced: a `delayed` order whose trade printed at 0.96 is recorded with a fill price of 0.97 and 0.00 ticks. Payout mapping in `RealEnv.result` checked with fake SDK objects: payouts (0, 1) give the second outcome, (0.5, 0.5) give a split, and the SDK yields `Decimal` payouts in outcome-index order (`models/data/resolutions.py`, `models/gamma/market.py`: yes = `outcomes[0]` = `clobTokenIds[0]`). |

## Must fix

### M1. A success answer with zero amounts is recorded as "unfilled" even when the trades list shows the fill (lines 1143-1158)

```python
known = status == "matched" or (status.startswith("delayed->") and ...)
...
if known:
    shares = taking
    state = "filled" if shares > 0 else "unfilled"
```

The SDK turns empty `makingAmount`/`takingAmount` strings into `0` (`RawOrderResponse._parse_amounts`), so empty
amounts are a shape the API can return. When `status == "matched"` and `taking == 0`, the trades read just above is
ignored and the order is booked `unfilled`. An unfilled order:
- counts toward neither the daily cap nor the exposure (`filled_on`, `open_exposure`);
- is never late-checked;
- and if it loses, it is not a loss (`build_ledger`, line 494, needs `filled`/`unknown`).

Probe: one such order, then a loss gives `losses() == (0, 0)`. The same applies to a `delayed->MATCHED` final state
whose `size_matched` reads 0. `unfilled` should come only from a definite rejection or from a final order state with
nothing matched **and** an empty trades list.

Patch (replace lines 1145-1158):

```python
        final = status == "matched" or (status.startswith("delayed->") and extra.get("delayed_final", {}).get("final"))
        trades, trades_ok = [], False
        try:
            trades = [t for t in env.trades(token, t_d) if t["taker_order_id"] == oid or t["id"] in resp["trade_ids"]]
            trades_ok = True
        except Exception as e:  # noqa: BLE001
            extra["trades_error"] = scrub(type(e).__name__)
        shares_tr = sum((D(t["size"]) for t in trades), Decimal(0))
        if shares_tr > 0:                                  # the exchange's own trade rows win
            shares, state = shares_tr, "filled"
        elif final and taking > 0:
            shares, state = taking, "filled"
        elif final and status != "matched" and trades_ok:  # delayed -> final with nothing matched, no trade rows
            shares, state = Decimal(0), "unfilled"
        else:                                              # 'matched' with no amounts, 'live', or unreadable
            shares, state = None, "unknown"                # worst case until the late check
```

Add a selftest case: `post_mode="matched"` with `making = taking = 0` must give `fill_state == "unknown"` and an open
exposure of 10.

### M2. A FAK reported "live" whose cancel is not confirmed is booked at its partial fill; the rest can fill later uncounted (lines 1135-1142, 1155-1156)

If the answer is `live` and `cancel` fails or raises, `cancelled_resting_remainder=False` is recorded. If the trades
list already shows part of the fill, the trade is booked `filled` at that part (probe: 5 shares, 4.853 USD). The
remainder of the order can still rest on the book at up to 0.979 and fill later. It is then missing from the exposure
gate and from the loss stop, by up to one ticket. The session also keeps trading.

Patch, in the `elif status == "live":` branch after the cancel attempt:

```python
            if not ok:
                extra["resting_remainder_possible"] = True
                self.begin_stop("a FAK was reported resting and its cancel was not confirmed; check open orders by hand")
```

and, as the first branch of the classification in M1:

```python
        if status == "live" and not extra.get("cancelled_resting_remainder"):
            shares, state = (shares_tr or None), "unknown"   # worst case: the full ticket until resolution
        elif shares_tr > 0:
            ...                                              # M1 branches unchanged
```

`unknown` makes the ledger book the full ticket (line 501), and the late check after resolution sorts it out. Add a
selftest case with `env.cancel = lambda oid: False`.

### M3. Fill price of "delayed" orders is the order's limit, not the fill; response amounts outrank the exchange's trades (lines 1128-1134, 1159-1160; selftest line 1686-1688)

For `delayed`, `making = taking * st["price"]`, where `st["price"]` is `OpenOrder.price` from `get_order`: the
order's own price, i.e. the limit, which equals the ask. So every delayed fill is recorded at exactly the ask, at
0.00 ticks of slippage. Price improvement is invisible, and so are fills on several levels. `NOTES.md` records a taker
delay on crypto markets, so `delayed` may be the normal answer here. In that case the slippage distribution, which is
the reason this test spends money, comes out as a constant. The trade rows with their real legs are fetched and
stored, but `avg` ignores them whenever `taking > 0`. The selftest cannot catch this: `FakeEnv.order_state` returns
the fill price where the real API returns the limit.

Patch: compute the fill from the trade legs when there are any, keep the response figure separately, and never derive
a price from `get_order`:

```python
        legs = [lg for t in trades for lg in t["legs"]]
        leg_sh = sum((D(s) for p, s in legs), Decimal(0))
        avg_tr = (sum(D(p) * D(s) for p, s in legs) / leg_sh) if leg_sh > 0 else None
        avg_resp = (making / taking) if (taking > 0 and making > 0 and not status.startswith("delayed")) else None
        avg = avg_tr if avg_tr is not None else avg_resp
        # record both: fill_price_trades=S(avg_tr), fill_price_response=S(avg_resp); report uses fill_price (= avg)
```

In the delayed branch keep `taking = size_matched`, but do not compute `making` from `st["price"]`. Change
`FakeEnv.order_state` to return the limit price, and add a check that the delayed fill price equals the trade price.
If both sources exist and disagree by more than 0.0005, write it in the record (`price_sources_disagree=True`). This
is the first thing to look at in the first live report.

### M4. Owner decision: the "favourite" can be a coin flip in a wide, thin book (rule, not a code bug)

In the widened dry-run, the daily Up/Down market `hype-updown-1d-1795798800` triggered with "Up" as the favourite.
Its book was ask 0.97 x 1008, bid 0.27 x 6; the other token showed ask 0.73 x 6, bid 0.03 x 1008. That is mid 0.62
against 0.38, chosen only because of a 6-share bid. The rule would pay 0.97 for an outcome the book prices near a
coin flip. Two seconds later the ask was 0.59. The other 11 real triggers had spreads of 0.001-0.09.

That trigger was 20 h before the end, outside the real window. Whether thin daily Up/Down books (BNB, DOGE, HYPE)
look like this in their last hour is unknown. If they do, such trades lose about 10 USD half the time: they would
spend the 2-loss stop fast and contaminate the measurement.

The task and `forward-tests.md` v1.0 forbid adding filters, so this review does not ask the author to add one. The
owner must choose before the first live session:
- **(a)** accept v1.0 as is: the caps bound the damage;
- **(b)** write v1.1 of lead 3 with a condition such as "the favourite's best bid >= 0.90" or "spread <= 0.03", with a
  date and reason, per the file's own rule. In code it is one more test in `trigger()`, line 336:
  `if book.best_bid is None or book.best_bid < Decimal("0.90"): return False, "wide spread"`.

Every record already stores `best_bid` and both books, so the paper data can show the effect either way.

## Should fix

- **S1. The ledger lives in the checkout, the halt file in HOME (lines 108, 111, 506).** `pilot/out/` belongs to one
  copy of the repository. If a newer version is unpacked into another folder, the live ledger there starts empty.
  The exchange checks then still cover one-order-per-market (`account_traded`) and the day's count at start
  (`fills_today`). But the loss count, the open positions in the exposure gate and the day's own records are lost,
  and the 2-loss stop can restart from zero. `exp_bids.py` already keeps its lock outside `pilot/` for this reason.
  Fix: keep the live records under `~/.polymarket-pilot/exp-fav/`, or refuse `--live` when the local live ledger is
  empty while `list_account_trades()` shows taker BUYs of this account.
- **S2. `exp_bids.py` can run live on the same account at the same time (line 112).** Its lock is
  `exp_bids.live.lock` and exp_fav's is `exp_fav.lock`, so the two programs' caps do not see each other. Fix: in live
  mode, also try a non-blocking lock on `~/.polymarket-pilot/exp_bids.live.lock` and refuse if it is held. At the least,
  `EXP-FAV.md` should say "never run both live on one account".
- **S3. The unknown-fill checks could use the authoritative token balance (lines 1194-1210, 1245-1255).** After a
  failed post, `reconcile` and `late_reconcile` read only the trades list and the activity feed. Both can lag or
  filter wrongly, and an empty pair downgrades the order to `unfilled` (the loss is then not counted).
  `get_balance_allowance(asset_type="CONDITIONAL", token_id=token)` gives the shares actually held. Use it as a third
  source, and downgrade only if all three say nothing was bought. `late_reconcile` also never upgrades an `unknown`
  with trades to `filled` with its real cost. Write that record too, so the report can show the trade.
- **S4. Trades with status FAILED count as fills (lines 698-713).** `ClobTrade.status` can be `FAILED` (terminal,
  settlement failed). Skip FAILED rows in `trades()`, and record the trade status in the order record. Over-counting
  is conservative for the caps, but it misreports profit and loss.
- **S5. One failed GET /time blocks orders for 10 minutes (lines 829-843).** `offset=None` makes every poll a
  technical skip until the next scheduled check 600 s later, a sixth of a window. On failure, retry after 30 s.
  Same for the geoblock check after an exception (line 813), although orders there may continue on a pass younger
  than 60 min.
- **S6. The selftest does not exercise the real exchange adapter.** `FakeEnv` replaces every exchange method of
  `RealEnv`: post error classification (4xx versus 408/429/5xx), `result()` payout mapping, complement-leg conversion
  in `trades()`, the activity fee read, and the making/taking swap. Add offline tests of those methods with fake
  SDK objects, as in this review's probe. Add cases for M1-M3. "Three triggers in one poll -> three orders" also runs
  with zero latency. In reality the 2nd and 3rd book may be older than 1.5 s after the first post and its trades
  read, and get technical skips. That is safe, but worth a line in `EXP-FAV.md`.
- **S7. The ledger is re-read from all record files twice per poll (lines 921, 1017).** Universe records every
  20 min and near-miss records make the files grow by a few MB a day. After a week or two a poll may run late and
  cause technical skips. Cache the ledger and update it from the records the session writes.
- **S8. A split result keeps the position in the open exposure for ever (lines 441-443).** `won is None` after a
  split, so the position stays "open" for the gate. This is conservative. Book a split as resolved (loss = cost - 0.5
  x shares) so it neither blocks capacity nor hides a partial loss.
- **S9. The selftest appends to the real log (line 126).** `FavOut.log_path` uses `smoke.OUT`, which the selftest
  does not redirect, so every selftest writes into `pilot/out/exp-fav-<date>.log`, mixed with live session logs.
  Redirect it to the temp folder in `cmd_selftest`.
- **S10. Version the deviations.** The runner deviates from v1.0 in three ways: no retry after a FAK that did not
  fill (the doc allows retries while the ask stays in range), a stop at 2 losses / 30 USD (the doc: 3rd loss /
  -25 USD net), and a daily cap and exposure gate. Live before the paper stage also deviates. `EXP-FAV.md` states all
  of this honestly. By the doc's own rule and harness rule 4, it belongs in `docs/forward-tests.md` as v1.1 with a
  date and reason, and in `HANDOFF.md` as the owner's decision. `HANDOFF.md` (run `wf_781d8bc7-c9a`) also says the
  forward-tests file got NEEDS_WORK from its sceptic and is being revised. Confirm which version is frozen before the
  first live order, and put it in `RULE_SOURCE`.

## Residual risks (after the fixes)

- **Unverified until the Mac.** Live client creation, balance, closed-only and approvals; the real answer to a FAK
  BUY with `max_price` (matched or delayed, units of making/taking); `get_order` and `cancel`; the trades list `after`
  parameter; the fee read from the activity feed; neg-risk BUYs on "between" markets; latency from Serbia. The code
  fails toward `unknown` (worst case) on most of these, once M1-M3 are applied. Read the first live order's record
  field by field before leaving the program alone.
- **Economics.** One loss costs about 10.00 USD and wipes out 20-50 wins. This test measures execution
  (fill rate, price, fee, latency), not profitability. Weeks of trades are needed for the latter (`EXP-FAV.md`).
- **The window runs past `endDate` until the market closes** (line 238, per v1.0). After `endDate` the result of
  "above / between" markets is already determined, so an ask still at 0.95-0.98 then is suspect (adverse
  selection). The exchange usually stops accepting orders at the end, so the exposure is small. A v1.1 could cut the
  window at `endDate`.
- **Mac sleep.** macOS `time.monotonic` stops during sleep. The jump check (wall versus monotonic) catches the first
  poll after waking. The state and universe refreshes run on monotonic time, though, so `accepting/closed` can be up
  to 60 s stale after waking. The exchange rejects orders on a closed market, so no money is at risk. Keep
  `caffeinate`, the lid open and the charger connected, as the guide says.
- **Where it runs.** Only on the owner's Mac in Serbia, on its own connection. A VPN or proxy to another country, or
  this cloud sandbox (US IP), is forbidden by Polymarket's geoblock rules. Getting around it would break the terms and
  can freeze the account. The program refuses when either geoblock check says blocked. Do not try to defeat that.
- **Key and funds.** Only about 30 USD are at risk by design. Everything else on the account is protected only by
  the key file. Use a Session Key, which can trade but not withdraw (`NOTES.md`, evening update). Keep the file at
  mode 600. Fund the first session with about 50-60 USD (the doc's own figure for lead 3), not 200 EUR. Winnings are
  not claimed automatically: Portfolio -> Claim on polymarket.com.
- **Thin markets.** Besides M4, small-asset daily Up/Down books can carry liquidity-reward ladders on both sides
  (both tokens showed asks at 0.97 x 1008). Watch the `best_bid` and `other_book` fields in the first triggers.

## Files

- Reviewed: `pilot/exp_fav.py`, `pilot/smoke.py`, `pilot/EXP-FAV.md`, `pilot/verification-fav-2026-11-27.txt`,
  `docs/forward-tests.md` (lead 3), `AGENTS.md`, `NOTES.md`.
- Written: this file only. The selftest run appended to `pilot/out/exp-fav-20261127.log` (S9). The dry-run and probes
  ran on copies in the session scratch folder and wrote nothing into the repository.
