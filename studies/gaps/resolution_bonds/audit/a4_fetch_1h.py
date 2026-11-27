"""Audit a4 (fetch): the hourly Up/Down markets the study's universe could not see after 18 Nov (renamed
`<asset>-updown-1h-<epoch>`, excluded by the `-updown-` filter). BTC and ETH, endDate 2026-11-18 .. 2026-11-27,
no volume filter. Saves gamma metadata, 300-s price history of token 0 and the whole tape, one file per market."""
import gzip, json, sys, time
from pathlib import Path
sys.path.insert(0, "/home/user/polymarket-lab")
from pmlab import gamma, dataapi
OUT = Path("/home/user/polymarket-lab/data/gaps_resolution_bonds/audit_1h")
ms = []
# slugs are <asset>-updown-1h-<epoch of the hour start>; walk them directly instead of listing every market
T0 = 1794960000  # 2026-11-18T00:00:00Z
T1 = 1795737600  # 2026-11-27T00:00:00Z
for st in range(T0 - 3600, T1 - 3600, 3600):
    for a in ("btc", "eth"):
        m = gamma.market_by_slug(f"{a}-updown-1h-{st}", cache=True)
        if m and m.get("closed"): ms.append(m)
print("markets", len(ms), flush=True)
json.dump(ms, open(OUT / "markets.json", "w"))
t0 = time.time()
for i, m in enumerate(ms):
    p = OUT / f"{m['conditionId']}.json.gz"
    if p.exists(): continue
    toks = gamma.jfield(m["clobTokenIds"])
    from datetime import datetime
    def T(s):
        s = s.replace(" ", "T").replace("Z", "+00:00")
        if s.endswith("+00"): s += ":00"
        return datetime.fromisoformat(s).timestamp()
    end = T(m["endDate"]); closed = T(m["closedTime"]) if m.get("closedTime") else end + 3600
    try:
        h = [[r["timestamp"], r["price"], r.get("resolution_seconds")] for r in dataapi.prices_history(toks[0], int(end - 4500), int(closed + 300), 300)]
        rows = [[r["timestamp"], r["side"], r["token_id"], r["price"], r["size"], r["proxy_wallet"]] for r in dataapi.iter_trades(condition=m["conditionId"], max_rows=60000)]
        err = None
    except Exception as e:  # noqa
        h, rows, err = [], [], repr(e)[:200]
    json.dump({"cid": m["conditionId"], "h": h, "rows": rows, "err": err, "capped": len(rows) >= 60000}, gzip.open(p, "wt"))
    if i % 25 == 0: print(i, len(ms), f"{time.time()-t0:.0f}s", flush=True)
print("done", flush=True)
