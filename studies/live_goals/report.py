#!/usr/bin/env python3
"""Report for the live_goals study. Reads the recorder's files and the paper trader's outputs (data/live_goals/paper/)
and prints coverage, clock checks, source lags, stale dollars and the paper trades per protocol.md.

  python3 studies/live_goals/report.py            print the report (also saved to data/live_goals/report.txt)
  python3 studies/live_goals/report.py --replay   rebuild the paper outputs from the raw files first

Exit B (hold to resolution) uses the WebSocket market_resolved events; for tokens without one it asks gamma
(public, read-only) whether the market has resolved.
"""
from __future__ import annotations

import collections
import glob
import gzip
import io
import json
import os
import re
import statistics
import subprocess
import sys
import time
import urllib.request
import zlib
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
DATA = Path(os.environ.get("LIVE_GOALS_DATA", ROOT / "data" / "live_goals"))
P = DATA / "paper"
SPLIT = datetime(2026, 11, 29, tzinfo=timezone.utc).timestamp()
SOURCES = ("pm_sports", "espn_sb", "espn_sum", "livescore", "s365", "bbc")

try:
    from pmlab.stats import ratio_cluster
except Exception:  # noqa: BLE001
    ratio_cluster = None

buf = io.StringIO()


def out(s: str = "") -> None:
    print(s)
    buf.write(s + "\n")


def jl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with open(path) as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
    return rows


def stream_files(stream: str) -> list[str]:
    fs = [f for f in glob.glob(str(DATA / "20*" / f"{stream}-*.jsonl*"))
          if re.match(rf"^{stream}2?-[0-2][0-9](\.(g\d+|0))?\.jsonl(\.gz)?$", os.path.basename(f))]
    if stream in ("meta", "polls"):  # the scores process writes meta2 / polls2
        fs += [f for f in glob.glob(str(DATA / "20*" / f"{stream}2-*.jsonl*"))
               if re.match(rf"^{stream}2-[0-2][0-9]\.jsonl(\.gz)?$", os.path.basename(f))]
    return sorted(set(fs), key=lambda f: (os.path.dirname(f), os.path.basename(f).replace(".jsonl", "~")))


def _lines(f: str):
    """Lines of a plain or gzip file; a gzip stream still being written is read up to its last flush."""
    with open(f, "rb") as fh:
        z = zlib.decompressobj(31) if f.endswith(".gz") else None
        part = b""
        while True:
            raw = fh.read(1 << 22)
            if not raw:
                break
            data = b""
            if z is None:
                data = raw
            else:
                while raw:
                    try:
                        data += z.decompress(raw)
                    except zlib.error:
                        raw = b""
                        break
                    if z.eof:
                        raw, z = z.unused_data, zlib.decompressobj(31)
                    else:
                        raw = b""
            ls = (part + data).split(b"\n")
            part = ls.pop()
            yield from ls


def iter_stream(stream: str, every: int = 1, last_files: int | None = None):
    fs = stream_files(stream)
    if last_files:
        fs = fs[-last_files:]
    for f in fs:
        for i, line in enumerate(_lines(f)):
            if i % every or not line:
                continue
            try:
                yield json.loads(line)
            except ValueError:
                continue


def q(xs, p):
    xs = sorted(xs)
    if not xs:
        return float("nan")
    k = (len(xs) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def ts(ms) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def cluster_ci(rows: list[dict], key_num: str, key_den: str | None = None):
    """Net per trade (or per share) with a cluster-robust SE by match."""
    by = collections.defaultdict(lambda: [0.0, 0.0])
    for r in rows:
        by[r["match"]][0] += r[key_num]
        by[r["match"]][1] += (r[key_den] if key_den else 1.0)
    nums = [v[0] for v in by.values()]
    dens = [v[1] for v in by.values()]
    if not nums or sum(dens) == 0:
        return None
    if ratio_cluster and len(nums) >= 2:
        est, se, t = ratio_cluster(nums, dens)
    else:
        est, se, t = sum(nums) / sum(dens), float("nan"), float("nan")
    return est, se, t, len(nums)


def gamma_outcomes(cids: list[str]) -> dict[str, dict]:
    res = {}
    for i in range(0, len(cids), 20):
        chunk = cids[i:i + 20]
        url = "https://gamma-api.polymarket.com/markets?closed=true&" + "&".join(f"condition_ids={c}" for c in chunk)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research)", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                for m in json.loads(r.read()):
                    res[m.get("conditionId")] = m
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.3)
    return res


