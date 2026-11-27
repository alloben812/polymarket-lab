#!/usr/bin/env python3
"""Live recorder for the live_goals study: Polymarket soccer books + trades and score sources, one local clock.

Public data only (no orders, no accounts, no keys). Everything is written under data/live_goals/<UTC date>/ as
hourly JSON-lines files; every line carries "r" = local receive time in epoch milliseconds.

Streams
  ws_market-HH.jsonl  Polymarket market WebSocket (book / price_change / last_trade_price / best_bid_ask /
                      tick_size_change / market_resolved), raw message in "d", shard id in "k".
  pm_sports-HH.jsonl  Polymarket sports WebSocket (wss://sports-api.polymarket.com/ws), raw game update in "d".
  scores-HH.jsonl     Score pollers (ESPN scoreboard, ESPN summary, LiveScore, 365Scores, BBC): one line per
                      change of a game's (score, state) as that source shows it.
  polls-HH.jsonl      One line per poll: source, HTTP status, latency, Date / Age / Cache-Control headers.
  meta-HH.jsonl       Connection up/down, subscriptions, discovery refreshes, errors.
  clock.jsonl         Local clock vs Binance serverTime (ms), CLOB /time and HTTP Date headers; NTP if reachable.
  matches.json        Latest discovered Polymarket matches (overwritten each refresh); matches.jsonl appends.

Run: python3 studies/live_goals/recorder.py   (see run.sh for the detached restart loop)
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import random
import re
import shutil
import socket
import struct
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wsclient import WS  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("LIVE_GOALS_DATA", ROOT / "data" / "live_goals"))
UA = "Mozilla/5.0 (X11; Linux x86_64) research-recorder"
GAMMA = "https://gamma-api.polymarket.com"
WS_MARKET = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
WS_SPORTS = "wss://sports-api.polymarket.com/ws"
ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer"

DISCOVERY_EVERY = 600          # s, gamma refresh (task: every 10 minutes)
WINDOW_BEFORE = 20 * 60        # subscribe this long before kickoff
WINDOW_AFTER = 3 * 3600        # ... and keep until this long after kickoff
SHARD_SIZE = 200               # asset ids per market WebSocket connection
POLL_EVERY = 2.0               # s, per score source / per league
SUMMARY_MAX_RATE = 2.0         # ESPN summary requests per second, all matches together
ESPN_LEAGUES = ["eng.1", "eng.2", "eng.3", "eng.4", "esp.1", "esp.2", "ger.1", "ger.2", "ger.3", "ita.1", "ita.2",
                "fra.1", "fra.2", "ned.1", "ned.2", "por.1", "bel.1", "tur.1", "sco.1", "den.1", "aut.1", "sui.1",
                "gre.1", "uefa.champions", "uefa.europa", "uefa.europa.conf", "usa.1", "mex.1", "bra.1", "arg.1",
                "jpn.1", "aus.1", "esp.copa_del_rey", "eng.fa", "eng.league_cup", "ger.dfb_pokal", "ita.coppa_italia",
                "fra.coupe_de_france", "ksa.1", "nor.1", "swe.1", "pol.1", "cze.1", "rou.1", "chn.1", "kor.1"]
MORE_TYPES = {"totals": {1.5, 2.5, 3.5}, "both_teams_to_score": None}
STOP = threading.Event()


def now_ms() -> int:
    return time.time_ns() // 1_000_000


def utc(ts: float | None = None) -> datetime:
    return datetime.fromtimestamp(ts if ts is not None else time.time(), tz=timezone.utc)


def parse_iso(s: str | None) -> float | None:
    if not s:
        return None
    s = s.strip().replace("Z", "+00:00").replace(" ", "T")
    if re.match(r".*[+-]\d\d$", s):
        s += ":00"
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.timestamp()


# ---------------------------------------------------------------- writer

class Writer:
    """Thread-safe hourly-rotated JSON-lines writer. Files: DATA/<YYYY-MM-DD>/<stream>-<HH>.jsonl."""

    def __init__(self):
        self.lock = threading.Lock()
        self.files: dict[str, tuple[str, object]] = {}
        self.counts: dict[str, int] = {}

    def write(self, stream: str, obj: dict, hourly: bool = True) -> None:
        t = obj.get("r") or now_ms()
        d = utc(t / 1000)
        name = f"{d:%Y-%m-%d}/{stream}-{d:%H}.jsonl" if hourly else f"{stream}.jsonl"
        line = json.dumps(obj, separators=(",", ":"), ensure_ascii=False) + "\n"
        with self.lock:
            cur = self.files.get(stream)
            if cur is None or cur[0] != name:
                if cur is not None:
                    cur[1].close()
                p = DATA / name
                p.parent.mkdir(parents=True, exist_ok=True)
                cur = (name, open(p, "a", encoding="utf-8"))
                self.files[stream] = cur
            cur[1].write(line)
            self.counts[stream] = self.counts.get(stream, 0) + 1

    def flush(self) -> None:
        with self.lock:
            for _, f in self.files.values():
                try:
                    f.flush()
                except Exception:  # noqa: BLE001
                    pass


W = Writer()


def meta(kind: str, **kw) -> None:
    W.write("meta", {"r": now_ms(), "kind": kind, **kw})


def log(msg: str) -> None:
    print(f"{utc():%Y-%m-%d %H:%M:%S} {msg}", flush=True)


# ---------------------------------------------------------------- polite HTTP with per-host backoff

class Backoff:
    def __init__(self):
        self.until: dict[str, float] = {}
        self.fails: dict[str, int] = {}
        self.lock = threading.Lock()

    def ok(self, key: str) -> bool:
        return time.time() >= self.until.get(key, 0)

    def success(self, key: str) -> None:
        with self.lock:
            self.fails[key] = 0

    def failure(self, key: str, status: int | None) -> float:
        with self.lock:
            n = self.fails.get(key, 0) + 1
            self.fails[key] = n
            base = 30 if status in (403, 429, 451) else 2
            wait = min(600, base * 2 ** (n - 1)) * (0.8 + 0.4 * random.random())
            self.until[key] = time.time() + wait
            return wait


BO = Backoff()


def http_get(url: str, src: str, timeout: float = 10.0, headers: dict | None = None, log_poll: bool = True):
    """GET JSON. Returns (obj or None, t_recv_ms). Logs one polls line. Applies backoff on errors."""
    h = {"User-Agent": UA, "Accept": "application/json", "Accept-Encoding": "gzip"}
    if headers:
        h.update(headers)
    t0 = now_ms()
    status, hdr, obj, err = None, {}, None, None
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
            status = r.status
            b = r.read()
            hdr = r.headers
            if r.headers.get("Content-Encoding") == "gzip":
                b = gzip.decompress(b)
            obj = json.loads(b)
    except urllib.error.HTTPError as e:
        status, err, hdr = e.code, "HTTP", e.headers or {}
    except Exception as e:  # noqa: BLE001
        err = type(e).__name__
    t1 = now_ms()
    if log_poll:
        W.write("polls", {"r": t1, "src": src, "st": status, "ms": t1 - t0, "err": err,
                          "date": hdr.get("Date") if hdr else None, "age": hdr.get("Age") if hdr else None,
                          "cc": hdr.get("Cache-Control") if hdr else None})
    key = src.split(":")[0]
    if obj is None:
        wait = BO.failure(key, status)
        meta("http_error", src=src, status=status, err=err, backoff_s=round(wait, 1))
    else:
        BO.success(key)
    return obj, t1, (t0, t1, hdr)


# ---------------------------------------------------------------- discovery (gamma)

SKIP_SUFFIX = ("-more-markets", "-halftime-result", "-exact-score", "-first-to-score", "-player-props",
               "-total-corners", "-corners")


def jl(v):
    if isinstance(v, str):
        try:
            return json.loads(v)
        except ValueError:
            return v
    return v


def market_rec(m: dict, role: str) -> dict:
    return {"cid": m.get("conditionId"), "slug": m.get("slug"), "q": m.get("question"), "role": role,
            "type": m.get("sportsMarketType"), "line": m.get("line"), "title": m.get("groupItemTitle"),
            "outcomes": jl(m.get("outcomes")), "tokens": jl(m.get("clobTokenIds")),
            "delay": m.get("secondsDelay"), "fee": m.get("feeSchedule"), "feeType": m.get("feeType"),
            "tick": m.get("orderPriceMinTickSize"), "minSize": m.get("orderMinSize"),
            "negRisk": m.get("negRisk"), "closed": m.get("closed")}


class Discovery:
    def __init__(self):
        self.matches: dict[str, dict] = {}
        self.lock = threading.Lock()
        self.last_hash = None

    def fetch_events(self) -> list[dict]:
        t = time.time()
        lo = utc(t - 4 * 3600).strftime("%Y-%m-%dT%H:%M:%SZ")
        hi = utc(t + 36 * 3600).strftime("%Y-%m-%dT%H:%M:%SZ")
        out = []
        for off in range(0, 5000, 100):
            url = (f"{GAMMA}/events?tag_slug=soccer&closed=false&end_date_min={lo}&end_date_max={hi}"
                   f"&limit=100&offset={off}")
            d, _, _ = http_get(url, "gamma", timeout=30)
            if d is None:
                raise RuntimeError("gamma fetch failed")
            out += d
            if len(d) < 100:
                break
            time.sleep(0.3)
        return out

    def refresh(self) -> None:
        evs = self.fetch_events()
        base = {}
        more = {}
        for e in evs:
            s = e.get("slug", "")
            if s.endswith("-more-markets"):
                more[s[: -len("-more-markets")]] = e
            elif not s.endswith(SKIP_SUFFIX):
                base[s] = e
        matches = {}
        for s, e in base.items():
            mk = e.get("markets") or []
            if not mk or len(mk) > 3:
                continue
            teams = e.get("teams") or []
            home = next((x for x in teams if x.get("ordering") == "home"), None)
            away = next((x for x in teams if x.get("ordering") == "away"), None)
            mlist = []
            for m in mk:
                ms = m.get("slug", "")
                if ms.endswith("-draw"):
                    role = "draw"
                elif home and ms.endswith("-" + (home.get("abbreviation") or "?")):
                    role = "home"
                elif away and ms.endswith("-" + (away.get("abbreviation") or "?")):
                    role = "away"
                else:
                    role = "team?"
                mlist.append(market_rec(m, role))
            me = more.get(s)
            for m in (me.get("markets") or []) if me else []:
                t = m.get("sportsMarketType")
                if t not in MORE_TYPES:
                    continue
                lines = MORE_TYPES[t]
                if lines is not None and m.get("line") not in lines:
                    continue
                mlist.append(market_rec(m, t))
            matches[s] = {"slug": s, "title": e.get("title"), "start": e.get("startTime") or e.get("endDate"),
                          "t0": parse_iso(e.get("startTime") or e.get("endDate")), "gameId": e.get("gameId"),
                          "league": (e.get("sport") or {}).get("sport") or s.split("-")[0],
                          "series": e.get("seriesSlug"),
                          "home": {k: (home or {}).get(k) for k in ("name", "abbreviation", "alias", "providerId")},
                          "away": {k: (away or {}).get(k) for k in ("name", "abbreviation", "alias", "providerId")},
                          "markets": mlist}
        with self.lock:
            # keep matches that dropped out of the gamma window while their live window is still open
            for s, m in self.matches.items():
                if s not in matches and m.get("t0") and time.time() < m["t0"] + WINDOW_AFTER:
                    matches[s] = m
            self.matches = matches
        blob = json.dumps(matches, sort_keys=True)
        h = hashlib.sha1(blob.encode()).hexdigest()
        tmp = DATA / "matches.json.tmp"
        DATA.mkdir(parents=True, exist_ok=True)
        tmp.write_text(blob)
        tmp.replace(DATA / "matches.json")
        if h != self.last_hash:
            W.write("matches", {"r": now_ms(), "n": len(matches), "matches": matches}, hourly=True)
            self.last_hash = h
        meta("discovery", events=len(evs), matches=len(matches),
             tokens=sum(len(m.get("tokens") or []) for x in matches.values() for m in x["markets"]))
        log(f"discovery: {len(evs)} events, {len(matches)} matches")

    def live_tokens(self) -> set[str]:
        t = time.time()
        out = set()
        with self.lock:
            for m in self.matches.values():
                if m.get("t0") and m["t0"] - WINDOW_BEFORE <= t <= m["t0"] + WINDOW_AFTER:
                    for mk in m["markets"]:
                        if mk.get("closed"):
                            continue
                        for tok in mk.get("tokens") or []:
                            out.add(str(tok))
        return out

    def run(self) -> None:
        STOP.wait(DISCOVERY_EVERY)  # main() did the first refresh
        while not STOP.is_set():
            try:
                self.refresh()
                wait = DISCOVERY_EVERY
            except Exception as e:  # noqa: BLE001
                meta("discovery_error", err=repr(e)[:300])
                log(f"discovery error {e!r}")
                wait = 60
            STOP.wait(wait)


# ---------------------------------------------------------------- market WebSocket shards

class Shard(threading.Thread):
    def __init__(self, sid: int, tokens: list[str]):
        super().__init__(daemon=True, name=f"shard{sid}")
        self.sid, self.tokens = sid, tokens
        self.stop = threading.Event()
        self.msgs = 0
        self.last_msg = 0

    def run(self) -> None:
        fails = 0
        while not self.stop.is_set() and not STOP.is_set():
            ws = None
            try:
                ws = WS(WS_MARKET)
                ws.send(json.dumps({"assets_ids": self.tokens, "type": "market", "initial_dump": True,
                                    "custom_feature_enabled": True}))
                meta("ws_up", shard=self.sid, n=len(self.tokens))
                ws.settimeout(1.0)
                next_ping = time.time() + 10
                last_rx = time.time()
                fails = 0
                while not self.stop.is_set() and not STOP.is_set():
                    if time.time() >= next_ping:
                        ws.send("PING")
                        next_ping = time.time() + 10
                    if time.time() - last_rx > 60:
                        raise ConnectionError("no data for 60 s")
                    try:
                        m = ws.recv()
                    except socket.timeout:
                        continue
                    last_rx = time.time()
                    if m is None:
                        continue
                    r = now_ms()
                    if m.strip() in ("PONG", "pong"):
                        continue
                    try:
                        d = json.loads(m)
                    except ValueError:
                        W.write("ws_market", {"r": r, "k": self.sid, "raw": m[:500]})
                        continue
                    self.msgs += 1
                    self.last_msg = r
                    W.write("ws_market", {"r": r, "k": self.sid, "d": d})
            except Exception as e:  # noqa: BLE001
                fails += 1
                wait = min(60, 2 ** min(fails, 6)) * (0.8 + 0.4 * random.random())
                meta("ws_down", shard=self.sid, err=repr(e)[:200], retry_s=round(wait, 1))
                if ws:
                    ws.close()
                self.stop.wait(wait)
                continue
            finally:
                pass
        meta("ws_closed", shard=self.sid)


class ShardManager:
    def __init__(self, disc: Discovery):
        self.disc = disc
        self.shards: dict[int, Shard] = {}
        self.next_id = int(time.time()) % 100000 * 100

    def run(self) -> None:
        while not STOP.is_set():
            try:
                want = self.disc.live_tokens()
                have = set()
                for sid, sh in list(self.shards.items()):
                    if not (set(sh.tokens) & want):
                        sh.stop.set()
                        del self.shards[sid]
                        meta("shard_retire", shard=sid)
                    else:
                        have |= set(sh.tokens)
                new = sorted(want - have)
                for i in range(0, len(new), SHARD_SIZE):
                    self.next_id += 1
                    sh = Shard(self.next_id, new[i:i + SHARD_SIZE])
                    self.shards[self.next_id] = sh
                    sh.start()
                    meta("shard_new", shard=self.next_id, n=len(sh.tokens))
                    log(f"market ws shard {self.next_id}: {len(sh.tokens)} tokens")
            except Exception as e:  # noqa: BLE001
                meta("shard_mgr_error", err=repr(e)[:300])
            STOP.wait(30)


# ---------------------------------------------------------------- Polymarket sports WebSocket

def sports_ws() -> None:
    fails = 0
    while not STOP.is_set():
        ws = None
        try:
            ws = WS(WS_SPORTS)
            ws.settimeout(1.0)
            meta("sports_up")
            last_rx = time.time()
            fails = 0
            while not STOP.is_set():
                if time.time() - last_rx > 60:
                    raise ConnectionError("no data for 60 s")
                try:
                    m = ws.recv()
                except socket.timeout:
                    continue
                last_rx = time.time()
                if m is None:
                    continue
                r = now_ms()
                if m.strip() == "ping":
                    ws.send("pong")
                    continue
                try:
                    d = json.loads(m)
                except ValueError:
                    W.write("pm_sports", {"r": r, "raw": m[:500]})
                    continue
                W.write("pm_sports", {"r": r, "d": d})
        except Exception as e:  # noqa: BLE001
            fails += 1
            wait = min(60, 2 ** min(fails, 6)) * (0.8 + 0.4 * random.random())
            meta("sports_down", err=repr(e)[:200], retry_s=round(wait, 1))
            if ws:
                ws.close()
            STOP.wait(wait)


# ---------------------------------------------------------------- score pollers

class ChangeTracker:
    """Writes a scores line when a (source, game id) key changes its state tuple."""

    def __init__(self):
        self.state: dict[tuple, tuple] = {}
        self.lock = threading.Lock()

    def see(self, src: str, gid, key: tuple, rec: dict, r: int, extra: dict | None = None) -> None:
        k = (src, str(gid))
        with self.lock:
            if self.state.get(k) == key:
                return
            first = k not in self.state
            self.state[k] = key
        out = {"r": r, "src": src, "id": str(gid), "first": first, **rec}
        if extra:
            out.update(extra)
        W.write("scores", out)


CT = ChangeTracker()


def to_int(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return None


class EspnPoller:
    def __init__(self):
        self.sched: dict[str, list[dict]] = {}
        self.live_games: dict[str, tuple[str, float]] = {}  # espn id -> (league, t0)
        self.lock = threading.Lock()

    def schedule_loop(self) -> None:
        while not STOP.is_set():
            days = sorted({utc(time.time() + k * 3600).strftime("%Y%m%d") for k in (-6, 0, 6)})
            sched = {}
            for lg in ESPN_LEAGUES:
                games, seen = [], set()
                for day in days:
                    if STOP.is_set():
                        return
                    # a date range (d0-d1) returns HTTP 400 on this API (2026-11-27): one request per day
                    d, r, _ = http_get(f"{ESPN}/{lg}/scoreboard?dates={day}", f"espn_sched:{lg}", log_poll=False)
                    time.sleep(0.3)
                    if d is None:
                        break
                    for e in d.get("events") or []:
                        if e.get("id") in seen:
                            continue
                        seen.add(e.get("id"))
                        t0 = parse_iso(e.get("date"))
                        st = ((e.get("status") or {}).get("type") or {}).get("state")
                        games.append({"id": e.get("id"), "t0": t0, "state": st, "name": e.get("name")})
                if games:
                    sched[lg] = games
            with self.lock:
                self.sched = sched
            n = sum(1 for g in sched.values() for x in g if self._in_window(x))
            meta("espn_schedule", leagues=len(sched), games=sum(len(g) for g in sched.values()), in_window=n)
            log(f"espn schedule: {len(sched)} leagues, {n} games in window")
            STOP.wait(600)

    @staticmethod
    def _in_window(g: dict) -> bool:
        t = time.time()
        return bool(g.get("t0")) and g["t0"] - 600 <= t <= g["t0"] + WINDOW_AFTER and g.get("state") != "post"

    def live_leagues(self) -> list[str]:
        with self.lock:
            return [lg for lg, gs in self.sched.items() if any(self._in_window(g) for g in gs)]

    def league_loop(self) -> None:
        """Poll each live league's scoreboard every POLL_EVERY seconds (one request covers all its games)."""
        nxt: dict[str, float] = {}
        while not STOP.is_set():
            lgs = self.live_leagues()
            if not lgs:
                STOP.wait(5)
                continue
            for lg in lgs:
                if STOP.is_set():
                    return
                if time.time() < nxt.get(lg, 0) or not BO.ok("espn_sb"):
                    continue
                nxt[lg] = time.time() + POLL_EVERY
                d, r, _ = http_get(f"{ESPN}/{lg}/scoreboard", f"espn_sb:{lg}")
                if d is None:
                    continue
                for e in d.get("events") or []:
                    comp = (e.get("competitions") or [{}])[0]
                    cs = {c.get("homeAway"): c for c in comp.get("competitors") or []}
                    h, a = cs.get("home") or {}, cs.get("away") or {}
                    st = (e.get("status") or {})
                    ty = st.get("type") or {}
                    hs, as_ = to_int(h.get("score")), to_int(a.get("score"))
                    rec = {"lg": lg, "home": (h.get("team") or {}).get("displayName"),
                           "away": (a.get("team") or {}).get("displayName"), "hs": hs, "as": as_,
                           "state": ty.get("state"), "status": ty.get("name"), "clock": st.get("displayClock"),
                           "period": st.get("period"), "t0": e.get("date")}
                    CT.see("espn_sb", e.get("id"), (hs, as_, ty.get("state"), ty.get("name"), st.get("period")), rec, r)
                    if ty.get("state") == "in":
                        with self.lock:
                            self.live_games[str(e.get("id"))] = (lg, time.time())
            time.sleep(0.05)

    def summary_loop(self) -> None:
        """ESPN summary for live games, round robin, at most SUMMARY_MAX_RATE requests per second overall."""
        seen_ke: dict[str, set] = {}
        while not STOP.is_set():
            with self.lock:
                games = [(gid, lg) for gid, (lg, ts) in self.live_games.items() if time.time() - ts < 120]
            if not games:
                STOP.wait(2)
                continue
            for gid, lg in games:
                if STOP.is_set():
                    return
                t_start = time.time()
                if BO.ok("espn_sum"):
                    d, r, _ = http_get(f"{ESPN}/{lg}/summary?event={gid}", f"espn_sum:{lg}")
                    if d is not None:
                        comp = (((d.get("header") or {}).get("competitions")) or [{}])[0]
                        cs = {c.get("homeAway"): c for c in comp.get("competitors") or []}
                        h, a = cs.get("home") or {}, cs.get("away") or {}
                        hs, as_ = to_int(h.get("score")), to_int(a.get("score"))
                        ty = ((comp.get("status") or {}).get("type") or {})
                        kes = d.get("keyEvents") or []
                        new_ke = []
                        s = seen_ke.setdefault(gid, set())
                        for k in kes:
                            kid = k.get("id")
                            if kid in s:
                                continue
                            s.add(kid)
                            new_ke.append({"id": kid, "type": (k.get("type") or {}).get("text"),
                                           "wc": k.get("wallclock"), "clock": (k.get("clock") or {}).get("displayValue"),
                                           "team": (k.get("team") or {}).get("displayName"),
                                           "sp": k.get("scoringPlay"), "txt": (k.get("text") or "")[:160]})
                        rec = {"lg": lg, "home": (h.get("team") or {}).get("displayName"),
                               "away": (a.get("team") or {}).get("displayName"), "hs": hs, "as": as_,
                               "state": ty.get("state"), "status": ty.get("name"), "nke": len(kes)}
                        CT.see("espn_sum", gid, (hs, as_, ty.get("state"), ty.get("name")), rec, r)
                        if new_ke:
                            W.write("scores", {"r": r, "src": "espn_sum_ke", "id": gid, "lg": lg, "ke": new_ke})
                dt = time.time() - t_start
                time.sleep(max(0.0, 1.0 / SUMMARY_MAX_RATE - dt))


