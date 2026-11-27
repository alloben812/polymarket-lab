"""Part 3: for the December release events now open on Polymarket: rules excerpt, fee, tick, min size, and one
snapshot of the books (depth within 10 cents of the best ask on each outcome token). Output: out/dec_books.json"""
import json, gzip, re, time
from pmlab import http

EV = ["jolts-job-openings-october-2026", "ism-manufacturing-pmi-november-2026", "november-unemployment-rate-2026",
      "how-many-jobs-added-in-november-2026", "fed-decision-in-december-20260729232808632",
      "how-many-dissent-at-the-december-fed-meeting-20260730000304473", "core-cpi-mom-november-2026",
      "core-cpi-yoy-november-2026", "november-inflation-us-annual", "november-inflation-us-monthly",
      "university-of-michigan-consumer-sentiment-december-2026", "core-pce-mom-november-2026", "core-pce-yoy-november-2026",
      "pce-mom-november-2026", "pce-yoy-november-2026", "canada-gdp-september-2026-mom", "november-2026-unemployment-rate-canada",
      "bank-of-canada-decision-in-december-20260908230600011", "ecb-interest-rates-december-2026", "bank-of-england-decision-in-december-2026",
      "swiss-national-bank-decision-in-december-2026", "reserve-bank-of-australia-decision-in-december-2026",
      "reserve-bank-of-new-zealand-decision-in-december-20260908230600001", "bank-of-mexico-decision-in-december-2026",
      "bank-of-russia-decision-in-december", "central-bank-of-chile-decision-in-december-2026", "us-gdp-growth-in-q4-2026",
      "price-of-dozen-eggs-in-november-2026", "november-inflation-canada-monthly-20261214"]
out = []
for slug in EV:
    try:
        es = http.get_json("https://gamma-api.polymarket.com/events", {"slug": slug})
    except Exception as ex:
        out.append({"slug": slug, "err": str(ex)[:100]}); continue
    if not es:
        out.append({"slug": slug, "err": "not found"}); continue
    e = es[0]
    ms = [m for m in e.get("markets", []) if not m.get("closed")]
    toks = []
    for m in ms:
        ids = json.loads(m.get("clobTokenIds") or "[]")
        toks += [(m, i, tid) for i, tid in enumerate(ids)]
    books = {}
    for k in range(0, len(toks), 20):
        chunk = toks[k:k + 20]
        r = http.get_json("https://clob.polymarket.com/books", data=[{"token_id": t[2]} for t in chunk])
        for b in r:
            books[b["asset_id"]] = b
        time.sleep(0.5)
    mk = []
    for m in ms:
        ids = json.loads(m.get("clobTokenIds") or "[]")
        row = {"q": (m.get("groupItemTitle") or m.get("question"))[:40], "vol": round(float(m.get("volumeNum") or 0)),
               "tick": m.get("orderPriceMinTickSize"), "min": m.get("orderMinSize"), "feeType": m.get("feeType"),
               "fee": m.get("feeSchedule"), "delay": m.get("secondsDelay"), "negRisk": m.get("negRisk")}
        for i, tid in enumerate(ids[:2]):
            b = books.get(tid)
            if not b:
                continue
            asks = sorted((float(a["price"]), float(a["size"])) for a in b.get("asks", []))
            bids = sorted(((float(a["price"]), float(a["size"])) for a in b.get("bids", [])), reverse=True)
            if asks:
                best = asks[0][0]
                row[f"ask{i}"] = best
                row[f"ask{i}_usd_within_10c"] = round(sum(p * s for p, s in asks if p <= best + 0.10), 1)
                row[f"ask{i}_usd_top"] = round(asks[0][0] * asks[0][1], 1)
                row[f"ask{i}_usd_below95"] = round(sum(p * s for p, s in asks if p < 0.95), 1)
                row[f"ask{i}_usd_20_95"] = round(sum(p * s for p, s in asks if 0.20 <= p < 0.95), 1)
            if bids:
                row[f"bid{i}"] = bids[0][0]
        mk.append(row)
    desc = (e.get("description") or (ms[0].get("description") if ms else "") or "")
    out.append({"slug": slug, "title": e.get("title"), "end": e.get("endDate"), "n_open": len(ms),
                "rules": re.sub(r"\s+", " ", desc)[:700], "markets": mk})
json.dump({"taken_utc": time.strftime("%Y-%m-%d %H:%M", time.gmtime()), "events": out},
          open("/home/user/polymarket-lab/studies/gaps/econ_release_sniper/out/dec_books.json", "w"), indent=0)
print(len(out))
