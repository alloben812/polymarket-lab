#!/usr/bin/env python3
"""Polymarket smoke test on the official Python SDK (polymarket-client==0.20.1).

Dry-run by default: nothing authenticated is sent and no order is posted.
Real requests only with --live. `roundtrip` also needs --yes-this-costs-money.

Subcommands
  auth       derive or create CLOB API credentials; show signer, wallet, wallet type,
             pUSD balance, allowances and trading approvals. Never prints secrets.
  place      ONE passive post-only BUY limit order of the market's minimum size, priced far
             below the best bid (cannot fill). Hard cap: notional <= 1 USD. GTD, expires by itself.
  status     open orders of this account.
  cancel     cancel the order(s) this script placed (ids from out/placed_orders.json).
  roundtrip  marketable BUY of at most 2 USD (fee included), then SELL of the shares received;
             prints fills, fees and the fee formula check.
  selftest   fully offline: throwaway key, offline signing, every cap and refusal.

Key: a file at $PM_KEY_FILE (default ~/.polymarket-pilot/key) holding one hex private key.
The script refuses to run if the file is readable or writable by group or others.
Wallet: $PM_WALLET = the account wallet address from the polymarket.com profile menu
(optional; without it the SDK uses the signer's Deposit Wallet).

Caps are constants below. There are no flags that change them.

Docs used (read 2026-11-27): https://docs.polymarket.com/getting-started/python.md,
https://docs.polymarket.com/trading/quickstart.md, https://docs.polymarket.com/trading/wallets-auth.md,
https://docs.polymarket.com/trading/place-orders.md, https://docs.polymarket.com/trading/manage-orders.md,
https://docs.polymarket.com/trading/fees.md, https://docs.polymarket.com/api-reference/geoblock.md.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import time
import urllib.request
from datetime import datetime, timezone
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from pathlib import Path

# ----------------------------------------------------------------------------- hard caps
SDK_VERSION_REQUIRED = "0.20.1"
MAX_PLACE_NOTIONAL_USD = Decimal("1.00")     # place: price * size, pUSD
MAX_ROUNDTRIP_SPEND_USD = Decimal("2.00")    # roundtrip BUY: spend + estimated taker fee, pUSD
PLACE_MAX_FRACTION_OF_BID = Decimal("0.5")   # place price <= 50% of best bid ...
PLACE_MIN_TICKS_BELOW_BID = 5                # ... and at least 5 ticks below it
PLACE_LIFETIME_S = 20 * 60                   # GTD: effective lifetime ~20 min (docs: now + 60 + N)
ROUNDTRIP_SHARE_BUFFER = Decimal("1.2")      # buy 20% above the minimum so the SELL is >= minimum
DEFAULT_MIN_SIZE = Decimal("5")
USDC_UNIT = Decimal(10) ** 6                 # pUSD has 6 decimals (concepts/pusd.md)

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
STATE = OUT / "placed_orders.json"
GEOBLOCK_URL = "https://polymarket.com/api/geoblock"


class Refusal(Exception):
    """A safety rule stopped the action. Exit code 2."""


# ----------------------------------------------------------------------------- output / log
class Out:
    """Prints and logs plain text. Every line passes through a redactor of known secrets."""

    def __init__(self) -> None:
        OUT.mkdir(parents=True, exist_ok=True)
        self.secrets: list[str] = []
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        self.log_path = OUT / f"smoke-{stamp}.log"

    def add_secret(self, s: str | None) -> None:
        if s and len(s) >= 8:
            self.secrets.append(s)
            if s.lower().startswith("0x"):
                self.secrets.append(s[2:])

    def _redact(self, text: str) -> str:
        for s in self.secrets:
            text = re.sub(re.escape(s), "<redacted>", text, flags=re.IGNORECASE)
        return text

    def __call__(self, text: str = "") -> None:
        text = self._redact(str(text))
        print(text)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(self.log_path, "a", encoding="utf-8") as f:
            for line in text.splitlines() or [""]:
                f.write(f"{ts} {line}\n")


out: Out


# ----------------------------------------------------------------------------- key file
def key_path() -> Path:
    return Path(os.environ.get("PM_KEY_FILE", "~/.polymarket-pilot/key")).expanduser()


def load_private_key() -> str:
    p = key_path()
    if not p.exists():
        raise Refusal(f"key file not found: {p}  (set PM_KEY_FILE or create it, see README)")
    st = os.stat(p)
    if not stat.S_ISREG(st.st_mode):
        raise Refusal(f"key file is not a regular file: {p}")
    if st.st_mode & 0o077:
        raise Refusal(
            f"key file {p} has mode {oct(st.st_mode & 0o777)}: readable/writable by group or "
            f"others. Run: chmod 600 '{p}'"
        )
    if hasattr(os, "getuid") and st.st_uid != os.getuid():
        raise Refusal(f"key file {p} is not owned by the current user")
    parent = os.stat(p.parent)
    if parent.st_mode & 0o022:
        raise Refusal(f"directory {p.parent} is writable by group or others. Run: chmod 700 '{p.parent}'")
    raw = p.read_text(encoding="utf-8").strip()
    hexpart = raw[2:] if raw.lower().startswith("0x") else raw
    if not re.fullmatch(r"[0-9a-fA-F]{64}", hexpart):
        raise Refusal(f"key file {p} must hold exactly one 32-byte hex private key (content not shown)")
    key = "0x" + hexpart.lower()
    out.add_secret(key)
    return key


def wallet_env() -> str | None:
    w = os.environ.get("PM_WALLET", "").strip()
    if not w:
        return None
    if not re.fullmatch(r"0x[0-9a-fA-F]{40}", w):
        raise Refusal("PM_WALLET must be a 0x... address of 40 hex characters")
    return w


def check_asset_id(s: str | None) -> str:
    if not s or not re.fullmatch(r"[0-9]{10,80}|0x[0-9a-fA-F]{1,64}", s):
        raise Refusal("--market must be an outcome token id / asset id (digits), e.g. from conn_check.py")
    return s


# ----------------------------------------------------------------------------- SDK
def sdk():
    import polymarket  # noqa: F401
    from polymarket.version import __version__ as v

    if v != SDK_VERSION_REQUIRED:
        raise Refusal(f"polymarket-client {v} installed, this script is pinned to {SDK_VERSION_REQUIRED}")
    return polymarket


def offline_client(private_key: str, wallet: str | None):
    """A SecureClient built without any network call and with dummy CLOB credentials.

    Uses internals of polymarket-client 0.20.1 (version is enforced). Good for building and
    signing orders; any authenticated request with it would be rejected by the server.
    """
    sdk()
    from eth_account import Account
    from polymarket import SecureClient
    from polymarket._internal.environment import get_environment_config
    from polymarket._internal.wallet import classify_account, derive_beacon_deposit_wallet_address
    from polymarket.environments import PRODUCTION
    from polymarket.models.clob.api_key import ApiKeyCreds

    config = get_environment_config(PRODUCTION)
    signer = Account.from_key(private_key)
    w = wallet or derive_beacon_deposit_wallet_address(signer.address, config.wallet_derivation)
    acct = classify_account(signer=signer.address, wallet=w, config=config.wallet_derivation)
    creds = ApiKeyCreds.model_validate(
        {"apiKey": "dry-run-not-a-key", "secret": "ZHJ5LXJ1bi1ub3QtYS1zZWNyZXQ=", "passphrase": "dry-run"}
    )
    return SecureClient._construct_for_wallet(  # noqa: SLF001
        signer=signer, wallet=w, wallet_type=acct.wallet_type, signer_type=acct.signer_type,
        environment=PRODUCTION, config=config, credentials=creds, api_key=None, logger=None,
        on_rate_limit_update=None,
    )


def live_client(private_key: str, wallet: str | None):
    sdk()
    from polymarket import SecureClient

    client = SecureClient.create(private_key=private_key, wallet=wallet)
    c = client.credentials
    for s in (getattr(c, "key", None), getattr(c, "secret", None), getattr(c, "passphrase", None)):
        out.add_secret(s)
    return client


def describe_identity(client) -> None:
    ctx = client._ctx  # noqa: SLF001
    out(f"  signer address : {client.signer}")
    out(f"  account wallet : {client.wallet}")
    out(f"  wallet type    : {client.wallet_type}   signer role: {ctx.signer_type}")
    if ctx.signer_type == "SESSION_KEY":
        out("  NOTE: PM_WALLET is not derived from this key, so the SDK treats the key as a Session Key.")
        out("        If you did not authorize a Session Key for this wallet, the key or PM_WALLET is wrong.")


def market_info(client, asset_id: str):
    ctx = client._ctx  # noqa: SLF001
    return ctx.order_metadata.resolve_market(ctx, token_id=asset_id)


def top_of_book(client, asset_id: str):
    book = client.get_order_book(asset_id=asset_id)
    best_bid = max((lv.price for lv in book.bids), default=None)
    best_ask = min((lv.price for lv in book.asks), default=None)
    ask_size = sum((lv.size for lv in book.asks if lv.price == best_ask), Decimal(0)) if best_ask else Decimal(0)
    return book, best_bid, best_ask, ask_size


def geoblock_or_refuse() -> None:
    req = urllib.request.Request(GEOBLOCK_URL, headers={"User-Agent": "pm-pilot-smoke/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            geo = json.loads(r.read().decode())
    except Exception as e:  # noqa: BLE001
        raise Refusal(f"geoblock check failed ({type(e).__name__}); not sending orders") from e
    out(f"  geoblock: blocked={geo.get('blocked')} country={geo.get('country')} (IP not shown)")
    if geo.get("blocked") is not False:
        raise Refusal("this IP is geoblocked for order placement; nothing was sent")


# ----------------------------------------------------------------------------- pure planning (caps)
def floor_tick(x: Decimal, tick: Decimal) -> Decimal:
    return (x / tick).to_integral_value(rounding=ROUND_FLOOR) * tick


def ceil_cents(x: Decimal) -> Decimal:
    return (x * 100).to_integral_value(rounding=ROUND_CEILING) / 100


def plan_passive_buy(best_bid, tick: Decimal, min_size) -> tuple[Decimal, Decimal]:
    size = Decimal(min_size) if min_size else DEFAULT_MIN_SIZE
    if best_bid is None:
        raise Refusal("the book has no bids; cannot price an order 'far below the best bid'")
    limit_by_cap = MAX_PLACE_NOTIONAL_USD / size
    limit_by_bid = min(best_bid * PLACE_MAX_FRACTION_OF_BID, best_bid - PLACE_MIN_TICKS_BELOW_BID * tick)
    if floor_tick(limit_by_cap, tick) < tick:
        raise Refusal(f"minimum size {size} even at one tick ({tick}) exceeds the 1 USD cap")
    price = floor_tick(min(limit_by_cap, limit_by_bid), tick)
    if price < tick:
        raise Refusal(
            f"best bid {best_bid} is too low to place {size} shares at <= 50% of the bid and "
            f">= {PLACE_MIN_TICKS_BELOW_BID} ticks below it; choose an outcome priced 0.10-0.90"
        )
    if price * size > MAX_PLACE_NOTIONAL_USD:
        raise Refusal(f"notional {price * size} > cap {MAX_PLACE_NOTIONAL_USD}")
    return price, size


def taker_fee(shares: Decimal, price: Decimal, rate: Decimal, exponent: Decimal = Decimal(1)) -> Decimal:
    """docs trading/fees.md: fee = C * feeRate * p * (1 - p); the SDK raises p(1-p) to `exponent`."""
    return shares * rate * (price * (1 - price)) ** exponent


def plan_roundtrip_buy(best_ask, ask_size, tick: Decimal, min_size, rate: Decimal, exponent: Decimal):
    if best_ask is None:
        raise Refusal("the book has no asks")
    msize = Decimal(min_size) if min_size else DEFAULT_MIN_SIZE
    shares = (msize * ROUNDTRIP_SHARE_BUFFER).quantize(Decimal("0.01"), rounding=ROUND_CEILING)
    amount = ceil_cents(shares * best_ask)
    fee = taker_fee(amount / best_ask, best_ask, rate, exponent)
    total = amount + fee
    if total > MAX_ROUNDTRIP_SPEND_USD:
        raise Refusal(
            f"{shares} shares at best ask {best_ask} cost {amount} + fee ~{fee:.4f} = {total:.4f} pUSD "
            f"> cap {MAX_ROUNDTRIP_SPEND_USD}; pick an outcome with ask <= ~0.30"
        )
    if ask_size < shares:
        raise Refusal(f"only {ask_size} shares at the best ask {best_ask}; need {shares}")
    return amount, best_ask, shares, fee


def guard_signed_buy(signed, cap: Decimal) -> Decimal:
    """Last check on the signed order itself: a BUY's maker amount is the pUSD it may spend."""
    if signed.side != "BUY":
        raise Refusal("internal: expected a BUY order")
    spend = Decimal(signed.maker_amount) / USDC_UNIT
    if spend > cap:
        raise Refusal(f"signed order would spend {spend} pUSD > cap {cap}; not posted")
    return spend


