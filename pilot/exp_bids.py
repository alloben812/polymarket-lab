#!/usr/bin/env python3
"""Live micro-experiments with resting post-only BUY bids on Polymarket crypto up/down windows.

Official Python SDK only (polymarket-client==0.20.1, enforced through smoke.py). Dry-run by default:
orders are planned and signed locally, nothing authenticated is sent. Real orders only with --live.

Subcommands
  run       --config experiments/<name>.json [--live] [--max-windows N]
            For each coming window of the config's asset and duration: at the configured second,
            read the public book and mid, choose the outcome (both / trailing / leading), sign a
            post-only GTD BUY limit order and (with --live) post it; cancel it at the configured
            second before the window end; after the window resolves, read the order's fills and
            the official result and write one JSON line per order and per window.
  report    [files...] [--dry-run]   per-level and per-day summary of the JSONL records.
  selftest  offline: throwaway key, fake clock and fake exchange, every cap and refusal.

Hard caps (constants below, no flag or config key changes them):
  only post-only BUY limit orders (GTD); per order price*size <= 2.50 pUSD; per window <= 5.00 pUSD;
  filled (plus still-open worst case) per UTC day <= 15.00 pUSD; <= 300 orders per UTC day;
  STOP file checked before every order; geoblock check before the first order of a live session;
  live start refused if the pUSD balance is below the worst-case resting notional of one window;
  final guard on every signed order's spend and expiration; --max-windows default 12, at most 96;
  one live session at a time (lock file); a level is not placed later than 5 s after its second
  (sleep, clock jump) or too close to its cancel second; a cancel counts only when the exchange
  confirms it, every order's state is read until it is no longer live (cancelled again at the
  window end if needed), and an order not known closed counts as fully filled.

Records: out/exp-<name>-<YYYYMMDD>.jsonl (live) or .dryrun.jsonl. They hold token ids, order ids,
prices and results; never a key, an API secret or a wallet address.

Docs used (read 2026-11-27): https://docs.polymarket.com/trading/place-orders.md (GTD: expires one
minute before the stated expiration; expiration >= now + 3 min; post-only),
https://docs.polymarket.com/trading/manage-orders.md, https://docs.polymarket.com/concepts/resolution.md,
https://docs.polymarket.com/trading/positions/manage.md (redeem), https://docs.polymarket.com/trading/fees.md.
"""
from __future__ import annotations

import argparse
import fcntl
import glob
import heapq
import json
import os
import re
import sys
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # smoke.py sits next to this file (python -I)
import smoke  # noqa: E402
from smoke import Refusal  # noqa: E402

# ----------------------------------------------------------------------------- hard caps
MAX_ORDER_NOTIONAL = Decimal("2.50")      # price * size of one order, pUSD
MAX_WINDOW_NOTIONAL = Decimal("5.00")     # all orders of one window together, pUSD
MAX_DAY_FILLED = Decimal("15.00")         # filled + still-open worst case, per UTC day, pUSD
MAX_DAY_ORDERS = 300                      # orders sent per UTC day (all experiments)
DEFAULT_MAX_WINDOWS = 12
HARD_MAX_WINDOWS = 96
GTD_SECURITY_S = 60                       # docs: GTD orders expire 60 s before the stated expiration
SDK_MIN_EXPIRATION_S = 180                # docs + SDK: expiration >= now + 3 min
EXPIRATION_MARGIN_S = 5
MIN_RESTING_S = 10                        # a level must rest at least this long
FINALIZE_FIRST_S = 20                     # first look for result/fills this long after the window end
FINALIZE_EVERY_S = 15
FINALIZE_TIMEOUT_S = 20 * 60
PREPARE_LEAD_S = 40
MAX_PLACE_LAG_S = 5                       # later than this after its second (sleep, clock jump): not placed
MAX_EXPIRY_PAST_END_S = 10                # effective GTD expiry may run at most this far past the window end
CANCEL_RETRY_S = 5                        # an unconfirmed cancel is tried again this often ...
CANCEL_RETRIES = 6                        # ... this many times; then again at the window end and at finalise
CLOSE_CHECK_S = 2                         # this long after the window end: confirm none of its orders is live
TERMINAL_STATUSES = {"MATCHED", "INVALID", "EXPIRED"}   # and every CANCELED*; anything else counts as live
ASSETS = ("btc", "eth", "sol", "xrp", "doge", "hype")
DURATIONS = {"5m": 300, "15m": 900}
OUTCOME_RULES = ("both", "trailing", "leading")
LEVEL_KEYS = {"label", "outcome", "price", "size", "place_after_start_s", "place_before_end_s",
              "expire_before_end_s"}
CONFIG_KEYS = {"name", "asset", "duration", "levels", "note"}

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "out"                                  # selftest points these to a temp dir
STOP_FILE = Path("~/.polymarket-pilot/STOP").expanduser()
LOCK_FILE = Path("~/.polymarket-pilot/exp_bids.live.lock").expanduser()   # outside pilot/: every checkout
ADDRESS_RE = re.compile(r"(?<![0-9a-fA-F])0x[0-9a-fA-F]{40}(?![0-9a-fA-F])")

out: smoke.Out


def scrub(text) -> str:
    """Text bound for a record or the log: known secrets redacted and no 40-hex address left."""
    return ADDRESS_RE.sub("<address>", out._redact(str(text)))  # noqa: SLF001


def order_closed(status) -> bool:
    """True only for a terminal order status; unknown or missing statuses count as live."""
    s = str(status or "").strip().upper().split(".")[-1]
    return s in TERMINAL_STATUSES or s.startswith("CANCELED") or s.startswith("CANCELLED")


