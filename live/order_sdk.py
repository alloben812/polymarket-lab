"""Pinned Polymarket SDK adapter for a separately authorized canary.

Authenticated operations run in a short-lived, isolated process. The operator
supplies an existing Deposit Wallet, an authorized CLOB session signer, and
already-issued L2 credentials. The worker allows only official HTTPS reads
and the one explicitly permitted order mutation. It cannot deploy wallets,
create credentials, or refresh allowances. Its standard streams are discarded.

A cancelled order can have matched shares. OrderState.terminal describes the
CLOB order, while settlement_final requires confirmed indexed maker fills for
its matched quantity. A missing or unrecognized order is ambiguous.
"""

from collections.abc import Callable
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from importlib.metadata import version
import json
import logging
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import time
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


SDK_VERSION = "0.20.1"
_REPO = Path(__file__).resolve().parents[1]
_CLOB = "clob.polymarket.com"
_GEO_URL = "https://polymarket.com/api/geoblock"
_READ_HOSTS = {
    _CLOB,
    "gamma-api.polymarket.com",
    "data-api.polymarket.com",
    "relayer-v2.polymarket.com",
}
_TOKEN = re.compile(r"[1-9][0-9]{0,77}")
_HASH = re.compile(r"0x[0-9a-fA-F]{64}")
_ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}")
_KEY = re.compile(r"(?:0x)?[0-9a-fA-F]{64}")
_IPC_LIMIT = 65536
_KEY_LIMIT = 4096
_TIMEOUT = 25
_GTD_EXPIRATION_S = 185
_SAFE_CODES = {
    "account_nonempty",
    "account_check_unavailable",
    "book_unavailable",
    "credential_file",
    "credential_unavailable",
    "geo_unavailable",
    "geo_blocked",
    "invalid_order",
    "sdk_unavailable",
    "order_rejected",
    "order_uncertain",
    "permission_denied",
}
_DOCUMENTED_REJECTIONS = {
    "market_not_ready",
    "not_enough_balance",
    "invalid_nonce",
    "invalid_expiration",
    "post_only_would_cross",
    "post_only_mode",
}


class OrderError(RuntimeError):
    def __init__(self, code: str):
        self.code = code if code in _SAFE_CODES else "sdk_unavailable"
        super().__init__(self.code)


class OrderUncertain(OrderError):
    def __init__(self):
        super().__init__("order_uncertain")


@dataclass(frozen=True)
class PublicBook:
    token: str
    condition_id: str
    best_bid: Decimal
    best_ask: Decimal
    min_size: Decimal
    tick_size: Decimal
    timestamp_ms: int


@dataclass(frozen=True)
class OrderState:
    order_id: str
    token: str
    condition_id: str
    price: Decimal
    size: Decimal
    filled: Decimal
    status: str
    terminal: bool
    settlement_final: bool
    side: str = "BUY"


def _identifier(value, pattern) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise OrderError("invalid_order")
    return value.lower()


def _token(value) -> str:
    token = _identifier(value, _TOKEN)
    if int(token).bit_length() > 256:
        raise OrderError("invalid_order")
    return token


def _decimal(value) -> Decimal:
    if not isinstance(value, (Decimal, str, int)) or isinstance(value, bool):
        raise ValueError("invalid decimal")
    number = Decimal(value)
    if (
        not number.is_finite()
        or number.adjusted() > 24
        or number.as_tuple().exponent < -24
    ):
        raise ValueError("invalid decimal")
    return number


def _order_terms(price, size) -> tuple[Decimal, Decimal]:
    try:
        price, size = _decimal(price), _decimal(size)
        if 0 < price < 1 and size > 0 and size % Decimal(".01") == 0:
            return price, size
    except (ValueError, InvalidOperation):
        pass
    raise OrderError("invalid_order")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _public_json(url: str):
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    request = Request(
        url, headers={"User-Agent": "pmlab-public/1", "Accept": "application/json"}
    )
    with opener.open(request, timeout=6) as response:
        return json.loads(response.read(2_000_001))


def _best(levels, select) -> Decimal:
    prices = []
    for level in levels:
        price, size = _decimal(level.price), _decimal(level.size)
        if not (0 < price < 1 and size > 0):
            raise ValueError("invalid depth")
        prices.append(price)
    return select(prices)


