"""Step 5b (protocol 2.4, W6): Stavenson's own fills in the period (taker_only=false), saved compactly to
data/gaps_tennis_wo/stavenson_fills.json; then his maker dollars at 0.48-0.495 after t_50 in class A events, as a
share of the W6 pool measured from the tape in s4. Read-only public data."""
import json, collections
from pmlab import dataapi
from common import *

STAV = "0xf5fe759cece500f58a431ef8dacea321f6e3e23d"


def main():
    path = DATA / "stavenson_fills.json"
    if path.exists():
        rows = json.load(open(path))
    else:
        rows = []
        for r in dataapi.iter_trades(user=STAV, start=int(P0) - 86400, end=int(P1) + 86400, taker_only=False):
            rows.append({"t": r["timestamp"], "c": r.get("condition_id") or r.get("conditionId"), "s": r["side"], "o": r["outcome"],
                         "p": float(r["price"]), "z": float(r["size"]), "tx": r.get("transaction_hash")})
        json.dump(rows, open(path, "w"))
    taker = collections.Counter()
    for r in dataapi.iter_trades(user=STAV, start=int(P0) - 86400, end=int(P1) + 86400, taker_only=True) if not (DATA / "stavenson_taker.json").exists() else []:
        taker[(r.get("transaction_hash"), r["outcome"], float(r["price"]), float(r["size"]), r["timestamp"])] += 1
    if taker:
        json.dump([list(k) + [v] for k, v in taker.items()], open(DATA / "stavenson_taker.json", "w"))
    else:
        taker = collections.Counter({tuple(x[:5]): x[5] for x in json.load(open(DATA / "stavenson_taker.json"))})
    U = json.load(open(DATA / "universe.json"))
    EA = {o["slug"]: o for o in json.load(open(OUT / "events_A.json"))}
    cid2ev = {}
    for r in U["A"]:
        for m in r["markets"]:
            cid2ev[m["cid"]] = r["slug"]
    maker_usd = 0.0
    maker_ev = set()
    all_in_A = 0
    left = collections.Counter(taker)
    for r in rows:
        k = (r["tx"], r["o"], r["p"], r["z"], r["t"])
        is_taker = left[k] > 0
        if is_taker:
            left[k] -= 1
        ev = cid2ev.get(r["c"])
        if ev is None:
            continue
        all_in_A += 1
        o = EA[ev]
        if is_taker or r["s"] != "BUY" or o.get("t_50") is None:
            continue
        if o["t_50"] <= r["t"] - LAG <= o["closed"] and 0.48 - 1e-9 <= r["p"] <= 0.495 + 1e-9:
            maker_usd += r["z"] * r["p"]
            maker_ev.add(ev)
    print(f"Stavenson fills in the window {len(rows)}, of them in class A markets {all_in_A}; maker BUYs at 0.48-0.495 after t_50 in class A: "
          f"${maker_usd:,.0f} in {len(maker_ev)} events")


if __name__ == "__main__":
    main()
