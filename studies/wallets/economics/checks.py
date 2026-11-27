"""Falsification checks: (1) jozeslemsek penny round trips, (2) sniper fill lags, (3) Ahpo/ATCapital fills right after US releases in Fed markets,
(4) post-release 'carry' on determined winners at 0.95-0.999 until resolution."""
import json, sys, pickle, collections, calendar, time, re, bisect, statistics as st, datetime as dt, os
f = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%m-%d %H:%M:%S")
P = "/home/user/polymarket-lab/data/econ_tapes"
src = open("release_analysis_v2.py").read(); ns = {}
exec("import calendar, time\ndef ts(s): return calendar.timegm(time.strptime(s, '%Y-%m-%d %H:%M'))\n" + src[src.index("SCHED = ["):src.index("OVERRIDE = {")], ns)
sched_T, ts = ns["sched_T"], ns["ts"]
ev = json.load(open("release_events.json")); condT = {}; win = {}; closed = {}
for e in ev:
    T = sched_T(e["slug"])
    for m in e["markets"]:
        if T: condT[m["cond"]] = (T, e["slug"])
        if m.get("prices"):
            pr = [float(x) for x in json.loads(m["prices"])]
            if max(pr) >= 0.99: win[m["cond"]] = pr.index(max(pr))
        if m.get("closed"): closed[m["cond"]] = calendar.timegm(time.strptime(m["closed"][:19], "%Y-%m-%d %H:%M:%S"))
US = sorted({ts(t) for pat, t in ns["SCHED"] if re.search(r"unemployment|inflation-us|ppi|pce|ism|fed-decision", pat)})
print("### (1) jozeslemsek: FIFO round trips per token, all markets, 88 days")
fills = sorted(pickle.load(open(f"{P}/fills_jozeslemsek.pkl", "rb")), key=lambda r: r["timestamp"])
inv = collections.defaultdict(collections.deque); trips = []; unmatched_sell = 0.0
for r in fills:
    k = r["token_id"]
    if r["side"] == "BUY": inv[k].append([r["size"], r["price"], r["timestamp"], r["role"]])
    else:
        left = r["size"]
        while left > 1e-9 and inv[k]:
            lot = inv[k][0]; q = min(left, lot[0])
            trips.append((q, lot[1], r["price"], r["timestamp"] - lot[2], lot[3], r["role"], r["condition_id"]))
            lot[0] -= q; left -= q
            if lot[0] <= 1e-9: inv[k].popleft()
        unmatched_sell += left * r["price"]
pnl = sum(q * (s - b) for q, b, s, *_ in trips); cost = sum(q * b for q, b, *_ in trips)
print(f"  round trips: {len(trips)} lots, cost {cost:.0f}, pnl {pnl:.0f} ({100*pnl/cost:.0f}% of cost); sells of older inventory {unmatched_sell:.0f}; unsold cost {sum(l[0]*l[1] for d in inv.values() for l in d):.0f}")
for lo, hi in ((0, 1.5), (1.5, 3), (3, 10), (10, 1e9)):
    sel = [(q, b, s) for q, b, s, *_ in trips if b > 0 and lo <= s / b < hi]
    print(f"   sell/buy ratio {lo}-{hi}: lots={len(sel):5d} cost={sum(q*b for q,b,s in sel):7.0f} pnl={sum(q*(s-b) for q,b,s in sel):7.0f}")
sel = [(q, b, s) for q, b, s, *_ in trips if s < b]; print(f"   losing lots: {len(sel)} pnl={sum(q*(s-b) for q,b,s in sel):.0f}")
hold = sorted(h for q, b, s, h, *_ in trips); print(f"   holding time: median {hold[len(hold)//2]/3600:.1f} h, p90 {hold[int(len(hold)*.9)]/86400:.1f} d; buy price median {st.median(b for q,b,*_ in trips):.4f}; maker share of buys {sum(q*b for q,b,s,h,rb,rs,c in trips if rb=='M')/cost:.2f}, of sells {sum(q*s for q,b,s,h,rb,rs,c in trips if rs=='M')/sum(q*s for q,b,s,*_ in trips):.2f}")
bym = collections.Counter()
for q, b, s, h, rb, rs, c in trips: bym[c] += q * (s - b)
top = bym.most_common(10); print(f"   markets with round trips: {len(bym)}, positive {sum(1 for v in bym.values() if v > 0)}; top-10 markets pnl {sum(v for _, v in top):.0f} of {pnl:.0f}")
bymonth = collections.Counter()
for r in fills: bymonth[f(r['timestamp'])[:2]] += 1
print("   fills by month:", dict(bymonth))

