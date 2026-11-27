"""Sceptic: Ahpo's taker fills in the first 60 s after 12:30/13:30/18:00/19:00 UTC (Sep-Nov), marked to the raw market tape
5 minutes and 1 hour later (last print at or before that time, converted to the outcome traded). Fee 0.04 before 11-21."""
import pickle, json, os, re, bisect, collections, datetime as dt
A = "0xcdb1f1ef8213c06911e4ba6a884176c5571e276c"; TP = "/home/user/polymarket-lab/data/econ_tapes"
ECON = re.compile(r"(fed|fomc|interest-rate|rate-cut|rate-hike|bps|cpi|inflation|jobs|payroll|unemployment|gdp|recession|ecb|bank-of-|pce|ppi|treasury|overheating|ism-)", re.I)
F = pickle.load(open(f"{TP}/fills_Ahpo.pkl", "rb")); f_ = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%m-%d %H:%M:%S")
fast = sorted([f for f in F if f["role"] == "T" and ECON.search((f.get("event_slug") or "") + " " + f["slug"]) and any(0 <= (f["timestamp"] % 86400) - s <= 60 for s in (45000, 48600, 64800, 68400))], key=lambda f: f["timestamp"])
tot = collections.defaultdict(float); n = 0
for f in fast:
    c = f["condition_id"]; p = next((x for x in (f"{TP}/{c}.json", f"{TP}/fedDec_{c}.json") if os.path.exists(x)), None)
    usd = f["size"] * f["price"]; line = f"{f_(f['timestamp'])} {f['side']:4} {f['outcome']:3} {f['size']:8.0f} @ {f['price']:.3f} ${usd:7.0f} {f['slug'][:52]:52}"
    if not p: print(line, "no cached tape"); tot["no_tape_usd"] += usd; continue
    rows = sorted(json.load(open(p))); ts_ = [r[0] for r in rows]
    if not (ts_[0] <= f["timestamp"] <= ts_[-1]): print(line, "tape does not cover"); tot["no_tape_usd"] += usd; continue
    oi = 0 if f["outcome"] == "Yes" else 1
    def px(t):
        i = bisect.bisect_right(ts_, t) - 1; r = rows[i]; return r[4] if r[3] == oi else 1 - r[4]
    T0 = f["timestamp"] - (f["timestamp"] % 1800); pre = px(T0 - 1)
    s = 1 if f["side"] == "BUY" else -1; fee = (0.04 if f["timestamp"] < 1795305600 else 0.01) * f["size"] * f["price"] * (1 - f["price"])
    m5, m60 = px(f["timestamp"] + 300), px(f["timestamp"] + 3600)
    p5, p60 = s * (m5 - f["price"]) * f["size"] - fee, s * (m60 - f["price"]) * f["size"] - fee
    print(line, f"pre {pre:.3f} +5min {m5:.3f} +1h {m60:.3f} pnl@1h {p60:7.0f}")
    tot["usd"] += usd; tot["p5"] += p5; tot["p60"] += p60; n += 1; tot["pos"] += p60 > 0
print(f"\nfast taker fills {len(fast)}; marked {n}, ${tot['usd']:.0f}: P&L after fee at +5 min {tot['p5']:.0f}, at +1 h {tot['p60']:.0f}; positive at +1 h {tot['pos']:.0f}/{n}; without a tape ${tot['no_tape_usd']:.0f}")