# ----------------------------------------------------------------------------- state
def load_state() -> list[dict]:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return []


def save_state(rows: list[dict]) -> None:
    STATE.write_text(json.dumps(rows, indent=2))


def show_order(signed) -> None:
    out(f"  signed order: side={signed.side} maker={signed.maker} signer={signed.signer}")
    out(f"    token={signed.token_id}")
    out(f"    maker_amount={signed.maker_amount} taker_amount={signed.taker_amount} "
        f"(base units, 1e6) sig_type={signed.signature_type} expiration={signed.expiration} "
        f"post_only={signed.post_only}")
    out(f"    signature: present, {len(signed.signature)} hex chars (not printed)")


# ----------------------------------------------------------------------------- commands
def cmd_auth(a) -> int:
    key = load_private_key()
    wallet = wallet_env()
    if not a.live:
        out("DRY-RUN auth: no request sent. Offline identity from the key:")
        describe_identity(offline_client(key, wallet))
        out("Re-run with --live to derive/create CLOB credentials and read balance and allowances.")
        return 0
    out("LIVE auth: deriving or creating CLOB API credentials (L1 signature, secrets never shown)")
    client = live_client(key, wallet)
    try:
        describe_identity(client)
        try:
            out(f"  closed-only mode: {client.get_closed_only_mode()}")
        except Exception as e:  # noqa: BLE001
            out(f"  closed-only mode: unavailable ({type(e).__name__})")
        ba = client.get_balance_allowance(asset_type="COLLATERAL")
        out(f"  collateral (pUSD) balance: {Decimal(ba.balance) / USDC_UNIT}")
        for spender, amt in ba.allowances.items():
            shown = "max" if amt >= 2**255 else str(Decimal(amt) / USDC_UNIT)
            out(f"  allowance -> {spender}: {shown}")
        try:
            st = client.get_trading_approvals_state()
            out(f"  trading approvals complete: {st.is_fully_approved}")
            if not st.is_fully_approved:
                out(f"  missing approvals: {st.missing}")
        except Exception as e:  # noqa: BLE001
            out(f"  trading approvals: unavailable ({type(e).__name__})")
        out("  API credentials: derived/created and held in memory only (not printed, not saved)")
    finally:
        client.close()
    return 0


