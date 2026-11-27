import json, time, urllib.request, gzip, sys
K = "https://api.elections.kalshi.com/trade-api/v2"; G = "https://gamma-api.polymarket.com"; C = "https://clob.polymarket.com"
def get(url, data=None, timeout=8):
    h = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}; body = None
    if data is not None: body = json.dumps(data).encode(); h["Content-Type"] = "application/json"
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=h), timeout=timeout) as r: return json.loads(r.read())
out = open("/home/user/polymarket-lab/data/r4/poll15m.jsonl", "a"); end = time.time() + float(sys.argv[1]); cur = None
while time.time() < end:
    try:
        t0 = int(time.time() // 900 * 900)
        if cur is None or cur["t0"] != t0:
            ev = get(f"{G}/events?slug=btc-updown-15m-{t0}")[0]; m = ev["markets"][0]
            ks = [x for x in get(f"{K}/markets?series_ticker=KXBTC15M&status=open&limit=5")["markets"]]
            ks = sorted(ks, key=lambda x: x["close_time"])
            cur = {"t0": t0, "tok": json.loads(m["clobTokenIds"]), "outs": json.loads(m["outcomes"]), "ptb": (ev.get("eventMetadata") or {}).get("priceToBeat"), "k": ks[0]["ticker"], "k_close": ks[0]["close_time"], "k_title": ks[0].get("yes_sub_title"), "k_strike": ks[0].get("floor_strike")}
            out.write(json.dumps({"meta": cur}) + "\n")
        ta = time.time(); b = get(f"{C}/books", [{"token_id": cur["tok"][0]}])[0]; tb = time.time()
        km = get(f"{K}/markets/{cur['k']}")["market"]; tc = time.time()
        try: cb = float(get("https://api.exchange.coinbase.com/products/BTC-USD/ticker")["price"])
        except Exception: cb = None
        bids = [float(x["price"]) for x in b.get("bids") or []]; asks = [float(x["price"]) for x in b.get("asks") or []]
        out.write(json.dumps({"t_pm": (ta + tb) / 2, "t_k": (tb + tc) / 2, "t0": t0, "pm_bid": max(bids) if bids else None, "pm_ask": min(asks) if asks else None,
                              "k_bid": float(km["yes_bid_dollars"]), "k_ask": float(km["yes_ask_dollars"]), "k": cur["k"], "cb": cb}) + "\n"); out.flush()
    except Exception as e:
        out.write(json.dumps({"err": str(e)[:200], "t": time.time()}) + "\n"); out.flush()
    time.sleep(2.0)
