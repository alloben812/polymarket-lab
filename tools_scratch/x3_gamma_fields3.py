import json, collections
evs=json.load(open("data/x3/open_events_top1000.json"))
def tags(e): return [t.get("slug") for t in (e.get("tags") or [])]
def show(pred, n=1, maxlen=1800):
    k=0
    for e in evs:
        if pred(e):
            m=(e.get("markets") or [{}])[0]
            print("\n=== EVENT", e.get("slug"), "| series", e.get("seriesSlug"), "| tags", tags(e)[:8], "| vol24h", round(e.get("volume24hr") or 0), "| nmarkets", len(e.get("markets") or []))
            print("resolutionSource:", e.get("resolutionSource"), "|", m.get("resolutionSource"))
            print("market:", m.get("slug"), "secondsDelay", m.get("secondsDelay"), "fee", m.get("feeSchedule"), "umaBond", m.get("umaBond"), "customLiveness", m.get("customLiveness"))
            print((m.get("description") or e.get("description") or "")[:maxlen])
            k+=1
            if k>=n: break
show(lambda e: (e.get("seriesSlug") or "")=="elon-tweets" or "elon-musk-of-tweets" in (e.get("slug") or ""), n=1, maxlen=2500)
show(lambda e: any("mention" in (t or "") for t in tags(e)) or "say" in (e.get("slug") or "").split("-"), n=2, maxlen=2500)
# liveness distribution by first-tag
c=collections.defaultdict(collections.Counter)
for e in evs:
    tg=tags(e)
    grp = "weather" if "weather" in tg else "sports" if "sports" in tg else "crypto" if "crypto" in tg else "politics" if "politics" in tg else "other"
    for m in e.get("markets") or []:
        c[grp][(m.get("customLiveness"), m.get("umaBond"))]+=1
for g,cc in c.items(): print(g, cc.most_common(6))