print("\n### (2) release snipers: every fill in release-event markets, lag to the scheduled release")
for label in ("TheElement115", "road2million", "makeit99"):
    fl = pickle.load(open(f"{P}/fills_{label}.pkl", "rb")); rows = []
    for r in fl:
        if r["condition_id"] in condT:
            T, slug = condT[r["condition_id"]]; lag = r["timestamp"] - T
            if 0 <= lag < 600: rows.append((lag, r["price"], r["size"] * r["price"], slug, r["role"], r["side"], T))
    lags = sorted(x[0] for x in rows)
    if not lags: continue
    evs = collections.defaultdict(list)
    for x in rows: evs[(x[6], x[3].split("-20")[0][:28])].append(x)
    print(f"  {label}: {len(rows)} fills in {len(evs)} events; lag s: min {lags[0]}, median {lags[len(lags)//2]}, p90 {lags[int(len(lags)*.9)]}, max {lags[-1]}; price median {st.median(x[1] for x in rows):.2f}; usd/fill median {st.median(x[2] for x in rows):.0f}, max {max(x[2] for x in rows):.0f}; takers {sum(1 for x in rows if x[4]=='T')}/{len(rows)}")
    print("     per release day: " + "; ".join(f"{f(T)[:11]} {s[:14]} n={len(v)} lag={min(x[0] for x in v)}-{max(x[0] for x in v)}s ${sum(x[2] for x in v):.0f}" for (T, s), v in sorted(evs.items())[:14]))
    print(f"     release days covered: {len({T for (T, s) in evs})} of {len(set(t for t, _ in condT.values()))} scheduled times in the sample")

print("\n### (3) Ahpo / ATCapital / GoldmanSachs: taker fills in OTHER econ markets within 120 s after a US release")
for label in ("Ahpo", "ATCapital", "GoldmanSachs", "perfectnosta"):
    fl = sorted(pickle.load(open(f"{P}/fills_{label}.pkl", "rb")), key=lambda r: r["timestamp"]); n = 0
    for r in fl:
        if r["condition_id"] in condT or r["role"] != "T": continue
        i = bisect.bisect_right(US, r["timestamp"]) - 1
        if i >= 0 and r["timestamp"] - US[i] < 120 and re.search(r"fed|rate|inflation|recession", r.get("slug") or ""):
            n += 1
            if n <= 7: print(f"  {label:12} {f(r['timestamp'])} lag={r['timestamp']-US[i]:3d}s {r['side']:4} {r['outcome']:3} px={r['price']:.3f} usd={r['size']*r['price']:8.0f} {r['slug'][:62]}")
    print(f"  {label}: {n} such taker fills")

print("\n### (4) carry after the release: taker-long-winner fills at 0.95 <= pw < 0.999, later than 60 s after the release, until resolution")
tot = [0, 0.0, 0.0]; rows = []
for e in ev:
    T = sched_T(e["slug"])
    if not T: continue
    a = [0, 0.0, 0.0, []]
    for m in e["markets"]:
        c = m["cond"]; p = f"{P}/{c}.json"
        if c not in win or not os.path.exists(p): continue
        for t, w, side, oi, px, sz, name in json.load(open(p)):
            pw = px if oi == win[c] else 1 - px; lw = (side == "BUY") == (oi == win[c])
            if t > T + 60 and lw and 0.95 <= pw < 0.999:
                a[0] += 1; a[1] += pw * sz; a[2] += (1 - pw) * sz - 0.01 * pw * (1 - pw) * sz; a[3].append(((closed.get(c, t) - t) / 3600, pw * sz))
    if a[0]:
        hrs = sorted(a[3]); wavg = sum(h * u for h, u in hrs) / a[1]
        rows.append((e["slug"][:40], a[0], a[1], a[2], wavg)); tot[0] += a[0]; tot[1] += a[1]; tot[2] += a[2]
for r in sorted(rows, key=lambda r: -r[3])[:14]:
    print(f"  {r[0]:40} fills={r[1]:4d} usd={r[2]:9.0f} profit={r[3]:7.0f} ({100*r[3]/r[2]:.2f}%) usd-weighted hours to close={r[4]:6.1f}")
print(f"  TOTAL {len(rows)} events: fills={tot[0]} usd={tot[1]:.0f} profit after fee={tot[2]:.0f} ({100*tot[2]/tot[1]:.2f}% of capital)")
