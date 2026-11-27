#!/usr/bin/env python3
"""First real-money forward test of one rule ("lead 3", docs/forward-tests.md v1.0, Зацепка 3).

Rule: daily crypto strike markets (above X / between X and Y (and the ladder's two tails) / reach or
dip to X on one date / daily Up or Down with a 24-hour window), taker fee rate 0.01, any asset that has
them. In the window [endDate - 3600 s, market close) the order books of both tokens are read every 5 s.
The favourite is the token with the higher mid. The first poll at which the favourite's best ask is in
[0.95, 0.98) with at least 10 USD on offer at that price AND whose best bid is no further than 0.03 below that
ask (narrow book; coordinator's decision of 2026-11-27 22:15, HANDOFF.md) triggers ONE fill-and-kill (FAK) BUY
of 10 USD with the price limit = that ask. The position is held to resolution. One order per market, never again.
A poll where only the narrow-book condition fails is not a trigger: it is recorded as 'wide-book' and the
market stays eligible on later polls.

The program exists to measure execution: for every order the ask and its size at decision time, the limit
sent, the fill price and size obtained, the fee charged against the formula, the time from decision to the
exchange's acknowledgement, the paper "twin" fill on the book 2 s later (the doc's paper model), and later
the result and the profit or loss.

Official Python SDK only (polymarket-client==0.20.1, enforced through smoke.py). Dry-run by default: the
program reads public data, signs the would-be order locally with a throwaway key and records it (this is
the paper stage). Real orders only with --live.

Subcommands
  run       [--live] [--ticket USD] [--hours H]   the session loop described above
  report    [files...] [--dry-run]                trades, slippage in ticks, fee check, wins/losses, net
  selftest                                         offline: throwaway key, fake clock and exchange, every cap

Hard-coded safety (constants below; no flag or file changes them):
  only FAK BUY orders with a price limit, limit in [0.95, 0.98) and never above 0.98; never a sell, never an
  order without a limit, never a resting order; ticket 10 USD (--ticket may lower it to 5, never raise it);
  one order per market and no retry after any outcome; at most 6 filled trades per UTC day (an order whose
  outcome is unknown counts as filled); at most 2 open tickets at once (an order whose outcome is unknown is
  open); worst-case open exposure: realised losses + open positions + the new ticket <= 30 USD (stop S of the
  protocol); permanent stop once realised losses reach 20 USD or after 2 losing trades, whichever comes first
  (a halt file that only a human removes); live only: a balance floor read from ~/.polymarket-pilot/FLOOR
  (one plain non-negative USD number; missing or malformed -> no live orders) checked at start and before
  every order (free pUSD - orders of the last 5 min - the ticket >= floor); STOP file checked before every
  order; one running instance (lock file); geoblock check at start and at least hourly (live refuses if
  blocked); clock checks before every order (server time offset, clock jumps, stale book, late poll after
  sleep); live start refused if the pUSD balance is below one ticket; a final guard on the signed order
  (side, type, token, spend, price).

Records: out/exp-fav-<YYYYMMDD>.jsonl (live) or out/exp-fav-<YYYYMMDD>.dryrun.jsonl (dry-run), one JSON line
per event. They hold market slugs, token ids, order ids, prices, sizes and times; never a key, an API secret
or a wallet address.

Docs used (read 2026-11-27): docs/forward-tests.md v1.0 (lead 3); https://docs.polymarket.com/trading/place-orders.md
(market orders: FAK with max_price), https://docs.polymarket.com/concepts/order-lifecycle.md (statuses, taker delay),
https://docs.polymarket.com/trading/fees.md (fee = C x rate x p x (1-p), rounded to 5 decimals),
https://docs.polymarket.com/api-reference/data/get-server-time.md (GET /time),
https://docs.polymarket.com/api-reference/geoblock.md, https://docs.polymarket.com/rate-limits.md (/books 500 req/10 s).
"""
from __future__ import annotations

import argparse
import fcntl
import glob
import hashlib
import json
import os
import re
import statistics
import sys
import time
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # smoke.py sits next to this file (python -I)
import smoke  # noqa: E402
from smoke import Refusal  # noqa: E402

VERSION = ("exp_fav 1.2 (2026-11-27, 1.1 + narrow-book condition, 2 open tickets, stop 20 USD / 2 losses, "
           "balance floor)")
RULE_SOURCE = ("docs/forward-tests.md v1.0 (2026-11-27), lead 3 (Зацепка 3), plus the narrow-book condition "
               "(best bid >= best ask - 0.03) of the coordinator's decision 2026-11-27 22:15 (HANDOFF.md)")

# ----------------------------------------------------------------------------- rule (forward-tests.md v1.0)
ASK_MIN = Decimal("0.95")                  # favourite's best ask must be in [ASK_MIN, ASK_MAX)
ASK_MAX = Decimal("0.98")
MIN_LEVEL_USD = Decimal("10")              # at least 10 USD on offer at that ask (doc); also >= the ticket
MAX_SPREAD = Decimal("0.03")               # narrow book: favourite's best bid >= best ask - 0.03 (HANDOFF 22:15)
FEE_RATE = Decimal("0.01")                 # only markets with this taker fee rate
WINDOW_S = 3600                            # window [endDate - 3600 s, market close)
POLL_S = 5                                 # books of every market in the window every 5 s
TWIN_DELTA_S = 2                           # paper model: fill on the book at t_d + 2 s (+ secondsDelay)
UPDOWN_DAY_S = 86400                       # daily Up/Down: a 24-hour window

# ----------------------------------------------------------------------------- hard caps
TICKET_DEFAULT = Decimal("10")             # USD per order
TICKET_MIN = Decimal("5")                  # --ticket may lower it to 5 ...
TICKET_MAX = Decimal("10")                 # ... and never raise it
HARD_MAX_LIMIT = Decimal("0.98")           # no order is ever signed with a limit above this
MAX_FILLED_PER_DAY = 6                     # filled (or unknown) trades per UTC day
MAX_OPEN_TICKETS = 2                       # open (filled or unknown, unresolved) tickets at once (protocol)
STOP_LOSS_USD = Decimal("20")              # permanent stop once realised losses reach this ...
STOP_LOSING_TRADES = 2                     # ... or after this many losing trades, whichever comes first
EXPOSURE_CAP_USD = Decimal("30")           # stop S of the protocol: realised losses + open + new ticket <= this
FEE_ALLOWANCE_USD = Decimal("0.05")        # exposure gate: 30 USD + taker fees (<= 0.005 USD per ticket here)
IN_FLIGHT_S = 300                          # floor check: orders sent this recently are subtracted from the balance
MAX_BOOK_AGE_S = 1.5                       # the book behind a decision must be this fresh when signing
MAX_POLL_LATE_S = 3.0                      # a poll this late after its slot (sleep, stall): no orders from it
CLOCK_JUMP_S = 1.0                         # wall clock vs monotonic clock disagree by more: no orders
MAX_SERVER_OFFSET_S = 2.5                  # |local - server time| above this: no orders (GET /time is 1 s)
GEO_EVERY_S = 1800                         # geoblock check every 30 min ...
GEO_MAX_AGE_S = 3600                       # ... and an order needs one younger than 60 min
SERVER_TIME_EVERY_S = 600
UNIVERSE_EVERY_S = 1200
STATE_EVERY_S = 60                         # refresh accepting/closed of markets in the window
RESULT_EVERY_S = 120
FEE_CHECK_AFTER_S = 45                     # read the charged fee from the activity feed this long after a fill
DELAYED_WAIT_S = 20                        # a 'delayed' FAK is followed this long
RECONCILE_WAIT_S = 120                     # after an unknown post outcome, look for trades this long
HORIZON_S = 26 * 3600                      # universe: markets ending in the next 26 h
BOOKS_CHUNK = 60                           # tokens per POST /books

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "out"                                         # selftest points these to a temp dir
HOME_DIR = Path("~/.polymarket-pilot").expanduser()
STOP_FILE = HOME_DIR / "STOP"                                  # shared with exp_bids.py: stops new orders
HALT_FILE = HOME_DIR / "EXP_FAV_HALT"                          # permanent stop; only a human removes it
LOCK_FILE = HOME_DIR / "exp_fav.lock"
BIDS_LOCK_FILE = HOME_DIR / "exp_bids.live.lock"               # exp_bids.py's live lock: held too in live mode
WATERMARK_FILE = HOME_DIR / "exp_fav.live-records.json"        # how many live decisions were ever written
FLOOR_FILE = HOME_DIR / "FLOOR"                                # balance floor in USD (deposit - 64); live only
FLOOR_RE = re.compile(r"[0-9]+(?:\.[0-9]+)?")
CLOB_TIME_URL = "https://clob.polymarket.com/time"
ADDRESS_RE = re.compile(r"(?<![0-9a-fA-F])0x[0-9a-fA-F]{40}(?![0-9a-fA-F])")
MONTHS = ("january|february|march|april|may|june|july|august|september|october|november|december")
DATE_RE = rf"(?:{MONTHS})-\d{{1,2}}-\d{{4}}"

out: smoke.Out


# ----------------------------------------------------------------------------- small helpers
class FavOut(smoke.Out):
    def __init__(self) -> None:
        super().__init__()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        self.log_path = smoke.OUT / f"exp-fav-{stamp}.log"


def scrub(text) -> str:
    """Text bound for a record or the log: known secrets redacted and no 40-hex address left."""
    return ADDRESS_RE.sub("<address>", out._redact(str(text)))  # noqa: SLF001


def D(x) -> Decimal:
    return x if isinstance(x, Decimal) else Decimal(str(x))


def S(x) -> str | None:
    return None if x is None else str(x)


