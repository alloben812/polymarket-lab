# Independent safety review of `pilot/exp_bids.py` (2026-11-27)

Reviewer: Claude (fresh context, did not write the runner). Scope: `exp_bids.py` (sha256 `7e31103e…a4713`, 1,276 lines),
the helpers it uses in `smoke.py` (sha256 `30198080…ddeca`), `EXPERIMENTS.md`, `experiments/{pairs,tails,late-tail}.json`,
`verification-exp-2026-11-27.txt`, and the SDK `polymarket-client==0.20.1` in `pilot/.venv` where the runner relies on it.
No existing file was changed. Selftest, dry-run and probes ran on a byte-identical copy in a scratch folder, so
nothing was appended to `pilot/out/`.

## Verdict: GO WITH FIXES

The first live session (pairs config, `--max-windows 2`, one instance, Mac awake) is within its stated caps on every
path I could construct. Only one code line posts (`env.post`, line 567). It is reached only through `place_one`,
which runs the STOP and cap check (`check_order_caps`, line 537) and the final guard on the signed order
(`guard_signed`, line 552). Signing is hard-wired to `side="BUY", post_only=True` with an expiration (line 332), and the
guard checks BUY, post-only, GTD, the token and spend <= min(2.50, planned) on the signed object. `RealEnv.post` calls
`SecureClient.post_order` directly. That path does not retry and does not run the SDK's automatic on-chain approval
(that only happens in `place_*_order`, SDK `_internal/actions/orders/place.py`). So the same order cannot be sent twice,
and the runner cannot send a market order, a SELL or a non-GTD order.

The worst case for two pairs windows is 8.00 pUSD spent on shares, if the losing leg fills in both windows. The
three must-fix items below cover the cases where the caps or the ledger stop holding: an unchecked cancel, two
instances, and late events after a sleep or clock jump. Each patch is small. Apply them before the first live run,
or at least M1 and M2, and run the selftest again.

## Must fix

### M1. Cancel results are not checked, and fills can be read while the order is still live, so the ledger undercounts (lines 589-596, 690-699, 598-608, 638-666)

`on_cancel` sets `rec.cancelled = True` even when the exchange cancelled nothing. `env.cancel` returns only
`canceled`. `not_canceled` (order id -> reason) is dropped, and the log line then says "nothing open (filled or
expired)". `begin_stop` marks every id as cancelled the same way. The window is then finalised at end + 20 s
(line 455), and the fill read there becomes final: `cost = size_matched * avg`. If the order is still `LIVE` at that
moment, its later fills are never counted in the day ledger.

When this happens: the cancel fails transiently, or the 60-second GTD rule from the docs does not hold in practice
(EXPERIMENTS.md says expiry at window close is "не подтверждено"). If the exchange expires at the signed time, the
pairs order lives until +330 s, which is after the finalise at +320 s. For late-tail it lives until +365 s, also
after +320 s.

Probe B (fake exchange: cancel returns nothing, fill read shows `LIVE` with 1 of 5 shares matched): the ledger
records filled 0.80 and open 0, while 4.00 is still exposed.

Patch:

```python
# near the constants
OPEN_STATUSES = {"LIVE", "DELAYED", "OPEN", "UNMATCHED"}   # anything not terminal

# RealEnv.cancel: return what was really cancelled; callers compare ids
    def cancel(self, ids):
        if not self.live or not ids:
            return []
        r = self.c.cancel_orders(order_ids=ids)
        if r.not_canceled:
            out(f"    not cancelled: {dict(r.not_canceled)}")
        return list(r.canceled)

# on_cancel
            done = set(self.env.cancel([rec.order_id]))
            rec.cancelled = rec.order_id in done
            if not rec.cancelled:
                out(f"    cancel {rec.level.label} {rec.outcome}: NOT confirmed; counted as fully filled until final")

# begin_stop / interrupt: mark only ids in the returned set
            done = set(self.env.cancel(ids))
            ... if r.order_id in done: r.cancelled = True

# on_finalize, first lines after `if w.done: return` (wait until the signed expiration, not 60 s before it):
        latest = max((r.signed_expiration or 0) for r in w.orders) if w.orders else 0
        if self.env.now() < latest + 10:
            self.push(latest + 10, "finalize", w)
            return

# write_order, inside `if rec.status == "posted" and fill is not None:`
            if str(fill["status"]).upper().split(".")[-1] in OPEN_STATUSES:
                cost = rec.price * rec.size          # still open: worst case stays in the ledger
                end_status = f"{fill['status']} (open at finalise; counted as fully filled)"
```

