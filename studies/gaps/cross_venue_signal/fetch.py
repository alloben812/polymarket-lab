"""Fetch the sample fixed in protocol.md.
1) football-data rows (already in data/gaps_cross_venue_signal/raw/), 2) gamma match events per league, matched,
3) whole tapes of the three moneyline markets, newest kick-off first, with a hard wall-clock deadline.
Output: data/gaps_cross_venue_signal/{matches.json, tapes/}."""
from __future__ import annotations

import csv
import gzip
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sports_score_lag"))
from fetch import sim, ts  # noqa: E402  (same matching code as the sports lag study)

from pmlab import dataapi
from pmlab.http import get_json

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data" / "gaps_cross_venue_signal"
RAW = OUT / "raw"
TAPES = OUT / "tapes"
OLD_TAPES = ROOT / "data" / "gaps_sports_lag" / "tapes"
GAMMA = "https://gamma-api.polymarket.com"
LEAGUES = {"E0": "premier-league", "E1": "efl-championship", "SP1": "la-liga", "D1": "bundesliga", "I1": "sea",
           "F1": "ligue-1"}
LON = ZoneInfo("Europe/London")
SLUG_RE = re.compile(r"^[a-z0-9]+-[a-z0-9]+-[a-z0-9]+-2026-\d\d-\d\d$")
DEADLINE = datetime(2026, 11, 27, 19, 40, tzinfo=timezone.utc).timestamp()


def fd_rows(div: str) -> list[dict]:
    out = []
    for r in csv.DictReader(open(RAW / f"fd_2627_{div}.csv", encoding="utf-8-sig")):
        if not r.get("Date") or not r.get("FTR"):
            continue
        d = datetime.strptime(r["Date"] + " " + (r.get("Time") or "15:00"), "%d/%m/%Y %H:%M").replace(tzinfo=LON)
        r["k"] = int(d.timestamp())
        r["div"] = div
        out.append(r)
    return out


def gamma_events(tag: str) -> list[dict]:
    out = []
    for off in range(0, 6000, 50):
        d = get_json(f"{GAMMA}/events", {"tag_slug": tag, "end_date_min": "2026-08-10T00:00:00Z",
                                         "end_date_max": "2026-11-27T00:00:00Z", "limit": 50, "offset": off},
                     cache=True)
        out += d
        if len(d) < 50:
            break
    return [e for e in out if SLUG_RE.match(e["slug"])]


def pick(e: dict):
    mk = [m for m in e.get("markets") or [] if m.get("sportsMarketType") == "moneyline"]
    if len(mk) != 3:
        return None
    draw = [m for m in mk if m["slug"].endswith("-draw")]
    teams = [m for m in mk if not m["slug"].endswith("-draw")]
    if len(draw) != 1 or len(teams) != 2:
        return None
    return draw[0], teams


def tape(cid: str) -> int:
    for d in (TAPES, OLD_TAPES):
        p = d / f"{cid}.jsonl.gz"
        if p.exists():
            return -1
    rows = [{"t": r["timestamp"], "s": r["side"], "o": r["outcome"], "z": float(r["size"]), "p": float(r["price"]),
             "w": r.get("proxy_wallet")} for r in dataapi.iter_trades(condition=cid)]
    rows.sort(key=lambda r: r["t"])
    path = TAPES / f"{cid}.jsonl.gz"
    tmp = path.with_suffix(".tmp")
    with gzip.open(tmp, "wt") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    tmp.replace(path)
    return len(rows)


def main():
    TAPES.mkdir(parents=True, exist_ok=True)
    log = []
    matches = []
    for div, tag in LEAGUES.items():
        rows = fd_rows(div)
        evs = [(e, pick(e)) for e in gamma_events(tag)]
        evs = [(e, p) for e, p in evs if p]
        nm = 0
        for r in rows:
            best, bs = None, 0.0
            for e, (draw, teams) in evs:
                st = e.get("startTime") or e.get("endDate")
                if not st or abs(ts(st) - r["k"]) > 3 * 3600:
                    continue
                q = [re.sub(r"^Will (.*) win on .*$", r"\1", m["question"]) for m in teams]
                s1 = sim(q[0], r["HomeTeam"]) + sim(q[1], r["AwayTeam"])
                s2 = sim(q[1], r["HomeTeam"]) + sim(q[0], r["AwayTeam"])
                sc = max(s1, s2)
                if sc > bs:
                    hm, am = (teams[0], teams[1]) if s1 >= s2 else (teams[1], teams[0])
                    best, bs = (e, hm, am, draw, ts(st)), sc
            if best is None or bs < 1.2:
                log.append(f"{div} no match {r['Date']} {r['HomeTeam']} v {r['AwayTeam']} best {bs:.2f}")
                continue
            e, hm, am, dm, st = best
            mk = {}
            for role, m in (("H", hm), ("A", am), ("D", dm)):
                mk[role] = {"cid": m["conditionId"], "slug": m["slug"], "q": m["question"],
                            "rate": (m.get("feeSchedule") or {}).get("rate"), "vol": m.get("volumeNum"),
                            "outcomes": m.get("outcomes"), "outcomePrices": m.get("outcomePrices"),
                            "closed": m.get("closed"), "created": m.get("createdAt"), "start": m.get("gameStartTime")}
            odds = {k: r.get(k) for k in r if k.startswith(("BFE", "Avg", "Max", "B365")) or k in ("FTR", "FTHG", "FTAG")}
            matches.append({"div": div, "date": r["Date"], "time": r.get("Time"), "k": r["k"], "pm_start": st,
                            "home": r["HomeTeam"], "away": r["AwayTeam"], "event": e["slug"], "score": round(bs, 2),
                            "markets": mk, "odds": odds})
            nm += 1
        log.append(f"{div}: fd {len(rows)} gamma events {len(evs)} matched {nm}")
        print(log[-1], flush=True)
    # duplicates: one gamma event matched twice -> keep the best score
    seen = {}
    for m in matches:
        if m["event"] not in seen or m["score"] > seen[m["event"]]["score"]:
            seen[m["event"]] = m
    matches = sorted(seen.values(), key=lambda m: -m["k"])
    json.dump(matches, open(OUT / "matches.json", "w"))
    (OUT / "match_log.txt").write_text("\n".join(log))
    print("matched", len(matches), flush=True)
    if "--no-tapes" in sys.argv:
        return
    jobs = [(m["k"], m["markets"][r]["cid"]) for m in matches for r in ("H", "D", "A")]
    done = 0
    with ThreadPoolExecutor(3) as ex:
        futs = {}
        it = iter(jobs)
        def submit():
            try:
                k, cid = next(it)
            except StopIteration:
                return False
            futs[ex.submit(tape, cid)] = (k, cid)
            return True
        for _ in range(6):
            submit()
        while futs:
            for f in as_completed(list(futs)):
                k, cid = futs.pop(f)
                try:
                    n = f.result()
                except Exception as exn:  # noqa: BLE001
                    print("ERR", cid, exn, flush=True)
                done += 1
                if done % 50 == 0:
                    print(time.strftime("%H:%M:%S"), "tapes", done, "of", len(jobs), "k", k, flush=True)
                if time.time() < DEADLINE:
                    submit()
                break
    print("tapes done", done, "of", len(jobs), flush=True)


if __name__ == "__main__":
    main()
