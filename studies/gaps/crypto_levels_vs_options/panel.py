"""Step 3: build the 5-minute panel (market x bucket) with spot, vols, model probabilities."""
import json, sys
import numpy as np, pandas as pd
from common import *

def build(grp):
    uni = [u for u in load_universe() if u["grp"] == grp]
    mins = {"BTC": Minute("BTCUSDT"), "ETH": Minute("ETHUSDT")}
    dv = {"BTC": Dvol("BTC"), "ETH": Dvol("ETH")}
    frames = []
    for mi, u in enumerate(uni):
        r = json.load(open(DATA / "ph" / f"{u['cond']}.json"))
        a = np.array([(x[0], x[1]) for x in r if x[2] == 300 and x[0] < u["T"]], dtype=float)
        if len(a) == 0: continue
        t = a[:, 0].astype(np.int64); pm = a[:, 1]
        M = mins[u["asset"]]
        S = M.spot(t); sa = dv[u["asset"]].at(t); sb = M.rv(t)
        tau = (u["T"] - t).astype(float)
        df = pd.DataFrame({"m": mi, "t": t, "pm": pm, "S": S, "sig_a": sa, "sig_b": sb, "tau": tau})
        if grp == "euro":
            df["pa"] = p_above(S, u["K"], sa, tau); df["pb"] = p_above(S, u["K"], sb, tau)
        else:
            # barrier: drop buckets at/after first hit since max(start, period start); period start = event start (00:00 ET)
            i0 = max(0, (max(u["start"], u["ev_start"]) - M.t0) // 60)
            i1 = min(M.n, (u["T"] - M.t0) // 60)
            if u["up"]: hit = np.where(M.high[i0:i1] >= u["K"])[0]
            else: hit = np.where(M.low[i0:i1] <= u["K"])[0]
            t_hit = M.t0 + (i0 + hit[0]) * 60 if len(hit) else None
            df["pa"] = p_touch(S, u["K"], sa, tau, u["up"]); df["pb"] = p_touch(S, u["K"], sb, tau, u["up"])
            beyond = (S >= u["K"]) if u["up"] else (S <= u["K"])
            keep = ~beyond
            if t_hit is not None: keep &= (t < t_hit)
            df = df[keep]
            u["t_hit"] = int(t_hit) if t_hit is not None else None
        frames.append(df)
    P = pd.concat(frames, ignore_index=True)
    meta = pd.DataFrame(uni); meta["m"] = range(len(uni))
    meta["period"] = np.where(meta["date"] <= TUNE_LAST, "tune", "report")
    meta["cluster"] = meta["asset"] + "_" + meta["date"]
    P.to_parquet(DATA / f"panel_{grp}.parquet"); meta.to_parquet(DATA / f"meta_{grp}.parquet")
    print(grp, len(P), "rows", P["m"].nunique(), "markets; NaN S", P.S.isna().sum(), "NaN sig_a", P.sig_a.isna().sum(), "NaN sig_b", P.sig_b.isna().sum())

if __name__ == "__main__":
    build(sys.argv[1])
