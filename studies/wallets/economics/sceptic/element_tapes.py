"""Sceptic check 3 for TheElement115: raw whole-market tapes (fresh from the Data API) for markets OUTSIDE the analyst's
53-event sample. For each: last winner-equivalent price before the quarter-hour boundary T, every fill from T-120 s to
T+45 s, the wallet's place in the queue, the first print at >= 0.95, and any buying of the winner in the 10 minutes before T."""
import pickle, json, collections, datetime as dt, os, sys
from pmlab import dataapi
P = "/home/user/polymarket-lab/data/econ_tapes/sceptic_%s.pkl"
W = "0x8cb3ed8b82e59276ceaef9799287f51dbb450114"
fills = pickle.load(open(P % "TheElement115", "rb"))["fills"]
sample = {m["cond"] for e in json.load(open("../release_events.json")) for m in e["markets"]}
f_ = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%m-%d %H:%M:%S")
cand = [f for f in fills if f["condition_id"] not in sample and f["size"] * f["price"] >= 100 and f["side"] == "BUY"]
print("fills >= $100 outside the analyst's sample:", len(cand), "in", len({f["condition_id"] for f in cand}), "markets")
cand.sort(key=lambda f: -(1 - f["price"]) * f["size"])
seen = []; 
for f in cand:
    if f["condition_id"] not in [g["condition_id"] for g in seen]: seen.append(f)
pick = seen[:9]
res = dataapi.resolutions([f["condition_id"] for f in pick])
summary = []
for f in pick:
    c = f["condition_id"]; cp = f"/home/user/polymarket-lab/data/econ_tapes/sceptic_tape_{c}.pkl"
    if os.path.exists(cp): tape = pickle.load(open(cp, "rb"))
    else:
        tape = [{k: r.get(k) for k in ("timestamp", "proxy_wallet", "side", "outcome", "price", "size", "name")} for r in dataapi.iter_trades(condition=c, max_rows=40000)]
        pickle.dump(tape, open(cp, "wb"))
    tape.sort(key=lambda r: r["timestamp"])
    win = max(res[c]["final"], key=lambda o: float(res[c]["final"][o] or 0))
    T = f["timestamp"] - f["timestamp"] % 900
    if f["timestamp"] % 900 > 60: T = f["timestamp"] - 30     # unscheduled second (press conference): look at the 30 s before the fill
    def pw(r): return r["price"] if r["outcome"] == win else 1 - r["price"]
    def lw(r): return (r["side"] == "BUY") == (r["outcome"] == win)
    before = [r for r in tape if r["timestamp"] < T]
    pre = pw(before[-1]) if before else None
    pre10 = [r for r in before if r["timestamp"] >= T - 600]
    lead = sum(r["size"] * pw(r) for r in pre10 if lw(r)); lead_n = sum(1 for r in pre10 if lw(r)); anti = sum(r["size"] * pw(r) for r in pre10 if not lw(r))
    after = [r for r in tape if T <= r["timestamp"] <= T + 45]
    first95 = next((r["timestamp"] - T for r in tape if r["timestamp"] >= T and pw(r) >= 0.95), None)
    mine = [r for r in after if r["proxy_wallet"] == W]
    ahead = [r for r in after if lw(r) and mine and r["timestamp"] < mine[0]["timestamp"] and r["proxy_wallet"] != W]
    sameblk = [r for r in after if lw(r) and mine and r["timestamp"] == mine[0]["timestamp"] and r["proxy_wallet"] != W]
    late = [r for r in tape if r["timestamp"] > T + 45 and lw(r) and pw(r) < 0.95]
    print(f"\n{f['slug'][:80]}  winner={win}  tape rows={len(tape)}  T={f_(T)}{' (not a quarter hour: fill-30s)' if f['timestamp']%900>60 else ''}")
    print(f"   last price before T (winner-equivalent) {pre}; last trade before T at {f_(before[-1]['timestamp']) if before else None}; 10 min before T: buys of the winner {lead_n} fills ${lead:.0f}, sells of it ${anti:.0f}")
    for r in after[:14]:
        tag = "<== TheElement115" if r["proxy_wallet"] == W else (r.get("name") or r["proxy_wallet"][:10])
        print(f"   +{r['timestamp']-T:3d}s {r['side']:4} {r['outcome']:3} px={r['price']:.3f} winner-eq={pw(r):.3f} sh={r['size']:8.0f} {'long-winner' if lw(r) else 'short-winner'}  {tag}")
    print(f"   first print >= 0.95 at +{first95}s; takers long the winner before it in the window: {len(ahead)} fills ${sum(r['size']*pw(r) for r in ahead):.0f}; in its block: {len(sameblk)} fills ${sum(r['size']*pw(r) for r in sameblk):.0f}; stale buys (<0.95) later than +45 s: {len(late)} fills ${sum(r['size']*pw(r) for r in late):.0f}")
    summary.append({"slug": f["slug"], "T": T, "pre": pre, "lag": mine[0]["timestamp"] - T if mine else None, "px": f["price"], "first95": first95, "ahead": len(ahead), "lead_usd": lead})
json.dump(summary, open("element_tapes.json", "w"))
print("\nSUMMARY"); 
for s in summary: print(f"  {f_(s['T'])} pre={s['pre']} lag={s['lag']}s paid={s['px']:.3f} first95=+{s['first95']}s ahead={s['ahead']} lead_buys_10min=${s['lead_usd']:.0f}  {s['slug'][:50]}")