The finalise then starts 20 s later for pairs (+340 s instead of +320 s) and 55 s later for late-tail.

### M2. Two live instances break the per-window cap and race the day cap (lines 742-789, 418-426)

`w.resting` exists only in memory, per session. Two live sessions with the same config both trade the same slug.
Probe A: two pairs instances put 8.00 pUSD into one window (cap 5.00). The day ledger reads the other session's
`placed` lines, but read-then-write is not atomic, so two sessions can both pass at 14.00 and both post. A second
checkout of `pilot/` (another `out/`) does not see the other ledger at all. EXPERIMENTS.md only asks the owner not
to run two sessions at once; the code does not stop it.

Patch (top of `cmd_run`, live only; the lock is held for the life of the process and released on exit or kill):

```python
import fcntl
LOCK_FILE = Path("~/.polymarket-pilot/exp_bids.live.lock").expanduser()   # outside pilot/: covers every checkout

    if a.live:
        LOCK_FILE.parent.mkdir(mode=0o700, exist_ok=True)
        a._lock = open(LOCK_FILE, "w")
        try:
            fcntl.flock(a._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Refusal("another live exp_bids.py session is running; one live session at a time") from None
```

### M3. Late events after a sleep or clock jump are posted, and the final guard has no upper bound on expiration (lines 494-498, 546-552, 288-297)

`run()` handles overdue events at once and in order. `on_place` never checks that it is still the scheduled
second. After the Mac sleeps (for example with the lid closed: `caffeinate -i` does not prevent that) or after a
forward clock jump, the session signs and posts for windows that are half over or already over. Probe D: after a
20-minute sleep, 2 orders were posted for a window that had ended 607 s earlier. The expiration is then
`now + 185` (effective about now + 125 s), long after `cancel_at`. The post-only rule and the cross check at
line 533 usually stop the losing side, so the money at risk is small. The orders still break the experiment's
design, and nothing bounds them. Probe K: `guard_signed` also accepts an order that expires in 2033.

Patch:

```python
MAX_PLACE_LAG_S = 5

# on_place, after the `self.stopping` check
        lag = self.env.now() - (w.start + lv.place_offset)
        if lag > MAX_PLACE_LAG_S:
            rec = OrderRec(uuid.uuid4().hex[:16], lv, lv.outcome, "", lv.price, lv.size)
            return self.skip(w, rec, f"{lag:.0f} s late (sleep or clock jump): not placed")

# place_one, before signing
        cancel_at = w.start + lv.cancel_offset
        if now + MIN_RESTING_S > cancel_at:
            return self.skip(w, rec, "too close to its cancel second")

# guard_signed(signed, token, planned, live, window_end): new last check
    if int(signed.expiration) > window_end + GTD_SECURITY_S + 10:
        raise Refusal("internal: signed expiration runs past the window end; not posted")
# call site: guard_signed(signed, rec.token, notional, self.live, w.end)

# parse_config: reject levels whose minimum SDK expiry runs past the window end
        if place + SDK_MIN_EXPIRATION_S + EXPIRATION_MARGIN_S - GTD_SECURITY_S > dur_s + 10:
            raise Refusal(f"config: level {i}: placed too late; its order would outlive the window")
```

late-tail (effective expiry +305 s, signed +365 s = end + 65) still passes. A level with `place_before_end_s: 20`
is accepted today, and its order would live 105 s past the window end (probe C). This patch rejects it.

## Should fix

