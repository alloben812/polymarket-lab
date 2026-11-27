#!/usr/bin/env python3
"""Paper trader for the live_goals protocol (protocol.md). Reads the recorder's files, merges them on the local
receive clock and applies the frozen rules. No orders are sent anywhere: every trade here is hypothetical.

  python3 studies/live_goals/paper.py            replay everything recorded so far, write data/live_goals/paper/
  python3 studies/live_goals/paper.py --follow   same, then keep following the files in real time

Each run starts from scratch and rewrites data/live_goals/paper/*.jsonl (deterministic replay). Outputs:
  triggers.jsonl   one line per trigger at the moment it fires, and a "final" line 600 s after the move
  fills.jsonl      every hypothetical entry (or the reason there was none), with the book snapshot it used;
                   an "exitA" line 300 s later
  goals.jsonl      every score increase seen by any source, linked to a Polymarket match
  resolved.jsonl   market_resolved events (winning token)
  links.jsonl      how each source game was linked to a Polymarket match
"""
from __future__ import annotations

import bisect
import difflib
import glob
import gzip
import heapq
import json
import math
import os
import re
import statistics
import sys
import time
import unicodedata
import zlib
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("LIVE_GOALS_DATA", ROOT / "data" / "live_goals"))
OUT = DATA / "paper"

# ---- frozen parameters (protocol.md) ----
REF_LO, REF_HI, REF_MIN_N = 65, 5, 20
MAX_SPREAD = 0.10
P_MIN, P_MAX = 0.03, 0.95
COOLDOWN = 180
MOVE_STEP, MOVE_BACK = 0.02, 30
CONF_BEFORE, CONF_AFTER = 120, 600
DELAYS = (1, 3)
FRACS = (0.5, 0.8)
NET_LAT = 0.10
NOTIONAL = 10.0
HOLD_EXIT = 300
INPLAY = 2.5 * 3600
STALE_GAP = 120
POST_LO, POST_HI = 120, 300
SOURCES = ("pm_sports", "espn_sb", "espn_sum", "livescore", "s365", "bbc")
STREAMS = ("matches", "ws_market", "pm_sports", "scores", "meta", "clock")


def thr(p_pre: float) -> float:
    return 0.03 + 0.10 * (1 - p_pre)


# ---------------------------------------------------------------- names

SUFFIX = r"\b(fc|cf|afc|sc|ac|ssc|as|ss|sk|fk|rc|rcd|ud|cd|sv|vfb|vfl|tsg|bv|bk|if|club|de|del|of|the|1|cp|sd|ca|cs|calcio|us)\b"


def norm(s: str | None) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(SUFFIX, " ", s)
    return re.sub(r"\s+", " ", s).strip()


def sim(a: str | None, b: str | None) -> float:
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    r = difflib.SequenceMatcher(None, a, b).ratio()
    if a in b or b in a:
        r = max(r, 0.9)
    if {w for w in a.split() if len(w) >= 4} & {w for w in b.split() if len(w) >= 4}:
        r = max(r, 0.75)
    return r


def team_names(t: dict) -> list[str]:
    return [x for x in (t.get("name"), t.get("alias")) if x]


def team_sim(src_name: str, t: dict) -> float:
    return max((sim(src_name, n) for n in team_names(t)), default=0.0)


# ---------------------------------------------------------------- Poisson model (ex-ante post-goal price)

def _pois(lam: float, kmax: int = 12) -> list[float]:
    p = [math.exp(-lam)]
    for k in range(1, kmax + 1):
        p.append(p[-1] * lam / k)
    return p


def win_probs(lh: float, la: float, h: int, a: int) -> tuple[float, float, float]:
    ph, pa = _pois(lh), _pois(la)
    hw = dr = aw = 0.0
    for i, x in enumerate(ph):
        for j, y in enumerate(pa):
            d = (h + i) - (a + j)
            if d > 0:
                hw += x * y
            elif d == 0:
                dr += x * y
            else:
                aw += x * y
    s = hw + dr + aw
    return hw / s, dr / s, aw / s


