import json, collections, re
evs=json.load(open("data/x3/open_events_top1000.json"))
def tags(e): return [t.get("slug") for t in (e.get("tags") or [])]
by=collections.defaultdict(collections.Counter)
for e in evs:
    tg=tags(e)
    for key in ("weather","mentions","crypto","up-or-down","5M","15M","1H","tennis","ufc","mma","cricket","esports","cs2","lol","dota2","valorant","economy","fed","elon-tweets","earnings","f1","golf","nba","nfl","soccer","hide-from-new","daily-temperature","temperature"):
        if key in tg:
            for m in e.get("markets") or []:
                fs=m.get("feeSchedule") or {}
                by[key][(m.get("secondsDelay"),fs.get("rate"))]+=1
for k,c in by.items(): print(f"{k:18s}", dict(c))
def show(pred, n=1, maxlen=2200):
    k=0
    for e in evs:
        if pred(e):
            m=(e.get("markets") or [{}])[0]
            print("\n=== EVENT", e.get("slug"), "| tags", tags(e)[:8], "| vol24h", round(e.get("volume24hr") or 0), "| nmarkets", len(e.get("markets") or []))
            print("resolutionSource:", e.get("resolutionSource"), "|", m.get("resolutionSource"))
            print("market:", m.get("slug"), "secondsDelay", m.get("secondsDelay"), "fee", m.get("feeSchedule"), "umaBond", m.get("umaBond"), "umaReward", m.get("umaReward"), "customLiveness", m.get("customLiveness"), "automaticallyResolved", m.get("automaticallyResolved"), "resolvedBy", m.get("resolvedBy"))
            print((m.get("description") or e.get("description") or "")[:maxlen])
            k+=1
            if k>=n: break
show(lambda e: "weather" in tags(e) and "temperature" in (e.get("slug") or ""), n=2)
show(lambda e: "mentions" in tags(e), n=2)
show(lambda e: "elon-tweets" in tags(e), n=1)
show(lambda e: (e.get("seriesSlug") or "")=="nba-2026", n=1, maxlen=900)
show(lambda e: (e.get("seriesSlug") or "")=="premier-league-2025", n=1, maxlen=900)
show(lambda e: "up-or-down" in tags(e) and "1H" in tags(e), n=1, maxlen=900)