def acquire_live_lock(path: Path):
    """Exclusive lock held for the life of the process (released on exit, crash or kill)."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    f = open(path, "a")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        f.close()
        raise Refusal(f"another live exp_bids.py session is running (lock {path}); "
                      f"one live session at a time") from None
    return f


class ExpOut(smoke.Out):
    def __init__(self) -> None:
        super().__init__()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        self.log_path = smoke.OUT / f"exp-{stamp}.log"


def utc(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def day_of(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


def D(x) -> Decimal:
    return x if isinstance(x, Decimal) else Decimal(str(x))


# ----------------------------------------------------------------------------- config
@dataclass
class Level:
    idx: int
    label: str
    outcome: str
    price: Decimal
    size: Decimal
    place_offset: int        # seconds after the window start
    cancel_offset: int       # seconds after the window start (= duration - expire_before_end_s)

    @property
    def notional(self) -> Decimal:
        return self.price * self.size

    @property
    def n_orders(self) -> int:
        return 2 if self.outcome == "both" else 1


@dataclass
class Config:
    name: str
    asset: str
    duration: str
    dur_s: int
    levels: list[Level]

    @property
    def window_notional(self) -> Decimal:
        return sum((lv.notional * lv.n_orders for lv in self.levels), Decimal(0))


def _dec(v, what: str, places: int) -> Decimal:
    if isinstance(v, bool) or not isinstance(v, (int, str, float)):
        raise Refusal(f"config: {what} must be a number")
    try:
        d = Decimal(str(v))
    except InvalidOperation as e:
        raise Refusal(f"config: {what} is not a number: {v!r}") from e
    if not d.is_finite() or d != d.quantize(Decimal(1).scaleb(-places)):
        raise Refusal(f"config: {what} must have at most {places} decimals: {v!r}")
    return d


def _int(v, what: str) -> int:
    if isinstance(v, bool) or not isinstance(v, int):
        raise Refusal(f"config: {what} must be an integer number of seconds")
    return v


def parse_config(obj: dict) -> Config:
    if not isinstance(obj, dict):
        raise Refusal("config: top level must be a JSON object")
    extra = set(obj) - CONFIG_KEYS
    if extra:
        raise Refusal(f"config: unknown keys {sorted(extra)} (caps cannot be set in a config)")
    name = obj.get("name")
    if not isinstance(name, str) or not name.replace("-", "").replace("_", "").isalnum() or len(name) > 40:
        raise Refusal("config: name must be 1-40 letters, digits, '-' or '_'")
    asset = obj.get("asset")
    if asset not in ASSETS:
        raise Refusal(f"config: asset must be one of {ASSETS}")
    duration = obj.get("duration")
    if duration not in DURATIONS:
        raise Refusal(f"config: duration must be one of {tuple(DURATIONS)}")
    dur_s = DURATIONS[duration]
    raw_levels = obj.get("levels")
    if not isinstance(raw_levels, list) or not raw_levels:
        raise Refusal("config: levels must be a non-empty list")
    levels = []
    for i, lv in enumerate(raw_levels):
        if not isinstance(lv, dict):
            raise Refusal(f"config: level {i} must be an object")
        extra = set(lv) - LEVEL_KEYS
        if extra:
            raise Refusal(f"config: level {i}: unknown keys {sorted(extra)}")
        rule = lv.get("outcome")
        if rule not in OUTCOME_RULES:
            raise Refusal(f"config: level {i}: outcome must be one of {OUTCOME_RULES} (orders are always BUY)")
        price = _dec(lv.get("price"), f"level {i} price", 2)
        if not (Decimal("0.01") <= price <= Decimal("0.99")):
            raise Refusal(f"config: level {i}: price must be 0.01-0.99")
        size = _dec(lv.get("size"), f"level {i} size", 2)
        if size <= 0:
            raise Refusal(f"config: level {i}: size must be positive (shares)")
        has_a, has_b = "place_after_start_s" in lv, "place_before_end_s" in lv
        if has_a == has_b:
            raise Refusal(f"config: level {i}: give exactly one of place_after_start_s / place_before_end_s")
        place = _int(lv["place_after_start_s"], "place_after_start_s") if has_a else \
            dur_s - _int(lv["place_before_end_s"], "place_before_end_s")
        if "expire_before_end_s" not in lv:
            raise Refusal(f"config: level {i}: expire_before_end_s is required")
        cancel = dur_s - _int(lv["expire_before_end_s"], "expire_before_end_s")
        if not (0 <= place < dur_s) or not (0 < cancel <= dur_s):
            raise Refusal(f"config: level {i}: placement and expiry must fall inside the window")
        if cancel - place < MIN_RESTING_S:
            raise Refusal(f"config: level {i}: the order would rest {cancel - place} s (< {MIN_RESTING_S} s)")
        if place + SDK_MIN_EXPIRATION_S + EXPIRATION_MARGIN_S - GTD_SECURITY_S > dur_s + MAX_EXPIRY_PAST_END_S:
            raise Refusal(f"config: level {i}: placed too late; the minimum expiry (now + "
                          f"{SDK_MIN_EXPIRATION_S} s) would let the order outlive the window by more than "
                          f"{MAX_EXPIRY_PAST_END_S} s")
        if price * size > MAX_ORDER_NOTIONAL:
            raise Refusal(f"config: level {i}: {size} x {price} = {price * size} pUSD > per-order cap "
                          f"{MAX_ORDER_NOTIONAL}")
        label = lv.get("label") or f"L{i}-{rule}-{price}"
        if not isinstance(label, str) or len(label) > 40:
            raise Refusal(f"config: level {i}: label must be a short string")
        levels.append(Level(i, label, rule, price, size, place, cancel))
    if len({lv.label for lv in levels}) != len(levels):
        raise Refusal("config: level labels must be unique")
    cfg = Config(name, asset, duration, dur_s, levels)
    if cfg.window_notional > MAX_WINDOW_NOTIONAL:
        raise Refusal(f"config: one window would rest {cfg.window_notional} pUSD > per-window cap "
                      f"{MAX_WINDOW_NOTIONAL}")
    return cfg


def load_config(path: str) -> Config:
    p = Path(path)
    if not p.exists():
        raise Refusal(f"config not found: {p}")
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise Refusal(f"config {p} is not valid JSON: {e}") from e
    return parse_config(obj)


# ----------------------------------------------------------------------------- records / ledger
def records_path(name: str, day: str, live: bool) -> Path:
    suffix = ".jsonl" if live else ".dryrun.jsonl"
    return OUT_DIR / f"exp-{name}-{day.replace('-', '')}{suffix}"


def append_record(path: Path, rec: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")


def read_records(paths) -> list[dict]:
    rows = []
    for p in paths:
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    return rows


def ledger(day: str, live: bool, session: str) -> tuple[int, Decimal, Decimal]:
    """(orders sent today, filled cost today, notional of orders sent today and not finalized).

    Live: every live record file (all experiments, all sessions). Dry-run: this session only.
    An order sent but never finalized (crash, Ctrl+C) counts as fully filled: worst case.
    """
    pattern = "exp-*.jsonl" if live else "exp-*.dryrun.jsonl"
    paths = [p for p in glob.glob(str(OUT_DIR / pattern)) if live != p.endswith(".dryrun.jsonl")]
    rows = read_records(paths)
    if not live:
        rows = [r for r in rows if r.get("session") == session]
    placed = {r["key"]: D(r["notional"]) for r in rows if r.get("type") == "placed" and r.get("day") == day}
    final = {r["key"]: r for r in rows if r.get("type") == "order" and r.get("key") in placed}
    filled = Decimal(0)
    for k, r in final.items():
        filled += D(r["cost"]) if r.get("cost") is not None else placed[k]
    open_ = sum((n for k, n in placed.items() if k not in final), Decimal(0))
    return len(placed), filled, open_


def check_order_caps(notional: Decimal, window_resting: Decimal, day_counts: tuple[int, Decimal, Decimal],
                     legs: int = 1) -> None:
    """Every cap that applies before an order (or `legs` equal orders) is sent. Raises Refusal."""
    if STOP_FILE.exists():
        raise Refusal(f"STOP file present ({STOP_FILE}): no new orders")
    if notional > MAX_ORDER_NOTIONAL:
        raise Refusal(f"order notional {notional} > per-order cap {MAX_ORDER_NOTIONAL}")
    add = notional * legs
    if window_resting + add > MAX_WINDOW_NOTIONAL:
        raise Refusal(f"window resting {window_resting} + {add} > per-window cap {MAX_WINDOW_NOTIONAL}")
    n, filled, open_ = day_counts
    if n + legs > MAX_DAY_ORDERS:
        raise Refusal(f"{n} orders already sent today (UTC); +{legs} > cap {MAX_DAY_ORDERS}")
    if filled + open_ + add > MAX_DAY_FILLED:
        raise Refusal(f"today filled {filled} + still open {open_} + {add} > daily cap {MAX_DAY_FILLED}")


def guard_signed(signed, token: str, planned: Decimal, live: bool, window_end: int, expiration: int) -> Decimal:
    """Final check on the signed order itself (same rule as smoke.py, plus shape and expiry checks)."""
    spend = smoke.guard_signed_buy(signed, min(MAX_ORDER_NOTIONAL, planned))
    if not signed.post_only:
        raise Refusal("internal: signed order is not post-only; not posted")
    if str(signed.token_id) != str(token):
        raise Refusal("internal: signed order token differs from the planned token; not posted")
    if int(signed.expiration) <= 0 or str(signed.order_type) != "GTD":
        raise Refusal("internal: signed order is not GTD; not posted")
    if int(signed.expiration) != int(expiration):
        raise Refusal("internal: signed expiration differs from the planned one; not posted")
    if int(signed.expiration) > window_end + GTD_SECURITY_S + MAX_EXPIRY_PAST_END_S:
        raise Refusal("internal: signed expiration runs past the window end; not posted")
    return spend


# ----------------------------------------------------------------------------- exchange adapters
class RealEnv:
    """Wraps an SDK SecureClient (offline client in dry-run, live client with --live)."""

    def __init__(self, client, live: bool):
        self.c = client
        self.live = live

    def now(self) -> float:
        return time.time()

    def sleep(self, s: float) -> None:
        time.sleep(max(0.0, s))

    def market(self, slug: str) -> dict:
        m = self.c.get_market(slug=slug)
        return {"condition_id": m.condition_id, "accepting": bool(m.state.accepting_orders),
                "closed": bool(m.state.closed),
                "tokens": {m.outcomes.yes.label: str(m.outcomes.yes.token_id),
                           m.outcomes.no.label: str(m.outcomes.no.token_id)},
                "index": {m.outcomes.yes.label: 0, m.outcomes.no.label: 1}}

    def book(self, token: str) -> dict:
        info = smoke.market_info(self.c, token)
        book, bid, ask, _ = smoke.top_of_book(self.c, token)
        return {"bid": bid, "ask": ask, "min_size": D(book.min_order_size or smoke.DEFAULT_MIN_SIZE),
                "tick": D(info.tick_size)}

    def mid(self, token: str) -> Decimal:
        return D(self.c.get_midpoint(asset_id=token))

    def sign(self, token: str, price: Decimal, size: Decimal, expiration: int):
        return self.c.create_limit_order(asset_id=token, price=price, size=size, side="BUY",
                                         post_only=True, expiration=expiration)

    def post(self, signed) -> dict:
        if not self.live:
            raise Refusal("internal: post called in dry-run")
        from polymarket.errors import RequestRejectedError
        try:
            r = self.c.post_order(signed)
        except RequestRejectedError as e:
            # a definite 4xx answer: the order was not placed. 408/429 and 5xx stay unknown (re-raised:
            # the caller counts them as fully filled, worst case)
            if 400 <= int(e.status) < 500 and int(e.status) not in (408, 429):
                return {"ok": False, "code": str(e.code or f"HTTP {e.status}"), "message": str(e)}
            raise
        if r.ok:
            return {"ok": True, "order_id": r.order_id, "status": str(r.status)}
        return {"ok": False, "code": str(getattr(r, "code", "")), "message": str(getattr(r, "message", ""))}

    def cancel(self, ids: list[str]) -> list[str]:
        """Ids the exchange confirms as cancelled; everything else counts as not cancelled."""
        if not self.live or not ids:
            return []
        r = self.c.cancel_orders(order_ids=ids)
        if r.not_canceled:
            out(f"    not cancelled by the exchange: {scrub(dict(r.not_canceled))}")
        return [str(i) for i in r.canceled]

    def order_state(self, order_id: str) -> dict:
        o = self.c.get_order(order_id=order_id)
        return {"status": str(o.status), "size_matched": D(o.size_matched)}

    def fills(self, order_id: str, token: str) -> dict:
        o = self.c.get_order(order_id=order_id)
        matched = D(o.size_matched)
        shares, value = Decimal(0), Decimal(0)
        seen = 0
        for t in self.c.list_account_trades(asset_id=token).iter_items():
            seen += 1
            if seen > 2000:
                break
            if t.status == "FAILED":
                continue
            for mo in t.maker_orders:
                if mo.order_id == order_id:
                    shares += D(mo.matched_amount)
                    value += D(mo.matched_amount) * D(mo.price)
            if t.taker_order_id == order_id:          # cannot happen for post-only; recorded if it does
                shares += D(t.size)
                value += D(t.size) * D(t.price)
        avg = (value / shares) if shares > 0 else None
        return {"status": str(o.status), "size_matched": matched, "trade_shares": shares, "avg_price": avg}

    def balance(self) -> Decimal:
        return Decimal(self.c.get_balance_allowance(asset_type="COLLATERAL").balance) / smoke.USDC_UNIT

    def result(self, condition_id: str, labels_by_index: dict[int, str]) -> str | None:
        for r in self.c.get_resolutions(condition_ids=[condition_id]):
            if str(r.status) == "resolved" and r.payouts:
                p0, p1 = r.payouts
                if p0 == 1 and p1 == 0:
                    return labels_by_index[0]
                if p1 == 1 and p0 == 0:
                    return labels_by_index[1]
                return f"split {p0}/{p1}"
        return None


# ----------------------------------------------------------------------------- session engine
@dataclass
class OrderRec:
    key: str
    level: Level
    outcome: str
    token: str
    price: Decimal
    size: Decimal
    status: str = "planned"
    reason: str = ""
    order_id: str | None = None
    signed_expiration: int | None = None
    placed_at: float | None = None
    cancel_at: float | None = None
    cancelled: bool = False          # the exchange confirmed the cancel
    closed: bool = False             # the exchange's order state is terminal (no longer live)
    last_state: str = ""
    cancel_tries: int = 0
    mid_up: Decimal | None = None
    bid: Decimal | None = None
    ask: Decimal | None = None


@dataclass
class Window:
    start: int
    end: int
    slug: str
    market: dict | None = None
    orders: list[OrderRec] = field(default_factory=list)
    resting: Decimal = Decimal(0)
    skipped_reason: str = ""
    done: bool = False


class Session:
    def __init__(self, cfg: Config, env, live: bool, max_windows: int):
        self.cfg, self.env, self.live, self.max_windows = cfg, env, live, max_windows
        self.session = uuid.uuid4().hex[:12]
        self.events: list = []
        self.seq = 0
        self.stopping = False
        self.geo_checked = False
        self.windows: list[Window] = []

    # -- plumbing
    def push(self, t: float, kind: str, *payload) -> None:
        self.seq += 1
        heapq.heappush(self.events, (t, self.seq, kind, payload))

    def path(self, ts: float) -> Path:
        return records_path(self.cfg.name, day_of(ts), self.live)

    def first_window_start(self) -> int:
        d = self.cfg.dur_s
        first_place = min(lv.place_offset for lv in self.cfg.levels)
        now = self.env.now()
        s = int(now // d) * d
        while s + first_place < now + 10:
            s += d
        return s

    def plan(self) -> None:
        s0 = self.first_window_start()
        for i in range(self.max_windows):
            s = s0 + i * self.cfg.dur_s
            w = Window(s, s + self.cfg.dur_s, f"{self.cfg.asset}-updown-{self.cfg.duration}-{s}")
            self.windows.append(w)
            first = min(lv.place_offset for lv in self.cfg.levels)
            self.push(max(self.env.now(), s + first - PREPARE_LEAD_S), "prepare", w)
            for lv in sorted(self.cfg.levels, key=lambda x: x.place_offset):
                self.push(s + lv.place_offset, "place", w, lv)
            self.push(w.end + CLOSE_CHECK_S, "close", w)
            self.push(w.end + FINALIZE_FIRST_S, "finalize", w)
        out(f"  plan: {self.max_windows} windows from {utc(s0)} ({self.windows[0].slug}), "
            f"worst-case resting per window {self.cfg.window_notional} pUSD")

    # -- event handlers
    def on_prepare(self, w: Window) -> None:
        try:
            w.market = self.env.market(w.slug)
        except Exception as e:  # noqa: BLE001
            w.skipped_reason = f"market lookup failed: {type(e).__name__}"
            out(f"  {w.slug}: {w.skipped_reason}")
            return
        if not w.market["accepting"] or w.market["closed"]:
            w.skipped_reason = "market not accepting orders"
        out(f"  {w.slug}: market found, accepting={w.market['accepting']}"
            f"{'' if not w.skipped_reason else ' -> window skipped'}")

    def choose(self, w: Window, lv: Level) -> tuple[list[str], Decimal | None, str]:
        labels = list(w.market["tokens"])            # [Up, Down]
        up = labels[0]
        try:
            mid_up = self.env.mid(w.market["tokens"][up])
        except Exception as e:  # noqa: BLE001
            mid_up = None
            if lv.outcome != "both":
                return [], None, f"mid unavailable ({type(e).__name__})"
        if lv.outcome == "both":
            return labels, mid_up, ""
        if mid_up == Decimal("0.5"):
            return [], mid_up, "mid exactly 0.50: no trailing/leading outcome"
        leading = up if mid_up > Decimal("0.5") else labels[1]
        trailing = labels[1] if leading == up else up
        return [trailing if lv.outcome == "trailing" else leading], mid_up, ""

    def skip(self, w: Window, rec: OrderRec, reason: str) -> None:
        rec.status, rec.reason = "skipped", reason
        w.orders.append(rec)
        out(f"    skip {rec.level.label} {rec.outcome}: {reason}")

    def on_place(self, w: Window, lv: Level) -> None:
        if w.market is None or w.skipped_reason:
            return
        if self.stopping:
            return
        lag = self.env.now() - (w.start + lv.place_offset)
        if lag > MAX_PLACE_LAG_S:
            rec = OrderRec(uuid.uuid4().hex[:16], lv, lv.outcome, "", lv.price, lv.size)
            return self.skip(w, rec, f"{lag:.0f} s after its placement second (sleep or clock jump): not placed")
        outcomes, mid_up, why = self.choose(w, lv)
        if not outcomes:
            rec = OrderRec(uuid.uuid4().hex[:16], lv, lv.outcome, "", lv.price, lv.size, mid_up=mid_up)
            self.skip(w, rec, why)
            return
        recs = [OrderRec(uuid.uuid4().hex[:16], lv, oc, w.market["tokens"][oc], lv.price, lv.size, mid_up=mid_up)
                for oc in outcomes]
        if len(recs) > 1:                         # "both": all legs fit the caps, or none is sent
            try:
                check_order_caps(lv.notional, w.resting,
                                 ledger(day_of(self.env.now()), self.live, self.session), legs=len(recs))
            except Refusal as e:
                for rec in recs:
                    self.skip(w, rec, f"both legs together: {e}")
                if "STOP" in str(e) or "today" in str(e):
                    self.begin_stop(str(e))
                return
        for rec in recs:
            self.place_one(w, rec)
            if self.stopping:
                return

    def place_one(self, w: Window, rec: OrderRec) -> None:
        env, lv = self.env, rec.level
        try:
            bk = env.book(rec.token)
        except Exception as e:  # noqa: BLE001
            return self.skip(w, rec, f"book unavailable ({type(e).__name__})")
        now = env.now()                           # after the book read: timing checks use the fresh clock
        rec.bid, rec.ask = bk["bid"], bk["ask"]
        lag = now - (w.start + lv.place_offset)
        if lag > MAX_PLACE_LAG_S:
            return self.skip(w, rec, f"{lag:.0f} s after its placement second (sleep or clock jump): not placed")
        cancel_at = w.start + lv.cancel_offset
        if now + MIN_RESTING_S > cancel_at:
            return self.skip(w, rec, f"too close to its cancel second ({cancel_at - now:.0f} s left)")
        expiration = max(cancel_at + GTD_SECURITY_S, int(now) + SDK_MIN_EXPIRATION_S + EXPIRATION_MARGIN_S)
        if expiration > w.end + GTD_SECURITY_S + MAX_EXPIRY_PAST_END_S:
            return self.skip(w, rec, f"its minimum expiry would outlive the window end by "
                                     f"{expiration - GTD_SECURITY_S - w.end} s: not placed")
        if rec.size < bk["min_size"]:
            return self.skip(w, rec, f"size {rec.size} < market minimum {bk['min_size']}")
        if (rec.price / bk["tick"]) % 1 != 0:
            return self.skip(w, rec, f"price {rec.price} not on the tick {bk['tick']}")
        if bk["ask"] is not None and rec.price >= bk["ask"]:
            return self.skip(w, rec, f"would cross: best ask {bk['ask']} <= price {rec.price} (post-only)")
        notional = rec.price * rec.size
        try:
            check_order_caps(notional, w.resting, ledger(day_of(now), self.live, self.session))
        except Refusal as e:
            self.skip(w, rec, str(e))
            if "STOP" in str(e) or "today" in str(e):
                self.begin_stop(str(e))
            return
        if self.live and not self.geo_checked:
            smoke.geoblock_or_refuse()            # raises Refusal: the whole session stops
            self.geo_checked = True
        try:
            signed = env.sign(rec.token, rec.price, rec.size, expiration)
        except Exception as e:  # noqa: BLE001  (SDK input checks: tick, size, expiration)
            return self.skip(w, rec, scrub(f"SDK refused to build the order: {type(e).__name__}: {e}"))
        # Refusal here stops the whole session
        guard_signed(signed, rec.token, notional, self.live, w.end, expiration)
        rec.signed_expiration, rec.cancel_at, rec.placed_at = expiration, cancel_at, now
        placed_line = {"type": "placed", "exp": self.cfg.name, "mode": "live" if self.live else "dry-run",
                       "session": self.session, "key": rec.key, "day": day_of(now),
                       "window_start": w.start, "notional": str(notional)}
        append_record(self.path(w.start), placed_line)   # written BEFORE posting: worst-case accounting
        w.resting += notional
        if not self.live:
            rec.status = "dry-run"
            w.orders.append(rec)
            out(f"    DRY {lv.label}: BUY {rec.size} {rec.outcome} @ {rec.price} = {notional} pUSD "
                f"(bid {rec.bid} ask {rec.ask}, mid Up {rec.mid_up}) signed exp {utc(expiration)}, "
                f"cancel {utc(cancel_at)}; NOT posted")
            return
        try:
            r = env.post(signed)
        except Exception as e:  # noqa: BLE001  network error / 5xx / 429: the order may or may not rest
            rec.status, rec.reason = "post-error", scrub(f"{type(e).__name__}: {e}")
            rec.cancel_at = cancel_at
            w.orders.append(rec)
            out(f"    POST ERROR {lv.label} {rec.outcome}: {rec.reason}; counted as filled in today's caps, "
                f"expires by GTD at the latest")
            return
        if r["ok"]:
            rec.status, rec.order_id = "posted", r["order_id"]
            self.push(cancel_at, "cancel", w, rec)
            out(f"    POSTED {lv.label}: BUY {rec.size} {rec.outcome} @ {rec.price} id {rec.order_id} "
                f"status {r['status']}, cancel at {utc(cancel_at)}")
        else:
            rec.status, rec.reason = "rejected", scrub(f"{r.get('code')}: {r.get('message')}")
            w.resting -= notional
            out(f"    REJECTED {lv.label} {rec.outcome}: {rec.reason}")
        w.orders.append(rec)
        if rec.status == "rejected":
            self.write_order(w, rec, None, None)          # finalize at once: cost 0
            rec.status = "rejected-recorded"

    def close_orders(self, recs, when: str) -> list[OrderRec]:
        """Cancel every posted order in `recs` not yet known closed, then read each one's state.

        A cancel counts only for ids the exchange returns as cancelled; an order counts as closed only
        when its state read from the exchange is terminal. Returns the orders still live or unknown."""
        todo = [r for r in recs if r.status == "posted" and r.order_id and not r.closed]
        if not todo or not self.live:
            return []
        try:
            done = set(self.env.cancel([r.order_id for r in todo]))
        except Exception as e:  # noqa: BLE001
            done = set()
            out(f"    {when}: cancel request failed: {scrub(type(e).__name__ + ': ' + str(e))}")
        left = []
        for r in todo:
            if r.order_id in done:
                r.cancelled = True
            try:
                st = self.env.order_state(r.order_id)
                r.last_state = str(st["status"])
                r.closed = order_closed(st["status"])
                state = f"state {r.last_state}, matched {st['size_matched']}"
            except Exception as e:  # noqa: BLE001
                state = scrub(f"state read failed ({type(e).__name__})")
            out(f"    {when}: cancel {r.level.label} {r.outcome}: "
                f"{'confirmed' if r.order_id in done else 'NOT confirmed'}; {state}; "
                f"{'closed' if r.closed else 'STILL LIVE or unknown: counted as fully filled until closed'}")
            if not r.closed:
                left.append(r)
        return left

    def on_cancel(self, w: Window, rec: OrderRec) -> None:
        if rec.status != "posted" or rec.closed:
            return
        rec.cancel_tries += 1
        if self.close_orders([rec], "planned cancel") and rec.cancel_tries < CANCEL_RETRIES:
            self.push(self.env.now() + CANCEL_RETRY_S, "cancel", w, rec)

    def on_close(self, w: Window) -> None:
        """Window end: confirm that none of the window's orders is still live; cancel again if one is."""
        if not any(r.status == "posted" for r in w.orders):
            return
        left = self.close_orders(w.orders, "window end")
        if left:
            out(f"  {w.slug}: {len(left)} order(s) still live or unknown after the window end; "
                f"cancel retried every {FINALIZE_EVERY_S} s, counted as fully filled until closed")
        else:
            out(f"  {w.slug}: window end: no order of this window is live")

    def write_order(self, w: Window, rec: OrderRec, result: str | None, fill: dict | None) -> dict:
        filled = avg = cost = payout = pnl = None
        end_status = rec.status
        if rec.status == "posted" and (not rec.closed or (fill is not None and not order_closed(fill["status"]))):
            cost = rec.price * rec.size          # still live or unknown at finalise: worst case stays counted
            end_status = (f"{(fill or {}).get('status') or rec.last_state or 'unknown'} "
                          f"(not confirmed closed at finalise; counted as fully filled)")
        elif rec.status == "posted" and fill is not None:
            filled = max(D(fill["size_matched"]), D(fill.get("trade_shares") or 0))
            avg = fill["avg_price"] if fill["avg_price"] is not None else (rec.price if filled > 0 else None)
            cost = (filled * avg) if filled > 0 else Decimal(0)
            end_status = fill["status"]
            if result is not None and not result.startswith("split"):
                payout = filled if rec.outcome == result else Decimal(0)
                pnl = payout - cost
        elif rec.status in ("rejected", "skipped"):
            filled, cost = Decimal(0), Decimal(0)
        rec_line = {
            "type": "order", "exp": self.cfg.name, "mode": "live" if self.live else "dry-run",
            "session": self.session, "key": rec.key,
            "day": day_of(rec.placed_at) if rec.placed_at else day_of(w.start),
            "window_start": w.start, "window_start_utc": utc(w.start), "slug": w.slug,
            "condition_id": (w.market or {}).get("condition_id"),
            "level": rec.level.idx, "level_label": rec.level.label, "rule": rec.level.outcome,
            "outcome": rec.outcome, "token": rec.token, "price": str(rec.price), "size": str(rec.size),
            "notional": str(rec.price * rec.size), "status": rec.status, "reason": rec.reason,
            "order_id": rec.order_id, "placed_utc": utc(rec.placed_at) if rec.placed_at else None,
            "signed_expiration": rec.signed_expiration,
            "cancel_utc": utc(rec.cancel_at) if rec.cancel_at else None,
            "mid_up_at_placement": None if rec.mid_up is None else str(rec.mid_up),
            "best_bid": None if rec.bid is None else str(rec.bid),
            "best_ask": None if rec.ask is None else str(rec.ask),
            "end_status": end_status,
            "filled_size": None if filled is None else str(filled),
            "avg_price": None if avg is None else str(avg),
            "trade_shares": None if not fill else str(fill.get("trade_shares")),
            "cost": None if cost is None else str(cost),
            "window_result": result,
            "payout": None if payout is None else str(payout),
            "pnl": None if pnl is None else str(pnl),
        }
        append_record(self.path(w.start), rec_line)
        return rec_line

    def on_finalize(self, w: Window) -> None:
        if w.done:
            return
        if w.market is None:
            append_record(self.path(w.start), {"type": "window", "exp": self.cfg.name, "session": self.session,
                                               "mode": "live" if self.live else "dry-run",
                                               "window_start": w.start, "slug": w.slug,
                                               "skipped": w.skipped_reason or "no market"})
            w.done = True
            return
        timed_out = self.env.now() >= w.end + FINALIZE_TIMEOUT_S
        # fills are read only once every order is known to be no longer live (cancel again if one is)
        if self.close_orders(w.orders, "finalise") and not timed_out:
            self.push(self.env.now() + FINALIZE_EVERY_S, "finalize", w)
            return
        result = None
        try:
            result = self.env.result(w.market["condition_id"], {v: k for k, v in w.market["index"].items()})
        except Exception as e:  # noqa: BLE001
            out(f"  {w.slug}: result lookup failed ({type(e).__name__}), will retry")
        if result is None and not timed_out:
            self.push(self.env.now() + FINALIZE_EVERY_S, "finalize", w)
            return
        lines = []
        for rec in w.orders:
            if rec.status == "rejected-recorded":
                continue
            fill = None
            if rec.status == "posted" and rec.closed:
                try:
                    fill = self.env.fills(rec.order_id, rec.token)
                except Exception as e:  # noqa: BLE001
                    rec.reason = scrub(f"fill lookup failed: {type(e).__name__}")
            elif rec.status == "posted":
                rec.reason = "not confirmed closed by the exchange at finalise: counted as fully filled"
            lines.append(self.write_order(w, rec, result, fill))
        tot = defaultdict(Decimal)
        for ln in lines:
            for k in ("cost", "payout", "pnl"):
                if ln[k] is not None:
                    tot[k] += D(ln[k])
        append_record(self.path(w.start), {
            "type": "window", "exp": self.cfg.name, "session": self.session,
            "mode": "live" if self.live else "dry-run", "window_start": w.start,
            "window_start_utc": utc(w.start), "slug": w.slug, "condition_id": w.market["condition_id"],
            "result": result, "skipped": w.skipped_reason or None,
            "orders_sent": sum(1 for r in w.orders if r.status in ("posted", "dry-run", "rejected-recorded", "post-error")),
            "orders_filled": sum(1 for ln in lines if ln["filled_size"] not in (None, "0") and D(ln["filled_size"]) > 0),
            "cost": str(tot["cost"]), "payout": str(tot["payout"]), "pnl": str(tot["pnl"])})
        out(f"  {w.slug}: result {result or 'UNRESOLVED'}; {len(lines)} order records; "
            f"cost {tot['cost']} payout {tot['payout']} net {tot['pnl']}")
        w.done = True

    def begin_stop(self, why: str) -> None:
        if self.stopping:
            return
        self.stopping = True
        out(f"  STOPPING: {why}. No new orders; open orders of this session are cancelled; "
            f"results of windows with orders are still recorded (Ctrl+C quits at once).")
        left = self.close_orders([r for w in self.windows for r in w.orders], "stop")
        if left:
            out(f"  {len(left)} order(s) not confirmed closed on stop; tried again at the window end and at "
                f"finalise, counted as fully filled until closed")
        # windows without orders need no result wait
        for w in self.windows:
            if not any(r.status in ("posted", "dry-run") for r in w.orders) and not w.done:
                w.done = True

    def run(self) -> int:
        self.plan()
        while self.events:
            if not self.stopping and STOP_FILE.exists():
                self.begin_stop(f"STOP file {STOP_FILE}")
            t, _, kind, payload = self.events[0]
            now = self.env.now()
            if t > now:
                self.env.sleep(min(t - now, 1.0))
                continue
            heapq.heappop(self.events)
            getattr(self, f"on_{kind}")(*payload)
            if self.stopping and all(w.done for w in self.windows):
                break
        out(f"  session {self.session} done: records in {OUT_DIR}")
        return 0

    def interrupt(self) -> None:
        recs = [r for w in self.windows for r in w.orders if r.status == "posted" and not r.closed]
        if recs and self.live:
            left = self.close_orders(recs, "interrupt")
            out(f"  interrupted: {len(recs) - len(left)} of {len(recs)} open order(s) confirmed closed"
                + (f"; {len(left)} NOT confirmed: they expire by GTD, check open orders on polymarket.com"
                   if left else ""))
        out("  interrupted: orders without a final record count as fully filled in today's caps")


