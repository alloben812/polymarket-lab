"""OpenDota pro matches for the study window -> out/od_pro.json (public API, no key)."""
import json, time, os, lib
from pmlab import http
out = f"{lib.HERE}/out/od_pro.json"
rows = []; last = None; lo = lib.END - 15*86400
while True:
    p = {"less_than_match_id": last} if last else {}
    d = http.get_json("https://api.opendota.com/api/proMatches", p)
    if not d: break
    rows += d; last = min(r["match_id"] for r in d)
    if min(r["start_time"] for r in d) < lo or len(rows) > 6000: break
    time.sleep(1.1)
json.dump(rows, open(out, "w")); print("pro matches", len(rows), lib.iso(min(r["start_time"] for r in rows)), lib.iso(max(r["start_time"] for r in rows)))