def cmd_place(a) -> int:
    asset = check_asset_id(a.market)
    key = load_private_key()
    wallet = wallet_env()
    client = offline_client(key, wallet) if not a.live else None
    try:
        if a.live:
            geoblock_or_refuse()
            client = live_client(key, wallet)
        describe_identity(client)
        info = market_info(client, asset)
        book, bid, ask, _ = top_of_book(client, asset)
        out(f"  book: best bid {bid} / best ask {ask}  tick {info.tick_size}  min size {book.min_order_size} "
            f"neg_risk {info.neg_risk}")
        price, size = plan_passive_buy(bid, info.tick_size, book.min_order_size)
        out(f"  plan: BUY {size} @ {price} = {price * size} pUSD (cap {MAX_PLACE_NOTIONAL_USD}), post-only, "
            f"GTD ~{PLACE_LIFETIME_S // 60} min")
        expiration = int(time.time()) + 60 + PLACE_LIFETIME_S
        signed = client.create_limit_order(asset_id=asset, price=price, size=size, side="BUY",
                                           post_only=True, expiration=expiration)
        guard_signed_buy(signed, MAX_PLACE_NOTIONAL_USD)
        show_order(signed)
        if not a.live:
            out("DRY-RUN: order built and signed, NOT posted. Re-run with --live to post it.")
            return 0
        resp = client.post_order(signed)
        if not resp.ok:
            out(f"  REJECTED: {resp.code}: {resp.message}")
            return 1
        rows = load_state()
        rows.append({"order_id": resp.order_id, "asset_id": asset, "price": str(price), "size": str(size),
                     "placed_utc": datetime.now(timezone.utc).isoformat(), "status": str(resp.status)})
        save_state(rows)
        out(f"  POSTED: order_id={resp.order_id} status={resp.status} "
            f"making={resp.making_amount} taking={resp.taking_amount}")
        out("  Next: smoke.py status --live, then smoke.py cancel --live")
        return 0
    finally:
        if client is not None:
            client.close()