def main() -> None:
    if "--replay" in sys.argv:
        subprocess.run([sys.executable, str(HERE / "paper.py")], check=True)
    out(f"live_goals report  {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC   protocol: studies/live_goals/protocol.md")
    fr = DATA / "protocol_frozen.txt"
    if fr.exists():
        out("freeze record: " + fr.read_text().strip().splitlines()[0][:150])
    out("All trades below are HYPOTHETICAL (paper). No order was sent.")
    out()

    # ---------------------------------------------------------------- coverage and clocks
    meta = list(iter_stream("meta"))
    clock = list(iter_stream("clock"))
    starts = [m for m in meta if m.get("kind") == "start"]
    ws_down = [m for m in meta if m.get("kind") == "ws_down"]
    sp_down = [m for m in meta if m.get("kind") == "sports_down"]
    status = [m for m in meta if m.get("kind") == "status"]
    first_r = min((m["r"] for m in meta), default=None)
    last_r = max((m["r"] for m in meta), default=None)
    out("== Recording")
    if first_r:
        out(f"span {ts(first_r)} .. {ts(last_r)} UTC  ({(last_r - first_r) / 60000:.0f} min)  recorder (re)starts: {len(starts)}")
    if status:
        out(f"lines written in the current process: {status[-1].get('counts')}")
    out(f"market WebSocket disconnects: {len(ws_down)}  sports WebSocket disconnects: {len(sp_down)}")
    du = sum(os.path.getsize(f) for f in glob.glob(str(DATA / "20*" / "*")))
    out(f"disk used by raw data: {du / 1e9:.2f} GB")
    st = json.loads((P / "state.json").read_text()) if (P / "state.json").exists() else {}
    bc = st.get("bookcheck") or {}
    if bc.get("n"):
        out(f"book check (rebuilt top of book vs the exchange's best_bid/best_ask in each price_change): {bc['n']:,} checks,"
            f" {bc['mismatch'] / bc['n']:.2%} transient mismatches (fills use the exchange quote as a floor/ceiling)")
    out()
    out("== Clock (local clock vs references; + means the local clock is ahead)")
    bo = [c["binance_off_ms"] for c in clock if c.get("binance_off_ms") is not None]
    br = [c["binance_rtt_ms"] for c in clock if c.get("binance_rtt_ms") is not None]
    if bo:
        out(f"Binance serverTime offset: n {len(bo)}, median {statistics.median(bo):+.0f} ms, range {min(bo):+.0f}..{max(bo):+.0f} ms;"
            f" round trip median {statistics.median(br):.0f} ms (so each offset is +-{statistics.median(br) / 2:.0f} ms at worst)")
    for k in ("clob_date_off_s", "gamma_date_off_s", "clob_time_off_s"):
        v = [c[k] for c in clock if c.get(k) is not None]
        if v:
            out(f"{k}: median {statistics.median(v):+.2f} s, range {min(v):+.2f}..{max(v):+.2f} (whole-second header: +-0.5 s, mean bias +0.5)")
    ntp = [c for c in clock if "ntp_err" in c or "ntp_off_ms" in c]
    if ntp:
        out(f"NTP (UDP 123): {ntp[0].get('ntp_off_ms', ntp[0].get('ntp_err'))}")
    lat = []
    for o in iter_stream("ws_market", every=97, last_files=2):
        d = o.get("d")
        for x in (d if isinstance(d, list) else [d]):
            if isinstance(x, dict) and x.get("event_type") in ("price_change", "last_trade_price") and x.get("timestamp"):
                lat.append(o["r"] - int(x["timestamp"]))
    if lat:
        out(f"market WebSocket: local receive - exchange timestamp: n {len(lat)} (sample), min {min(lat)} ms, p10 {q(lat, .1):.0f},"
            f" median {q(lat, .5):.0f}, p90 {q(lat, .9):.0f}, p99 {q(lat, .99):.0f}, max {max(lat)} ms")
        out("  (this is one-way latency + clock offset; a minimum near +50 ms bounds the local clock to within ~50 ms"
            " behind .. ~+50 ms of the exchange clock if the fastest path is ~0-100 ms)")
    out()

    # ---------------------------------------------------------------- sources
    out("== Score sources (polls)")
    polls = collections.defaultdict(lambda: collections.Counter())
    pms = collections.defaultdict(list)
    cc = {}
    last_t: dict[str, int] = {}
    gaps = collections.defaultdict(list)
    ages = collections.defaultdict(list)
    for o in iter_stream("polls"):
        s = o["src"].split(":")[0]
        polls[s][o.get("st")] += 1
        if o.get("st") == 200:
            pms[s].append(o["ms"])
        cc.setdefault(s, o.get("cc"))
        if o.get("age") not in (None, ""):
            try:
                ages[s].append(float(o["age"]))
            except ValueError:
                pass
        k = o["src"]
        if k in last_t and o["r"] - last_t[k] < 60000:
            gaps[s].append((o["r"] - last_t[k]) / 1000)
        last_t[k] = o["r"]
    for s in sorted(polls):
        c = polls[s]
        tot = sum(c.values())
        out(f"{s:10s} polls {tot:7d}  ok {c.get(200, 0):7d}  other: {dict((k, v) for k, v in c.items() if k != 200)}"
            f"  median {statistics.median(pms[s]) if pms[s] else float('nan'):.0f} ms"
            f"  interval per league/match median {q(gaps[s], .5):.1f} s p90 {q(gaps[s], .9):.1f} s  Cache-Control: {cc.get(s)}"
            + (f"  CDN Age header: present {len(ages[s]) / max(1, c.get(200, 0)):.0%}, median {q(ages[s], .5):.0f} s" if ages[s] else ""))
    nsp = sum(1 for _ in iter_stream("pm_sports"))
    out(f"pm_sports  pushed messages {nsp} (Polymarket sports WebSocket, no polling)")
    out("not usable from this sandbox (2026-11-27 probe): SofaScore 403, TheSportsDB 403, FotMob 404, Flashscore (signed header)")
    out()

    # ---------------------------------------------------------------- matches, goals, triggers
    trig = jl(P / "triggers.jsonl")
    fills = jl(P / "fills.jsonl")
    goals = jl(P / "goals.jsonl")
    res = jl(P / "resolved.jsonl")
    links = jl(P / "links.jsonl")
    tr0 = {t["id"]: t for t in trig if t.get("kind") == "trigger"}
    fin = {t["id"]: t for t in trig if t.get("kind") == "final"}
    matches = json.loads((DATA / "matches.json").read_text()) if (DATA / "matches.json").exists() else {}
    t_end = last_r or time.time() * 1000
    inplay = [s for s, m in matches.items() if m.get("t0") and first_r and m["t0"] * 1000 < t_end and
              m["t0"] * 1000 + 2.5 * 3600 * 1000 > first_r]
    out("== Matches and goals")
    out(f"Polymarket soccer matches in play during the recording: {len(inplay)}"
        f" (leagues: {dict(collections.Counter(matches[s]['league'] for s in inplay).most_common(12))})")
    linked = collections.defaultdict(set)
    for l in links:
        linked[l["src"]].add(l["match"])
    out("matches linked per source: " + ", ".join(f"{s} {len(linked[s] & set(inplay))}" for s in SOURCES))
    first_seen = {}
    for g in goals:
        k = (g["match"], g["role"], tuple(g["score"]))
        if k not in first_seen or g["r"] < first_seen[k]["r"]:
            first_seen[k] = g
    by_src = collections.defaultdict(set)
    for g in goals:
        by_src[g["src"]].add((g["match"], g["role"], tuple(g["score"])))
    out(f"distinct goals seen by any source (match, team, new score): {len(first_seen)} in {len({k[0] for k in first_seen})} matches")
    out("  seen per source: " + ", ".join(f"{s} {len(by_src[s])}" for s in SOURCES))
    out("  first source to show the goal: " + str(dict(collections.Counter(g["src"] for g in first_seen.values()))))
    conf = [f for f in fin.values() if f["confirmed"]]
    false = [f for f in fin.values() if not f["confirmed"]]
    open_ = [t for i, t in tr0.items() if i not in fin]
    out(f"triggers: {len(tr0)}  confirmed {len(conf)}  NOT confirmed (false triggers) {len(false)}  still open (<600 s) {len(open_)}")
    if false:
        out("  false triggers, jump size (mid - P_pre) c: " + ", ".join(f"{(f['mid_trig'] - f['p_pre']) * 100:.0f}" for f in false[:40]))
    trig_goals = set()
    for f in conf:
        t = tr0[f["id"]]
        for s, c in f["conf"].items():
            trig_goals.add((t["match"], t["role"], tuple(c["score"])))
    missed = [k for k, g in first_seen.items() if k not in trig_goals and g["r"] < t_end - 600 * 1000]
    out(f"goals with no trigger (book did not jump by the threshold, or the match had no usable book): {len(missed)}")
    out()

    # ---------------------------------------------------------------- lags
    out("== Confirmation lag behind the market's first move (seconds, local receive clock on both ends)")
    out("   negative = the source showed the goal before the book moved")
    out(f"{'source':10s} {'n':>4s} {'share':>6s} {'p10':>7s} {'median':>7s} {'p90':>7s} {'min':>7s} {'max':>7s}   | median vs trigger time")
    nconf = len(conf)
    rows = []
    for s in SOURCES + ("FIRST",):
        lags, lags_t = [], []
        for f in conf:
            t = tr0[f["id"]]
            if s == "FIRST":
                c = f["conf"].get(f["first_src"]) if f.get("first_src") else None
            else:
                c = f["conf"].get(s)
            if c:
                lags.append(c["lag_s"])
                lags_t.append((c["r"] - t["r_trig"]) / 1000)
        if lags:
            out(f"{s:10s} {len(lags):4d} {len(lags) / nconf:6.0%} {q(lags, .1):7.1f} {q(lags, .5):7.1f} {q(lags, .9):7.1f}"
                f" {min(lags):7.1f} {max(lags):7.1f}   | {q(lags_t, .5):6.1f}")
        else:
            out(f"{s:10s} {0:4d}")
        rows.append((s, lags))
    out()

    # ESPN's own goal stamp (summary keyEvents wallclock, 1-s resolution) vs the market's first move
    sys.path.insert(0, str(HERE))
    from paper import team_sim  # noqa: E402
    off = statistics.median(bo) if bo else 0.0
    espn_link = {l["id"]: l["match"] for l in links if l["src"] in ("espn_sum", "espn_sb")}
    kes = collections.defaultdict(list)
    for o in iter_stream("scores"):
        if o.get("src") != "espn_sum_ke":
            continue
        mt = espn_link.get(str(o.get("id")))
        if not mt or mt not in matches:
            continue
        for k in o.get("ke") or []:
            if not k.get("sp") or not k.get("wc"):
                continue
            try:
                wc = datetime.fromisoformat(k["wc"].replace("Z", "+00:00")).timestamp() * 1000
            except ValueError:
                continue
            m = matches[mt]
            role = "home" if team_sim(k.get("team"), m["home"]) >= team_sim(k.get("team"), m["away"]) else "away"
            kes[(mt, role)].append(wc)
    wl = []
    for f in conf:
        t = tr0[f["id"]]
        move_true = t["r_move"] - off
        c = [w for w in kes.get((t["match"], t["role"]), []) if move_true - 120000 <= w <= move_true + 600000]
        if c:
            wl.append((min(c) - move_true) / 1000)
    if wl:
        out(f"ESPN summary 'wallclock' of the goal minus the market's first move: n {len(wl)}, p10 {q(wl, .1):+.1f} s,"
            f" median {q(wl, .5):+.1f} s, p90 {q(wl, .9):+.1f} s (ESPN's own stamp, not when its API showed it)")
    out()

    # ---------------------------------------------------------------- stale dollars (descriptive, look-ahead)
    out("== What was still on offer at t_x (order arrival + 1 s taker delay), scoring team's Yes asks")
    out("   'stale' = price <= P_pre + k x (P_post_real - P_pre); P_post_real = median mid 120-300 s after the move (LOOK-AHEAD, descriptive)")
    ent = [f for f in fills if f.get("kind") == "entry" and f.get("f") == 0.5]
    for d in (1, 3):
        e = [x for x in ent if x["d"] == d and fin.get(x["id"], {}).get("p_post_real") is not None]
        tot50 = tot80 = totcap = 0.0
        per = []
        for x in e:
            pp = fin[x["id"]]["p_post_real"]
            pre = x["p_pre"]
            if pp <= pre:
                continue
            l50, l80 = pre + 0.5 * (pp - pre), pre + 0.8 * (pp - pre)
            a50 = sum(p * s for p, s in x["asks"] if p <= l50 + 1e-9)
            a80 = sum(p * s for p, s in x["asks"] if p <= l80 + 1e-9)
            acap = sum(p * s for p, s in x["asks"] if x.get("cap") is not None and p <= x["cap"] + 1e-9)
            tot50 += a50
            tot80 += a80
            totcap += acap
            per.append(a50)
        if e:
            out(f"d = {d} s: goals {len(per)}; $ at <= halfway {tot50:,.0f} (goals with any: {sum(1 for v in per if v > 0)},"
                f" median per goal ${q(per, .5):,.0f}); $ at <= 80% of the way {tot80:,.0f}; $ at <= ex-ante cap (f 0.5) {totcap:,.0f}")
        else:
            out(f"d = {d} s: no confirmed goal with a post-goal price yet")
    out("   (snapshot = the 25 lowest asks at t_x)")
    out()

    # ---------------------------------------------------------------- paper trades
    out("== Paper trades (BUY scoring team Yes, up to $10, cap = P_pre + f x (Poisson P_post - P_pre), 0.05 fee per leg)")
    winners = {}
    for r_ in res:
        for a in r_.get("assets") or []:
            winners[str(a)] = r_["winner"]
    entries = [f for f in fills if f.get("kind") == "entry"]
    exits = {(f["id"], f["d"], f["f"]): f for f in fills if f.get("kind") == "exitA"}
    tok_cid = {}
    for m in matches.values():
        for mk in m.get("markets") or []:
            for t in mk.get("tokens") or []:
                tok_cid[str(t)] = mk.get("cid")
    need = sorted({tok_cid.get(f["token"]) for f in entries if f.get("status") == "filled" and f["token"] not in winners} - {None})
    gm = gamma_outcomes(need) if need else {}
    for cid, m in gm.items():
        try:
            prices = json.loads(m.get("outcomePrices") or "[]")
            toks = json.loads(m.get("clobTokenIds") or "[]")
        except ValueError:
            continue
        if m.get("closed") and prices and max(float(x) for x in prices) >= 0.99:
            w = toks[[float(x) for x in prices].index(max(float(x) for x in prices))]
            for t in toks:
                winners[str(t)] = str(w)
    out(f"{'d':>2s} {'f':>4s} {'tried':>5s} {'filled':>6s} {'reasons not filled':40s} | exit A: n, net/trade $ (95% CI), c/share, t | exit B (hold): n, net/trade $, c/share, pending")
    for d in (1, 3):
        for fr_ in (0.5, 0.8):
            e = [x for x in entries if x["d"] == d and x["f"] == fr_]
            fl = [x for x in e if x.get("status") == "filled"]
            why = collections.Counter(x.get("status") for x in e if x.get("status") != "filled")
            a_rows, b_rows, pend = [], [], 0
            for x in fl:
                ex = exits.get((x["id"], d, fr_))
                if ex:
                    a_rows.append({"match": x["match"], "net": ex["net"], "sh": x["shares"]})
                w = winners.get(x["token"])
                if w is None:
                    pend += 1
                else:
                    pay = x["shares"] * (1.0 if w == x["token"] else 0.0)
                    b_rows.append({"match": x["match"], "net": pay - x["cost"] - x["fee_in"], "sh": x["shares"]})
            sa = cluster_ci(a_rows, "net")
            sa_s = cluster_ci(a_rows, "net", "sh")
            sb = cluster_ci(b_rows, "net")
            sb_s = cluster_ci(b_rows, "net", "sh")
            fa = (f"{len(a_rows)}, {sa[0]:+.2f} ({sa[0] - 1.96 * sa[1]:+.2f}..{sa[0] + 1.96 * sa[1]:+.2f}), {sa_s[0] * 100:+.1f}c, t {sa[2]:.1f}"
                  if sa else "0")
            fb = (f"{len(b_rows)}, {sb[0]:+.2f} ({sb[0] - 1.96 * sb[1]:+.2f}..{sb[0] + 1.96 * sb[1]:+.2f}), {sb_s[0] * 100:+.1f}c"
                  if sb else "0")
            prim = "  <- primary" if (d, fr_) == (3, 0.5) else ""
            out(f"{d:2d} {fr_:4.1f} {len(e):5d} {len(fl):6d} {str(dict(why))[:40]:40s} | {fa} | {fb}, pending {pend}{prim}")
    out("   8 combinations looked at; primary per protocol = d 3 s, f 0.5, exit A. CI = +-1.96 x cluster-robust se by match.")
    early = [x for x in entries if x["d"] == 3 and x["f"] == 0.5 and x.get("status") == "filled" and x["t_dec"] / 1000 < SPLIT]
    late = [x for x in entries if x["d"] == 3 and x["f"] == 0.5 and x.get("status") == "filled" and x["t_dec"] / 1000 >= SPLIT]
    out(f"   split (primary, filled): early (before 29 Nov) {len(early)}, late {len(late)}; the decision rule needs >= 30 late trades")
    out()
    out("== Each confirmed trigger (first 40)")
    for f in sorted(conf, key=lambda z: z["r_move"])[:40]:
        t = tr0[f["id"]]
        e3 = next((x for x in entries if x["id"] == f["id"] and x["d"] == 3 and x["f"] == 0.5), {})
        srcs = " ".join(f"{s}:{c['lag_s']:+.0f}" for s, c in sorted(f["conf"].items(), key=lambda kv: kv[1]["lag_s"]))
        pp = f.get("p_post_real")
        out(f"{ts(t['r_move'])} {t['match'][:34]:34s} {t['role']:4s} pre {t['p_pre']:.2f} trig {t['mid_trig']:.2f}"
            f" post {pp if pp is None else round(pp, 2)} cap {e3.get('cap')} -> {e3.get('status')} | {srcs}")
    rep = DATA / "report.txt"
    rep.write_text(buf.getvalue())


if __name__ == "__main__":
    main()