# ----------------------------------------------------------------------------- run command
def check_balance(env, cfg: Config) -> Decimal:
    bal = env.balance()
    out(f"  pUSD balance {bal}; worst-case resting per window {cfg.window_notional}")
    if bal < cfg.window_notional:
        raise Refusal(f"balance {bal} pUSD < worst-case resting notional {cfg.window_notional}; not starting")
    return bal


def cmd_run(a) -> int:
    try:
        return _cmd_run(a)
    finally:
        lock = getattr(a, "_lock", None)
        if lock is not None:
            lock.close()                         # releases the live lock (process exit does too)


def _cmd_run(a) -> int:
    cfg = load_config(a.config)
    if a.max_windows < 1 or a.max_windows > HARD_MAX_WINDOWS:
        raise Refusal(f"--max-windows must be 1-{HARD_MAX_WINDOWS}")
    out(f"  experiment {cfg.name}: {cfg.asset} {cfg.duration}, {len(cfg.levels)} level(s), "
        f"worst case per window {cfg.window_notional} pUSD")
    for lv in cfg.levels:
        out(f"    {lv.label}: {lv.outcome} BUY {lv.size} @ {lv.price} ({lv.notional} pUSD each), "
            f"place at +{lv.place_offset} s, cancel at +{lv.cancel_offset} s")
    if STOP_FILE.exists():
        raise Refusal(f"STOP file present ({STOP_FILE}); remove it to start")
    wallet = smoke.wallet_env()
    if a.live:
        # one live session at a time, across every checkout: held until the process ends
        a._lock = acquire_live_lock(LOCK_FILE)
        key = smoke.load_private_key()
        smoke.geoblock_or_refuse()
        client = smoke.live_client(key, wallet)
    else:
        try:
            key = smoke.load_private_key()
            out("  dry-run: your key file is used only to sign locally; nothing is sent")
        except Refusal:
            from eth_account import Account
            key = "0x" + Account.create().key.hex().removeprefix("0x")
            out.add_secret(key)
            out("  dry-run: no usable key file, signing with a throwaway in-memory key")
        try:
            smoke.geoblock_or_refuse()
        except Refusal as e:
            out(f"  dry-run: geoblock would refuse a live run here ({e})")
        client = smoke.offline_client(key, wallet)
    out.add_secret(str(client.wallet))
    out.add_secret(str(client.signer))
    out(f"  wallet type {client.wallet_type} (addresses are not printed)")
    try:
        env = RealEnv(client, a.live)
        if a.live:
            check_balance(env, cfg)
        s = Session(cfg, env, a.live, a.max_windows)
        try:
            return s.run()
        except KeyboardInterrupt:
            s.interrupt()
            return 130
        except BaseException:
            s.interrupt()                       # cancel this session's open orders, then report the error
            raise
    finally:
        client.close()