def utc(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def day_of(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


def fee_formula(shares: Decimal, price: Decimal, rate: Decimal = FEE_RATE) -> Decimal:
    """docs trading/fees.md: fee = C x rate x p x (1 - p), rounded to 5 decimals."""
    return (D(shares) * D(rate) * D(price) * (1 - D(price))).quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)


def fill_from_trades(trades: list[dict], rate: Decimal = FEE_RATE) -> tuple[Decimal, Decimal | None, Decimal | None]:
    """(shares, average fill price, fee by formula) from the exchange's own trade rows of one order.
    The price is the share-weighted mean of the maker legs (the real levels hit); without legs, the rows' prices."""
    shares = sum((D(t["size"]) for t in trades), Decimal(0))
    if shares <= 0:
        return Decimal(0), None, None
    legs = [(D(p), D(s)) for t in trades for p, s in (t.get("legs") or [])]
    leg_sh = sum((s for _, s in legs), Decimal(0))
    if leg_sh > 0:
        avg = sum((p * s for p, s in legs), Decimal(0)) / leg_sh
        fee = sum((fee_formula(s, p, rate) for p, s in legs), Decimal(0))
    else:
        avg = sum((D(t["price"]) * D(t["size"]) for t in trades), Decimal(0)) / shares
        fee = fee_formula(shares, avg, rate)
    return shares, avg, fee


def ticks(diff: Decimal | None, tick: Decimal | None) -> Decimal | None:
    if diff is None or not tick:
        return None
    return (D(diff) / D(tick)).quantize(Decimal("0.01"))


def code_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def acquire_lock(path: Path, held_by: str = "another exp_fav.py session is running"):
    """Exclusive lock held for the life of the process (released on exit, crash or kill)."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    f = open(path, "a")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        f.close()
        raise Refusal(f"{held_by} (lock {path}); one session at a time") from None
    return f


def read_watermark() -> int:
    """Live decisions ever written by this program on this Mac (kept outside the checkout, S1)."""
    if not WATERMARK_FILE.exists():
        return 0
    try:
        return int(json.loads(WATERMARK_FILE.read_text())["live_decisions"])
    except Exception:  # noqa: BLE001
        raise Refusal(f"{WATERMARK_FILE} is not readable; it guards the live records; fix it by hand") from None


def write_watermark(n: int) -> None:
    WATERMARK_FILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = WATERMARK_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps({"live_decisions": n, "records_dir": str(OUT_DIR),
                               "updated_utc": utc(time.time())}) + "\n")
    os.replace(tmp, WATERMARK_FILE)


def count_live_decisions() -> int:
    return sum(1 for r in read_records(record_files(True), strict=True) if r.get("type") == "decision")


def check_ticket(x) -> Decimal:
    t = D(x)
    if not t.is_finite() or t != t.quantize(Decimal("0.01")):
        raise Refusal("--ticket must be a USD amount with at most 2 decimals")
    if t > TICKET_MAX:
        raise Refusal(f"--ticket {t} > {TICKET_MAX}: the ticket can be lowered, never raised")
    if t < TICKET_MIN:
        raise Refusal(f"--ticket {t} < {TICKET_MIN}: below the smallest ticket of this test")
    return t


def read_floor() -> Decimal:
    """The balance floor in USD from FLOOR_FILE: one plain non-negative number (e.g. '36' or '36.50'), nothing
    else on the line. Missing, unreadable or anything else -> Refusal (no live orders)."""
    how = (f"write it with one number, the deposit minus 64 USD, e.g. "
           f"`mkdir -p {FLOOR_FILE.parent} && echo 36 > {FLOOR_FILE}`")
    try:
        if not FLOOR_FILE.exists():
            raise Refusal(f"balance floor file {FLOOR_FILE} is missing; no live orders without it; {how}")
        if not FLOOR_FILE.is_file():
            raise Refusal(f"balance floor file {FLOOR_FILE} is not a regular file; no live orders; {how}")
        text = FLOOR_FILE.read_text(encoding="ascii")
    except Refusal:
        raise
    except Exception as e:  # noqa: BLE001  (permissions, not ASCII, a directory ...)
        raise Refusal(f"balance floor file {FLOOR_FILE} is not readable ({type(e).__name__}); no live orders; "
                      f"{how}") from None
    s = text.strip()
    if not FLOOR_RE.fullmatch(s):
        raise Refusal(f"balance floor file {FLOOR_FILE} must hold one plain non-negative number of USD, got "
                      f"{scrub(s[:40])!r}; no live orders; {how}")
    return Decimal(s)


def check_floor(balance: Decimal, in_flight: Decimal, ticket: Decimal, floor: Decimal) -> None:
    """Refusal if the free pUSD balance minus orders still in flight minus this ticket would fall below the floor."""
    after = D(balance) - D(in_flight) - D(ticket)
    if after < D(floor):
        raise Refusal(f"balance floor: free {D(balance):.2f} - in flight {D(in_flight):.2f} - ticket {ticket} = "
                      f"{after:.2f} USD < floor {D(floor)} USD ({FLOOR_FILE})")


# ----------------------------------------------------------------------------- universe (which markets)
def classify(event_slug: str, market_slug: str, event_tags: set[str]) -> tuple[str, str] | None:
    """(type, asset) for a market of the rule's universe, else None. Structural, by slug, per the doc:
    above / between (+ tails) / reach / dip on ONE date, and daily Up or Down; hourly, 4-hour, weekly and
    monthly series are excluded. The 24-hour check of Up/Down and the fee rate are checked elsewhere."""
    es, ms = event_slug or "", market_slug or ""
    m = re.fullmatch(rf"([a-z0-9]+)-above-on-{DATE_RE}", es)          # no '-3pm-et' suffix: daily only
    if m and re.fullmatch(rf"[a-z0-9]+-above-[a-z0-9]+-on-{DATE_RE}", ms):
        return "above", m.group(1)
    m = re.fullmatch(rf"([a-z0-9]+)-price-on-{DATE_RE}", es)
    if m and ("crypto" in event_tags or "crypto-prices" in event_tags):
        if "-between-" in ms:
            return "between", m.group(1)
        if "-less-than-" in ms or "-greater-than-" in ms:
            return "between-tail", m.group(1)
        return None
    m = re.fullmatch(rf"what-price-will-([a-z0-9]+)-hit-on-{DATE_RE}", es)
    if m and ("crypto" in event_tags or "crypto-prices" in event_tags):
        if re.fullmatch(rf"will-[a-z0-9]+-reach-[a-z0-9]+-on-{DATE_RE}", ms):
            return "reach", m.group(1)
        if re.fullmatch(rf"will-[a-z0-9]+-dip-to-[a-z0-9]+-on-{DATE_RE}", ms):
            return "dip", m.group(1)
        return None
    m = re.fullmatch(r"([a-z0-9]+)-updown-1d-(\d+)", es)
    if m:
        return "updown-daily", m.group(1)
    m = re.fullmatch(rf"([a-z0-9]+)-up-or-down-on-{DATE_RE}", es)
    if m and "crypto-prices" in event_tags:
        return "updown-daily", m.group(1)
    return None


@dataclass
class Mkt:
    key: str                     # condition id
    slug: str
    event_slug: str
    type: str
    asset: str
    end: float                   # endDate, unix seconds
    tokens: dict                 # label -> token id (yes label first)
    index: dict                  # label -> outcome index (0 = yes token)
    rate: Decimal
    seconds_delay: int = 0
    neg_risk: bool = False
    accepting: bool = True
    closed: bool = False
    note: str = ""

    def in_window(self, now: float) -> bool:
        return self.end - WINDOW_S <= now and self.accepting and not self.closed


def market_from_sdk(m, ev_slug: str, ev_tags: set[str], ev_start: float | None) -> tuple[Mkt | None, str]:
    """Build a Mkt from an SDK Market, or (None, reason)."""
    c = classify(ev_slug, m.slug, ev_tags)
    if c is None:
        return None, "not in the rule's universe"
    typ, asset = c
    end = m.state.end_date.timestamp() if m.state.end_date else None
    if end is None:
        return None, "no endDate"
    fs = m.trading.fee_schedule
    rate = D(fs.rate) if fs and fs.rate is not None else None
    if not m.trading.fees_enabled or rate != FEE_RATE or (fs and D(fs.exponent) != 1):
        return None, f"fee rate {rate} (exponent {getattr(fs, 'exponent', None)}) is not {FEE_RATE}"
    if typ == "updown-daily":
        mm = re.fullmatch(r"[a-z0-9]+-updown-1d-(\d+)", ev_slug)
        start = int(mm.group(1)) if mm else ev_start
        if start is not None and abs(end - start - UPDOWN_DAY_S) > 60:
            return None, f"Up/Down window {end - start:.0f} s is not 24 h"
    yes, no = m.outcomes.yes, m.outcomes.no
    tdm = getattr(m.trading, "taker_delay_ms", None)
    if tdm:
        delay = int((int(tdm) + 999) // 1000)            # whole seconds, rounded up
    else:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            delay = int(getattr(m.trading, "seconds_delay", None) or 0)
    mk = Mkt(key=str(m.condition_id), slug=m.slug, event_slug=ev_slug, type=typ, asset=asset, end=end,
             tokens={yes.label: str(yes.token_id), no.label: str(no.token_id)},
             index={yes.label: 0, no.label: 1}, rate=rate,
             seconds_delay=delay, neg_risk=bool(m.state.neg_risk),
             accepting=bool(m.state.accepting_orders), closed=bool(m.state.closed))
    return mk, ""


# ----------------------------------------------------------------------------- books and the trigger
@dataclass
class Book:
    token: str
    asks: list                   # [(price, size)] ascending (best first)
    bids: list                   # [(price, size)] descending (best first)
    tick: Decimal
    min_size: Decimal
    received: float              # local wall time the response arrived
    server_ts: float | None = None

    @property
    def best_ask(self):
        return self.asks[0][0] if self.asks else None

    @property
    def best_bid(self):
        return self.bids[0][0] if self.bids else None

    @property
    def ask_size(self) -> Decimal:
        a = self.best_ask
        return sum((s for p, s in self.asks if p == a), Decimal(0)) if a is not None else Decimal(0)

    @property
    def mid(self):
        if self.best_ask is None or self.best_bid is None:
            return None
        return (self.best_ask + self.best_bid) / 2

    def top(self, n: int = 10) -> dict:
        return {"asks": [[str(p), str(s)] for p, s in self.asks[:n]],
                "bids": [[str(p), str(s)] for p, s in self.bids[:n]]}


def book_from_sdk(b, received: float) -> Book:
    asks = sorted(((D(lv.price), D(lv.size)) for lv in b.asks), key=lambda x: x[0])
    bids = sorted(((D(lv.price), D(lv.size)) for lv in b.bids), key=lambda x: x[0], reverse=True)
    return Book(str(b.asset_id), asks, bids, D(b.tick_size), D(b.min_order_size or smoke.DEFAULT_MIN_SIZE),
                received, b.timestamp.timestamp() if b.timestamp else None)


def favourite(m: Mkt, books: dict) -> tuple[str | None, str]:
    """Label of the token with the higher mid ((bid + ask) / 2), or (None, reason)."""
    labels = list(m.tokens)
    mids = {lb: (books[m.tokens[lb]].mid if m.tokens[lb] in books else None) for lb in labels}
    a, b = labels
    if mids[a] is not None and mids[b] is not None:
        if mids[a] == mids[b]:
            return None, "equal mids"
        return (a if mids[a] > mids[b] else b), "mid"
    one = a if mids[a] is not None else (b if mids[b] is not None else None)
    if one is None:
        return None, "no two-sided book"
    other = b if one == a else a
    if mids[one] == Decimal("0.5"):
        return None, "one-sided book at 0.50"
    return (one if mids[one] > Decimal("0.5") else other), "mid of one token (other book one-sided)"


WIDE_BOOK = "wide book"                    # prefix of trigger()'s reason when only the narrow-book condition fails


def spread_of(book: Book) -> Decimal | None:
    """best ask - best bid of one token's book, or None if a side is empty."""
    if book is None or book.best_ask is None or book.best_bid is None:
        return None
    return book.best_ask - book.best_bid


def trigger(book: Book, ticket: Decimal) -> tuple[bool, str]:
    """The doc's trigger on the favourite's book: best ask in [0.95, 0.98) and >= 10 USD (and >= ticket) there,
    plus the narrow-book condition: best bid no further than MAX_SPREAD (0.03) below that ask."""
    a = book.best_ask
    if a is None:
        return False, "no ask"
    if not (ASK_MIN <= a < ASK_MAX):
        return False, f"ask {a} outside [{ASK_MIN}, {ASK_MAX})"
    usd = a * book.ask_size
    if usd < max(MIN_LEVEL_USD, ticket):
        return False, f"only {usd:.2f} USD at the ask {a}"
    b = book.best_bid
    if b is None:
        return False, f"{WIDE_BOOK}: no bid under the ask {a} (needs bid >= ask - {MAX_SPREAD})"
    if a - b > MAX_SPREAD:
        return False, f"{WIDE_BOOK}: bid {b} is {a - b} below the ask {a} (max {MAX_SPREAD})"
    return True, ""


def paper_fill(book: Book, limit: Decimal, usd: Decimal, rate: Decimal = FEE_RATE) -> dict:
    """The doc's paper model: walk the asks upward while price <= limit until `usd` is spent; fee per level."""
    left, shares, cost, fee = D(usd), Decimal(0), Decimal(0), Decimal(0)
    levels = []
    for p, s in book.asks:
        if p > limit or left <= 0:
            break
        take = min(s, (left / p).quantize(Decimal("0.0001"), rounding="ROUND_DOWN"))
        if take <= 0:
            break
        shares += take
        cost += take * p
        fee += fee_formula(take, p, rate)
        left -= take * p
        levels.append([str(p), str(take)])
    filled = shares >= book.min_size
    return {"filled": filled, "shares": str(shares if filled else 0),
            "avg_price": S((cost / shares).quantize(Decimal("0.000001")) if filled else None),
            "notional": str(cost if filled else 0), "fee": str(fee if filled else 0), "levels": levels,
            "best_ask": S(book.best_ask), "ask_size": str(book.ask_size), "min_size": str(book.min_size),
            "best_bid": S(book.best_bid), "spread": S(spread_of(book)),
            "reason": "" if filled else f"fillable {shares} < market minimum {book.min_size} (missed)"}


# ----------------------------------------------------------------------------- final guard on the signed order
def guard_signed(signed, token: str, ticket: Decimal, limit: Decimal) -> tuple[Decimal, Decimal]:
    """Last check on the signed order itself. Returns (spend in pUSD, implied price). Raises Refusal."""
    spend = smoke.guard_signed_buy(signed, ticket)          # side BUY and maker amount <= ticket
    if str(signed.order_type) != "FAK":
        raise Refusal(f"internal: signed order type {signed.order_type} is not FAK; not posted")
    if bool(signed.post_only):
        raise Refusal("internal: signed FAK is post-only; not posted")
    if str(signed.token_id) != str(token):
        raise Refusal("internal: signed token differs from the favourite's token; not posted")
    if int(signed.expiration or 0) != 0:
        raise Refusal("internal: a FAK order carries no expiration; not posted")
    if not (ASK_MIN <= limit < ASK_MAX) or limit > HARD_MAX_LIMIT:
        raise Refusal(f"internal: limit {limit} outside [{ASK_MIN}, {ASK_MAX}); not posted")
    shares = D(signed.taker_amount) / smoke.USDC_UNIT
    if shares <= 0:
        raise Refusal("internal: signed order buys no shares; not posted")
    implied = spend / shares
    if implied > HARD_MAX_LIMIT or implied >= limit + Decimal("0.0001"):
        raise Refusal(f"internal: signed price {implied:.6f} above the limit {limit}; not posted")
    return spend, implied


# ----------------------------------------------------------------------------- records and the ledger
def records_path(day: str, live: bool) -> Path:
    return OUT_DIR / f"exp-fav-{day.replace('-', '')}{'.jsonl' if live else '.dryrun.jsonl'}"


def append_record(rec: dict, live: bool, ts: float) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    line = scrub(json.dumps(rec, sort_keys=True, default=str))
    with open(records_path(day_of(ts), live), "a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()
        os.fsync(f.fileno())


def record_files(live: bool) -> list[str]:
    pat = "exp-fav-*.jsonl" if live else "exp-fav-*.dryrun.jsonl"
    return sorted(p for p in glob.glob(str(OUT_DIR / pat)) if p.endswith(".dryrun.jsonl") != live)


def read_records(paths, strict: bool) -> list[dict]:
    rows = []
    for p in paths:
        with open(p, encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    if strict:
                        raise Refusal(f"record file {p} line {i} is not valid JSON; fix or move it before a "
                                      f"live run (the ledger must be complete)") from None
    return rows


@dataclass
class Ledger:
    consumed: set = field(default_factory=set)        # markets with a decision (one order per market)
    trades: dict = field(default_factory=dict)        # key -> summary
    halted_at: float | None = None
    cleared_at: float | None = None

    def filled_on(self, day: str) -> int:
        return sum(1 for t in self.trades.values() if t["day"] == day and t["state"] in ("filled", "unknown"))

    def open_count(self) -> int:
        """Open tickets: filled or unknown (a decision without an outcome counts) and not resolved yet."""
        return sum(1 for t in self.trades.values() if t["state"] in ("filled", "unknown") and not t["resolved"])

    def in_flight(self, now: float, within: float = IN_FLIGHT_S) -> Decimal:
        """Tickets of orders sent in the last `within` seconds (the balance may not show them yet)."""
        return sum((t["ticket"] for t in self.trades.values()
                    if t.get("t_decision") is not None and now - t["t_decision"] <= within), Decimal(0))

    def open_exposure(self) -> Decimal:
        return sum((t["worst_cost"] for t in self.trades.values()
                    if t["state"] in ("filled", "unknown") and not t["resolved"]), Decimal(0))

    def losses(self) -> tuple[int, Decimal]:
        """Losing trades and realised loss (USD) since the last time the halt file was removed by hand.
        A split result that lost money counts as a losing trade (conservative)."""
        n, usd = 0, Decimal(0)
        for t in self.trades.values():
            if t["resolved"] and (t["won"] is False or t["loss"] > 0) and t["state"] in ("filled", "unknown"):
                if self.cleared_at is not None and (t["result_t"] or 0) <= self.cleared_at:
                    continue
                n += 1
                usd += t["loss"]
        return n, usd


def build_ledger(rows: list[dict]) -> Ledger:
    L = Ledger()
    by = defaultdict(dict)
    for r in rows:
        typ = r.get("type")
        if typ in ("decision", "order", "result", "fee") and r.get("key"):
            if typ == "decision" and r.get("sent") is False:
                L.consumed.add(r["key"])              # a decision skipped by a cap still consumes the market
                continue
            if typ == "order" and r.get("post") == "late-check" and "order" in by[r["key"]]:
                # after resolution, three exchange reads (CLOB trades, activity feed, token balance) settled an
                # order whose fill was unknown: unfilled, filled at the real cost, or still unknown (worst case)
                by[r["key"]]["order"] = {**by[r["key"]]["order"], "fill_state": r["fill_state"],
                                         "filled_shares": r["filled_shares"], "cost": r["cost"]}
                continue
            by[r["key"]].setdefault(typ, r)
            if typ == "decision":
                L.consumed.add(r["key"])
        elif typ == "halt":
            L.halted_at = max(L.halted_at or 0, r["t"])
        elif typ == "halt-cleared":
            L.cleared_at = max(L.cleared_at or 0, r["t"])
    for k, g in by.items():
        dec = g.get("decision")
        if dec is None:
            continue
        ticket = D(dec["ticket"])
        o = g.get("order")
        if o is None:                                  # decided, then crashed before the outcome was written
            state, cost, shares = "unknown", ticket, None
        else:
            state = o["fill_state"]
            shares = D(o["filled_shares"]) if o.get("filled_shares") is not None else None
            cost = D(o["cost"]) if o.get("cost") is not None else ticket
        res = g.get("result")
        won = None
        loss = Decimal(0)
        result_t = None
        resolved = False
        if res is not None and res.get("winner") is not None and state in ("filled", "unknown"):
            result_t = res["t"]
            resolved = True
            won = res["winner"] == dec["outcome"]
            if res.get("winner_is_split"):
                # S8: a split is resolved too (it leaves the open exposure); loss = cost - payout x shares
                won = None
                payout = D(res.get("our_payout") or "0.5")
                if state == "filled" and shares is not None:
                    loss = max(Decimal(0), cost - payout * shares)
                else:
                    loss = ticket                                     # unknown fill: worst case
            elif not won:
                loss = cost if state == "filled" else ticket          # unknown fill: worst case
        L.trades[k] = {"day": dec["day"], "state": state, "shares": shares, "worst_cost": cost if state == "filled" else ticket,
                       "won": won, "loss": loss, "result_t": result_t, "outcome": dec["outcome"], "resolved": resolved,
                       "ticket": ticket, "t_decision": dec.get("t_decision")}
    return L


def ledger_now(live: bool) -> Ledger:
    return build_ledger(read_records(record_files(live), strict=live))


def halt_reason(L: Ledger) -> str | None:
    n, usd = L.losses()
    if n >= STOP_LOSING_TRADES:
        return f"{n} losing trades (stop at {STOP_LOSING_TRADES})"
    if usd >= STOP_LOSS_USD:
        return f"realised losses {usd:.2f} USD (stop at {STOP_LOSS_USD})"
    return None


def check_caps(L: Ledger, key: str, day: str, ticket: Decimal, exchange_filled_today: int = 0) -> None:
    """Every money cap that applies before an order. Raises Refusal (the market is then consumed)."""
    if HALT_FILE.exists():
        raise Refusal(f"halt file present ({HALT_FILE}): permanent stop")
    if STOP_FILE.exists():
        raise Refusal(f"STOP file present ({STOP_FILE}): no new orders")
    if key in L.consumed:
        raise Refusal("this market already had its one decision")
    why = halt_reason(L)
    if why:
        raise Refusal(f"stop condition reached: {why}")
    n = max(L.filled_on(day), exchange_filled_today)
    if n >= MAX_FILLED_PER_DAY:
        raise Refusal(f"{n} filled (or unknown) trades today (UTC); cap {MAX_FILLED_PER_DAY}")
    n_open = L.open_count()
    if n_open >= MAX_OPEN_TICKETS:
        raise Refusal(f"{n_open} open tickets (filled or unknown, not resolved); cap {MAX_OPEN_TICKETS} open at once")
    _, lost = L.losses()
    exposure = L.open_exposure()
    if lost + exposure + ticket > EXPOSURE_CAP_USD + FEE_ALLOWANCE_USD:
        raise Refusal(f"worst case: realised losses {lost:.2f} + open {exposure:.2f} + ticket {ticket} > "
                      f"{EXPOSURE_CAP_USD} USD")


# ----------------------------------------------------------------------------- exchange adapter (real)
class RealEnv:
    """Public data through the SDK's public client; signing through an SDK SecureClient (offline client with a
    throwaway key in dry-run, live client with --live); posting only with --live."""

    def __init__(self, client, live: bool):
        from polymarket import PublicClient
        self.c = client
        self.pub = PublicClient()
        self.live = live

    def wall(self) -> float:
        return time.time()

    def mono(self) -> float:
        return time.monotonic()

    def sleep(self, s: float) -> None:
        time.sleep(max(0.0, s))

    def close(self) -> None:
        for c in (self.pub, self.c):
            try:
                c.close()
            except Exception:  # noqa: BLE001
                pass

    # --- public data
    def discover(self, now: float) -> tuple[list[Mkt], list[dict]]:
        lo = datetime.fromtimestamp(now - WINDOW_S, timezone.utc)
        hi = datetime.fromtimestamp(now + HORIZON_S, timezone.utc)
        seen, found, rejected = set(), [], []
        for tag in ("multi-strikes", "hit-price", "crypto-prices"):
            for e in self.pub.list_events(closed=False, tag_slug=tag, end_date_min=lo, end_date_max=hi,
                                          page_size=100).iter_items():
                if e.slug in seen:
                    continue
                seen.add(e.slug)
                if re.search(r"-updown-(5m|15m|1h|4h)-", e.slug or ""):
                    continue
                tags = {t.slug for t in (e.tags or ())}
                ev_start = None
                for m in (e.markets or ()):
                    mk, why = market_from_sdk(m, e.slug, tags, ev_start)
                    if mk is not None:
                        found.append(mk)
                    elif why != "not in the rule's universe":
                        rejected.append({"slug": m.slug, "why": why})
        return found, rejected

    def refresh(self, keys: list[str]) -> dict:
        """key -> (accepting, closed) for up to 100 condition ids."""
        res = {}
        for i in range(0, len(keys), 50):
            for m in self.pub.list_markets(condition_ids=keys[i:i + 50], page_size=100).iter_items():
                res[str(m.condition_id)] = (bool(m.state.accepting_orders), bool(m.state.closed))
            missing = [k for k in keys[i:i + 50] if k not in res]
            if missing:
                for m in self.pub.list_markets(condition_ids=missing, closed=True, page_size=100).iter_items():
                    res[str(m.condition_id)] = (bool(m.state.accepting_orders), bool(m.state.closed))
        return res

    def books(self, tokens: list[str]) -> dict:
        res = {}
        for i in range(0, len(tokens), BOOKS_CHUNK):
            got = self.pub.get_order_books(asset_ids=tokens[i:i + BOOKS_CHUNK])
            t = time.time()
            for b in got:
                res[str(b.asset_id)] = book_from_sdk(b, t)
        return res

    def server_time(self) -> tuple[float, float]:
        """(offset local - server in seconds, round trip in seconds) from the CLOB's GET /time."""
        import httpx
        t0 = time.time()
        r = httpx.get(CLOB_TIME_URL, timeout=10)
        t1 = time.time()
        r.raise_for_status()
        server = float(r.json() if not isinstance(r.json(), dict) else r.json().get("time"))
        return (t0 + t1) / 2 - server, t1 - t0

    def geoblock(self) -> dict:
        """Two checks of the official endpoint: smoke.py's (urllib) and httpx (the SDK's HTTP stack, which reads
        only environment proxies). Both must say not blocked."""
        import httpx
        r = httpx.get(smoke.GEOBLOCK_URL, timeout=15, headers={"User-Agent": "pm-pilot-expfav/1.0"})
        r.raise_for_status()
        g = r.json()
        res = {"blocked": g.get("blocked"), "country": g.get("country")}
        try:
            smoke.geoblock_or_refuse()
            res["urllib_blocked"] = False
        except Refusal:
            res["urllib_blocked"] = True
        return res

    def result(self, m: Mkt) -> tuple[str | None, bool]:
        """(winning label or None if not resolved yet, split?)."""
        labels = {v: k for k, v in m.index.items()}
        for r in self.pub.get_resolutions(condition_ids=[m.key]):
            if str(r.status) == "resolved" and r.payouts:
                p0, p1 = r.payouts
                if p0 == 1 and p1 == 0:
                    return labels[0], False
                if p1 == 1 and p0 == 0:
                    return labels[1], False
                return f"split {p0}/{p1}", True
        for mm in self.pub.list_markets(condition_ids=[m.key], closed=True, page_size=10).iter_items():
            if mm.state.closed:
                y, n = D(mm.outcomes.yes.price or 0), D(mm.outcomes.no.price or 0)
                if y == 1 and n == 0:
                    return labels[0], False
                if n == 1 and y == 0:
                    return labels[1], False
        return None, False

    # --- signing and the account
    def warm(self, m: Mkt) -> None:
        """Live: load the SDK's market metadata (tick, fee) when the window opens, so signing needs no network."""
        if self.live:
            for tok in m.tokens.values():
                smoke.market_info(self.c, tok)

    def register(self, m: Mkt, tick: Decimal) -> None:
        """Dry-run only: give the offline client the market metadata it needs to sign (no network)."""
        if not self.live:
            _register_offline_market(self.c, tuple(m.tokens.values()), m.key, tick, m.rate, m.neg_risk)

    def sign(self, token: str, amount: Decimal, limit: Decimal):
        return self.c.create_market_order(asset_id=token, side="BUY", amount=amount, max_price=limit,
                                          order_type="FAK")

    def post(self, signed) -> dict:
        if not self.live:
            raise Refusal("internal: post called in dry-run")
        from polymarket.errors import RequestRejectedError
        try:
            r = self.c.post_order(signed)
        except RequestRejectedError as e:
            # a definite 4xx answer: not placed. 408/429 and 5xx stay unknown (re-raised).
            if 400 <= int(e.status) < 500 and int(e.status) not in (408, 429):
                return {"ok": False, "code": str(getattr(e, "code", "") or f"HTTP {e.status}"), "message": str(e)}
            raise
        if r.ok:
            return {"ok": True, "order_id": str(r.order_id), "status": str(r.status), "making": D(r.making_amount),
                    "taking": D(r.taking_amount), "trade_ids": [str(t) for t in r.trade_ids]}
        return {"ok": False, "code": str(r.code), "message": str(r.message)}

    def order_state(self, order_id: str) -> dict:
        o = self.c.get_order(order_id=order_id)
        return {"status": str(o.status), "size_matched": D(o.size_matched), "price": D(o.price)}

    def cancel(self, order_id: str) -> bool:
        if not self.live:
            return False
        r = self.c.cancel_orders(order_ids=[order_id])
        return order_id in {str(i) for i in r.canceled}

    def trades(self, token: str, since: float) -> list[dict]:
        """Taker trades of this account on `token` matched at or after `since`."""
        res = []
        after = str(int(since) - 5)
        for t in self.c.list_account_trades(asset_id=token, after=after).iter_items():
            if t.trader_side != "TAKER" or t.side != "BUY":
                continue
            if str(t.status).upper().split(".")[-1] == "FAILED":   # S4: terminal, settlement failed: no fill
                continue
            legs = []
            for mo in t.maker_orders:
                p = D(mo.price) if str(mo.asset_id) == str(token) else 1 - D(mo.price)   # complement BUY maker
                legs.append([str(p), str(D(mo.matched_amount))])
            res.append({"id": str(t.id), "taker_order_id": str(t.taker_order_id), "price": str(t.price),
                        "size": str(t.size), "status": str(t.status), "fee_rate_bps": str(t.fee_rate_bps),
                        "match_time": t.matched_at.timestamp() if t.matched_at else None,
                        "tx": t.transaction_hash, "legs": legs})
        return res

    def activity(self, m: Mkt, token: str, since: float) -> list[dict]:
        """The account's TRADE activity rows on this market (public data API; amount includes the fee)."""
        res = []
        for a in self.pub.list_activity(user=str(self.c.wallet), condition_id=m.key, activity_types=["TRADE"],
                                        start=int(since) - 60).iter_items():
            if getattr(a, "asset_id", None) is None or str(a.asset_id) != str(token):
                continue
            if str(getattr(a, "side", "")) != "BUY":
                continue
            res.append({"amount": str(a.amount), "shares": str(a.shares), "price": str(a.price),
                        "t": a.timestamp.timestamp(), "tx": str(a.transaction_hash)})
        return res

    def balance(self) -> Decimal:
        return Decimal(self.c.get_balance_allowance(asset_type="COLLATERAL").balance) / smoke.USDC_UNIT

    def token_balance(self, token: str) -> Decimal:
        """Shares of `token` the account holds (S3: the authoritative third source after an unknown outcome).
        Raises if neither asset type could be read, so an unreadable balance never looks like zero."""
        best, read = Decimal(0), False
        for typ in ("CONDITIONAL", "CONDITIONAL-V2"):
            try:
                b = Decimal(self.c.get_balance_allowance(asset_type=typ, token_id=token).balance) / smoke.USDC_UNIT
                best, read = max(best, b), True
            except Exception:  # noqa: BLE001
                continue
        if not read:
            raise RuntimeError("token balance not readable")
        return best

    def account_traded(self, tokens: list[str]) -> bool:
        for tok in tokens:
            for _ in self.c.list_account_trades(asset_id=tok).iter_items():
                return True
        return False

    def fills_today(self, midnight: float) -> int:
        ids = set()
        for t in self.c.list_account_trades(after=str(int(midnight))).iter_items():
            if t.trader_side == "TAKER" and t.side == "BUY":
                ids.add(str(t.taker_order_id))
        return len(ids)

    def closed_only(self) -> bool:
        return bool(self.c.get_closed_only_mode())

    def approvals_ok(self) -> bool | None:
        """post_order does not repair missing approvals (unlike place_*). None: the SDK could not tell."""
        try:
            return bool(self.c.get_trading_approvals_state().is_fully_approved)
        except Exception:  # noqa: BLE001
            return None


def _register_offline_market(client, tokens, cond, tick: Decimal, rate: Decimal, neg_risk: bool) -> None:
    from polymarket._internal.actions.orders.market_data import MarketInfo, PlatformFeeInfo
    ctx = client._ctx  # noqa: SLF001
    info = MarketInfo(fee_info=PlatformFeeInfo(rate=D(rate), exponent=Decimal(1)), neg_risk=bool(neg_risk),
                      tick_size=D(tick), token_ids=frozenset(tokens))
    for t in tokens:
        ctx.order_metadata._conditions.set(t, cond)  # noqa: SLF001
    ctx.order_metadata._markets.set(cond, info)  # noqa: SLF001


# ----------------------------------------------------------------------------- the session
class Session:
    def __init__(self, env, live: bool, ticket: Decimal, hours: float | None):
        self.env, self.live, self.ticket = env, live, ticket
        self.session = uuid.uuid4().hex[:12]
        self.mode = "live" if live else "dry-run"
        self.markets: dict[str, Mkt] = {}
        self.decided: dict[str, dict] = {}            # key -> open decision context (result pending)
        self.stopping = False
        self.halted = False
        self.t_end = env.wall() + hours * 3600 if hours else None
        self.last = defaultdict(lambda: -1e18)        # task -> mono time last done
        self.geo_ok_at: float | None = None           # mono time of the last geoblock pass
        self.geo_blocked = None
        self.offset: float | None = None              # local - server, seconds
        self.prev_wall = self.prev_mono = None
        self.next_poll = None
        self.near_seen: dict[str, float] = {}
        self.wide_seen: dict[str, float] = {}         # key -> mono time of the last 'wide-book' record
        self.wide_polls: dict[str, int] = {}          # key -> wide-book polls since that record
        self.tech_seen: dict[str, float] = {}
        self.polls = 0
        self.in_window_seen: set = set()
        self.exchange_fills: dict[str, int] = {}      # UTC day -> taker BUY orders the exchange shows (live)

    # -- plumbing
    def rec(self, typ: str, **kw) -> dict:
        t = self.env.wall()
        r = {"type": typ, "t": t, "t_utc": utc(t), "mode": self.mode, "session": self.session, **kw}
        append_record(r, self.live, t)
        if self.live and typ == "decision":           # S1: the watermark outside the checkout follows the records
            write_watermark(max(count_live_decisions(), read_watermark()))
        return r

    def ledger(self) -> Ledger:
        return ledger_now(self.live)

    def due(self, task: str, every: float) -> bool:
        now = self.env.mono()
        if now - self.last[task] >= every:
            self.last[task] = now
            return True
        return False

    # -- periodic checks
    def check_geoblock(self, force: bool = False) -> None:
        if not force and not self.due("geo", GEO_EVERY_S):
            return
        if force:
            self.last["geo"] = self.env.mono()
        try:
            g = self.env.geoblock()
        except Exception as e:  # noqa: BLE001
            self.geo_blocked = None
            out(f"  geoblock check failed: {scrub(type(e).__name__)}; no orders until a check passes")
            self.rec("geoblock", ok=False, error=scrub(type(e).__name__))
            return
        blocked = g.get("blocked") is not False or g.get("urllib_blocked") is True
        self.geo_blocked = blocked
        self.rec("geoblock", ok=True, blocked=g.get("blocked"), urllib_blocked=g.get("urllib_blocked"),
                 country=g.get("country"))
        out(f"  geoblock: blocked={g.get('blocked')} (second check {g.get('urllib_blocked')}) country={g.get('country')}"
            + ("" if not blocked else ("  -> LIVE ORDERS REFUSED" if self.live else "  -> a live run would be refused here")))
        if not blocked:
            self.geo_ok_at = self.env.mono()
        elif self.live:
            self.begin_stop("geoblocked IP")

    def check_server_time(self, force: bool = False) -> None:
        if not force and not self.due("time", SERVER_TIME_EVERY_S):
            return
        if force:
            self.last["time"] = self.env.mono()
        try:
            off, rtt = self.env.server_time()
            self.offset = off
            self.rec("clock", offset_s=round(off, 3), rtt_ms=round(rtt * 1000))
            out(f"  clock: local - server {off:+.2f} s (GET /time, 1 s resolution), round trip {rtt * 1000:.0f} ms"
                + ("  -> NO ORDERS until the clock is fixed" if abs(off) > MAX_SERVER_OFFSET_S else ""))
        except Exception as e:  # noqa: BLE001
            self.offset = None
            self.rec("clock", error=scrub(type(e).__name__))
            out(f"  clock check failed ({scrub(type(e).__name__)}); no orders until it passes")

    def refresh_universe(self, force: bool = False) -> None:
        if not force and not self.due("universe", UNIVERSE_EVERY_S):
            return
        if force:
            self.last["universe"] = self.env.mono()
        now = self.env.wall()
        try:
            found, rejected = self.env.discover(now)
        except Exception as e:  # noqa: BLE001
            out(f"  universe refresh failed ({scrub(type(e).__name__ + ': ' + str(e))[:200]}); keeping the old list")
            return
        new = 0
        for m in found:
            if m.key not in self.markets:
                new += 1
                self.markets[m.key] = m
            else:
                old = self.markets[m.key]
                old.accepting, old.closed = m.accepting, m.closed
        rows = sorted(((m.end, m.type, m.asset, m.slug, m.accepting and not m.closed) for m in found
                       if m.end >= now - WINDOW_S))
        self.rec("universe", markets=[{"slug": s, "type": t, "asset": a, "end_utc": utc(e), "open": o}
                                      for e, t, a, s, o in rows],
                 rejected=rejected[:50], n_rejected=len(rejected))
        ends = Counter((utc(e)[:16], t) for e, t, a, s, o in rows)
        opn = Counter((utc(e)[:16], t) for e, t, a, s, o in rows if o)
        assets = Counter(a for e, t, a, s, o in rows)
        out(f"  universe: {len(rows)} markets end in the next {HORIZON_S // 3600} h ({new} new; "
            f"{sum(opn.values())} accepting orders); {len(rejected)} crypto markets rejected (fee rate / window); "
            f"assets {dict(assets)}")
        for (end, typ), n in sorted(ends.items()):
            out(f"    end {end}Z  {typ:13} {n:3d} ({opn[(end, typ)]:3d} open)   window opens "
                f"{utc(datetime.fromisoformat(end).replace(tzinfo=timezone.utc).timestamp() - WINDOW_S)[:16]}Z")

    def refresh_states(self) -> None:
        keys = [k for k, m in self.markets.items() if m.end - WINDOW_S - 120 <= self.env.wall() and not m.closed]
        if not keys or not self.due("state", STATE_EVERY_S):
            return
        try:
            st = self.env.refresh(keys)
        except Exception as e:  # noqa: BLE001
            out(f"  market state refresh failed ({scrub(type(e).__name__)})")
            return
        for k, (acc, cl) in st.items():
            m = self.markets.get(k)
            if m and (m.accepting != acc or m.closed != cl):
                m.accepting, m.closed = acc, cl
                out(f"  {m.slug}: accepting={acc} closed={cl}")

    # -- the poll
    def clock_ok(self, late: float) -> tuple[bool, str]:
        w, mo = self.env.wall(), self.env.mono()
        why = ""
        if self.prev_wall is not None:
            jump = (w - self.prev_wall) - (mo - self.prev_mono)
            if abs(jump) > CLOCK_JUMP_S:
                why = f"clock jump {jump:+.1f} s between polls"
                self.check_server_time(force=True)
        self.prev_wall, self.prev_mono = w, mo
        if not why and late > MAX_POLL_LATE_S:
            why = f"poll {late:.1f} s late (sleep or stall)"
        if not why and (self.offset is None or abs(self.offset) > MAX_SERVER_OFFSET_S):
            why = f"server clock offset {self.offset if self.offset is None else round(self.offset, 2)} s"
        return (why == ""), why

    def poll(self, late: float = 0.0) -> None:
        self.polls += 1
        now = self.env.wall()
        win = [m for m in self.markets.values() if m.in_window(now) and m.key not in self.decided]
        ready = []
        for m in win:
            if m.key not in self.in_window_seen:
                if not self.enter_window(m):
                    continue
                self.in_window_seen.add(m.key)
            ready.append(m)
        L = self.ledger()
        win = [m for m in ready if m.key not in L.consumed]
        if not win:
            return
        tokens = [t for m in win for t in m.tokens.values()]
        try:
            books = self.env.books(tokens)
        except Exception as e:  # noqa: BLE001
            out(f"  books read failed ({scrub(type(e).__name__)}); next poll in {POLL_S} s")
            return
        clock_good, clock_why = self.clock_ok(late)
        hits = []
        for m in win:
            fav, how = favourite(m, books)
            if fav is None:
                continue
            bk = books.get(m.tokens[fav])
            if bk is None:
                continue
            ok, why = trigger(bk, self.ticket)
            if ok:
                hits.append((m, fav, how, bk, books))
            elif why.startswith(WIDE_BOOK):
                self.wide(m, fav, bk, why)
            else:
                self.near(m, fav, bk, why)
        twins = []
        for m, fav, how, bk, bks in hits:          # phase 1: every decision and order of this poll, at once
            if self.stopping:
                break
            job = self.decide(m, fav, how, bk, bks, clock_good, clock_why)
            if job is not None:
                twins.append(job)
        if twins:                                  # phase 2: paper twins on the books 2 s (+ delay) later
            self.do_twins(twins)

    def enter_window(self, m: Mkt) -> bool:
        """First sight of a market in its window. False: not ready (checked again on the next poll)."""
        out(f"  {m.slug}: window open ({m.type}, {m.asset}, ends {utc(m.end)[:19]}Z)")
        if self.live:
            try:
                if self.env.account_traded(list(m.tokens.values())):
                    self.rec("decision", key=m.key, slug=m.slug, sent=False, day=day_of(self.env.wall()),
                             reason="the account already traded this market (one position per market)",
                             ticket=str(self.ticket), outcome=None)
                    out(f"    {m.slug}: the account already traded this market: skipped for good")
                self.env.warm(m)
            except Exception as e:  # noqa: BLE001
                out(f"    {m.slug}: own-trades / metadata check failed ({scrub(type(e).__name__)}); not traded "
                    f"until it passes")
                return False
        return True

    def near(self, m: Mkt, fav: str, bk: Book, why: str) -> None:
        """Doc: record the cases where every condition but the price held (at most once a minute per market)."""
        a = bk.best_ask
        if a is None or not (Decimal("0.92") <= a < Decimal("0.995")) or ASK_MIN <= a < ASK_MAX and "USD" not in why:
            return
        now = self.env.mono()
        if now - self.near_seen.get(m.key, -1e18) < 60:
            return
        self.near_seen[m.key] = now
        self.rec("near", key=m.key, slug=m.slug, market_type=m.type, asset=m.asset, outcome=fav, token=m.tokens[fav],
                 best_ask=str(a), ask_size=str(bk.ask_size), best_bid=S(bk.best_bid), spread=S(spread_of(bk)), why=why,
                 seconds_to_end=round(m.end - self.env.wall()))

    def wide(self, m: Mkt, fav: str, bk: Book, why: str) -> None:
        """Every condition of the trigger held except the narrow book (bid >= ask - 0.03). Not a trigger: the market
        is NOT consumed and later polls check it again. Recorded with its own reason ('wide-book'), at most once a
        minute per market, with the number of such polls since the last record."""
        self.wide_polls[m.key] = self.wide_polls.get(m.key, 0) + 1
        now = self.env.mono()
        if now - self.wide_seen.get(m.key, -1e18) < 60:
            return
        self.wide_seen[m.key] = now
        n, self.wide_polls[m.key] = self.wide_polls[m.key], 0
        a = bk.best_ask
        self.rec("wide-book", key=m.key, slug=m.slug, market_type=m.type, asset=m.asset, outcome=fav,
                 token=m.tokens[fav], best_ask=str(a), ask_size=str(bk.ask_size),
                 ask_usd=str((a * bk.ask_size).quantize(Decimal("0.01"))), best_bid=S(bk.best_bid),
                 spread=S(spread_of(bk)), max_spread=str(MAX_SPREAD), why=why, polls_since_last=n,
                 seconds_to_end=round(m.end - self.env.wall()), book=bk.top(10))
        out(f"    {m.slug}: ask {a} x {bk.ask_size} in range but NOT a trigger: {why} (re-checked next poll)")

    def decide(self, m: Mkt, fav: str, how: str, bk: Book, books: dict, clock_good: bool, clock_why: str) -> None:
        env = self.env
        t_d = bk.received                                  # decision time: arrival of the book that triggered
        mono_d = env.mono() - (env.wall() - t_d)
        token = m.tokens[fav]
        ask, size, tick = bk.best_ask, bk.ask_size, bk.tick
        other = books.get(m.tokens[[lb for lb in m.tokens if lb != fav][0]])
        base = dict(key=m.key, slug=m.slug, event_slug=m.event_slug, market_type=m.type, asset=m.asset,
                    end_utc=utc(m.end), seconds_to_end=round(m.end - t_d, 1), outcome=fav, token=token,
                    outcome_index=m.index[fav], fav_method=how, decision_utc=utc(t_d), t_decision=t_d,
                    day=day_of(t_d), best_ask=str(ask), ask_size=str(size), ask_usd=str((ask * size).quantize(Decimal("0.01"))),
                    best_bid=S(bk.best_bid), mid=S(bk.mid), spread=S(spread_of(bk)), max_spread=str(MAX_SPREAD),
                    tick=str(tick), min_size=str(bk.min_size),
                    book_server_ts=bk.server_ts, book=bk.top(10), other_book=other.top(10) if other else None,
                    limit=str(ask), ticket=str(self.ticket), fee_rate=str(m.rate), seconds_delay=m.seconds_delay,
                    rule=RULE_SOURCE)
        # technical checks first: they do NOT consume the market (no decision was acted on; next poll re-checks)
        tech = ""
        if not clock_good:
            tech = clock_why
        elif env.wall() - bk.received > MAX_BOOK_AGE_S:
            tech = f"book {env.wall() - bk.received:.1f} s old at decision"
        elif self.live and (self.geo_ok_at is None or env.mono() - self.geo_ok_at > GEO_MAX_AGE_S):
            self.check_geoblock(force=True)
            if self.geo_ok_at is None or env.mono() - self.geo_ok_at > GEO_MAX_AGE_S:
                tech = "no passing geoblock check in the last 60 min"
        if tech:
            self.tech_skip(m, tech, bk)
            return
        # money caps: a refusal consumes the market (the rule's first trigger happened)
        L = self.ledger()
        sent = True
        reason = ""
        floor_info = None
        try:
            check_caps(L, m.key, day_of(t_d), self.ticket, self.exchange_fills.get(day_of(t_d), 0))
            if self.ticket / ask < bk.min_size:
                raise Refusal(f"{self.ticket} USD buys {self.ticket / ask:.2f} shares < market minimum {bk.min_size}")
            if self.live:                               # balance floor (account ceiling A): live only
                floor_info = {"floor": None, "balance": None, "in_flight": None}
                floor = read_floor()                    # read before EVERY live order (the owner may change it)
                floor_info["floor"] = str(floor)
                try:
                    bal = D(env.balance())
                except Exception as e:  # noqa: BLE001
                    raise Refusal(f"balance floor: free pUSD balance not readable ({scrub(type(e).__name__)}); "
                                  f"order refused") from None
                fl = L.in_flight(env.wall())
                floor_info["balance"], floor_info["in_flight"] = f"{bal:.6f}", str(fl)
                check_floor(bal, fl, self.ticket, floor)
                if env.wall() - bk.received > MAX_BOOK_AGE_S:   # the balance read took time: book must stay fresh
                    self.tech_skip(m, f"book {env.wall() - bk.received:.1f} s old after the balance read", bk)
                    return
        except Refusal as e:
            sent, reason = False, str(e)
        signed = None
        if sent:
            try:
                env.register(m, tick)
                signed = env.sign(token, self.ticket, ask)
            except Exception as e:  # noqa: BLE001  (SDK input checks: tick grid, precision)
                sent, reason = False, scrub(f"SDK refused to build the order: {type(e).__name__}: {e}")
        spend = implied = None
        if sent:
            spend, implied = guard_signed(signed, token, self.ticket, ask)   # Refusal here stops the session
        dec = self.rec("decision", sent=sent, reason=reason, **base, balance_floor=floor_info,
                       signed=None if signed is None else {"maker_amount": str(signed.maker_amount),
                                                          "taker_amount": str(signed.taker_amount),
                                                          "order_type": str(signed.order_type),
                                                          "spend": str(spend), "implied_price": f"{implied:.6f}"})
        self.decided[m.key] = {"m": m, "dec": dec, "result_tries": 0}
        if not sent:
            out(f"    {m.slug}: TRIGGER {fav} ask {ask} x {size} -> not sent: {reason}")
        order_rec = None
        if sent and not self.live:
            out(f"    {m.slug}: DRY TRIGGER {fav} ask {ask} x {size} ({ask * size:.2f} USD), bid {bk.best_bid} "
                f"(spread {spread_of(bk)}), "
                f"{m.end - t_d:+.0f} s to end: would send FAK BUY {self.ticket} USD @ <= {ask} "
                f"(signed {signed.maker_amount}/{signed.taker_amount}, price {implied:.5f}); NOT posted")
        elif sent:
            order_rec = self.send(m, fav, token, signed, t_d, mono_d, ask, tick)
            if order_rec.get("fill_state") == "filled":
                self.decided[m.key]["fee_due"] = env.mono() + FEE_CHECK_AFTER_S
        return {"m": m, "token": token, "ask": ask, "bid": bk.best_bid, "spread": spread_of(bk), "tick": tick,
                "t_d": t_d, "sent": sent, "delta": TWIN_DELTA_S + m.seconds_delay}

    def tech_skip(self, m: Mkt, why: str, bk: Book) -> None:
        """A trigger not acted on for a technical reason: the market is NOT consumed (next poll re-checks)."""
        if self.env.mono() - self.tech_seen.get(m.key, -1e18) > 30:
            self.tech_seen[m.key] = self.env.mono()
            self.rec("tech-skip", key=m.key, slug=m.slug, why=why, best_ask=str(bk.best_ask), ask_size=str(bk.ask_size),
                     best_bid=S(bk.best_bid), spread=S(spread_of(bk)))
            out(f"    {m.slug}: trigger at ask {bk.best_ask} NOT acted on: {why} (re-checked next poll)")

    def do_twins(self, jobs: list[dict]) -> None:
        """The doc's paper model for every decision of this poll (also refused ones): the book at t_d + 2 s
        (+ secondsDelay). In dry-run the twin IS the trade: its fill is written as the order record."""
        env = self.env
        wait = max(j["t_d"] + j["delta"] for j in jobs) - env.wall()
        if wait > 0:
            env.sleep(wait)
        try:
            got = env.books([j["token"] for j in jobs])
        except Exception as e:  # noqa: BLE001
            got = {}
            out(f"    twin book read failed ({scrub(type(e).__name__)})")
        for j in jobs:
            m, ask, tick, tb = j["m"], j["ask"], j["tick"], got.get(j["token"])
            twin = paper_fill(tb, ask, self.ticket, m.rate) if tb is not None else {"filled": None, "reason": "no book"}
            self.rec("twin", key=m.key, slug=m.slug, delta_s=j["delta"], book_t=tb.received if tb else None,
                     decision_best_ask=S(ask), decision_best_bid=S(j["bid"]), decision_spread=S(j["spread"]),
                     after_decision_s=round(tb.received - j["t_d"], 2) if tb else None,
                     ask_move_ticks=S(ticks((tb.best_ask - ask) if tb and tb.best_ask is not None else None, tick)), **twin)
            out(f"    {m.slug}: paper twin at +{j['delta']} s: best ask {twin.get('best_ask')}, bid {twin.get('best_bid')}, "
                + (f"fills {twin['shares']} @ {twin['avg_price']}" if twin.get("filled") else f"no fill ({twin.get('reason')})"))
            if j["sent"] and not self.live:
                filled = bool(twin.get("filled"))
                self.rec("order", key=m.key, slug=m.slug, post="dry-run", fill_state="filled" if filled else "unfilled",
                         filled_shares=twin.get("shares") if filled else "0", fill_price=twin.get("avg_price"),
                         fill_vs_ask_ticks=S(ticks(D(twin["avg_price"]) - ask, tick)) if filled else None,
                         fee_formula=twin.get("fee"), cost=str(D(twin["notional"]) + D(twin["fee"])) if filled else "0",
                         note="dry-run: the fill is the paper twin (book at t_d + 2 s)")

    def resume_pending(self) -> None:
        """Decisions of earlier sessions whose result is not recorded yet: follow them to resolution."""
        rows = read_records(record_files(self.live), strict=self.live)
        res = {r["key"] for r in rows if r.get("type") == "result"}
        n = 0
        for r in rows:
            if r.get("type") == "decision" and r.get("best_ask") and r["key"] not in res and r["key"] not in self.decided:
                idx = int(r["outcome_index"])
                other = "other outcome"
                m = Mkt(key=r["key"], slug=r["slug"], event_slug=r.get("event_slug", ""), type=r["market_type"],
                        asset=r["asset"], end=datetime.fromisoformat(r["end_utc"].replace("Z", "+00:00")).timestamp(),
                        tokens={r["outcome"]: r["token"]}, index={r["outcome"]: idx, other: 1 - idx}, rate=D(r["fee_rate"]))
                self.decided[r["key"]] = {"m": m, "dec": r, "result_tries": 0, "fee_done": True}
                n += 1
        if n:
            out(f"  following {n} earlier decision(s) to their result")

    def send(self, m: Mkt, fav: str, token: str, signed, t_d: float, mono_d: float, ask: Decimal, tick: Decimal) -> dict:
        env = self.env
        t_sent = env.wall()
        m0 = env.mono()
        resp, err = None, None
        try:
            resp = env.post(signed)
        except Exception as e:  # noqa: BLE001  network error / 5xx / 429: outcome unknown, never retried
            err = scrub(f"{type(e).__name__}: {e}")
        m1 = env.mono()
        base = dict(key=m.key, slug=m.slug, t_sent=t_sent, ack_utc=utc(t_sent + (m1 - m0)),
                    decision_to_send_ms=round((m0 - mono_d) * 1000), send_to_ack_ms=round((m1 - m0) * 1000),
                    decision_to_ack_ms=round((m1 - mono_d) * 1000))
        if err is not None:
            out(f"    {m.slug}: POST OUTCOME UNKNOWN ({err}); never retried; counted as filled at {self.ticket} USD "
                f"until the exchange's trades show otherwise")
            fill = self.reconcile(token, t_d, None)
            return self.rec("order", **base, post="error", error=err, order_id=None, status=None, **fill)
        if not resp["ok"]:
            msg = scrub(f"{resp.get('code')}: {resp.get('message')}")
            out(f"    {m.slug}: REJECTED {msg} (definite: nothing bought; the market is not tried again)")
            return self.rec("order", **base, post="rejected", code=scrub(resp.get("code")), message=msg,
                            order_id=None, status=None, fill_state="unfilled", filled_shares="0", cost="0")
        status = str(resp["status"]).lower()
        oid = resp["order_id"]
        making, taking = D(resp["making"]), D(resp["taking"])
        extra = {}
        resting = status in ("live", "unmatched")        # docs: 'unmatched' = placed on the book after the delay
        final = status == "matched"
        if status == "delayed":
            st = self.follow_delayed(oid)
            extra["delayed_final"] = st
            # M3: get_order's price is the order's own limit, never a fill price; only size_matched is used
            making = Decimal(0)
            if st and st.get("final"):
                taking = D(st["size_matched"])
                status = "delayed->" + st["status"].lower()
                final = True
                resting = st["status"].upper() == "UNMATCHED"
            elif st and str(st["status"]).upper().split(".")[-1] == "LIVE":
                status, resting = "delayed->live", True
        if resting:
            ok = False
            try:
                ok = bool(env.cancel(oid))
            except Exception as e:  # noqa: BLE001
                extra["cancel_error"] = scrub(type(e).__name__)
            extra["cancelled_resting_remainder"] = ok
            out(f"    {m.slug}: WARNING: FAK reported '{status}'; cancel {'confirmed' if ok else 'NOT confirmed'}")
            if not ok:                                   # M2: a remainder may rest on the book and fill later
                extra["resting_remainder_possible"] = True
                self.begin_stop(f"a FAK was reported '{status}' and its cancel was not confirmed; check open orders "
                                f"by hand on polymarket.com")
        if making > 0 and taking > 0 and making / taking > 1:          # defensive: BUY making = USD, taking = shares
            making, taking = taking, making
        trades, trades_ok = [], False
        try:
            trades = [t for t in env.trades(token, t_d) if t["taker_order_id"] == oid or t["id"] in resp["trade_ids"]]
            trades_ok = True
        except Exception as e:  # noqa: BLE001
            extra["trades_error"] = scrub(type(e).__name__)
        shares_tr, avg_tr, fee_tr = fill_from_trades(trades, m.rate)
        final_status = status.split("->")[-1].upper()
        # M1/M2: 'unfilled' only from a definite final state with nothing matched AND an empty trades list;
        # every other unclear shape is 'unknown' (counted at the full ticket until the late check).
        if resting and not extra.get("cancelled_resting_remainder"):
            shares, state = (shares_tr or None), "unknown"
        elif shares_tr > 0 or (final and taking > 0):
            shares, state = max(shares_tr, taking if final else Decimal(0)), "filled"
            if shares_tr > 0 and final and taking > 0 and abs(shares_tr - taking) > Decimal("0.01"):
                extra["shares_sources_disagree"] = True
        elif (final and final_status.startswith(("CANCELED", "CANCELLED", "INVALID")) and taking == 0
              and trades_ok):
            shares, state = Decimal(0), "unfilled"
        else:                                            # 'matched' with no amounts, 'live', unreadable trades ...
            shares, state = None, "unknown"
        # M3: the fill price comes from the exchange's trade legs; the response figure is kept beside it
        avg_resp = (making / taking) if (taking > 0 and making > 0 and not status.startswith("delayed")) else None
        avg = avg_tr if avg_tr is not None else avg_resp
        if avg_tr is not None and avg_resp is not None and abs(avg_tr - avg_resp) > Decimal("0.0005"):
            extra["price_sources_disagree"] = True
        if state == "filled":
            f_formula = fee_tr if (avg_tr is not None and shares == shares_tr) else (
                fee_formula(shares, avg, m.rate) if avg is not None else None)
        else:
            f_formula = None
        if state == "filled" and avg is not None:
            cost = shares * avg + (f_formula or 0)
        elif state == "filled":                          # shares known, price not: worst case, the full ticket
            cost = None
            state = "unknown"
        else:
            cost = Decimal(0) if state == "unfilled" else None
        matched_ms = None
        mts = [t["match_time"] for t in trades if t.get("match_time")]
        if mts:
            matched_ms = round((min(mts) - t_d) * 1000)
        rec = self.rec("order", **base, post="accepted", order_id=oid, status=status, making=str(making),
                       taking=str(taking), trade_ids=resp["trade_ids"], fill_state=state,
                       filled_shares=S(shares), fill_price=S(avg), fill_price_trades=S(avg_tr),
                       fill_price_response=S(avg_resp), shares_trades=S(shares_tr),
                       fill_vs_ask_ticks=S(ticks((avg - ask) if avg is not None else None, tick)),
                       fill_fraction=S((shares * ask / self.ticket).quantize(Decimal("0.001")) if shares else None),
                       fee_formula=S(f_formula), cost=S(cost), trades=trades,
                       trade_statuses=sorted({str(t.get("status")) for t in trades}),
                       decision_to_match_ms=matched_ms, **extra)
        out(f"    {m.slug}: SENT FAK BUY {self.ticket} USD @ <= {ask}: {status}; "
            + (f"filled {shares} @ {avg:.5f} ({ticks(avg - ask, tick)} ticks vs ask)" if state == "filled" and avg else state)
            + f"; decision->ack {base['decision_to_ack_ms']} ms")
        return rec

    def follow_delayed(self, oid: str) -> dict | None:
        t0 = self.env.mono()
        st = None
        while self.env.mono() - t0 < DELAYED_WAIT_S:
            self.env.sleep(0.5)
            try:
                st = self.env.order_state(oid)
            except Exception:  # noqa: BLE001
                continue
            s = str(st["status"]).upper().split(".")[-1]
            if s not in ("DELAYED", "LIVE", "PENDING", ""):
                return {"status": s, "size_matched": str(st["size_matched"]), "price": str(st["price"]), "final": True}
        return None if st is None else {"status": str(st["status"]), "size_matched": str(st["size_matched"]),
                                        "price": str(st["price"]), "final": False}

    def reconcile(self, token: str, t_d: float, oid: str | None) -> dict:
        """After an unknown post outcome: look for our taker trades on this token for a while. Never re-sends."""
        t0 = self.env.mono()
        while self.env.mono() - t0 < RECONCILE_WAIT_S:
            self.env.sleep(5)
            try:
                tr = self.env.trades(token, t_d)
            except Exception:  # noqa: BLE001
                continue
            sh, avg, f = fill_from_trades(tr)
            if sh > 0:
                return {"fill_state": "filled", "filled_shares": str(sh), "fill_price": str(avg), "cost": str(sh * avg + f),
                        "fee_formula": str(f), "trades": tr, "reconciled": True}
        return {"fill_state": "unknown", "filled_shares": None, "cost": None, "reconciled": False,
                "note": "no trade seen; counted as filled at the full ticket (worst case) until resolution"}

    # -- fees, results, stops
    def follow_up(self) -> None:
        now_m, now = self.env.mono(), self.env.wall()
        for k, ctx in list(self.decided.items()):
            m, dec = ctx["m"], ctx["dec"]
            if ctx.get("fee_due") and now_m >= ctx["fee_due"]:
                ctx["fee_due"] = None
                self.fee_check(m, dec)
            if now < m.end or now_m - ctx.get("res_at", -1e18) < RESULT_EVERY_S:
                continue
            ctx["res_at"] = now_m
            try:
                winner, split = self.env.result(m)
            except Exception as e:  # noqa: BLE001
                out(f"  {m.slug}: result lookup failed ({scrub(type(e).__name__)}), will retry")
                continue
            if winner is None:
                continue
            L = self.ledger()
            t = L.trades.get(k, {})
            state = t.get("state", "dry-run")
            won = (winner == dec["outcome"]) if not split else None
            payout = Decimal(1) if won else Decimal(0)
            if split:                                   # RealEnv.result names a split "split <p0>/<p1>"
                ps = re.findall(r"[0-9]+(?:\.[0-9]+)?", str(winner))
                idx = int(dec.get("outcome_index", 0))
                payout = D(ps[idx]) if len(ps) == 2 and D(ps[idx]) <= 1 else Decimal("0.5")
            self.rec("result", key=k, slug=m.slug, winner=winner, winner_is_split=split, our_outcome=dec["outcome"],
                     won=won, fill_state=state, our_payout=str(payout))
            out(f"  {m.slug}: RESULT {winner}; we bought {dec['outcome']} -> {'WON' if won else 'LOST' if won is False else 'split'}"
                f" ({state})")
            if state == "unknown" and self.live:
                self.late_reconcile(m, dec)
            if ctx.get("fee_due") is not None or (self.live and state == "filled" and not ctx.get("fee_done")):
                self.fee_check(m, dec)
            del self.decided[k]
            self.check_halt()

    def late_reconcile(self, m: Mkt, dec: dict) -> None:
        """After resolution, an order whose fill was unknown is settled from three exchange sources (S3): the CLOB
        trades list, the activity feed and the token balance. 'unfilled' only if all three say nothing was bought;
        'filled' at the real cost if the trades show it and the balance does not show more; else stays worst case."""
        try:
            tr = self.env.trades(dec["token"], dec["t_decision"])
            act = self.env.activity(m, dec["token"], dec["t_decision"])
        except Exception as e:  # noqa: BLE001
            out(f"  {m.slug}: late check of an unknown order failed ({scrub(type(e).__name__)}); stays worst case")
            return
        held = None
        try:
            held = D(self.env.token_balance(dec["token"]))
        except Exception as e:  # noqa: BLE001
            out(f"  {m.slug}: token balance not readable ({scrub(type(e).__name__)})")
        sh, avg, fee = fill_from_trades(tr, m.rate)
        common = dict(key=m.key, slug=m.slug, post="late-check", trades_seen=len(tr), activity_rows=len(act),
                      token_balance=S(held))
        if not tr and not act and held is not None and held == 0:
            self.rec("order", **common, fill_state="unfilled", filled_shares="0", cost="0",
                     note="no trade in the CLOB trades list, no TRADE row in the activity feed, token balance 0")
        elif sh > 0 and held is not None and held <= sh + Decimal("0.01"):
            self.rec("order", **common, fill_state="filled", filled_shares=str(sh), fill_price=str(avg),
                     fee_formula=str(fee), cost=str(sh * avg + fee), trades=tr,
                     note="fill found after resolution in the CLOB trades list")
        else:
            self.rec("order", **common, fill_state="unknown", filled_shares=None, cost=None,
                     note="sources disagree or show a holding the trades do not explain: full ticket (worst case)")
        out(f"  {m.slug}: late check of the unknown order: {len(tr)} trade(s), {len(act)} activity row(s), "
            f"token balance {held if held is not None else 'unreadable'}")

    def fee_check(self, m: Mkt, dec: dict) -> None:
        ctx = self.decided.get(m.key)
        if ctx is not None:
            ctx["fee_done"] = True
        if not self.live:
            return
        try:
            act = self.env.activity(m, dec["token"], dec["t_decision"])
        except Exception as e:  # noqa: BLE001
            out(f"  {m.slug}: fee check failed ({scrub(type(e).__name__)})")
            return
        if not act:
            out(f"  {m.slug}: fee check: no activity row yet")
            return
        amount = sum((D(a["amount"]) for a in act), Decimal(0))
        shares = sum((D(a["shares"]) for a in act), Decimal(0))
        notional = sum((D(a["shares"]) * D(a["price"]) for a in act), Decimal(0))
        charged = amount - notional
        formula = fee_formula(shares, notional / shares, m.rate) if shares > 0 else Decimal(0)
        diff = charged - formula
        bad = abs(diff) > Decimal("0.001") or (formula > 0 and abs(diff) / formula > Decimal("0.02"))
        self.rec("fee", key=m.key, slug=m.slug, activity_amount=str(amount), activity_shares=str(shares),
                 notional=str(notional), fee_charged=str(charged), fee_formula_vwap=str(formula), diff=str(diff),
                 mismatch=bad, rows=act)
        out(f"  {m.slug}: fee charged {charged:.5f} vs formula {formula:.5f} ({'MISMATCH: stop and look' if bad else 'ok'})")
        if bad:
            self.begin_stop("fee charged differs from the formula by more than 2% or 0.001 USD (doc: stop and look)")

    def check_halt(self) -> None:
        L = self.ledger()
        why = halt_reason(L)
        if not why or self.halted:
            return
        if self.live:
            HALT_FILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            HALT_FILE.write_text(f"exp_fav.py permanent stop {utc(self.env.wall())}: {why}\n"
                                 f"Remove this file by hand only after reading the report.\n")
            self.rec("halt", why=why)
            self.halted = True
            out(f"  PERMANENT STOP: {why}. Halt file {HALT_FILE} written; no more orders until a human removes it.")
            self.begin_stop(why)
        else:
            self.rec("would-halt", why=why)
            self.halted = True
            out(f"  (dry-run) a live session would stop for good here: {why}. The paper stage keeps recording.")

    def begin_stop(self, why: str) -> None:
        if self.stopping:
            return
        self.stopping = True
        self.rec("stopping", why=why)
        out(f"  STOPPING NEW ORDERS: {why}. Open positions are held to resolution; their results are still "
            f"recorded while the program runs (Ctrl+C quits at once; `report` works later).")

    # -- main loop
    def start_checks(self) -> None:
        if self.live:
            if HALT_FILE.exists():
                raise Refusal(f"halt file present ({HALT_FILE}): permanent stop. Read the report; remove the file "
                              f"by hand only if you decide to continue")
            have, wrote = count_live_decisions(), read_watermark()
            if have < wrote:                         # S1: records of earlier live sessions are not in this folder
                raise Refusal(f"the live records in {OUT_DIR} hold {have} decision(s), but live sessions of this "
                              f"program on this Mac wrote {wrote} (see {WATERMARK_FILE}). Copy every "
                              f"exp-fav-*.jsonl of the earlier folder into {OUT_DIR}, then start again: the loss "
                              f"count, the open positions and the daily cap need the whole ledger")
            L = self.ledger()
            if L.halted_at is not None and (L.cleared_at or 0) < L.halted_at and halt_reason(L):
                self.rec("halt-cleared", note="halt file was removed by hand; losses are counted again from now")
                out("  the halt file was removed by hand: the loss count restarts from now")
            elif halt_reason(L):
                HALT_FILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                HALT_FILE.write_text(f"exp_fav.py permanent stop {utc(self.env.wall())}: {halt_reason(L)}\n")
                self.rec("halt", why=halt_reason(L))
                raise Refusal(f"stop condition already reached in the records: {halt_reason(L)}")
            floor = read_floor()                     # missing / malformed FLOOR file: no live session at all
            out(f"  balance floor {floor} USD (from {FLOOR_FILE})")
        else:
            try:
                out(f"  balance floor file: {read_floor()} USD (dry-run does not use it)")
            except Refusal as e:
                out(f"  balance floor file: not usable, a live run would refuse ({scrub(e)[:120]}); dry-run continues")
        if STOP_FILE.exists():
            raise Refusal(f"STOP file present ({STOP_FILE}); remove it to start")

    def run(self) -> int:
        self.rec("session", version=VERSION, rule=RULE_SOURCE, code_sha256=code_sha256(), ticket=str(self.ticket),
                 caps={"max_limit": str(HARD_MAX_LIMIT), "max_filled_per_day": MAX_FILLED_PER_DAY,
                       "stop_loss_usd": str(STOP_LOSS_USD), "stop_losing_trades": STOP_LOSING_TRADES,
                       "max_open_tickets": MAX_OPEN_TICKETS, "exposure_cap_usd": str(EXPOSURE_CAP_USD),
                       "max_spread": str(MAX_SPREAD), "in_flight_s": IN_FLIGHT_S})
        self.start_checks()
        self.check_geoblock(force=True)
        if self.live and self.geo_blocked is not False:
            raise Refusal("geoblock check did not pass; nothing was sent")
        self.check_server_time(force=True)
        if self.live:
            bal = self.env.balance()
            out(f"  pUSD balance {bal:.2f}")
            if bal < self.ticket:
                raise Refusal(f"balance {bal:.2f} pUSD < one ticket {self.ticket}; not starting")
            L0 = self.ledger()
            check_floor(bal, L0.in_flight(self.env.wall()), self.ticket, read_floor())   # Refusal: not starting
            out(f"  balance floor ok: {bal:.2f} - one ticket {self.ticket} >= floor {read_floor()} USD")
            if self.env.closed_only():
                raise Refusal("the account is in closed-only mode; not starting")
            ap = self.env.approvals_ok()
            if ap is False:
                raise Refusal("trading approvals are incomplete (see `smoke.py auth --live`); this program posts "
                              "with post_order, which does not set approvals; not starting")
            out(f"  trading approvals complete: {'yes' if ap else 'unknown (the SDK could not tell)'}")
            midnight = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
            ex = self.env.fills_today(midnight)
            fl = self.ledger().filled_on(day_of(self.env.wall()))
            out(f"  filled trades today: {fl} in the records, {ex} taker BUY orders on the exchange")
            if max(ex, fl) >= MAX_FILLED_PER_DAY:
                out(f"  daily cap {MAX_FILLED_PER_DAY} already reached today; the session waits for tomorrow (UTC)")
            self.exchange_fills[day_of(self.env.wall())] = ex
        self.resume_pending()
        self.refresh_universe(force=True)
        self.next_poll = self.env.mono()
        while True:
            if self.t_end is not None and self.env.wall() >= self.t_end and (not self.decided or self.stopping):
                out("  --hours reached")
                break
            if self.t_end is not None and self.env.wall() >= self.t_end + 6 * 3600:
                out("  --hours reached (+6 h for pending results); unresolved decisions are finished by a later run")
                break
            if not self.stopping and (STOP_FILE.exists() or HALT_FILE.exists()):
                self.begin_stop(f"STOP or halt file present")
            if self.stopping and not self.decided:
                break
            self.check_geoblock()
            self.check_server_time()
            self.refresh_universe()
            self.refresh_states()
            now_m = self.env.mono()
            if now_m < self.next_poll:
                self.env.sleep(min(self.next_poll - now_m, 1.0))
                continue
            late = now_m - self.next_poll
            self.next_poll = max(self.next_poll + POLL_S, now_m + POLL_S - 1) if late > POLL_S else self.next_poll + POLL_S
            if not self.stopping:
                self.poll(late)
            self.follow_up()
        out(f"  session {self.session} done after {self.polls} polls; records in {OUT_DIR}")
        return 0


# ----------------------------------------------------------------------------- run command
def cmd_run(a) -> int:
    ticket = check_ticket(a.ticket)
    if a.hours is not None and not (0 < a.hours <= 24 * 14):
        raise Refusal("--hours must be between 0 and 336")
    lock = acquire_lock(LOCK_FILE)
    bids_lock = None
    try:
        if STOP_FILE.exists():
            raise Refusal(f"STOP file present ({STOP_FILE}); remove it to start")
        wallet = smoke.wallet_env()
        if a.live:
            # S2: exp_bids.py's caps do not see this program's trades and vice versa: never both live on one
            # account. Holding its live lock for the whole session also keeps a live exp_bids.py from starting.
            bids_lock = acquire_lock(BIDS_LOCK_FILE, "a live exp_bids.py session is running; never run exp_bids.py "
                                                     "and exp_fav.py live at the same time")
            if HALT_FILE.exists():
                raise Refusal(f"halt file present ({HALT_FILE}): permanent stop")
            read_floor()                             # FLOOR file missing or malformed: refused before the key is read
            key = smoke.load_private_key()
            client = smoke.live_client(key, wallet)
        else:
            from eth_account import Account
            key = "0x" + Account.create().key.hex().removeprefix("0x")
            out.add_secret(key)
            out("  dry-run: public data only; the would-be orders are signed with a throwaway in-memory key")
            client = smoke.offline_client(key, None)
        out.add_secret(str(client.wallet))
        out.add_secret(str(client.signer))
        out(f"  mode {'LIVE' if a.live else 'dry-run'}, ticket {ticket} USD, wallet type {client.wallet_type} "
            f"(addresses are not printed)")
        env = RealEnv(client, a.live)
        try:
            s = Session(env, a.live, ticket, a.hours)
            try:
                return s.run()
            except KeyboardInterrupt:
                out("  interrupted (Ctrl+C). FAK orders never rest, so nothing is left on the book. Open positions "
                    "are held; run again (or `report`) to record their results.")
                return 130
        finally:
            env.close()
    finally:
        if bids_lock is not None:
            bids_lock.close()
        lock.close()


# ----------------------------------------------------------------------------- report
def _pct(xs, q):
    if not xs:
        return None
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))]