def _public_book(token: str, condition_id: str) -> PublicBook:
    try:
        from polymarket import PublicClient

        with PublicClient() as client:
            book = client.get_order_book(asset_id=token)
        if (
            str(book.asset_id) != token
            or _identifier(str(book.condition_id), _HASH) != condition_id
        ):
            raise ValueError("mismatched market")
        bid, ask = _best(book.bids, max), _best(book.asks, min)
        minimum, tick = _decimal(book.min_order_size), _decimal(book.tick_size)
        if book.timestamp is None or book.timestamp.tzinfo is None:
            raise ValueError("invalid timestamp")
        timestamp = int(book.timestamp.timestamp() * 1000)
        if not (
            -1000 <= time.time_ns() // 1_000_000 - timestamp <= 10_000
            and bid < ask
            and minimum > 0
            and 0 < tick < 1
        ):
            raise ValueError("invalid book or freshness")
        return PublicBook(token, condition_id, bid, ask, minimum, tick, timestamp)
    except Exception:
        raise OrderError("book_unavailable") from None


def verify_book(token: str, condition_id: str) -> PublicBook:
    request = {
        "operation": "book",
        "token": _token(token),
        "condition_id": _identifier(condition_id, _HASH),
    }
    result = _invoke(None, request)
    try:
        for name in ("best_bid", "best_ask", "min_size", "tick_size"):
            result[name] = _decimal(result[name])
        return PublicBook(**result)
    except (KeyError, InvalidOperation, TypeError, ValueError):
        raise OrderError("book_unavailable") from None


def geo_allowed() -> bool:
    try:
        payload = _public_json(_GEO_URL)
        if type(payload["blocked"]) is not bool:
            raise ValueError("invalid geoblock response")
        return not payload["blocked"]
    except Exception:
        raise OrderError("geo_unavailable") from None


def _require_passive(book: PublicBook, price: Decimal, size: Decimal) -> None:
    if price >= book.best_ask or price % book.tick_size != 0 or size < book.min_size:
        raise OrderError("invalid_order")


