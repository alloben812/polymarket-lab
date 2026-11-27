"""Step 2: market table. Applies the volume filter, verifies winners with dataapi.resolutions, drops markets closed before T."""
import gzip, json, calendar, time, re, collections
from pmlab import gamma, dataapi
import release_calendar as rc

D = "/home/user/polymarket-lab/data/gaps_econ"


def ts(s):
    s = (s or "").replace(" ", "T")[:19]
    return calendar.timegm(time.strptime(s, "%Y-%m-%dT%H:%M:%S")) if len(s) == 19 else None


ev = json.load(gzip.open(f"{D}/events_core.json.gz"))
rows, drops = [], collections.Counter()
drop_list = []
cand = []
for e in ev:
    r = rc.match(e["slug"])
    if not r:
        continue
    for m in e.get("markets") or []:
        vol = float(m.get("volumeNum") or 0)
        base = {"release": r["id"], "type": r["type"], "group": r["group"], "tier": r["tier"], "T": r["T"], "when": r["when"],
                "family_flag": r["flag"], "event": e["slug"], "slug": m.get("slug"), "cond": m.get("conditionId"),
                "title": m.get("groupItemTitle"), "question": m.get("question"), "vol": vol, "closed_ts": ts(m.get("closedTime")),
                "outcomes": gamma.jfield(m.get("outcomes")), "fee_field": (m.get("feeSchedule") or {}).get("rate"), "negRisk": bool(m.get("negRisk"))}
        if vol < 5000:
            drops["volume < 5,000"] += 1; continue
        if base["outcomes"] != ["Yes", "No"]:
            drops["not Yes/No"] += 1; drop_list.append((base["slug"], "not Yes/No")); continue
        if base["closed_ts"] is None or base["closed_ts"] <= r["T"]:
            drops["closed before the release"] += 1; drop_list.append((base["slug"], f"closed before the release ({m.get('closedTime')})")); continue
        cand.append(base)
res = dataapi.resolutions([c["cond"] for c in cand])
for c in cand:
    x = res.get(c["cond"])
    if not x or not x["resolved"]:
        drops["not resolved"] += 1; drop_list.append((c["slug"], "not resolved")); continue
    fin = {k: float(v) for k, v in x["final"].items() if v is not None}
    if sorted(fin.values()) != [0.0, 1.0] or set(fin) != {"Yes", "No"}:
        drops["resolution not 1/0"] += 1; drop_list.append((c["slug"], f"resolution {fin}")); continue
    c["winner"] = "Yes" if fin["Yes"] == 1.0 else "No"
    c["late_close"] = (c["closed_ts"] - c["T"]) > 6 * 3600
    c["flag"] = "; ".join(x for x in (c["family_flag"], "closed more than 6 h after the release" if c["late_close"] else "") if x)
    rows.append(c)
json.dump({"markets": rows, "drops": dict(drops), "drop_list": drop_list}, open(f"{D}/markets.json", "w"))
print("kept", len(rows), "markets in", len({r['release'] for r in rows}), "releases;", len({r['T'] for r in rows}), "release seconds")
print("drops", dict(drops))
for s, w in drop_list: print("  drop", s[:70], "|", w)
by = collections.Counter((r["type"]) for r in rows); print(by)
print("flagged", sum(1 for r in rows if r["flag"]), "late close", sum(1 for r in rows if r["late_close"]))
print("total volume kept", round(sum(r["vol"] for r in rows)))
