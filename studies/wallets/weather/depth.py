"""Book depth snapshot for open daily-temperature events (size available to a taker).  python3 depth.py"""
import json, sys, re, datetime as dt
sys.path.insert(0, "/home/user/polymarket-lab")
from pmlab import gamma
from pmlab.http import get_json
MK = json.load(open("out/mk.json"))
cities = sorted({re.sub(r"-on-november.*", "", d["event"]) for d in MK.values() if d["kind"] == "hi" and "november-27" in d["event"]})
pick = [c for c in cities if any(k in c for k in ("moscow", "nyc", "new-york", "london", "seoul", "dallas", "tokyo", "shanghai", "wellington"))][:8]
now = dt.datetime.now(dt.timezone.utc); print("snapshot", now.strftime("%Y-%m-%d %H:%M UTC"), "cities", len(cities))
tot = []
for c in pick:
    for day in ("28", "29"):
        ev = gamma.event_by_slug(f"{c}-on-november-{day}-2026")
        if not ev: continue
        ms = [m for m in ev["markets"] if not m.get("closed")]
        toks = [(m["groupItemTitle"], gamma.jfield(m["clobTokenIds"])) for m in ms]
        books = get_json("https://clob.polymarket.com/books", data=[{"token_id": t[1][0]} for t in toks], cache=False) if toks else []
        bk = {b["asset_id"]: b for b in books}
        est = ev["markets"][0].get("eventStartTime"); line = []; ev_ask = ev_bid = 0.0; sumask = 0.0
        for name, tk in toks:
            b = bk.get(tk[0]);
            if not b: continue
            bids = sorted(((float(x["price"]), float(x["size"])) for x in b.get("bids", [])), reverse=True); asks = sorted((float(x["price"]), float(x["size"])) for x in b.get("asks", []))
            if not bids or not asks: continue
            bb, ba = bids[0], asks[0]
            ask3 = sum(p * s for p, s in asks if p <= ba[0] + 0.03); bid3 = sum((1 - p) * s for p, s in bids if p >= bb[0] - 0.03)   # $ to buy YES / $ to buy NO within 3c
            sumask += ba[0]
            if 0.05 <= (bb[0] + ba[0]) / 2 <= 0.95:
                line.append(f"{name} {bb[0]:.2f}/{ba[0]:.2f} top {bb[1]:.0f}x{ba[1]:.0f} 3c$ YES {ask3:.0f} NO {bid3:.0f}"); ev_ask += ask3; ev_bid += bid3; tot.append((ba[0] - bb[0], ask3, bid3))
        print(f"\n{ev['slug'][23:]} (local day starts {est}) vol ${float(ev.get('volume') or 0):.0f}; sum of YES asks {sumask:.3f}; within 3c: buy-YES ${ev_ask:.0f}, buy-NO ${ev_bid:.0f}")
        for l in line: print("   " + l)
sp = sorted(t[0] for t in tot); a = sorted(t[1] for t in tot); b = sorted(t[2] for t in tot); n = len(tot)
print(f"\nactive buckets {n}: spread median {sp[n//2]:.3f} p90 {sp[int(.9*n)]:.3f}; $ within 3c of best ask (YES) median {a[n//2]:.0f}; $ to buy NO within 3c median {b[n//2]:.0f}")