def livescore_loop() -> None:
    url = "https://prod-public-api.livescore.com/v1/api/app/live/soccer/0?MD=1"
    while not STOP.is_set():
        t = time.time()
        if BO.ok("livescore"):
            d, r, _ = http_get(url, "livescore")
            if d is not None:
                for stg in d.get("Stages") or []:
                    for e in stg.get("Events") or []:
                        t1 = (e.get("T1") or [{}])[0]
                        t2 = (e.get("T2") or [{}])[0]
                        hs, as_ = to_int(e.get("Tr1")), to_int(e.get("Tr2"))
                        eps = e.get("Eps")
                        stc = "HT" if eps == "HT" else ("FT" if eps in ("FT", "AET", "AP") else
                                                         ("NS" if eps == "NS" else "LIVE"))
                        rec = {"lg": stg.get("Snm"), "cn": stg.get("Cnm"), "home": t1.get("Nm"), "away": t2.get("Nm"),
                               "hs": hs, "as": as_, "state": stc, "clock": eps, "t0": e.get("Esd")}
                        CT.see("livescore", e.get("Eid"), (hs, as_, stc), rec, r, {"ts": d.get("Ts")})
        STOP.wait(max(0.1, POLL_EVERY - (time.time() - t)))


def s365_loop() -> None:
    url = ("https://webws.365scores.com/web/games/current/?appTypeId=5&langId=1&timezoneName=UTC"
           "&userCountryId=-1&sports=1")
    while not STOP.is_set():
        t = time.time()
        if BO.ok("s365"):
            d, r, _ = http_get(url, "s365")
            if d is not None:
                comps = {c.get("id"): c.get("name") for c in d.get("competitions") or []}
                for g in d.get("games") or []:
                    if g.get("statusGroup") not in (3, 4):
                        continue
                    h, a = g.get("homeCompetitor") or {}, g.get("awayCompetitor") or {}
                    hs, as_ = to_int(h.get("score")), to_int(a.get("score"))
                    rec = {"lg": comps.get(g.get("competitionId")) or g.get("competitionDisplayName"),
                           "home": h.get("name"), "away": a.get("name"), "hs": hs, "as": as_,
                           "state": g.get("statusGroup"), "status": g.get("shortStatusText"),
                           "clock": g.get("gameTime"), "t0": g.get("startTime")}
                    CT.see("s365", g.get("id"), (hs, as_, g.get("statusGroup"), g.get("shortStatusText")), rec, r,
                           {"uid": d.get("lastUpdateId")})
        STOP.wait(max(0.1, POLL_EVERY - (time.time() - t)))