def _read_credentials(path: Path) -> dict[str, str]:
    """Open every component relative to a descriptor without following symlinks."""
    if not path.is_absolute() or ".." in path.parts or path.is_relative_to(_REPO):
        raise OrderError("credential_file")
    try:
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY
        parent = os.open("/", flags)
        try:
            for name in path.parts[1:-1]:
                child = os.open(name, flags, dir_fd=parent)
                os.close(parent)
                parent = child
                try:
                    os.stat(".git", dir_fd=parent, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    raise ValueError("credentials are under a Git worktree")
            fd = os.open(
                path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
            )
            with os.fdopen(fd, "rb") as source:
                info = os.fstat(source.fileno())
                if (
                    not stat.S_ISREG(info.st_mode)
                    or stat.S_IMODE(info.st_mode) != 0o600
                    or info.st_uid != os.geteuid()
                    or info.st_nlink != 1
                    or not 0 < info.st_size <= _KEY_LIMIT
                ):
                    raise ValueError("unsafe file")
                body = source.read(_KEY_LIMIT + 1)
                if len(body) > _KEY_LIMIT:
                    raise ValueError("credential file changed")
                data = json.loads(body)
        finally:
            os.close(parent)
        expected = {
            "session_private_key",
            "session_signer",
            "deposit_wallet",
            "api_key",
            "api_secret",
            "api_passphrase",
        }
        if set(data) != expected or any(
            not isinstance(v, str) or not v for v in data.values()
        ):
            raise ValueError("invalid credential fields")
        if (
            not _KEY.fullmatch(data["session_private_key"])
            or not _ADDRESS.fullmatch(data["session_signer"])
            or not _ADDRESS.fullmatch(data["deposit_wallet"])
            or data["session_signer"].lower() == data["deposit_wallet"].lower()
        ):
            raise ValueError("invalid signer or wallet")
        return data
    except (OSError, TypeError, ValueError, AttributeError):
        raise OrderError("credential_file") from None


class _NetworkGate:
    """The pinned SDK's synchronous transport only uses httpx.Client."""

    def __init__(self):
        self.mutation = None

    def allow(
        self, method: str, scheme: str, host: str, path: str, port: int | None
    ) -> None:
        if scheme != "https" or host not in _READ_HOSTS or port not in (None, 443):
            raise OrderError("sdk_unavailable")
        if method == "GET" and self.mutation is None:
            return
        if host == _CLOB and path == "/order" and method == self.mutation:
            self.mutation = None
            return
        raise OrderError("sdk_unavailable")

    def install(self):
        import httpx

        send = httpx.Client.send

        def guarded(client, request, **kwargs):
            url = request.url
            self.allow(request.method, url.scheme, url.host, url.path, url.port)
            return send(client, request, **{**kwargs, "follow_redirects": False})

        httpx.Client.send = guarded


def _secure_client(path: Path):
    from eth_account import Account
    from polymarket import ApiKeyCreds, SecureClient
    from polymarket._internal.environment import get_environment_config
    from polymarket._internal.wallet import classify_account
    from polymarket.environments import PRODUCTION

    creds = _read_credentials(path)
    wallet = creds["deposit_wallet"]
    signer = Account.from_key(creds["session_private_key"]).address
    config = get_environment_config(PRODUCTION)
    account = classify_account(
        signer=signer, wallet=wallet, config=config.wallet_derivation
    )
    if signer.lower() != creds["session_signer"].lower() or (
        account.wallet_type,
        account.signer_type,
    ) != ("DEPOSIT_WALLET", "SESSION_KEY"):
        raise OrderError("credential_unavailable")
    # The network gate blocks credential bootstrap and undeployed-wallet recovery.
    return SecureClient.create(
        private_key=creds["session_private_key"],
        wallet=wallet,
        environment=PRODUCTION,
        credentials=ApiKeyCreds(
            apiKey=creds["api_key"],
            secret=creds["api_secret"],
            passphrase=creds["api_passphrase"],
        ),
    )


def _complete_items(paginator):
    seen = set()
    page = None
    for page in paginator:
        if page.limit_reached:
            raise OrderError("account_check_unavailable")
        cursor = page.next_cursor
        if page.has_more and (not cursor or cursor in seen):
            raise OrderError("account_check_unavailable")
        seen.add(cursor)
        yield from page.items
    if page is None or page.has_more:
        raise OrderError("account_check_unavailable")


def _clear_wallet(client) -> None:
    try:
        if client.get_closed_only_mode() is not False:
            raise OrderError("account_check_unavailable")
        for _ in _complete_items(client.list_wallet_open_orders()):
            raise OrderError("account_nonempty")
        now = int(time.time())
        utc_midnight = now // 86_400 * 86_400
        wallet = str(client.wallet)
        for filters in ({"include_archived": True}, {"status": "CLOSED"}):
            positions = client.list_positions(user=wallet, full_history=True, **filters)
            for position in _complete_items(positions):
                if str(position.wallet).lower() != wallet.lower():
                    raise OrderError("account_check_unavailable")
                if _decimal(position.current_size) != 0:
                    raise OrderError("account_nonempty")
                changed = position.last_event_at
                if changed is None or changed.tzinfo is None:
                    raise OrderError("account_check_unavailable")
                if changed.timestamp() >= utc_midnight:
                    raise OrderError("account_nonempty")
        # An explicit UTC lower bound cannot be combined with full_history.
        for activity in _complete_items(
            client.list_activity(user=wallet, start=utc_midnight)
        ):
            if (
                str(activity.wallet).lower() != wallet.lower()
                or activity.timestamp.tzinfo is None
                or not utc_midnight <= activity.timestamp.timestamp() <= now + 5
            ):
                raise OrderError("account_check_unavailable")
            if activity.type != "DEPOSIT" or _decimal(activity.amount) <= 0:
                raise OrderError("account_nonempty")
        # A fill may already be visible to this session before Data API indexing.
        for _ in _complete_items(client.list_account_trades(after=str(utc_midnight))):
            raise OrderError("account_nonempty")
    except OrderError:
        raise
    except Exception:
        raise OrderError("account_check_unavailable") from None


def _settled_fills(client, order, matched: Decimal) -> bool:
    try:
        seen = set()
        confirmed = Decimal(0)
        for trade in _complete_items(
            client.list_account_trades(market=str(order.condition_id))
        ):
            makers = [
                maker
                for maker in trade.maker_orders
                if str(maker.order_id).lower() == str(order.id).lower()
            ]
            if not makers:
                continue
            if (
                len(makers) != 1
                or not trade.id
                or trade.id in seen
                or str(trade.condition_id).lower() != str(order.condition_id).lower()
                or trade.status != "CONFIRMED"
            ):
                return False
            seen.add(trade.id)
            maker = makers[0]
            amount = _decimal(maker.matched_amount)
            if (
                str(maker.asset_id) != str(order.asset_id)
                or str(maker.maker_address).lower() != str(client.wallet).lower()
                or maker.side != "BUY"
                or _decimal(maker.price) != _decimal(order.price)
                or amount <= 0
            ):
                return False
            confirmed += amount
        return confirmed == matched
    except Exception:
        return False


def _order_snapshot(client, request: dict) -> dict:
    try:
        order = client.get_order(order_id=request["order_id"])
        price, size = _order_terms(request["price"], request["size"])
        matched = _decimal(order.size_matched)
        if (
            str(order.id).lower() != request["order_id"]
            or str(order.asset_id) != request["token"]
            or str(order.condition_id).lower() != request["condition_id"]
            or str(order.maker_address).lower() != str(client.wallet).lower()
            or order.side != "BUY"
            or order.order_type != "GTD"
            or order.expires_at is None
            or _decimal(order.price) != price
            or _decimal(order.original_size) != size
            or not 0 <= matched <= size
        ):
            raise ValueError("order identity mismatch")
        status = order.status.lower()
        if status in {"live", "open"} and matched < size:
            status, terminal = "open", False
        elif (
            status in {"cancelled", "canceled", "canceled_market_resolved"}
            and matched < size
        ):
            status, terminal = "cancelled", True
        elif status in {"matched", "filled"} and matched == size:
            status, terminal = "filled", True
        elif status == "rejected" and matched == 0:
            status, terminal = "rejected", True
        else:
            raise ValueError("ambiguous status")
        final = terminal and (matched == 0 or _settled_fills(client, order, matched))
        return {
            "order_id": request["order_id"],
            "token": request["token"],
            "condition_id": request["condition_id"],
            "price": str(price),
            "size": str(size),
            "filled": str(matched),
            "status": status,
            "terminal": terminal,
            "settlement_final": final,
        }
    except Exception:
        raise OrderUncertain() from None


def _read(stream) -> dict:
    line = stream.readline(_IPC_LIMIT + 1)
    if not line or len(line) > _IPC_LIMIT:
        raise ValueError("invalid worker response")
    message = json.loads(line)
    if not isinstance(message, dict):
        raise ValueError("invalid worker response")
    return message


def _write(stream, message: dict) -> None:
    stream.write(json.dumps(message, separators=(",", ":")).encode() + b"\n")
    stream.flush()


def _worker_action(client, gate: _NetworkGate, stream, request: dict):
    operation = request["operation"]
    if operation == "clear":
        _clear_wallet(client)
        return None
    if operation == "get":
        return _order_snapshot(client, request)
    if operation == "cancel":
        gate.mutation = "DELETE"
        response = client.cancel_order(order_id=request["order_id"])
        if list(response.canceled) != [request["order_id"]] or response.not_canceled:
            raise OrderUncertain()
        return None
    if operation != "submit":
        raise OrderError("invalid_order")

    _clear_wallet(client)
    token, condition = request["token"], request["condition_id"]
    price, size = _order_terms(request["price"], request["size"])
    _require_passive(_public_book(token, condition), price, size)
    expiration = int(time.time()) + _GTD_EXPIRATION_S
    signed = client.create_limit_order(
        asset_id=token,
        side="BUY",
        price=price,
        size=size,
        post_only=True,
        expiration=expiration,
    )
    if (
        signed.side != "BUY"
        or signed.post_only is not True
        or signed.order_type != "GTD"
        or signed.expiration != expiration
        or str(signed.token_id) != token
        or signed.signature_type != 3
        or str(signed.maker).lower() != str(client.wallet).lower()
        or signed.taker_amount != size * 1_000_000
        or signed.maker_amount != price * size * 1_000_000
    ):
        raise OrderError("invalid_order")

    _write(stream, {"event": "ready"})
    if _read(stream) != {"event": "send"}:
        raise OrderError("permission_denied")
    gate.mutation = "POST"
    try:
        response = client.post_order(signed)
        if response.ok is True and response.status in {"live", "matched", "delayed"}:
            return _identifier(response.order_id, _HASH)
        if response.ok is False and response.code in _DOCUMENTED_REJECTIONS:
            raise OrderError("order_rejected")
    except OrderError as error:
        if error.code == "order_rejected":
            raise
    except Exception:
        pass
    raise OrderUncertain()


def _worker(fd: int) -> None:
    logging.disable(logging.CRITICAL)
    with socket.socket(fileno=fd) as channel, channel.makefile("rwb") as stream:
        try:
            request = _read(stream)
            if version("polymarket-client") != SDK_VERSION:
                raise OrderError("sdk_unavailable")
            gate = _NetworkGate()
            gate.install()
            if request["operation"] == "book":
                fields = asdict(_public_book(request["token"], request["condition_id"]))
                result = {
                    key: str(value) if isinstance(value, Decimal) else value
                    for key, value in fields.items()
                }
            else:
                with _secure_client(Path(request["key_file"])) as client:
                    result = _worker_action(client, gate, stream, request)
            _write(stream, {"event": "ok", "result": result})
        except OrderError as error:
            _write(stream, {"event": "error", "code": error.code})
        except Exception:
            _write(stream, {"event": "error", "code": "sdk_unavailable"})


def _invoke(
    path: Path | None, request: dict, before_send: Callable[[], None] | None = None
):
    granted = request["operation"] in {"get", "cancel"}
    callback_failed = False
    try:
        parent, child = socket.socketpair()
        with parent, child:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-I",
                    str(Path(__file__).resolve()),
                    "--worker",
                    str(child.fileno()),
                ],
                pass_fds=(child.fileno(),),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd="/",
                env={"PATH": os.defpath},
            )
            with process:
                child.close()
                parent.settimeout(_TIMEOUT)
                try:
                    with parent.makefile("rwb") as stream:
                        _write(
                            stream,
                            request
                            if path is None
                            else {**request, "key_file": str(path)},
                        )
                        reply = _read(stream)
                        if reply == {"event": "ready"} and before_send is not None:
                            try:
                                if before_send() is False:
                                    raise OrderError("permission_denied")
                            except BaseException:
                                callback_failed = True
                                raise
                            granted = True
                            _write(stream, {"event": "send"})
                            reply = _read(stream)
                finally:
                    if process.poll() is None:
                        process.kill()
        if reply.get("event") == "ok" and (request["operation"] != "submit" or granted):
            return reply["result"]
        if reply.get("event") == "error":
            code = reply.get("code")
            if code == "order_uncertain" or (granted and code != "order_rejected"):
                raise OrderUncertain()
            raise OrderError(code)
        raise ValueError("invalid worker response")
    except OrderError:
        raise
    except (OSError, ValueError, KeyError, TypeError):
        if callback_failed:
            raise
        if granted:
            raise OrderUncertain() from None
        raise OrderError("sdk_unavailable") from None