| # | Lines | Finding | Proposed change |
| - | - | - | - |
| S1 | 566-574, 335-341 | The CLOB answers most rejections with HTTP 4xx. The SDK raises `RequestRejectedError` for these (`clients/_transport.py:420`), so they never reach the `r.ok == False` branch. Probe E: a 400 "order crosses book" was recorded as `post-error`, counted as 2.00 filled per leg, and printed as "POST ERROR" instead of the "REJECTED" line that EXPERIMENTS.md tells the owner to send. This is safe (over-counts), but it misreports, and a bad first setup (signature type, allowance) uses up the day's budget. | `except RequestRejectedError as e: if 400 <= e.status < 500 and e.status != 429:` treat as rejected (cost 0, `code=e.code`); keep `post-error` for `TransportError`, 5xx, 429 and `UnexpectedResponseError`. |
| S2 | 566-574 | After a timeout or 5xx, the order may be resting, but it has no `order_id`. STOP, Ctrl+C and the cancel at +270 s cannot reach it. It lives until GTD (pairs: +270 s if the docs are right). Its fills are never read, and the report shows it as "without fill data". No retry happens, so it cannot be sent twice. | After `post-error`, call `list_open_orders()` for that token once, match on price, size and expiration, adopt the id and schedule the cancel. Or call `cancel_all()` at session end when any post-error happened. |
| S3 | 557, 231-234 | `order_id` is held only in memory until the window is finalised. After a crash or kill, no file has the ids of resting orders, so neither the owner nor a later tool can cancel or reconcile them by id. | Append a `{"type":"posted","key":…,"order_id":…}` line right after a successful post. |
| S4 | 231-248, 251-268 | The ledger trusts the files. A torn or corrupt `placed` line is dropped silently (probe G: 3 orders and 6.00 open are seen as 1 order and 2.00). Moved, deleted or separate-checkout files reset the day cap to zero (probe H). There is no `fsync`. | Live mode: `os.fsync` after each `placed` line. `read_records` raises `Refusal` on an undecodable line in a live file instead of skipping it. At live start, also add today's maker BUY fills from `list_account_trades(after=<UTC midnight>)` and take the maximum of the file ledger and the exchange. |
| S5 | 569, 551, 581 | Exception and server messages go into `reason` in the records **unredacted**. The redactor in `smoke.Out` covers only printed lines. Probe F: an exception text with the wallet address appears in `out/exp-*.jsonl` (the log line was redacted). The SDK messages I read do not carry an address, so this is unlikely, but the records file promises "never a wallet address". | `rec.reason = out._redact(f"{type(e).__name__}: {e}")` at all three places. In the same way, redact `message` from rejected orders. |
| S6 | smoke.py 216-225 | The geoblock check uses `urllib`, which on macOS also reads the **system** proxy settings. The SDK uses `httpx`, which reads only environment variables. With a VPN or proxy app that sets the system proxy, the check and the orders can leave from different IPs. The check also runs only once per session. | Run the geoblock GET through the same `httpx` settings (`httpx.get(GEOBLOCK_URL, timeout=15)`), and repeat it at each window's `prepare`. |
| S7 | 308-309, 436-443 | No clock check. The slug, the place and cancel times, the expiration and the UTC day all come from `time.time()`. A clock off by tens of seconds places orders before the window opens, or breaks the 3-minute minimum expiry. | At start, compare `time.time()` with the `Date` header of a CLOB response. Refuse to start if the clock is more than 2 s off. |
| S8 | — | No dead-man switch. When the process is killed, orders rest until GTD, up to 270 s for pairs. SDK 0.20.1 has `send_order_heartbeat`: once armed, the server cancels all orders of the API key about 10 s after the heartbeats stop (SDK docstring, `clients/secure.py:1946`). | Optional: arm the heartbeat for live sessions and send one every 5 s from the event loop. The trade-off: the server cancels everything for this API key, and arming cannot be undone. |
| S9 | 853-862 | In the report, the day line `net` leaves out the cost of filled but unresolved orders, while `cost` includes it. The `rej` column misses the S1 cases. | Show unresolved cost in its own column, or count it in `net` as cost with payout 0 and a flag. |
| S10 | late-tail.json | With late-tail, the effective expiry is +305 s, which is 5 s past the window end. If the cancel at +295 s fails, the bid rests into the post-close, when most outcomes are already known. | `place_before_end_s: 125`, or accept and document it. |
| S11 | 946-1238 | The selftest does not test everything it claims. (a) "day: 299 sent, a 'both' level (2 legs) refused" runs while the STOP file exists (written at line 1051), so it passes because of STOP. Its output says so: `refused: STOP file present`. (b) "STOP file mid-session" writes STOP **before** the session starts (line 1190), so the stop-while-resting cancel path is never asserted. (c) `FakeEnv.sign` ignores the computed expiration and uses wall-clock + 600 (line 904), so the expiry logic is untested. (d) `post` always succeeds, `cancel` always cancels, `fills` and `result` never fail. The rejected branch (581-587), the unconfirmed cancel, the fill-lookup failure and the 20-minute finalise timeout never run. (e) "records hold no address" is trivially true, because the fake never produces exception text. (f) `RealEnv` is never exercised: market mapping, fills parsing and result mapping run only in the dry-run, or not at all (fills). | Move `STOP_FILE.write_text` below the 299 check. Write STOP from inside a fake `sleep` after the first post, and assert `env.cancelled`. Assert `signed.expiration == max(...)`. Add fakes for a rejection, an empty cancel, a fill exception and a never-resolving result (probes B, E, I, J in this review are templates). |

