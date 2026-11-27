"""Audit a5: hourly BTC/ETH up/down outcomes in the universe vs Binance 1h klines (open of the hour ending at endDate
vs its close), as an independent check of the payoff data; only hours before the 18 Nov Chainlink switch."""
import gzip, json, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, "/home/user/polymarket-lab")
from pmlab.http import get_json
D = Path("/home/user/polymarket-lab/data/gaps_resolution_bonds")
def T(s):
    s = str(s).replace(" ", "T").replace("Z", "+00:00")
    if s.endswith("+00"): s += ":00"
    return datetime.fromisoformat(s).timestamp()
uni = [json.loads(l) for l in gzip.open(D / "universe.jsonl.gz", "rt")]
hr = [m for m in uni if "-up-or-down-" in m["slug"] and "-et" in m["slug"] and "-on-" not in m["slug"]]
K = {}
for sym in ("BTCUSDT", "ETHUSDT"):
    st = int(datetime(2026, 10, 19, tzinfo=timezone.utc).timestamp() * 1000)
    for _ in range(2):
        ks = get_json("https://data-api.binance.vision/api/v3/klines", {"symbol": sym, "interval": "1h", "startTime": st, "limit": 1000}, cache=True)
        for k in ks: K[(sym, k[0] // 1000)] = (float(k[1]), float(k[4]))
        if not ks: break
        st = ks[-1][0] + 3600000
agree = dis = miss = 0; bad = []
for m in hr:
    sym = "BTCUSDT" if m["slug"].startswith("bitcoin") else "ETHUSDT" if m["slug"].startswith("ethereum") else None
    end = T(m["endDate"])
    if sym is None or end > datetime(2026, 11, 18, tzinfo=timezone.utc).timestamp(): continue
    k = K.get((sym, int(end - 3600)))
    if not k: miss += 1; continue
    up = k[1] >= k[0]
    op = [float(x) for x in m["outcomePrices"]]
    won = m["outcomes"][op.index(max(op))]
    if (won == "Up") == up: agree += 1
    else: dis += 1; bad.append((m["slug"], won, k, round(100 * (k[1] - k[0]) / k[0], 4)))
print(f"hourly up/down checked vs Binance 1h: agree {agree}, disagree {dis}, no kline {miss}")
for b in bad: print("  ", b)
