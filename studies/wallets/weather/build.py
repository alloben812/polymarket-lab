"""Step 1: fetch labelled fills (14 d) for the chosen accounts + market metadata + resolutions. Writes out/fills.json, out/markets.json."""
import json, re, sys, time, datetime as dt
sys.path.insert(0, "/home/user/polymarket-lab")
from pmlab import wallet as W, gamma, dataapi

ACCTS = ["WrongBy1Degree", "OnlyLuckNoBrain", "241532532432", "haiwenxiang", "edgewarehouse", "Lex-tang", "HighTempTation"]
END = 1795793820 if False else int(dt.datetime(2026, 11, 27, 15, 37, tzinfo=dt.timezone.utc).timestamp())
START = END - 14 * 86400
fills = {}
for a in ACCTS:
    name, w = gamma.resolve_profile(a)
    f, trunc = W.fetch_fills(w, START, END, 60000)
    fills[a] = f
    print(a, len(f), "truncated" if trunc else "", min(r["timestamp"] for r in f), flush=True)
json.dump(fills, open("out/fills.json", "w"))
conds = sorted({r["condition_id"] for f in fills.values() for r in f})
print("conditions", len(conds), flush=True)
meta = gamma.markets_by_condition(conds)
res = dataapi.resolutions(conds)
out = {}
for c in conds:
    m = meta.get(c) or {}
    ev = (m.get("events") or [{}])[0]
    out[c] = dict(slug=m.get("slug"), event=ev.get("slug"), series=ev.get("seriesSlug"), q=m.get("question"), item=m.get("groupItemTitle"),
                  end=m.get("endDate"), est=m.get("eventStartTime"), start=m.get("startDate"), closed=m.get("closedTime"),
                  src=m.get("resolutionSource"), vol=m.get("volumeNum"), tokens=gamma.jfield(m.get("clobTokenIds")),
                  outcomes=gamma.jfield(m.get("outcomes")), fee=m.get("feeSchedule"), tags=gamma.tag_slugs(m) if m else [],
                  desc_head=(m.get("description") or "")[:400], res=res.get(c))
json.dump(out, open("out/markets.json", "w"))
print("meta", len(meta), "res", len(res))
