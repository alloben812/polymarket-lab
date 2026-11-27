"""Fetch the sample fixed in protocol.md: ESPN games + scoring events with wallclock, matching Polymarket
moneyline markets, their whole tapes and resolutions. Output: data/gaps_sports_lag/{games.json, tapes/}."""
from __future__ import annotations

import difflib
import gzip
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from pmlab import dataapi
from pmlab.http import get_json

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data" / "gaps_sports_lag"
TAPES = OUT / "tapes"
GAMMA = "https://gamma-api.polymarket.com"
ESPN = "https://site.api.espn.com/apis/site/v2/sports"

SOCCER = {"eng.1": "premier-league", "esp.1": "la-liga", "ger.1": "bundesliga", "ita.1": "sea",
          "fra.1": "ligue-1", "uefa.champions": "ucl", "uefa.europa": "uel"}
S_LO, S_HI = "2026-11-21T00:00:00Z", "2026-11-27T00:00:00Z"
N_LO, N_HI = "2026-11-20T00:00:00Z", "2026-11-27T06:00:00Z"
SLUG_RE = re.compile(r"^[a-z0-9]+-[a-z0-9]+-[a-z0-9]+-2026-11-(1[9]|2[0-7])$")


def ts(s: str) -> int:
    s = s.replace("Z", "+00:00")
    if len(s) == 22 and s[-6] == "+" and "T" in s and s.count(":") == 2:  # 2026-11-22T18:00+00:00
        s = s[:-6] + ":00+00:00"
    return int(datetime.fromisoformat(s).timestamp())


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(fc|cf|afc|sc|ac|ssc|as|ss|sk|fk|rc|rcd|ud|cd|sv|vfb|vfl|tsg|bv|club|de|of|the|1)\b", " ", s)
    return re.sub(r"[^a-z0-9 ]", " ", s).strip()


def sim(a: str, b: str) -> float:
    a, b = norm(a), norm(b)
    r = difflib.SequenceMatcher(None, a, b).ratio()
    if a and b and (a in b or b in a):
        r = max(r, 0.9)
    ta, tb = set(a.split()), set(b.split())
    if ta & tb:
        r = max(r, 0.75)
    return r


def gamma_events(tag: str, lo: str, hi: str) -> list[dict]:
    out = []
    for off in range(0, 2000, 50):
        d = get_json(f"{GAMMA}/events", {"tag_slug": tag, "end_date_min": lo, "end_date_max": hi, "limit": 50, "offset": off},
                     cache=True)
        out += d
        if len(d) < 50:
            break
    return [e for e in out if SLUG_RE.match(e["slug"])]


def espn_games(sport: str, league: str, lo: str, hi: str) -> list[dict]:
    evs, seen = [], set()
    for day in range(19, 28):
        d = get_json(f"{ESPN}/{sport}/{league}/scoreboard", {"dates": f"202611{day:02d}"}, cache=True)
        for e in d.get("events") or []:
            if e["id"] not in seen:
                seen.add(e["id"]); evs.append(e)
    out = []
    for e in evs:
        t0 = ts(e["date"])
        if not (ts(lo) <= t0 < ts(hi)):
            continue
        if e["status"]["type"].get("name") != "STATUS_FINAL" and not e["status"]["type"].get("completed"):
            continue
        comp = e["competitions"][0]
        teams = {c["homeAway"]: c["team"] for c in comp["competitors"]}
        out.append({"espn_id": e["id"], "t0": t0, "home": teams["home"], "away": teams["away"], "league": league})
    return out


def soccer_events(league: str, gid: str, home_id: str) -> list[dict]:
    s = get_json(f"{ESPN}/soccer/{league}/summary", {"event": gid}, cache=True)
    ev = []
    for k in s.get("keyEvents") or []:
        if not k.get("scoringPlay") or k.get("shootout") or not k.get("wallclock"):
            continue
        ev.append({"t": ts(k["wallclock"]), "team_id": (k.get("team") or {}).get("id"), "text": (k.get("shortText") or k.get("text") or "")[:80],
                   "clock": (k.get("clock") or {}).get("displayValue")})
    ev.sort(key=lambda x: x["t"])
    # running score
    h = a = 0
    for x in ev:
        x["before"] = (h, a)
        if x["team_id"] == home_id:
            h += 1
        else:
            a += 1
        x["after"] = (h, a)
    return ev


def nfl_events(gid: str) -> list[dict]:
    s = get_json(f"{ESPN}/football/nfl/summary", {"event": gid}, cache=True)
    wc = {}
    for dr in (s.get("drives") or {}).get("previous") or []:
        for p in dr.get("plays") or []:
            if p.get("wallclock"):
                wc[p["id"]] = p["wallclock"]
    ev = []
    for p in s.get("scoringPlays") or []:
        w = wc.get(p["id"])
        if not w:
            continue
        ev.append({"t": ts(w), "team_id": (p.get("team") or {}).get("id"), "text": (p.get("type") or {}).get("text", "")[:40],
                   "after": (p.get("homeScore"), p.get("awayScore"))})
    ev.sort(key=lambda x: x["t"])
    return ev


