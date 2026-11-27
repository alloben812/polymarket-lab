import json, sys, time, collections, statistics
from concurrent.futures import ThreadPoolExecutor
from pmlab import dataapi
from subfam import subfam
L = json.load(open("leaders.json"))
rows = L if isinstance(L, list) else L.get("rows") or L.get("accounts")
now = int(time.time()); start = now - 3 * 86400
def scr(r):
    w = r["wallet"]
    if not ((r.get("mkts") or 0) >= 150 or (r.get("fills") or 0) >= 1500):
        return None
    try:
        f = list(dataapi.iter_trades(user=w, start=start, end=now, taker_only=False, max_rows=4000))
    except Exception as e:
        return dict(name=r["name"], err=str(e)[:60])
    usd = collections.Counter(); tot = 0; mk = set(); pr = []; buy = 0
    for x in f:
        u = float(x["size"]) * float(x["price"]); sf = subfam(x.get("slug"), x.get("title"))
        usd[sf] += u; tot += u; mk.add(x["condition_id"]); pr.append(float(x["price"])); buy += u if x["side"] == "BUY" else 0
    span = (max(x["timestamp"] for x in f) - min(x["timestamp"] for x in f)) / 3600 if f else 0
    top = ", ".join(f"{k} {v/tot:.0%}" for k, v in usd.most_common(5)) if tot else ""
    return dict(name=r["name"], wallet=w, n=len(f), span_h=round(span, 1), usd=round(tot), mk=len(mk), medp=round(statistics.median(pr), 3) if pr else None,
                buy=round(buy / tot, 2) if tot else None, top=top, kept=r.get("kept_all"), reb=r.get("rebates_all"), months=r.get("months"),
                fam={k: round(v) for k, v in usd.items()})
with ThreadPoolExecutor(6) as ex:
    out = [o for o in ex.map(scr, rows) if o]
json.dump(out, open("screen.json", "w"), indent=0)
for o in out:
    if "err" in o: print(o); continue
    ms = " ".join(f"{k[-2:]}:{v/1000:+.0f}K" for k, v in (o["months"] or []))
    rb = (o["reb"] or 0) / o["kept"] if o.get("kept") and o["kept"] > 0 else float("nan")
    print(f"{o['name'][:22]:22} n={o['n']:5} span={o['span_h']:5}h usd={o['usd']:9,} mk={o['mk']:5} medp={o['medp']} buy={o['buy']} kept={o['kept'] or 0:11,.0f} reb={rb:5.0%} [{ms}] | {o['top']}")
