"""Auditor's own download (urllib, tx hashes kept) for a sample of markets; compare with the analyst's cache."""
import sys; sys.path.insert(0, "/tmp/claude-0/-home-user/05556429-066d-541b-b886-b8da26bcc648/scratchpad/audit")
import json, gzip, os, time, random, urllib.request, urllib.parse, collections
from a1 import *
API="https://data-api.polymarket.com/v2"
def get(path, **params):
    url=f"{API}/{path}?"+urllib.parse.urlencode({k:v for k,v in params.items() if v is not None})
    for attempt in range(4):
        try:
            req=urllib.request.Request(url, headers={"User-Agent":"research-client/1.0","Accept":"application/json"})
            with urllib.request.urlopen(req, timeout=30) as r: return json.loads(r.read())
        except Exception as ex:
            if attempt==3: raise
            time.sleep(1.5*(attempt+1))
def tape(cond, stop_ts):
    rows=[]; cursor=None
    for page in range(40):
        d=get("trades", condition=cond, limit=1000, cursor=cursor) if cursor is None else get("trades", condition=cond, cursor=cursor)
        data=d.get("data") or []
        rows+=data
        cursor=(d.get("pagination") or {}).get("next_cursor")
        if not data or not cursor or min(x["timestamp"] for x in data) < stop_ts: break
        time.sleep(0.2)
    return rows
if __name__=="__main__":
    res30={m["cond"]: e4(rows_gaps(m), m, 30) for m in kept}
    must=[m for m in kept if res30[m["cond"]]["fills"]]
    rng=random.Random(20261127); rest=[m for m in kept if not res30[m["cond"]]["fills"]]; rng.shuffle(rest)
    sample=must+rest[:58]
    os.makedirs("live", exist_ok=True)
    for i,m in enumerate(sample):
        p=f"live/{m['cond']}.json"
        if os.path.exists(p): continue
        rows=tape(m["cond"], m["T"]-7203)
        json.dump(rows, open(p,"w")); time.sleep(0.25)
    print("downloaded", len(sample), "markets;", len({m['T'] for m in sample}), "release seconds")
    json.dump([m["cond"] for m in sample], open("sample.json","w"))