def tape(cid: str) -> list[dict]:
    path = TAPES / f"{cid}.jsonl.gz"
    if path.exists():
        with gzip.open(path, "rt") as f:
            return [json.loads(l) for l in f]
    rows = [{"t": r["timestamp"], "s": r["side"], "o": r["outcome"], "z": float(r["size"]), "p": float(r["price"]),
             "w": r.get("proxy_wallet")} for r in dataapi.iter_trades(condition=cid)]
    rows.sort(key=lambda r: r["t"])
    TAPES.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with gzip.open(tmp, "wt") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    tmp.replace(path)
    return rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    games = []
    log = []
    # soccer
    for league, tag in SOCCER.items():
        eg = espn_games("soccer", league, S_LO, S_HI)
        pm = gamma_events(tag, "2026-11-19T00:00:00Z", "2026-11-28T00:00:00Z")
        log.append(f"{league}: espn {len(eg)} gamma {len(pm)}")
        for g in eg:
            best, bs = None, 0.0
            for e in pm:
                st = e.get("startTime") or e.get("endDate")
                if abs(ts(st) - g["t0"]) > 1200:
                    continue
                mk = [m for m in e.get("markets") or [] if m.get("sportsMarketType") == "moneyline"]
                if len(mk) != 3:
                    continue
                draw = [m for m in mk if m["slug"].endswith("-draw")]
                teams = [m for m in mk if not m["slug"].endswith("-draw")]
                if len(draw) != 1 or len(teams) != 2:
                    continue
                q = [re.sub(r"^Will (.*) win on .*$", r"\1", m["question"]) for m in teams]
                s1 = sim(q[0], g["home"]["displayName"]) + sim(q[1], g["away"]["displayName"])
                s2 = sim(q[1], g["home"]["displayName"]) + sim(q[0], g["away"]["displayName"])
                sc = max(s1, s2)
                if sc > bs:
                    hm, am = (teams[0], teams[1]) if s1 >= s2 else (teams[1], teams[0])
                    best, bs = {"event": e["slug"], "home_m": hm, "away_m": am, "draw_m": draw[0]}, sc
            if best is None or bs < 1.2:
                log.append(f"  no match {g['home']['displayName']} v {g['away']['displayName']} best {bs:.2f}")
                continue
            ev = soccer_events(league, g["espn_id"], g["home"]["id"])
            mk = {}
            for role in ("home_m", "away_m", "draw_m"):
                m = best[role]
                mk[role[:-2]] = {"cid": m["conditionId"], "slug": m["slug"], "q": m["question"], "delay": m.get("secondsDelay"),
                                 "rate": (m.get("feeSchedule") or {}).get("rate"), "vol": m.get("volumeNum")}
            games.append({"sport": "soccer", "league": league, "espn_id": g["espn_id"], "t0": g["t0"], "event": best["event"],
                          "home": g["home"]["displayName"], "away": g["away"]["displayName"], "home_id": g["home"]["id"],
                          "away_id": g["away"]["id"], "markets": mk, "events": ev, "match_score": round(bs, 2)})
    # NFL
    eg = espn_games("football", "nfl", N_LO, N_HI)
    pm = gamma_events("nfl", "2026-11-19T00:00:00Z", "2026-11-28T00:00:00Z")
    log.append(f"nfl: espn {len(eg)} gamma {len(pm)}")
    for g in eg:
        best, bs = None, 0.0
        for e in pm:
            st = e.get("startTime") or e.get("endDate")
            if abs(ts(st) - g["t0"]) > 1200:
                continue
            ml = [m for m in e.get("markets") or [] if m["slug"] == e["slug"]]
            if len(ml) != 1:
                continue
            outs = json.loads(ml[0]["outcomes"])
            s1 = sim(outs[0], g["home"]["name"]) + sim(outs[1], g["away"]["name"])
            s2 = sim(outs[1], g["home"]["name"]) + sim(outs[0], g["away"]["name"])
            sc = max(s1, s2)
            if sc > bs:
                best, bs = (e, ml[0], outs, s1 >= s2), sc
        if best is None or bs < 1.2:
            log.append(f"  no match NFL {g['home']['name']} v {g['away']['name']} {bs:.2f}")
            continue
        e, m, outs, straight = best
        home_out, away_out = (outs[0], outs[1]) if straight else (outs[1], outs[0])
        games.append({"sport": "nfl", "league": "nfl", "espn_id": g["espn_id"], "t0": g["t0"], "event": e["slug"],
                      "home": g["home"]["name"], "away": g["away"]["name"], "home_id": g["home"]["id"], "away_id": g["away"]["id"],
                      "home_out": home_out, "away_out": away_out,
                      "markets": {"ml": {"cid": m["conditionId"], "slug": m["slug"], "q": m["question"], "delay": m.get("secondsDelay"),
                                         "rate": (m.get("feeSchedule") or {}).get("rate"), "vol": m.get("volumeNum")}},
                      "events": nfl_events(g["espn_id"]), "match_score": round(bs, 2)})
    games.sort(key=lambda g: g["t0"])
    log.append(f"games kept: {len(games)}")
    # tapes + resolutions
    cids = [m["cid"] for g in games for m in g["markets"].values()]
    res = dataapi.resolutions(cids)
    for g in games:
        for k, m in g["markets"].items():
            m["final"] = (res.get(m["cid"]) or {}).get("final")
            try:
                m["n_rows"] = len(tape(m["cid"]))
            except Exception as ex:  # noqa
                m["n_rows"] = None
                log.append(f"  tape fail {m['slug']}: {ex}")
        print(g["event"], len(g["events"]), [m["n_rows"] for m in g["markets"].values()], flush=True)
    (OUT / "games.json").write_text(json.dumps(games, indent=1))
    print("\n".join(log))


if __name__ == "__main__":
    sys.exit(main())
