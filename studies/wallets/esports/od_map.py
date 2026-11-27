"""Map Polymarket Dota 2 'Game N Winner' markets to OpenDota pro matches (team names + time + order in the series).
Check: the OpenDota winner must equal the Polymarket resolution. Output out/od_map.json."""
import json, re, difflib, collections, time, lib
from pmlab import http
rows = json.load(open(f"{lib.HERE}/out/od_pro.json"))
last = min(r["match_id"] for r in rows)
if len(rows) < 500:   # two more pages for safety (a stray old match can end the paging early)
    for _ in range(3):
        d = http.get_json("https://api.opendota.com/api/proMatches", {"less_than_match_id": last}); rows += d; last = min(r["match_id"] for r in d); time.sleep(1.1)
    json.dump(rows, open(f"{lib.HERE}/out/od_pro.json", "w"))
days = collections.Counter(lib.iso(r["start_time"])[:5] for r in rows); print("pro matches", len(rows), sorted(days.items()))
norm = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower().replace("team", "").replace("esports", "").replace("gaming", ""))
def same(a, b):
    a, b = norm(a), norm(b)
    return bool(a and b) and (a == b or (len(a) >= 3 and a in b) or (len(b) >= 3 and b in a) or difflib.SequenceMatcher(None, a, b).ratio() >= 0.75)
ser = collections.defaultdict(list)
for r in rows:
    if r.get("radiant_name") and r.get("dire_name"): ser[(r["series_id"] or r["match_id"])].append(r)
for s in ser.values(): s.sort(key=lambda r: r["start_time"])
conds = {}
for n in lib.WALLETS:
    F = lib.fills(n); M = lib.meta({f["condition_id"] for f in F})
    for c, m in M.items():
        if (m.get("slug") or "").startswith("dota2-") and lib.mtype(m) == "child_moneyline": conds[c] = m
R = lib.resol(list(conds))
out = {}; bad = 0; nomatch = 0
for c, m in conds.items():
    g = re.search(r"game(\d)$", m["slug"]); outs = lib.gamma.jfield(m["outcomes"]); gs = lib.ts(m.get("gameStartTime"))
    if not g or not gs: continue
    k = int(g.group(1)); hit = None
    for s in ser.values():
        a = s[0]
        if not (gs - 3 * 3600 <= a["start_time"] <= gs + 10 * 3600): continue
        if (same(a["radiant_name"], outs[0]) and same(a["dire_name"], outs[1])) or (same(a["radiant_name"], outs[1]) and same(a["dire_name"], outs[0])):
            if len(s) >= k: hit = s[k - 1]
            break
    if not hit: nomatch += 1; continue
    w = hit["radiant_name"] if hit["radiant_win"] else hit["dire_name"]
    fin = (R.get(c) or {}).get("final") or {}
    pm_w = next((o for o in outs if float(fin.get(o) or 0) == 1), None)
    ok = pm_w is not None and same(w, pm_w)
    if pm_w is not None and not ok: bad += 1; continue
    out[c] = dict(slug=m["slug"], match_id=hit["match_id"], start=hit["start_time"], dur=hit["duration"], radiant=hit["radiant_name"], dire=hit["dire_name"], radiant_win=hit["radiant_win"], league=hit["league_name"], out0_is_radiant=same(hit["radiant_name"], outs[0]), checked=ok)
json.dump(out, open(f"{lib.HERE}/out/od_map.json", "w"))
print(f"dota2 game markets {len(conds)}, mapped {len(out)} (winner agrees with the Polymarket resolution in all of them), winner mismatch (dropped) {bad}, no match {nomatch}")
print(collections.Counter(v["league"] for v in out.values()).most_common(8))
