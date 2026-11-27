"""Live test (2026-11-27, Aurora vs PARIVISION, BLAST Slam IX, game 1 then game 2): when does the finished game
appear in OpenDota /proMatches (real time?) compared with the DotaTV feed (/live, delay 900 s) and with the
Polymarket game-winner price? One row per poll in out/live_probe2.jsonl."""
import json, time, sys, lib
from pmlab import http, gamma
MID = int(sys.argv[1]); slugs = sys.argv[2].split(","); n = int(sys.argv[3]); gap = int(sys.argv[4])
log = open(f"{lib.HERE}/out/live_probe2.jsonl", "a"); seen = False
for i in range(n):
    now = int(time.time()); row = {"now": now, "iso": lib.iso(now)}
    try:
        lv = [g for g in http.get_json("https://api.opendota.com/api/live") if g.get("league_id") == 20208]
        row["live"] = [{k: g.get(k) for k in ("match_id", "game_time", "delay", "radiant_lead", "radiant_score", "dire_score", "last_update_time", "activate_time", "deactivate_time")} for g in lv]
        pm = http.get_json("https://api.opendota.com/api/proMatches")[:8]
        row["pro"] = [{k: g.get(k) for k in ("match_id", "radiant_name", "dire_name", "start_time", "duration", "radiant_win")} for g in pm if g.get("leagueid") == 20208][:3]
        row["pro_has_target"] = any(g["match_id"] == MID for g in pm)
    except Exception as e: row["err"] = str(e)[:100]
    row["pm"] = {}
    for s in slugs:
        try:
            m = gamma.market_by_slug(s); row["pm"][s] = [m.get("bestBid"), m.get("bestAsk"), m.get("lastTradePrice"), m.get("closed")]
        except Exception as e: row["pm"][s] = str(e)[:60]
    try:
        e = gamma.event_by_slug(slugs[-1]); row["pm_score"] = [e.get("score"), e.get("period"), e.get("live"), e.get("ended")]
    except Exception as e: pass
    log.write(json.dumps(row) + "\n"); log.flush(); time.sleep(gap)
