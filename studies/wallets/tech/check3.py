"""Falsification checks. (1) first-mover test for the snipers; (2) how fast the gap closes; (3) reversal risk after the
jump; (4) does 0xAee8611B trade in bursts aligned with leaderboard updates or on a clock; (5) melonmanm late buys;
(6) who are the fastest wallets."""
import bisect, collections, statistics as st
from common import *
from race import INFO, JUMP, APP, groups, appearance, pw_rows, check_time, tape, NAMES
def side_px(c, outcome, t):
    rows = pw_rows(c); i = bisect.bisect_right([r[0] for r in rows], t) - 1
    if i < 0: return None
    return rows[i][1] if outcome == INFO[c]["winner"] else 1 - rows[i][1]
ev_markets = collections.defaultdict(list)
for c in INFO: ev_markets[INFO[c]["event"]].append(c)
print("(1) taker buys in debut markets inside the 40 h before the check: was the account the first to move the price?")
print(f"{'account':14} {'fills':>5} {'mkts':>4} {'right':>5} {'pre_px':>6} {'fill_px':>7} {'px+10m':>6} {'quiet10m':>8} {'quiet60s':>8} {'lead<=5s':>8} {'net_usd':>8}   pre_px = bought side on the tape 10 s before; quiet = no other trade in the event's cached markets in the window before the fill; lead = fill within 5 s of the first trade of its burst")
for name in ACC:
    d = load(name); bym = {m["condition"]: m for m in d["_markets"]}
    n = right = q10 = q60 = lead = 0; pre = []; fp = []; post = []; net = 0.0; mk = set()
    for r in d["_fills"]:
        c = r["condition_id"]
        if c not in JUMP or r["side"] != "BUY" or r["role"] != "T" or "debut" not in (bym[c]["event"] or ""): continue
        chk = check_time(bym[c]["closed_at"]); t = r["timestamp"]
        if not (chk - 40 * 3600 <= t <= chk) or float(r["price"]) >= 0.97: continue
        allt = sorted(x[0] for cc in ev_markets[bym[c]["event"]] for x in tape(cc))
        i = bisect.bisect_left(allt, t - 3); prev = allt[i - 1] if i > 0 else None
        n += 1; mk.add(c); w = r["outcome"] == INFO[c]["winner"]; right += w
        q10 += prev is None or t - prev > 600; q60 += prev is None or t - prev > 60
        # first trade of the burst it belongs to: walk back while gaps < 60 s
        j = bisect.bisect_right(allt, t) - 1; k = j
        while k > 0 and allt[k] - allt[k - 1] < 60: k -= 1
        lead += t - allt[k] <= 5
        p0 = side_px(c, r["outcome"], t - 10); p1 = side_px(c, r["outcome"], t + 600)
        if p0 is not None: pre.append(p0)
        if p1 is not None: post.append(p1)
        fp.append(float(r["price"])); net += ((1.0 if w else 0.0) - float(r["price"])) * float(r["size"]) - float(r["size"]) * 0.05 * float(r["price"]) * (1 - float(r["price"]))
    if n: print(f"{name:14} {n:5d} {len(mk):4d} {right/n:5.2f} {st.mean(pre) if pre else float('nan'):6.3f} {st.mean(fp):7.3f} {st.mean(post) if post else float('nan'):6.3f} {q10/n:8.2f} {q60/n:8.2f} {lead/n:8.2f} {net:8.0f}")
print("\n(2) gap money by seconds after the first sweep (20 events, taker buys of the eventual winner below 0.97, edge = 1 - price):")
buckets = collections.OrderedDict((k, 0.0) for k in ("<=3s", "3-10s", "10-60s", "1-10m", "10m-6h", ">6h")); wall = collections.defaultdict(set); cost = collections.defaultdict(float)
for k, t0 in APP.items():
    if not t0: continue
    for c in groups[k]:
        for t, pw, usd, wal, bw, sh in pw_rows(c):
            if t0 - 5 <= t <= k[1] and bw and pw < 0.97:
                x = t - t0; b = "<=3s" if x <= 3 else "3-10s" if x <= 10 else "10-60s" if x <= 60 else "1-10m" if x <= 600 else "10m-6h" if x <= 21600 else ">6h"
                buckets[b] += sh * (1 - pw); wall[b].add(wal); cost[b] += sh * pw
tot = sum(buckets.values())
print("   " + " | ".join(f"{b}: ${v:.0f} ({v/tot:.0%}, {len(wall[b])} wallets, cost ${cost[b]:.0f}, {100*v/(cost[b]+v) if cost[b] else 0:.1f}c/sh)" for b, v in buckets.items()))
print("\n(3) reversal risk: price of each cached sibling 10 min after the first sweep vs the final outcome")
cnt = collections.Counter()
for k, t0 in APP.items():
    if not t0: continue
    for c in groups[k]:
        rows = pw_rows(c); i = bisect.bisect_right([r[0] for r in rows], t0 + 600) - 1
        if i < 0: continue
        pw = rows[i][1]
        cnt["winner>=0.97" if pw >= 0.97 else "winner 0.90-0.97" if pw >= 0.9 else "0.10-0.90 undecided" if pw > 0.1 else "winner<=0.10 (market was confidently WRONG)"] += 1
