"""Step 2: reward-universe table (as-of), gamma metadata (local day, station, close time, tokens) and settlement.

Outputs under data/gaps_weather_rewards/: universe.parquet (snapshot rows), meta.json (per condition).
Run: python3 s2_meta.py   (reads only our own filtered parquet + public APIs)
"""
import glob, json, os, re, sys
import pandas as pd, pyarrow.parquet as pq
from pmlab import gamma, dataapi

HX = "/home/user/polymarket-lab/data/datasets/houroux_weather"
OUT = "/home/user/polymarket-lab/data/gaps_weather_rewards"
os.makedirs(OUT, exist_ok=True)

cols = ["discovery_sequence", "received_at_ns", "condition_id", "market_slug", "event_slug", "group_item_title", "token_id",
        "outcome", "daily_reward", "rewards_max_spread_cents", "rewards_min_size", "end_date"]
u = pd.concat([pq.read_table(f, columns=cols).to_pandas() for f in sorted(glob.glob(HX + "/marketsfull_*.parquet"))])
u = u[u.market_slug.str.startswith("highest-temperature-in-")]
tok = u.drop_duplicates(["condition_id", "outcome"]).pivot(index="condition_id", columns="outcome", values="token_id")
snap = u.drop_duplicates(["discovery_sequence", "condition_id"])[["discovery_sequence", "received_at_ns", "condition_id", "daily_reward",
                                                                  "rewards_max_spread_cents", "rewards_min_size"]]
# one receive time per snapshot (the earliest row time of the snapshot is not used: the as-of time is the latest row)
snap_t = u.groupby("discovery_sequence").received_at_ns.max().rename("snap_ns")
all_snaps = pd.concat([pq.read_table(f, columns=["discovery_sequence", "received_at_ns"]).to_pandas() for f in sorted(glob.glob(HX + "/marketsfull_*.parquet"))])
snap = snap.merge(snap_t, on="discovery_sequence")
snap.to_parquet(OUT + "/universe.parquet", index=False)
print("snapshots with temperature rows", snap.discovery_sequence.nunique(), "conditions", snap.condition_id.nunique())

conds = sorted(snap.condition_id.unique())
info = u.drop_duplicates("condition_id").set_index("condition_id")
gm = gamma.markets_by_condition(conds, cache=True)
print("gamma metadata for", len(gm), "of", len(conds))
res = dataapi.resolutions(conds)
print("resolutions for", len(res))
meta = {}
for c in conds:
    g = gm.get(c) or {}
    r = res.get(c) or {}
    ev = info.loc[c, "event_slug"]
    m = re.match(r"^highest-temperature-in-(.+)-on-([a-z]+)-(\d{1,2})-(\d{4})$", ev)
    src = g.get("resolutionSource") or ""
    st = re.search(r"ids=([A-Za-z0-9]{4})", src) or re.search(r"site=([A-Za-z0-9]{4})", src) or re.search(r"/([A-Z]{4})(?:[/?]|$)", src)
    meta[c] = {
        "slug": info.loc[c, "market_slug"], "event": ev, "city": m.group(1) if m else None,
        "target": f"{m.group(4)}-{m.group(2)}-{int(m.group(3)):02d}" if m else None,
        "item": info.loc[c, "group_item_title"],
        "yes": tok.loc[c].get("Yes"), "no": tok.loc[c].get("No"),
        "est": g.get("eventStartTime") or g.get("gameStartTime"), "closed": g.get("closedTime"), "end": g.get("endDate"), "src": src,
        "station": st.group(1).upper() if st else None,
        "fee": (g.get("feeSchedule") or {}).get("rate"), "tick": g.get("orderPriceMinTickSize"),
        "resolved": r.get("resolved"), "final_yes": (r.get("final") or {}).get("Yes"),
        "desc": (g.get("description") or "")[:300],
    }
json.dump(meta, open(OUT + "/meta.json", "w"), indent=0)
import collections
print("stations", collections.Counter(v["station"] for v in meta.values()).most_common(60))
print("missing est", sum(1 for v in meta.values() if not v["est"]), "unresolved", sum(1 for v in meta.values() if not v["resolved"]),
      "final values", collections.Counter(v["final_yes"] for v in meta.values()))