def fit_lambdas(ph: float, pd: float, pa: float, h: int, a: int):
    tot = ph + pd + pa
    if tot <= 0:
        return None
    ph, pa = ph / tot, pa / tot
    grid = [0.005 * (1.12 ** k) for k in range(60)]  # 0.005 .. ~4.4
    grid = [g for g in grid if g <= 5]
    best = None
    for lh in grid:
        for la in grid:
            w = win_probs(lh, la, h, a)
            e = (w[0] - ph) ** 2 + (w[2] - pa) ** 2
            if best is None or e < best[0]:
                best = (e, lh, la)
    e, lh, la = best
    step = 0.06
    for _ in range(40):  # coordinate refinement
        improved = False
        for dl in ((step, 0), (-step, 0), (0, step), (0, -step)):
            nh, na = min(5, max(0.005, lh * (1 + dl[0]))), min(5, max(0.005, la * (1 + dl[1])))
            w = win_probs(nh, na, h, a)
            ne = (w[0] - ph) ** 2 + (w[2] - pa) ** 2
            if ne < e:
                e, lh, la, improved = ne, nh, na, True
        if not improved:
            step /= 2
            if step < 1e-3:
                break
    return lh, la, e


def post_goal_price(pre: dict, h: int, a: int, role: str):
    """pre = {'home': mid, 'draw': mid, 'away': mid}; returns (P_post_hat, lh, la, fit_err) or None."""
    if any(pre.get(k) is None for k in ("home", "draw", "away")):
        return None
    f = fit_lambdas(pre["home"], pre["draw"], pre["away"], h, a)
    if f is None:
        return None
    lh, la, err = f
    nh, na = (h + 1, a) if role == "home" else (h, a + 1)
    w = win_probs(lh, la, nh, na)
    return (w[0] if role == "home" else w[2]), lh, la, err


# ---------------------------------------------------------------- file readers

FNAME = re.compile(r"^(?P<stream>[a-z_0-9]+?)-(?P<hh>[0-2][0-9])(?:\.(?P<var>g\d+|0))?\.jsonl(?P<gz>\.gz)?$")


def _hour_files(stream: str) -> list[tuple[tuple, str]]:
    """[(key, path)] in time order. key = (date, hour, variant); a plain hourly file and its later gzip copy share
    variant 0; on-the-fly gzip streams are variant g<process start epoch> (one per process and hour)."""
    best: dict[tuple, str] = {}
    for f in glob.glob(str(DATA / "20*" / f"{stream}-*.jsonl*")):
        m = FNAME.match(os.path.basename(f))
        if not m or m.group("stream") != stream:
            continue
        var = m.group("var")
        vkey = int(var[1:]) if var and var.startswith("g") else 0
        key = (os.path.basename(os.path.dirname(f)), m.group("hh"), vkey)
        if key not in best or f.endswith(".jsonl"):  # prefer the plain file while it exists
            best[key] = f
    return [(k, best[k]) for k in sorted(best)]


class Reader:
    """Incremental reader of one stream's hourly files: plain text, finished gzip, or gzip still being written."""

    def __init__(self, stream: str):
        self.stream = stream
        self.done: set[tuple] = set()
        self.cur = None
        self.fh = None
        self.z = None
        self.partial = b""
        self.last_r = 0
        self.eof = False

    def _open(self, key, path):
        if self.fh:
            self.fh.close()
        self.cur = key
        self.fh = open(path, "rb")
        self.z = zlib.decompressobj(31) if path.endswith(".gz") else None
        self.partial = b""

    def _chunk(self) -> bytes | None:
        raw = self.fh.read(1 << 20)
        if not raw:
            return None
        if self.z is None:
            return raw
        out = b""
        while raw:
            out += self.z.decompress(raw)
            if self.z.eof:  # next gzip member
                raw = self.z.unused_data
                self.z = zlib.decompressobj(31)
            else:
                raw = b""
        return out

    def read_new(self, max_lines: int = 200000) -> list[dict]:
        out = []
        files = _hour_files(self.stream)
        for i, (key, path) in enumerate(files):
            if key in self.done:
                continue
            if self.cur != key:
                self._open(key, path)
            while len(out) < max_lines:
                data = self._chunk()
                if data is None:
                    break
                lines = (self.partial + data).split(b"\n")
                self.partial = lines.pop()
                for line in lines:
                    if not line:
                        continue
                    try:
                        o = json.loads(line)
                    except ValueError:
                        continue
                    out.append(o)
                    self.last_r = max(self.last_r, o.get("r") or 0)
            if len(out) >= max_lines:
                self.eof = False
                return out
            if i < len(files) - 1:  # a later file exists: this one is complete
                self.done.add(key)
                self.fh.close()
                self.fh, self.cur = None, None
            else:
                break
        self.eof = True
        return out