def cmd_report(a) -> int:
    live = not a.dry_run
    paths = a.files or record_files(live)
    if not paths:
        out(f"  no {'live' if live else 'dry-run'} record files in {OUT_DIR}")
        return 0
    rows = read_records(paths, strict=False)
    by = defaultdict(dict)
    near = Counter()
    wide = Counter()                                # wide-book polls per market (narrow-book condition failed)
    tech = 0
    sessions = set()
    halts = [r for r in rows if r.get("type") in ("halt", "would-halt", "halt-cleared", "stopping")]
    for r in rows:
        sessions.add(r.get("session"))
        if r.get("type") in ("decision", "order", "twin", "fee", "result") and r.get("key"):
            g = by[r["key"]]
            if r["type"] == "order" and "order" in g and r.get("post") == "late-check":
                g["order"] = {**g["order"], **{k: r[k] for k in ("fill_state", "filled_shares", "cost")},
                              **({"fill_price": r["fill_price"], "fee_formula": r.get("fee_formula")}
                                 if r.get("fill_state") == "filled" else {}), "late_check": True}
            else:
                g.setdefault(r["type"], r)
        elif r.get("type") == "near":
            near[r.get("slug")] += 1
        elif r.get("type") == "tech-skip":
            tech += 1
        elif r.get("type") == "wide-book":
            wide[r.get("slug")] += int(r.get("polls_since_last") or 1)
    mode = "LIVE" if live else "DRY-RUN (paper stage: the 'fill' columns are the paper twin)"
    out(f"  report: {mode}; {len(paths)} file(s), {len(sessions)} session(s)")
    decs = [g for g in by.values() if "decision" in g and g["decision"].get("best_ask") is not None]
    decs.sort(key=lambda g: g["decision"]["t_decision"])
    sent = [g for g in decs if g["decision"]["sent"]]
    refused = [g for g in decs if not g["decision"]["sent"]]
    out(f"  triggers: {len(decs)}  sent: {len(sent)}  refused by a cap: {len(refused)}  "
        f"technical skips (re-checked): {tech}  near-misses: {sum(near.values())} in {len(near)} markets")
    out(f"  wide book (ask in range with >= 10 USD, but bid more than {MAX_SPREAD} below the ask; not triggers, "
        f"markets not consumed): {sum(wide.values())} polls in {len(wide)} markets"
        + (f"; of these markets, {len(set(wide) & {g['decision']['slug'] for g in by.values() if 'decision' in g})} "
           f"triggered later" if wide else ""))
    out("")
    hdr = (f"  {'decision UTC':19} {'type':12} {'asset':8} {'s->end':>6} {'ask':>6} {'askUSD':>7} {'limit':>6} "
           f"{'fill':>8} {'shares':>7} {'tick':>5} {'slip':>5} {'feeF':>7} {'feeC':>7} {'ack ms':>6} "
           f"{'twin':>8} {'result':>6} {'pnl':>7}")
    out(hdr)
    slips, moves, twin_diff, acks, fees = [], [], [], [], []
    wins = losses = unresolved = unfilled = unknown = splits = disagree = 0
    net = Decimal(0)
    net_sent = Decimal(0)
    per_type = defaultdict(lambda: [0, 0, 0, Decimal(0)])
    for g in decs:
        d, o, tw, fe, rs = g["decision"], g.get("order", {}), g.get("twin", {}), g.get("fee"), g.get("result")
        tick = D(d["tick"])
        ask = D(d["best_ask"])
        if not d["sent"] and live:
            tws = (f"{D(tw['avg_price']):.4f}" if tw.get("avg_price") else "miss")
            out(f"  {d['decision_utc'][:19]} {d['market_type'][:12]:12} {d['asset'][:8]:8} {d['seconds_to_end']:>6.0f} "
                f"{ask:>6} {D(d['ask_usd']):>7.2f}  REFUSED ({d['reason'][:60]}); paper twin {tws}")
            continue
        if live:
            state = o.get("fill_state", "unknown")
            price = D(o["fill_price"]) if o.get("fill_price") else None
            shares = D(o["filled_shares"]) if o.get("filled_shares") not in (None, "0") else None
            cost = D(o["cost"]) if o.get("cost") not in (None,) else None
        else:                                       # paper stage: the twin is the trade (also for capped triggers)
            state = "filled" if tw.get("filled") else "unfilled"
            price = D(tw["avg_price"]) if tw.get("avg_price") else None
            shares = D(tw["shares"]) if tw.get("filled") else None
            cost = (D(tw["notional"]) + D(tw["fee"])) if tw.get("filled") else Decimal(0)
        if tw.get("ask_move_ticks") is not None:
            moves.append(D(tw["ask_move_ticks"]))
        slip = ticks(price - ask, tick) if price is not None else None
        if slip is not None:
            slips.append(slip)
        if live and price is not None and tw.get("avg_price"):
            twin_diff.append(price - D(tw["avg_price"]))
        if live and o.get("decision_to_ack_ms") is not None:
            acks.append(o["decision_to_ack_ms"])
        f_c = D(fe["fee_charged"]) if fe else None
        f_f = D(o["fee_formula"]) if live and o.get("fee_formula") else (D(tw["fee"]) if not live and tw.get("filled") else None)
        if fe:
            fees.append((D(fe["fee_charged"]), D(fe["fee_formula_vwap"]), bool(fe.get("mismatch"))))
        won = rs.get("won") if rs else None
        pnl = None
        if live and o.get("price_sources_disagree"):
            disagree += 1
        if rs and rs.get("winner_is_split") and state in ("filled", "unknown"):
            pay = D(rs.get("our_payout") or "0.5")
            pnl = (pay * shares - cost) if (state == "filled" and cost is not None and shares is not None) else -D(d["ticket"])
            net += pnl
            if d["sent"]:
                net_sent += pnl
            splits += 1
        elif state == "filled" and won is not None and cost is not None and shares is not None:
            pnl = (shares if won else Decimal(0)) - cost
            net += pnl
            if d["sent"]:
                net_sent += pnl
            wins += bool(won)
            losses += (not won)
            pt = per_type[d["market_type"]]
            pt[0] += 1
            pt[1] += bool(won)
            pt[2] += (not won)
            pt[3] += pnl
        elif state == "unknown" and won is False:
            pnl = -D(d["ticket"])
            net += pnl
            losses += 1
        elif state == "filled":
            unresolved += 1
        if state == "unfilled":
            unfilled += 1
        if state == "unknown":
            unknown += 1
        tw_s = (f"{D(tw['avg_price']):.4f}" if tw.get("avg_price") else ("miss" if tw.get("filled") is False else "-"))
        out(f"  {d['decision_utc'][:19]}{'*' if not d['sent'] else ' '}{d['market_type'][:12]:12} {d['asset'][:8]:8} {d['seconds_to_end']:>6.0f} "
            f"{ask:>6} {D(d['ask_usd']):>7.2f} {D(d['limit']):>6} "
            f"{(f'{price:.4f}' if price is not None else state):>8} {(f'{shares:.2f}' if shares else '-'):>7} "
            f"{tick:>5} {(f'{slip:+.1f}' if slip is not None else '-'):>5} "
            f"{(f'{f_f:.5f}' if f_f is not None else '-'):>7} {(f'{f_c:.5f}' if f_c is not None else '-'):>7} "
            f"{(str(o.get('decision_to_ack_ms')) if live and o.get('decision_to_ack_ms') is not None else '-'):>6} "
            f"{tw_s:>8} {('won' if won else 'LOST' if won is False else 'split' if rs and rs.get('winner_is_split') else '-'):>6} "
            f"{(f'{pnl:+.3f}' if pnl is not None else '-'):>7}")
    out("")
    out("  Slippage (fill price - ask at decision, in ticks of that market; a limit at the ask can only fill at or "
        "below it, so the cost of a moving book shows up as 'unfilled'):")
    c = Counter(str(s) for s in slips)
    out(f"    filled {len(slips)}: " + (", ".join(f"{k} ticks: {v}" for k, v in sorted(c.items(), key=lambda x: D(x[0]))) or "none")
        + f"; unfilled (FAK killed) {unfilled}; outcome unknown {unknown}")
    if live:
        out(f"    fill price from the exchange's trade legs; orders whose response amounts disagree with the trades by "
            f"more than 0.0005: {disagree}")
    cm = Counter(str(x) for x in moves)
    out(f"    best ask {TWIN_DELTA_S} s after the decision minus the ask at decision, in ticks ({len(moves)} triggers): "
        + (", ".join(f"{k}: {v}" for k, v in sorted(cm.items(), key=lambda x: D(x[0]))) or "none"))
    if twin_diff:
        out(f"    live fill - paper twin fill: mean {sum(twin_diff) / len(twin_diff):+.5f} (doc limit +0.005), "
            f"n {len(twin_diff)}")
    if acks:
        out(f"    decision -> acknowledgement: median {statistics.median(acks):.0f} ms, p90 {_pct(acks, 0.9)} ms, "
            f"max {max(acks)} ms (n {len(acks)})")
    out("")
    out("  Fee check (charged = activity usdc_size - shares x price; formula = 0.01 x p x (1-p) x shares):")
    if fees:
        for ch, fo, bad in fees:
            out(f"    charged {ch:.5f}  formula {fo:.5f}  diff {ch - fo:+.5f}  {'MISMATCH' if bad else 'ok'}")
    else:
        out("    no fee rows yet" + ("" if live else " (dry-run: the paper fee is the formula)"))
    out("")
    out(f"  Results: won {wins}, lost {losses}, split {splits}, filled but unresolved {unresolved}; net {net:+.3f} USD "
        f"(after fees, before redemption)")
    if not live:
        out(f"    paper stage counts every trigger (rows marked * were refused by a cap a live run applies); "
            f"net of the triggers a live run would have sent: {net_sent:+.3f} USD")
    for t, (n, w, lo, p) in sorted(per_type.items()):
        out(f"    {t:13} trades {n:3d}  won {w:3d}  lost {lo:2d}  net {p:+.3f}")
    if refused:
        rc = Counter(re.sub(r"[\d.]+", "N", g["decision"]["reason"])[:70] for g in refused)
        out("  Triggers refused by a cap (market consumed; paper twin still recorded):")
        for k, v in rc.most_common():
            out(f"    {v:3d}  {k}")
    for h in halts:
        out(f"  {h['type'].upper()} {h.get('t_utc', '')[:19]}: {h.get('why') or h.get('note') or ''}")
    out(f"  Halt file {'PRESENT' if HALT_FILE.exists() else 'absent'} ({HALT_FILE}); STOP file "
        f"{'PRESENT' if STOP_FILE.exists() else 'absent'}")
    return 0


