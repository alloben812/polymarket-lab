"""m3: survey of all open markets: taker delay (gamma secondsDelay), fee type and rate, 24 h volume.
Also samples the CLOB `clob-markets/{condition_id}` record (field `itode` = crypto/finance taker delay per docs).
Output: out/m3_markets.jsonl.gz, out/m3_summary.txt. Public data only.
Run: python3 -I m3_delays.py
"""
import gzip, json, os, time, urllib.request, collections, random

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
UA = {"User-Agent": "pm-research/0.1"}


def get(url):
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return json.loads(r.read())
        except Exception as ex:
            time.sleep(1 + i)
    raise RuntimeError(url)


def main():
    path = os.path.join(OUT, "m3_markets.jsonl.gz")
    rows = []
    cur = None
    while True:
        u = "https://gamma-api.polymarket.com/markets/keyset?closed=false&limit=500"
        dd = get(u + (f"&after_cursor={cur}" if cur else ""))
        d = dd.get("markets") or []
        for m in d:
            ev = (m.get("events") or [{}])[0]
            rows.append({"cid": m.get("conditionId"), "slug": m.get("slug"), "q": m.get("question", "")[:90],
                         "fee": m.get("feeType"), "rate": (m.get("feeSchedule") or {}).get("rate"),
                         "sd": m.get("secondsDelay", "ABSENT"), "v24": float(m.get("volume24hr") or 0),
                         "acc": m.get("acceptingOrders"), "series": ev.get("seriesSlug") or ev.get("ticker", "")[:40],
                         "start": m.get("gameStartTime") or m.get("eventStartTime")})
        cur = dd.get("next_cursor")
        if not d or not cur or len(rows) > 300000:
            break
        time.sleep(0.15)
    with gzip.open(path, "wt") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    agg = collections.defaultdict(lambda: collections.Counter())
    vol = collections.defaultdict(float)
    volsd = collections.defaultdict(float)
    rates = collections.defaultdict(collections.Counter)
    for r in rows:
        k = r["fee"] or "None"
        agg[k][str(r["sd"])] += 1
        vol[k] += r["v24"]
        volsd[(k, str(r["sd"]))] += r["v24"]
        rates[k][r["rate"]] += 1
    lines = [f"open markets: {len(rows)}  fetched {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}",
             "feeType | markets | secondsDelay counts | 24h volume $ | 24h volume by delay | rates"]
    for k in sorted(agg, key=lambda k: -vol[k]):
        byd = {d: round(volsd[(k, d)]) for d in agg[k]}
        lines.append(f"{k} | {sum(agg[k].values())} | {dict(agg[k])} | {vol[k]:,.0f} | {byd} | {dict(rates[k])}")
    # CLOB record sample: itode flag
    random.seed(1)
    samp = collections.defaultdict(list)
    for r in sorted(rows, key=lambda r: -r["v24"]):
        k = r["fee"] or "None"
        if len(samp[k]) < 6 and r["cid"]:
            samp[k].append(r)
    lines.append("\nCLOB clob-markets sample (itode = taker delay flag per docs; other delay-like keys shown)")
    for k, lst in samp.items():
        for r in lst:
            try:
                c = get(f"https://clob.polymarket.com/clob-markets/{r['cid']}")
                keys = {kk: c[kk] for kk in c if any(s in kk.lower() for s in ("itode", "delay", "sd", "fd", "mts", "mos"))}
                lines.append(f"{k} | {r['slug'][:60]} | sd={r['sd']} | {keys}")
            except Exception as ex:
                lines.append(f"{k} | {r['slug'][:60]} | err {ex}")
            time.sleep(0.1)
    open(os.path.join(OUT, "m3_summary.txt"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
