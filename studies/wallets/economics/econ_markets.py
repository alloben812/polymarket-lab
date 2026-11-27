"""Per account: economics markets in the 88-day window, grouped by a slug stem, with timing relative to the gamma end date."""
import json, re, sys, collections, datetime as dt
f = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%m-%d %H:%M") if t else "-"
for s in sys.argv[1:]:
    d = json.load(open(f"{s}_88d.json"))
    ms = [m for m in d["_markets"] if m["family"] == "economics"]
    print(f"\n=== {s}: {len(ms)} economics markets, turnover {sum(m['turnover'] for m in ms):.0f}")
    grp = collections.defaultdict(list)
    for m in ms:
        stem = re.sub(r"(-\d+(pt\d+)?(bps|k|pct)?)+$", "", re.sub(r"-\d{3}(-\d{3})*$", "", m["slug"] or "?"))
        stem = re.sub(r"(will-|-by-.*$)", "", stem)[:60]
        grp[stem].append(m)
    rows = sorted(grp.items(), key=lambda kv: -sum(m["turnover"] for m in kv[1]))
    for stem, g in rows[:int(18)]:
        to = sum(m["turnover"] for m in g); tk = sum(m["taker_usd"] for m in g)
        res = [m for m in g if m["resolved"] and not m["incomplete"]]
        net = sum(m["net"] for m in res)
        print(f"  {stem:60} n={len(g):3d} turn={to:9.0f} taker={tk/to if to else 0:4.2f} fills={sum(m['n_fills'] for m in g):5d} first={f(min(m['first_ts'] or 9e9 for m in g) if any(m['first_ts'] for m in g) else None)} last={f(max(m['last_ts'] or 0 for m in g))} end={f(g[0]['end'])} resolved={len(res)}/{len(g)} net={net:8.0f}")