def _bbc_walk(o, out):
    if isinstance(o, dict):
        if isinstance(o.get("home"), dict) and isinstance(o.get("away"), dict) and "id" in o:
            out.append(o)
            return
        for v in o.values():
            _bbc_walk(v, out)
    elif isinstance(o, list):
        for v in o:
            _bbc_walk(v, out)


def bbc_loop() -> None:
    while not STOP.is_set():
        t = time.time()
        day = utc().strftime("%Y-%m-%d")
        url = ("https://web-cdn.api.bbci.co.uk/wc-poll-data/container/sport-data-scores-fixtures?"
               f"selectedEndDate={day}&selectedStartDate={day}&todayDate={day}"
               "&urn=urn%3Abbc%3Asportsdata%3Afootball%3Atournament-collection%3Acollated")
        if BO.ok("bbc"):
            d, r, _ = http_get(url, "bbc")
            if d is not None:
                evs = []
                _bbc_walk(d, evs)
                for e in evs:
                    h, a = e["home"], e["away"]
                    hs, as_ = to_int(h.get("score")), to_int(a.get("score"))
                    st = e.get("status") or e.get("eventStatus")
                    per = e.get("periodLabel") or e.get("statusComment")
                    if isinstance(per, dict):
                        per = per.get("value")
                    rec = {"home": h.get("fullName") or h.get("name"), "away": a.get("fullName") or a.get("name"),
                           "hs": hs, "as": as_, "state": st, "clock": per, "t0": e.get("date") or e.get("startDateTime")}
                    CT.see("bbc", e.get("id"), (hs, as_, str(st)), rec, r)
        STOP.wait(max(0.1, POLL_EVERY - (time.time() - t)))