# ----------------------------------------------------------------------------- report
def fmt(x: Decimal) -> str:
    return f"{x:.2f}"


def cmd_report(a) -> int:
    if a.files:
        paths = a.files
    else:
        pat = "exp-*.dryrun.jsonl" if a.dry_run else "exp-*.jsonl"
        paths = sorted(p for p in glob.glob(str(OUT_DIR / pat)) if a.dry_run == p.endswith(".dryrun.jsonl"))
    if not paths:
        out("  no record files found")
        return 0
    rows = read_records(paths)
    orders = {r["key"]: r for r in rows if r.get("type") == "order" and "status" in r and "level_label" in r}
    placed = {r["key"]: r for r in rows if r.get("type") == "placed"}
    windows = [r for r in rows if r.get("type") == "window"]
    out(f"  files: {len(paths)}  order records: {len(orders)}  windows: {len(windows)}")
    finalized = {r.get("key") for r in rows if r.get("type") == "order"}
    unfinal = [k for k in placed if k not in finalized]
    if unfinal:
        out(f"  orders sent without a final record (session interrupted): {len(unfinal)}")

    def agg(group_key):
        g = defaultdict(lambda: defaultdict(Decimal))
        for r in orders.values():
            k = group_key(r)
            s = g[k]
            if r["status"] == "skipped":
                s["skipped"] += 1
                continue
            if r["status"] in ("rejected",):
                s["rejected"] += 1
                continue
            s["placed"] += 1
            if r["filled_size"] is None:
                s["unknown"] += 1
                continue
            f = D(r["filled_size"])
            if f > 0:
                s["filled_orders"] += 1
                s["shares"] += f
                s["cost"] += D(r["cost"])
                if r["payout"] is not None:
                    s["payout"] += D(r["payout"])
                    s["net"] += D(r["pnl"])
                    s["resolved_filled"] += 1
                    if D(r["payout"]) > 0:
                        s["won"] += 1
                else:
                    s["unresolved_filled"] += 1
        return g

    hdr = (f"  {'experiment / level':34} {'placed':>6} {'rej':>4} {'skip':>4} {'fill%':>6} {'shares':>8} "
           f"{'cost':>7} {'payout':>7} {'net':>7} {'win%':>6}")
    out("\nPer level (cost, payout, net in pUSD; payout = winning shares x 1, before redemption):")
    out(hdr)
    for k, s in sorted(agg(lambda r: f"{r['exp']} / {r['level_label']}").items()):
        known = s["placed"] - s["unknown"]
        fr = f"{100 * s['filled_orders'] / known:.0f}%" if known else "n/a"
        wr = f"{100 * s['won'] / s['resolved_filled']:.0f}%" if s["resolved_filled"] else "n/a"
        out(f"  {k:34} {int(s['placed']):>6} {int(s['rejected']):>4} {int(s['skipped']):>4} {fr:>6} "
            f"{fmt(s['shares']):>8} {fmt(s['cost']):>7} {fmt(s['payout']):>7} {fmt(s['net']):>7} {wr:>6}"
            + (f"  ({int(s['unknown'])} without fill data)" if s["unknown"] else "")
            + (f"  ({int(s['unresolved_filled'])} filled, unresolved)" if s["unresolved_filled"] else ""))
    out("\nTotals by UTC day:")
    out(f"  {'day':12} {'placed':>6} {'filled':>6} {'shares':>8} {'cost':>7} {'payout':>7} {'net':>7}")
    for k, s in sorted(agg(lambda r: r["day"]).items()):
        out(f"  {k:12} {int(s['placed']):>6} {int(s['filled_orders']):>6} {fmt(s['shares']):>8} "
            f"{fmt(s['cost']):>7} {fmt(s['payout']):>7} {fmt(s['net']):>7}")
    res = defaultdict(int)
    for w in windows:
        res[w.get("result") or ("skipped" if w.get("skipped") else "unresolved")] += 1
    out(f"\nWindow results: {dict(res)}")
    return 0


