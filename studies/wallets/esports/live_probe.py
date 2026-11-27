"""Is a finished pro game visible in public APIs before the delayed broadcast (and the market) shows the end?
Polls OpenDota /live (DotaTV feed, has its own `delay`), /proMatches (finished games) and the Polymarket book."""
import json, time, sys, lib
from pmlab import http
n = int(sys.argv[1]) if len(sys.argv) > 1 else 1; gap = int(sys.argv[2]) if len(sys.argv) > 2 else 20
log = open(f"{lib.HERE}/out/live_probe.jsonl", "a")
for i in range(n):
    now = int(time.time()); row = {"now": now, "iso": lib.iso(now)}
    try:
        lv = [g for g in http.get_json("https://api.opendota.com/api/live") if g.get("league_id") and g.get("team_name_radiant")]
        row["live"] = [{k: g.get(k) for k in ("match_id", "team_name_radiant", "team_name_dire", "game_time", "delay", "radiant_lead", "radiant_score", "dire_score", "last_update_time", "activate_time", "deactivate_time")} for g in lv]
        pm = http.get_json("https://api.opendota.com/api/proMatches")[:6]
        row["pro"] = [{k: g.get(k) for k in ("match_id", "radiant_name", "dire_name", "start_time", "duration", "radiant_win", "league_name")} for g in pm]
    except Exception as e: row["err"] = str(e)[:100]
    log.write(json.dumps(row) + "\n"); log.flush()
    for g in row.get("live", []): print(row["iso"], "LIVE", g)
    for g in row.get("pro", [])[:3]: print(row["iso"], "PRO ", g, "real_end+90", lib.iso(g["start_time"] + g["duration"] + 90), "seen_after_s", now - (g["start_time"] + g["duration"] + 90))
    if i < n - 1: time.sleep(gap)