# ---------------------------------------------------------------- clock checks

def ntp_offset(host: str = "pool.ntp.org", timeout: float = 2.0):
    pkt = b"\x1b" + 47 * b"\0"
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        t1 = time.time()
        s.sendto(pkt, (host, 123))
        data, _ = s.recvfrom(256)
        t4 = time.time()
        sec, frac = struct.unpack("!II", data[40:48])
        t3 = sec - 2208988800 + frac / 2 ** 32
        return round(((t1 + t4) / 2 - t3) * 1000, 1), round((t4 - t1) * 1000, 1)
    finally:
        s.close()


def clock_loop() -> None:
    first = True
    while not STOP.is_set():
        rec = {"r": now_ms()}
        best = None
        for _ in range(5):
            t0 = time.time()
            d, _, (_, _, hdr) = http_get("https://data-api.binance.vision/api/v3/time", "binance_time", log_poll=False)
            t1 = time.time()
            if d and "serverTime" in d:
                rtt = (t1 - t0) * 1000
                off = ((t0 + t1) / 2) * 1000 - d["serverTime"]
                if best is None or rtt < best[1]:
                    best = (round(off, 1), round(rtt, 1))
            time.sleep(0.3)
        if best:
            rec["binance_off_ms"], rec["binance_rtt_ms"] = best
        for name, url in (("clob", "https://clob.polymarket.com/time"), ("gamma", f"{GAMMA}/status")):
            try:
                t0 = time.time()
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=10) as r:
                    body = r.read(200)
                    date = r.headers.get("Date")
                t1 = time.time()
                if date:
                    hd = datetime.strptime(date, "%a, %d %b %Y %H:%M:%S GMT").replace(tzinfo=timezone.utc).timestamp()
                    rec[f"{name}_date_off_s"] = round((t0 + t1) / 2 - hd, 2)  # +-0.5 s resolution
                if name == "clob":
                    try:
                        rec["clob_time_off_s"] = round((t0 + t1) / 2 - float(body.strip()), 2)
                    except ValueError:
                        pass
            except Exception as e:  # noqa: BLE001
                rec[f"{name}_err"] = type(e).__name__
        if first:
            try:
                rec["ntp_off_ms"], rec["ntp_rtt_ms"] = ntp_offset()
            except Exception as e:  # noqa: BLE001
                rec["ntp_err"] = type(e).__name__
            first = False
        W.write("clock", rec)
        log(f"clock {rec}")
        STOP.wait(300)