# ----------------------------------------------------------------------------- selftest
class FakeEnv:
    """Fake clock and exchange for the selftest. Signs with the real SDK offline client; never touches the network."""

    def __init__(self, client, live: bool, t0: float):
        self.c, self.live = client, live
        self.t, self.m = t0, 1000.0
        self.mk: list[Mkt] = []
        self.book_by_token: dict[str, Book] = {}
        self.post_mode = "matched"           # matched / reject / fak / raise / delayed / live
        self.posted: list = []
        self.cancelled: list = []
        self.trade_rows: dict[str, list] = defaultdict(list)
        self.activity_rows: dict[str, list] = defaultdict(list)
        self.winner: dict[str, str] = {}
        self.geo = {"blocked": False, "country": "RS", "urllib_blocked": False}
        self.offset = 0.0
        self.bal = Decimal("100")
        self.fee_bump = Decimal(0)
        self.err_text = "ConnectError: timed out"
        self.geo_calls = 0
        self.traded_before: set = set()
        self.fill_px: Decimal | None = None   # the trade prints at this price (default: the signed limit)
        self.resp_px: Decimal | None = None   # 'matched' response amounts imply this price (default: the fill)
        self.record_trades = True             # False: the trades list stays empty
        self.partial: Decimal | None = None   # fraction of the order that fills
        self.cancel_ok = True
        self.split = False
        self.held: dict[str, Decimal] = {}    # token balance override; default: the shares in the trade rows

    def wall(self):
        return self.t

    def mono(self):
        return self.m

    def sleep(self, s):
        s = max(s, 0.001)
        self.t += s
        self.m += s

    def jump(self, s):                      # wall clock only (NTP step, manual change)
        self.t += s

    def close(self):
        pass

    def discover(self, now):
        return [Mkt(**{**m.__dict__}) for m in self.mk], []

    def refresh(self, keys):
        return {m.key: (m.accepting, m.closed) for m in self.mk if m.key in keys}

    def books(self, tokens):
        res = {}
        for t in tokens:
            b = self.book_by_token.get(t)
            if b is not None:
                res[t] = Book(b.token, list(b.asks), list(b.bids), b.tick, b.min_size, self.t, self.t)
        return res

    def server_time(self):
        return self.offset, 0.05

    def geoblock(self):
        self.geo_calls += 1
        return dict(self.geo)

    def result(self, m):
        w = self.winner.get(m.key)
        if w and self.split:
            return "split 0.5/0.5", True
        return (w, False) if w else (None, False)

    def register(self, m, tick):
        _register_offline_market(self.c, tuple(m.tokens.values()), m.key, tick, m.rate, m.neg_risk)

    def warm(self, m):
        pass

    def sign(self, token, amount, limit):
        return self.c.create_market_order(asset_id=token, side="BUY", amount=amount, max_price=limit, order_type="FAK")

    def post(self, signed):
        if not self.live:
            raise Refusal("internal: post called in dry-run")
        self.posted.append(signed)
        tok = str(signed.token_id)
        mk, tk = Decimal(signed.maker_amount) / smoke.USDC_UNIT, Decimal(signed.taker_amount) / smoke.USDC_UNIT
        oid = "0x" + uuid.uuid4().hex * 2
        if self.post_mode == "raise":
            raise RuntimeError(self.err_text)
        if self.post_mode == "reject":
            return {"ok": False, "code": "not_enough_balance", "message": "not enough balance / allowance"}
        if self.post_mode == "fak":
            return {"ok": False, "code": "fak_not_filled", "message": "no orders found to match with FAK order"}
        limit = (mk / tk).quantize(Decimal("0.001"))
        p = self.fill_px if self.fill_px is not None else limit
        spend = mk * (self.partial if self.partial is not None else 1)
        tk = (spend / p).quantize(Decimal("0.01"), rounding="ROUND_DOWN")   # a better price buys more shares
        tid = uuid.uuid4().hex
        if self.record_trades:
            self.trade_rows[tok].append({"id": tid, "taker_order_id": oid, "price": str(p), "size": str(tk),
                                         "status": "MATCHED", "fee_rate_bps": "100", "match_time": self.t + 0.3,
                                         "tx": "0x" + "cd" * 32, "legs": [[str(p), str(tk)]]})
            self.activity_rows[tok].append({"amount": str(tk * p + fee_formula(tk, p) + self.fee_bump), "shares": str(tk),
                                            "price": str(p), "t": self.t, "tx": "0x" + "cd" * 32})
        if self.post_mode == "delayed":
            self._delayed = (oid, tk, limit)
            return {"ok": True, "order_id": oid, "status": "delayed", "making": Decimal(0), "taking": Decimal(0), "trade_ids": []}
        if self.post_mode == "live":
            return {"ok": True, "order_id": oid, "status": "live", "making": Decimal(0), "taking": Decimal(0), "trade_ids": []}
        if self.post_mode == "matched0":     # success answer with empty amounts (the SDK parses '' as 0)
            return {"ok": True, "order_id": oid, "status": "matched", "making": Decimal(0), "taking": Decimal(0),
                    "trade_ids": [tid] if self.record_trades else []}
        rp = self.resp_px if self.resp_px is not None else p
        if self.post_mode == "swapped":      # making / taking the other way round (shares, USD)
            return {"ok": True, "order_id": oid, "status": "matched", "making": tk, "taking": tk * rp, "trade_ids": [tid]}
        return {"ok": True, "order_id": oid, "status": "matched", "making": tk * rp, "taking": tk, "trade_ids": [tid]}

    def order_state(self, oid):
        o, tk, limit = self._delayed
        return {"status": "MATCHED", "size_matched": tk, "price": limit}   # like the API: price = the order's limit

    def cancel(self, oid):
        self.cancelled.append(oid)
        return self.cancel_ok

    def token_balance(self, token):
        if token in self.held:
            return self.held[token]
        return sum((D(r["size"]) for r in self.trade_rows[token]), Decimal(0))

    def trades(self, token, since):
        return [r for r in self.trade_rows[token] if r["match_time"] >= since - 5]

    def activity(self, m, token, since):
        return list(self.activity_rows[token])

    def balance(self):
        return self.bal

    def account_traded(self, tokens):
        return any(t in self.traded_before for t in tokens)

    def fills_today(self, midnight):
        return 0

    def closed_only(self):
        return False

    def approvals_ok(self):
        return getattr(self, "approved", True)