Also checked, no change needed:
- The 15.00 day cap counts fills plus worst-case open orders, and a cancelled zero-fill order frees its budget. So
  daily exposure can turn over many times, but cost actually filled stays <= 15.00 per UTC day, plus at most one
  window across midnight, by design.
- `post-error` orders and orders whose fill lookup failed count as fully filled (probe I).
- An unresolved result waits at most 20 minutes (probe J: the session ended 1,205 s after the window end).
- `--max-windows` is limited to 1-96 (`cmd_run`), and no other path builds a `Session`.

## Accounting check

- Outcome mapping: the SDK builds `outcomes.yes` from gamma `outcomes[0]` and `clobTokenIds[0]`
  (`models/gamma/market.py:525-570`). `Resolution.payouts` is the pair in outcome-index order, divided by 1e6
  (`models/data/resolutions.py`). The runner maps index 0 to `yes.label`, so index 0 = "Up" for these markets. I
  checked this against gamma for the dry-run windows below: token ids and results match. `choose()` does not depend
  on the labels: it reads the mid of `labels[0]`'s own token.
- Signs: `payout = filled` if our outcome won, else 0; `pnl = payout - cost`. The selftest late-tail case gives
  +24.50 for 25 shares at 0.02 that won, and pairs gives -2.00 for a filled loser. Both are correct.
- Fill rate = orders with fills > 0 / placed orders with known fill data. `post-error`, `dry-run` and failed lookups
  are left out of the denominator and listed as "without fill data". Rejections that arrived as `RequestRejectedError`
  are wrongly in that group (S1).
- Payout is before redemption. The runner does not redeem, as EXPERIMENTS.md says.

## Verified by running (sandbox, 2026-11-27, US IP, no key, no account; nothing authenticated sent)

All runs used a byte-identical copy (same sha256) in a scratch folder, with `PM_KEY_FILE` pointing to a missing file
(throwaway in-memory key) and `python -I`.

1. **Selftest** `exp_bids.py selftest`: `selftest: ALL PASS`, exit 0, 59 PASS lines. Line 27 of its output shows the
   S11(a) defect: `day: 299 sent, a 'both' level (2 legs) refused: refused: STOP file present`.