# ---------------------------------------------------------------- book

class Book:
    __slots__ = ("bids", "asks", "last_r", "last_ts", "valid", "shard", "eb", "ea")

    def __init__(self):
        self.bids: dict[float, float] = {}
        self.asks: dict[float, float] = {}
        self.last_r = 0
        self.last_ts = 0
        self.valid = False
        self.shard = None
        self.eb = None  # exchange's own best bid / ask from the last price_change (None after a book snapshot)
        self.ea = None

    def best(self):
        bb = max(self.bids) if self.bids else None
        ba = min(self.asks) if self.asks else None
        return bb, ba

    def mid(self):
        bb, ba = self.best()
        if bb is None or ba is None or ba - bb > MAX_SPREAD + 1e-9 or ba < bb:
            return None
        return (bb + ba) / 2

    def asks_sorted(self, n: int = 40):
        """Asks ascending; levels below the exchange's own best ask are dropped (transient rebuild lag)."""
        return [(p, s) for p, s in sorted(self.asks.items()) if self.ea is None or p >= self.ea - 1e-9][:n]

    def bids_sorted(self, n: int = 40):
        return [(p, s) for p, s in sorted(self.bids.items(), reverse=True) if self.eb is None or p <= self.eb + 1e-9][:n]


def fee(rate: float, p: float) -> float:
    return rate * p * (1 - p)


def buy_walk(asks, cap: float, notional: float, rate: float):
    shares = cost = fees = 0.0
    for p, s in asks:
        if p > cap + 1e-9:
            break
        room = notional - cost
        if room <= 1e-9:
            break
        take = min(s, room / p)
        shares += take
        cost += take * p
        fees += take * fee(rate, p)
    return shares, cost, fees


def sell_walk(bids, shares: float, rate: float):
    left, cash, fees = shares, 0.0, 0.0
    for p, s in bids:
        if left <= 1e-9:
            break
        take = min(s, left)
        left -= take
        cash += take * p
        fees += take * fee(rate, p)
    return shares - left, cash, fees, left


# ---------------------------------------------------------------- engine