def cmd_status(a) -> int:
    key = load_private_key()
    wallet = wallet_env()
    mine = {r["order_id"] for r in load_state()}
    if not a.live:
        out(f"DRY-RUN status: would list open orders. Orders recorded by this script: {sorted(mine) or 'none'}")
        return 0
    client = live_client(key, wallet)
    try:
        describe_identity(client)
        n = 0
        for o in client.list_open_orders().iter_items():
            n += 1
            tag = "  <- placed by smoke.py" if o.id in mine else ""
            out(f"  {o.id} {o.side} {o.original_size} @ {o.price} matched {o.size_matched} "
                f"status {o.status} type {o.order_type} expires {o.expires_at}{tag}")
        out(f"  open orders (this API key): {n}")
        if client.wallet_type == "DEPOSIT_WALLET":
            m = sum(1 for _ in client.list_wallet_open_orders().iter_items())
            out(f"  open orders (whole Deposit Wallet, all signers): {m}")
    finally:
        client.close()
    return 0


def cmd_cancel(a) -> int:
    key = load_private_key()
    wallet = wallet_env()
    rows = load_state()
    ids = [r["order_id"] for r in rows if r.get("status") != "canceled"]
    if not ids:
        out("Nothing to cancel: no order placed by smoke.py is recorded in out/placed_orders.json")
        return 0
    if not a.live:
        out(f"DRY-RUN cancel: would cancel {ids}")
        return 0
    client = live_client(key, wallet)
    try:
        resp = client.cancel_orders(order_ids=ids)
        out(f"  canceled: {list(resp.canceled)}")
        out(f"  not canceled: {resp.not_canceled or '-'}")
        done = set(resp.canceled)
        for r in rows:
            if r["order_id"] in done:
                r["status"] = "canceled"
        save_state(rows)
    finally:
        client.close()
    return 0


