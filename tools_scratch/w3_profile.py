import json, sys, urllib.request, collections, time, re
W, START, END = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
def get(url):
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"}), timeout=60) as r:
                return json.load(r)
        except Exception as e:
            err = e; time.sleep(1+i)
    raise err
def pull(taker_only):
    rows, cur = [], None
    while True:
        u = f"https://data-api.polymarket.com/v2/trades?user={W}&start={START}&end={END}&taker_only={'true' if taker_only else 'false'}&limit=1000" + (f"&cursor={cur}" if cur else "")
        d = get(u)
        data = d.get("data", d if isinstance(d, list) else [])
        rows += data
        cur = (d.get("pagination") or {}).get("next_cursor") if isinstance(d, dict) else None
        if not cur or not data or len(rows) > 40000: break
    return rows
allr = pull(False); tk = pull(True)
print("fills all", len(allr), "taker", len(tk))
if allr: print("keys:", sorted(allr[0].keys()))
def g(r, *ks):
    for k in ks:
        if k in r: return r[k]
usd = lambda r: float(g(r,"size") or 0)*float(g(r,"price") or 0)
tot = sum(usd(r) for r in allr); tkusd = sum(usd(r) for r in tk)
print(f"notional ${tot:,.0f}, taker share {tkusd/max(tot,1):.0%}")
side = collections.Counter(); pb = collections.Counter(); cat = collections.Counter(); ev = collections.Counter()
for r in allr:
    s = g(r,"side"); p = float(g(r,"price") or 0); t = g(r,"title","market_title","question") or ""
    side[s] += usd(r)
    b = "<0.05" if p<0.05 else "0.05-0.20" if p<0.2 else "0.20-0.50" if p<0.5 else "0.50-0.80" if p<0.8 else "0.80-0.95" if p<0.95 else ">=0.95"
    pb[(s,b)] += usd(r)
    k = "temp-daily" if re.search(r"temperature|°|highest temp|lowest temp", t, re.I) else "tweets" if re.search(r"tweet|post", t, re.I) else "climate/other-weather" if re.search(r"hottest|rain|snow|hurricane|precip|anomal|warmest|earthquake", t, re.I) else "other"
    cat[k] += usd(r); ev[re.sub(r"\d+", "#", t)[:70]] += usd(r)
print("by side $:", {k: round(v) for k,v in side.items()})
print("by side/price $:"); [print("   ", k, round(v)) for k,v in sorted(pb.items(), key=lambda x:-x[1])]
print("by category $:", {k: round(v) for k,v in cat.items()})
print("top title patterns:"); [print("   ", round(v), k) for k,v in ev.most_common(12)]