# ---------------------------------------------------------------- housekeeping

def housekeeping(sm: ShardManager) -> None:
    last_status = 0
    while not STOP.is_set():
        W.flush()
        t = time.time()
        if t - last_status > 60:
            last_status = t
            st = {"r": now_ms(), "kind": "status", "counts": dict(W.counts),
                  "shards": {sid: {"n": len(s.tokens), "msgs": s.msgs, "alive": s.is_alive()}
                             for sid, s in sm.shards.items()}}
            W.write("meta", st)
            (DATA / "status.json").write_text(json.dumps({**st, "utc": f"{utc():%Y-%m-%d %H:%M:%S}"}))
        # gzip hourly files that are at least two hours old
        if int(t) % 600 < 2:
            cutoff = utc(t - 2 * 3600).strftime("%Y-%m-%d/%H")
            for p in DATA.glob("20*/*-[0-2][0-9].jsonl"):
                key = p.parent.name + "/" + p.stem[-2:]
                if key < cutoff:
                    with open(p, "rb") as f, gzip.open(str(p) + ".gz.tmp", "wb", 6) as g:
                        shutil.copyfileobj(f, g)
                    os.replace(str(p) + ".gz.tmp", str(p) + ".gz")
                    p.unlink()
        STOP.wait(1.0)


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    log(f"recorder start, data in {DATA}")
    meta("start", pid=os.getpid())
    disc = Discovery()
    try:
        disc.refresh()
    except Exception as e:  # noqa: BLE001
        log(f"first discovery failed: {e!r}")
    sm = ShardManager(disc)
    espn = EspnPoller()
    targets = [disc.run, sm.run, sports_ws, espn.schedule_loop, espn.league_loop, espn.summary_loop,
               livescore_loop, s365_loop, bbc_loop, clock_loop]
    threads = []
    for f in targets:
        th = threading.Thread(target=_guard, args=(f,), daemon=True, name=getattr(f, "__name__", "t"))
        th.start()
        threads.append(th)
    try:
        housekeeping(sm)
    except KeyboardInterrupt:
        STOP.set()
    W.flush()


def _guard(f) -> None:
    """Restart a worker loop if it raises (the process itself is restarted by run.sh if it dies)."""
    while not STOP.is_set():
        try:
            f()
            return
        except Exception:  # noqa: BLE001
            meta("thread_crash", name=getattr(f, "__name__", "?"), tb=traceback.format_exc()[-800:])
            STOP.wait(5)


if __name__ == "__main__":
    import signal
    signal.signal(signal.SIGTERM, lambda *_: STOP.set())
    main()