def _fake_market(i: int, end: float, typ="above", asset="bitcoin") -> Mkt:
    y, n = str(10 ** 30 + i), str(2 * 10 ** 30 + i)
    return Mkt(key="0x" + f"{i:064x}", slug=f"{asset}-above-{i}k-on-november-28-2026", event_slug=f"{asset}-above-on-november-28-2026",
               type=typ, asset=asset, end=end, tokens={"Yes": y, "No": n}, index={"Yes": 0, "No": 1}, rate=FEE_RATE)


def _book(token, ask, ask_size, bid, tick="0.001", min_size="5") -> Book:
    asks = [(D(ask), D(ask_size)), (D(ask) + D(tick), D("500"))] if ask is not None else []
    bids = [(D(bid), D("300"))] if bid is not None else []
    return Book(token, asks, bids, D(tick), D(min_size), 0.0)


def cmd_selftest(a) -> int:
    import tempfile
    global OUT_DIR, STOP_FILE, HALT_FILE, LOCK_FILE, BIDS_LOCK_FILE, WATERMARK_FILE, FLOOR_FILE
    for var in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
        os.environ[var] = "http://127.0.0.1:9"                 # no network for this process
    os.environ.pop("NO_PROXY", None)
    os.environ.pop("no_proxy", None)
    from eth_account import Account

    ok = True
    n_checks = 0

    def check(name, fn, expect_refusal):
        nonlocal ok, n_checks
        n_checks += 1
        try:
            r = fn()
            passed = not expect_refusal
            out(f"  [{'PASS' if passed else 'FAIL'}] {name}: returned {r}")
        except Refusal as e:
            passed = expect_refusal
            out(f"  [{'PASS' if passed else 'FAIL'}] {name}: refused: {e}")
        ok &= passed

    def expect(name, cond, detail=""):
        nonlocal ok, n_checks
        n_checks += 1
        out(f"  [{'PASS' if cond else 'FAIL'}] {name}{': ' + str(detail) if detail != '' else ''}")
        ok &= bool(cond)

    tmp = Path(tempfile.mkdtemp(prefix="pm-fav-selftest-"))
    os.chmod(tmp, 0o700)
    saved = (OUT_DIR, STOP_FILE, HALT_FILE, LOCK_FILE, BIDS_LOCK_FILE, WATERMARK_FILE, FLOOR_FILE)
    OUT_DIR, STOP_FILE, HALT_FILE, LOCK_FILE = tmp / "out", tmp / "STOP", tmp / "EXP_FAV_HALT", tmp / "exp_fav.lock"
    BIDS_LOCK_FILE, WATERMARK_FILE = tmp / "exp_bids.live.lock", tmp / "exp_fav.live-records.json"
    FLOOR_FILE = tmp / "FLOOR"
    out.log_path = tmp / "selftest.log"                        # S9: never the real pilot/out log
    key = "0x" + Account.create().key.hex().removeprefix("0x")
    out.add_secret(key)
    out("selftest: throwaway key in memory, records in a temp folder, network disabled for this process")
    try:
        # ---- smoke.py helpers as the live path uses them (key file, geoblock): they print through `out`
        kdir = tmp / "keydir"
        kdir.mkdir(mode=0o700)
        kf = kdir / "key"
        kf.write_text(key[2:])
        old_pm = os.environ.get("PM_KEY_FILE")
        os.environ["PM_KEY_FILE"] = str(kf)
        try:
            os.chmod(kf, 0o644)
            check("smoke.load_private_key: key file mode 0644 refused", smoke.load_private_key, True)
            os.chmod(kf, 0o600)
            check("smoke.load_private_key: mode 0600 accepted (content not shown)",
                  lambda: "loaded" if smoke.load_private_key() == key else None, False)
        finally:
            if old_pm is None:
                os.environ.pop("PM_KEY_FILE", None)
            else:
                os.environ["PM_KEY_FILE"] = old_pm
            kf.unlink()
            kdir.rmdir()
        check("smoke.geoblock_or_refuse with no network -> refused (fails closed)", smoke.geoblock_or_refuse, True)
        g_env = RealEnv(smoke.offline_client(key, None), True)
        g_s = Session(g_env, True, TICKET_DEFAULT, None)
        g_s.rec = lambda *a_, **k_: {}
        g_s.check_geoblock(force=True)
        expect("live: geoblock endpoint unreachable -> no passing check, orders blocked", g_s.geo_ok_at is None
               and g_s.geo_blocked is None)
        g_env.close()

        # ---- the ticket flag and constants
        check("ticket default 10 accepted", lambda: check_ticket("10"), False)
        check("ticket lowered to 5 accepted", lambda: check_ticket("5"), False)
        check("ticket 10.01 refused (never raised)", lambda: check_ticket("10.01"), True)
        check("ticket 50 refused (never raised)", lambda: check_ticket("50"), True)
        check("ticket 4 refused (below 5)", lambda: check_ticket("4"), True)
        expect("hard limit cap is 0.98 and the rule range is [0.95, 0.98)", HARD_MAX_LIMIT == Decimal("0.98")
               and ASK_MIN == Decimal("0.95") and ASK_MAX == Decimal("0.98"))
        expect("fee formula: 10.352 shares at 0.966 -> 0.00340", fee_formula(Decimal("10.352"), Decimal("0.966")) == Decimal("0.00340"),
               fee_formula(Decimal("10.352"), Decimal("0.966")))

        # ---- universe
        tags = {"crypto", "crypto-prices"}
        cases = [
            ("bitcoin-above-on-november-28-2026", "bitcoin-above-60k-on-november-28-2026", ("above", "bitcoin")),
            ("bitcoin-above-on-november-27-2026-4pm-et", "bitcoin-above-60k-on-november-27-2026-4pm-et", None),
            ("bitcoin-price-on-november-28-2026", "will-the-price-of-bitcoin-be-between-60000-62000-on-november-28-2026", ("between", "bitcoin")),
            ("bitcoin-price-on-november-28-2026", "will-the-price-of-bitcoin-be-less-than-52000-on-november-28-2026", ("between-tail", "bitcoin")),
            ("what-price-will-solana-hit-on-november-27-2026", "will-solana-reach-150-on-november-27-2026", ("reach", "solana")),
            ("what-price-will-xrp-hit-on-november-27-2026", "will-xrp-dip-to-1pt8-on-november-27-2026", ("dip", "xrp")),
            ("will-bitcoin-hit-week-of-november-23-2026", "will-bitcoin-reach-70k-november-23-29-2026", None),
            ("what-price-will-bitcoin-hit-in-november-2026", "will-bitcoin-reach-80k-in-november-2026", None),
            ("btc-updown-1d-1795798800", "btc-updown-1d-1795798800", ("updown-daily", "btc")),
            ("btc-updown-4h-1795798800", "btc-updown-4h-1795798800", None),
            ("btc-updown-1h-1795892400", "btc-updown-1h-1795892400", None),
            ("btc-updown-5m-1795805400", "btc-updown-5m-1795805400", None),
            ("spx-up-or-down-on-november-27-2026", "spx-up-or-down-on-november-27-2026", None),
        ]
        for ev, ms, want in cases:
            got = classify(ev, ms, tags if not ev.startswith("spx") else {"finance"})
            expect(f"universe: {ms} -> {want}", got == want, got)

        class _O:   # minimal SDK-like market objects for market_from_sdk
            def __init__(self, **kw):
                self.__dict__.update(kw)
        def sdk_market(slug, rate, end, start_epoch=None):
            return _O(slug=slug, condition_id="0x" + "11" * 32,
                      state=_O(end_date=datetime.fromtimestamp(end, timezone.utc), accepting_orders=True, closed=False, neg_risk=False),
                      trading=_O(fees_enabled=True, fee_schedule=_O(rate=D(rate), exponent=1), seconds_delay=None),
                      outcomes=_O(yes=_O(label="Up", token_id="1" * 70), no=_O(label="Down", token_id="2" * 70)))
        mk, why = market_from_sdk(sdk_market("btc-updown-1d-1795798800", "0.01", 1795798800 + 86400), "btc-updown-1d-1795798800", tags, None)
        expect("daily Up/Down with a 24 h window and rate 0.01 accepted", mk is not None, why)
        mk, why = market_from_sdk(sdk_market("btc-updown-1d-1795798800", "0.01", 1795798800 + 4 * 3600), "btc-updown-1d-1795798800", tags, None)
        expect("'1d' slug whose window is not 24 h refused", mk is None, why)
        mk, why = market_from_sdk(sdk_market("bitcoin-above-60k-on-november-28-2026", "0.05", 1795798800), "bitcoin-above-on-november-28-2026", tags, None)
        expect("fee rate 0.05 refused (rule: 0.01 only)", mk is None, why)

        # ---- the trigger and the favourite
        t10 = Decimal("10")
        expect("ask 0.949 does not trigger", not trigger(_book("a", "0.949", 500, "0.94"), t10)[0])
        expect("ask 0.95 with 10.45 USD triggers", trigger(_book("a", "0.95", 11, "0.94"), t10)[0])
        expect("ask 0.95 with 9.50 USD does not trigger (needs >= 10 USD)", not trigger(_book("a", "0.95", 10, "0.94"), t10)[0])
        expect("ask 0.979 triggers", trigger(_book("a", "0.979", 50, "0.97"), t10)[0])
        expect("ask 0.98 does not trigger (range is [0.95, 0.98))", not trigger(_book("a", "0.98", 500, "0.97"), t10)[0])
        # narrow-book condition (v1.2): favourite's best bid >= best ask - 0.03
        expect("v1.2: narrow book constant is 0.03", MAX_SPREAD == Decimal("0.03"))
        expect("v1.2: ask 0.97, bid 0.94 (exactly 0.03 below) triggers", trigger(_book("a", "0.97", 50, "0.94"), t10)[0],
               trigger(_book("a", "0.97", 50, "0.94"), t10))
        r_ = trigger(_book("a", "0.97", 50, "0.939"), t10)
        expect("v1.2: ask 0.97, bid 0.939 (0.031 below) -> no trigger, reason 'wide book'",
               not r_[0] and r_[1].startswith(WIDE_BOOK), r_)
        r_ = trigger(_book("a", "0.97", 50, "0.27"), t10)
        expect("v1.2: the review's HYPE case, bid 0.27 / ask 0.97 -> no trigger, reason 'wide book'",
               not r_[0] and r_[1].startswith(WIDE_BOOK), r_)
        r_ = trigger(_book("a", "0.97", 50, None), t10)
        expect("v1.2: no bid at all -> no trigger, reason 'wide book'", not r_[0] and r_[1].startswith(WIDE_BOOK), r_)
        r_ = trigger(_book("a", "0.97", 5, "0.27"), t10)
        expect("v1.2: too little at the ask AND wide -> the size reason (wide-book only when all else held)",
               not r_[0] and "USD at the ask" in r_[1], r_)
        pfw = paper_fill(_book("a", "0.97", 50, "0.95"), Decimal("0.97"), t10)
        expect("v1.2: the paper twin carries bid, ask and spread", pfw["best_bid"] == "0.95" and pfw["best_ask"] == "0.97"
               and pfw["spread"] == "0.02", {k: pfw.get(k) for k in ("best_bid", "best_ask", "spread")})
        # balance floor file (v1.2)
        def floor_with(text):
            if FLOOR_FILE.is_dir():
                FLOOR_FILE.rmdir()
            elif FLOOR_FILE.exists():
                FLOOR_FILE.unlink()
            if text is not None:
                FLOOR_FILE.write_bytes(text if isinstance(text, bytes) else text.encode())
            return read_floor
        check("v1.2 FLOOR: file missing -> refused", floor_with(None), True)
        check("v1.2 FLOOR: '36' -> 36", floor_with("36"), False)
        check("v1.2 FLOOR: '36.50' plus newline -> 36.50", floor_with("36.50\n"), False)
        check("v1.2 FLOOR: '0' -> 0 (non-negative)", floor_with("0\n"), False)
        for bad in ("", "-5", "1e3", "NaN", "36 USD", "36\n40", "abc", "36,5", "+36", ".5", "Infinity"):
            check(f"v1.2 FLOOR: {bad!r} -> refused (not a plain non-negative number)", floor_with(bad), True)
        check("v1.2 FLOOR: not ASCII text -> refused (unreadable)", floor_with(b"\xff\xfe3\x006"), True)
        floor_with(None)
        FLOOR_FILE.mkdir()
        check("v1.2 FLOOR: a directory instead of a file -> refused", read_floor, True)
        FLOOR_FILE.rmdir()
        check("v1.2 floor: 100 free - 0 in flight - 10 ticket = 90 >= floor 90 -> allowed",
              lambda: check_floor(D(100), D(0), t10, D(90)), False)
        check("v1.2 floor: 100 - 0 - 10 = 90 < floor 90.01 -> refused", lambda: check_floor(D(100), D(0), t10, D("90.01")), True)
        check("v1.2 floor: 100 - 10 in flight - 10 = 80 < floor 85 -> refused", lambda: check_floor(D(100), D(10), t10, D(85)), True)
        fm = _fake_market(1, 0)
        bks = {fm.tokens["Yes"]: _book(fm.tokens["Yes"], "0.03", 100, "0.02"),
               fm.tokens["No"]: _book(fm.tokens["No"], "0.97", 100, "0.96")}
        expect("favourite = token with the higher mid", favourite(fm, bks)[0] == "No", favourite(fm, bks))
        pf = paper_fill(_book("a", "0.96", 5, "0.95", tick="0.01"), Decimal("0.96"), t10)
        expect("paper model: only 5 shares at the limit -> filled 5 (>= min 5), rest not bought", pf["filled"] and D(pf["shares"]) == 5, pf["shares"])
        pf2 = paper_fill(_book("a", "0.96", 4, "0.95", tick="0.01"), Decimal("0.96"), t10)
        expect("paper model: 4 shares < minimum 5 -> missed", not pf2["filled"], pf2["reason"])

        # ---- signing through the real SDK (offline) and the final guard
        client = smoke.offline_client(key, None)
        out.add_secret(str(client.wallet))
        out.add_secret(str(client.signer))
        tokY, tokN = fm.tokens["Yes"], fm.tokens["No"]
        _register_offline_market(client, (tokY, tokN), fm.key, Decimal("0.001"), FEE_RATE, False)
        sg = client.create_market_order(asset_id=tokN, side="BUY", amount=Decimal("10"), max_price=Decimal("0.966"), order_type="FAK")
        check("signed FAK BUY 10 USD @ <= 0.966 passes the guard", lambda: guard_signed(sg, tokN, t10, Decimal("0.966")), False)
        check("guard: same order checked against a 9 USD ticket refused", lambda: guard_signed(sg, tokN, Decimal("9"), Decimal("0.966")), True)
        check("guard: wrong token refused", lambda: guard_signed(sg, tokY, t10, Decimal("0.966")), True)
        check("guard: signed price above the stated limit refused", lambda: guard_signed(sg, tokN, t10, Decimal("0.955")), True)
        big = client.create_market_order(asset_id=tokN, side="BUY", amount=Decimal("11"), max_price=Decimal("0.966"), order_type="FAK")
        check("guard: 11 USD order refused (ticket 10)", lambda: guard_signed(big, tokN, t10, Decimal("0.966")), True)
        hi = client.create_market_order(asset_id=tokN, side="BUY", amount=Decimal("10"), max_price=Decimal("0.99"), order_type="FAK")
        check("guard: limit 0.99 refused (cap 0.98)", lambda: guard_signed(hi, tokN, t10, Decimal("0.99")), True)
        gtc = client.create_limit_order(asset_id=tokN, price=Decimal("0.966"), size=Decimal("10"), side="BUY")
        check("guard: a resting (GTC) limit order refused", lambda: guard_signed(gtc, tokN, t10, Decimal("0.966")), True)
        sell = client.create_market_order(asset_id=tokN, side="SELL", shares=Decimal("10"), min_price=Decimal("0.95"), order_type="FAK")
        check("guard: a SELL refused", lambda: guard_signed(sell, tokN, t10, Decimal("0.966")), True)
        fok = client.create_market_order(asset_id=tokN, side="BUY", amount=Decimal("10"), max_price=Decimal("0.966"), order_type="FOK")
        check("guard: FOK refused (only FAK)", lambda: guard_signed(fok, tokN, t10, Decimal("0.966")), True)

        # ---- the session against a fake exchange
        def new_session(live=True, ticket=t10, n_markets=1, t0=1_800_000_000.0, ask="0.97", size="200", types=None,
                        floor="20"):
            for p in OUT_DIR.glob("*"):
                p.unlink()
            for f in (STOP_FILE, HALT_FILE, WATERMARK_FILE, FLOOR_FILE):
                if f.exists():
                    f.unlink()
            if floor is not None:
                FLOOR_FILE.write_text(floor + "\n")       # fake free balance is 100 USD
            env = FakeEnv(client, live, t0)
            for i in range(n_markets):
                m = _fake_market(100 + i, t0 + 1800, *(types[i] if types else ()))
                env.mk.append(m)
                env.book_by_token[m.tokens["Yes"]] = _book(m.tokens["Yes"], str(1 - D(ask) + D("0.01")), 300, str(1 - D(ask) - D("0.01")))
                env.book_by_token[m.tokens["No"]] = _book(m.tokens["No"], ask, size, str(D(ask) - D("0.01")))
            s = Session(env, live, ticket, None)
            s.rec("session", version=VERSION)
            s.check_geoblock(force=True)
            s.check_server_time(force=True)
            s.refresh_universe(force=True)
            return env, s

        def recs(typ=None):
            rows = read_records(record_files(True) + record_files(False), strict=False)
            return [r for r in rows if typ is None or r.get("type") == typ]

        env, s = new_session()
        s.poll()
        expect("live: one trigger -> one FAK posted", len(env.posted) == 1, len(env.posted))
        o = recs("order")[-1]
        expect("order record: filled, fill price, shares, ticks vs ask, ack time, fee formula",
               o["fill_state"] == "filled" and o["fill_price"] and o["filled_shares"] and o["fill_vs_ask_ticks"] is not None
               and o["decision_to_ack_ms"] is not None and o["fee_formula"] is not None, {k: o.get(k) for k in ("fill_price", "filled_shares", "fill_vs_ask_ticks", "fee_formula")})
        d = recs("decision")[-1]
        expect("decision record: ask, size, limit = ask, top-10 books of both tokens",
               d["best_ask"] == "0.97" and d["limit"] == "0.97" and d["book"]["asks"] and d["other_book"]["asks"])
        expect("paper twin recorded 2 s after the decision", recs("twin") and recs("twin")[-1]["delta_s"] == 2)
        s.poll()
        s.poll()
        expect("same market, later polls: no second order (one per market)", len(env.posted) == 1, len(env.posted))
        s2 = Session(env, True, t10, None)
        s2.markets = s.markets
        s2.offset = 0.0
        s2.geo_ok_at = env.mono()
        s2.poll()
        expect("a new session on the same records: still no second order", len(env.posted) == 1, len(env.posted))
        env.sleep(FEE_CHECK_AFTER_S + 1)
        s.follow_up()
        f = recs("fee")
        expect("fee check: charged (activity) vs formula, ok", f and f[-1]["mismatch"] is False, f and f[-1]["diff"])

        # result -> loss -> second loss -> permanent stop
        env, s = new_session(n_markets=3)
        s.poll()
        expect("three markets trigger in one poll -> two orders (cap: 2 open tickets at once)", len(env.posted) == 2, len(env.posted))
        expect("the third is refused by the open-ticket cap, with that reason",
               [r for r in recs("decision") if r.get("sent") is False]
               and "cap 2 open" in [r for r in recs("decision") if r.get("sent") is False][-1]["reason"],
               [r.get("reason") for r in recs("decision") if r.get("sent") is False])
        for m in env.mk:
            env.winner[m.key] = "Yes"                     # we bought No: both sent orders lose
        env.sleep(1800 + 10)
        s.follow_up()
        expect("two losing trades -> halt file written (permanent stop)", HALT_FILE.exists())
        expect("halt record written", any(r["type"] == "halt" for r in recs()))
        expect("stopping: no new orders", s.stopping)
        n_before = len(env.posted)
        env.mk.append(_fake_market(200, env.t + 1800))
        mnew = env.mk[-1]
        env.book_by_token[mnew.tokens["Yes"]] = _book(mnew.tokens["Yes"], "0.04", 300, "0.02")
        env.book_by_token[mnew.tokens["No"]] = _book(mnew.tokens["No"], "0.97", 300, "0.96")
        s3 = Session(env, True, t10, None)
        check("start refused while the halt file exists", s3.start_checks, True)
        s3.offset, s3.geo_ok_at = 0.0, env.mono()
        s3.refresh_universe(force=True)
        s3.poll()
        expect("order path refused while halted (no post)", len(env.posted) == n_before, len(env.posted))
        HALT_FILE.unlink()
        s4 = Session(env, True, t10, None)
        check("halt file removed by hand -> start allowed, counting restarts", s4.start_checks, False)
        expect("halt-cleared record written", any(r["type"] == "halt-cleared" for r in recs()))
        expect("loss count after the reset is 0", ledger_now(True).losses()[0] == 0, ledger_now(True).losses())

        # the 20 USD path of the stop (pure ledger function; a 20 USD loss on one trade cannot happen with 10 USD
        # tickets, so this checks the threshold itself)
        def _tr(loss, resolved=True, won=False, state="filled", t_dec=None):
            return {"day": "2026-11-28", "state": state, "shares": D(10), "worst_cost": D(10), "won": won if resolved else None,
                    "loss": D(loss), "result_t": 1.0 if resolved else None, "outcome": "Yes", "resolved": resolved,
                    "ticket": D(10), "t_decision": t_dec}
        L = Ledger()
        L.trades = {"a": _tr(20)}
        expect("v1.2: realised loss 20 USD with one losing trade -> stop", halt_reason(L) is not None, halt_reason(L))
        L.trades["a"]["loss"] = D("19.99")
        expect("v1.2: realised loss 19.99 USD with one losing trade -> no stop yet", halt_reason(L) is None, halt_reason(L))
        L.trades = {"a": _tr("9.99")}
        expect("v1.2: one losing trade of 9.99 USD -> no stop", halt_reason(L) is None, halt_reason(L))
        L.trades = {"a": _tr("9.99"), "b": _tr("0.50")}
        expect("v1.2: two losing trades (10.49 USD in all) -> stop on the count first", halt_reason(L) is not None
               and "2 losing trades" in halt_reason(L), halt_reason(L))
        expect("v1.2: constants: stop 20 USD / 2 losses, 2 open tickets, exposure cap 30, 6 a day",
               (STOP_LOSS_USD, STOP_LOSING_TRADES, MAX_OPEN_TICKETS, EXPOSURE_CAP_USD, MAX_FILLED_PER_DAY)
               == (Decimal("20"), 2, 2, Decimal("30"), 6))
        # open-ticket cap and the exposure gate (pure check_caps)
        L = Ledger()
        L.trades = {"a": _tr(0, resolved=False, state="unknown"), "b": _tr(0, resolved=False)}
        check("v1.2: two open tickets (one of them unknown) -> a third refused", lambda: check_caps(L, "x", "2026-11-28", t10), True)
        L.trades["a"] = _tr(0, resolved=True, won=True)
        check("v1.2: one of them resolved (won) -> a new ticket allowed", lambda: check_caps(L, "x", "2026-11-28", t10), False)
        L.trades = {"a": _tr("15"), "b": _tr(0, resolved=False)}
        check("exposure gate kept: realised 15 + open 10 + ticket 10 = 35 > 30 -> refused (one open ticket only)",
              lambda: check_caps(L, "x", "2026-11-28", t10), True)
        L.trades["a"]["loss"] = D("9.99")
        check("exposure gate: realised 9.99 + open 10 + ticket 10 = 29.99 -> allowed",
              lambda: check_caps(L, "x", "2026-11-28", t10), False)

        # worst-case exposure gate
        env, s = new_session(n_markets=4)
        s.poll()
        expect("four triggers at once -> only two sent (2 open tickets at once)", len(env.posted) == 2, len(env.posted))
        refused = [r for r in recs("decision") if r.get("sent") is False]
        expect("the third and fourth are recorded as refused with their paper twins", len(refused) == 2
               and all("open tickets" in r["reason"] for r in refused) and len(recs("twin")) == 4,
               [r["reason"] for r in refused])

        # daily cap 6 (positions resolve as wins in between so the exposure gate does not bind)
        env, s = new_session(n_markets=8)
        sent_n = []
        for i, m in enumerate(env.mk):
            for other in env.mk:
                other.accepting = other is m
            s.markets = {mm.key: Mkt(**mm.__dict__) for mm in env.mk}
            s.poll()
            env.winner[m.key] = "No"
            for k, ctx in s.decided.items():
                ctx["m"].end = env.t - 1
            s.follow_up()
            sent_n.append(len(env.posted))
        expect("daily cap: 6 filled trades, the 7th and 8th refused", len(env.posted) == 6, sent_n)
        expect("refusal reason names the daily cap", any("cap 6" in r.get("reason", "") for r in recs("decision")))

        # unknown post outcome: never retried, counted as filled (worst case)
        env, s = new_session(n_markets=1)
        env.post_mode = "raise"
        env.err_text = "ReadTimeout talking to 0x" + "ab" * 20
        s.poll()
        s.poll()
        expect("post raised -> exactly one attempt, no retry (trades watched for 120 s, none seen)", len(env.posted) == 1, len(env.posted))
        o = recs("order")[-1]
        expect("unknown outcome recorded, counted as filled at the ticket", o["fill_state"] == "unknown"
               and ledger_now(True).open_exposure() == t10, ledger_now(True).open_exposure())
        expect("error text scrubbed: no 40-hex address in the records", "0x" + "ab" * 20 not in json.dumps(recs()), o.get("error"))
        expect("an unknown fill counts toward the daily cap", ledger_now(True).filled_on(day_of(env.t)) == 1)
        env.winner[env.mk[0].key] = "Yes"
        for ctx in s.decided.values():
            ctx["m"].end = env.t - 1
        orig_act = env.activity
        env.activity = lambda *a_: (_ for _ in ()).throw(RuntimeError("feed down"))
        s.follow_up()
        env.activity = orig_act
        n, usd = ledger_now(True).losses()
        expect("unknown fill on the losing side, late check impossible -> full-ticket loss (worst case)", n == 1 and usd == t10, (n, usd))
        env, s = new_session(n_markets=1)
        env.post_mode = "raise"
        s.poll()
        env.winner[env.mk[0].key] = "Yes"
        for ctx in s.decided.values():
            ctx["m"].end = env.t - 1
        s.follow_up()
        expect("unknown fill, trades list and activity feed both empty after resolution -> recorded unfilled, no loss",
               ledger_now(True).losses()[0] == 0 and recs("order")[-1]["post"] == "late-check", ledger_now(True).losses())

        # definite rejections: nothing bought, market not retried
        env, s = new_session(n_markets=1)
        env.post_mode = "fak"
        s.poll()
        s.poll()
        expect("FAK not filled -> unfilled, one attempt only", len(env.posted) == 1 and recs("order")[-1]["fill_state"] == "unfilled")
        expect("an unfilled order does not count toward the daily cap", ledger_now(True).filled_on(day_of(env.t)) == 0)

        # delayed status is followed until final
        env, s = new_session(n_markets=1)
        env.post_mode = "delayed"
        s.poll()
        o = recs("order")[-1]
        expect("'delayed' -> followed to MATCHED, fill recorded", o["fill_state"] == "filled" and o["status"].startswith("delayed->"), o["status"])

        # a FAK reported as resting is cancelled at once
        env, s = new_session(n_markets=1)
        env.post_mode = "live"
        s.poll()
        expect("'live' FAK -> cancel sent at once", len(env.cancelled) == 1)

        # ---- REVIEW-exp_fav.md (2026-11-27): the reviewer's failing scenarios, now passing
        def resolve(env, s, winner="Yes"):                 # we bought "No": winner "Yes" is a loss
            for mm in env.mk:
                env.winner[mm.key] = winner
            for ctx in s.decided.values():
                ctx["m"].end = env.t - 1
            s.follow_up()

        # M1: a success answer with zero amounts
        env, s = new_session(n_markets=1)
        env.post_mode, env.record_trades = "matched0", False
        s.poll()
        o = recs("order")[-1]
        expect("M1: 'matched' with zero amounts and no trade rows -> unknown, open exposure = the full ticket",
               o["fill_state"] == "unknown" and ledger_now(True).open_exposure() == t10,
               (o["fill_state"], ledger_now(True).open_exposure()))
        expect("M1: ... and it counts toward the daily cap", ledger_now(True).filled_on(day_of(env.t)) == 1)
        env, s = new_session(n_markets=1)
        env.post_mode = "matched0"
        s.poll()
        o = recs("order")[-1]
        expect("M1: 'matched' with zero amounts, trades list shows the fill -> filled at the trades' shares and price",
               o["fill_state"] == "filled" and D(o["filled_shares"]) == D("10.30") and D(o["fill_price"]) == D("0.97"),
               {k: o.get(k) for k in ("fill_state", "filled_shares", "fill_price")})
        resolve(env, s)
        n, usd = ledger_now(True).losses()
        expect("M1: ... and when it loses, the loss is counted (probe gave losses() == (0, 0))",
               n == 1 and usd == D(o["cost"]) and usd > 9, (n, usd))
        env, s = new_session(n_markets=1)
        env.post_mode, env.record_trades = "delayed", False
        env.order_state = lambda oid: {"status": "MATCHED", "size_matched": Decimal(0), "price": Decimal("0.97")}
        s.poll()
        o = recs("order")[-1]
        expect("M1: 'delayed' -> MATCHED with size_matched 0 and no trade rows -> unknown (not unfilled)",
               o["fill_state"] == "unknown", (o["status"], o["fill_state"]))
        env, s = new_session(n_markets=1)
        env.post_mode, env.record_trades = "delayed", False
        env.order_state = lambda oid: {"status": "CANCELED", "size_matched": Decimal(0), "price": Decimal("0.97")}
        s.poll()
        o = recs("order")[-1]
        expect("M1: 'delayed' -> CANCELED, nothing matched, trades list read and empty -> unfilled (definite)",
               o["fill_state"] == "unfilled" and ledger_now(True).open_exposure() == 0, (o["status"], o["fill_state"]))

        # M2: a FAK reported 'live' whose cancel is not confirmed
        env, s = new_session(n_markets=1)
        env.post_mode, env.cancel_ok, env.partial = "live", False, Decimal("0.5")
        s.poll()
        o = recs("order")[-1]
        expect("M2: 'live' FAK, 5 shares filled, cancel not confirmed -> unknown at the full ticket, not 'filled 5'",
               o["fill_state"] == "unknown" and o.get("resting_remainder_possible") is True
               and ledger_now(True).open_exposure() == t10, (o["fill_state"], ledger_now(True).open_exposure()))
        expect("M2: ... and the session stops new orders", s.stopping and any(
            r["type"] == "stopping" and "cancel was not confirmed" in r["why"] for r in recs()))
        resolve(env, s)
        lc = recs("order")[-1]
        n, usd = ledger_now(True).losses()
        expect("S3: after resolution, trades and token balance agree (5 shares) -> late check books the real cost",
               lc["post"] == "late-check" and lc["fill_state"] == "filled" and n == 1 and usd == D(lc["cost"])
               and D("4.8") < usd < D("5.1"), (lc["fill_state"], n, usd))
        env, s = new_session(n_markets=1)
        env.post_mode, env.partial = "live", Decimal("0.5")
        env.cancel = lambda oid: (_ for _ in ()).throw(RuntimeError("cancel endpoint down"))
        s.poll()
        expect("M2: cancel raised -> unknown at the full ticket, session stops",
               recs("order")[-1]["fill_state"] == "unknown" and s.stopping)
        env.held[env.mk[0].tokens["No"]] = Decimal("10.30")    # the remainder filled later, outside the trades read
        resolve(env, s)
        n, usd = ledger_now(True).losses()
        expect("S3: token balance shows more shares than the trades -> stays unknown, full-ticket loss",
               recs("order")[-1]["fill_state"] == "unknown" and (n, usd) == (1, t10), (n, usd))

        # S3: the token balance as the third source before an unknown order is downgraded
        env, s = new_session(n_markets=1)
        env.post_mode = "raise"
        s.poll()
        env.token_balance = lambda tok: (_ for _ in ()).throw(RuntimeError("balance endpoint down"))
        resolve(env, s)
        n, usd = ledger_now(True).losses()
        expect("S3: unknown fill, trades and feed empty, token balance unreadable -> not downgraded, full-ticket loss",
               (n, usd) == (1, t10), (n, usd))
        env, s = new_session(n_markets=1)
        env.post_mode = "raise"
        s.poll()
        env.held[env.mk[0].tokens["No"]] = Decimal("10.30")
        resolve(env, s)
        n, usd = ledger_now(True).losses()
        expect("S3: unknown fill, trades and feed empty, but the account holds the shares -> full-ticket loss",
               (n, usd) == (1, t10), (n, usd))

        # M3: the fill price comes from the trades, never from get_order (which returns the limit)
        env, s = new_session(n_markets=1)
        env.post_mode, env.fill_px = "delayed", Decimal("0.96")
        s.poll()
        o = recs("order")[-1]
        expect("M3: 'delayed' order printed at 0.96 under a 0.97 limit -> fill price 0.96, -10 ticks (probe: 0.97, 0)",
               D(o["fill_price"]) == D("0.96") and D(o["fill_vs_ask_ticks"]) == D("-10"),
               {k: o.get(k) for k in ("status", "fill_price", "fill_vs_ask_ticks")})
        env, s = new_session(n_markets=1)
        env.fill_px, env.resp_px = Decimal("0.96"), Decimal("0.97")
        s.poll()
        o = recs("order")[-1]
        expect("M3: response amounts imply 0.97, trade legs 0.96 -> fill price from the legs, disagreement recorded",
               D(o["fill_price"]) == D("0.96") and D(o["fill_price_response"]) == D("0.97")
               and o.get("price_sources_disagree") is True, {k: o.get(k) for k in ("fill_price", "fill_price_response")})
        env, s = new_session(n_markets=1)
        env.post_mode = "swapped"
        s.poll()
        o = recs("order")[-1]
        expect("making/taking the other way round -> swapped back, response price 0.97, no disagreement",
               D(o["fill_price_response"]) == D("0.97") and not o.get("price_sources_disagree"), o.get("fill_price_response"))

        # S8: a split result is resolved and its partial loss counted
        env, s = new_session(n_markets=1)
        s.poll()
        o = recs("order")[-1]
        env.split = True
        resolve(env, s)
        L = ledger_now(True)
        tr0 = next(iter(L.trades.values()))
        want = D(o["cost"]) - Decimal("0.5") * D(o["filled_shares"])
        expect("S8: split -> resolved (open exposure 0), loss = cost - 0.5 x shares, counted as a losing trade",
               L.open_exposure() == 0 and tr0["loss"] == want and L.losses() == (1, want), (L.open_exposure(), tr0["loss"]))

        # S1: the live ledger cannot silently restart empty in another folder
        env, s = new_session(n_markets=1)
        s.poll()
        expect("S1: a live decision raises the watermark outside the checkout to 1", read_watermark() == 1, read_watermark())
        check("S1: live start allowed while the records hold every live decision", Session(env, True, t10, None).start_checks, False)
        for p in OUT_DIR.glob("*"):
            p.unlink()                                   # as in a fresh checkout: the records are not here
        check("S1: live start refused when the records hold fewer live decisions than were written",
              Session(env, True, t10, None).start_checks, True)

        # S2: never live next to exp_bids.py on the same account
        held_bids = acquire_lock(BIDS_LOCK_FILE)

        def run_live_next_to_bids():
            try:
                cmd_run(argparse.Namespace(live=True, ticket="10", hours=None))
            except Refusal as e:
                if "exp_bids" in str(e):
                    raise
                return f"refused for another reason: {e}"
            return "started"
        check("S2: run --live refused while a live exp_bids.py holds its lock (before the key is read)",
              run_live_next_to_bids, True)
        held_bids.close()

        # S4 / S6: the real exchange adapter with fake SDK objects (no network)
        from polymarket.errors import RequestRejectedError

        class _It(list):
            def iter_items(self):
                return iter(self)
        ra = RealEnv.__new__(RealEnv)
        ra.live, ra.pub = True, None

        class _Post:
            def __init__(self, status):
                self.status = status

            def post_order(self, signed):
                raise RequestRejectedError("rejected", status=self.status, code="x")
        ra.c = _Post(400)
        expect("S6: RealEnv.post: HTTP 400 -> definite rejection (nothing bought)", ra.post(None)["ok"] is False)
        for st_ in (408, 429, 500, 503):
            ra.c = _Post(st_)
            try:
                ra.post(None)
                how = "returned"
            except RequestRejectedError:
                how = "raised"
            expect(f"S6: RealEnv.post: HTTP {st_} -> outcome unknown (raised, never booked as rejected)", how == "raised")

        class _Pub:
            def __init__(self, payouts):
                self.payouts = payouts

            def get_resolutions(self, condition_ids):
                return [_O(status="resolved", payouts=self.payouts)]

            def list_markets(self, **kw):
                return _It()
        ra.pub = _Pub((Decimal(0), Decimal(1)))
        expect("S6: RealEnv.result: payouts (0, 1) -> the second outcome", ra.result(fm) == ("No", False), ra.result(fm))
        ra.pub = _Pub((Decimal("0.5"), Decimal("0.5")))
        expect("S6: RealEnv.result: payouts (0.5, 0.5) -> split", ra.result(fm) == ("split 0.5/0.5", True), ra.result(fm))
        tA, tB = fm.tokens["No"], fm.tokens["Yes"]

        def _trade(i, status, side="TAKER"):
            return _O(trader_side=side, side="BUY", status=status, id=f"t{i}", taker_order_id="o1", price=D("0.966"),
                      size=D("10"), fee_rate_bps=100, matched_at=None, transaction_hash="0x" + "cd" * 32,
                      maker_orders=[_O(asset_id=tA, price=D("0.97"), matched_amount=D("6")),
                                    _O(asset_id=tB, price=D("0.04"), matched_amount=D("4"))])

        class _Tr:
            def list_account_trades(self, asset_id=None, after=None):
                return _It([_trade(1, "CONFIRMED"), _trade(2, "FAILED"), _trade(3, "MATCHED", side="MAKER")])
        ra.c = _Tr()
        tr = ra.trades(tA, 0)
        expect("S4: a FAILED trade and a maker trade are not fills; S6: complement-token leg 0.04 -> 0.96",
               len(tr) == 1 and tr[0]["legs"] == [["0.97", "6"], ["0.96", "4"]], tr and tr[0]["legs"])
        sh, avg, fee = fill_from_trades(tr)
        expect("fill from the legs: 10 shares at 0.966, fee per leg", sh == 10 and avg == D("0.966")
               and fee == fee_formula(D(6), D("0.97")) + fee_formula(D(4), D("0.96")), (sh, avg, fee))

        class _Bal:
            def __init__(self, ok):
                self.ok = ok

            def get_balance_allowance(self, asset_type, asset_id=None, token_id=None):
                if self.ok and asset_type == "CONDITIONAL" and token_id == tA:
                    return _O(balance=5_150_000)
                raise RuntimeError("not readable")
        ra.c = _Bal(True)
        expect("S3: RealEnv.token_balance reads the CONDITIONAL balance in base units", ra.token_balance(tA) == D("5.15"))
        ra.c = _Bal(False)
        try:
            ra.token_balance(tA)
            how = "returned"
        except RuntimeError:
            how = "raised"
        expect("S3: RealEnv.token_balance unreadable -> raises (never reads as zero)", how == "raised")

        # ---- v1.2: narrow-book condition in the session
        def wide_books(env, m, bid):
            env.book_by_token[m.tokens["No"]] = _book(m.tokens["No"], "0.97", 200, bid)      # mid (0.97 + bid) / 2
            env.book_by_token[m.tokens["Yes"]] = _book(m.tokens["Yes"], "0.40", 300, "0.03")  # mid 0.215: No is the favourite
        for live_ in (True, False):
            lab = "live" if live_ else "dry-run"
            env, s = new_session(live=live_, n_markets=1)
            m0 = env.mk[0]
            wide_books(env, m0, "0.27")
            s.poll()
            wb = recs("wide-book")
            expect(f"v1.2 {lab}: favourite bid 0.27 / ask 0.97 -> no decision, nothing signed or posted",
                   len(env.posted) == 0 and not recs("decision") and m0.key not in ledger_now(live_).consumed)
            expect(f"v1.2 {lab}: ... recorded as 'wide-book' with its own reason, bid, ask and spread",
                   len(wb) == 1 and wb[0]["why"].startswith(WIDE_BOOK) and wb[0]["best_bid"] == "0.27"
                   and wb[0]["best_ask"] == "0.97" and wb[0]["spread"] == "0.70", wb and {k: wb[0].get(k) for k in
                                                                                        ("why", "best_bid", "spread")})
            s.poll()
            expect(f"v1.2 {lab}: a second wide poll within a minute adds no record", len(recs("wide-book")) == 1)
            env.sleep(61)
            s.prev_wall = s.prev_mono = None
            s.poll()
            expect(f"v1.2 {lab}: a minute later one more record, counting the polls in between",
                   len(recs("wide-book")) == 2 and recs("wide-book")[-1]["polls_since_last"] == 2,
                   recs("wide-book") and recs("wide-book")[-1].get("polls_since_last"))
            wide_books(env, m0, "0.95")
            s.poll()
            dd = recs("decision")
            tw = recs("twin")
            expect(f"v1.2 {lab}: the book narrows (bid 0.95) -> the same market triggers on a later poll",
                   len(dd) == 1 and dd[0]["sent"] is True and len(env.posted) == (1 if live_ else 0), (len(dd), len(env.posted)))
            expect(f"v1.2 {lab}: the decision and the paper twin carry bid, ask and spread",
                   dd and dd[0]["best_bid"] == "0.95" and dd[0]["best_ask"] == "0.97" and dd[0]["spread"] == "0.02"
                   and dd[0]["max_spread"] == "0.03" and tw and tw[0]["decision_spread"] == "0.02"
                   and tw[0]["decision_best_bid"] == "0.95" and tw[0]["spread"] == "0.02" and tw[0]["best_bid"] == "0.95",
                   tw and {k: tw[0].get(k) for k in ("decision_best_bid", "decision_spread", "best_bid", "spread")})

        # ---- v1.2: balance floor in the session
        env, s = new_session(n_markets=1, floor=None)
        s.poll()
        d_ = recs("decision")
        expect("v1.2 floor: live, FLOOR file missing -> order refused, recorded with the reason (market consumed)",
               len(env.posted) == 0 and d_ and d_[-1]["sent"] is False and "floor file" in d_[-1]["reason"],
               d_ and d_[-1]["reason"])
        env, s = new_session(live=False, n_markets=1, floor=None)
        s.poll()
        d_ = recs("decision")
        expect("v1.2 floor: dry-run, FLOOR file missing -> unaffected (decided and signed, nothing posted)",
               d_ and d_[-1]["sent"] is True and d_[-1]["signed"] and len(env.posted) == 0, d_ and d_[-1]["reason"])
        env, s = new_session(n_markets=2, floor="85")
        s.poll()
        d_ = recs("decision")
        expect("v1.2 floor: free 100, floor 85: first order 100 - 10 = 90 >= 85 sent; second in the same poll "
               "100 - 10 in flight - 10 = 80 < 85 refused", len(env.posted) == 1 and len(d_) == 2 and d_[1]["sent"] is False
               and "balance floor" in d_[1]["reason"] and d_[0]["balance_floor"]["floor"] == "85"
               and d_[1]["balance_floor"]["in_flight"] == "10", [(r["sent"], r["reason"][:60]) for r in d_])
        env, s = new_session(n_markets=1, floor="90.01")
        s.poll()
        expect("v1.2 floor: free 100 - ticket 10 = 90 < floor 90.01 -> refused", len(env.posted) == 0
               and "balance floor" in recs("decision")[-1]["reason"], recs("decision")[-1]["reason"])
        env, s = new_session(n_markets=1)
        env.balance = lambda: (_ for _ in ()).throw(RuntimeError("balance endpoint down"))
        s.poll()
        expect("v1.2 floor: free balance unreadable -> refused", len(env.posted) == 0
               and "not readable" in recs("decision")[-1]["reason"], recs("decision")[-1]["reason"])
        env, s = new_session(n_markets=1, floor="25")
        FLOOR_FILE.write_text("95\n")                    # the owner raises the floor mid-session
        s.poll()
        expect("v1.2 floor: the file is read again before every order (raised to 95 mid-session -> refused)",
               len(env.posted) == 0 and "floor 95" in recs("decision")[-1]["reason"], recs("decision")[-1]["reason"])
        env, s = new_session(n_markets=1)
        orig_bal = env.balance

        def slow_balance():
            env.sleep(2.0)                               # the balance read takes 2 s: the book is then too old
            return orig_bal()
        env.balance = slow_balance
        s.poll()
        expect("v1.2 floor: book older than 1.5 s after the balance read -> technical skip, market not consumed",
               len(env.posted) == 0 and not recs("decision") and recs("tech-skip")
               and "after the balance read" in recs("tech-skip")[-1]["why"], recs("tech-skip") and recs("tech-skip")[-1]["why"])
        env, s = new_session(n_markets=1, floor=None)
        check("v1.2 floor: live start refused when the FLOOR file is missing", Session(env, True, t10, None).start_checks, True)
        env, s = new_session(n_markets=1, floor="abc")
        check("v1.2 floor: live start refused when the FLOOR file is malformed", Session(env, True, t10, None).run, True)
        env, s = new_session(n_markets=1, floor="95")
        check("v1.2 floor: live start refused when free 100 - one ticket 10 < floor 95", Session(env, True, t10, None).run, True)
        env, s = new_session(live=False, n_markets=1, floor=None)
        check("v1.2 floor: dry-run start allowed without a FLOOR file", Session(env, False, t10, None).start_checks, False)
        old_pm = os.environ.get("PM_KEY_FILE")
        os.environ["PM_KEY_FILE"] = str(tmp / "no-such-key")

        def run_live_without_floor():
            try:
                cmd_run(argparse.Namespace(live=True, ticket="10", hours=None))
            except Refusal as e:
                if "floor file" in str(e):
                    raise
                return f"refused for another reason: {e}"
            return "started"
        try:
            env, s = new_session(n_markets=1, floor=None)
            check("v1.2 floor: run --live refused before the key is read when the FLOOR file is missing",
                  run_live_without_floor, True)
        finally:
            if old_pm is None:
                os.environ.pop("PM_KEY_FILE", None)
            else:
                os.environ["PM_KEY_FILE"] = old_pm

        # STOP file
        env, s = new_session(n_markets=1)
        STOP_FILE.write_text("stop")
        s.poll()
        expect("STOP file -> no order", len(env.posted) == 0)
        check("STOP file -> start refused", Session(env, True, t10, None).start_checks, True)
        STOP_FILE.unlink()

        # clock and lag checks (not consuming the market)
        env, s = new_session(n_markets=1)
        env.offset = 4.0
        s.check_server_time(force=True)
        s.poll()
        expect("server clock 4 s off -> no order, recorded as a technical skip", len(env.posted) == 0 and recs("tech-skip"))
        env.offset = 0.0
        s.check_server_time(force=True)
        s.poll()
        expect("clock fixed -> the same market trades on a later poll", len(env.posted) == 1, len(env.posted))
        env, s = new_session(n_markets=1)
        s.poll()                                   # first poll sets the clock baseline; market not decided yet?
        posted0 = len(env.posted)
        env, s = new_session(n_markets=1)
        s.prev_wall, s.prev_mono = env.wall(), env.mono()
        env.jump(30)                               # wall clock steps 30 s, monotonic does not
        s.poll()
        expect("wall-clock jump of 30 s -> no order on that poll", len(env.posted) == 0, recs("tech-skip")[-1]["why"] if recs("tech-skip") else "")
        env, s = new_session(n_markets=1)
        s.poll(late=40.0)
        expect("poll 40 s late (Mac slept) -> no order on that poll", len(env.posted) == 0)
        env, s = new_session(n_markets=1)
        orig_books = env.books
        env.books = lambda toks: {k: Book(b.token, b.asks, b.bids, b.tick, b.min_size, env.t - 3.0) for k, b in orig_books(toks).items()}
        s.poll()
        expect("book 3 s old at decision -> no order", len(env.posted) == 0)
        expect(f"posted on a normal first poll (control) = {posted0}", posted0 == 1)

        # geoblock
        env, s = new_session(n_markets=1)
        env.geo = {"blocked": True, "country": "US", "urllib_blocked": True}
        s.check_geoblock(force=True)
        s.poll()
        expect("live: geoblocked -> stopping, no order", s.stopping and len(env.posted) == 0)
        env, s = new_session(n_markets=1)
        env.geo = {"blocked": False, "country": "RS", "urllib_blocked": True}
        s.check_geoblock(force=True)
        expect("live: the two geoblock checks disagree -> treated as blocked", s.stopping)
        env, s = new_session(n_markets=1)
        env.sleep(GEO_MAX_AGE_S + 5)
        s.prev_wall = s.prev_mono = None
        s.check_server_time(force=True)
        env.geo = {"blocked": True, "country": "US", "urllib_blocked": True}
        calls = env.geo_calls
        s.poll()
        expect("geoblock check older than 60 min -> re-checked before the order; blocked -> no order",
               env.geo_calls > calls and len(env.posted) == 0)
        env, s = new_session(n_markets=1)
        env.geo = {"blocked": True, "country": "US", "urllib_blocked": True}
        s5 = Session(env, True, t10, None)
        check("live run refused at start when geoblocked", s5.run, True)

        # balance
        env, s = new_session(n_markets=1)
        env.bal = Decimal("9.99")
        s6 = Session(env, True, t10, None)
        check("live run refused at start when the balance is below one ticket", s6.run, True)
        env, s = new_session(n_markets=1)
        env.approved = False
        check("live run refused at start when trading approvals are incomplete", Session(env, True, t10, None).run, True)

        # min order size
        env, s = new_session(n_markets=1, ask="0.97")
        env.book_by_token[env.mk[0].tokens["No"]].min_size = Decimal("20")
        s.poll()
        expect("ticket buys fewer shares than the market minimum -> refused", len(env.posted) == 0
               and "minimum" in recs("decision")[-1]["reason"])

        # one position per market: account already traded it
        env, s = new_session(n_markets=1)
        env.traded_before.add(env.mk[0].tokens["Yes"])
        s.poll()
        expect("the account already traded this market -> skipped for good", len(env.posted) == 0)

        # window
        env, s = new_session(n_markets=1)
        env.mk[0].end = env.t + WINDOW_S + 60
        s.markets[env.mk[0].key].end = env.t + WINDOW_S + 60
        s.poll()
        expect("61 min before the end (outside the window) -> no trigger", len(env.posted) == 0)
        s.markets[env.mk[0].key].end = env.t - 300
        s.markets[env.mk[0].key].closed = True
        s.poll()
        expect("market closed -> no trigger", len(env.posted) == 0)
        s.markets[env.mk[0].key].closed = False
        s.poll()
        expect("after endDate but still open (doc: window runs to the close) -> trigger", len(env.posted) == 1)

        # dry-run never posts and records the would-be order
        env, s = new_session(live=False, n_markets=2)
        s.poll()
        expect("dry-run: nothing posted", len(env.posted) == 0)
        dr = [r for r in recs("decision") if r["mode"] == "dry-run"]
        expect("dry-run: decisions with the signed would-be order recorded", len(dr) == 2 and dr[0]["signed"]["order_type"] == "FAK",
               dr and dr[0]["signed"])
        env.post_mode = "matched"
        check("dry-run env refuses post", lambda: env.post(None), True)

        # lock
        f1 = acquire_lock(LOCK_FILE)
        check("second instance refused by the lock", lambda: acquire_lock(LOCK_FILE), True)
        f1.close()
        check("lock free again after the first instance ends", lambda: acquire_lock(LOCK_FILE).close(), False)

        # corrupt record file is refused in live (ledger must be complete)
        with open(records_path(day_of(env.t), True), "a") as fh:
            fh.write('{"type": "decision", "key": broken\n')
        check("a corrupt live record line refuses the live ledger", lambda: ledger_now(True), True)

        # secrets
        allrec = "".join(Path(p).read_text() for p in glob.glob(str(OUT_DIR / "*")))
        expect("records hold no private key", key[2:].lower() not in allrec.lower())
        expect("records hold no wallet or signer address", str(client.wallet).lower()[2:] not in allrec.lower()
               and str(client.signer).lower()[2:] not in allrec.lower())
        expect("records hold no 40-hex address at all", not ADDRESS_RE.search(allrec))
        client.close()
        leaked = key[2:] in out.log_path.read_text().lower()
        expect("private key absent from the log file", not leaked)
    finally:
        OUT_DIR, STOP_FILE, HALT_FILE, LOCK_FILE, BIDS_LOCK_FILE, WATERMARK_FILE, FLOOR_FILE = saved
        out.log_path = Path(os.devnull)
        for p in sorted(tmp.rglob("*"), reverse=True):
            p.unlink() if p.is_file() else p.rmdir()
        tmp.rmdir()
    out(f"selftest: {n_checks} checks, {'ALL PASS' if ok else 'FAILURES'}")
    return 0 if ok else 1


