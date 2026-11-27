"""Audit a3: (1) hourly up/down markets per day in the universe (did the series continue after 18 Nov?);
(2) crypto markets with NO 5-minute entry: did the favourite cross [0.95,0.98) between snapshots, and did it lose?"""
import gzip, json, pickle, re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
D = Path("/home/user/polymarket-lab/data/gaps_resolution_bonds"); OUT = Path(__file__).resolve().parent
def T(s):
    s = str(s).replace(" ", "T")
    if s.endswith("Z"): s = s[:-1] + "+00:00"
    if s.endswith("+00"): s += ":00"
    d = datetime.fromisoformat(s); return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()
day = lambda t: datetime.fromtimestamp(t, tz=timezone.utc).strftime("%m-%d")
uni = [json.loads(l) for l in gzip.open(D / "universe.jsonl.gz", "rt")]
cr = [m for m in uni if m["family"] == "crypto"]
hr = [m for m in cr if re.search(r"up-or-down-(october|november)-\d+-2026-\d+(am|pm)-et", m["slug"])]
c = Counter(day(T(m["endDate"])) for m in hr)
print("hourly up/down in universe by endDate day:", sorted(c.items()))
print("hourly vol quantiles:", sorted(m["volumeNum"] for m in hr)[::60])
# listing day files: were hourly markets listed with low volume? check listing_days raw
import os
ld = sorted(os.listdir(D / "listing_days"))
print("listing files", len(ld), ld[:2])
ent = {e["cid"] for e in pickle.load(open(OUT / "a1_entries.pkl", "rb"))}
res = json.load(open(D / "resolutions.json")); res.update(json.load(open(D / "ext/resolutions.json")))
by = {m["conditionId"]: m for m in cr}
noentry = []
for path in (D / "hist.jsonl.gz", D / "ext/hist.jsonl.gz"):
    for line in gzip.open(path, "rt"):
        h = json.loads(line)
        m = by.get(h["cid"])
        if m is None or h["cid"] in ent or not h["h"] or h.get("err") or h.get("skip"): continue
        end, closed = T(m["endDate"]), T(m["closedTime"])
        hh = h["h"][0] if isinstance(h["h"][0][0], list) else h["h"]
        pts = sorted((t, p) for t, p, rs in hh if rs == 300 and end - 3600 <= t < closed)
        r = res.get(h["cid"]); pay0 = r["final"].get(m["outcomes"][0]) if r and r.get("resolved") else None
        if not pts or pay0 is None: continue
        fav = [max(p, 1 - p) for _, p in pts]
        # max mid of the eventual loser in window
        los = [p if pay0 < 1 else 1 - p for _, p in pts]
        noentry.append(dict(cid=h["cid"], slug=m["slug"], lost_max=max(los), fav_max=max(fav), fav_min=min(fav), n=len(pts), end=end, closed=closed,
                            crossed=any(a < 0.95 and b >= 0.98 or a >= 0.98 and b < 0.95 for a, b in zip(fav, fav[1:]))))
print("crypto markets in window without entry:", len(noentry))
print(" whose favourite crossed the range between snapshots:", sum(x["crossed"] for x in noentry))
cand = [x for x in noentry if x["lost_max"] >= 0.85]
print(" eventual loser had mid >= 0.85 in window:", len(cand))
for x in sorted(cand, key=lambda x: -x["lost_max"]): print("  ", x["slug"], round(x["lost_max"], 3), "n", x["n"], "crossed", x["crossed"])
pickle.dump(cand, open(OUT / "a3_noentry_losers.pkl", "wb"))
