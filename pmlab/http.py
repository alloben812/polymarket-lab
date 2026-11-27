"""Polite JSON-over-HTTP helper with retries and an optional on-disk cache (read-only research use)."""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = Path(os.environ.get("PMLAB_CACHE", ROOT / "data" / "cache"))
UA = "Mozilla/5.0 (polymarket-lab research)"

_lock = threading.Lock()
_last_call: dict[str, float] = {}
MIN_INTERVAL = 0.04  # seconds between calls to the same host


class HttpError(RuntimeError):
    def __init__(self, code: int, url: str, body: str):
        super().__init__(f"HTTP {code} for {url}: {body[:300]}")
        self.code, self.url, self.body = code, url, body


def _throttle(host: str) -> None:
    with _lock:
        wait = _last_call.get(host, 0.0) + MIN_INTERVAL - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_call[host] = time.monotonic()


def build_url(url: str, params: dict | list | None = None) -> str:
    if not params:
        return url
    items = params.items() if isinstance(params, dict) else params
    clean = [(k, v) for k, v in items if v is not None]
    return url + ("&" if "?" in url else "?") + urllib.parse.urlencode(clean, doseq=True)


def _cache_path(key: str) -> Path:
    h = hashlib.sha1(key.encode()).hexdigest()
    return CACHE_DIR / h[:2] / f"{h}.json.gz"


def get_json(url: str, params: dict | list | None = None, data=None, *, tries: int = 6, timeout: float = 60.0,
             cache: bool = False, headers: dict | None = None):
    """GET (or POST when `data` is given) and decode JSON.

    cache=True stores the decoded response on disk forever: use it only for immutable resources
    (resolved markets, past trade windows, closed-market metadata).
    """
    full = build_url(url, params)
    key = full + ("|" + json.dumps(data, sort_keys=True) if data is not None else "")
    path = _cache_path(key) if cache else None
    if path is not None and path.exists():
        with gzip.open(path, "rt") as f:
            return json.load(f)
    host = urllib.parse.urlsplit(full).netloc
    last: Exception | None = None
    for attempt in range(tries):
        _throttle(host)
        hdrs = {"User-Agent": UA, "Accept": "application/json"}
        body = None
        if data is not None:
            body = json.dumps(data).encode()
            hdrs["Content-Type"] = "application/json"
        if headers:
            hdrs.update(headers)
        try:
            with urllib.request.urlopen(urllib.request.Request(full, data=body, headers=hdrs), timeout=timeout) as r:
                obj = json.loads(r.read())
            if path is not None:
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp = path.with_suffix(f".tmp{os.getpid()}")
                with gzip.open(tmp, "wt") as f:
                    json.dump(obj, f)
                os.replace(tmp, path)
            return obj
        except urllib.error.HTTPError as e:
            text = e.read().decode(errors="replace")
            if e.code == 429 or e.code >= 500:
                retry_after = e.headers.get("Retry-After") if e.headers else None
                try:
                    delay = float(retry_after) if retry_after else 1.5 * (attempt + 1)
                except ValueError:
                    delay = 1.5 * (attempt + 1)
                last = HttpError(e.code, full, text)
                time.sleep(min(delay, 30.0))
                continue
            raise HttpError(e.code, full, text) from None
        except Exception as e:  # noqa: BLE001 - timeouts, resets, JSON errors: retry
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"request failed after {tries} tries: {full}: {last}")