class Engine:
    def __init__(self, follow: bool):
        self.follow = follow
        OUT.mkdir(parents=True, exist_ok=True)
        self.outs = {k: open(OUT / f"{k}.jsonl", "w") for k in ("triggers", "fills", "goals", "resolved", "links")}
        self.matches: dict[str, dict] = {}
        self.tok: dict[str, tuple[str, dict]] = {}       # token -> (match slug, market rec) for moneyline Yes
        self.books: dict[str, Book] = {}
        self.samples: dict[str, deque] = defaultdict(lambda: deque(maxlen=200))  # (sec, mid)
        self.last_sec: dict[str, int] = {}
        self.hist: dict[str, deque] = defaultdict(lambda: deque(maxlen=4000))    # (r, ts, mid)
        self.last_trig: dict[str, int] = {}
        self.mid_track: dict[str, list] = defaultdict(list)  # token -> [(sec, mid)] for P_post_real (30 min)
        self.offsets: deque = deque(maxlen=48)
        self.src_state: dict[tuple, tuple] = {}
        self.src_link: dict[tuple, tuple | None] = {}
        self.goals: dict[str, list] = defaultdict(list)       # match -> [goal events]
        self.open_trigs: dict[int, dict] = {}
        self.pending: list = []                               # heap of (t_x_ms_exchange, seq, action)
        self.pend_tok: dict[str, list] = defaultdict(list)
        self.seq = 0
        self.ntrig = 0
        self.now_r = 0
        self.shard_tokens: dict[int, set] = defaultdict(set)
        self.resolved: dict[str, str] = {}
        self.gid2match: dict[str, str] = {}
        self.bookcheck = {"n": 0, "mismatch": 0, "examples": []}

    # ---------- helpers
    def emit(self, kind: str, obj: dict) -> None:
        self.outs[kind].write(json.dumps(obj, separators=(",", ":")) + "\n")

    def offset_ms(self) -> float:
        return statistics.median(self.offsets) if self.offsets else 0.0

    def to_exch(self, r: float) -> float:
        return r - self.offset_ms()

    # ---------- matches
    def on_matches(self, o: dict) -> None:
        for slug, m in (o.get("matches") or {}).items():
            self.matches[slug] = m
            if m.get("gameId") is not None:
                self.gid2match[str(m["gameId"])] = slug
            for mk in m.get("markets") or []:
                if mk.get("role") in ("home", "away", "draw") and mk.get("tokens"):
                    outs = mk.get("outcomes") or []
                    yi = outs.index("Yes") if "Yes" in outs else 0
                    self.tok[str(mk["tokens"][yi])] = (slug, mk)

    def market_tokens(self, slug: str) -> dict:
        out = {}
        for mk in self.matches[slug].get("markets") or []:
            if mk.get("role") in ("home", "away", "draw") and mk.get("tokens"):
                outs = mk.get("outcomes") or []
                yi = outs.index("Yes") if "Yes" in outs else 0
                out[mk["role"]] = str(mk["tokens"][yi])
        return out

    # ---------- books
    def sample(self, tok: str, ts: int, before_mid) -> None:
        sec = ts // 1000
        ls = self.last_sec.get(tok)
        dq = self.samples[tok]
        if ls is None:
            self.last_sec[tok] = sec
            return
        if sec > ls:
            # seconds ls .. sec-1 end with the state before this update
            if before_mid is not None:
                tr = self.mid_track[tok]
                for s in range(max(ls, sec - 90), sec):
                    dq.append((s, before_mid))
                    tr.append((s, before_mid))
                if len(tr) > 6000:
                    del tr[:3000]
            self.last_sec[tok] = sec

    def p_ref(self, tok: str, ts: int):
        sec = ts // 1000
        vals = [m for s, m in self.samples[tok] if sec - REF_LO <= s <= sec - REF_HI]
        if len(vals) < REF_MIN_N:
            return None
        return statistics.median(vals)

    def apply_ws(self, o: dict) -> None:
        r = o["r"]
        k = o.get("k")
        d = o.get("d")
        for x in (d if isinstance(d, list) else [d]):
            if not isinstance(x, dict):
                continue
            et = x.get("event_type")
            if et == "book":
                tok = str(x.get("asset_id"))
                if tok not in self.tok:
                    continue
                ts = int(x.get("timestamp") or 0)
                self.fire_token(tok, ts)
                b = self.books.setdefault(tok, Book())
                before = b.mid()
                b.bids = {float(l["price"]): float(l["size"]) for l in x.get("bids") or [] if float(l["size"]) > 0}
                b.asks = {float(l["price"]): float(l["size"]) for l in x.get("asks") or [] if float(l["size"]) > 0}
                b.valid, b.shard = True, k
                b.eb = b.ea = None
                self.shard_tokens[k].add(tok)
                self.after_update(tok, b, r, ts, before)
            elif et == "price_change":
                ts = int(x.get("timestamp") or 0)
                touched = {}
                exp = {}
                for c in x.get("price_changes") or []:
                    tok = str(c.get("asset_id"))
                    if tok not in self.tok:
                        continue
                    if tok not in touched:
                        self.fire_token(tok, ts)
                        b = self.books.setdefault(tok, Book())
                        touched[tok] = (b, b.mid())
                    b = touched[tok][0]
                    p, s = float(c["price"]), float(c["size"])
                    side = b.bids if c.get("side") == "BUY" else b.asks
                    if s > 0:
                        side[p] = s
                    else:
                        side.pop(p, None)
                    if c.get("best_bid") is not None or c.get("best_ask") is not None:
                        exp[tok] = (c.get("best_bid"), c.get("best_ask"))
                        try:
                            eb, ea = float(c.get("best_bid") or 0), float(c.get("best_ask") or 1)
                            b.eb = eb if eb > 0 else None
                            b.ea = ea if ea < 1 else None
                        except ValueError:
                            pass
                for tok, (b, before) in touched.items():
                    if tok in exp and b.valid:
                        self.check_book(b, exp[tok])
                    self.after_update(tok, b, r, ts, before)
            elif et == "market_resolved":
                w = str(x.get("winning_asset_id"))
                for a in x.get("assets_ids") or x.get("asset_ids") or []:
                    self.resolved[str(a)] = w
                self.emit("resolved", {"r": r, "market": x.get("market"), "winner": w,
                                       "assets": x.get("assets_ids") or x.get("asset_ids")})

    def check_book(self, b: Book, e) -> None:
        """Compare the rebuilt top of book with best_bid / best_ask that the exchange sends in price_change."""
        bb, ba = b.best()
        try:
            eb = float(e[0]) if e[0] not in (None, "") else None
            ea = float(e[1]) if e[1] not in (None, "") else None
        except ValueError:
            return
        if eb == 0:
            eb = None
        if ea is not None and ea >= 1:
            ea = None if ba is None else ea
        ok = (eb is None and bb is None or (eb is not None and bb is not None and abs(eb - bb) < 1e-9)) and \
             (ea is None and ba is None or (ea is not None and ba is not None and abs(ea - ba) < 1e-9))
        self.bookcheck["n"] += 1
        if not ok:
            self.bookcheck["mismatch"] += 1
            if len(self.bookcheck["examples"]) < 10:
                self.bookcheck["examples"].append({"ours": [bb, ba], "exchange": [e[0], e[1]]})

    def after_update(self, tok: str, b: Book, r: int, ts: int, before_mid) -> None:
        b.last_r, b.last_ts = r, ts
        self.sample(tok, ts, before_mid)
        m = b.mid()
        h = self.hist[tok]
        h.append((r, ts, m))
        slug, mk = self.tok[tok]
        if mk.get("role") not in ("home", "away") or m is None:
            return
        match = self.matches.get(slug) or {}
        t0 = match.get("t0")
        if not t0 or not (t0 <= ts / 1000 <= t0 + INPLAY):
            return
        if ts - self.last_trig.get(tok, -10 ** 15) < COOLDOWN * 1000:
            return
        pre = self.p_ref(tok, ts)
        if pre is None or not (P_MIN <= pre <= P_MAX):
            return
        if m - pre < thr(pre):
            return
        self.last_trig[tok] = ts
        # first move: after the last update (within 30 s) whose mid was below pre + 0.02
        move = None
        lst = list(h)
        for i in range(len(lst) - 1, -1, -1):
            rr, tt, mm = lst[i]
            if tt < ts - MOVE_BACK * 1000:
                move = lst[i + 1] if i + 1 < len(lst) else lst[i]
                break
            if mm is not None and mm < pre + MOVE_STEP:
                move = lst[i + 1] if i + 1 < len(lst) else lst[i]
                break
        if move is None:
            move = lst[0]
        toks = self.market_tokens(slug)
        pre3 = {role: (self.p_ref(t, ts) if t in self.books else None) for role, t in toks.items()}
        self.ntrig += 1
        tid = self.ntrig
        trig = {"id": tid, "match": slug, "league": match.get("league"), "role": mk["role"], "token": tok,
                "r_trig": r, "ts_trig": ts, "r_move": move[0], "ts_move": move[1], "p_pre": round(pre, 4),
                "mid_trig": round(m, 4), "thr": round(thr(pre), 4), "pre3": pre3,
                "delay": mk.get("delay") if mk.get("delay") is not None else 1,
                "rate": ((mk.get("fee") or {}).get("rate") if (mk.get("fee") or {}).get("rate") is not None else 0.05),
                "minSize": float(mk.get("minSize") or 5), "tick": float(mk.get("tick") or 0.01),
                "conf": {}, "t_conf": None, "first_src": None, "decided": False}
        self.open_trigs[tid] = trig
        self.emit("triggers", {k: v for k, v in trig.items() if k not in ("conf",)} | {"kind": "trigger"})
        # sources that already showed the goal (window starts 120 s before the move)
        for g in self.goals.get(slug, []):
            if g["role"] == mk["role"] and move[0] - CONF_BEFORE * 1000 <= g["r"] <= move[0] + CONF_AFTER * 1000:
                self.confirm(trig, g)
        self.schedule(trig["r_move"] + CONF_AFTER * 1000 + 1, ("final", tid), local=True)
        self.schedule(trig["ts_move"] + POST_HI * 1000 + 1000, ("post", tid), local=False)

    # ---------- scheduling: actions keyed on exchange ms (local=True converts)
    def schedule(self, t: float, action: tuple, local: bool, token: str | None = None) -> None:
        tx = self.to_exch(t) if local else t
        self.seq += 1
        heapq.heappush(self.pending, (tx, self.seq, action))
        if token:
            self.pend_tok[token].append((tx, self.seq))

    def fire_token(self, tok: str, ts: int) -> None:
        """Before applying a message with exchange ts to tok, run its actions due at or before ts (book = state at tx)."""
        if not self.pend_tok.get(tok):
            return
        due = [p for p in self.pend_tok[tok] if p[0] < ts]
        if not due:
            return
        self.run_due(max(p[0] for p in due), only_tok=tok)

    def run_due(self, t_exch: float, only_tok: str | None = None) -> None:
        keep = []
        while self.pending and self.pending[0][0] <= t_exch:
            item = heapq.heappop(self.pending)
            act = item[2]
            if only_tok is not None and (len(act) < 3 or act[2] != only_tok):
                keep.append(item)
                continue
            tok = act[2] if len(act) >= 3 else None
            if tok and (item[0], item[1]) in self.pend_tok.get(tok, []):
                self.pend_tok[tok].remove((item[0], item[1]))
            self.do(act, item[0])
        for it in keep:
            heapq.heappush(self.pending, it)

    def tick(self, r: int) -> None:
        # a token's book is only certain up to exch_now - 1 s (in-order delivery, ~60 ms latency)
        self.run_due(self.to_exch(r) - 1000)

    # ---------- sources
    def link(self, src: str, gid: str, rec: dict, r: int):
        key = (src, gid)
        cached = self.src_link.get(key)
        if cached is not None:
            if cached[0] != "none":
                return cached
            if r - cached[1] < 600 * 1000:  # retry a failed link every 10 minutes
                return None
        if src == "pm_sports" and gid in self.gid2match:
            slug = self.gid2match[gid]
            res = (slug, False)
            self.src_link[key] = res
            self.emit("links", {"r": r, "src": src, "id": gid, "match": slug, "how": "gameId", "swap": False})
            return res
        hn, an = rec.get("home"), rec.get("away")
        if not hn or not an:
            return None
        best = None
        t = r / 1000
        for slug, m in self.matches.items():
            t0 = m.get("t0")
            if not t0 or not (t0 - 1200 <= t <= t0 + 3 * 3600):
                continue
            s_hh, s_aa = team_sim(hn, m["home"]), team_sim(an, m["away"])
            s_ha, s_ah = team_sim(hn, m["away"]), team_sim(an, m["home"])
            if min(s_hh, s_aa) >= 0.6 and (best is None or s_hh + s_aa > best[0]):
                best = (s_hh + s_aa, slug, False)
            if min(s_ha, s_ah) >= 0.6 and (best is None or s_ha + s_ah > best[0]):
                best = (s_ha + s_ah, slug, True)
        if best is None:
            self.src_link[key] = ("none", r)
            return None
        res = (best[1], best[2])
        self.src_link[key] = res
        self.emit("links", {"r": r, "src": src, "id": gid, "match": best[1], "how": "names", "swap": best[2],
                            "score": round(best[0], 2), "src_home": hn, "src_away": an,
                            "pm": self.matches[best[1]].get("title")})
        return res

    def on_score(self, src: str, gid: str, rec: dict, r: int) -> None:
        hs, as_ = rec.get("hs"), rec.get("as")
        if hs is None or as_ is None:
            return
        ln = self.link(src, gid, rec, r)
        key = (src, gid)
        prev = self.src_state.get(key)
        self.src_state[key] = (hs, as_)
        if ln is None or prev is None:
            return
        slug, swap = ln
        ph, pa = prev
        for side, new, old in (("h", hs, ph), ("a", as_, pa)):
            if new > old:
                role = ("home" if side == "h" else "away")
                if swap:
                    role = "away" if role == "home" else "home"
                sh, sa = (hs, as_) if not swap else (as_, hs)
                g = {"r": r, "src": src, "id": gid, "match": slug, "role": role, "score": [sh, sa], "n": new - old}
                self.goals[slug].append(g)
                self.emit("goals", g)
                for trig in list(self.open_trigs.values()):
                    if trig["match"] == slug and trig["role"] == role and \
                            trig["r_move"] - CONF_BEFORE * 1000 <= r <= trig["r_move"] + CONF_AFTER * 1000:
                        self.confirm(trig, g)

    def confirm(self, trig: dict, g: dict) -> None:
        if g["src"] in trig["conf"]:
            return
        trig["conf"][g["src"]] = {"lag_s": round((g["r"] - trig["r_move"]) / 1000, 3), "r": g["r"], "score": g["score"]}
        if trig["t_conf"] is None or g["r"] < trig["t_conf"]:
            first = trig["t_conf"] is None
            trig["t_conf"], trig["first_src"] = g["r"], g["src"]
            if first and not trig["decided"]:
                trig["decided"] = True
                sh, sa = g["score"]
                hb, ab = (sh - 1, sa) if trig["role"] == "home" else (sh, sa - 1)
                trig["score_before"] = [hb, ab]
                t_dec = max(trig["r_trig"], g["r"])
                trig["t_dec"] = t_dec
                for d in DELAYS:
                    t_x_local = t_dec + d * 1000 + NET_LAT * 1000
                    tx = self.to_exch(t_x_local) + trig["delay"] * 1000
                    self.seq += 1
                    heapq.heappush(self.pending, (tx, self.seq, ("entry", trig["id"], trig["token"], d)))
                    self.pend_tok[trig["token"]].append((tx, self.seq))

    # ---------- actions
    def do(self, act: tuple, tx: float) -> None:
        kind = act[0]
        if kind == "entry":
            self.entry(act[1], act[3], tx)
        elif kind == "exitA":
            self.exit_a(act[1], act[3], tx)
        elif kind == "final":
            self.final(act[1])
        elif kind == "post":
            self.post(act[1])

    def book_ok(self, tok: str, tx: float) -> tuple[bool, str]:
        b = self.books.get(tok)
        if b is None or not b.valid:
            return False, "ws_gap"
        if b.last_ts < tx - STALE_GAP * 1000:
            return False, "no_book_msg_120s"
        return True, ""

    def entry(self, tid: int, d: int, tx: float) -> None:
        trig = self.open_trigs.get(tid)
        if trig is None:
            return
        tok = trig["token"]
        b = self.books.get(tok)
        ok, why = self.book_ok(tok, tx)
        hb, ab = trig["score_before"]
        model = post_goal_price(trig["pre3"], hb, ab, trig["role"])
        snap_asks = [(p, round(s, 2)) for p, s in (b.asks_sorted(25) if b else [])]
        snap_bids = [(p, round(s, 2)) for p, s in (b.bids_sorted(5) if b else [])]
        base = {"kind": "entry", "id": tid, "match": trig["match"], "role": trig["role"], "token": tok, "d": d,
                "t_dec": trig["t_dec"], "t_x_exch": round(tx), "first_src": trig["first_src"],
                "lag_first_s": round((trig["t_conf"] - trig["r_move"]) / 1000, 3), "p_pre": trig["p_pre"],
                "score_before": trig["score_before"], "asks": snap_asks, "bids": snap_bids,
                "mid_at_x": b.mid() if b else None}
        if model is None or model[0] <= trig["p_pre"]:
            for f in FRACS:
                self.emit("fills", base | {"f": f, "status": "no_model", "model": model})
            return
        p_post_hat = model[0]
        for f in FRACS:
            cap = trig["p_pre"] + f * (p_post_hat - trig["p_pre"])
            cap = math.floor(cap / trig["tick"] + 1e-9) * trig["tick"]
            rec = base | {"f": f, "p_post_hat": round(p_post_hat, 4), "lam": [round(model[1], 3), round(model[2], 3)],
                          "cap": round(cap, 4)}
            if not ok:
                self.emit("fills", rec | {"status": why})
                continue
            shares, cost, fees = buy_walk(b.asks_sorted(60), cap, NOTIONAL, trig["rate"])
            if shares < trig["minSize"] - 1e-9:
                self.emit("fills", rec | {"status": "no_fill", "shares": round(shares, 4)})
                continue
            rec |= {"status": "filled", "shares": round(shares, 4), "cost": round(cost, 4), "fee_in": round(fees, 5),
                    "avg_px": round(cost / shares, 5)}
            self.emit("fills", rec)
            texit = tx + HOLD_EXIT * 1000 + trig["delay"] * 1000
            self.seq += 1
            heapq.heappush(self.pending, (texit, self.seq, ("exitA", (tid, d, f, shares, cost, fees), tok, d)))
            self.pend_tok[tok].append((texit, self.seq))

    def exit_a(self, info: tuple, d: int, tx: float) -> None:
        tid, d, f, shares, cost, fees = info
        trig = self.open_trigs.get(tid) or {}
        tok = trig.get("token")
        b = self.books.get(tok)
        ok, why = self.book_ok(tok, tx)
        if b is None:
            self.emit("fills", {"kind": "exitA", "id": tid, "d": d, "f": f, "status": "no_book"})
            return
        sold, cash, fee_out, left = sell_walk(b.bids_sorted(60), shares, trig.get("rate", 0.05))
        net = cash - fee_out - cost - fees
        self.emit("fills", {"kind": "exitA", "id": tid, "match": trig.get("match"), "d": d, "f": f,
                            "t_x_exch": round(tx), "book_ok": ok, "why": why, "sold": round(sold, 4),
                            "unsold": round(left, 4), "cash": round(cash, 4), "fee_out": round(fee_out, 5),
                            "net": round(net, 4), "bids": [(p, round(s, 2)) for p, s in b.bids_sorted(5)]})

    def post(self, tid: int) -> None:
        trig = self.open_trigs.get(tid)
        if trig is None:
            return
        tr = self.mid_track[trig["token"]]
        lo, hi = trig["ts_move"] // 1000 + POST_LO, trig["ts_move"] // 1000 + POST_HI
        vals = [m for s, m in tr if lo <= s <= hi]
        trig["p_post_real"] = statistics.median(vals) if vals else None

    def final(self, tid: int) -> None:
        trig = self.open_trigs.get(tid)
        if trig is None:
            return
        out = {"kind": "final", "id": tid, "match": trig["match"], "role": trig["role"], "token": trig["token"],
               "confirmed": trig["t_conf"] is not None, "conf": trig["conf"], "first_src": trig["first_src"],
               "t_conf": trig["t_conf"], "r_move": trig["r_move"], "p_pre": trig["p_pre"],
               "mid_trig": trig["mid_trig"], "p_post_real": trig.get("p_post_real"),
               "score_before": trig.get("score_before")}
        self.emit("triggers", out)
        # keep it for late exits; drop after an hour
        trig["final_r"] = self.now_r

    # ---------- main loop
    def handle(self, stream: str, o: dict) -> None:
        r = o.get("r") or 0
        self.now_r = max(self.now_r, r)
        if stream == "matches":
            self.on_matches(o)
        elif stream == "clock":
            if o.get("binance_off_ms") is not None:
                self.offsets.append(o["binance_off_ms"])
        elif stream == "meta":
            if o.get("kind") == "ws_down":
                for tok in self.shard_tokens.get(o.get("shard"), ()):
                    if tok in self.books:
                        self.books[tok].valid = False
        elif stream == "ws_market":
            self.tick(r)
            self.apply_ws(o)
        elif stream == "pm_sports":
            d = o.get("d") or {}
            sc = d.get("score")
            if isinstance(sc, str) and "-" in sc and d.get("gameId") is not None:
                try:
                    hs, as_ = (int(x) for x in sc.split("-")[:2])
                except ValueError:
                    return
                self.on_score("pm_sports", str(d["gameId"]),
                              {"home": d.get("homeTeam"), "away": d.get("awayTeam"), "hs": hs, "as": as_}, r)
        elif stream == "scores":
            src = o.get("src")
            if src in SOURCES:
                self.on_score(src, str(o.get("id")), o, r)
        self.tick(r)

    def run(self) -> None:
        readers = {s: Reader(s) for s in STREAMS}
        buf: list = []
        seq = 0
        last_flush = time.time()
        while True:
            got = 0
            for s, rd in readers.items():
                for o in rd.read_new():
                    seq += 1
                    heapq.heappush(buf, (o.get("r") or 0, 0 if s in ("matches", "clock") else 1, seq, s, o))
                    got += 1
            live = [rd.last_r for rd in readers.values() if not rd.eof]
            if live:
                wm = min(live)
            else:
                wm = (time.time() * 1000 - 4000) if self.follow else float("inf")
            while buf and buf[0][0] <= wm:
                _, _, _, s, o = heapq.heappop(buf)
                self.handle(s, o)
            if time.time() - last_flush > 5 or not self.follow:
                for f in self.outs.values():
                    f.flush()
                (OUT / "state.json").write_text(json.dumps({"now_r": self.now_r, "triggers": self.ntrig,
                                                            "open": len(self.open_trigs),
                                                            "pending": len(self.pending),
                                                            "bookcheck": self.bookcheck}))
                last_flush = time.time()
                # forget triggers whose exits are long done
                for tid in [t for t, v in self.open_trigs.items() if v.get("final_r") and
                            self.now_r - v["final_r"] > 3600 * 1000]:
                    del self.open_trigs[tid]
            if not self.follow:
                if got == 0 and not buf:
                    break
                continue
            if got == 0:
                time.sleep(1.0)
        for f in self.outs.values():
            f.close()


def main() -> None:
    follow = "--follow" in sys.argv
    Engine(follow).run()


if __name__ == "__main__":
    main()
