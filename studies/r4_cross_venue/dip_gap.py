import json, time, urllib.request, urllib.error, statistics as st, collections, sys, math
import pmlab.dataapi as da
sys.argv = ["x", "a", "b"]
K = "https://api.elections.kalshi.com/trade-api/v2"; G = "https://gamma-api.polymarket.com"
def get(u, tries=7):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}), timeout=40) as r: return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503): time.sleep(3 + 3 * i); continue
            return {"_err": e.code}
        except Exception: time.sleep(2)
    return {"_err": "retries"}
now = int(time.time()); s0 = now - 30 * 86400
ev = get(f"{G}/events?slug=what-price-will-bitcoin-hit-before-2027")[0]
for strike in (55000, 50000, 45000, 40000):
    m = next(x for x in ev["markets"] if x.get("groupItemTitle") == f"↓ {strike:,}"); tok = json.loads(m["clobTokenIds"])[0]
    ph = da.prices_history(tok, s0, s0 + 15 * 86400 - 60, 1800) + da.prices_history(tok, s0 + 15 * 86400, now, 1800); pser = {}
    for r in ph: pser[int(r["timestamp"]) // 3600 * 3600] = float(r["price"])
    c = get(f"{K}/series/KXBTCMINY/markets/KXBTCMINY-27JAN01-{strike}.00/candlesticks?start_ts={s0}&end_ts={now}&period_interval=60"); kser = {}
    for x in c.get("candlesticks") or []:
        b = (x.get("yes_bid") or {}).get("close_dollars"); a = (x.get("yes_ask") or {}).get("close_dollars")
        if b is not None and a is not None and float(a) - float(b) <= 0.05: kser[(int(x["end_period_ts"]) - 1) // 3600 * 3600] = (float(a) + float(b)) / 2
    ts = sorted(set(pser) & set(kser)); d = [(t, kser[t] - pser[t]) for t in ts]
    if not d: print(strike, "no overlap", len(pser), len(kser), c.get("_err")); continue
    wk = collections.defaultdict(list)
    for t, x in d: wk[(now - t) // (7 * 86400)].append(x)
    print(f"dip to {strike}: hours {len(d)}  K-PM mean {st.mean(x for _, x in d):+.4f} median {st.median(x for _, x in d):+.4f}  share>0.02: {sum(x > 0.02 for _, x in d)/len(d):.2f} share<0: {sum(x < 0 for _, x in d)/len(d):.2f} | by week (0=latest): " + " ".join(f"w{w}:{st.mean(v):+.3f}" for w, v in sorted(wk.items())) + f" | PM now {pser[ts[-1]]:.3f} K now {kser[ts[-1]]:.3f}")
    time.sleep(1.5)
# Kalshi REST staleness check on the live 15m market: /markets quote vs /orderbook
ms = sorted(get(f"{K}/markets?series_ticker=KXBTC15M&status=open&limit=5")["markets"], key=lambda x: x["close_time"])
if ms:
    t = ms[0]["ticker"]; diffs = []
    for i in range(6):
        q = get(f"{K}/markets/{t}").get("market", {}); ob = get(f"{K}/markets/{t}/orderbook?depth=1").get("orderbook_fp", {})
        yb = max([float(p) for p, _ in ob.get("yes_dollars") or [[0, 0]]]); nb = max([float(p) for p, _ in ob.get("no_dollars") or [[0, 0]]])
        diffs.append((q.get("yes_bid_dollars"), q.get("yes_ask_dollars"), yb, round(1 - nb, 2), q.get("updated_time", "")[-15:])); time.sleep(2.5)
    print("Kalshi", t, "(/markets bid, ask, /orderbook bid, ask, updated_time):", diffs)
