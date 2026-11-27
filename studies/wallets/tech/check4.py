"""(a) how long the stale price survives after fountaim / lamyk hit it, by deciding source; (b) what else fountaim snipes;
(c) calibration of taker buys per account in resolved tech markets; (d) size of the debut universe seen in the cache."""
import bisect, collections, statistics as st
from common import *
from race import INFO, JUMP, APP, groups, appearance, pw_rows, check_time, tape
ev_markets = collections.defaultdict(list)
for c in INFO: ev_markets[INFO[c]["event"]].append(c)
print("(a) seconds from the account's sniping fill to the next OTHER wallet's taker buy of the winner in the same event (cached siblings)")
for name in ("fountaim", "lamyk"):
    d = load(name); bym = {m["condition"]: m for m in d["_markets"]}; res = collections.defaultdict(list); seen = set()
    for r in sorted(d["_fills"], key=lambda r: r["timestamp"]):
        c = r["condition_id"]
        if c not in JUMP or r["side"] != "BUY" or r["role"] != "T" or "debut" not in (bym[c]["event"] or "") or float(r["price"]) >= 0.97: continue
        chk = check_time(bym[c]["closed_at"]); t = r["timestamp"]
        if not (chk - 40 * 3600 <= t <= chk) or r["outcome"] != INFO[c]["winner"]: continue
        key = (bym[c]["event"], t // 60)
        if key in seen: continue
        seen.add(key)
        before = [x[0] for cc in ev_markets[bym[c]["event"]] for x in pw_rows(cc) if x[4] and x[3] != ACC[name] and t - 600 <= x[0] < t - 3]
        nxt = sorted(x[0] for cc in ev_markets[bym[c]["event"]] for x in pw_rows(cc) if x[4] and x[3] != ACC[name] and x[0] >= t - 3)
        src = "hle (agi.safe.ai)" if "hle" in bym[c]["event"] else "arena.ai"
        res[src].append((nxt[0] - t if nxt else None, len(before), fs(t), bym[c]["event"][:40]))
    for src, xs in res.items():
        print(f"   {name} {src}: {len(xs)} sweeps; others already buying in the 10 min before: {sum(1 for x in xs if x[1] > 0)}; next other buyer after (s): " + ", ".join(f"{x[0] if x[0] is not None else 'none'}" for x in xs))
print("\n(b) fountaim outside debut markets: events by turnover (88 d)")
d = load("fountaim"); ev = collections.defaultdict(lambda: [0.0, 0.0, 0, set()])
for m in d["_markets"]:
    if "debut" in (m["event"] or ""): continue
    k = re.sub(r"-20\d{6,}.*$|-(on|by|in)-(january|february|march|april|may|june|july|august|september|october|november|december).*$|-(september|october|november|december)(-\d+)?(-20\d\d)?$", "", m["event"] or ""); e = ev[(m["sub"], k)]
    e[0] += m["turnover"]; e[1] += m.get("net") or 0; e[2] += 1; e[3].update(m["tags"][:3])
for (s, k), e in sorted(ev.items(), key=lambda x: -x[1][0])[:16]: print(f"   {e[0]:7.0f} net {e[1]:6.0f} mk {e[2]:3d} [{s}] {k[:70]}")
print("\n(c) taker BUY fills in resolved tech markets (all sub-families): $-weighted win rate by price bucket (clustered unit = market; n markets shown)")
bk = [(0, .2), (.2, .5), (.5, .8), (.8, .9), (.9, .95), (.95, .98), (.98, 1.01)]
print(f"   {'account':14} " + " ".join(f"{lo:.2f}-{min(hi,1):.2f}".rjust(22) for lo, hi in bk))
for name in ACC:
    d = load(name); bym = {m["condition"]: m for m in d["_markets"]}; a = collections.defaultdict(lambda: [0.0, 0.0, 0.0, set()])
    for r in d["_fills"]:
        m = bym[r["condition_id"]]
        if not (m["tech"] and m["resolved"] and r["side"] == "BUY" and r["role"] == "T"): continue
        p, s = float(r["price"]), float(r["size"]); val = float((m.get("final") or {}).get(r["outcome"]) or 0)
        for lo, hi in bk:
            if lo <= p < hi: x = a[(lo, hi)]; x[0] += s * p; x[1] += s * val; x[2] += s; x[3].add(m["condition"])
    print(f"   {name:14} " + " ".join((f"px{a[b][0]/a[b][2]:.2f} win{a[b][1]/a[b][2]:.2f} n{len(a[b][3])}" if a[b][2] else "-").rjust(22) for b in bk))
print("\n(d) debut universe in the tape cache")
dv = collections.defaultdict(lambda: [0, 0.0])
for c, i in INFO.items():
    if "debut" in (i["event"] or ""):
        mth = dt.datetime.fromtimestamp(i["closed"], dt.timezone.utc).strftime("%Y-%m"); dv[mth][0] += 1; dv[mth][1] += i["vol"]
print("   " + " | ".join(f"{k}: {v[0]} markets, volume ${v[1]:.0f}" for k, v in sorted(dv.items())), f"| event groups with a detected sweep: {sum(1 for v in APP.values() if v)} of {len(APP)}")
vols = sorted(i["vol"] for i in INFO.values() if "debut" in (i["event"] or ""))
print(f"   debut market volume q25/q50/q75/max: {vols[len(vols)//4]:.0f}/{vols[len(vols)//2]:.0f}/{vols[3*len(vols)//4]:.0f}/{vols[-1]:.0f}")
