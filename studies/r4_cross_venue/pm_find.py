import json, sys, urllib.request, urllib.parse, gzip, time
G = "https://gamma-api.polymarket.com"
def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=60) as r:
        b = r.read()
        if r.headers.get("Content-Encoding") == "gzip": b = gzip.decompress(b)
        return json.loads(b)
for q in sys.argv[1:]:
    if q.startswith("slug:"):
        evs = get(f"{G}/events?slug={q[5:]}")
    else:
        d = get(f"{G}/public-search?q={urllib.parse.quote(q)}&limit_per_type=8&events_status=active")
        evs = d.get("events") or []
    print(f"=== {q}: {len(evs)} events")
    for e in evs[:8]:
        if e.get("closed"): continue
        ms = e.get("markets") or []
        print(f"  EV {e.get('slug')} | {e.get('title')} | vol={float(e.get('volume') or 0):.0f} v24={float(e.get('volume24hr') or 0):.0f} negRisk={e.get('negRisk')} n={len(ms)} end={e.get('endDate')}")
        ms = sorted([m for m in ms if not m.get('closed')], key=lambda m: -float(m.get('volume24hr') or 0))[:int(6)]
        for m in ms:
            print(f"     {m.get('slug')[:60]:<60} bid={m.get('bestBid')} ask={m.get('bestAsk')} v24={float(m.get('volume24hr') or 0):.0f} fee={ (m.get('feeSchedule') or {}).get('rate')} | {m.get('groupItemTitle') or m.get('question')[:50]}")
    time.sleep(0.2)
