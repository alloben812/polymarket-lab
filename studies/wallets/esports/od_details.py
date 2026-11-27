"""OpenDota match details (kills_log, teamfights, objectives, gold adv) for the mapped matches -> out/od_matches/<id>.json"""
import json, os, time, lib
from pmlab import http
mp = json.load(open(f"{lib.HERE}/out/od_map.json")); os.makedirs(f"{lib.HERE}/out/od_matches", exist_ok=True)
ids = sorted({v["match_id"] for v in mp.values()}); got = 0
for i in ids:
    p = f"{lib.HERE}/out/od_matches/{i}.json"
    if os.path.exists(p): continue
    try:
        d = http.get_json(f"https://api.opendota.com/api/matches/{i}")
    except Exception as e:
        print("fail", i, str(e)[:80]); time.sleep(5); continue
    keep = {k: d.get(k) for k in ("match_id", "start_time", "duration", "pre_game_duration", "first_blood_time", "radiant_win", "radiant_gold_adv", "objectives", "radiant_name", "dire_name", "draft_timings", "pauses")}
    keep["teamfights"] = [{k: t.get(k) for k in ("start", "end", "last_death", "deaths")} | {"rad_gold": sum((p.get("gold_delta") or 0) for p in (t.get("players") or [])[:5]), "dire_gold": sum((p.get("gold_delta") or 0) for p in (t.get("players") or [])[5:])} for t in (d.get("teamfights") or [])]
    keep["kills"] = sorted((k["time"], pl.get("isRadiant", pl.get("player_slot", 0) < 128)) for pl in (d.get("players") or []) for k in (pl.get("kills_log") or []))
    json.dump(keep, open(p, "w")); got += 1; time.sleep(1.2)
print("details fetched", got, "of", len(ids))
