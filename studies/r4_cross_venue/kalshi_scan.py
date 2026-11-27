"""Page through Kalshi open events (nested markets) and rank by 24h volume. Read-only public API."""
import json, sys, time, urllib.request, collections
K = "https://api.elections.kalshi.com/trade-api/v2"
def get(url):
    for i in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}), timeout=60) as r:
                return json.loads(r.read())
        except Exception as e:
            time.sleep(1.5 * (i + 1)); last = e
    raise SystemExit(str(last))
cur = ""; evs = []; pages = 0
while pages < int(sys.argv[1]) :
    d = get(f"{K}/events?status=open&with_nested_markets=true&limit=200" + (f"&cursor={cur}" if cur else ""))
    evs += d.get("events", []); cur = d.get("cursor") or ""; pages += 1
    if not cur: break
    time.sleep(0.15)
json.dump(evs, open("/home/user/polymarket-lab/data/r4/kalshi_open_events.json", "w"))
rows = []
for e in evs:
    ms = e.get("markets") or []
    v24 = sum(float(m.get("volume_24h_fp") or 0) for m in ms); oi = sum(float(m.get("open_interest_fp") or 0) for m in ms)
    rows.append((v24, oi, e["event_ticker"], e.get("series_ticker"), e.get("category"), e.get("title"), len(ms)))
rows.sort(reverse=True)
print("pages", pages, "events", len(evs), "cursor_left", bool(cur))
cat = collections.Counter()
for r in rows: cat[r[4]] += r[0]
print("24h contracts by category:", {k: int(v) for k, v in cat.most_common()})
for r in rows[:int(sys.argv[2])]:
    print(f"{int(r[0]):>10} oi={int(r[1]):>10} {r[2]:<34} {r[4]:<12} n={r[6]:<3} {r[5][:70]}")