def _conditional_balance(client, asset: str) -> Decimal:
    best = Decimal(0)
    for t in ("CONDITIONAL", "CONDITIONAL-V2"):
        try:
            b = Decimal(client.get_balance_allowance(asset_type=t, asset_id=asset).balance) / USDC_UNIT
            best = max(best, b)
        except Exception:  # noqa: BLE001
            pass
    return best


def cmd_roundtrip(a) -> int:
    asset = check_asset_id(a.market)
    if not (a.live and a.yes_this_costs_money):
        raise Refusal("roundtrip spends real money: it needs both --live and --yes-this-costs-money")
    key = load_private_key()
    wallet = wallet_env()
    geoblock_or_refuse()
    client = live_client(key, wallet)
    try:
        describe_identity(client)
        info = market_info(client, asset)
        rate, expo = info.fee_info.rate, info.fee_info.exponent
        book, bid, ask, ask_size = top_of_book(client, asset)
        out(f"  book: bid {bid} / ask {ask} (size {ask_size})  tick {info.tick_size}  min {book.min_order_size}  "
            f"fee rate {rate} exponent {expo}")
        amount, max_price, shares, fee_est = plan_roundtrip_buy(ask, ask_size, info.tick_size,
                                                                book.min_order_size, rate, expo)
        cash0 = Decimal(client.get_balance_allowance(asset_type="COLLATERAL").balance) / USDC_UNIT
        pos0 = _conditional_balance(client, asset)
        out(f"  before: pUSD {cash0}, shares {pos0}")
        out(f"  BUY plan: spend {amount} pUSD at <= {max_price} (~{shares} sh), fee est {fee_est:.5f}, "
            f"max_spend {MAX_ROUNDTRIP_SPEND_USD}")
        buy = client.create_market_order(asset_id=asset, side="BUY", amount=amount,
                                         max_spend=MAX_ROUNDTRIP_SPEND_USD, max_price=max_price,
                                         order_type="FAK")
        guard_signed_buy(buy, MAX_ROUNDTRIP_SPEND_USD)
        r1 = client.post_order(buy)
        if not r1.ok:
            out(f"  BUY REJECTED: {r1.code}: {r1.message}")
            return 1
        out(f"  BUY accepted: {r1.order_id} status {r1.status} making {r1.making_amount} taking {r1.taking_amount}")
        try:
            client.wait_for_order_fill_settlement(r1, timeout_s=120)
        except Exception as e:  # noqa: BLE001
            out(f"  settlement wait: {type(e).__name__}: {e}")
        time.sleep(3)
        cash1 = Decimal(client.get_balance_allowance(asset_type="COLLATERAL").balance) / USDC_UNIT
        pos1 = _conditional_balance(client, asset)
        got = (pos1 - pos0).quantize(Decimal("0.01"), rounding=ROUND_FLOOR)
        out(f"  after BUY: pUSD {cash1} (spent {cash0 - cash1}), shares {pos1} (+{pos1 - pos0})")
        r2 = None
        if got >= Decimal(book.min_order_size or DEFAULT_MIN_SIZE):
            _, bid2, _, _ = top_of_book(client, asset)
            min_price = max(info.tick_size, (bid2 or info.tick_size) - 2 * info.tick_size)
            sell = client.create_market_order(asset_id=asset, side="SELL", shares=got,
                                              min_price=min_price, order_type="FAK")
            r2 = client.post_order(sell)
            if r2.ok:
                out(f"  SELL accepted: {r2.order_id} status {r2.status} making {r2.making_amount} "
                    f"taking {r2.taking_amount}")
                try:
                    client.wait_for_order_fill_settlement(r2, timeout_s=120)
                except Exception as e:  # noqa: BLE001
                    out(f"  settlement wait: {type(e).__name__}: {e}")
            else:
                out(f"  SELL REJECTED: {r2.code}: {r2.message}")
        else:
            out(f"  received {got} shares < minimum {book.min_order_size}; SELL skipped, position kept")
        time.sleep(3)
        cash2 = Decimal(client.get_balance_allowance(asset_type="COLLATERAL").balance) / USDC_UNIT
        pos2 = _conditional_balance(client, asset)
        out(f"  final: pUSD {cash2} (net {cash2 - cash0}), shares {pos2}")
        # fills and fee check
        ids = {r1.order_id} | ({r2.order_id} if r2 is not None and r2.ok else set())
        trade_ids = set(r1.trade_ids) | (set(r2.trade_ids) if r2 is not None and r2.ok else set())
        fee_formula = Decimal(0)
        notional = {"BUY": Decimal(0), "SELL": Decimal(0)}
        for t in client.list_account_trades(asset_id=asset).iter_items():
            if t.id not in trade_ids and t.taker_order_id not in ids:
                continue
            f = taker_fee(t.size, t.price, rate, expo) if t.trader_side == "TAKER" else Decimal(0)
            fee_formula += f
            notional[t.side] += t.size * t.price
            out(f"  fill {t.id}: {t.side} {t.size} @ {t.price} {t.trader_side} fee_rate_bps {t.fee_rate_bps} "
                f"status {t.status} formula fee {f:.5f}")
        observed = (cash0 - cash2) - (notional["BUY"] - notional["SELL"])
        out(f"  fee by formula (rate x p x (1-p) x shares, summed): {fee_formula:.5f} pUSD")
        out(f"  fee observed from balances (cash out - net notional): {observed:.5f} pUSD"
            f"{'  (valid only if all shares were sold)' if pos2 > pos0 else ''}")
        out(f"  difference: {observed - fee_formula:+.5f} pUSD (docs: fees rounded to 5 decimals)")
    finally:
        client.close()
    return 0


