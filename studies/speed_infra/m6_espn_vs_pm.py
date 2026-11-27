"""m6: free ESPN scoreboard (polled every 2 s from this sandbox) versus the Polymarket tape, live games of 27 Nov 2026.

For every score change seen in out/m1_espn_*.jsonl: F = first poll that shows the new score (receive time),
F_prev = the poll before it (the change happened in (F_prev, F]). The game's Polymarket event is found by
public-search on the team names and the scheduled date; its moneyline market tape (data API, taker rows,
block time) is read. PM move = first print in [F-180, F+60] whose price differs from the last price before F-180
... more simply: from the median of prints in [F-240, F-120] by >= 0.03 on the first moneyline market. Lag reported
as F minus (block time - 2 s), 2.09 s being the median block lag measured in NOTES.md.
Positive lag = ESPN's free feed shows the score AFTER the market moved.
Run after the pollers end: python3 -I m6_espn_vs_pm.py
"""
import glob, json, os, statistics, sys, time, urllib.parse, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from pmlab import dataapi  # noqa: E402

UA = {"User-Agent": "pm-research/0.1"}


def gj(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return json.loads(r.read())


names = json.load(open(HERE / "out/m6_espn_names.json"))
for lg in ['soccer/all', 'hockey/nhl', 'football/college-football', 'basketball/mens-college-basketball']:
    try:
        d = gj(f"https://site.api.espn.com/apis/site/v2/sports/{lg}/scoreboard")
        for e in d["events"]:
            c = e["competitions"][0]
            names.setdefault(e["id"], {"lg": lg, "name": e.get("name"), "date": e.get("date"),
                                        "teams": [x["team"].get("displayName") for x in c["competitors"]]})
    except Exception:
        pass

changes = []  # (eid, F_prev, F, old, new, source file)
for f in glob.glob(str(HERE / "out/m1_espn_*.jsonl")):
    last = {}
    lastt = {}
    for line in open(f):
        r = json.loads(line)
        if "live" not in r:
            continue
        for eid, clock, per, sc in r["live"]:
            if eid in last and last[eid] != sc:
                changes.append((eid, lastt[eid], r["t1"], last[eid], sc, os.path.basename(f), clock, per))
            last[eid] = sc
            lastt[eid] = r["t1"]

pm_cache = {}


def pm_market(eid):
    if eid in pm_cache:
        return pm_cache[eid]
    n = names.get(eid)
    res = None
    if n:
        day = n["date"][:10]
        for q in [" ".join(t.split()[-1] for t in n["teams"]), " ".join(n["teams"])]:
            try:
                d = gj("https://gamma-api.polymarket.com/public-search?" + urllib.parse.urlencode({"q": q, "limit_per_type": 5}))
            except Exception:
                continue
            for e in d.get("events") or []:
                if day in (e.get("slug") or "") and e.get("markets"):
                    ms = e["markets"]
                    ml = [m for m in ms if m.get("slug") == e["slug"]] or ms[:1]
                    res = {"event": e["slug"], "cid": ml[0]["conditionId"], "q": ml[0].get("question")}
                    break
            if res:
                break
    pm_cache[eid] = res
    return res


tapes = {}
rows_out = []
for eid, fprev, F, old, new, src, clock, per in changes:
    m = pm_market(eid)
    if not m:
        rows_out.append({"eid": eid, "src": src, "name": names.get(eid, {}).get("name"), "pm": None})
        continue
    if m["cid"] not in tapes:
        tapes[m["cid"]] = sorted(((int(r["timestamp"]), float(r["price"]), r.get("outcome"), r.get("side"), float(r["size"]))
                                  for r in dataapi.iter_trades(condition=m["cid"])), key=lambda x: x[0])
        time.sleep(0.2)
    tp = tapes[m["cid"]]
    o0 = tp[0][2] if tp else None
    conv = lambda x: x[1] if x[2] == o0 else 1 - x[1]
    base = [conv(x) for x in tp if F - 240 <= x[0] - 2 <= F - 120]
    if not base:
        base = [conv(x) for x in tp if F - 600 <= x[0] - 2 <= F - 60]
    mv = None
    if base:
        b = statistics.median(base)
        for x in tp:
            if F - 180 <= x[0] - 2 <= F + 60 and abs(conv(x) - b) >= 0.03:
                mv = x[0] - 2
                break
    rows_out.append({"eid": eid, "src": src, "name": names.get(eid, {}).get("name"), "pm": m["event"], "old": old, "new": new,
                     "clock": clock, "per": per, "poll_gap": round(F - fprev, 1),
                     "lag_F_minus_pm_move": None if mv is None else round(F - mv, 1), "n_base": len(base)})

json.dump(rows_out, open(HERE / "out/m6_rows.json", "w"), indent=0)
lags = [r["lag_F_minus_pm_move"] for r in rows_out if r.get("lag_F_minus_pm_move") is not None]
by = {}
for r in rows_out:
    if r.get("lag_F_minus_pm_move") is not None:
        by.setdefault(r["src"], []).append(r["lag_F_minus_pm_move"])
L = [f"score changes seen {len(changes)}; matched to a PM event {sum(1 for r in rows_out if r.get('pm'))}; with a PM move "
     f">= 3c within [F-180, F+60] {len(lags)}"]
if lags:
    s = sorted(lags)
    L.append(f"ESPN first-seen minus PM first move, s: median {statistics.median(s):.1f}; p10 {s[int(.1*(len(s)-1))]:.1f}; "
             f"p90 {s[int(.9*(len(s)-1))]:.1f}; ESPN later than PM in {sum(1 for x in s if x > 0)} of {len(s)}")
for k, v in by.items():
    L.append(f"  {k}: n {len(v)} median {statistics.median(v):.1f} s, values {sorted(v)}")
open(HERE / "out/m6_summary.txt", "w").write("\n".join(L) + "\n")
print("\n".join(L))