# ----------------------------------------------------------------------------- selftest
class FakeEnv:
    """Fake clock and exchange for the selftest. Signs with the real SDK offline client."""

    def __init__(self, client, live: bool, t0: float, mid_up="0.70", ask="0.60", min_size="5",
                 fill_outcome="Down", result="Up"):
        self.c, self.live, self.t = client, live, t0
        self.mid_up, self.ask, self.min_size = D(mid_up), D(ask), D(min_size)
        self.fill_outcome, self.res = fill_outcome, result
        self.posted, self.cancelled, self.tokens = [], [], {}
        self.cancel_log, self.closed_ids, self.fill_reads = [], set(), []   # (time, id), ids, (time, id)

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += max(s, 0.001)

    def market(self, slug):
        s = int(slug.rsplit("-", 1)[1])
        up, dn = str(10 ** 20 + s), str(2 * 10 ** 20 + s)
        self.tokens[up], self.tokens[dn] = "Up", "Down"
        cond = "0x" + f"{s:064x}"
        _register_offline_market(self.c, (up, dn), cond)
        return {"condition_id": cond, "accepting": True, "closed": False,
                "tokens": {"Up": up, "Down": dn}, "index": {"Up": 0, "Down": 1}}

    def book(self, token):
        return {"bid": Decimal("0.01"), "ask": self.ask, "min_size": self.min_size, "tick": Decimal("0.01")}

    def mid(self, token):
        return self.mid_up

    def sign(self, token, price, size, expiration):
        return self.c.create_limit_order(asset_id=token, price=price, size=size, side="BUY",
                                         post_only=True, expiration=expiration)

    def post(self, signed):
        if not self.live:
            raise Refusal("internal: post called in dry-run")
        oid = "0x" + uuid.uuid4().hex * 2
        self.posted.append((oid, str(signed.token_id), Decimal(signed.maker_amount), Decimal(signed.taker_amount),
                            int(signed.expiration), self.t))
        return {"ok": True, "order_id": oid, "status": "live"}

    def _order(self, order_id):
        for p in self.posted:
            if p[0] == order_id:
                return p
        raise KeyError(order_id)

    def order_state(self, order_id):
        _, tok, mk, tk, _, _ = self._order(order_id)
        if self.tokens[tok] == self.fill_outcome:
            return {"status": "MATCHED", "size_matched": tk / smoke.USDC_UNIT}
        if order_id in self.closed_ids:
            return {"status": "CANCELED", "size_matched": Decimal(0)}
        return {"status": "LIVE", "size_matched": Decimal(0)}

    def cancel(self, ids):                       # like the exchange: only a live order can be cancelled
        self.cancelled.extend(ids)
        self.cancel_log.extend((self.t, i) for i in ids)
        done = [i for i in ids if self.order_state(i)["status"] == "LIVE"]
        self.closed_ids.update(done)
        return done

    def fills(self, order_id, token):
        self.fill_reads.append((self.t, order_id))
        _, tok, mk, tk, _, _ = self._order(order_id)
        st = self.order_state(order_id)
        sz = st["size_matched"]
        return {"status": st["status"], "size_matched": sz, "trade_shares": sz,
                "avg_price": (mk / tk) if sz > 0 else None}

    def balance(self):
        return Decimal("3.00")

    def result(self, condition_id, labels):
        return self.res


def _register_offline_market(client, tokens, cond):
    from polymarket._internal.actions.orders.market_data import MarketInfo, PlatformFeeInfo
    tokens = (tokens,) if isinstance(tokens, str) else tuple(tokens)
    ctx = client._ctx  # noqa: SLF001
    info = MarketInfo(fee_info=PlatformFeeInfo(rate=Decimal("0.05"), exponent=Decimal(1)), neg_risk=False,
                      tick_size=Decimal("0.01"), token_ids=frozenset(tokens))
    for t in tokens:
        ctx.order_metadata._conditions.set(t, cond)  # noqa: SLF001
    ctx.order_metadata._markets.set(cond, info)  # noqa: SLF001


