"""HighTempTation: timing of each NO purchase relative to the routine observation that made the bucket impossible."""
import json, sys, bisect, collections, datetime as dt, math
sys.path.insert(0, "/home/user/polymarket-lab")
ACCT = sys.argv[1] if len(sys.argv) > 1 else "HighTempTation"
F = json.load(open("out/fills.json"))[ACCT]; MK = json.load(open("out/mk.json")); OBS = json.load(open("out/obs2.json"))
def whole(t, unit):
    v = t / 10.0 if unit == "C" else t / 10.0 * 9 / 5 + 32
    return math.floor(v + 0.5 + 1e-9)
u = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%m-%d %H:%M:%S")
bym = collections.defaultdict(list)
for r in F: bym[r["condition_id"]].append(r)
dts = []; n_no = 0; rows = []
for c, fl in bym.items():
    d = MK.get(c)
    if not d or not d["ok"] or d["kind"] != "hi": continue
    obs = [(t, whole(v, d["unit"])) for t, v, _ in OBS.get(d["station"], []) if v is not None and d["est"] <= t < d["est"] + 86400]
    kill = next((t for t, w in obs if w > d["hi"]), None)       # first routine obs above the bucket top
    reach = next((t for t, w in obs if w >= d["lo"]), None)
    fl.sort(key=lambda r: r["timestamp"])
    buys = [r for r in fl if r["side"] == "BUY"]; sells = [r for r in fl if r["side"] == "SELL"]
    for r in buys:
        if r["outcome"] == "No":
            n_no += 1
            dts.append((r["timestamp"] - 3 - kill) if kill else None)
    b = buys[0] if buys else None
    rows.append((d["slug"][20:], d["station"], (d["final"] or {}).get("Yes"), u(kill) if kill else "never", 
                 "; ".join(f"{r['role']} {r['side']} {r['outcome']} {r['size']:.0f}@{r['price']:.3f} {u(r['timestamp'])} (kill{(r['timestamp']-3-kill)/60:+.1f}m lh={((r['timestamp']-d['est'])/3600):.1f})" if kill else f"{r['role']} {r['side']} {r['outcome']} {r['size']:.0f}@{r['price']:.3f} {u(r['timestamp'])} (no-kill lh={((r['timestamp']-d['est'])/3600):.1f})" for r in fl[:4])))
have = [x for x in dts if x is not None]
print(ACCT, "NO purchases:", n_no, "| bucket never exceeded by a routine obs (IEM):", dts.count(None), "| with kill obs:", len(have))
edges = [-1e9, -3600, -600, 0, 120, 300, 600, 1800, 3600, 4 * 3600, 1e9]
lab = ["<-60m", "-60..-10m", "-10..0m", "0..2m", "2..5m", "5..10m", "10..30m", "30..60m", "1..4h", ">4h"]
cnt = collections.Counter(lab[bisect.bisect_right(edges, x) - 1] for x in have)
print("fill time minus kill-observation time stamp:", {k: cnt[k] for k in lab})
import random; random.seed(3); random.shuffle(rows)
for r in rows[:22]: print(" | ".join(str(x) for x in r))
