#!/usr/bin/env python3
"""Dump a handle's timeline to jsonl with cursor resume. usage: tl.py Handle out.jsonl since [start_cursor] [pages]"""
import json, sys, time, urllib.request, datetime as dt
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
API = "https://api.fxtwitter.com"
def get(url, tries=6):
    last=None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read())
        except Exception as e:
            last=e; time.sleep(2.5*(i+1))
    return {"_err": str(last)}
h, out, since = sys.argv[1], sys.argv[2], sys.argv[3]
cursor = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != "-" else None
pages = int(sys.argv[5]) if len(sys.argv) > 5 else 60
since_ts = dt.datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc).timestamp()
seen=set()
try:
    for l in open(out):
        seen.add(json.loads(l)["id"])
except FileNotFoundError:
    pass
f=open(out,"a")
for p in range(pages):
    d = get(f"{API}/2/profile/{h}/statuses" + (f"?cursor={cursor}" if cursor else ""))
    if "_err" in d:
        print("ERR", d["_err"], "cursor", cursor); break
    rows = d.get("results") or []
    if not rows:
        print("no rows", d.get("code"), "cursor", cursor); break
    oldest=None; new=0
    for s in rows:
        ts = s.get("created_timestamp") or 0
        oldest = ts if oldest is None else min(oldest, ts)
        if s.get("id") in seen: continue
        seen.add(s.get("id")); new+=1
        f.write(json.dumps(s, ensure_ascii=False)+"\n")
    cursor = (d.get("cursor") or {}).get("bottom")
    print(p, len(rows), new, dt.datetime.fromtimestamp(oldest, dt.timezone.utc).isoformat() if oldest else None, cursor, flush=True)
    if not cursor or (oldest and oldest < since_ts): break
    time.sleep(0.8)
