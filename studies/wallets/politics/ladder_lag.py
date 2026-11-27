"""EXPLORATORY (not pre-registered): when one market of an event jumps, how long until its sibling markets jump, and
what could still be traded in the sibling in between?  Uses every cached tape; jump = >= 8 c within 120 s, as jumps.py."""
import bisect, collections, glob, json, os, statistics as st, time
base = '/home/user/polymarket-lab/data/politics_wallets/'; meta = {}; ev_of = {}
for f in glob.glob('*.json'):
    try: d = json.load(open(f))
    except Exception: continue
    if isinstance(d, dict) and '_markets' in d:
        for m in d['_markets']: meta[m['condition']] = m
for f in glob.glob(base + '*.fills.json'):
    for r in json.load(open(f)): ev_of[r['condition_id']] = r['event_slug']
J = collections.defaultdict(list); ser = {}
for p in glob.glob(base + 'tapes/*.json'):
    c = os.path.basename(p)[:-5]; tp = json.load(open(p))
    if len(tp) < 50 or c not in ev_of: continue
    s = [(t, (px if oi == 0 else 1 - px), sz) for t, sd, oi, px, sz, w in tp]; ts = [x[0] for x in s]; ser[c] = (ts, s); i = 1; last = 0
    while i < len(s):
        t = s[i][0]; pre = s[i - 1][1]
        if abs(s[i][1] - pre) >= 0.02 and t - last > 1800:
            k5 = bisect.bisect_right(ts, t + 300) - 1; j = bisect.bisect_right(ts, t + 120) - 1
            ext = max((x[1] for x in s[i:j + 1]), key=lambda v: abs(v - pre)); l5 = s[k5][1]
            if abs(ext - pre) >= 0.08 and abs(l5 - pre) >= 0.048 and (l5 - pre) * (ext - pre) > 0: J[ev_of[c]].append((t, c, pre, l5)); last = t
        i += 1
lags = []; rows = []
for e, js in J.items():
    js.sort(); used = set()
    for a in range(len(js)):
        if a in used: continue
        grp = [js[a]]; used.add(a)
        for b in range(a + 1, len(js)):
            if js[b][0] - js[a][0] <= 300 and js[b][1] not in {g[1] for g in grp}: grp.append(js[b]); used.add(b)
        if len(grp) < 2: continue
        t0 = grp[0][0]
        for t, c, pre, l5 in grp[1:]:
            ts, s = ser[c]; lo = bisect.bisect_left(ts, t0 + 3); hi = bisect.bisect_left(ts, t)
            stale = [x for x in s[lo:hi] if abs(x[1] - pre) < 0.02]          # prints at the OLD level after the leader moved
            d = 1 if l5 > pre else -1
            val = sum(x[2] * d * (l5 - x[1]) for x in stale)
            lags.append(t - t0); rows.append((e, t0, c, t - t0, pre, l5, len(stale), sum(x[2] for x in stale), val))
print(f"events with a multi-leg jump cluster: {len({r[0] for r in rows})}; follower legs: {len(rows)}")
if lags:
    q = sorted(lags); print(f"  lag leader -> follower leg (s): p10 {q[len(q) // 10]}, median {st.median(q)}, p90 {q[9 * len(q) // 10]};  followers lagging >= 5 s: {sum(1 for x in q if x >= 5)}, >= 30 s: {sum(1 for x in q if x >= 30)}")
    print(f"  follower legs with at least one print at the OLD level after the leader moved (+3 s): {sum(1 for r in rows if r[6])}; shares printed stale {sum(r[7] for r in rows):,.0f}; value vs level 5 min later ${sum(r[8] for r in rows):,.0f}")
    for r in sorted(rows, key=lambda r: -abs(r[8]))[:14]:
        print(f"   {time.strftime('%m-%d %H:%M:%S', time.gmtime(r[1]))} {meta[r[2]]['slug'][:56]:56} lag {r[3]:4d} s  {r[4]:.2f}->{r[5]:.2f}  stale prints {r[6]:3d} ({r[7]:7.0f} sh) value ${r[8]:+7.0f}")