# ----------------------------------------------------------------------------- main
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run", help="the session loop (dry-run unless --live)")
    r.add_argument("--live", action="store_true", help="send real orders (default: dry-run, nothing sent)")
    r.add_argument("--ticket", default=str(TICKET_DEFAULT), help="USD per order: 10 (default) or lower, minimum 5")
    r.add_argument("--hours", type=float, default=None, help="stop looking for new trades after this many hours")
    rp = sub.add_parser("report", help="summary of the records")
    rp.add_argument("files", nargs="*")
    rp.add_argument("--dry-run", action="store_true", help="report the dry-run (paper) records")
    sub.add_parser("selftest", help="offline checks of every cap and refusal")
    return p


def main(argv=None) -> int:
    global out
    out = FavOut()
    smoke.out = out                       # smoke.py's helpers (key loading, geoblock) print through the same redactor
    a = build_parser().parse_args(argv)
    if a.command == "selftest":
        out.log_path = Path(os.devnull)   # S9: the selftest never writes into the real log (it logs to a temp file)
    mode = "LIVE" if getattr(a, "live", False) else "dry-run"
    out(f"=== exp_fav.py {a.command} {mode if a.command == 'run' else ''} "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC ({VERSION})")
    try:
        smoke.sdk()
        return {"run": cmd_run, "report": cmd_report, "selftest": cmd_selftest}[a.command](a)
    except Refusal as e:
        out(f"REFUSED: {scrub(e)}")
        return 2
    except Exception as e:  # noqa: BLE001
        out(f"ERROR: {scrub(type(e).__name__ + ': ' + str(e))}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
