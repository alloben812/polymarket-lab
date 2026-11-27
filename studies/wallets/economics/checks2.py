"""(5) FIFO round trips in economics markets for the directional accounts: holding period, realised P&L, how positions end.
(6) Calibration of economics release markets: Yes price N time before the release vs outcome (is 'buy the favourite' enough?)."""
import json, sys, pickle, collections, calendar, time, re, statistics as st, os
P = "/home/user/polymarket-lab/data/econ_tapes"
ECON = re.compile(r"(fed|fomc|interest-rate|rate-cut|rate-hike|bps|cpi|inflation|jobs|payroll|unemployment|gdp|recession|ecb|bank-of-|pce|ppi|treasury|overheating|ism-)", re.I)
print("### (5) FIFO round trips, economics markets only")
for label in ("perfectnosta", "GoldmanSachs", "Ahpo", "0x831449c4b9", "Stonktrader", "ATCapital"):
    fills = sorted(pickle.load(open(f"{P}/fills_{label}.pkl", "rb")), key=lambda r: r["timestamp"])
    d = json.load(open(f"{label}_88d.json")); mk = {m["condition"]: m for m in d["_markets"]}
    inv = collections.defaultdict(collections.deque); trips = []; buys = 0.0
    for r in fills:
        if not ECON.search((r.get("event_slug") or "") + " " + (r.get("slug") or "")): continue
        k = r["token_id"]
        if r["side"] == "BUY":
            inv[k].append([r["size"], r["price"], r["timestamp"], r["condition_id"], r["outcome"]]); buys += r["size"] * r["price"]
        else:
            left = r["size"]
            while left > 1e-9 and inv[k]:
                lot = inv[k][0]; q = min(left, lot[0]); trips.append((q, lot[1], r["price"], r["timestamp"] - lot[2])); lot[0] -= q; left -= q
                if lot[0] <= 1e-9: inv[k].popleft()
    sold_cost = sum(q * b for q, b, s, h in trips); pnl = sum(q * (s - b) for q, b, s, h in trips)
    held_res = held_open = res_pnl = 0.0
    for dq in inv.values():
        for q, b, t, c, o in dq:
            m = mk.get(c) or {}
            if m.get("resolved") and m.get("final"):
                held_res += q * b; res_pnl += q * (float(m["final"].get(o) or 0) - b)
            else: held_open += q * b
    hs = sorted((h, q * b) for q, b, s, h in trips); tot = sum(u for _, u in hs) or 1; acc = 0; med = 0
    for h, u in hs:
        acc += u
        if acc >= tot / 2: med = h; break
    print(f"  {label:13} buys ${buys:9.0f}: sold before resolution ${sold_cost:9.0f} ({100*sold_cost/buys if buys else 0:3.0f}%) pnl {pnl:8.0f}, usd-weighted median hold {med/3600:7.1f} h | held to resolution ${held_res:8.0f} pnl {res_pnl:7.0f} | still open ${held_open:8.0f}")

print("\n### (6) calibration: Yes-price before the release vs outcome, all release-event markets with tapes (Fed tapes start T-4d)")
src = open("release_analysis_v2.py").read(); ns = {}
exec("import calendar, time\ndef ts(s): return calendar.timegm(time.strptime(s, '%Y-%m-%d %H:%M'))\n" + src[src.index("SCHED = ["):src.index("OVERRIDE = {")], ns)
ev = json.load(open("release_events.json"))
for name, back in (("7 days before", 7 * 86400), ("1 day before", 86400), ("1 hour before", 3600)):
    bk = collections.defaultdict(lambda: [0, 0.0, 0.0, set()])
    for e in ev:
        T = ns["sched_T"](e["slug"])
        if not T: continue
        for m in e["markets"]:
            p = f"{P}/{m['cond']}.json"
            if not m.get("prices") or not os.path.exists(p): continue
            pr = [float(x) for x in json.loads(m["prices"])]
            if max(pr) < 0.99: continue
            rows = sorted(json.load(open(p))); last = None
            for t, w, side, oi, px, sz, nm in rows:
                if t > T - back: break
                if t > T - back - 3 * 86400: last = px if oi == 0 else 1 - px
            if last is None: continue
            for side_name, price, won in (("Yes", last, pr[0] > 0.5), ("No", 1 - last, pr[1] > 0.5)):   # both sides as separate bets
                for lo, hi in ((0, .1), (.1, .3), (.3, .5), (.5, .7), (.7, .9), (.9, .97), (.97, 1.01)):
                    if lo <= price < hi:
                        b = bk[(lo, hi)]; b[0] += 1; b[1] += price; b[2] += 1.0 if won else 0.0; b[3].add(e["slug"])
    print(f"  {name}:")
    for k in sorted(bk):
        b = bk[k]; n = b[0]; avg = b[1] / n; wr = b[2] / n
        print(f"     price {k[0]:.2f}-{k[1]:.2f}: bets={n:4d} events={len(b[3]):2d} avg price={avg:.3f} win rate={wr:.3f} edge per $1 share={wr-avg:+.3f} (after 1% fee {wr-avg-0.01*avg*(1-avg):+.3f})")