def cmd_selftest(a) -> int:
    """Offline checks with a throwaway key. Network is disabled by a dead proxy for this process."""
    import tempfile

    for var in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
        os.environ[var] = "http://127.0.0.1:9"
    os.environ.pop("NO_PROXY", None)
    os.environ.pop("no_proxy", None)
    from eth_account import Account
    from eth_account.messages import encode_typed_data
    from polymarket._internal.actions.orders.market_data import MarketInfo, PlatformFeeInfo
    from polymarket._internal.actions.orders.orders import create_unsigned_order
    from polymarket._internal.actions.orders.typed_data import build_order_typed_data
    from polymarket._internal.actions.orders.limit import _build_limit_order_draft, validate_limit_order_params

    ok = True

    def check(name, fn, expect_refusal):
        nonlocal ok
        try:
            r = fn()
            passed = not expect_refusal
            out(f"  [{'PASS' if passed else 'FAIL'}] {name}: returned {r}")
        except Refusal as e:
            passed = expect_refusal
            out(f"  [{'PASS' if passed else 'FAIL'}] {name}: refused: {e}")
        ok &= passed

    tmp = Path(tempfile.mkdtemp(prefix="pm-selftest-"))
    os.chmod(tmp, 0o700)
    acct = Account.create()
    kf = tmp / "key"
    kf.write_text(acct.key.hex())
    old = os.environ.get("PM_KEY_FILE")
    os.environ["PM_KEY_FILE"] = str(kf)
    out("selftest: throwaway key generated in memory; written to a temp file only for the checks")
    try:
        os.chmod(kf, 0o644)
        check("key file mode 0644 refused", load_private_key, True)
        os.chmod(kf, 0o640)
        check("key file mode 0640 refused", load_private_key, True)
        os.environ["PM_KEY_FILE"] = str(tmp / "missing")
        check("missing key file refused", load_private_key, True)
        bad = tmp / "bad"
        bad.write_text("not a key")
        os.chmod(bad, 0o600)
        os.environ["PM_KEY_FILE"] = str(bad)
        check("malformed key refused (content not shown)", load_private_key, True)
        os.environ["PM_KEY_FILE"] = str(kf)
        os.chmod(kf, 0o600)
        check("key file mode 0600 accepted", lambda: "loaded (not shown)" if load_private_key() else None, False)
        key = load_private_key()

        t = Decimal("0.01")
        check("place plan, bid 0.40 tick 0.01 min 5", lambda: plan_passive_buy(Decimal("0.40"), t, 5), False)
        check("place plan, bid 0.90 -> price capped by 1 USD", lambda: plan_passive_buy(Decimal("0.90"), t, 5), False)
        check("place plan, min size 100 -> price <= 0.01", lambda: plan_passive_buy(Decimal("0.40"), t, 100), False)
        check("place plan, bid 0.05 refused (not far enough)", lambda: plan_passive_buy(Decimal("0.05"), t, 5), True)
        check("place plan, min size 200 refused (1 USD cap)", lambda: plan_passive_buy(Decimal("0.40"), t, 200), True)
        check("place plan, empty bid side refused", lambda: plan_passive_buy(None, t, 5), True)
        r, e = Decimal("0.05"), Decimal(1)
        check("roundtrip plan, ask 0.30", lambda: plan_roundtrip_buy(Decimal("0.30"), Decimal(100), t, 5, r, e), False)
        check("roundtrip plan, ask 0.40 refused (> 2 USD)",
              lambda: plan_roundtrip_buy(Decimal("0.40"), Decimal(100), t, 5, r, e), True)
        check("roundtrip plan, thin ask refused",
              lambda: plan_roundtrip_buy(Decimal("0.20"), Decimal(2), t, 5, r, e), True)
        ns = argparse.Namespace(market="123456789012345", live=False, yes_this_costs_money=False)
        check("roundtrip without --live refused", lambda: cmd_roundtrip(ns), True)
        ns2 = argparse.Namespace(market="123456789012345", live=True, yes_this_costs_money=False)
        check("roundtrip --live without --yes-this-costs-money refused", lambda: cmd_roundtrip(ns2), True)
        check("bad --market refused", lambda: check_asset_id("drop table"), True)

        # offline signing through the SDK
        client = offline_client(key, None)
        try:
            describe_identity(client)
            asset = "71321045679252212594626385532706912750332728571942532289631379312455583992563"
            cond = "0x" + "ab" * 32
            info = MarketInfo(fee_info=PlatformFeeInfo(rate=r, exponent=e), neg_risk=False,
                              tick_size=t, token_ids=frozenset({asset}))
            ctx = client._ctx  # noqa: SLF001
            ctx.order_metadata._conditions.set(asset, cond)  # noqa: SLF001
            ctx.order_metadata._markets.set(cond, info)  # noqa: SLF001
            price, size = plan_passive_buy(Decimal("0.40"), t, 5)
            exp = int(time.time()) + 60 + PLACE_LIFETIME_S
            signed = client.create_limit_order(asset_id=asset, price=price, size=size, side="BUY",
                                               post_only=True, expiration=exp)
            show_order(signed)
            check("signed passive BUY within 1 USD", lambda: guard_signed_buy(signed, MAX_PLACE_NOTIONAL_USD), False)
            big = client.create_limit_order(asset_id=asset, price=Decimal("0.30"), size=Decimal(5), side="BUY")
            check("signed BUY 5 @ 0.30 = 1.5 USD blocked by final guard",
                  lambda: guard_signed_buy(big, MAX_PLACE_NOTIONAL_USD), True)
            # signature recovers to the signer (same typed data the SDK signs)
            params = validate_limit_order_params(asset_id=asset, price=price, size=size, side="BUY")
            draft = _build_limit_order_draft(ctx, params, price=price, metadata=info)
            unsigned = create_unsigned_order(draft, wallet=ctx.wallet, wallet_type=ctx.wallet_type)
            typed = build_order_typed_data(unsigned)
            sig = ctx.signer.sign_typed_data(full_message=typed).signature
            rec = Account.recover_message(encode_typed_data(full_message=typed), signature=sig)
            check("EIP-712 order signature recovers to the signer",
                  lambda: rec if rec == ctx.signer.address else (_ for _ in ()).throw(Refusal("mismatch")),
                  False)
        finally:
            client.close()
        leaked = key[2:] in out.log_path.read_text().lower()
        check("private key absent from the log file",
              lambda: "absent" if not leaked else (_ for _ in ()).throw(Refusal("KEY FOUND IN LOG")), False)
    finally:
        if old is None:
            os.environ.pop("PM_KEY_FILE", None)
        else:
            os.environ["PM_KEY_FILE"] = old
        for f in tmp.iterdir():
            f.unlink()
        tmp.rmdir()
    out(f"selftest: {'ALL PASS' if ok else 'FAILURES'}")
    return 0 if ok else 1


def main(argv=None) -> int:
    global out
    out = Out()
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("command", choices=["auth", "place", "status", "cancel", "roundtrip", "selftest"])
    p.add_argument("--market", help="outcome token id (asset id), e.g. printed by conn_check.py")
    p.add_argument("--live", action="store_true", help="send real requests (default: dry-run)")
    p.add_argument("--yes-this-costs-money", action="store_true", help="required for roundtrip")
    a = p.parse_args(argv)
    out(f"=== smoke.py {a.command} {'LIVE' if a.live else 'dry-run'} "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    try:
        return {"auth": cmd_auth, "place": cmd_place, "status": cmd_status, "cancel": cmd_cancel,
                "roundtrip": cmd_roundtrip, "selftest": cmd_selftest}[a.command](a)
    except Refusal as e:
        out(f"REFUSED: {e}")
        return 2
    except Exception as e:  # noqa: BLE001
        out(f"ERROR: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