def cmd_selftest(a) -> int:
    import tempfile
    import urllib.request

    global OUT_DIR, STOP_FILE, LOCK_FILE
    for var in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
        os.environ[var] = "http://127.0.0.1:9"
    os.environ.pop("NO_PROXY", None)
    os.environ.pop("no_proxy", None)
    from eth_account import Account

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

    def expect(name, cond, detail=""):
        nonlocal ok
        out(f"  [{'PASS' if cond else 'FAIL'}] {name}{': ' + detail if detail else ''}")
        ok &= bool(cond)

    tmp = Path(tempfile.mkdtemp(prefix="pm-exp-selftest-"))
    os.chmod(tmp, 0o700)
    real_out, real_stop, real_lock = OUT_DIR, STOP_FILE, LOCK_FILE
    OUT_DIR, STOP_FILE, LOCK_FILE = tmp / "out", tmp / "STOP", tmp / "lockdir" / "exp_bids.live.lock"
    old_key = os.environ.get("PM_KEY_FILE")
    acct = Account.create()
    key = "0x" + acct.key.hex().removeprefix("0x")
    out.add_secret(key)
    out("selftest: throwaway key, fake clock, fake exchange; records in a temp dir")
    try:
        # ---- configs
        for f in sorted((HERE / "experiments").glob("*.json")):
            check(f"shipped config {f.name} valid", lambda f=f: (lambda c: f"{c.name}: {len(c.levels)} level(s), "
                  f"window {c.window_notional} pUSD")(load_config(str(f))), False)
        base = {"name": "t", "asset": "btc", "duration": "5m",
                "levels": [{"outcome": "both", "price": "0.02", "size": "25", "place_after_start_s": 0,
                            "expire_before_end_s": 30}]}

        def cfg_with(**lv_over):
            c = json.loads(json.dumps(base))
            c["levels"][0].update(lv_over)
            for k, v in list(c["levels"][0].items()):
                if v is None:
                    del c["levels"][0][k]
            return c

        check("order 6 x 0.50 = 3.00 > 2.50 refused", lambda: parse_config(cfg_with(price="0.50", size="6")), True)
        check("order 5 x 0.50 = 2.50 accepted (cap is inclusive)",
              lambda: parse_config(cfg_with(outcome="trailing", price="0.50", size="5")).window_notional, False)
        check("window both 2 x (5 x 0.50) = 5.00 accepted", lambda: parse_config(cfg_with(price="0.50", size="5"))
              .window_notional, False)
        c2 = json.loads(json.dumps(base))
        c2["levels"] = [{"label": "a", "outcome": "both", "price": "0.40", "size": "5", "place_after_start_s": 0,
                         "expire_before_end_s": 30},
                        {"label": "b", "outcome": "trailing", "price": "0.02", "size": "60",
                         "place_before_end_s": 120, "expire_before_end_s": 5}]
        check("window 4.00 + 1.20 = 5.20 > 5.00 refused", lambda: parse_config(c2), True)
        check("unknown config key (max_order_usd) refused",
              lambda: parse_config({**base, "max_order_usd": 100}), True)
        check("unknown level key (side: SELL) refused", lambda: parse_config(cfg_with(side="SELL")), True)
        check("outcome 'sell' refused", lambda: parse_config(cfg_with(outcome="sell")), True)
        check("price 0.015 (3 decimals) refused", lambda: parse_config(cfg_with(price="0.015")), True)
        check("price 1.00 refused", lambda: parse_config(cfg_with(price="1.00")), True)
        check("size 0 refused", lambda: parse_config(cfg_with(size="0")), True)
        check("both placement keys refused", lambda: parse_config(cfg_with(place_before_end_s=100)), True)
        check("placement after expiry refused",
              lambda: parse_config(cfg_with(place_after_start_s=280, expire_before_end_s=30)), True)
        check("asset 'trump' refused", lambda: parse_config({**base, "asset": "trump"}), True)
        check("duration '1h' refused", lambda: parse_config({**base, "duration": "1h"}), True)

        # ---- flags
        def parse_flags(argv):
            import contextlib
            import io
            try:
                with contextlib.redirect_stderr(io.StringIO()):
                    build_parser().parse_args(argv)
                return "parsed"
            except SystemExit:
                raise Refusal("argparse rejected the flag") from None
        check("flag --max-notional does not exist", lambda: parse_flags(["run", "--max-notional", "100"]), True)
        check("--max-windows 500 refused",
              lambda: cmd_run(argparse.Namespace(config=str(HERE / "experiments" / "tails.json"), live=False,
                                                 max_windows=500)), True)

        # ---- per-order caps
        day = (0, Decimal(0), Decimal(0))
        check("order 2.51 refused by per-order cap", lambda: check_order_caps(Decimal("2.51"), Decimal(0), day), True)
        check("window 4.50 + 1.00 refused by per-window cap",
              lambda: check_order_caps(Decimal("1.00"), Decimal("4.50"), day), True)
        check("day: 300 orders sent -> 301st refused", lambda: check_order_caps(Decimal("0.10"), Decimal(0),
                                                                           (300, Decimal(0), Decimal(0))), True)
        check("day: filled 14.00 + open 0.50 + 1.00 > 15 refused",
              lambda: check_order_caps(Decimal("1.00"), Decimal(0), (10, Decimal("14.00"), Decimal("0.50"))), True)
        check("day: filled 14.00 + 1.00 = 15.00 accepted",
              lambda: check_order_caps(Decimal("1.00"), Decimal(0), (10, Decimal("14.00"), Decimal(0))), False)
        expect("(no STOP file during the count-cap checks)", not STOP_FILE.exists())
        check("day: 299 sent, a 'both' level (2 legs) refused",
              lambda: check_order_caps(Decimal("0.10"), Decimal(0), (299, Decimal(0), Decimal(0)), legs=2), True)
        check("day: 299 sent, one more single order accepted",
              lambda: check_order_caps(Decimal("0.10"), Decimal(0), (299, Decimal(0), Decimal(0)), legs=1), False)
        STOP_FILE.write_text("")
        check("STOP file present -> refused", lambda: check_order_caps(Decimal("0.10"), Decimal(0), day), True)
        STOP_FILE.unlink()

        # ---- M3 config: a level whose minimum expiry outlives the window is refused
        check("place_before_end_s 20 refused (minimum expiry would outlive the window)",
              lambda: parse_config(cfg_with(place_after_start_s=None, place_before_end_s=20,
                                            expire_before_end_s=5, price="0.02", size="25")), True)
        check("place_before_end_s 120 (late-tail) accepted",
              lambda: parse_config(cfg_with(place_after_start_s=None, place_before_end_s=120,
                                            expire_before_end_s=5)).levels[0].place_offset, False)

        # ---- M2: single-instance lock
        def second_lock():
            h1 = acquire_live_lock(LOCK_FILE)
            try:
                return acquire_live_lock(LOCK_FILE)
            finally:
                h1.close()
        check("live lock: a second live instance is refused while the first holds the lock", second_lock, True)
        check("live lock: free again once the first instance ends",
              lambda: (lambda h: (h.close(), "acquired")[1])(acquire_live_lock(LOCK_FILE)), False)
        held = acquire_live_lock(LOCK_FILE)
        try:
            msg = ""
            try:
                cmd_run(argparse.Namespace(config=str(HERE / "experiments" / "pairs.json"), live=True, max_windows=2))
            except Refusal as e:
                msg = str(e)
            expect("live lock: `run --live` refused before the key is read while another session runs",
                   "another live" in msg, msg)
        finally:
            held.close()

        # ---- ledger from files (crash-safe worst case)
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        lp = records_path("ledger", "2026-01-01", True)
        append_record(lp, {"type": "placed", "key": "a", "day": "2026-01-01", "notional": "2.00"})
        append_record(lp, {"type": "placed", "key": "b", "day": "2026-01-01", "notional": "1.00"})
        append_record(lp, {"type": "order", "key": "a", "day": "2026-01-01", "cost": "0.80"})
        n, f_, o_ = ledger("2026-01-01", True, "x")
        expect("ledger: 2 sent, filled 0.80, unfinalized 1.00 counted as open", (n, f_, o_) ==
               (2, Decimal("0.80"), Decimal("1.00")), f"{n}, {f_}, {o_}")
        lp.unlink()

        # ---- signed-order guard on real SDK signatures
        client = smoke.offline_client(key, None)
        tok = "71321045679252212594626385532706912750332728571942532289631379312455583992563"
        _register_offline_market(client, tok, "0x" + "ab" * 32)
        exp = int(time.time()) + 600
        good = client.create_limit_order(asset_id=tok, price=Decimal("0.40"), size=Decimal(5), side="BUY",
                                         post_only=True, expiration=exp)
        wend = exp - GTD_SECURITY_S              # window end such that exp = cancel at the end + 60 s

        def g(signed, token=tok, planned=Decimal("2.00"), window_end=wend, expiration=exp):
            return guard_signed(signed, token, planned, True, window_end, expiration)
        check("signed BUY 5 @ 0.40 passes the final guard", lambda: g(good), False)
        big = client.create_limit_order(asset_id=tok, price=Decimal("0.60"), size=Decimal(5), side="BUY",
                                        post_only=True, expiration=exp)
        check("signed BUY 5 @ 0.60 = 3.00 blocked by the final guard", lambda: g(big, planned=Decimal("3.00")), True)
        check("signed order larger than planned blocked", lambda: g(good, planned=Decimal("1.00")), True)
        nopo = client.create_limit_order(asset_id=tok, price=Decimal("0.40"), size=Decimal(5), side="BUY",
                                         expiration=exp)
        check("signed order without post-only blocked", lambda: g(nopo), True)
        gtc = client.create_limit_order(asset_id=tok, price=Decimal("0.40"), size=Decimal(5), side="BUY",
                                        post_only=True)
        check("signed GTC (no expiration) blocked", lambda: g(gtc), True)
        check("signed order for another token blocked", lambda: g(good, token="1" + tok[1:]), True)
        sell = client.create_limit_order(asset_id=tok, price=Decimal("0.40"), size=Decimal(5), side="SELL",
                                         post_only=True, expiration=exp)
        check("signed SELL blocked", lambda: g(sell), True)
        # M3 probe K: an order expiring in 2033 passed the old guard
        far = client.create_limit_order(asset_id=tok, price=Decimal("0.40"), size=Decimal(5), side="BUY",
                                        post_only=True, expiration=2_000_000_000)
        check("signed order expiring in 2033 blocked (expiration bounded by the window end)",
              lambda: g(far, expiration=2_000_000_000), True)
        check("signed expiration other than the planned one blocked", lambda: g(good, expiration=exp + 1), True)
        check("signed expiration = window end + 60 + 10 accepted (upper bound inclusive)",
              lambda: g(good, window_end=exp - GTD_SECURITY_S - MAX_EXPIRY_PAST_END_S), False)
        check("signed expiration = window end + 60 + 11 blocked",
              lambda: g(good, window_end=exp - GTD_SECURITY_S - MAX_EXPIRY_PAST_END_S - 1), True)
        addrs = [str(client.wallet).lower(), str(client.signer).lower()]
        out.add_secret(str(client.wallet))       # as cmd_run does
        out.add_secret(str(client.signer))

        # ---- live refusals before any order
        os.environ["PM_KEY_FILE"] = str(tmp / "missing-key")
        check("--live without a key file refused",
              lambda: cmd_run(argparse.Namespace(config=str(HERE / "experiments" / "tails.json"), live=True,
                                                 max_windows=2)), True)
        check("geoblock unreachable -> refused (network is dead in selftest)", smoke.geoblock_or_refuse, True)

        class _Resp:
            def __init__(self, body): self.body = body
            def read(self): return self.body
            def __enter__(self): return self
            def __exit__(self, *x): return False
        real_urlopen = urllib.request.urlopen
        try:
            urllib.request.urlopen = lambda *x, **k: _Resp(b'{"blocked": true, "country": "US"}')
            check("geoblock blocked=true -> refused", smoke.geoblock_or_refuse, True)
            # geoblock blocked inside a live session: refused before the first post
            cfg = load_config(str(HERE / "experiments" / "pairs.json"))
            env = FakeEnv(client, True, t0=1_800_000_000.0)
            s = Session(cfg, env, True, 1)
            check("live session with blocked geoblock stops before posting", s.run, True)
            expect("  ... and nothing was posted", not env.posted, f"posted {len(env.posted)}")
            urllib.request.urlopen = lambda *x, **k: _Resp(b'{"blocked": false, "country": "RS"}')

            # balance below worst case
            class LowBal(FakeEnv):
                def balance(self): return Decimal("3.99")
            check("balance 3.99 < worst-case 4.00 (pairs) refused",
                  lambda: check_balance(LowBal(client, True, 0), cfg), True)
            check("balance 3.00 >= worst-case 1.00 (tails) accepted",
                  lambda: check_balance(FakeEnv(client, True, 0), load_config(str(HERE / "experiments" / "tails.json"))),
                  False)

            # ---- dry-run session: nothing posted
            for f in OUT_DIR.glob("*"):
                f.unlink()
            cfg_t = load_config(str(HERE / "experiments" / "tails.json"))
            env = FakeEnv(client, False, t0=1_800_000_007.0)
            Session(cfg_t, env, False, 2).run()
            dry = read_records(OUT_DIR.glob("*.dryrun.jsonl"))
            o = [r for r in dry if r["type"] == "order"]
            expect("dry-run: 2 windows x 2 orders planned and signed, none posted",
                   len(o) == 4 and all(r["status"] == "dry-run" for r in o) and not env.posted,
                   f"{len(o)} order records, posted {len(env.posted)}")
            expect("dry-run: window results recorded", sum(r["type"] == "window" for r in dry) == 2)

            # ---- live session (fake exchange): fills, pnl, cancel, caps
            env = FakeEnv(client, True, t0=1_800_000_007.0, fill_outcome="Down", result="Up")
            Session(cfg, env, True, 2).run()
            live = read_records(OUT_DIR.glob("exp-pairs-*.jsonl"))
            o = [r for r in live if r["type"] == "order"]
            downs = [r for r in o if r["outcome"] == "Down"]
            ups = [r for r in o if r["outcome"] == "Up"]
            cancel_secs = sorted({int(t) % 300 for t, _ in env.cancel_log})   # windows start on multiples of 300
            expect("live (fake): 4 orders posted, each cancelled at its expiry second (+270 s)",
                   len(env.posted) == 4 and len(env.cancelled) == 4 and cancel_secs == [270],
                   f"posted {len(env.posted)} cancelled {len(env.cancelled)} at +{cancel_secs} s")
            expect("live (fake): signed expiration = cancel second + 60 s (+330 s), as planned",
                   all(p[4] - (p[5] - p[5] % 300) == 330 for p in env.posted),
                   str(sorted({p[4] - (p[5] - p[5] % 300) for p in env.posted})))
            expect("live (fake): fills read only after each order's state was terminal (after its cancel)",
                   all(t >= next(ct for ct, ci in env.cancel_log if ci == oid) for t, oid in env.fill_reads)
                   and len(env.fill_reads) == 4)
            expect("live (fake): Down filled 5 @ 0.40, lost: cost 2.00 payout 0 net -2.00",
                   all(r["filled_size"] == "5" and D(r["cost"]) == 2 and D(r["pnl"]) == -2 for r in downs),
                   json.dumps([(r["filled_size"], r["cost"], r["pnl"]) for r in downs]))
            expect("live (fake): Up not filled, cost 0", all(D(r["filled_size"]) == 0 for r in ups))
            # late-tail: trailing outcome by mid
            cfg_l = load_config(str(HERE / "experiments" / "late-tail.json"))
            env = FakeEnv(client, True, t0=1_800_000_007.0, mid_up="0.80", fill_outcome="Down", result="Down")
            Session(cfg_l, env, True, 1).run()
            o = [r for r in read_records(OUT_DIR.glob("exp-late-tail-*.jsonl")) if r["type"] == "order"]
            expect("late-tail: mid Up 0.80 -> trailing = Down, placed 120 s before the end",
                   len(o) == 1 and o[0]["outcome"] == "Down" and
                   o[0]["placed_utc"] == utc(o[0]["window_start"] + 180), json.dumps([(r["outcome"], r["placed_utc"]) for r in o]))
            expect("late-tail: Down won: payout 25, cost 0.50, net +24.50",
                   len(o) == 1 and D(o[0]["pnl"]) == Decimal("24.50"), o[0]["pnl"] if o else "")
            env = FakeEnv(client, True, t0=1_800_000_007.0, mid_up="0.50")
            Session(cfg_l, env, True, 1).run()
            expect("late-tail: mid exactly 0.50 -> skipped, nothing posted", not env.posted)
            # market minimum above the configured size
            env = FakeEnv(client, True, t0=1_800_000_007.0, min_size="10")
            Session(cfg, env, True, 1).run()
            expect("size 5 < market minimum 10 -> skipped, nothing posted", not env.posted)
            # post-only would cross
            env = FakeEnv(client, True, t0=1_800_000_007.0, ask="0.40")
            Session(cfg, env, True, 1).run()
            expect("best ask 0.40 <= price 0.40 -> skipped (post-only would be rejected)", not env.posted)
            # network error while posting: counted as fully filled (worst case) in the day's caps
            for f in OUT_DIR.glob("*"):
                f.unlink()

            class PostErr(FakeEnv):
                def post(self, signed):
                    raise TimeoutError("simulated")
            env = PostErr(client, True, t0=1_800_000_007.0)
            Session(cfg, env, True, 1).run()
            n, f_, o_ = ledger(day_of(1_800_000_007.0), True, "")
            st = [r["status"] for r in read_records(OUT_DIR.glob("*.jsonl")) if r["type"] == "order"]
            expect("post error -> recorded as post-error, its 4.00 counted as filled today",
                   st == ["post-error", "post-error"] and f_ == Decimal("4.00"), f"{st}, filled {f_}")
            # STOP file present before the session's first order: nothing posted
            STOP_FILE.write_text("")
            env = FakeEnv(client, True, t0=1_800_000_007.0)
            Session(cfg, env, True, 3).run()
            expect("STOP file before the first order -> no order posted in the session", not env.posted)
            STOP_FILE.unlink()

            # STOP file written mid-session, while this session's orders rest: they are cancelled at once,
            # no later order is posted, the window with orders is still finalised
            for f in OUT_DIR.glob("*"):
                f.unlink()

            class StopMid(FakeEnv):
                stop_at = None

                def sleep(self, s):
                    super().sleep(s)
                    if self.posted and self.stop_at is None and self.t >= self.posted[-1][5] + 30:
                        STOP_FILE.write_text("")
                        self.stop_at = self.t
            env = StopMid(client, True, t0=1_800_000_007.0, fill_outcome="none")
            Session(cfg, env, True, 3).run()
            STOP_FILE.unlink()
            ids = [p[0] for p in env.posted]
            o = [r for r in read_records(OUT_DIR.glob("*.jsonl")) if r["type"] == "order"]
            expect("STOP mid-session: 2 orders resting when STOP appears, no order posted after it",
                   len(env.posted) == 2 and env.stop_at is not None and all(p[5] < env.stop_at for p in env.posted),
                   f"posted {len(env.posted)}")
            expect("STOP mid-session: both resting orders cancelled right after STOP, before their +270 s cancel",
                   sorted(i for t, i in env.cancel_log if t < env.posted[0][5] + 270) == sorted(ids)
                   and all(t - env.stop_at < 2 for t, _ in env.cancel_log),
                   f"cancel times after STOP: {[round(t - env.stop_at, 1) for t, _ in env.cancel_log]}")
            expect("STOP mid-session: the window with orders is finalised, both orders closed at cost 0",
                   len(o) == 2 and all(r["end_status"] == "CANCELED" and D(r["cost"]) == 0 for r in o),
                   json.dumps([(r["end_status"], r["cost"]) for r in o]))
            # daily filled cap stops a session: 4.00 per window, 15 per day -> 3 windows max
            for f in OUT_DIR.glob("*"):
                f.unlink()
            env = FakeEnv(client, True, t0=1_800_000_007.0, fill_outcome="Down")
            Session(cfg, env, True, 6).run()
            n, f_, o_ = ledger(day_of(1_800_000_007.0), True, "")
            expect("daily cap: 6 windows of pairs stop at <= 15.00 pUSD worst case, both legs or none",
                   f_ + o_ <= MAX_DAY_FILLED and len(env.posted) == 10,
                   f"posted {len(env.posted)}, worst-case used {f_ + o_}")
            # daily order-count cap from earlier sessions' files
            for f in OUT_DIR.glob("*"):
                f.unlink()
            d0 = day_of(1_800_000_007.0)
            for i in range(MAX_DAY_ORDERS):
                append_record(records_path("old", d0, True), {"type": "placed", "key": f"k{i}", "day": d0,
                                                              "notional": "0"})
                append_record(records_path("old", d0, True), {"type": "order", "key": f"k{i}", "day": d0,
                                                              "cost": "0"})
            env = FakeEnv(client, True, t0=1_800_000_007.0)
            Session(cfg, env, True, 1).run()
            expect("300 orders already sent today -> nothing posted", not env.posted)

            def clean():
                for f in OUT_DIR.glob("*"):
                    f.unlink()

            def orders_now():
                return [r for r in read_records(OUT_DIR.glob("*.jsonl")) if r["type"] == "order"]
            d0 = day_of(1_800_000_007.0)

            # ---- M1 probe B: the exchange never confirms the cancel; the order stays LIVE with 1 of 5 matched
            clean()

            class CancelNoop(FakeEnv):
                def cancel(self, ids):
                    self.cancelled.extend(ids)
                    self.cancel_log.extend((self.t, i) for i in ids)
                    return []

                def order_state(self, order_id):
                    self._order(order_id)
                    return {"status": "LIVE", "size_matched": Decimal(1)}
            env = CancelNoop(client, True, t0=1_800_000_007.0)
            Session(cfg, env, True, 1).run()
            n, f_, o_ = ledger(d0, True, "")
            o = orders_now()
            expect("M1: cancel never confirmed, order LIVE 1/5 -> day ledger keeps the full 4.00 (not 0.80)",
                   f_ + o_ == Decimal("4.00") and len(o) == 2 and all(D(r["cost"]) == 2 for r in o),
                   f"filled {f_} open {o_}; {[(r['end_status'], r['cost']) for r in o]}")
            expect("M1: ... no fill read while the order was live; recorded as not confirmed closed",
                   not env.fill_reads and all("not confirmed closed" in r["end_status"] for r in o))
            ws = env.posted[0][5] - env.posted[0][5] % 300
            expect("M1: ... cancel retried after +270 s, at the window end and at finalise",
                   any(t < ws + 300 for t, _ in env.cancel_log) and any(ws + 300 <= t < ws + 320 for t, _ in env.cancel_log)
                   and any(t >= ws + 320 for t, _ in env.cancel_log),
                   f"{len(env.cancel_log)} cancel attempts")

            # ---- (d): the cancel only takes effect after the window end (the market still accepts orders then):
            # the window-end check cancels again, reads the state, and only then reads fills
            clean()

            class LateCancel(FakeEnv):
                def cancel(self, ids):
                    self.cancelled.extend(ids)
                    self.cancel_log.extend((self.t, i) for i in ids)
                    p = self._order(ids[0])
                    if self.t < (p[5] - p[5] % 300) + 300:
                        return []
                    self.closed_ids.update(ids)
                    return list(ids)
            env = LateCancel(client, True, t0=1_800_000_007.0, fill_outcome="none")
            Session(cfg, env, True, 1).run()
            ws = env.posted[0][5] - env.posted[0][5] % 300
            n, f_, o_ = ledger(d0, True, "")
            o = orders_now()
            confirmed_at = min(t for t, i in env.cancel_log if t >= ws + 300)
            expect("(d): planned cancel not effective -> cancelled again at the window end check (+302 s)",
                   ws + 300 <= confirmed_at < ws + 300 + FINALIZE_FIRST_S and
                   sum(1 for t, _ in env.cancel_log if t < ws + 300) == 2 * CANCEL_RETRIES,
                   f"confirmed at +{confirmed_at - ws:.0f} s after {2 * CANCEL_RETRIES} unconfirmed tries")
            expect("(d): fills read only after the order was confirmed closed; ledger frees the 4.00 (cost 0)",
                   len(env.fill_reads) == 2 and all(t > confirmed_at for t, _ in env.fill_reads)
                   and f_ + o_ == 0 and all(r["end_status"] == "CANCELED" for r in o),
                   f"filled {f_} open {o_}")

            # ---- M3 probe D: the Mac sleeps 20 minutes just before the first placement second
            clean()

            class SleepJump(FakeEnv):
                jumped = False

                def sleep(self, s):
                    super().sleep(s)
                    if not self.jumped and self.t >= 1_800_000_300 - 3:
                        self.t += 1200
                        self.jumped = True
            env = SleepJump(client, True, t0=1_800_000_007.0)
            Session(cfg, env, True, 2).run()
            o = orders_now()
            expect("M3: after a 20-minute sleep no order is placed for windows that are over",
                   not env.posted and len(o) == 2 and all("sleep or clock jump" in r["reason"] for r in o),
                   json.dumps([r["reason"] for r in o]))

            # ---- M3: a level that would rest too short after a slow book read is skipped, not posted
            clean()

            class SlowBook(FakeEnv):
                def book(self, token):
                    self.t += 4
                    return super().book(token)
            cfg_s = parse_config({**base, "levels": [{"outcome": "both", "price": "0.02", "size": "25",
                                                      "place_after_start_s": 0, "expire_before_end_s": 290}]})
            env = SlowBook(client, True, t0=1_800_000_007.0)
            Session(cfg_s, env, True, 1).run()
            o = orders_now()
            expect("M3: 4 s book read before a 10 s resting level -> skipped as too close to its cancel second",
                   not env.posted and o and "too close to its cancel second" in o[0]["reason"],
                   json.dumps([r["reason"] for r in o]))

            # ---- (a) + (b): RealEnv.post maps a definite 4xx to "rejected" (cost 0); timeouts, 5xx, 429 stay
            # unknown (worst case); error text in records is redacted and carries no address
            from polymarket.errors import RequestRejectedError, TransportError
            from polymarket.models.clob.cancel import CancelOrdersResponse
            stranger = "0x" + "5a" * 20

            class _PostStub:
                def __init__(self, exc): self.exc = exc
                def post_order(self, signed): raise self.exc

            def via_real_post(exc):
                class ViaReal(FakeEnv):
                    def post(self, signed):
                        return RealEnv(_PostStub(exc), True).post(signed)
                clean()
                e = ViaReal(client, True, t0=1_800_000_007.0)
                Session(cfg, e, True, 1).run()
                return e, ledger(d0, True, ""), orders_now()
            env, (n, f_, o_), o = via_real_post(RequestRejectedError(
                f"order crosses book (maker {client.wallet}, {stranger})", status=400, code="INVALID_ORDER"))
            expect("(a) HTTP 400 'order crosses book' -> rejected, not counted as filled (day 0.00)",
                   [r["status"] for r in o] == ["rejected", "rejected"] and f_ + o_ == 0 and not env.cancelled,
                   f"{[r['status'] for r in o]}, filled {f_} open {o_}")
            rej_text = json.dumps(o).lower()
            expect("(b) rejection text in records: wallet redacted, no 40-hex address",
                   all(x not in rej_text and x[2:] not in rej_text for x in addrs + [stranger])
                   and not ADDRESS_RE.search(rej_text) and "<redacted>" in rej_text, o[0]["reason"] if o else "")
            for exc, what in ((TransportError("read timed out after the request was sent"), "timeout"),
                              (RequestRejectedError("service unavailable", status=503), "HTTP 503"),
                              (RequestRejectedError("too many requests", status=429), "HTTP 429")):
                env, (n, f_, o_), o = via_real_post(exc)
                expect(f"(a) {what} -> post-error, unknown outcome counted as exposed: day 4.00",
                       [r["status"] for r in o] == ["post-error", "post-error"] and f_ + o_ == Decimal("4.00"),
                       f"{[r['status'] for r in o]}, filled {f_} open {o_}")

            class AddrErr(FakeEnv):
                def post(self, signed):
                    raise TimeoutError(f"timed out; wallet {client.wallet} signer {str(client.signer)[2:]} "
                                       f"proxy {stranger}")
            clean()
            Session(cfg, AddrErr(client, True, t0=1_800_000_007.0), True, 1).run()
            err_text = "".join(p.read_text() for p in OUT_DIR.glob("*.jsonl")).lower()
            expect("(b) exception text with addresses -> records carry no address",
                   all(x not in err_text and x[2:] not in err_text for x in addrs + [stranger])
                   and not ADDRESS_RE.search(err_text) and "timed out" in err_text)

            class _CancelStub:
                def cancel_orders(self, order_ids):
                    return CancelOrdersResponse.model_validate(
                        {"canceled": [], "not_canceled": {order_ids[0]: "order can't be found - already canceled"}})
            oid = "0x" + "ab" * 32
            expect("M1: RealEnv.cancel returns only ids the exchange confirms (not_canceled -> [])",
                   RealEnv(_CancelStub(), True).cancel([oid]) == [])
            expect("order status: LIVE / DELAYED / UNMATCHED / unknown count as live; CANCELED*, MATCHED closed",
                   not any(order_closed(s) for s in ("LIVE", "live", "DELAYED", "UNMATCHED", "", None, "WHATEVER"))
                   and all(order_closed(s) for s in ("CANCELED", "CANCELED_EXPIRED_ORDER", "MATCHED",
                                                     "KnownUserOrderStatus.CANCELED")))
        finally:
            urllib.request.urlopen = real_urlopen
            client.close()

        # ---- records carry no key / address; report runs
        text = "".join(p.read_text() for p in OUT_DIR.glob("*.jsonl")).lower()
        expect("records hold no key and no wallet/signer address",
               key[2:] not in text and not any(x in text or x[2:] in text for x in addrs))
        global_out = out.log_path.read_text().lower()
        expect("private key absent from the log", key[2:] not in global_out)
        check("report runs on the selftest records", lambda: cmd_report(argparse.Namespace(files=[], dry_run=False)),
              False)
    finally:
        OUT_DIR, STOP_FILE, LOCK_FILE = real_out, real_stop, real_lock
        if old_key is None:
            os.environ.pop("PM_KEY_FILE", None)
        else:
            os.environ["PM_KEY_FILE"] = old_key
        for f in sorted(tmp.rglob("*"), reverse=True):
            f.unlink() if f.is_file() else f.rmdir()
        tmp.rmdir()
    out(f"selftest: {'ALL PASS' if ok else 'FAILURES'}")
    return 0 if ok else 1


