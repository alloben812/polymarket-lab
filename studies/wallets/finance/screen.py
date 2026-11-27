import json, sys, time, collections, statistics, re
from concurrent.futures import ThreadPoolExecutor
from pmlab import dataapi

def subfam(slug, title):
    s = (slug or "").lower(); t = (title or "").lower()
    if re.match(r"^(btc|eth|sol|xrp|doge|hype|bnb)-updown", s): return "crypto-updown"
    if re.search(r"bitcoin|ethereum|solana|xrp|dogecoin|\bbtc\b|\beth\b", t): return "crypto-other"
    if re.search(r"up or down", t): return "fin-updown"
    if re.search(r"(close|closes|finish|settle)\w* (above|below|at|over|under|between)|close above|closing price", t): return "fin-close"
    if re.search(r"earnings|eps|revenue|beat|guidance", t): return "fin-earnings"
    if re.search(r"\bipo\b|market cap|largest company", t): return "fin-ipo/cap"
    if re.search(r"\b(hit|reach|dip)\b", t) and re.search(r"\$|s&p|nasdaq|gold|oil|silver|nvda|tsla|stock", t): return "fin-hit"
    if re.search(r"s&p|nasdaq|dow|gold|silver|crude|oil|nvda|nvidia|tesla|tsla|aapl|apple|msft|amzn|googl|meta|stock|nikkei|dax|ftse|\(\w{1,5}\)", t): return "fin-other"
    return "non-fin"

if __name__ == "__main__":
    L = json.load(open("leaders.json"))
    rows = L if isinstance(L, list) else L.get("rows") or L.get("accounts")
    now = int(time.time()); start = now - 7 * 86400
    def scr(r):
        w = r["wallet"]
        if not ((r.get("mkts") or 0) >= 100 or (r.get("fills") or 0) >= 1000):
            return None
        try:
            f = list(dataapi.iter_trades(user=w, start=start, end=now, taker_only=False, max_rows=5000))
        except Exception as e:
            return dict(name=r["name"], err=str(e)[:60])
        usd = collections.Counter(); tot = 0; mk = set(); pr = []; buy = 0; ex = {}
        for x in f:
            u = float(x["size"]) * float(x["price"]); sf = subfam(x.get("slug"), x.get("title"))
            usd[sf] += u; tot += u; mk.add(x["condition_id"]); pr.append(float(x["price"])); buy += u if x["side"] == "BUY" else 0
            ex.setdefault(sf, x.get("title"))
        span = (max(x["timestamp"] for x in f) - min(x["timestamp"] for x in f)) / 3600 if f else 0
        top = ", ".join(f"{k} {v/tot:.0%}" for k, v in usd.most_common(5)) if tot else ""
        return dict(name=r["name"], wallet=w, n=len(f), span_h=round(span, 1), usd=round(tot), mk=len(mk), medp=round(statistics.median(pr), 3) if pr else None,
                    buy=round(buy / tot, 2) if tot else None, top=top, kept=r.get("kept_all"), reb=r.get("rebates_all"), months=r.get("months"),
                    fam={k: round(v) for k, v in usd.items()}, ex=ex)
    with ThreadPoolExecutor(6) as exr:
        out = [o for o in exr.map(scr, rows) if o]
    json.dump(out, open("screen.json", "w"), indent=0)
    for o in out:
        if "err" in o: print(o); continue
        ms = " ".join(f"{k[-2:]}:{v/1000:+.0f}K" for k, v in (o["months"] or []))
        rb = (o["reb"] or 0) / o["kept"] if o.get("kept") and o["kept"] > 0 else float("nan")
        print(f"{o['name'][:22]:22} n={o['n']:5} span={o['span_h']:5}h usd={o['usd']:9,} mk={o['mk']:5} medp={o['medp']} buy={o['buy']} kept={o['kept'] or 0:11,.0f} reb={rb:5.0%} [{ms}] | {o['top']}")
