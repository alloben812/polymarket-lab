"""Protocol 4.11 check: prints of the PendulumFlow feed against the Data API tape, three markets, 2026-10-02 14:00-15:00 UTC.
Count, share volume and price agreement; Data API row time (block time) minus the WS match time.
Run: python3 s6_tapecheck.py   -> out/tapecheck.json"""
import json, numpy as np, pandas as pd, pyarrow.parquet as pq
from pmlab import dataapi
PF = "/home/user/polymarket-lab/data/datasets/pflow_weather"
RES = "/home/user/polymarket-lab/studies/gaps/weather_rewards_quoting/out"
t = pq.read_table(f"{PF}/flat_2026-10-02T14.parquet").to_pandas()
tr = t[t.event_type == "last_trade_price"].copy(); tr["market"] = tr.market.astype(str); tr["asset_id"] = tr.asset_id.astype(str)
out = {}
for c in tr.market.value_counts().index[:3]:
    w = tr[tr.market == c]
    a, z = 1790949600, 1790953200          # 2026-10-02 14:00 .. 15:00 UTC
    rows = list(dataapi.iter_trades(condition=c, start=a - 60, end=z + 60, taker_only=True))
    api = pd.DataFrame(rows)
    tcol = "timestamp" if "timestamp" in api else api.columns[0]
    api["t"] = api[tcol].astype(float)
    api_in = api[(api.t >= a + 3) & (api.t < z + 3)]
    # nearest-match: for each WS print, the API row of the same token, price and size with the smallest |dt|
    lag = []
    for r in w.itertuples():
        cand = api[(api["token_id"].astype(str) == r.asset_id) & (np.isclose(api["price"].astype(float), r.price)) & (np.isclose(api["size"].astype(float), r.size))] if "token_id" in api else api.iloc[0:0]
        if len(cand):
            d = cand.t.values - r.ts / 1000.0
            lag.append(float(d[np.argmin(np.abs(d))]))
    lag = np.array(lag)
    out[c] = dict(ws_prints=int(len(w)), ws_shares=float(w["size"].sum()), api_rows=int(len(api_in)),
                  api_shares=float(api_in["size"].astype(float).sum()) if "size" in api_in else None,
                  matched_by_token_price=int(len(lag)), lag_median_s=float(np.median(lag)) if len(lag) else None,
                  lag_p10_p90=[float(np.quantile(lag, .1)), float(np.quantile(lag, .9))] if len(lag) else None,
                  api_columns=list(api.columns)[:20])
    print(c, out[c], flush=True)
json.dump(out, open(f"{RES}/tapecheck.json", "w"), indent=1)