# ----------------------------------------------------------------------------- main
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run", help="run an experiment (dry-run unless --live)")
    r.add_argument("--config", required=True, help="experiments/<name>.json")
    r.add_argument("--live", action="store_true", help="post real orders (default: dry-run)")
    r.add_argument("--max-windows", type=int, default=DEFAULT_MAX_WINDOWS,
                   help=f"windows in this session (default {DEFAULT_MAX_WINDOWS}, at most {HARD_MAX_WINDOWS})")
    rp = sub.add_parser("report", help="summarise record files")
    rp.add_argument("files", nargs="*", help="JSONL files (default: all live files in out/)")
    rp.add_argument("--dry-run", action="store_true", help="summarise dry-run files instead")
    sub.add_parser("selftest", help="offline checks of every cap and refusal")
    return p


def main(argv=None) -> int:
    global out
    out = ExpOut()
    smoke.out = out
    a = build_parser().parse_args(argv)
    live = getattr(a, "live", False)
    out(f"=== exp_bids.py {a.command} {'LIVE' if live else ('dry-run' if a.command == 'run' else '')} "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    try:
        return {"run": cmd_run, "report": cmd_report, "selftest": cmd_selftest}[a.command](a)
    except Refusal as e:
        out(f"REFUSED: {e}")
        return 2
    except Exception as e:  # noqa: BLE001
        out(f"ERROR: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