2. **Dry-run, pairs, 2 real windows** `run --config experiments/pairs.json --max-windows 2`, 18:47-19:00:37 UTC:
   - geoblock `blocked=True country=US` -> "would refuse a live run here" (correct here).
   - `btc-updown-5m-1795805400` (18:50): DRY BUY 5 Up @ 0.40 (book 0.53/0.54) and 5 Down @ 0.40 (0.46/0.47), signed
     expiration start + 330 s, cancel at + 270 s, NOT posted. Result **Up**.
   - `btc-updown-5m-1795805700` (18:55): Up book 0.44/0.45, Down 0.55/0.56. Result **Down**.
   - Token ids in the records equal gamma `clobTokenIds[0]` (Up) and `[1]` (Down) for both markets. Raw
     `get_resolutions`: 1795805400 `resolved (1, 0)` at 18:55:46, 1795805700 `resolved (0, 1)` at 19:00:22, so the
     index-to-label mapping is correct. Gamma lagged: at 19:00:37, right after the runner recorded Down, gamma still
     showed Up 0.73. Then Down 0.995, then closed `["1","0"]` for the first market. A multi-id `get_resolutions` call
     once omitted a just-resolved row. The runner treats that as "not yet" and retries, which is fine.
   - `grep -oE '0x[0-9a-fA-F]{40}\b'` on the records: 0 hits. `report --dry-run`: 4 placed, 4 "without fill data",
     results `{'Up': 1, 'Down': 1}`.
3. **Market keeps accepting orders after the window end** (gamma, public): `btc-updown-5m-1795805700` showed
   `closed False, acceptingOrders True` at 19:02:18, 2 min 18 s after its end. The 18:50 market closed at 18:55:46,
   46 s after its end. So any order that outlives its window (M1, M3, S10) can be filled after the outcome is known,
   which in practice means on the losing side.
4. **Probes** (fake exchange, real SDK signing, no network). Results:

| Probe | Scenario | Result |
| - | - | - |
| A | two live pairs instances, same window | 8.00 pUSD resting in one window (cap 5.00) -> M2 |
| B | cancel returns nothing; fill read shows LIVE 1/5 | ledger filled 0.80, open 0 while 4.00 is exposed -> M1 |
| C | effective GTD expiry | pairs +270 s (end +300); late-tail +305 s; `place_before_end_s: 20` accepted, effective end + 105 s -> M3/S10 |
| D | 20-minute sleep, then resume | 2 orders posted for a window that ended 607 s earlier -> M3 |
| E | HTTP 400 "order crosses book" | recorded `post-error`, 4.00 counted as filled (true cost 0) -> S1 |
| F | exception text containing the wallet address | address present in records, redacted in log -> S5 |
| G | torn `placed` line between two good ones | ledger sees 1 order / 2.00 instead of 3 / 6.00 -> S4 |
| H | record files gone | ledger (0, 0, 0) -> S4 |
| I | fill lookup raises | 4.00 kept as filled (safe) |
| J | result never resolves | session ends 1,205 s after the window end (bounded) |
| K | signed order expiring in 2033 | passes `guard_signed` -> M3 |

Not verifiable here: `post_order`, `cancel_orders` (including the shape of `not_canceled`), `get_order` statuses
after cancel or expiry, `list_account_trades` maker fills, the balance call, and whether the 60-second GTD rule holds
in practice. All of these run for the first time on the owner's Mac.

## Residual risks for the owner before the first live run

- **Losing leg fills.** pairs is built to show adverse selection. Expect the losing leg to fill often:
  about -2.00 pUSD per window, -4.00 to -8.00 for a two-window session. That is within the caps.
- **Untested live paths.** Placing, cancelling and reading fills have never run against the real exchange. Watch
  the first window by hand: after `POSTED`, check the order on polymarket.com; at +270 s, check that it is gone.
  If it is not, cancel it on the site.
- **Orders that survive the window.** The market keeps accepting orders after the window ends (verified above). An
  order that survives its cancel can fill against sellers of the losing side. The only thing bounding it is the GTD
  rule from the docs (expires 60 s before the signed time), and that is not yet confirmed live.
- **Ctrl+C and kill.** Ctrl+C cancels this session's orders. `kill -9`, a crash or a network drop leaves them until
  GTD expiry, at most +270 s into the window for pairs. Keep the Mac awake with the lid open, one live session at
  a time, VPN off.
- **Redemption.** Winnings are not redeemed by the script, and `payout` in the report is before redemption.