class OrderSDK:
    def __init__(self, key_file: Path):
        self._key_file = Path(key_file).absolute()

    verify_book = staticmethod(verify_book)
    geo_allowed = staticmethod(geo_allowed)

    def assert_clear_for_canary(self) -> None:
        _invoke(self._key_file, {"operation": "clear"})

    def submit_post_only(
        self,
        token: str,
        price,
        size,
        *,
        condition_id: str,
        before_send: Callable[[], None],
    ) -> str:
        token, condition_id = _token(token), _identifier(condition_id, _HASH)
        price, size = _order_terms(price, size)
        if not callable(before_send):
            raise OrderError("permission_denied")
        if not self.geo_allowed():
            raise OrderError("geo_blocked")
        _require_passive(self.verify_book(token, condition_id), price, size)
        result = _invoke(
            self._key_file,
            {
                "operation": "submit",
                "token": token,
                "condition_id": condition_id,
                "price": str(price),
                "size": str(size),
            },
            before_send,
        )
        try:
            return _identifier(result, _HASH)
        except OrderError:
            raise OrderUncertain() from None

    def cancel(self, order_id: str) -> None:
        _invoke(
            self._key_file,
            {"operation": "cancel", "order_id": _identifier(order_id, _HASH)},
        )

    def get_order(
        self, order_id: str, *, token: str, condition_id: str, price, size
    ) -> OrderState:
        price, size = _order_terms(price, size)
        request = {
            "operation": "get",
            "order_id": _identifier(order_id, _HASH),
            "token": _token(token),
            "condition_id": _identifier(condition_id, _HASH),
            "price": str(price),
            "size": str(size),
        }
        result = _invoke(self._key_file, request)
        try:
            for name in ("price", "size", "filled"):
                result[name] = _decimal(result[name])
            return OrderState(**result)
        except (KeyError, InvalidOperation, TypeError, ValueError):
            raise OrderUncertain() from None


if __name__ == "__main__" and len(sys.argv) == 3 and sys.argv[1] == "--worker":
    _worker(int(sys.argv[2]))