print("   ", dict(cnt))
print("\n(4) 0xAee8611B bursts")
d = load("0xAee8611B"); ts = sorted(r["timestamp"] for r in d["_fills"])
b10 = collections.defaultdict(set)
for r in d["_fills"]: b10[r["timestamp"] // 10].add(r["condition_id"])
big = sorted(k * 10 for k, v in b10.items() if len(v) >= 8)
starts = [t for i, t in enumerate(big) if i == 0 or t - big[i - 1] > 600]
mins = collections.Counter((t // 60) % 60 // 5 * 5 for t in starts); hrs = collections.Counter(dt.datetime.fromtimestamp(t, dt.timezone.utc).hour for t in starts)
print(f"   bursts touching >=8 markets within 10 s: {len(starts)} over 88 days; by 5-minute slot of the hour {dict(sorted(mins.items()))}; by UTC hour {dict(sorted(hrs.items()))}")
apps = sorted({t0 for t0 in APP.values() if t0})
hit = 0
for t0 in apps:
    near = [t for t in ts if t0 - 60 <= t <= t0 + 600]; hit += len(near) > 0
print(f"   distinct first-sweep moments in debut markets: {len(apps)}; 0xAee8611B has any fill within -60 s..+10 min of them: {hit} (its base rate: {len({t//660 for t in ts})/(88*86400/660):.2f} of all 11-minute slots contain a fill)")
gaps = [starts[i + 1] - starts[i] for i in range(len(starts) - 1)]
print(f"   hours between bursts q25/q50/q75: {sorted(gaps)[len(gaps)//4]/3600:.1f}/{sorted(gaps)[len(gaps)//2]/3600:.1f}/{sorted(gaps)[3*len(gaps)//4]/3600:.1f}")
bym = {m["condition"]: m for m in d["_markets"]}
done = [m for m in d["_markets"] if m["resolved"] and m["sub"] == "arena"]
print(f"   resolved arena markets {len(done)}: net incl. incomplete {sum(m['net'] for m in done):.0f}; complete only {sum(m['net'] for m in done if not m['incomplete']):.0f}; turnover {sum(m['turnover'] for m in done):.0f}; fees {sum(m['fee'] for m in done):.0f}")
print("\n(5) melonmanm tech buys at >= 0.95 (resolved markets): ")
d = load("melonmanm"); bym = {m["condition"]: m for m in d["_markets"]}
agg = collections.defaultdict(lambda: [0, 0.0, 0.0, 0.0, set(), 0.0])
for r in d["_fills"]:
    m = bym[r["condition_id"]]
    if r["side"] != "BUY" or not m["resolved"] or float(r["price"]) < 0.95: continue
    fin = m.get("final") or {}; val = float(fin.get(r["outcome"]) or 0); p, s = float(r["price"]), float(r["size"])
    k = ("tech" if m["tech"] else "non-tech", r["role"]); a = agg[k]; a[0] += 1; a[1] += s * p; a[2] += (val - p) * s; a[3] += s * 0.05 * p * (1 - p) if r["role"] == "T" else 0; a[4].add(m["condition"]); a[5] += s * p * (val < 0.5)
for k, a in sorted(agg.items()): print(f"   {k}: fills {a[0]}, markets {len(a[4])}, cost ${a[1]:.0f}, gross ${a[2]:.0f}, fee ${a[3]:.0f}, $ lost-side share {a[5]/a[1]:.3f}")
hold = []
for r in d["_fills"]:
    m = bym[r["condition_id"]]
    if r["side"] == "BUY" and m["tech"] and float(r["price"]) >= 0.95 and m.get("closed_at"): hold.append((m["closed_at"] - r["timestamp"]) / 3600)
if hold: print(f"   tech >=0.95 buys: hours to close q25/q50/q75 {sorted(hold)[len(hold)//4]:.1f}/{st.median(hold):.1f}/{sorted(hold)[3*len(hold)//4]:.1f}")
print("\n(6) fastest wallets outside the study list")
for w in ["0x09e27c2cbcd9", "0xa7d2ec6680f4", "0xa2770432a5e6", "0x5a218c7ad041", "0x64ff984a6d29", "0x564f22744b79"]:
    full = next((x[3] for c in INFO for x in pw_rows(c) if x[3].startswith(w)), None)
    if not full: continue
    try:
        s = dataapi.user_stats(full); p = s.get("all_time_pnl") or {}
        print(f"   {full} {s.get('name') or s.get('pseudonym') or ''}: kept_all {p.get('economic_pnl') or 0:.0f}, gross {p.get('trade_pnl') or 0:.0f}, fees {p.get('fees') or 0:.0f}, rebates {(p.get('taker_rebate') or 0)+(p.get('maker_rebate') or 0)+(p.get('reward_income') or 0):.0f}, fills {p.get('trade_count') or 0:.0f}, markets {s.get('trades')}, volume {p.get('volume_usdc') or 0:.0f}")
    except Exception as e: print("   ", full, "error", str(e)[:80])
